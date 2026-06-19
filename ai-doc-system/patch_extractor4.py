with open("backend/object_model_extractor/extractor.py", "r") as f:
    lines = f.readlines()

for i in range(len(lines)):
    if "def _extract_circular_dependencies(" in lines[i] or "def _extract_entrypoints(" in lines[i]:
        # if they start with 4 spaces exactly, we do nothing. if 0 spaces, we add 4.
        pass

# Actually, let's just do a regex replace to fix indentation
import re
with open("backend/object_model_extractor/extractor.py", "r") as f:
    code = f.read()

code = code.replace("\n    def _extract_circular_dependencies", "\n    def _extract_circular_dependencies") # Wait, in my previous patch: "    def _extract_circular_dependencies" was the string.
