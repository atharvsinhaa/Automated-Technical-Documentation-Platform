from backend.docx_service.mermaid_renderer import MermaidToPng
import sys
r = MermaidToPng(verbose=True)
res = r.render("flowchart TD\n  A-->B", "/tmp", "test")
print("Rendered:", res)
