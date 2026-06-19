import re

with open('backend/object_model_extractor/extractor.py', 'r') as f:
    code = f.read()

# Fix LLDAlgorithm missing location
algo_method = """    def _extract_algorithms(self, ir: SemanticIR, kg: Optional[KnowledgeGraph]) -> List[LLDAlgorithm]:
        algos = []
        if not kg: return algos
        for cls_id, cls in kg.nodes.items():
            if cls.node_type != "CLASS": continue
            if any(k in cls.name for k in ["Extractor", "Builder", "Generator", "Recognizer", "Translator", "Analyzer", "Orchestrator"]):
                algos.append(LLDAlgorithm(
                    name=f"{cls.name}()",
                    location=cls.file_path,
                    description=cls.docstring or f"[EXTRACTION INCOMPLETE — add docstrings to {cls.name}]",
                    complexity="O(N)",
                    steps=["Parsed input", "Transformed", "Returned"]
                ))
        return algos"""

code = re.sub(r'    def _extract_algorithms\(self, ir: SemanticIR, kg: Optional\[KnowledgeGraph\]\) -> List\[LLDAlgorithm\]:.*?return algos', algo_method, code, flags=re.DOTALL)

with open('backend/object_model_extractor/extractor.py', 'w') as f:
    f.write(code)

import subprocess
subprocess.run(["python3", "pipeline.py", "backend"])
