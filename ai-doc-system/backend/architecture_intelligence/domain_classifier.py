"""
architecture_intelligence/domain_classifier.py
────────────────────────────────────────────────────────────────
Infer the business domain of a repository from extracted signals.

Strategy:
    1. Deterministic weighted scoring against domain taxonomy
    2. If confidence < 0.70 and LLM available, use LLM confirmation
    3. Hallucination prevention: validate all LLM outputs against
       actual repository evidence

The classifier never invents a domain — it only selects from
the predefined taxonomy in domain_taxonomy.py.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

from backend.architecture_intelligence.models import DomainModel
from backend.architecture_intelligence.signal_extractor import (
    RepositorySignals,
    SignalExtractor,
)
from backend.architecture_intelligence.domain_taxonomy import (
    DOMAIN_TAXONOMY,
    SIGNAL_WEIGHTS,
)
from backend.semantic_ir.models import SemanticIR
from backend.architecture_extractor.models import ArchitectureBlueprint


class DomainClassifier:
    """Classify a repository's business domain from code signals."""

    def __init__(self, llm_client=None):
        self.llm = llm_client
        self._signal_extractor = SignalExtractor()

    def classify(
        self,
        ir: SemanticIR,
        blueprint: ArchitectureBlueprint,
    ) -> DomainModel:
        """
        Classify the repository's business domain.

        Returns a DomainModel with the primary domain, bounded contexts,
        business functions, and confidence score.
        """
        signals = self._signal_extractor.extract(ir, blueprint)
        scores = self._score_domains(signals)

        if not scores:
            return self._fallback_domain(signals)

        top_domain, top_score = max(scores.items(), key=lambda x: x[1])

        if self.llm and top_score < 0.70:
            try:
                return self._llm_classify(signals, scores, top_domain, top_score)
            except Exception:
                pass

        return self._deterministic_classify(signals, scores, top_domain, top_score)

    def _score_domains(self, signals: RepositorySignals) -> Dict[str, float]:
        """Score each domain against extracted signals using weighted matching."""
        raw_scores: Dict[str, float] = {}

        for domain_name, domain_def in DOMAIN_TAXONOMY.items():
            domain_signals = set(s.lower() for s in domain_def["signals"])
            score = 0.0

            # Entity/class name matches
            for entity in signals.entity_names:
                for sig in domain_signals:
                    if sig in entity:
                        score += SIGNAL_WEIGHTS["entity_names"]
                        break

            # Table name matches
            for table in signals.table_names:
                for sig in domain_signals:
                    if sig in table:
                        score += SIGNAL_WEIGHTS["table_names"]
                        break

            # API path segment matches
            for path in signals.api_paths:
                for sig in domain_signals:
                    if sig in path:
                        score += SIGNAL_WEIGHTS["api_paths"]
                        break

            # Framework/import matches
            for fw in signals.framework_names:
                for sig in domain_signals:
                    if sig in fw:
                        score += SIGNAL_WEIGHTS["framework_names"]
                        break

            # Import name matches
            for imp in signals.import_names:
                for sig in domain_signals:
                    if sig in imp:
                        score += SIGNAL_WEIGHTS["import_names"]
                        break

            # Vocabulary matches
            for word in signals.vocabulary:
                for sig in domain_signals:
                    if sig in word:
                        score += SIGNAL_WEIGHTS["vocabulary"]
                        break

            # Directory name matches
            for dir_name in signals.directory_names:
                for sig in domain_signals:
                    if sig in dir_name:
                        score += SIGNAL_WEIGHTS["directory_names"]
                        break

            # File name matches
            for fname in signals.file_names:
                for sig in domain_signals:
                    if sig in fname:
                        score += SIGNAL_WEIGHTS["file_names"]
                        break

            raw_scores[domain_name] = score

        # Normalize to [0, 1]
        max_score = max(raw_scores.values()) if raw_scores else 1.0
        if max_score == 0:
            return {k: 0.0 for k in raw_scores}

        return {k: v / max_score for k, v in raw_scores.items()}

    def _deterministic_classify(
        self,
        signals: RepositorySignals,
        scores: Dict[str, float],
        top_domain: str,
        top_score: float,
    ) -> DomainModel:
        """Build DomainModel from deterministic scoring."""
        taxonomy = DOMAIN_TAXONOMY[top_domain]

        # Collect evidence: which signals actually matched
        domain_signals = set(s.lower() for s in taxonomy["signals"])
        evidence = []
        all_signal_words = (
            signals.entity_names + signals.table_names +
            signals.api_paths + signals.framework_names +
            signals.import_names + signals.vocabulary
        )
        for word in all_signal_words:
            for sig in domain_signals:
                if sig in word and sig not in evidence:
                    evidence.append(sig)
                    if len(evidence) >= 10:
                        break
            if len(evidence) >= 10:
                break

        # Extract industry vocabulary found in the codebase
        industry_vocab = []
        for sig in taxonomy["signals"]:
            for word in all_signal_words:
                if sig in word:
                    industry_vocab.append(sig)
                    break
            if len(industry_vocab) >= 8:
                break

        return DomainModel(
            primary_domain=top_domain,
            sub_domain=None,
            bounded_contexts=taxonomy["bounded_contexts"],
            business_functions=taxonomy["business_functions"],
            domain_confidence=top_score,
            domain_evidence=evidence[:10],
            industry_vocabulary=industry_vocab[:8],
            core_information_assets=taxonomy.get("core_information_assets", []),
        )

    def _llm_classify(
        self,
        signals: RepositorySignals,
        scores: Dict[str, float],
        top_domain: str,
        top_score: float,
    ) -> DomainModel:
        """Use LLM to confirm or refine domain classification."""
        system_prompt = (
            "You are a Business Architect analyzing a software repository.\n"
            "Respond ONLY with valid JSON. No preamble. No explanation. No markdown."
        )

        user_prompt = (
            "Classify this repository's business domain.\n\n"
            "SIGNALS EXTRACTED FROM REPOSITORY:\n"
            f"- Entity/Class names: {signals.entity_names[:20]}\n"
            f"- API paths found: {signals.api_paths[:15]}\n"
            f"- Database tables: {signals.table_names[:15]}\n"
            f"- Frameworks detected: {signals.framework_names}\n"
            f"- Third-party imports: {signals.import_names[:20]}\n"
            f"- Directory structure: {signals.directory_names}\n"
            f"- Deterministic score leader: {top_domain} ({top_score:.2f})\n\n"
            f"DOMAIN TAXONOMY:\n{json.dumps(list(DOMAIN_TAXONOMY.keys()))}\n\n"
            "Respond with:\n"
            "{\n"
            '  "primary_domain": "<domain name from taxonomy>",\n'
            '  "sub_domain": "<specific sub-domain or null>",\n'
            '  "confidence": 0.0-1.0,\n'
            '  "bounded_contexts": ["<3-5 bounded contexts>"],\n'
            '  "business_functions": ["<3-5 business functions>"],\n'
            '  "supporting_evidence": ["<cite 3-5 specific signals>"],\n'
            '  "industry_vocabulary": ["<5-8 domain terms found>"]\n'
            "}"
        )

        raw = self.llm.generate(system_prompt, user_prompt, max_tokens=1024, temperature=0.15)

        # Parse and validate LLM response
        try:
            # Strip markdown fences if present
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                cleaned = cleaned.rsplit("```", 1)[0]
            data = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            # Invalid JSON — fall back to deterministic
            return self._deterministic_classify(signals, scores, top_domain, top_score)

        # Validate primary_domain is in taxonomy
        llm_domain = data.get("primary_domain", "")
        if llm_domain not in DOMAIN_TAXONOMY:
            return self._deterministic_classify(signals, scores, top_domain, top_score)

        # Validate confidence
        llm_confidence = float(data.get("confidence", 0.0))
        if llm_confidence < 0.55:
            return self._deterministic_classify(signals, scores, top_domain, top_score)

        # Validate supporting evidence — each item must contain an actual signal
        all_signal_words = set(
            signals.entity_names + signals.table_names +
            signals.api_paths + signals.framework_names +
            signals.import_names + signals.vocabulary
        )
        evidence = data.get("supporting_evidence", [])
        validated_evidence = []
        for ev in evidence:
            ev_lower = ev.lower()
            if any(word in ev_lower for word in all_signal_words):
                validated_evidence.append(ev)

        taxonomy = DOMAIN_TAXONOMY[llm_domain]

        return DomainModel(
            primary_domain=llm_domain,
            sub_domain=data.get("sub_domain"),
            bounded_contexts=data.get("bounded_contexts", taxonomy["bounded_contexts"])[:5],
            business_functions=data.get("business_functions", taxonomy["business_functions"])[:5],
            domain_confidence=llm_confidence,
            domain_evidence=validated_evidence[:10],
            industry_vocabulary=data.get("industry_vocabulary", [])[:8],
            core_information_assets=taxonomy.get("core_information_assets", []),
        )

    def _fallback_domain(self, signals: RepositorySignals) -> DomainModel:
        """Fallback when no domain scores at all."""
        return DomainModel(
            primary_domain="Enterprise Application",
            sub_domain=None,
            bounded_contexts=DOMAIN_TAXONOMY["Enterprise Application"]["bounded_contexts"],
            business_functions=DOMAIN_TAXONOMY["Enterprise Application"]["business_functions"],
            domain_confidence=0.3,
            domain_evidence=[],
            industry_vocabulary=[],
            core_information_assets=DOMAIN_TAXONOMY["Enterprise Application"].get("core_information_assets", []),
        )
