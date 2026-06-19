from backend.semantic_ir.ir_builder import IRBuilder
from backend.object_model_extractor.extractor import ObjectModelExtractor

repo = "mock_repos/fastapi_crud"
builder = IRBuilder()
ir = builder.build(repo)
kg = builder.kg

extractor = ObjectModelExtractor()
tables = extractor._extract_data_type_tables(ir, kg)
print(f"Extracted {len(tables)} tables")
for t in tables:
    print(t.name)
