import re

with open("backend/object_model_extractor/extractor.py", "r") as f:
    code = f.read()

# 1. Error paths:
# Search for the instantiation of LLDErrorPath
old_err_ir = """paths.append(LLDErrorPath(
                    source=ep.source_function,
                    error_type=ep.error_type or "Exception",
                    handler=ep.error_handler or "caller",
                    recovery_strategy=ep.recovery_strategy,
                ))"""
new_err_ir = """impact = "System halted" if (ep.error_type and "Error" in ep.error_type) else "Process failed"
                severity = "High" if "Error" in (ep.error_type or "") else "Medium"
                paths.append(LLDErrorPath(
                    source=ep.source_function,
                    error_type=ep.error_type or "Exception",
                    handler=ep.error_handler or "caller",
                    recovery_strategy=ep.recovery_strategy,
                    trigger=f"{ep.source_function} invoked with invalid state",
                    affected_component=ep.source_function.split('.')[0] if '.' in ep.source_function else "Application",
                    impact=impact,
                    severity=severity
                ))"""
code = code.replace(old_err_ir, new_err_ir)

old_err_raises = """paths.append(LLDErrorPath(source=node.name, error_type=exc_type,
                                handler="caller", recovery_strategy="Propagated to caller"))"""
new_err_raises = """paths.append(LLDErrorPath(source=node.name, error_type=exc_type,
                                handler="caller", recovery_strategy="Propagated to caller",
                                trigger=f"Execution of {node.name}", affected_component=node.name,
                                impact="Caller operation fails", severity="Medium"))"""
code = code.replace(old_err_raises, new_err_raises)

old_err_catches = """paths.append(LLDErrorPath(source=node.name, error_type=exc_type,
                                handler=node.name, recovery_strategy="Internal handler"))"""
new_err_catches = """paths.append(LLDErrorPath(source=node.name, error_type=exc_type,
                                handler=node.name, recovery_strategy="Internal handler",
                                trigger=f"Exception {exc_type} caught", affected_component=node.name,
                                impact="Handled internally", severity="Low"))"""
code = code.replace(old_err_catches, new_err_catches)

old_err_def = """paths.append(LLDErrorPath(
                            source="(raised by system)",
                            error_type=cls.name,
                            handler="catch block",
                            recovery_strategy=cls.docstring[:80] if cls.docstring
                                              else f"Custom exception extending {parent_name}",
                        ))"""
new_err_def = """paths.append(LLDErrorPath(
                            source="(raised by system)",
                            error_type=cls.name,
                            handler="catch block",
                            recovery_strategy=cls.docstring[:80] if cls.docstring
                                              else f"Custom exception extending {parent_name}",
                            trigger=f"System throws {cls.name}",
                            affected_component="Global",
                            impact="Defined custom error",
                            severity="Info"
                        ))"""
code = code.replace(old_err_def, new_err_def)

old_err_val = """paths.append(LLDErrorPath(
                            source=fn.name, error_type="ValidationError",
                            handler=fn.name, recovery_strategy="Early return with error details",
                        ))"""
new_err_val = """paths.append(LLDErrorPath(
                            source=fn.name, error_type="ValidationError",
                            handler=fn.name, recovery_strategy="Early return with error details",
                            trigger="Invalid input parameters",
                            affected_component=fn.name,
                            impact="Validation fails, operation aborted",
                            severity="Medium"
                        ))"""
code = code.replace(old_err_val, new_err_val)

# 2. Components
old_comp = """components.append(LLDComponent(
                name=comp.name,
                component_type=comp_type,
                layer=layer,
                responsibility=comp.description or f"{comp_type} component",
                depends_on=list(set(deps))[:6],
                technology=", ".join(ir.frameworks[:2]) if ir.frameworks else "",
            ))"""

new_comp = """
            tech_evidence = []
            if kg:
                for node in kg.nodes.values():
                    if "test" in node.file_path.lower() or "mock" in node.file_path.lower(): continue
                    if name_lower in node.name.lower() or name_lower in node.file_path.lower():
                        for rel in node.dependencies:
                            if rel.relation_type == KGRelationType.IMPORTS:
                                target = kg.get_node(rel.target_id)
                                if target and any(k in target.name.lower() for k in ["kafka", "celery", "fastapi", "anthropic", "openai", "sqlalchemy", "neo4j", "pydantic", "jinja", "react"]):
                                    tech_evidence.append(f"{target.name} ({node.file_path})")
            tech_evidence = list(set(tech_evidence))
            tech_list = list(set(e.split(" ")[0] for e in tech_evidence))
            technology = ", ".join(tech_list) if tech_list else ""
            
            purpose = comp.description or f"{comp_type} logic for {comp.name}"
            consumes = ["Data payload"] if "repository" not in name_lower else ["Database queries"]
            produces = ["Response models"] if "repository" not in name_lower else ["Data objects"]
            artifacts = []
            
            # Use IR to get real consumes/produces
            for cls in getattr(ir, 'classes', []):
                if name_lower in cls.name.lower():
                    if getattr(cls, 'receives', None): consumes = [cls.receives]
                    if getattr(cls, 'returns', None): produces = [cls.returns]
            
            components.append(LLDComponent(
                name=comp.name,
                component_type=comp_type,
                layer=layer,
                purpose=purpose,
                consumes=consumes,
                produces=produces,
                artifacts=artifacts,
                depends_on=list(set(deps))[:6],
                technology=technology,
                tech_evidence=tech_evidence,
            ))"""

code = code.replace(old_comp, new_comp)

# 3. Modules
old_mod = """modules.append(LLDModule(name=mod_name, package_path=pkg, responsibility=f"Handles operations for {mod_name}", classes_contained=classes))"""
new_mod = """
            tech_evidence = []
            for c in components:
                if c.name in classes and hasattr(c, 'tech_evidence'):
                    tech_evidence.extend(c.tech_evidence)
            tech_evidence = list(set(tech_evidence))
            modules.append(LLDModule(name=mod_name, package_path=pkg, responsibility=f"Handles operations for {mod_name}", classes_contained=classes, tech_evidence=tech_evidence))"""
code = code.replace(old_mod, new_mod)

with open("backend/object_model_extractor/extractor.py", "w") as f:
    f.write(code)

print("Patch applied to extractor.py")
