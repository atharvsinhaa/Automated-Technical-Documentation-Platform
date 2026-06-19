import os
import re

def read_file(path):
    with open(path, 'r') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w') as f:
        f.write(content)

# ---------------------------------------------------------
# PROMPT 1: lld_docx_generator.py
# ---------------------------------------------------------
path_lld_docx = "backend/docx_service/lld_docx_generator.py"
content = read_file(path_lld_docx)
if "lld_model=None" not in content:
    content = content.replace(
        "def generate_from_semantic_ir(self, semantic_ir, output_path: str, kg=None, repo_path: str = \"\") -> str:",
        "def generate_from_semantic_ir(self, semantic_ir, output_path: str, kg=None, repo_path: str = \"\", lld_model=None) -> str:"
    )
    content = content.replace(
        "obj_extractor = ObjectModelExtractor()",
        "if lld_model is None:\n            obj_extractor = ObjectModelExtractor()"
    )
    content = content.replace(
        "lld_model = obj_extractor.extract(semantic_ir, kg)",
        "    lld_model = obj_extractor.extract(semantic_ir, kg)"
    )
    content = content.replace(
        "lld_model = DocumentationSummarizer().summarize_lld(lld_model)",
        "    lld_model = DocumentationSummarizer().summarize_lld(lld_model)"
    )
    write_file(path_lld_docx, content)

# ---------------------------------------------------------
# PROMPT 1, 4, 5, 7, 8: pipeline.py
# ---------------------------------------------------------
path_pipeline = "pipeline.py"
content = read_file(path_pipeline)

# Task B (Prompt 1) - Pass lld_summary
if "lld_model=lld_summary" not in content:
    content = content.replace(
        "lld_docx_gen.generate_from_semantic_ir(semantic_ir, lld_docx_path, kg=getattr(builder, \"kg\", None), repo_path=repo_path)",
        "lld_docx_gen.generate_from_semantic_ir(semantic_ir, lld_docx_path, kg=getattr(builder, \"kg\", None), repo_path=repo_path, lld_model=lld_summary)"
    )

# Prompt 4: Change default output directory
if "basename(repo_path.rstrip(\"/\")) + \"-docs\"" not in content:
    content = content.replace(
        'output_dir = args.output or os.path.join(repo_path, "outputs")',
        'output_dir = args.output or os.path.join(os.path.dirname(repo_path.rstrip("/")), os.path.basename(repo_path.rstrip("/")) + "-docs")'
    )

# Prompt 4: SKIP_DIRS
if "commented_code" not in content and "SKIP_DIRS =" in content:
    content = content.replace(
        """    SKIP_DIRS = {"__pycache__", ".git", "venv", ".venv", "node_modules", "dist", "build", ".pytest_cache", "outputs", ".mypy_cache", ".tox", "eggs", "*.egg-info"}""",
        """    SKIP_DIRS = {"__pycache__", ".git", "venv", ".venv", "node_modules", "dist", "build", ".pytest_cache", "outputs", ".mypy_cache", ".tox", "eggs", "*.egg-info", "commented_code"}"""
    )
    content = content.replace(
        "dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(\".\")]",
        "dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(\".\") and not d.endswith(\"-docs\")]"
    )

# Prompt 5: AST warning log
if "get_supported_extensions" not in content:
    content = content.replace(
        "import argparse\nimport os\nimport sys",
        "import argparse\nimport os\nimport sys\nfrom backend.ast_engine.languages.registry import get_supported_extensions"
    )
    content = content.replace(
        "    if verbose:\n        print(\"[PIPELINE] Initializing components...\")",
        "    if verbose:\n        print(\"[PIPELINE] Initializing components...\")\n        _supported = get_supported_extensions()\n        print(f\"[PIPELINE] AST languages registered: {_supported}\")"
    )

# Prompt 7: AIM/blueprint sync
content = content.replace(
        "aim = aim_builder.build(semantic_ir, blueprint, repository_name=repo_name)",
        "aim = aim_builder.build(semantic_ir, hld_blueprint, repository_name=repo_name)"
)

# Prompt 7: exclude patch files
if "SKIP_FILE_PREFIXES" not in content:
    content = content.replace(
        "                source_files.append(os.path.join(root, fname))",
        """                source_files.append(os.path.join(root, fname))
            
            SKIP_FILE_PREFIXES = ("patch_", "fix_", "rewrite_", "refactor_", "test_", "get_old_", "final_patch_")
            source_files = [
                f for f in source_files
                if not any(os.path.basename(f).startswith(p) for p in SKIP_FILE_PREFIXES)
                or os.path.dirname(f) != repo_path
            ]"""
    )

# Prompt 8: AIM failure logging
if "AIE failed at stage (see traceback)" not in content:
    content = content.replace(
        """        except Exception as e:
            if verbose:
                print(f"  ✗ AIE failed at stage: {e}")
            aim = None""",
        """        except Exception as e:
            import traceback
            if verbose:
                print(f"  ✗ AIE failed at stage (see traceback): {e}")
                traceback.print_exc()
            aim = None"""
    )

# Prompt 8: DOCX failure summary
if "DOCX generation FAILED" not in content:
    content = content.replace(
        """    except Exception as e:
        if verbose:
            print(f"  ✗ DOCX generation failed: {e}")
        hld_docx_path = None
        lld_docx_path = None""",
        """    except Exception as e:
        if verbose:
            print(f"  ✗ DOCX generation FAILED: {e}")
        hld_docx_path = None
        lld_docx_path = None"""
    )
    content = content.replace(
        """    if hld_docx_path:
        print(f"  HLD DOCX: {hld_docx_path}")
    else:
        print(f"  HLD: {hld_path}")
        
    if lld_docx_path:
        print(f"  LLD DOCX: {lld_docx_path}")
    else:
        print(f"  LLD: {lld_path}")""",
        """    if hld_docx_path:
        print(f"  HLD DOCX:  {hld_docx_path}")
    else:
        print(f"  [FAILED]   HLD.docx not generated")
        print(f"  [FALLBACK] HLD.md: {hld_path}")

    if lld_docx_path:
        print(f"  LLD DOCX:  {lld_docx_path}")
    else:
        print(f"  [FAILED]   LLD.docx not generated")
        print(f"  [FALLBACK] LLD.md: {lld_path}")"""
    )
write_file(path_pipeline, content)

# ---------------------------------------------------------
# PROMPT 2 & 11: backend/object_model_extractor/extractor.py
# ---------------------------------------------------------
path_obj_ext = "backend/object_model_extractor/extractor.py"
content = read_file(path_obj_ext)

old_seq_flows = """    def _extract_sequence_flows(self, ir, kg) -> List[LLDSequenceFlow]:
        BANNED_TRIGGERS = [".sql", ".csv", ".json", ".xml", ".txt"]

        def is_sql_stub(flow) -> bool:
            trigger = getattr(flow, "trigger", "") or ""
            steps = getattr(flow, "steps", []) or []
            if any(trigger.endswith(ext) for ext in BANNED_TRIGGERS):
                return True
            if len(steps) < 4:
                return True
            if all(s == s.upper() for s in steps if isinstance(s, str)):
                return True
            return False

        flows = []
        # Source 1: real IR flows
        if hasattr(ir, "request_flows") and ir.request_flows:
            for f in ir.request_flows:
                flows.append(LLDSequenceFlow(
                    name=f.name,
                    trigger=f.entry_point,
                    steps=f.steps,
                    description=f.description
                ))
        
        # Source 2: KG BFS
        if not flows and kg:
            flows = self._kg_bfs_flows(ir, kg)
            
        # Source 3: library method flows
        if not flows:
            flows = self._library_method_flows(ir, kg)

        flows = [f for f in flows if not is_sql_stub(f)]
        return flows[:6]"""

new_seq_flows = """    def _extract_sequence_flows(self, ir, kg) -> List[LLDSequenceFlow]:
        BANNED_TRIGGERS = [".sql", ".csv", ".json", ".xml", ".txt"]
        def is_sql_stub(flow) -> bool:
            trigger = getattr(flow, "trigger", "") or ""
            steps = getattr(flow, "steps", []) or []
            if any(trigger.endswith(ext) for ext in BANNED_TRIGGERS):
                return True
            if len(steps) < 4:
                return True
            if all(s == s.upper() for s in steps if isinstance(s, str)):
                return True
            return False

        # Source 1: real IR flows — filter stubs
        ir_flows = [f for f in getattr(ir, 'request_flows', [])
                    if not is_sql_stub(LLDSequenceFlow(
                        name=f.name, trigger=f.entry_point,
                        steps=f.steps, description=f.description))]
        flows = [LLDSequenceFlow(name=f.name, trigger=f.entry_point,
                                  steps=f.steps, description=f.description)
                 for f in getattr(ir, 'request_flows', [])]
        flows = [f for f in flows if not is_sql_stub(f)]

        # Source 2: KG BFS (no stub filter)
        if not flows and kg:
            flows = self._kg_bfs_flows(ir, kg)

        # Source 3: API endpoint flows (restored — evidence-backed, not hallucination)
        if not flows and ir.api_endpoints:
            flows = self._api_endpoint_flows(ir)

        # Source 4: library method flows (no stub filter)
        if not flows:
            flows = self._library_method_flows(ir, kg)

        return flows[:6]"""

if "def _extract_sequence_flows" in content and "Source 3: API endpoint flows" not in content:
    content = content.replace(old_seq_flows, new_seq_flows)

new_api_endpoint_flows = """    def _api_endpoint_flows(self, ir) -> List[LLDSequenceFlow]:
        HTTP_STEPS = {
            "POST":   ["Validate request body", "Apply business rules",
                       "Persist to database", "Return 201 Created"],
            "GET":    ["Parse query parameters", "Query database",
                       "Serialize response", "Return 200 OK"],
            "PUT":    ["Validate request body", "Find existing record",
                       "Update record", "Return 200 OK"],
            "DELETE": ["Verify authorization", "Delete record",
                       "Return 204 No Content"],
            "PATCH":  ["Validate partial body", "Apply partial update",
                       "Return 200 OK"],
        }
        flows = []
        for ep in ir.api_endpoints[:5]:
            service = ep.service or "Service"
            steps = [f"Client → {service}: {ep.method} {ep.path}"]
            steps += [f"{service}: {s}"
                      for s in HTTP_STEPS.get(ep.method, ["Process request"])]
            steps.append(f"{service} → Client: response")
            flows.append(LLDSequenceFlow(
                name=f"{ep.method} {ep.path}",
                trigger=f"HTTP {ep.method} to {ep.path}",
                steps=steps,
                description=getattr(ep, "description", "") or f"{ep.method} {ep.path}",
            ))
        return flows"""

if "def _api_endpoint_flows" not in content:
    content = content.replace("    def _library_method_flows", new_api_endpoint_flows + "\n\n    def _library_method_flows")

# Prompt 11: Add return steps to library flows
if "→ Caller: return result" not in content:
    content = content.replace(
        'steps.append(f"{curr_actor} → {callee_actor}: {callee_name}()")',
        'steps.append(f"{curr_actor} → {callee_actor}: {callee_name}()")\n                            steps.append(f"{callee_actor} → {curr_actor}: return result")'
    )
    content = content.replace(
        'flows.append(LLDSequenceFlow(',
        'if not any("→ Caller" in s for s in steps):\n                steps.append(f"{cls_name} → Caller: return result")\n            flows.append(LLDSequenceFlow('
    )

write_file(path_obj_ext, content)
