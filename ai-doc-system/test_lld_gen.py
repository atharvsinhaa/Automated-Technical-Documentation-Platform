from backend.semantic_ir.ir_builder import IRBuilder
from backend.object_model_extractor.extractor import ObjectModelExtractor
from backend.document_generator.lld_generator import LLDGenerator

repo = "mock_repos/fastapi_crud"
builder = IRBuilder()
ir = builder.build(repo)
kg = builder.kg

extractor = ObjectModelExtractor()
model = extractor.extract(ir, kg)

gen = LLDGenerator()
lines = []
gen._section_data_types_and_tables(lines, model)
print("\n".join(lines))
