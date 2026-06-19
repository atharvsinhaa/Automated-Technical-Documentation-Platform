import json

with open("/Users/sarabafna/.gemini/antigravity-ide/brain/0be367b7-6d56-4d6a-b11f-51a2682ea11a/.system_generated/logs/transcript.jsonl", "r") as f:
    for line in f:
        data = json.loads(line)
        if data.get("type") == "VIEW_FILE" or data.get("type") == "GENERIC":
            content = data.get("content", "")
            if "lld_sequence_generator.py" in content and "def _generate_component_architecture_diagram" in content:
                print("FOUND!")
                with open("scratch.txt", "w") as out:
                    out.write(content)
                break
