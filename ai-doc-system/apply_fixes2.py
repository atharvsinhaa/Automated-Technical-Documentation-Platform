import os
import re

def read_file(path):
    with open(path, 'r') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w') as f:
        f.write(content)

# ---------------------------------------------------------
# PROMPT 3: backend/architecture_extractor/extractor.py
# ---------------------------------------------------------
path_arch_ext = "backend/architecture_extractor/extractor.py"
content = read_file(path_arch_ext)
if "_classify_layer" not in content:
    content = content.replace(
        'layer=cap.name.split()[-1] if " " in cap.name else "Application"',
        'layer=self._classify_layer(cap.name)'
    )
    new_method = """    def _classify_layer(self, name: str) -> str:
        n = name.lower()
        if any(k in n for k in ("controller","router","view","endpoint","handler","frontend","ui")):
            return "Presentation"
        if any(k in n for k in ("service","manager","orchestrator","use case","application")):
            return "Application"
        if any(k in n for k in ("model","entity","schema","repository","domain","rule","aggregate")):
            return "Domain"
        if any(k in n for k in ("database","cache","queue","config","infra","store","persistence","adapter")):
            return "Infrastructure"
        return "Application"

    def _infer_frameworks"""
    content = content.replace("    def _infer_frameworks", new_method)
    write_file(path_arch_ext, content)

# ---------------------------------------------------------
# PROMPT 3 & 11: backend/architecture_intelligence/service_architect.py
# ---------------------------------------------------------
path_srv_arch = "backend/architecture_intelligence/service_architect.py"
content = read_file(path_srv_arch)

old_dict = """_TYPE_TO_LAYER = {
    "Core": "Domain",
    "Supporting": "Application",
    "Generic": "Infrastructure"
}"""

new_dict = """_TYPE_TO_LAYER = {
    "Domain":        "Domain",
    "Application":   "Application",
    "Infrastructure":"Infrastructure",
    "Integration":   "Infrastructure",
    # AIM tier values
    "Core":          "Domain",
    "Supporting":    "Application",
    "Generic":       "Infrastructure",
}"""

if '"Domain":        "Domain"' not in content:
    content = content.replace(old_dict, new_dict)

if "if domain.primary_domain == \"Architecture Documentation Platform\":" in content:
    lines = content.split('\n')
    new_lines = []
    skip = False
    for line in lines:
        if 'if domain.primary_domain == "Architecture Documentation Platform":' in line:
            skip = True
        elif skip and 'return "Semantic Processing Pipeline", "The system performs sequential' in line:
            skip = False
            continue
        elif skip:
            continue
        else:
            new_lines.append(line)
    content = '\n'.join(new_lines)
write_file(path_srv_arch, content)

# ---------------------------------------------------------
# PROMPT 5: backend/ast_engine/languages/registry.py
# ---------------------------------------------------------
path_registry = "backend/ast_engine/languages/registry.py"
content = read_file(path_registry)

old_reg = """def _register_all():
    try:
        import tree_sitter_python as m
        _try("python", [".py", ".pyw", ".pyx"], m.language)
    except ImportError:
        pass
    
    try:
        import tree_sitter_javascript as m
        _try("javascript", [".js", ".jsx"], m.language)
    except ImportError:
        pass

_register_all()"""

new_reg = """def _register_all():
    # Python (always available)
    try:
        import tree_sitter_python as m
        _try("python", [".py", ".pyw", ".pyx"], m.language)
    except ImportError:
        pass

    # JavaScript / TypeScript
    try:
        import tree_sitter_javascript as m
        _try("javascript", [".js", ".jsx", ".mjs"], m.language)
    except ImportError:
        pass
    try:
        import tree_sitter_typescript as m
        _try("typescript", [".ts", ".tsx"], m.language_typescript)
    except ImportError:
        pass

    # Java
    try:
        import tree_sitter_java as m
        _try("java", [".java"], m.language)
    except ImportError:
        pass

    # Go
    try:
        import tree_sitter_go as m
        _try("go", [".go"], m.language)
    except ImportError:
        pass

    # Rust
    try:
        import tree_sitter_rust as m
        _try("rust", [".rs"], m.language)
    except ImportError:
        pass

    # C / C++
    try:
        import tree_sitter_c as m
        _try("c", [".c", ".h"], m.language)
    except ImportError:
        pass
    try:
        import tree_sitter_cpp as m
        _try("cpp", [".cpp", ".cc", ".cxx", ".hpp"], m.language)
    except ImportError:
        pass

_register_all()

def get_supported_extensions() -> list:
    return list(_EXTENSION_MAP.keys())
"""

if "tree_sitter_java" not in content:
    content = content.replace(old_reg, new_reg)
    write_file(path_registry, content)

# ---------------------------------------------------------
# PROMPT 6: backend/document_generator/lld_generator.py
# ---------------------------------------------------------
path_lld_gen = "backend/document_generator/lld_generator.py"
content = read_file(path_lld_gen)

if "if fpath.suffix not in allowed_exts:" not in content:
    content = content.replace(
        "    def _build_class_ast_map(self, repo: Path, allowed_exts: set) -> dict:\n        result = {}\n        for fpath in repo.rglob(\"*\"):\n            if fpath.is_file() and fpath.suffix in allowed_exts:",
        "    def _build_class_ast_map(self, repo: Path, allowed_exts: set) -> dict:\n        result = {}\n        for fpath in repo.rglob(\"*\"):\n            if fpath.suffix not in allowed_exts:\n                continue\n            if fpath.is_file():"
    )
    write_file(path_lld_gen, content)

# ---------------------------------------------------------
# PROMPT 6: backend/context_builder/context_builder.py
# ---------------------------------------------------------
path_ctx_build = "backend/context_builder/context_builder.py"
content = read_file(path_ctx_build)

if "def _get_telecom_extractor(self):" not in content:
    content = content.replace(
        "        self.telecom_extractor = TelecomExtractor(self.client, self.traverser, verbose=verbose)",
        "        self._telecom_extractor = None\n\n    def _get_telecom_extractor(self):\n        if self._telecom_extractor is None:\n            from .telecom_context import TelecomExtractor\n            self._telecom_extractor = TelecomExtractor(self.client, self.traverser, verbose=self.verbose)\n        return self._telecom_extractor"
    )
    content = content.replace(
        "            if telecom_keywords & set(tags):\n                telecom_signals = self.telecom_extractor.extract(project_path)\n                if telecom_signals:",
        "            telecom_signals_found = {t for t in tags if t in telecom_keywords}\n            if telecom_signals_found:\n                telecom_signals = self._get_telecom_extractor().extract(project_path)\n                if telecom_signals:"
    )
    write_file(path_ctx_build, content)

# ---------------------------------------------------------
# PROMPT 8: backend/comment_engine/inline_commentor.py
# ---------------------------------------------------------
path_commentor = "backend/comment_engine/inline_commentor.py"
content = read_file(path_commentor)

if "overlap =" not in content:
    content = content.replace(
        """        if node_type == "function":
            purpose = self._infer_function_purpose(name)
            return f"# {purpose}\\n# Function: {name} (in {os.path.basename(source_file)})\"""",
        """        if node_type == "function":
            purpose = self._infer_function_purpose(name)
            import re
            name_words = set(re.sub(r'_', ' ', name.lower()).split())
            purpose_words = set(purpose.lower().split())
            overlap = name_words & purpose_words - {"the", "a", "an", "of", "in"}
            if len(overlap) >= len(name_words) * 0.8:
                return ""
            return f"# {purpose}\\n# Function: {name} (in {os.path.basename(source_file)})\""""
    )
    content = content.replace(
        """        elif node_type == "class":
            purpose = self._infer_class_purpose(name)
            return f"# Class: {name}\\n# {purpose}\\n# Defined in: {os.path.basename(source_file)}\"""",
        """        elif node_type == "class":
            purpose = self._infer_class_purpose(name)
            return (f"# Class: {name}\\n"
                    f"# {purpose}\\n"
                    f"# Defined in: {os.path.basename(source_file)}")"""
    )
    write_file(path_commentor, content)
