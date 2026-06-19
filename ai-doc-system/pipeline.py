#!/usr/bin/env python3
"""
pipeline.py
────────────────────────────────────────────────────────────────
End-to-end pipeline for the Repository Intelligence Platform.

Single entry point that chains:

  Repository
  → Repository Intelligence
  → AST Engine → Dependency Extraction → Knowledge Graph
  → KGToIRTranslator → SemanticIR
  → HLD Generator + LLD Generator + Diagram Generator

Usage:
  python3 pipeline.py /path/to/repo
  python3 pipeline.py /path/to/repo --output ./my-docs
  python3 pipeline.py /path/to/repo --kg-json /path/to/knowledge_graph.json
"""

from __future__ import annotations

import argparse
import os
import sys
from backend.ast_engine.languages.registry import get_supported_extensions
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(
        description="Repository Intelligence Platform — Full Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "repo_path",
        help="Path to the repository to analyze",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory (default: <repo>/outputs)",
    )
    parser.add_argument(
        "--kg-json",
        default=None,
        help="Path to pre-built knowledge_graph.json",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress verbose output",
    )
    parser.add_argument(
        "--llm",
        default="",
        help="LLM model name for AIE narrative generation (e.g. 'qwen2.5:7b'). "
             "Empty = deterministic mode (no LLM required).",
    )

    args = parser.parse_args()
    repo_path = os.path.abspath(args.repo_path)
    repo_name = os.path.basename(repo_path.rstrip("/"))
    output_dir = args.output or os.path.join(os.path.dirname(repo_path.rstrip("/")), os.path.basename(repo_path.rstrip("/")) + "-docs")
    verbose = not args.quiet
    llm_model = args.llm

    t_start = time.time()

    if verbose:
        print("\n" + "=" * 65)
        print("  Repository Intelligence Platform — Full Pipeline")
        print(f"  Repository: {repo_path}")
        print(f"  Output:     {output_dir}")
        print("=" * 65 + "\n")
        
        _supported = get_supported_extensions()
        print(f"[PIPELINE] AST languages registered: {_supported}")

    # ── Step 1: Build SemanticIR (full pipeline) ─────────────
    if verbose:
        print("[PIPELINE] Step 1: Building Semantic IR…\n")

    from backend.semantic_ir.ir_builder import IRBuilder

    builder = IRBuilder(verbose=verbose)

    # If a KG JSON is provided, load it and pass it
    kg = None
    if args.kg_json:
        try:
            from backend.knowledge_graph.models import KnowledgeGraph
            import json
            with open(args.kg_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            kg = KnowledgeGraph.from_dict(data)
            if verbose:
                print(
                    f"[PIPELINE] Loaded KG: {kg.node_count} nodes, "
                    f"{kg.edge_count} edges\n"
                )
        except Exception as e:
            print(f"[PIPELINE] WARNING: Failed to load KG JSON: {e}")

    semantic_ir = builder.build(repo_path, kg=kg)

    # ── Step 2: Generate HLD ─────────────────────────────────
    if verbose:
        print("\n[PIPELINE] Step 2: Generating HLD…")

    from backend.document_generator.hld_generator import HLDGenerator
    from backend.architecture_extractor.extractor import ArchitectureExtractor

    # Extract Architecture Blueprint
    extractor = ArchitectureExtractor()
    blueprint = extractor.extract(semantic_ir)

    # Save raw JSON for verification
    hld_json_path = os.path.join(output_dir, "hld", "architecture_blueprint.json")
    os.makedirs(os.path.dirname(hld_json_path), exist_ok=True)
    with open(hld_json_path, "w", encoding="utf-8") as f:
        f.write(blueprint.to_json())
        
    if len(blueprint.services) == 0:
        raise RuntimeError("Fail Loudly: 0 services discovered. Aborting generation. Do not generate placeholder documentation.")

    if verbose:
        print(f"\n[DEBUG] Discovered Services: {len(blueprint.services)}")
        for s in blueprint.services:
            print(f"  - {s.name}")
        print(f"[DEBUG] Discovered Workflows: {len(blueprint.workflows)}")
        for w in blueprint.workflows:
            print(f"  - {w.name}")
        print(f"[DEBUG] Discovered Data Flows: {len(blueprint.data_flows)}")
        for d in blueprint.data_flows:
            print(f"  - {d.name}")

    # Apply compression for document generation (raw blueprint kept for JSON export)
    from backend.document_generator.summarizer import DocumentationSummarizer
    summarizer = DocumentationSummarizer()
    hld_blueprint = summarizer.summarize_hld(blueprint)
    if verbose:
        hld_meta = hld_blueprint.metadata.get("summarizer", {})
        print(
            f"[SUMMARIZER] HLD: {hld_meta.get('shown_services')} / "
            f"{hld_meta.get('total_services')} services, "
            f"{hld_meta.get('shown_workflows')} / "
            f"{hld_meta.get('total_workflows')} workflows"
        )

    # ── Step 2b: Architecture Intelligence Engine (AIE) ──────
    aim = None
    try:
        from backend.architecture_intelligence.aim_builder import AIMBuilder

        if verbose:
            print("\n[PIPELINE] Step 2b: Architecture Intelligence Engine…")

        llm_client = None
        if llm_model:
            from backend.llm_orchestrator.llm_client import create_llm_client
            llm_client = create_llm_client(model=llm_model, verbose=verbose)

        aim_builder = AIMBuilder(llm_client=llm_client, verbose=verbose)
        aim = aim_builder.build(semantic_ir, hld_blueprint, repository_name=repo_name)

        # Validate minimum viability (P3 fix)
        if not aim.domain.primary_domain:
            raise ValueError("AIM domain classification failed — primary_domain is empty")
        if not aim.capabilities.core_capabilities:
            raise ValueError("AIM capability modeling produced zero core capabilities")
        if not aim.narrative.executive_summary or len(aim.narrative.executive_summary) < 50:
            raise ValueError("AIM narrative generation produced empty executive summary")

        # Save AIM JSON for inspection
        aim_json_path = os.path.join(output_dir, "hld", "architecture_intelligence_model.json")
        import json
        with open(aim_json_path, "w", encoding="utf-8") as f:
            json.dump(aim.to_dict(), f, indent=2, default=str)
        if verbose:
            print(f"  → AIM saved: {aim_json_path}")

    except Exception as e:
        import traceback
        print(f"\n[CRITICAL ERROR] Architecture Intelligence Engine (AIM) failed: {e}")
        traceback.print_exc()
        print("[FALLBACK] AIM generation aborted. HLD will be generated using baseline Semantic IR properties without intelligent analysis.")
        aim = None


    # ── Step 3: Generate LLD ─────────────────────────────────
    if verbose:
        print("[PIPELINE] Step 3: Generating LLD…")

    from backend.document_generator.lld_generator import LLDGenerator
    from backend.object_model_extractor.extractor import ObjectModelExtractor

    # Extract Object Model (LLDModel)
    obj_extractor = ObjectModelExtractor()
    lld_model = obj_extractor.extract(semantic_ir, getattr(builder, "kg", None))

    # Save raw JSON for verification
    lld_json_path = os.path.join(output_dir, "lld", "lld_model.json")
    os.makedirs(os.path.dirname(lld_json_path), exist_ok=True)
    with open(lld_json_path, "w", encoding="utf-8") as f:
        f.write(lld_model.to_json())
        
    if len(lld_model.classes) == 0:
        raise RuntimeError("Fail Loudly: 0 classes discovered. Aborting generation. Do not generate placeholder documentation.")

    if verbose:
        print(f"\n[DEBUG] Discovered Classes: {len(lld_model.classes)}")
        for c in lld_model.classes:
            print(f"  - {c.name}")
        print(f"[DEBUG] Discovered Interfaces: {len(lld_model.interfaces)}")
        for i in lld_model.interfaces:
            print(f"  - {i.name}")
        print(f"[DEBUG] Discovered Sequence Flows: {len(lld_model.sequence_flows)}")
        for f in lld_model.sequence_flows:
            print(f"  - {f.name}")

    # Apply compression for document generation (raw lld_model kept for JSON export)
    lld_summary = summarizer.summarize_lld(lld_model)
    if verbose:
        lld_meta = lld_summary.metadata.get("summarizer", {})
        print(
            f"[SUMMARIZER] LLD: {lld_meta.get('shown_classes')} / "
            f"{lld_meta.get('total_classes')} classes, "
            f"{lld_meta.get('shown_sequences')} / "
            f"{lld_meta.get('total_sequences')} sequence flows"
        )
    # ── Step 3b: KG -> IR Validation ─────────────────────────
    kg_obj = getattr(builder, "kg", None)
    if kg_obj:
        from backend.knowledge_graph.models import KGNodeType
        kg_api_count = len(kg_obj.nodes_by_type(KGNodeType.API_ENDPOINT))
        kg_class_count = len(kg_obj.nodes_by_type(KGNodeType.CLASS))
        kg_method_count = len(kg_obj.nodes_by_type(KGNodeType.METHOD))
        
        ir_api_count = len(semantic_ir.api_endpoints)
        lld_class_count = len(lld_model.classes)
        lld_method_count = sum(len(c.methods) for c in lld_model.classes)
        
        warnings = []
        if kg_api_count > 0 and ir_api_count < (kg_api_count * 0.5):
            warnings.append(f"APIs dropped (KG: {kg_api_count} -> IR: {ir_api_count})")
        if kg_class_count > 0 and lld_class_count < (kg_class_count * 0.5):
            warnings.append(f"Classes dropped (KG: {kg_class_count} -> LLD: {lld_class_count})")
        if kg_method_count > 0 and lld_method_count < (kg_method_count * 0.5):
            warnings.append(f"Methods dropped (KG: {kg_method_count} -> LLD: {lld_method_count})")
            
        if warnings:
            print("\n[WARNING] KG -> IR Data loss detected during translation:")
            for w in warnings:
                print(f"  - {w}")



    # ── Step 4: Generate Diagrams ────────────────────────────
    if verbose:
        print("[PIPELINE] Step 4: Generating Diagrams…")

    from backend.diagram_generator.hld_mermaid_generator import (
        HLDMermaidGenerator,
    )
    from backend.diagram_generator.lld_sequence_generator import (
        LLDSequenceGenerator,
    )

    diagram_dir = os.path.join(output_dir, "diagrams")
    os.makedirs(diagram_dir, exist_ok=True)

    hld_diagrams = HLDMermaidGenerator().generate(hld_blueprint, aim=aim, semantic_ir=semantic_ir)
    
    for name, mmd_code in hld_diagrams.items():
        if mmd_code:
            mmd_path = os.path.join(diagram_dir, f"hld_{name}.mmd")
            with open(mmd_path, "w", encoding="utf-8") as f:
                f.write(mmd_code)
            if verbose:
                print(f"  → {mmd_path}")

    lld_diagrams = LLDSequenceGenerator().generate(lld_model)
    
    for name, mmd_code in lld_diagrams.items():
        if mmd_code:
            mmd_path = os.path.join(diagram_dir, f"lld_{name}.mmd")
            with open(mmd_path, "w", encoding="utf-8") as f:
                f.write(mmd_code)
            if verbose:
                print(f"  → {mmd_path}")

    # ── Generate Markdown with Diagrams ──────────────────────
    if verbose:
        print("[PIPELINE] Generating Markdown Documentation…")
        
    from backend.document_generator.hld_generator import HLDGenerator
    from backend.document_generator.lld_generator import LLDGenerator

    hld_gen = HLDGenerator()
    hld_path = os.path.join(output_dir, "hld", "HLD.md")
    if aim:
        hld_content = hld_gen.generate_from_aim(aim, diagram_paths=hld_diagrams)
    else:
        hld_content = hld_gen.generate(hld_blueprint, diagram_paths=hld_diagrams, repository_name=repo_name)
    hld_gen.save(hld_content, hld_path)

    lld_gen = LLDGenerator()
    lld_path = os.path.join(output_dir, "lld", "LLD.md")
    lld_content = lld_gen.generate(lld_summary, diagram_paths=lld_diagrams, repo_path=repo_path)
    lld_gen.save(lld_content, lld_path)

    # ── Step 5: Render Mermaid to SVG (optional) ─────────────
    try:
        from backend.diagram_generator.mermaid_renderer import MermaidRenderer
        renderer = MermaidRenderer()

        for name, mmd_code in hld_diagrams.items():
            if mmd_code:
                svg_path = os.path.join(diagram_dir, f"hld_{name}.svg")
                renderer.render(mmd_code, svg_path)
                if verbose:
                    print(f"  → {svg_path}")

        for name, mmd_code in lld_diagrams.items():
            if mmd_code:
                svg_path = os.path.join(diagram_dir, f"lld_{name}.svg")
                renderer.render(mmd_code, svg_path)
                if verbose:
                    print(f"  → {svg_path}")

    except Exception as e:
        import traceback
        print(f"\n[ERROR] SVG Rendering failed: {e}")
        traceback.print_exc()
        print("[FALLBACK] Discarding SVG assets. Markdown documents will retain raw Mermaid.js text blocks.")

    # ── Step 5b: Inline Code Commenting ──────────────────
    if verbose:
        print("\n[PIPELINE] Step 5b: Generating Inline Code Comments…")

    commented_dir = os.path.join(output_dir, "commented_code")
    os.makedirs(commented_dir, exist_ok=True)

    SKIP_DIRS = {
        "__pycache__", ".git", "venv", ".venv", "node_modules",
        "dist", "build", ".pytest_cache", "outputs", ".mypy_cache",
        ".tox", "eggs", "*.egg-info",
        "commented_code", "test_repo", "mock_repos", "fixtures",
        "samples", "examples", "tests",
    }
    SOURCE_EXTS = {
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".java", ".go", ".rb", ".php",
        ".cpp", ".c", ".cs", ".swift", ".kt", ".rs"
    }

    source_files = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs
                   if d not in SKIP_DIRS
                   and not d.startswith(".")
                   and not d.endswith("-docs")]
        for fname in files:
            if os.path.splitext(fname)[1] in SOURCE_EXTS:
                source_files.append(os.path.join(root, fname))
                
    SKIP_FILE_PREFIXES = ("patch_", "fix_", "rewrite_", "refactor_", "test_", "get_old_", "final_patch_")
    source_files = [
        f for f in source_files
        if not any(os.path.basename(f).startswith(p) for p in SKIP_FILE_PREFIXES)
        or os.path.dirname(f) != repo_path
    ]

    if verbose:
        print(f"  → {len(source_files)} source files found")

    try:
        from backend.comment_engine.inline_commentor import (
            ASTInlineCommentor,
        )
        kg_obj = getattr(builder, "kg", None)
        llm_client_for_comments = None
        if llm_model:
            try:
                from backend.llm_orchestrator.llm_client import (
                    create_llm_client,
                )
                llm_client_for_comments = create_llm_client(
                    model=llm_model, verbose=False
                )
            except Exception:
                pass

        commentor = ASTInlineCommentor(
            llm_client=llm_client_for_comments,
            kg=kg_obj,
        )

        ok, failed = 0, []
        for src in source_files:
            rel = os.path.relpath(src, repo_path)
            out = os.path.join(commented_dir, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            try:
                commentor.inject_comments(src, out)
                ok += 1
                if verbose:
                    print(f"  ✓ {rel}")
            except Exception as e:
                failed.append(rel)
                if verbose:
                    print(f"  ✗ {rel}: {e}")

        if verbose:
            print(f"  → Done: {ok}/{len(source_files)} commented")
            if failed:
                print(f"  → Failed: {len(failed)} files")

    except Exception as e:
        import traceback
        print(f"\n[ERROR] Semantic Inline Comment Engine failed: {e}")
        traceback.print_exc()
        print("[FALLBACK] Original repository source code will be documented as-is without inline semantic annotations.")

    # ── Step 6: Generate DOCX ────────────────────────────────
    if verbose:
        print("\n[PIPELINE] Step 6: Generating DOCX…")
    
    hld_docx_path = None
    lld_docx_path = None
    
    try:
        from backend.docx_service.hld_docx_generator import HLDDocxGenerator
        from backend.docx_service.lld_docx_generator import LLDDocxGenerator
        
        hld_docx_gen = HLDDocxGenerator(repo_name=os.path.basename(repo_path), verbose=verbose)
        hld_docx_path = os.path.join(output_dir, "hld", "HLD.docx")
        if aim:
            hld_docx_gen.generate_from_aim(aim, hld_docx_path, diagram_paths=hld_diagrams)
        else:
            hld_docx_gen.generate_from_semantic_ir(semantic_ir, hld_docx_path)
        if verbose:
            print(f"  → {hld_docx_path}")
            
        lld_docx_gen = LLDDocxGenerator(repo_name=os.path.basename(repo_path), verbose=verbose)
        lld_docx_path = os.path.join(output_dir, "lld", "LLD.docx")
        lld_docx_gen.generate_from_semantic_ir(semantic_ir, lld_docx_path, kg=getattr(builder, "kg", None), repo_path=repo_path, lld_model=lld_summary)
        if verbose:
            print(f"  → {lld_docx_path}")
            
    except Exception as e:
        import traceback
        print(f"\n[ERROR] DOCX Generation failed: {e}")
        traceback.print_exc()
        print("[FALLBACK] Binary DOCX artifacts discarded. Please refer to the raw Markdown files (HLD.md, LLD.md) generated in the output directory.")
        hld_docx_path = None
        lld_docx_path = None

    # ── Summary ──────────────────────────────────────────────
    elapsed = time.time() - t_start

    if verbose:
        print(f"\n{'='*65}")
        print(f"  Pipeline Complete ({elapsed:.1f}s)")
        print(f"  {'─'*40}")
        print(f"  Components:    {len(semantic_ir.components)}")
        print(f"  Relationships: {len(semantic_ir.relationships)}")
        print(f"  Workflows:     {len(semantic_ir.workflows)}")
        print(f"  API Endpoints: {len(semantic_ir.api_endpoints)}")
        print(f"  Data Stores:   {len(semantic_ir.data_stores)}")
        print(f"  Request Flows: {len(semantic_ir.request_flows)}")
        print(f"  Architecture:  {semantic_ir.architecture_pattern}")
        print(f"  {'─'*40}")
        if hld_docx_path:
            print(f"  HLD DOCX:  {hld_docx_path}")
        else:
            print(f"  [FAILED]   HLD.docx not generated")
            print(f"  [FALLBACK] HLD.md: {hld_path}")
            
        if lld_docx_path:
            print(f"  LLD DOCX:  {lld_docx_path}")
        else:
            print(f"  [FAILED]   LLD.docx not generated")
            print(f"  [FALLBACK] LLD.md: {lld_path}")
            
        print(f"  Diagrams: {diagram_dir}")
        print(f"  Comments: {commented_dir}")
        print(f"{'='*65}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
