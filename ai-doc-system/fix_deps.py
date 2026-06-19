import re

with open('backend/document_generator/lld_generator.py', 'r') as f:
    code = f.read()

code = code.replace(', dependencies=["Volume Mounts"]', '')
code = code.replace(', dependencies=["Models"]', '')
code = code.replace(', dependencies=["Python"]', '')
code = code.replace(', dependencies=["Pip Packages"]', '')

code = code.replace('| Env Variables | Depends On |', '| Env Variables | Components |')
code = code.replace('|---------------|------------|', '|---------------|------------|')

def rep_func(match):
    return match.group(0).replace('deps = ", ".join(unit.dependencies) if getattr(unit, "dependencies", None) else "—"', 'deps = ", ".join(unit.hosts_components) if getattr(unit, "hosts_components", None) else "—"')

code = re.sub(r'deps = .*?else "—"', 'deps = ", ".join(unit.hosts_components) if getattr(unit, "hosts_components", None) else "—"', code)

with open('backend/document_generator/lld_generator.py', 'w') as f:
    f.write(code)
print("Dependencies fixed.")
