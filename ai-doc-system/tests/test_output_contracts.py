"""
Output contract tests — verify document quality constraints
that must hold for ANY repository input.
"""
import pytest
import re
from backend.object_model_extractor.models import LLDModel, LLDSequenceFlow
from backend.document_generator.lld_generator import LLDGenerator
from backend.diagram_generator.lld_sequence_generator import LLDSequenceGenerator


def make_minimal_model(**kwargs) -> LLDModel:
    from backend.object_model_extractor.models import LLDClass, LLDMethod
    defaults = dict(
        repository_type="web_application",
        classes=[LLDClass(
            name="OrderService",
            file_path="src/order_service.py",
            description="Handles orders",
            methods=[LLDMethod(name="create_order", signature="create_order(data)",
                               parameters=["data"], return_type="Order")],
            fields=["id: int"],
        )],
        sequence_flows=[LLDSequenceFlow(
            name="POST /orders",
            trigger="HTTP POST",
            steps=["Client → OrderService: POST /orders",
                   "OrderService: Validate request body",
                   "OrderService: Persist to database",
                   "OrderService → Client: return 201 Created"],
            description="Create order flow",
        )],
    )
    defaults.update(kwargs)
    return LLDModel(**defaults)


def test_executive_summary_non_empty():
    model = make_minimal_model()
    gen = LLDGenerator()
    md = gen.generate(model, repo_path="")
    assert "## Executive Summary" in md
    summary_start = md.index("## Executive Summary") + len("## Executive Summary")
    next_section = md.find("##", summary_start)
    summary_text = md[summary_start:next_section]
    assert len(summary_text.strip()) > 50, "Executive summary is empty"


def test_class_diagram_no_unclosed_parenthesis():
    model = make_minimal_model()
    gen = LLDSequenceGenerator()
    diagrams = gen.generate(model)
    class_diag = diagrams.get("class_diagram", "")
    # Must not contain unclosed signatures like +methodName(
    bad_sigs = re.findall(r'\+\w+\($', class_diag, re.MULTILINE)
    assert not bad_sigs, f"Unclosed method signatures: {bad_sigs}"


def test_sequence_diagram_not_empty_when_flows_exist():
    model = make_minimal_model()
    gen = LLDSequenceGenerator()
    diagrams = gen.generate(model)
    seq = diagrams.get("sequence_diagram", "")
    assert "No execution flows" not in seq, (
        "Sequence diagram shows fallback despite sequence_flows being present"
    )
    assert "->>" in seq or "-->" in seq, "Sequence diagram has no arrows"


def test_no_component_uri_in_module_paths():
    model = make_minimal_model()
    gen = LLDGenerator()
    md = gen.generate(model, repo_path="")
    assert "component://" not in md, "Fake component:// URIs found in LLD output"


def test_api_repos_with_no_kg_still_get_sequence_flows():
    """Regression: API endpoint flows must not be empty for non-KG repos."""
    from backend.semantic_ir.models import SemanticIR, IRApiEndpoint
    from backend.object_model_extractor.extractor import ObjectModelExtractor
    ir = SemanticIR(
        repository_type="web_application",
        api_endpoints=[
            IRApiEndpoint(path="/orders", method="POST", service="OrderService"),
            IRApiEndpoint(path="/orders/{id}", method="GET", service="OrderService"),
        ],
    )
    extractor = ObjectModelExtractor()
    lld_model = extractor.extract(ir, kg=None)
    assert len(lld_model.sequence_flows) > 0, (
        "API repos without KG produce zero sequence flows — API flow source is missing"
    )


def test_erd_types_are_mermaid_compatible():
    """ERD must not contain Python type wrappers like Optional[, List[."""
    model = make_minimal_model()
    gen = LLDSequenceGenerator()
    diagrams = gen.generate(model)
    erd = diagrams.get("erd_diagram", "")
    if "erDiagram" in erd:
        assert "Optional[" not in erd, "Python Optional[] type in ERD"
        assert "List[" not in erd, "Python List[] type in ERD"
