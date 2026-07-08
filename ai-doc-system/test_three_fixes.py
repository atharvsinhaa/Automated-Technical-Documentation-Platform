#!/usr/bin/env python3
"""
test_three_fixes.py
──────────────────────────────────────────────
Verification script for the three fixes:
1. Commented-code download endpoint
2. Exact code preservation (integrity verification)
3. Full-coverage plain-English comments including imports
"""

import os
import sys
import tempfile
import shutil
import difflib

# Ensure project root is on the path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def create_test_repo(base_dir: str) -> str:
    """Create a small multi-file test repo."""
    repo = os.path.join(base_dir, "test_repo")
    os.makedirs(repo, exist_ok=True)

    # Python file with imports, classes, functions
    with open(os.path.join(repo, "app.py"), "w") as f:
        f.write('''import os
import json
from datetime import datetime

class UserService:
    """Manages user operations."""

    def __init__(self, db_path):
        self.db_path = db_path

    def get_user(self, user_id):
        with open(self.db_path, "r") as f:
            data = json.load(f)
        return data.get(str(user_id))

    def create_user(self, name, email):
        user = {"name": name, "email": email, "created": str(datetime.now())}
        return user

    def validate_email(self, email):
        return "@" in email and "." in email

def process_request(request_data):
    """Main entry point."""
    svc = UserService("/tmp/users.json")
    if request_data.get("action") == "create":
        return svc.create_user(request_data["name"], request_data["email"])
    return svc.get_user(request_data.get("id", 0))
''')

    # Second Python file
    os.makedirs(os.path.join(repo, "utils"), exist_ok=True)
    with open(os.path.join(repo, "utils", "__init__.py"), "w") as f:
        f.write("")

    with open(os.path.join(repo, "utils", "helpers.py"), "w") as f:
        f.write('''import re
import hashlib
from typing import List, Optional

def parse_config(raw_text: str) -> dict:
    """Parse key=value config."""
    result = {}
    for line in raw_text.strip().split("\\n"):
        if "=" in line:
            key, val = line.split("=", 1)
            result[key.strip()] = val.strip()
    return result

def build_hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()

class ConfigValidator:
    def __init__(self, schema: dict):
        self.schema = schema

    def validate_config(self, config: dict) -> List[str]:
        errors = []
        for key in self.schema:
            if key not in config:
                errors.append(f"Missing: {key}")
        return errors
''')

    # Third Python file — edge case with tricky formatting
    with open(os.path.join(repo, "edge_case.py"), "w") as f:
        f.write('''# This file has existing comments
import sys  # inline comment here

x = 42  # inline code comment

def fetch_data_from_remote_api(url):
    """Fetches data."""
    # Existing developer comment
    return {"url": url, "status": "ok"}

class DataTransformer:
    pass
''')

    return repo


def collect_source_files(repo_path: str, exts=None) -> list:
    """Collect source files from repo."""
    if exts is None:
        exts = {".py", ".js", ".ts"}
    files = []
    for root, dirs, fnames in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git", "venv"}]
        for f in fnames:
            if os.path.splitext(f)[1] in exts:
                files.append(os.path.join(root, f))
    return sorted(files)


def main():
    print("=" * 60)
    print("  VERIFICATION: Three Fixes")
    print("=" * 60)

    tmp = tempfile.mkdtemp(prefix="docai_verify_")
    try:
        # ── Step 1: Create test repo ────────────────────────────
        print("\n[1] Creating test repo…")
        repo_path = create_test_repo(tmp)
        source_files = collect_source_files(repo_path)
        print(f"    Source files: {len(source_files)}")
        for f in source_files:
            print(f"      - {os.path.relpath(f, repo_path)}")

        # ── Step 2: Run inline commentor ────────────────────────
        print("\n[2] Running ASTInlineCommentor…")
        from backend.comment_engine.inline_commentor import ASTInlineCommentor

        commentor = ASTInlineCommentor()
        commented_dir = os.path.join(tmp, "commented_code")
        os.makedirs(commented_dir, exist_ok=True)

        ok, failed = 0, []
        for src in source_files:
            rel = os.path.relpath(src, repo_path)
            out = os.path.join(commented_dir, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            try:
                commentor.inject_comments(src, out)
                ok += 1
            except Exception as e:
                failed.append((rel, str(e)))
                print(f"    FAIL: {rel}: {e}")

        print(f"    Commented: {ok}/{len(source_files)}")
        if failed:
            print(f"    Failed: {len(failed)}")

        # ── Step 3: Verify file count match ─────────────────────
        print("\n[3] Verifying file count…")
        commented_files = collect_source_files(commented_dir)
        src_count = len(source_files)
        out_count = len(commented_files)
        if src_count == out_count:
            print(f"    PASS: File count matches: {src_count}")
        else:
            print(f"    FAIL: MISMATCH: source={src_count}, output={out_count}")

        # ── Step 4: Verify zero code changes ────────────────────
        print("\n[4] Verifying code integrity (comment lines excluded)…")
        integrity_ok = True
        for src in source_files:
            rel = os.path.relpath(src, repo_path)
            out = os.path.join(commented_dir, rel)
            if not os.path.isfile(out):
                print(f"    FAIL MISSING: {rel}")
                integrity_ok = False
                continue

            with open(src, "r", encoding="utf-8") as f:
                orig_lines = f.read().splitlines()
            with open(out, "r", encoding="utf-8") as f:
                out_lines = f.read().splitlines()

            # Walk through output lines, match against original
            # in order. Any output line that doesn't match the
            # next expected original line is an injected comment.
            orig_idx = 0
            mismatch = False
            for out_line in out_lines:
                if orig_idx < len(orig_lines) and out_line == orig_lines[orig_idx]:
                    orig_idx += 1
                # else: this is an injected comment line, skip it

            if orig_idx == len(orig_lines):
                print(f"    PASS {rel}: zero code changes")
            else:
                integrity_ok = False
                print(f"    FAIL {rel}: CODE CHANGED!")
                print(f"       Only matched {orig_idx}/{len(orig_lines)} original lines")

        # ── Step 5: Check that comments include imports ─────────
        print("\n[5] Checking for import/dependency comments…")
        with open(os.path.join(commented_dir, "app.py"), "r") as f:
            content = f.read()

        import_comments_found = 0
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") and "Loads" in stripped:
                import_comments_found += 1
                print(f"    PASS Import comment: {stripped[:80]}")

        if import_comments_found == 0:
            print("    FAIL: No import comments found!")
        else:
            print(f"    -> {import_comments_found} import comments total")

        # ── Step 6: Test zip creation (simulating download endpoint) ─
        print("\n[6] Testing zip creation…")
        zip_base = os.path.join(tmp, "test_download")
        archive_path = shutil.make_archive(zip_base, "zip", commented_dir)
        import zipfile
        with zipfile.ZipFile(archive_path, "r") as zf:
            zip_files = [n for n in zf.namelist() if not n.endswith("/")]
            print(f"    ZIP contains {len(zip_files)} files:")
            for n in zip_files:
                print(f"      - {n}")
            if len(zip_files) >= src_count:
                print(f"    PASS: ZIP file count >= source count")
            else:
                print(f"    FAIL: ZIP file count ({len(zip_files)}) < source count ({src_count})")
        os.remove(archive_path)

        # ── Summary ─────────────────────────────────────────────
        print(f"\n{'=' * 60}")
        all_pass = integrity_ok and src_count == out_count and import_comments_found > 0
        if all_pass:
            print("  ALL VERIFICATIONS PASSED")
        else:
            print("  SOME VERIFICATIONS FAILED")
        print(f"{'=' * 60}\n")

        return 0 if all_pass else 1

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
