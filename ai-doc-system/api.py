#!/usr/bin/env python3
"""
api.py — FastAPI async-job wrapper around pipeline.py.

The pipeline takes 1–5 minutes, so we use a background-thread job pattern:
  POST /api/jobs       → enqueue & return { job_id, status: "queued" }
  GET  /api/jobs/{id}  → poll progress
  GET  /api/jobs/{id}/download/{doc_type}  → stream HLD / LLD file
  GET  /health         → liveness probe
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
from typing import Optional
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask
import zipfile

# ── Load .env (if present) before reading any env vars ───────────────
load_dotenv()

# ── In-memory job store ──────────────────────────────────────────────
# NOTE: This dict lives in a single process. If you scale to multiple
# instances behind a load balancer, replace with Redis or a shared DB.
job_store: dict[str, dict] = {}

# ── App ──────────────────────────────────────────────────────────────
app = FastAPI(title="DocAI API", version="2.0.0")

# ── CORS — origins from env, never hard-coded ────────────────────────
_raw_origins = os.environ.get("CORS_ORIGINS", "http://localhost:4200")
_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Env helpers ──────────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", "8000"))
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "./outputs")
PIPELINE_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline.py")


# ── Request / Response models ────────────────────────────────────────
class JobRequest(BaseModel):
    source_type: str            # "folder" | "github" | "code"
    value: str                  # path, URL, or raw code
    filename: Optional[str] = None   # only for source_type="code"
    use_llm: Optional[bool] = False


class JobCreatedResponse(BaseModel):
    job_id: str
    status: str  # "queued"


# ── Helper: locate output files ─────────────────────────────────────
def _find_file(directory: str, names: list[str]) -> str | None:
    """Walk *directory* looking for the first file whose name matches."""
    for root, _, files in os.walk(directory):
        for name in names:
            if name in files:
                return os.path.join(root, name)
    return None


# ── Pipeline runner (executed in a background thread) ────────────────
def _run_pipeline_job(job_id: str, repo_path: str, use_llm: bool) -> None:
    """
    Blocking call that runs pipeline.py as a subprocess.
    Updates ``job_store[job_id]`` in-place as it progresses.
    """
    job = job_store[job_id]
    job["status"] = "running"
    job["current_step"] = "starting pipeline"

    # Build output dir — use OUTPUT_DIR env var, else beside the repo
    repo_basename = os.path.basename(repo_path.rstrip("/"))
    if OUTPUT_DIR and OUTPUT_DIR != "./outputs":
        output_dir = os.path.join(os.path.abspath(OUTPUT_DIR), repo_basename)
    else:
        output_dir = os.path.join(
            os.path.dirname(repo_path.rstrip("/")),
            repo_basename + "-docs",
        )
    os.makedirs(output_dir, exist_ok=True)

    cmd = [sys.executable, PIPELINE_SCRIPT, repo_path, "--output", output_dir]
    if use_llm:
        cmd += ["--llm", OLLAMA_MODEL]

    job["current_step"] = "running pipeline subprocess"

    # Pass env vars so child process (pipeline → llm_client) inherits them
    child_env = {**os.environ, "OLLAMA_HOST": OLLAMA_HOST}

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(PIPELINE_SCRIPT),
            env=child_env,
        )

        if result.returncode != 0:
            job["status"] = "failed"
            # Surface last 2 000 chars of stderr for debugging
            job["error"] = (result.stderr or "unknown error")[-2000:]
            job["current_step"] = None
            try:
                from db import job_logs
                completed_at = datetime.now(timezone.utc)
                # Compute duration from the stored created_at
                log_doc = job_logs.find_one({"job_id": job_id})
                duration = None
                if log_doc and log_doc.get("created_at"):
                    duration = (completed_at - log_doc["created_at"]).total_seconds()
                update_fields: dict = {
                    "status": "failed",
                    "error": job["error"],
                    "completed_at": completed_at,
                }
                if duration is not None:
                    update_fields["duration_seconds"] = round(duration, 1)
                job_logs.update_one(
                    {"job_id": job_id},
                    {"$set": update_fields}
                )
            except Exception:
                pass
            return

        # ── Locate generated artefacts ──────────────────────────
        hld_path = (
            _find_file(output_dir, ["HLD.docx", "hld.docx"])
            or _find_file(output_dir, ["HLD.md", "hld.md"])
        )
        lld_path = (
            _find_file(output_dir, ["LLD.docx", "lld.docx"])
            or _find_file(output_dir, ["LLD.md", "lld.md"])
        )
        commented_dir = os.path.join(output_dir, "commented_code")

        # Check if Ollama was requested but might have been unreachable
        warning = None
        if use_llm and result.stderr and "ollama" in result.stderr.lower():
            warning = (
                "LLM (Ollama) may have been unreachable; pipeline fell back "
                "to AST-only analysis. Check stderr for details."
            )

        job["status"] = "done"
        job["current_step"] = None
        job["warning"] = warning
        job["files"] = {
            "hld": hld_path,
            "lld": lld_path,
            "commented_code_dir": (
                commented_dir if os.path.isdir(commented_dir) else None
            ),
        }
        try:
            from db import job_logs
            completed_at = datetime.now(timezone.utc)
            log_doc = job_logs.find_one({"job_id": job_id})
            duration = None
            if log_doc and log_doc.get("created_at"):
                duration = (completed_at - log_doc["created_at"]).total_seconds()
            update_fields: dict = {
                "status": "done",
                "files": job["files"],
                "completed_at": completed_at,
            }
            if duration is not None:
                update_fields["duration_seconds"] = round(duration, 1)
            job_logs.update_one(
                {"job_id": job_id},
                {"$set": update_fields}
            )
        except Exception:
            pass

    except Exception as exc:
        job["status"] = "failed"
        job["error"] = f"{exc}\n{traceback.format_exc()}"
        job["current_step"] = None
        try:
            from db import job_logs
            completed_at = datetime.now(timezone.utc)
            log_doc = job_logs.find_one({"job_id": job_id})
            duration = None
            if log_doc and log_doc.get("created_at"):
                duration = (completed_at - log_doc["created_at"]).total_seconds()
            update_fields_exc: dict = {
                "status": "failed",
                "error": job["error"],
                "completed_at": completed_at,
            }
            if duration is not None:
                update_fields_exc["duration_seconds"] = round(duration, 1)
            job_logs.update_one(
                {"job_id": job_id},
                {"$set": update_fields_exc}
            )
        except Exception:
            pass


# ── POST /api/jobs ───────────────────────────────────────────────────
@app.post("/api/jobs", response_model=JobCreatedResponse, status_code=202)
async def create_job(req: JobRequest):
    """
    Validate the source, prepare a working directory, then kick off
    pipeline.py in a background thread and return immediately.
    """
    repo_path: str

    # ── source_type: folder ──────────────────────────────────────
    if req.source_type == "folder":
        if not os.path.isdir(req.value):
            raise HTTPException(
                status_code=400,
                detail=f"Directory not found: {req.value}",
            )
        repo_path = os.path.abspath(req.value)

    # ── source_type: github ──────────────────────────────────────
    elif req.source_type == "github":
        if not req.value.startswith("https://github.com/"):
            raise HTTPException(
                status_code=400,
                detail="GitHub URL must start with https://github.com/",
            )
        tmp_dir = tempfile.mkdtemp(prefix="docai_clone_")
        try:
            clone = subprocess.run(
                ["git", "clone", "--depth", "1", req.value, tmp_dir],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if clone.returncode != 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"git clone failed: {clone.stderr[-500:]}",
                )
        except subprocess.TimeoutExpired:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise HTTPException(
                status_code=400,
                detail="git clone timed out (120 s limit).",
            )
        repo_path = tmp_dir

    # ── source_type: code ────────────────────────────────────────
    elif req.source_type == "code":
        tmp_dir = tempfile.mkdtemp(prefix="docai_code_")
        filename = req.filename or "main.py"
        code_file = os.path.join(tmp_dir, filename)
        with open(code_file, "w", encoding="utf-8") as fh:
            fh.write(req.value)
        repo_path = tmp_dir

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source_type: {req.source_type!r}. "
                   f"Must be 'folder', 'github', or 'code'.",
        )

    # ── Create job entry & launch background thread ──────────────
    job_id = uuid.uuid4().hex[:12]
    job_store[job_id] = {
        "status": "queued",
        "current_step": None,
        "error": None,
        "warning": None,
        "files": None,
        "created_at": time.time(),
    }
    
    try:
        from db import job_logs
        val_preview = req.value if len(req.value) < 100 else req.value[:97] + "..."
        job_logs.insert_one({
            "job_id": job_id,
            "source_type": req.source_type,
            "value": val_preview,
            "status": "queued",
            "created_at": datetime.now(timezone.utc)
        })
    except Exception as e:
        print(f"Mongo error: {e}")

    thread = threading.Thread(
        target=_run_pipeline_job,
        args=(job_id, repo_path, bool(req.use_llm)),
        daemon=True,
    )
    thread.start()

    return JobCreatedResponse(job_id=job_id, status="queued")


# ── GET /api/jobs/{job_id} ───────────────────────────────────────────
@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """Return the current state of a pipeline job."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    payload: dict = {"status": job["status"]}

    if job["current_step"]:
        payload["current_step"] = job["current_step"]
    if job["error"]:
        payload["error"] = job["error"]
    if job.get("warning"):
        payload["warning"] = job["warning"]
    if job["files"]:
        payload["files"] = job["files"]

    return JSONResponse(content=payload)


# ── GET /api/jobs/{job_id}/download/commented-code ───────────────────
@app.get("/api/jobs/{job_id}/download/commented-code")
async def download_commented_code(job_id: str):
    """
    Stream the commented code as a zip archive.
    """
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Job is not done yet (status={job['status']})",
        )

    commented_dir = (job.get("files") or {}).get("commented_code_dir")
    if not commented_dir or not os.path.isdir(commented_dir):
        raise HTTPException(
            status_code=404,
            detail="No commented code directory was generated for this job",
        )
    # Create a temp archive — shutil.make_archive returns the full path
    tmp_base = os.path.join(
        tempfile.gettempdir(),
        f"docai_commented_{job_id}_{uuid.uuid4().hex[:6]}",
    )
    archive_path = shutil.make_archive(tmp_base, "zip", commented_dir)

    def _cleanup():
        try:
            os.remove(archive_path)
        except OSError:
            pass

    return FileResponse(
        path=archive_path,
        filename="commented_code.zip",
        media_type="application/zip",
        background=BackgroundTask(_cleanup),
    )


# ── GET /api/jobs/{job_id}/download/{doc_type} ───────────────────────
@app.get("/api/jobs/{job_id}/download/{doc_type}")
async def download_doc(job_id: str, doc_type: str):
    """
    Stream a generated document.
    ``doc_type`` must be ``"hld"`` or ``"lld"``.
    """
    if doc_type not in ("hld", "lld"):
        raise HTTPException(
            status_code=400,
            detail="doc_type must be 'hld' or 'lld'",
        )

    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Job is not done yet (status={job['status']})",
        )

    # ── HLD / LLD: single file download ──────────────────────────
    if not job.get("files") or not job["files"].get(doc_type):
        raise HTTPException(
            status_code=404,
            detail=f"No {doc_type.upper()} file was generated for this job",
        )

    file_path = job["files"][doc_type]
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File missing from disk")

    return FileResponse(
        path=file_path,
        filename=os.path.basename(file_path),
        media_type="application/octet-stream",
    )


# ── GET /health ──────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}

# ── POST /api/jobs/upload-folder ──────────────────────────────────────
@app.post("/api/jobs/upload-folder")
async def upload_folder(file: UploadFile = File(...)):
    tmp_zip_path = None
    try:
        content = await file.read()
        fd, tmp_zip_path = tempfile.mkstemp(suffix=".zip")
        with os.fdopen(fd, "wb") as f:
            f.write(content)

        extract_dir = tempfile.mkdtemp(prefix="docai_folder_")
        with zipfile.ZipFile(tmp_zip_path, "r") as zf:
            zf.extractall(extract_dir)

        # zip has one top-level folder (the original folder name) —
        # descend into it so paths in the output docs are clean
        entries = os.listdir(extract_dir)
        if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
            extract_dir = os.path.join(extract_dir, entries[0])

        # Delegate to the shared internal handler which already implements
        # the folder source_type validation, DB logging, and async thread spawn
        req = JobRequest(source_type="folder", value=extract_dir, use_llm=True)
        return await create_job(req)
    finally:
        if tmp_zip_path and os.path.exists(tmp_zip_path):
            os.remove(tmp_zip_path)

# ── GET /api/audit/logs ──────────────────────────────────────────────

def _format_duration(seconds) -> str:
    """Convert seconds to a human-readable duration string."""
    if seconds is None:
        return "—"
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s"


@app.get("/api/audit/logs")
async def get_audit_logs(limit: int = 50):
    from db import job_logs
    logs = list(job_logs.find().sort("created_at", -1).limit(limit))
    
    activity_logs = []
    compliance_logs = []
    
    for log in logs:
        created_at = log.get("created_at")
        time_str = created_at.strftime("%I:%M %p") if hasattr(created_at, "strftime") else "Unknown"
        date_str = created_at.strftime("%Y-%m-%d %I:%M %p") if hasattr(created_at, "strftime") else "Unknown"
        
        status = log.get("status")
        stype = log.get("source_type")
        val = log.get("value", "")
        job_id = log.get("job_id", "UNKNOWN")
        duration_sec = log.get("duration_seconds")
        duration_str = _format_duration(duration_sec)
        
        icon = "📂" if stype != "code" else "📝"
        severity = "info"
        title = "Repository Uploaded" if stype == "github" else ("Folder Uploaded" if stype == "folder" else "Code Submitted")
        desc = f"Source: {stype} - {val}"
        
        if status == "done":
            icon = "📑"
            severity = "success"
            title = "Documentation Generated"
            desc = f"Successfully generated docs for {val}"
        elif status == "failed":
            icon = "⚠️"
            severity = "warning"
            title = "Generation Failed"
            desc = f"Failed for {val}"
            
        activity_logs.append({
            "icon": icon,
            "title": title,
            "description": desc,
            "time": time_str,
            "severity": severity,
            "duration": duration_str,
            "duration_seconds": duration_sec,
            "value": val,
            "source_type": stype,
            "date": date_str,
        })
        
        compliance_logs.append({
            "id": job_id[:8].upper() if job_id else "UNKNOWN",
            "user": "System",
            "action": title,
            "module": "Documentation",
            "time": time_str,
            "status": "Success" if status == "done" else ("Failed" if status == "failed" else "Pending"),
            "duration": duration_str,
            "duration_seconds": duration_sec,
            "value": val,
            "source_type": stype,
            "date": date_str,
        })
        
    return {
        "activityLogs": activity_logs,
        "complianceLogs": compliance_logs
    }

# ── GET /api/audit/metrics ───────────────────────────────────────────
@app.get("/api/audit/metrics")
async def get_audit_metrics():
    from db import job_logs
    total = job_logs.count_documents({})
    done = job_logs.count_documents({"status": "done"})
    failed = job_logs.count_documents({"status": "failed"})
    
    pipeline_src = [{"$group": {"_id": "$source_type", "count": {"$sum": 1}}}]
    by_source_type = {doc["_id"]: doc["count"] for doc in job_logs.aggregate(pipeline_src)}
    
    # Average duration for completed jobs
    pipeline_dur = [
        {"$match": {"duration_seconds": {"$exists": True, "$ne": None}}},
        {"$group": {"_id": None, "avg": {"$avg": "$duration_seconds"}}},
    ]
    avg_result = list(job_logs.aggregate(pipeline_dur))
    avg_duration = round(avg_result[0]["avg"], 1) if avg_result else None
    
    return {
        "total": total,
        "done": done,
        "failed": failed,
        "by_source_type": by_source_type,
        "avg_duration_seconds": avg_duration,
    }


# ── Entrypoint ───────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=PORT,
        reload=True,
    )