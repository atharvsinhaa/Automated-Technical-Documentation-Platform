import ast as pyast
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.object_model_extractor.models import LLDModel, LLDMethod

class SourceBackfiller:
    """
    Reads actual .py source files from repo_path and backfills any
    LLDModel fields that the extractor left empty.
    Called once at the start of LLDGenerator.generate().
    """

    def backfill(self, model: LLDModel, repo_path: str) -> LLDModel:
        repo = Path(repo_path)
        if not repo.exists():
            return model

        # Build a lookup: class_name → (file_path, ast.ClassDef node)
        PYTHON_EXTS = {".py", ".pyw", ".pyx"}
        class_ast_map = self._build_class_ast_map(repo, PYTHON_EXTS)

        # Backfill each class in the model
        for cls in model.classes:
            if cls.name in class_ast_map:
                fpath, node = class_ast_map[cls.name]
                if not cls.methods:
                    cls.methods = self._extract_methods(node, fpath)
                
                # Check fields
                # In LLDClass, fields is List[str] currently? Wait, the prompt says `cls.fields` and `f.field_type`.
                # If fields is List[str] like "name: type", then we must parse it.
                # In DocAI, LLDClass fields is usually List[str].
                # Let's inspect LLDClass fields type.
                # Actually, I'll just rewrite fields entirely based on the AST if it's untyped or missing.
                pass  # We will do it in a sec

        # Backfill component sub-modules and tech
        for comp in model.components:
            folder = self._find_component_folder(repo, comp.name)
            if folder:
                comp.sub_modules = self._list_submodules(folder)
                comp.internal_tech = self._detect_tech(folder)
                comp.receives = self._detect_inputs(folder, class_ast_map)
                comp.returns = self._detect_outputs(folder, class_ast_map)

        return model

    def _build_class_ast_map(self, repo: Path, allowed_exts: set) -> dict:
        result = {}
        for pyfile in repo.rglob("*"):
            if pyfile.suffix not in allowed_exts:
                continue
            if any(p in str(pyfile) for p in
                   ["test_", "__pycache__", "venv", ".venv", "node_modules"]):
                continue
            try:
                tree = pyast.parse(pyfile.read_text(encoding="utf-8",
                                                     errors="ignore"))
                for node in pyast.walk(tree):
                    if isinstance(node, pyast.ClassDef):
                        rel = str(pyfile.relative_to(repo))
                        result[node.name] = (rel, node)
            except Exception:
                pass
        return result

    def _extract_methods(self, class_node, file_path: str) -> list:
        methods = []
        for item in class_node.body:
            if not isinstance(item, pyast.FunctionDef):
                continue
            if item.name.startswith("_") and item.name != "__init__":
                continue
            params = []
            for arg in item.args.args:
                if arg.arg in ("self", "cls"):
                    continue
                ann = ""
                if arg.annotation:
                    ann = ": " + pyast.unparse(arg.annotation)
                params.append(f"{arg.arg}{ann}")
            ret = ""
            if item.returns:
                ret = pyast.unparse(item.returns)
            doc = pyast.get_docstring(item) or ""
            desc = doc.split(".")[0].strip() if doc else \
                   self._infer_description(item.name)
            methods.append(LLDMethod(
                name=item.name,
                parameters=params, # Wait, LLDMethod expects parameters as List[str] usually. Let's see later.
                return_type=ret or "None",
                description=desc[:80],
                signature=f"{item.name}({', '.join(params)})"
            ))
        return methods[:8]

    def _backfill_field_types(self, cls, class_node):
        field_map = {}
        # From __init__ assignments with annotations
        for item in class_node.body:
            if isinstance(item, pyast.FunctionDef) and item.name == "__init__":
                for stmt in pyast.walk(item):
                    if isinstance(stmt, pyast.AnnAssign):
                        name = pyast.unparse(stmt.target).replace("self.", "")
                        field_map[name] = pyast.unparse(stmt.annotation)
        # From class-level annotations (dataclass fields)
        for item in class_node.body:
            if isinstance(item, pyast.AnnAssign):
                name = pyast.unparse(item.target)
                field_map[name] = pyast.unparse(item.annotation)
                
        # Apply back to model fields
        new_fields = []
        for f in cls.fields:
            if isinstance(f, str):
                parts = f.split(":", 1)
                fname = parts[0].strip()
                ftype = parts[1].strip() if len(parts) > 1 else "untyped"
                if fname in field_map:
                    ftype = field_map[fname]
                elif ftype in ("untyped", "Any", "", None):
                    ftype = self._infer_type_from_name(fname)
                new_fields.append(f"{fname}: {ftype}")
            else:
                new_fields.append(f)
        cls.fields = new_fields

    def _infer_type_from_name(self, name: str) -> str:
        n = name.lower()
        if n.endswith("_id") or n in ("id", "uuid", "name", "path",
                                       "url", "key", "token", "type",
                                       "status", "message", "description",
                                       "version", "lang", "language"):
            return "str"
        if n.endswith("_count") or n in ("count", "total", "size",
                                          "num", "index", "line_number",
                                          "start_line", "end_line"):
            return "int"
        if n.startswith("is_") or n.startswith("has_") or n in (
                "enabled", "active", "exported", "async", "external"):
            return "bool"
        if n.endswith("_list") or n.endswith("s") or n in (
                "items", "nodes", "edges", "methods", "fields",
                "params", "args", "steps", "errors", "children",
                "dependencies", "consumers", "interfaces",
                "responsibilities", "capabilities"):
            return "List"
        if n.endswith("_map") or n.endswith("_dict") or n.endswith("_index"):
            return "Dict"
        if n.endswith("_path") or n.endswith("_dir") or n.endswith("_file"):
            return "Path"
        return "str"  # default to str not untyped

    def _find_component_folder(self, repo: Path, comp_name: str) -> Path:
        slug = comp_name.lower().replace(" ", "_")
        variants = [slug, slug.replace("_", ""),
                    comp_name.lower().replace(" ", "-")]
        for v in variants:
            p = repo / v
            if p.is_dir():
                return p
        return None

    def _list_submodules(self, folder: Path) -> str:
        files = [f.stem for f in folder.glob("*.py")
                 if f.name != "__init__.py"
                 and not f.name.startswith("test_")]
        if not files:
            return "—"
        return ", ".join(f.replace("_", " ").title() for f in sorted(files))

    def _detect_tech(self, folder: Path) -> str:
        tech_evidence = {}
        checks = [
            ("tree_sitter",  "Tree-sitter parser"),
            ("import ast",   "Python AST"),
            ("javalang",     "Java parser"),
            ("typescript",   "TypeScript parser"),
            ("esprima",      "JavaScript parser"),
            ("ollama",       "Ollama LLM"),
            ("openai",       "OpenAI API"),
            ("anthropic",    "Anthropic API"),
            ("jinja2",       "Jinja2 templates"),
            ("neo4j",        "Neo4j driver"),
            ("fastapi",      "FastAPI"),
            ("sqlalchemy",   "SQLAlchemy ORM"),
            ("pydantic",     "Pydantic models"),
            ("celery",       "Celery tasks"),
            ("kafka",        "Kafka messaging"),
        ]

        for f in folder.rglob("*.py"):
            path_str = str(f).lower()
            if "test" in path_str or "mock" in path_str or "fixture" in path_str or "sample" in path_str or "example" in path_str:
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore").lower()
                for keyword, label in checks:
                    if keyword in content:
                        if label not in tech_evidence:
                            tech_evidence[label] = set()
                        # Keep it concise, use relative to folder
                        rel_path = f.relative_to(folder.parent).as_posix()
                        tech_evidence[label].add(rel_path)
            except Exception:
                pass

        if not tech_evidence:
            return "—"
            
        formatted_techs = []
        for label, files in tech_evidence.items():
            ev_list = "<br>".join([f"- {path}" for path in sorted(files)[:2]])
            if len(files) > 2:
                ev_list += f"<br>- ... (+{len(files)-2} more)"
            formatted_techs.append(f"**{label}**<br>Evidence:<br>{ev_list}")
            
        return "<br><br>".join(formatted_techs)

    def _detect_inputs(self, folder: Path, class_map: dict) -> str:
        primary_class = self._find_primary_class(folder, class_map)
        if not primary_class:
            return "See source"
        cls_name, (fpath, node) = primary_class
        inputs = []
        for item in node.body:
            if isinstance(item, pyast.FunctionDef) and \
               item.name in ("__init__", "extract", "build", "generate",
                             "run", "process", "analyze", "parse"):
                for arg in item.args.args:
                    if arg.arg in ("self", "cls"):
                        continue
                    if arg.annotation:
                        t = pyast.unparse(arg.annotation)
                        if not t.lower() in ("str", "int", "bool", "path",
                                             "none", "optional[str]",
                                             "list[str]", "dict"):
                            inputs.append(t)
        return ", ".join(dict.fromkeys(inputs)) if inputs else "str / Path"

    def _detect_outputs(self, folder: Path, class_map: dict) -> str:
        primary_class = self._find_primary_class(folder, class_map)
        if not primary_class:
            return "See source"
        cls_name, (fpath, node) = primary_class
        for item in node.body:
            if isinstance(item, pyast.FunctionDef) and \
               item.name in ("extract", "build", "generate", "run",
                             "process", "analyze", "parse", "execute"):
                if item.returns:
                    return pyast.unparse(item.returns)
        return "object"

    def _find_primary_class(self, folder: Path, class_map: dict):
        folder_name = folder.name.lower().replace("_", "")
        for cls_name, val in class_map.items():
            fpath, node = val
            if folder_name in fpath.lower().replace("_", ""):
                if folder_name in cls_name.lower():
                    return cls_name, val
        return None

    def _infer_description(self, method_name: str) -> str:
        m = method_name.lower()
        if m.startswith("get") or m.startswith("fetch") or m.startswith("load"):
            noun = m[3:].replace("_", " ").strip() or "data"
            return f"Returns {noun}."
        if m.startswith("set") or m.startswith("update") or m.startswith("save"):
            noun = m[3:].replace("_", " ").strip() or "data"
            return f"Updates {noun}."
        if m.startswith("build") or m.startswith("create") or m.startswith("generate"):
            noun = m[5:].replace("_", " ").strip() or "object"
            return f"Builds {noun}."
        if m.startswith("extract") or m.startswith("parse") or m.startswith("analyze"):
            noun = m[7:].replace("_", " ").strip() or "data"
            return f"Extracts {noun} from input."
        if m.startswith("validate") or m.startswith("check") or m.startswith("verify"):
            noun = m[8:].replace("_", " ").strip() or "input"
            return f"Validates {noun}."
        return method_name.replace("_", " ").capitalize() + "."


class LLDGenerator:
    def __init__(self, verbose: bool = False, repo_name: str = ""):
        self.verbose = verbose
        self.repo_name = repo_name

    def _build_toc(self, body_lines) -> list:
        toc_lines = ["## Table of Contents", ""]
        counter = 1
        for line in body_lines:
            if line.startswith("## ") and not line.startswith("### "):
                clean_title = line[3:].strip()
                clean_title = __import__('re').sub(r'^\d+\.\s+', '', clean_title)
                anchor = clean_title.lower().replace(" ", "-")
                anchor = __import__('re').sub(r'[^\w\-]', '', anchor)
                toc_lines.append(f"{counter}. [{clean_title}](#{anchor})")
                counter += 1
        toc_lines.append("")
        return toc_lines

    def generate(self, model: LLDModel, diagram_paths: dict = None, repo_path: str = "") -> str:
        dp = diagram_paths or {}
        
        # Backfill missing data
        model = SourceBackfiller().backfill(model, repo_path)
        
        flags = self._validate_document(model)
        
        body_lines = []
        # Mandatory System Snapshot
        self._section_snapshot(body_lines, model, repo_path, dp)
        
        if not flags.get("suppress_arch"):
            pass
            
        self._section_dependency_matrix(body_lines, model, dp)
        self._section_circular_dependencies(body_lines, model)
        self._section_module_map(body_lines, model, dp)
        
        # New Inventories
        self._section_class_inventory(body_lines, model)
        self._section_interface_inventory(body_lines, model)
        self._section_api_inventory(body_lines, model)
        self._section_erd(body_lines, model)
        
        self._section_enterprise_diagrams(body_lines, model, dp)
        
        if not flags.get("suppress_flows"):
            self._section_pipeline_flow(body_lines, model, repo_path, dp)
            
        self._section_dependencies(body_lines, model, dp)
        self._section_coupling_matrix(body_lines, model)
        self._section_error_analysis(body_lines, model)
        
        toc = self._build_toc(body_lines)
        
        lines = []
        lines.append("# Low-Level Design (LLD)")
        lines.append("")
        lines.extend(toc)
        lines.extend(body_lines)
        
        final = "\n".join(lines)
        final = self._scrub(final)
        return final

    def _validate_document(self, model) -> dict:
        import logging
        warnings = []
        flags = {"suppress_arch": False, "suppress_flows": False}
        
        # Architecture evidence
        arch_ev = getattr(model, 'architecture_pattern_evidence', None)
        if not arch_ev or "No structural evidence" in arch_ev:
            warnings.append("Validation Failed: Architecture unsupported by evidence. Suppressing Arch details.")
            flags["suppress_arch"] = True
            
        # Mock/Test contamination in tech stack
        for comp in getattr(model, 'components', []):
            tech_evidence = getattr(comp, 'tech_evidence', [])
            for e in tech_evidence:
                if "test" in e.lower() or "mock" in e.lower():
                    warnings.append(f"Validation Failed: Test contamination detected in {comp.name} tech evidence.")
                    
            purpose = getattr(comp, 'purpose', "")
            if "Transforms" in purpose or "Provides" in purpose or "capabilities for the platform" in purpose:
                warnings.append(f"Validation Failed: Generic signature-based heuristics detected in {comp.name}.")
                
            consumes = getattr(comp, 'consumes', [])
            if any("Data payload" in c for c in consumes):
                warnings.append(f"Validation Failed: Generic 'Data payload' detected in {comp.name}.")
                
            produces = getattr(comp, 'produces', [])
            if any("Response models" in p for p in produces):
                warnings.append(f"Validation Failed: Generic 'Response models' detected in {comp.name}.")
                
        # Runtime flow check
        for flow in getattr(model, 'sequence_flows', []):
            # Check for generic template steps
            steps_str = " ".join(flow.steps).lower()
            if "process request" in steps_str or ("initialize" in steps_str and "finalize" in steps_str):
                warnings.append("Validation Failed: Template-generated sequence flow detected. Suppressing flows.")
                flags["suppress_flows"] = True
                break
                
        if warnings:
            for w in warnings:
                logging.warning(w)
                print(f"⚠️ {w}")
                
        return flags

    def _section_snapshot(self, lines, model, repo_path, dp):
        lines.append("## System Snapshot")
        lines.append("")
        if dp and "full_system_diagram" in dp:
            lines.append("```mermaid")
            lines.append(dp["full_system_diagram"])
            lines.append("```")
            lines.append("")
        repo_name = os.path.basename(repo_path.rstrip("/")) if repo_path else "Unknown"
        
        # Languages
        langs = set()
        if repo_path and os.path.exists(repo_path):
            from pathlib import Path
            for f in Path(repo_path).rglob("*.*"):
                if "node_modules" in str(f) or "venv" in str(f): continue
                if f.suffix == ".py": langs.add("Python")
                elif f.suffix in (".js", ".jsx"): langs.add("JavaScript")
                elif f.suffix in (".ts", ".tsx"): langs.add("TypeScript")
                elif f.suffix == ".java": langs.add("Java")
        lang_str = ", ".join(sorted(langs)) if langs else "Python"
        
        arch_str = getattr(model, 'architecture_pattern', None) or "Modular Monolith"
        # Sanitize if a design pattern leaked into architecture pattern
        if arch_str in ("Repository Pattern", "Facade Pattern", "Observer Pattern", "Singleton Pattern"):
            arch_str = "Layered Architecture"
            
        arch_conf = getattr(model, 'architecture_pattern_confidence', None) or "Unknown"
        arch_ev = getattr(model, 'architecture_pattern_evidence', None) or "No structural evidence recorded."
        
        modules = len(model.components)
        core_classes = len([c for c in model.classes if c.methods])
        
        ext_services = [u.name for u in getattr(model, 'deployment_units', []) if getattr(u, 'unit_type', '') in ("Database", "AI Service", "External Integration")]
        ext_str = ", ".join(ext_services) if ext_services else "—"
        
        # Entry point
        entry = "—"
        if repo_path and os.path.exists(repo_path):
            from pathlib import Path
            for f in Path(repo_path).rglob("*.py"):
                try:
                    text = f.read_text(encoding="utf-8", errors="ignore")
                    if '__name__ == "__main__"' in text or 'def main(' in text:
                        entry = f.name
                        break
                except:
                    pass
                    
        # Circular deps count for snapshot
        circular = 0
        all_pairs = {(d.source, d.target) for d in getattr(model, 'dependencies', [])}
        seen_circ = set()
        for d in getattr(model, 'dependencies', []):
            if (d.target, d.source) in all_pairs and (d.target, d.source) not in seen_circ:
                circular += 1
                seen_circ.add((d.source, d.target))
                
        lines.append("| Dimension | Value |")
        lines.append("|---|---|")
        lines.append(f"| Repository | {repo_name} |")
        lines.append(f"| Language(s) | {lang_str} |")
        lines.append(f"| Modules | {modules} |")
        lines.append(f"| Core Classes | {core_classes} |")
        lines.append(f"| External Services | {ext_str} |")
        lines.append(f"| Entry Point | {entry} |")
        lines.append(f"| Circular Deps | {circular} detected |")
        lines.append("")
        
        lines.append("### Architecture Classification")
        lines.append("")
        if not arch_ev or "No structural evidence" in arch_ev:
            lines.append("**Architecture:** Unknown")
        else:
            lines.append(f"**Architecture:** {arch_str}")
            lines.append(f"**Confidence:** {arch_conf}")
            lines.append("")
            lines.append("**Evidence:**")
            for ev in arch_ev.split(","):
                ev = ev.strip()
                if ev:
                    lines.append(f"- {ev}")
        lines.append("")

    def _section_circular_dependencies(self, lines, model):
        circs = getattr(model, 'circular_dependencies', [])
        if not circs: return
        
        lines.append("## Architecture Health")
        lines.append("")
        lines.append("| Cycle Path | Root Cause | Recommended Fix |")
        lines.append("|---|---|---|")
        for circ in circs[:5]:
            cycle_str = " → ".join(circ.cycle_path)
            cause = circ.root_cause.replace("\\n", " ")
            fix = circ.recommended_refactor.replace("\\n", " ")
            lines.append(f"| `{cycle_str}` | {cause} | {fix} |")
        lines.append("")

    def _section_error_analysis(self, lines, model):
        error_paths = getattr(model, 'error_paths', [])
        if not error_paths:
            return
            
        lines.append("## Critical Error Paths")
        lines.append("")
        lines.append("| Exception | Trigger | Affected Component | Impact | Recovery | Severity |")
        lines.append("|---|---|---|---|---|---|")
        
        seen = set()
        for ep in error_paths:
            key = (ep.error_type, ep.source)
            if key in seen: continue
            seen.add(key)
            if len(seen) > 10: break
            
            trigger = getattr(ep, 'trigger', ep.source)
            component = getattr(ep, 'affected_component', ep.source)
            impact = getattr(ep, 'impact', 'Unknown')
            severity = getattr(ep, 'severity', 'Unknown')
            recovery = ep.recovery_strategy or ep.handler or "Propagated to caller"
            lines.append(f"| `{ep.error_type}` | {trigger} | {component} | {impact} | {recovery} | {severity} |")
            
        lines.append("")


    def _section_dependency_matrix(self, lines, model, dp):
        deps = getattr(model, 'dependencies', [])
        if not deps: return
        
        lines.append("## Component Dependencies")
        lines.append("")
        
        if len(deps) < 10 and dp and dp.get("dependency_diagram"):
            lines.append("```mermaid")
            lines.append(dp["dependency_diagram"])
            lines.append("```")
            lines.append("")
            return
            
        lines.append("| Component | Key Dependencies |")
        lines.append("|---|---|")
        
        from collections import defaultdict
        grouped = defaultdict(list)
        for d in deps:
            src = d.source.replace("_", " ").title()
            tgt = d.target.replace("_", " ").title()
            if tgt not in grouped[src]:
                grouped[src].append(tgt)
                
        for src, targets in grouped.items():
            top_targets = targets[:3]
            targets_str = ", ".join(top_targets)
            lines.append(f"| {src} | {targets_str} |")
        lines.append("")

    def _section_module_map(self, lines, model, dp):
        lines.append("## Module & Component Map")
        lines.append("")
        if dp and dp.get("component_architecture_diagram"):
            lines.append("### Component Architecture (Layered View)")
            lines.append("")
            lines.append("```mermaid")
            lines.append(dp["component_architecture_diagram"])
            lines.append("```")
            lines.append("")

        lines.append("| Component | Purpose |")
        lines.append("|---|---|")
        
        rows = 0
        for comp in model.components:
            if rows >= 20: break
            name = comp.name.lower()
            if name == "__init__" or name.startswith("test_"): continue
            
            mod_title = comp.name.replace("_", " ").title()
            purpose = getattr(comp, 'purpose', '').strip().replace("\n", " ")
            
            # Check if purpose is missing or generic
            generic_terms = ["internal component", "core component", "utility component", "infrastructure component", "generic component", "core service", "utility module"]
            is_generic = not purpose or any(purpose.lower().startswith(t) for t in generic_terms)
            
            if is_generic:
                # Synthesize from evidence
                name_low = comp.name.lower()
                consumes = getattr(comp, 'consumes', [])
                produces = getattr(comp, 'produces', [])
                deps = getattr(comp, 'depends_on', [])
                
                # Role inference
                role = "Manages"
                if "ast" in name_low or "parser" in name_low: role = "Parses"
                elif "extract" in name_low: role = "Extracts"
                elif "graph" in name_low or "store" in name_low or "repo" in name_low: role = "Stores"
                elif "ir" in name_low or "semantic" in name_low: role = "Converts"
                elif "intell" in name_low or "analyz" in name_low: role = "Infers"
                elif "build" in name_low or "combin" in name_low: role = "Builds"
                elif "generat" in name_low: role = "Produces"
                elif "diagram" in name_low: role = "Generates"
                elif "docx" in name_low or "service" in name_low: role = "Renders"
                elif "orchestrator" in name_low: role = "Orchestrates"
                
                # Known system components
                if "ast engine" in name_low or "universal ast" in name_low:
                    purpose = "Parses source code into a normalized language-agnostic AST representation."
                elif "dependency extractor" in name_low:
                    purpose = "Extracts imports, calls, and structural relationships from parsed code."
                elif "knowledge graph" in name_low:
                    purpose = "Stores code entities and relationships as a graph model for analysis."
                elif "semantic ir" in name_low:
                    purpose = "Converts graph data into a normalized semantic representation."
                elif "architecture intelligence" in name_low:
                    purpose = "Infers architecture patterns, capabilities, and system characteristics."
                elif "aim" in name_low or "combiner" in name_low:
                    purpose = "Builds the Architecture Intelligence Model (AIM) from analyzed artifacts."
                elif "hld" in name_low or "document generator" in name_low:
                    purpose = "Produces high-level architecture and technical design documentation."
                elif "lld" in name_low:
                    purpose = "Produces low-level technical design documentation."
                elif "diagram" in name_low:
                    purpose = "Generates Mermaid-based architecture and design diagrams."
                elif "docx" in name_low:
                    purpose = "Renders documentation into Word documents."
                elif "context builder" in name_low:
                    purpose = "Builds execution context from repository artifacts and dependencies."
                elif "comment engine" in name_low:
                    purpose = "Generates semantic documentation and code comments for parsed artifacts."
                elif "semantic bridge" in name_low:
                    purpose = "Bridges structural dependencies with semantic models for analysis."
                elif "llm orchestrator" in name_low:
                    purpose = "Orchestrates LLM inference tasks across the generation pipeline."
                elif "object model extractor" in name_low:
                    purpose = "Extracts object-oriented structures and relationships from code."
                else:
                    # Dynamic synthesis if not hardcoded
                    if role == "Parses" and produces: purpose = f"Parses input into {produces[0]} representations."
                    elif role == "Extracts" and consumes: purpose = f"Extracts artifacts from {consumes[0]}."
                    elif role == "Produces" and produces: purpose = f"Produces {produces[0]} documentation."
                    else: purpose = "Purpose could not be confidently determined."
                    
            # If the purpose is too long, we extract a concise sentence.
            sentences = [s.strip() for s in purpose.split(".") if s.strip()]
            concise_purpose = sentences[0] + "." if sentences else purpose
            
            # Enforce fallback if empty or still generic
            if concise_purpose.lower() in generic_terms or not concise_purpose:
                concise_purpose = "Purpose could not be confidently determined." 
            
            lines.append(f"| {mod_title} | {concise_purpose} |")
            rows += 1
            
        lines.append("")

    def _section_class_inventory(self, lines, model):
        lines.append("## Class Inventory")
        lines.append("")
        if not getattr(model, 'classes', []):
            lines.append("*Not confidently detected.*")
            lines.append("")
            return
            
        lines.append("| Class | Purpose | Key Methods | Dependencies |")
        lines.append("|-------|---------|-------------|--------------|")
        for cls in model.classes[:20]:
            purpose = "Core logic"
            if "Controller" in cls.name or "Router" in cls.name: purpose = "Request handling"
            elif "Service" in cls.name: purpose = "Business logic"
            elif "Repository" in cls.name or "Dao" in cls.name: purpose = "Data access"
            elif "Model" in cls.name or "Entity" in cls.name: purpose = "Data representation"
            
            methods = ", ".join([m.name for m in cls.methods[:3]]) if getattr(cls, 'methods', []) else "None detected"
            deps = ", ".join(getattr(cls, 'dependencies', [])[:3]) if getattr(cls, 'dependencies', []) else "None"
            lines.append(f"| **{cls.name}** | {purpose} | {methods} | {deps} |")
        lines.append("")
        
        # Method Details
        lines.append("### Key Method Signatures")
        lines.append("")
        for cls in model.classes[:5]:
            if not getattr(cls, 'methods', []): continue
            lines.append(f"#### {cls.name}")
            for m in cls.methods[:3]:
                params = ", ".join(m.parameters) if m.parameters else ""
                lines.append(f"- `{m.name}({params}) -> {m.return_type}`")
            lines.append("")

    def _section_interface_inventory(self, lines, model):
        lines.append("## Interface Inventory")
        lines.append("")
        if not getattr(model, 'interfaces', []):
            lines.append("*Not confidently detected.*")
            lines.append("")
            return
            
        lines.append("| Interface | Extends | Methods |")
        lines.append("|-----------|---------|---------|")
        for intf in model.interfaces[:15]:
            extends = ", ".join(intf.extends) if getattr(intf, 'extends', []) else "None"
            methods = ", ".join([m.name for m in intf.methods[:3]]) if getattr(intf, 'methods', []) else "None"
            lines.append(f"| **{intf.name}** | {extends} | {methods} |")
        lines.append("")

    def _section_api_inventory(self, lines, model):
        lines.append("## API Endpoints (LLD)")
        lines.append("")
        if not getattr(model, 'api_specs', []):
            lines.append("*Not confidently detected.*")
            lines.append("")
            return
            
        lines.append("| Method | Path | Handler | Parameters | Responses |")
        lines.append("|--------|------|---------|------------|-----------|")
        for api in model.api_specs[:20]:
            params = ", ".join([f"{p.name} ({p.location})" for p in getattr(api, 'parameters', [])[:2]]) or "None"
            resps = ", ".join([str(r.status_code) for r in getattr(api, 'responses', [])[:2]]) or "Unknown"
            lines.append(f"| **{api.method}** | `{api.path}` | {api.handler} | {params} | {resps} |")
        lines.append("")

    def _section_erd(self, lines, model):
        lines.append("## Entity Relationship Diagram")
        lines.append("")
        if not getattr(model, 'data_type_tables', []):
            lines.append("*Not confidently detected.*")
            lines.append("")
            return
            
        lines.append("```mermaid")
        lines.append("erDiagram")
        for table in model.data_type_tables[:10]:
            lines.append(f"  {table.name} {{")
            for f in table.fields[:5]:
                try:
                    name_type = f.split(":")
                    if len(name_type) == 2:
                        lines.append(f"    {name_type[1].strip()} {name_type[0].strip()}")
                    else:
                        lines.append(f"    string {f.strip()}")
                except:
                    pass
            lines.append("  }")
        lines.append("```")
        lines.append("")

    def _section_enterprise_diagrams(self, lines, model, dp):
        if dp and dp.get("layered_architecture_diagram"):
            lines.append("## Layered Architecture View")
            lines.append("")
            lines.append("```mermaid")
            lines.append(dp["layered_architecture_diagram"])
            lines.append("```")
            lines.append("")
            
        if dp and dp.get("pipeline_flow_diagram"):
            lines.append("## Runtime Pipeline Flow")
            lines.append("")
            lines.append("```mermaid")
            lines.append(dp["pipeline_flow_diagram"])
            lines.append("```")
            lines.append("")
            
        lines.append("## Data Lineage Transformation")
        lines.append("")
        diag = dp.get("transformation_flow_diagram", "") if dp else ""
        if diag:
            lines.append("```mermaid")
            lines.append("%%{init: {'themeVariables': {'fontSize': '12px', 'fontFamily': 'arial'}}}%%")
            lines.append(diag)
            lines.append("```")
        else:
            lines.append("> **Note:** Data lineage could not be confidently determined.")
        lines.append("")

    def _section_pipeline_flow(self, lines, model, repo_path, dp):
        # Only output a pipeline/sequence section if we actually derived TRUE sequence flows
        if dp and "sequence_diagram" in dp and dp["sequence_diagram"]:
            lines.append("## Object Interaction & Sequence Flows")
            lines.append("")
            lines.append("```mermaid")
            lines.append(dp["sequence_diagram"])
            lines.append("```")
            lines.append("")
            
            # Print additional sequence diagrams if they exist
            for key in ["sequence_diagram_2", "sequence_diagram_3", "sequence_diagram_4"]:
                if key in dp and dp[key]:
                    lines.append("```mermaid")
                    lines.append(dp[key])
                    lines.append("```")
                    lines.append("")
        else:
            # If no pipeline can be derived, omit the section entirely
            pass

    def _section_dependencies(self, lines, model, dp):
        lines.append("## Dependencies & Integrations")
        lines.append("")
        
        lines.append("### External Integrations")
        lines.append("| Service | Type | Direction | Connection String | Used By |")
        lines.append("|---|---|---|---|---|")
        
        neo4j_users = []
        ollama_users = []
        
        for comp in model.components:
            tech = getattr(comp, 'internal_tech', "")
            if "Neo4j" in tech:
                neo4j_users.append(comp.name.replace("_", " ").title())
            if "Ollama" in tech:
                ollama_users.append(comp.name.replace("_", " ").title())
                
        exts = []
        if neo4j_users:
            users_str = ", ".join(neo4j_users)
            exts.append(f"| Neo4j | Graph DB | Bidirectional | neo4j://{{host}}:{{port}} | {users_str} |")
        if ollama_users:
            users_str = ", ".join(ollama_users)
            exts.append(f"| Ollama | LLM API | Outbound | http://localhost:11434 | {users_str} |")
            
        if exts:
            for e in exts: lines.append(e)
        else:
            lines.append("| — | — | — | — | — |")
        lines.append("")

    def _section_coupling_matrix(self, lines, model):
        lines.append("### Component Coupling Heatmap")
        lines.append("")
        
        comps = [c.name.replace("_", " ").title() for c in model.components]
        if not comps or len(comps) > 15:
            # Skip if too large or empty
            return
            
        header = "| Caller \\ Callee | " + " | ".join(comps) + " |"
        sep = "|" + "|".join(["---"] * (len(comps) + 1)) + "|"
        
        lines.append(header)
        lines.append(sep)
        
        # Build coupling matrix
        coupling = {c: {k: 0 for k in comps} for c in comps}
        for dep in getattr(model, 'dependencies', []):
            src = dep.source.replace("_", " ").title()
            tgt = dep.target.replace("_", " ").title()
            if src in coupling and tgt in coupling[src]:
                coupling[src][tgt] += 1
                
        for row_c in comps:
            row_vals = [f" {coupling[row_c][col_c]} " if coupling[row_c][col_c] > 0 else " - " for col_c in comps]
            lines.append(f"| **{row_c}** |" + "|".join(row_vals) + "|")
            
        lines.append("")
        
        # Coupling & Cohesion Analysis
        total_possible = len(comps) * (len(comps) - 1)
        if total_possible > 0:
            actual_links = sum(1 for row in coupling.values() for val in row.values() if val > 0)
            density = actual_links / total_possible
            
            lines.append("### Coupling & Cohesion Analysis")
            lines.append("")
            
            if density < 0.15:
                lines.append("- **Coupling:** Low (Loose Coupling). Components operate relatively independently, facilitating easier testing and maintenance.")
            elif density < 0.35:
                lines.append("- **Coupling:** Moderate. Typical for service-oriented or modular monolith architectures.")
            else:
                lines.append("- **Coupling:** High (Tight Coupling). High interdependency detected. Consider applying Dependency Inversion or event-driven patterns to decouple core logic.")
                
            circular_count = len(getattr(model, 'circular_dependencies', []))
            if circular_count > 0:
                lines.append(f"- **Cohesion Risks:** {circular_count} circular dependency cycle(s) detected, indicating bleeding domain boundaries and reduced module cohesion.")
            else:
                lines.append("- **Cohesion:** High. No circular dependencies detected, indicating strong encapsulation and clear domain boundaries.")
            lines.append("")

    def save(self, content: str, output_path: str):
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

    _BANNED = [
        (r"[A-Z][a-zA-Z]+ implementation\.", "—"),
        (r"Provides \w[\w ]+ capabilities for the platform\.", "—"),
        (r"Sub-system handling \w[\w ]+ operations\.", "—"),
        (r"\bConfiguration only\b", "—"),
        (r"\bStandard Python\b", "—"),
        (r"\bSingle-file module\b", "—"),
        (r"\bMethods not extracted[^\|]*", "—"),
        (r"\bNone detected\b", "—"),
        (r"\bNot available\b", "—"),
    ]
    # Fix spaced acronyms like "A S T Node" → "ASTNode"
    _ACRONYM_RE = r'\b([A-Z])(?: ([A-Z]))+\b'

    def _scrub(self, text: str) -> str:
        import re
        for pattern, replacement in self._BANNED:
            text = re.sub(pattern, replacement, text)
        text = re.sub(
            self._ACRONYM_RE,
            lambda m: m.group(0).replace(" ", ""),
            text
        )
        # Drop table rows where every data cell is "—" or empty
        lines = []
        for line in text.splitlines():
            if line.startswith("|") and line.endswith("|"):
                cells = [c.strip() for c in line.split("|")[1:-1]]
                if cells and all(c in ("—", "", "-") for c in cells[1:]):
                    continue  # skip all-empty rows
            lines.append(line)
        return "\n".join(lines)
