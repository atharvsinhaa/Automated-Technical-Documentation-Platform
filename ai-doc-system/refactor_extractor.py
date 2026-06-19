import re
import ast

with open('backend/object_model_extractor/extractor.py', 'r') as f:
    content = f.read()

# RULE 1: Fix Template Strings
# Replace '"Provides {name} capabilities for the platform."'
content = re.sub(
    r'responsibility=f"Provides \{name\} capabilities for the platform\."',
    r'responsibility="[EXTRACTION INCOMPLETE — add docstrings to source code]"',
    content
)
content = re.sub(
    r'responsibility=f"Provides \{mod_name\} capabilities for the platform\."',
    r'responsibility="[EXTRACTION INCOMPLETE — add docstrings to source code]"',
    content
)

# Replace "Any" with "untyped" inside _extract_classes_and_interfaces
content = content.replace("'Any'", "'untyped'")
content = content.replace('"Any"', '"untyped"')

# RULE 4: Deduplicate Classes in extract() method
# Find def extract
extract_idx = content.find("def extract(")
return_model_idx = content.find("return model", extract_idx)

# Inject deduplication logic right before `return model`
dedup_logic = """
        # --- RULE 4: Deduplication ---
        def dedup(items):
            seen = {}
            for item in items:
                key = item.name
                if key not in seen:
                    seen[key] = item
                else:
                    existing = seen[key]
                    # Merge logic for classes/interfaces
                    if hasattr(item, 'methods') and len(item.methods) > len(existing.methods):
                        seen[key] = item
            return list(seen.values())
        
        model.classes = dedup(model.classes)
        model.interfaces = dedup(model.interfaces)
        model.database_objects = dedup(model.database_objects)
        
        sf_seen = {}
        for sf in model.sequence_flows:
            if sf.name not in sf_seen or len(sf.steps) > len(sf_seen[sf.name].steps):
                sf_seen[sf.name] = sf
        model.sequence_flows = list(sf_seen.values())

        """

if "def dedup(items):" not in content:
    content = content[:return_model_idx] + dedup_logic + content[return_model_idx:]

with open('backend/object_model_extractor/extractor_test.py', 'w') as f:
    f.write(content)

print("Applied quick fixes.")
