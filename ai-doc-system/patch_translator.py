with open("backend/semantic_bridge/kg_to_ir_translator.py", "r") as f:
    code = f.read()

old_fallback = """        # ── Final fallback (should rarely trigger) ────────────
        name_human = name.replace("_", " ").title()
        return f"Provides {name_human} capabilities for the platform.""""

new_fallback = """        # ── Final fallback (should rarely trigger) ────────────
        return \"\""""

code = code.replace(old_fallback, new_fallback)

# There is also one more generic fallback at strategy 4 maybe?
old_dep = """        # ── Strategy 4: Dependency-based inference ────────────
        if dependencies:
            dep_names = ", ".join(
                d.replace("_", " ").title() for d in dependencies[:3]
            )
            name_human = name.replace("_", " ").title()
            return (
                f"Coordinates {name_human} functionality, integrating "
                f"with {dep_names}."
            )"""
            
new_dep = """        # ── Strategy 4: Dependency-based inference ────────────
        if dependencies:
            dep_names = ", ".join(
                d.replace("_", " ").title() for d in dependencies[:3]
            )
            name_human = name.replace("_", " ").title()
            return (
                f"Coordinates {name_human} functionality, integrating "
                f"with {dep_names}."
            )"""
            
code = code.replace(old_dep, new_dep)

with open("backend/semantic_bridge/kg_to_ir_translator.py", "w") as f:
    f.write(code)
print("Patched kg_to_ir_translator.py")
