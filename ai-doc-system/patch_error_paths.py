import re

with open("backend/object_model_extractor/extractor.py", "r") as f:
    code = f.read()

old_src3 = """            # Source 3: Exception CLASS definitions
            for cls in kg.nodes_by_type("CLASS"):
                if any(x in cls.name for x in ("Error", "Exception", "Warning", "Fault")):
                    parent_name = "Exception"
                    for edge in kg.outgoing_edges(cls.id):
                        if str(edge.relation).endswith("EXTENDS"):
                            parent = kg.nodes.get(edge.to_id)
                            if parent:
                                parent_name = parent.name
                            break
                    key = (cls.name, "definition")
                    if key not in seen:
                        seen.add(key)
                        paths.append(LLDErrorPath(
                            source="Global",
                            error_type=cls.name,
                            handler="Defined custom error",
                            recovery_strategy=f"Custom exception extending {parent_name}",
                            trigger=f"System throws {cls.name}",
                            affected_component="Global",
                            impact="Defined custom error",
                            severity="Info"
                        ))"""

new_src3 = """            # Source 3: Operational Failures mapping
            operational_errors = {
                "Neo4jError": ("Database Connection", "Neo4j connection fails or query times out", "Data Persistence", "Graph updates fail", "Retry with exponential backoff", "High"),
                "OllamaError": ("LLM Service", "Ollama API unreachable or times out", "AI Engine", "Semantic inference fails", "Fallback to stub or retry", "High"),
                "XMLParseError": ("File Parser", "Malformed XML or encoding issue", "AST Builder", "Repository indexing halts", "Skip file and log warning", "Medium"),
                "RepositoryValidationError": ("Source Loader", "Invalid repository structure", "Project Loader", "Pipeline fails to start", "Abort and notify user", "Critical"),
                "FileAccessError": ("I/O System", "Permission denied or file missing", "File System", "Incomplete analysis", "Log error and continue", "Medium")
            }
            
            for cls in kg.nodes_by_type("CLASS"):
                if cls.name in operational_errors:
                    source, trigger, comp, impact, recovery, severity = operational_errors[cls.name]
                    key = (cls.name, "operational")
                    if key not in seen:
                        seen.add(key)
                        paths.append(LLDErrorPath(
                            source=source,
                            error_type=cls.name,
                            handler="Global Error Handler",
                            recovery_strategy=recovery,
                            trigger=trigger,
                            affected_component=comp,
                            impact=impact,
                            severity=severity
                        ))"""

code = code.replace(old_src3, new_src3)

with open("backend/object_model_extractor/extractor.py", "w") as f:
    f.write(code)

print("Patched error paths.")
