"""
architecture_intelligence/information_modeler.py
────────────────────────────────────────────────────────────────
Derive information assets and data lifecycles from the blueprint.

Transforms databases, artifacts, and data flows into an
InformationModel with business-meaningful descriptions,
lifecycle stages, and sensitivity classifications.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from backend.architecture_intelligence.models import (
    CapabilityModel,
    DataFlow,
    DomainModel,
    InformationAsset,
    InformationModel,
)
from backend.architecture_extractor.models import ArchitectureBlueprint
from backend.architecture_intelligence.domain_taxonomy import DOMAIN_TAXONOMY


# Sensitivity indicators
CONFIDENTIAL_TERMS = {
    "patient", "health", "medical", "ssn", "passport", "financial",
    "transaction", "payment", "account", "credit", "social_security",
    "password", "secret", "token", "credential", "hipaa",
}

RESTRICTED_TERMS = {
    "encryption_key", "private_key", "master_key", "root_password",
}

IMPLEMENTATION_TERMS = {
    "component", "database", "boundary", "spec", "node", "context",
    "factory", "manager", "registry", "util", "helper", "wrapper",
    "entity", "model", "schema", "file", "project", "parsed", "ast",
    "root",
}


class InformationModeler:
    """Derive information assets and data lifecycles."""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def model(
        self,
        blueprint: ArchitectureBlueprint,
        domain: DomainModel,
        capabilities: CapabilityModel,
    ) -> InformationModel:
        """Build InformationModel from blueprint data."""
        assets = self._identify_assets(blueprint, domain)
        flows = self._derive_flows(blueprint, domain, capabilities, assets)
        summary = self._generate_summary(assets, flows, domain)

        return InformationModel(
            information_assets=assets[:6],
            primary_data_flows=flows[:3],
            data_model_summary=summary,
        )

    def _identify_assets(
        self,
        blueprint: ArchitectureBlueprint,
        domain: DomainModel,
    ) -> List[InformationAsset]:
        """Build InformationAsset objects from blueprint data."""
        assets: List[Tuple[InformationAsset, int]] = []
        seen_names: set = set()

        # Phase 1: Inject explicit domain core assets with highest priority
        if getattr(domain, "core_information_assets", None):
            for core_asset in domain.core_information_assets:
                if core_asset.lower() not in seen_names:
                    seen_names.add(core_asset.lower())
                    assets.append((InformationAsset(
                        name=core_asset,
                        asset_type=self._classify_asset_type_by_name(core_asset),
                        description=f"Core {domain.primary_domain} domain entity.",
                        lifecycle_stages=self._lifecycle_from_name(core_asset),
                        produced_by="Domain",
                        consumed_by=[],
                        persistence="Persistent",
                        sensitivity=self._classify_sensitivity(core_asset),
                    ), 100))

        def _score_asset(name: str) -> int:
            name_lower = name.lower()
            if getattr(domain, "core_information_assets", None) and any(name_lower in a.lower() or a.lower() in name_lower for a in domain.core_information_assets):
                return 90
            if any(name_lower in c.lower() or c.lower() in name_lower for c in domain.bounded_contexts):
                return 80
            if getattr(domain, "industry_vocabulary", None) and any(name_lower in v.lower() for v in domain.industry_vocabulary):
                return 60
            
            # Reject generic placeholder fixtures if they completely misalign with the domain
            generic_fixtures = {"customer", "customers", "order", "orders", "user", "users"}
            if name_lower in generic_fixtures:
                if domain.primary_domain not in ("E-Commerce", "Financial Services", "Insurance", "Enterprise Application"):
                    return -100
                return 10
            return 20

        # Phase 2: Evaluate blueprint databases
        for db in blueprint.databases:
            if any(term in db.name.lower() for term in IMPLEMENTATION_TERMS):
                continue
                
            name = self._business_name(db.name)
            score = _score_asset(name)
            if score < 0 or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())

            assets.append((InformationAsset(
                name=name,
                asset_type=self._asset_type_from_ops(db.operations),
                description=f"{name} data managed by the {domain.primary_domain} system.",
                lifecycle_stages=self._lifecycle_from_operations(db.operations),
                produced_by=db.accessed_by[0] if db.accessed_by else "Unknown",
                consumed_by=db.accessed_by[1:] if len(db.accessed_by) > 1 else [],
                persistence="Persistent",
                sensitivity=self._classify_sensitivity(db.name),
                confidence=min(1.0, max(0.5, score / 100.0)),
                evidence=["database_schema_extractor"]
            ), score))

        # Phase 3: Evaluate blueprint artifacts
        for artifact in blueprint.artifacts:
            if any(term in artifact.name.lower() for term in IMPLEMENTATION_TERMS):
                continue
                
            art_type = getattr(artifact, "artifact_type", "")
            name = self._business_name(artifact.name)
            score = _score_asset(name)
            if score < 0 or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())

            if art_type == "Domain Entity":
                assets.append((InformationAsset(
                    name=name,
                    asset_type="Master Data",
                    description=artifact.description or f"{name} domain entity.",
                    lifecycle_stages=["Created", "Updated", "Retrieved"],
                    produced_by=artifact.producer,
                    consumed_by=artifact.consumers[:3],
                    persistence="Persistent",
                    sensitivity=self._classify_sensitivity(artifact.name),
                    confidence=min(1.0, max(0.6, score / 100.0)),
                    evidence=["object_model_extractor"]
                ), score))
            elif art_type == "Request Payload":
                assets.append((InformationAsset(
                    name=name,
                    asset_type="Transactional",
                    description=artifact.description or f"{name} request data.",
                    lifecycle_stages=["Received", "Validated", "Processed"],
                    produced_by=artifact.producer,
                    consumed_by=artifact.consumers[:3],
                    persistence="Transient",
                    sensitivity="Internal",
                    confidence=min(1.0, max(0.6, score / 100.0)),
                    evidence=["api_endpoint_extractor"]
                ), score))

        # Sort by score descending
        assets.sort(key=lambda x: x[1], reverse=True)
        final_assets = [a[0] for a in assets]

        # Generate LLM descriptions if available
        if self.llm:
            for asset in final_assets:
                if asset.description.endswith("system.") or asset.description.endswith("entity."):
                    try:
                        asset.description = self._llm_asset_description(asset, domain)
                    except Exception:
                        pass

        return final_assets

    def _derive_flows(
        self,
        blueprint: ArchitectureBlueprint,
        domain: DomainModel,
        capabilities: CapabilityModel,
        final_assets: List[InformationAsset],
    ) -> List[DataFlow]:
        """Build DataFlow objects from blueprint data flows."""
        flows: List[DataFlow] = []

        # Map capability names for stage naming
        cap_names = (
            [c.name for c in capabilities.core_capabilities]
            + [c.name for c in capabilities.supporting_capabilities]
        )

        for df in blueprint.data_flows:
            # Skip flows with file paths or implementation terms
            if self._is_file_path(df.source) or self._is_file_path(df.sink):
                continue
            if any(term in df.source.lower() or term in df.sink.lower() for term in IMPLEMENTATION_TERMS):
                continue

            source_stage = self._to_stage_name(df.source, cap_names)
            sink_stage = self._to_stage_name(df.sink, cap_names)

            if source_stage and sink_stage:
                name = df.name or f"{source_stage} to {sink_stage} Flow"
                # Clean up name
                name = self._business_name(name)

                stages = [source_stage]
                if df.steps:
                    for step in df.steps[:3]:
                        step_name = self._to_stage_name(step, cap_names)
                        if step_name and step_name not in stages:
                            stages.append(step_name)
                if sink_stage not in stages:
                    stages.append(sink_stage)

                flows.append(DataFlow(
                    name=name,
                    description=df.description or f"Data transformation from {source_stage} to {sink_stage}.",
                    stages=stages,
                    trigger=f"{source_stage} produces output",
                    outcome=f"{sink_stage} receives processed data",
                ))

        if not flows and final_assets:
            # 1. First try domain taxonomy primary_flows (strongest)
            taxonomy = DOMAIN_TAXONOMY.get(domain.primary_domain, {})
            primary_flows = taxonomy.get("primary_flows", [])

            if primary_flows:
                for f_def in primary_flows[:2]:
                    flows.append(DataFlow(
                        name=f_def["name"],
                        description=f"Core {domain.primary_domain} data flow.",
                        stages=f_def["stages"],
                        trigger=f_def.get("trigger", "Business event"),
                        outcome=f_def.get("outcome", "Business outcome achieved"),
                    ))
            else:
                # 2. Fallback: infer from asset producer/consumer evidence
                ordered_assets = []
                unplaced = list(final_assets)
                if unplaced:
                    current = unplaced.pop(0)
                    ordered_assets.append(current.name)

                    while unplaced:
                        next_asset = None
                        for candidate in unplaced:
                            if current.consumed_by and candidate.produced_by in current.consumed_by:
                                next_asset = candidate
                                break

                        if next_asset:
                            ordered_assets.append(next_asset.name)
                            unplaced.remove(next_asset)
                            current = next_asset
                        else:
                            next_asset = unplaced.pop(0)
                            ordered_assets.append(next_asset.name)
                            current = next_asset

                if ordered_assets:
                    flows.append(DataFlow(
                        name=f"{domain.primary_domain} Processing Flow",
                        description=f"Core information flow through the {domain.primary_domain} system.",
                        stages=ordered_assets[:5],
                        trigger=f"{ordered_assets[0]} ingested",
                        outcome=f"{ordered_assets[-1]} generated",
                    ))

        return flows

    def _generate_summary(
        self,
        assets: List[InformationAsset],
        flows: List[DataFlow],
        domain: DomainModel,
    ) -> str:
        """Generate data model summary."""
        if self.llm:
            try:
                return self._llm_summary(assets, flows, domain)
            except Exception:
                pass

        # Template fallback
        asset_names = ", ".join(a.name for a in assets[:4])
        persistent = sum(1 for a in assets if a.persistence == "Persistent")
        transient = sum(1 for a in assets if a.persistence == "Transient")

        return (
            f"The {domain.primary_domain} system manages {len(assets)} key information assets "
            f"including {asset_names}. "
            f"Of these, {persistent} are persistently stored and {transient} are transient. "
            f"Data flows through {len(flows)} primary transformation pipelines."
        )

    # ── LLM helpers ──────────────────────────────────────────

    def _llm_asset_description(self, asset: InformationAsset, domain: DomainModel) -> str:
        """LLM-generated asset description."""
        system_prompt = (
            "You are a Data Architect. Write one sentence describing an information asset "
            "from a business perspective. No technical jargon. Plain text only."
        )
        user_prompt = (
            f"Given this is a {domain.primary_domain} system, describe this information asset:\n"
            f"Asset name: {asset.name}\n"
            f"Asset type: {asset.asset_type}\n"
            f"Produced by: {asset.produced_by}\n"
        )
        text = self.llm.generate(system_prompt, user_prompt, max_tokens=128, temperature=0.2)
        text = text.strip()
        if len(text) > 200:
            text = text[:197] + "..."
        return text if text else asset.description

    def _llm_summary(
        self, assets: List[InformationAsset], flows: List[DataFlow], domain: DomainModel
    ) -> str:
        """LLM-generated data model summary."""
        system_prompt = (
            "You are a Data Architect writing a data model summary for an HLD. "
            "One paragraph, 3-4 sentences. Plain text. No headings or bullets."
        )
        asset_list = [{"name": a.name, "type": a.asset_type, "persistence": a.persistence} for a in assets[:6]]
        flow_list = [{"name": f.name, "stages": f.stages} for f in flows[:3]]
        user_prompt = (
            f"Describe the information architecture for this {domain.primary_domain} system.\n\n"
            f"INFORMATION ASSETS:\n{json.dumps(asset_list, indent=2)}\n\n"
            f"DATA FLOWS:\n{json.dumps(flow_list, indent=2)}\n"
        )
        text = self.llm.generate(system_prompt, user_prompt, max_tokens=512, temperature=0.2)
        text = text.strip()
        if 50 < len(text) < 1000:
            return text
        return self._generate_summary.__wrapped__(self, assets, flows, domain)  # noqa — won't reach here

    # ── Deterministic helpers ────────────────────────────────

    @staticmethod
    def _business_name(raw: str) -> str:
        """Clean a raw name into a business-friendly name."""
        # Insert space before capital letters (CamelCase split)
        name = re.sub(r'([a-z])([A-Z])', r'\1 \2', raw)
        
        name = name.replace("_", " ").replace("-", " ").strip()
        # Title case
        name = " ".join(w.capitalize() for w in name.split())
        # Remove common suffixes
        for suffix in ["Table", "Collection", "Schema", "Model", "Entity"]:
            if name.endswith(f" {suffix}"):
                name = name[: -len(suffix) - 1].strip()
        return name

    @staticmethod
    def _is_file_path(text: str) -> bool:
        """Return True if text looks like a file path."""
        return (
            "/" in text and "." in text.split("/")[-1]
        ) or text.endswith((".py", ".js", ".ts", ".java", ".go"))

    @staticmethod
    def _classify_sensitivity(name: str) -> str:
        """Classify data sensitivity from name."""
        name_lower = name.lower()
        if any(t in name_lower for t in RESTRICTED_TERMS):
            return "Restricted"
        if any(t in name_lower for t in CONFIDENTIAL_TERMS):
            return "Confidential"
        return "Internal"

    @staticmethod
    def _lifecycle_from_operations(operations: List[str]) -> List[str]:
        """Derive lifecycle stages from SQL operations."""
        ops = set(op.upper() for op in operations)
        if ops == {"SELECT"}:
            return ["Created elsewhere", "Queried"]
        if ops >= {"INSERT", "UPDATE", "DELETE"}:
            return ["Created", "Updated", "Archived"]
        if ops >= {"INSERT", "SELECT"}:
            return ["Created", "Stored", "Retrieved"]
        if ops >= {"INSERT", "UPDATE"}:
            return ["Created", "Updated", "Retrieved"]
        if "INSERT" in ops:
            return ["Created", "Stored"]
        return ["Managed"]

    @staticmethod
    def _asset_type_from_ops(operations: List[str]) -> str:
        """Determine asset type from operations."""
        ops = set(op.upper() for op in operations)
        if "INSERT" in ops and "UPDATE" in ops:
            return "Transactional"
        if "SELECT" in ops and "INSERT" not in ops:
            return "Reference"
        return "Master Data"

    @staticmethod
    def _to_stage_name(raw: str, cap_names: List[str]) -> Optional[str]:
        """Map a raw source/sink to a business stage name."""
        raw_lower = raw.lower()
        # Try matching against capability names
        for cap in cap_names:
            if cap.lower() in raw_lower or raw_lower in cap.lower():
                return cap

        # Clean up the raw name
        name = raw.replace("_", " ").replace("-", " ").strip()
        if "/" in name or "." in name.split("/")[-1] if "/" in name else False:
            return None  # File path

        name = " ".join(w.capitalize() for w in name.split())
        return name if len(name) > 2 else None

    # ── Name-based asset classification (Q5 fix) ─────────────

    _TRANSACTIONAL_KEYWORDS = {
        "transaction", "order", "payment", "invoice", "booking", "reservation",
        "session", "cart", "basket", "request", "response", "event", "log",
        "notification", "message", "transfer", "claim",
    }
    _MASTER_DATA_KEYWORDS = {
        "catalog", "product", "customer", "account", "user", "profile",
        "inventory", "supplier", "vendor", "category", "reference", "policy",
        "config", "template", "rule", "rate", "source code", "record",
        "subscriber", "patient", "lead", "contact",
    }
    _DERIVED_KEYWORDS = {
        "report", "analytics", "summary", "aggregate", "dashboard",
        "insight", "metric", "statistic", "forecast",
        "model", "graph", "artifact", "context", "result",
    }

    @classmethod
    def _classify_asset_type_by_name(cls, name: str) -> str:
        """Classify asset type from name using keyword matching."""
        name_lower = name.lower()
        for kw in cls._TRANSACTIONAL_KEYWORDS:
            if kw in name_lower:
                return "Transactional"
        for kw in cls._DERIVED_KEYWORDS:
            if kw in name_lower:
                return "Derived"
        for kw in cls._MASTER_DATA_KEYWORDS:
            if kw in name_lower:
                return "Master Data"
        return "Reference"

    @staticmethod
    def _lifecycle_from_name(name: str) -> list:
        """Derive lifecycle stages from asset name using domain knowledge."""
        name_lower = name.lower()
        if any(kw in name_lower for kw in ["order", "booking", "claim"]):
            return ["Created", "Submitted", "Processed", "Completed", "Archived"]
        if any(kw in name_lower for kw in ["payment", "transaction", "transfer"]):
            return ["Initiated", "Authorized", "Settled", "Archived"]
        if any(kw in name_lower for kw in ["cart", "basket", "session"]):
            return ["Created", "Modified", "Checked Out", "Abandoned/Expired"]
        if any(kw in name_lower for kw in ["catalog", "product", "inventory"]):
            return ["Created", "Published", "Updated", "Discontinued"]
        if any(kw in name_lower for kw in ["report", "analytics", "dashboard"]):
            return ["Generated", "Published", "Consumed", "Archived"]
        return ["Created", "Updated", "Archived"]
