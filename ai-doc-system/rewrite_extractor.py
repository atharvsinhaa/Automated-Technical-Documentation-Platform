import re

with open('backend/object_model_extractor/extractor.py', 'r') as f:
    content = f.read()

# Replace the "Any" with "untyped"
content = content.replace("'Any'", "'untyped'")
content = content.replace('"Any"', '"untyped"')

# ---------------------------------------------------------
# Deduplication (Rule 4)
# ---------------------------------------------------------
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

        return model"""

content = content.replace("return model", dedup_logic)

# ---------------------------------------------------------
# Write it out
# ---------------------------------------------------------
with open('backend/object_model_extractor/extractor.py', 'w') as f:
    f.write(content)
print("Extractor deduplication and Any replacement complete.")
