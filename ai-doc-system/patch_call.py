with open("backend/document_generator/lld_generator.py", "r") as f:
    code = f.read()

old_call = """        self._section_circular_dependencies(body_lines, model)
        self._section_module_map(body_lines, model, dp)"""

new_call = """        self._section_dependency_matrix(body_lines, model)
        self._section_circular_dependencies(body_lines, model)
        self._section_module_map(body_lines, model, dp)"""

code = code.replace(old_call, new_call)

# wait, I also want to remove `self._section_dependencies(body_lines, model, dp)`? No, section_dependencies generates External Integrations. The request asks to remove Component Dependency Diagram section, which was inside _section_module_map.

with open("backend/document_generator/lld_generator.py", "w") as f:
    f.write(code)
print("Patched call")
