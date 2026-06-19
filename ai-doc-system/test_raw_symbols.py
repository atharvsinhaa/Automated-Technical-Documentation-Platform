from backend.dependency_extractor.xml_loader import load

project = load("mock_repos/fastapi_crud/outputs/combined.xml")
for fr in project.files:
    for sym in fr.symbols:
        if "user" in sym.name.lower():
            print(f"File: {fr.rel_path}, Symbol: {sym.name}, Decorators: {sym.decorators}")
