import os
import re

def read_file(path):
    with open(path, 'r') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w') as f:
        f.write(content)

# ---------------------------------------------------------
# PROMPT 9: backend/diagram_generator/hld_mermaid_generator.py
# ---------------------------------------------------------
path_hld_mermaid = "backend/diagram_generator/hld_mermaid_generator.py"
content = read_file(path_hld_mermaid)

if "ACTOR_KEYWORDS =" not in content:
    old_float = """        floating = declared_nodes - nodes_in_edges
        if len(floating) > 1:
            return False"""
    
    new_float = """        ACTOR_KEYWORDS = {"user", "client", "actor", "admin", "external",
                          "browser", "mobile", "consumer", "caller"}
        floating = declared_nodes - nodes_in_edges
        # Actors legitimately have no incoming edges — exclude them from float count
        non_actor_floating = {
            n for n in floating
            if not any(kw in n.lower() for kw in ACTOR_KEYWORDS)
        }
        if len(non_actor_floating) > 1:
            return False"""
            
    content = content.replace(old_float, new_float)
    write_file(path_hld_mermaid, content)

# ---------------------------------------------------------
# PROMPT 10: backend/architecture_intelligence/narrative_engine.py
# ---------------------------------------------------------
path_narrative = "backend/architecture_intelligence/narrative_engine.py"
content = read_file(path_narrative)

if "domain_name = domain.primary_domain or" not in content:
    # Need to replace the entire _template_executive_summary
    match = re.search(r'    def _template_executive_summary\(.*?\)(?:.|\n)*?(?=    def )', content, re.DOTALL)
    if match:
        old_method = match.group(0)
        new_method = """    def _template_executive_summary(
        self, domain, capabilities, services, information,
        languages, frameworks, databases, ai_ml_tools
    ) -> str:
        domain_name = domain.primary_domain or "Enterprise"
        sub = f" ({domain.sub_domain})" if domain.sub_domain else ""
        lang_str = ", ".join(languages[:3]) if languages else "Python"
        fw_str   = ", ".join(frameworks[:2]) if frameworks else "standard libraries"
        db_str   = ", ".join(databases[:2]) if databases else ""
        style    = getattr(services, "architecture_style", "") or "Modular"
        biz_fns  = ", ".join(domain.business_functions[:3]) if domain.business_functions else ""
        contexts = ", ".join(domain.bounded_contexts[:3]) if domain.bounded_contexts else ""

        core_caps = capabilities.core_capabilities or []
        cap_str = "; ".join(
            f"{c.name} ({c.description[:60].rstrip('.')})"
            for c in core_caps[:3]
        ) if core_caps else "core platform capabilities"

        p1 = (
            f"This document describes the architecture of a {domain_name}{sub} system "
            f"implemented in {lang_str} using {fw_str}. "
            f"The system delivers {len(core_caps)} primary business capability(ies): {cap_str}."
        )
        p2 = (
            f"The platform supports {biz_fns or 'core business operations'} "
            + (f"across {contexts} bounded contexts. " if contexts else "")
            + f"It is organized into {len(services.services)} architectural service(s) "
            f"following a {style} pattern."
            + (f" Data is persisted across {db_str}." if db_str else "")
        )

        rationale = getattr(services, "architecture_rationale", "") or ""
        p3 = (
            f"The architecture follows {style.lower()}, "
            f"enabling {(domain.business_functions[0].lower() if domain.business_functions else 'core operations')} "
            f"with maintainability and extensibility as primary design goals."
            + (f" {rationale}" if rationale and rationale not in p3 else "")
        )

        return f"{p1}\\n\\n{p2}\\n\\n{p3}"
\n"""
        content = content.replace(old_method, new_method)
        write_file(path_narrative, content)

# ---------------------------------------------------------
# PROMPT 11 B: backend/diagram_generator/lld_sequence_generator.py
# ---------------------------------------------------------
path_lld_seq = "backend/diagram_generator/lld_sequence_generator.py"
content = read_file(path_lld_seq)

if "def _clean_erd_type" not in content:
    helper = """    def _clean_erd_type(self, python_type: str) -> str:
        \"\"\"Convert Python type annotations to Mermaid erDiagram types.\"\"\"
        t = python_type.strip()
        # Strip wrappers
        for wrapper in ("Optional[", "List[", "Set[", "Dict[", "Tuple["):
            if t.startswith(wrapper):
                t = t[len(wrapper):].rstrip("]")
        # Map Python → SQL-compatible
        TYPE_MAP = {
            "str": "string", "int": "int", "float": "float",
            "bool": "boolean", "datetime": "datetime", "date": "date",
            "bytes": "binary", "Any": "string", "None": "string",
        }
        return TYPE_MAP.get(t, "string")\n
    def _generate_erd_diagram"""
    content = content.replace("    def _generate_erd_diagram", helper)
    
    # replace field type append
    content = content.replace(
        'lines.append(f"        {ftype} {self._safe_id(fname)}")',
        'lines.append(f"        {self._clean_erd_type(ftype)} {self._safe_id(fname)}")'
    )
    write_file(path_lld_seq, content)

