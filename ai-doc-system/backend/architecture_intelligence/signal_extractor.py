"""
architecture_intelligence/signal_extractor.py
────────────────────────────────────────────────────────────────
Deterministic signal extraction from SemanticIR + ArchitectureBlueprint.

Produces a RepositorySignals dataclass containing all raw evidence
used by DomainClassifier for domain scoring.

No LLM calls — purely deterministic text scanning.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import List

from backend.semantic_ir.models import SemanticIR
from backend.architecture_extractor.models import ArchitectureBlueprint


@dataclass
class RepositorySignals:
    """Raw evidence collected from the repository before classification."""
    entity_names: List[str] = field(default_factory=list)       # class names, model names
    api_paths: List[str] = field(default_factory=list)          # URL paths found
    table_names: List[str] = field(default_factory=list)        # database table/collection names
    framework_names: List[str] = field(default_factory=list)    # from ir.frameworks
    config_keys: List[str] = field(default_factory=list)        # env var names, config keys
    import_names: List[str] = field(default_factory=list)       # third-party imports
    vocabulary: List[str] = field(default_factory=list)         # words from descriptions
    directory_names: List[str] = field(default_factory=list)    # top-level directory names
    file_names: List[str] = field(default_factory=list)         # significant file names


class SignalExtractor:
    """Extract classification signals from SemanticIR and ArchitectureBlueprint."""

    def extract(
        self,
        ir: SemanticIR,
        blueprint: ArchitectureBlueprint,
    ) -> RepositorySignals:
        signals = RepositorySignals()

        # ── Entity / class names from IR components ──────────
        for comp in ir.components:
            # Component name
            signals.entity_names.append(comp.name.lower())

            # Key classes inside this component
            for cls in comp.key_classes:
                signals.entity_names.append(cls.lower())

            # Description vocabulary
            if comp.description:
                words = self._extract_words(comp.description)
                signals.vocabulary.extend(words)

            # Directory names from file paths
            for fpath in comp.files:
                parts = fpath.replace("\\", "/").split("/")
                if len(parts) > 1:
                    signals.directory_names.append(parts[0].lower())
                # File names
                fname = parts[-1].lower() if parts else ""
                if fname:
                    signals.file_names.append(fname)

            # Dependencies as import signals
            for dep in comp.dependencies:
                dep_lower = dep.lower()
                # Only third-party style imports (not internal paths)
                if not ("/" in dep_lower or "\\" in dep_lower):
                    signals.import_names.append(dep_lower)

        # ── API paths from IR endpoints ──────────────────────
        for endpoint in ir.api_endpoints:
            if endpoint.path:
                signals.api_paths.append(endpoint.path.lower())
                # Also extract path segments as vocabulary
                segments = [s for s in endpoint.path.split("/") if s and not s.startswith("{")]
                signals.vocabulary.extend([s.lower() for s in segments])

        # ── Table names from IR data stores ──────────────────
        for store in ir.data_stores:
            signals.table_names.append(store.name.lower())

        # ── Framework names ──────────────────────────────────
        signals.framework_names.extend([f.lower() for f in ir.frameworks])

        # ── Infrastructure signals ───────────────────────────
        signals.import_names.extend([i.lower() for i in ir.infrastructure])

        # ── AI/ML tools ──────────────────────────────────────
        signals.import_names.extend([t.lower() for t in ir.ai_ml_tools])

        # ── Code analysis tools ──────────────────────────────
        signals.import_names.extend([t.lower() for t in getattr(ir, "code_analysis_tools", [])])

        # ── Database names ───────────────────────────────────
        signals.import_names.extend([d.lower() for d in ir.databases])

        # ── Messaging systems ────────────────────────────────
        signals.import_names.extend([m.lower() for m in ir.messaging_systems])

        # ── Blueprint enrichments ────────────────────────────

        # Service names
        for srv in blueprint.services:
            signals.entity_names.append(srv.name.lower())
            if srv.purpose:
                signals.vocabulary.extend(self._extract_words(srv.purpose))

        # Capability names
        for cap in getattr(blueprint, "capabilities", []):
            signals.entity_names.append(cap.name.lower())
            if cap.description:
                signals.vocabulary.extend(self._extract_words(cap.description))

        # Database tables from blueprint
        for db in blueprint.databases:
            signals.table_names.append(db.name.lower())

        # API paths from blueprint
        for api in blueprint.apis:
            if api.path:
                signals.api_paths.append(api.path.lower())

        # Integration targets
        for integ in blueprint.integrations:
            signals.vocabulary.append(integ.target.lower())
            signals.vocabulary.append(integ.source.lower())

        # Artifact names
        for artifact in blueprint.artifacts:
            signals.entity_names.append(artifact.name.lower())

        # ── Deduplicate ──────────────────────────────────────
        signals.entity_names = list(set(signals.entity_names))
        signals.api_paths = list(set(signals.api_paths))
        signals.table_names = list(set(signals.table_names))
        signals.framework_names = list(set(signals.framework_names))
        signals.import_names = list(set(signals.import_names))
        signals.vocabulary = list(set(signals.vocabulary))
        signals.directory_names = list(set(signals.directory_names))
        signals.file_names = list(set(signals.file_names))

        return signals

    @staticmethod
    def _extract_words(text: str) -> List[str]:
        """Extract meaningful words from a text string."""
        # Split on non-alpha, filter short/common words
        words = re.findall(r"[a-zA-Z]{3,}", text.lower())
        stop_words = {
            "the", "and", "for", "with", "this", "that", "from",
            "are", "was", "were", "has", "have", "been", "not",
            "but", "all", "can", "had", "her", "his", "its",
            "may", "new", "now", "old", "see", "way", "who",
            "did", "get", "let", "say", "she", "too", "use",
            "which", "each", "other", "into", "some", "than",
            "them", "then", "these", "such", "only", "also",
        }
        return [w for w in words if w not in stop_words]
