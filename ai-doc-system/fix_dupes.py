with open("backend/diagram_generator/lld_sequence_generator.py", "r") as f:
    code = f.read()

code = code.replace(
    'proven_stages.append(stage)',
    'if n_id not in [s[1] for s in proven_stages]: proven_stages.append(stage)'
)

with open("backend/diagram_generator/lld_sequence_generator.py", "w") as f:
    f.write(code)

print("Fixed dupes.")
