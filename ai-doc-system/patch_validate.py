with open("backend/document_generator/lld_generator.py", "r") as f:
    code = f.read()

old_val = """        # Mock/Test contamination in tech stack
        for comp in getattr(model, 'components', []):
            tech_evidence = getattr(comp, 'tech_evidence', [])
            for e in tech_evidence:
                if "test" in e.lower() or "mock" in e.lower():
                    warnings.append(f"Validation Failed: Test contamination detected in {comp.name} tech evidence.")
                    
            if "Transforms" in getattr(comp, 'purpose', ""):
                warnings.append(f"Validation Failed: Generic signature-based heuristics detected in {comp.name}.")"""

new_val = """        # Mock/Test contamination in tech stack
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
                warnings.append(f"Validation Failed: Generic 'Response models' detected in {comp.name}.")"""

code = code.replace(old_val, new_val)

with open("backend/document_generator/lld_generator.py", "w") as f:
    f.write(code)

print("Patched validation gate.")
