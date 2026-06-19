"""
context_builder/prompt_builder.py
────────────────────────────────────────────────────────────────
Generates LLM-ready prompts from ContextResult.

Supports 6 prompt types: documentation, HLD, LLD,
code-comment, architecture, business.
"""

from __future__ import annotations

import json
from typing import Dict

from .models import ContextResult, PromptPayload
from .token_estimator import TokenEstimator


class PromptBuilder:
    """Generates LLM-ready prompts from assembled context."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.estimator = TokenEstimator()

    def build_prompt(
        self,
        context: ContextResult,
        prompt_type: str = "documentation",
    ) -> PromptPayload:
        """Build a prompt for the specified type."""
        builders = {
            "documentation": self._documentation_prompt,
            "hld":           self._hld_prompt,
            "lld":           self._lld_prompt,
            "code-comment":  self._code_comment_prompt,
            "architecture":  self._architecture_prompt,
            "business":      self._business_prompt,
        }

        builder = builders.get(prompt_type, self._documentation_prompt)
        return builder(context)

    def _documentation_prompt(self, ctx: ContextResult) -> PromptPayload:
        target_name = ctx.target_node.name if ctx.target_node else "Unknown"
        context_json = ctx.to_dict()

        system_prompt = (
            "You are an expert software documentation engineer analyzing an enterprise codebase. "
            "You have deep understanding of software architecture, telecom systems, and business workflows. "
            "Generate comprehensive, accurate documentation based ONLY on the provided context. "
            "Do NOT invent or hallucinate information not present in the context. "
            "Include: purpose, architecture role, dependencies, data flow, and business context."
        )

        user_prompt = (
            f"Generate comprehensive documentation for: **{target_name}**\n\n"
            f"## Provided Context\n"
            f"```json\n{json.dumps(context_json, indent=2, ensure_ascii=False, default=str)}\n```\n\n"
            f"## Required Sections\n"
            f"1. **Overview**: What this component does and its purpose\n"
            f"2. **Architecture Role**: Where it sits in the system architecture\n"
            f"3. **Dependencies**: What it depends on and what depends on it\n"
            f"4. **Data Flow**: How data moves through this component\n"
            f"5. **Business Context**: Business meaning and domain relevance\n"
            f"6. **API Surface**: Exposed APIs and consumed APIs\n"
            f"7. **Key Functions**: Important functions and their roles\n"
        )

        tokens = self.estimator.estimate_tokens(system_prompt + user_prompt)
        return PromptPayload(
            prompt_type="documentation",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            context_json=context_json,
            estimated_tokens=tokens,
        )

    def _hld_prompt(self, ctx: ContextResult) -> PromptPayload:
        target_name = ctx.target_node.name if ctx.target_node else "Unknown"
        context_json = ctx.to_dict()

        system_prompt = (
            "You are an enterprise architect generating a High-Level Design (HLD) document. "
            "Focus on service boundaries, inter-service communication, data flows, "
            "and architectural patterns. Use the provided knowledge graph context as "
            "the SOLE source of truth. Do NOT invent architecture not present in the context."
        )

        user_prompt = (
            f"Generate a High-Level Design (HLD) document for: **{target_name}**\n\n"
            f"## Provided Context\n"
            f"```json\n{json.dumps(context_json, indent=2, ensure_ascii=False, default=str)}\n```\n\n"
            f"## Required Sections\n"
            f"1. **System Overview**: High-level purpose and scope\n"
            f"2. **Architecture Diagram** (describe in text/mermaid): Services and their relationships\n"
            f"3. **Service Boundaries**: Microservices involved and their responsibilities\n"
            f"4. **Data Flow**: How data moves between services\n"
            f"5. **API Contracts**: Inter-service API surface\n"
            f"6. **Event Architecture**: Event buses, pub/sub, async flows\n"
            f"7. **Data Stores**: Databases, collections, and tables\n"
            f"8. **Non-Functional**: Scalability, security, performance considerations\n"
        )

        tokens = self.estimator.estimate_tokens(system_prompt + user_prompt)
        return PromptPayload(
            prompt_type="hld",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            context_json=context_json,
            estimated_tokens=tokens,
        )

    def _lld_prompt(self, ctx: ContextResult) -> PromptPayload:
        target_name = ctx.target_node.name if ctx.target_node else "Unknown"
        context_json = ctx.to_dict()

        system_prompt = (
            "You are a senior developer generating a Low-Level Design (LLD) document. "
            "Focus on class structure, function signatures, control flow, error handling, "
            "and implementation details. Use the provided context as the SOLE source of truth."
        )

        user_prompt = (
            f"Generate a Low-Level Design (LLD) document for: **{target_name}**\n\n"
            f"## Provided Context\n"
            f"```json\n{json.dumps(context_json, indent=2, ensure_ascii=False, default=str)}\n```\n\n"
            f"## Required Sections\n"
            f"1. **Module Overview**: Purpose and responsibilities\n"
            f"2. **Class/Function Structure**: Key classes and functions with signatures\n"
            f"3. **Execution Flow**: Step-by-step execution sequence\n"
            f"4. **Control Flow**: Conditional logic, branching, exception handling\n"
            f"5. **Data Structures**: Key data structures and their usage\n"
            f"6. **Database Interaction**: Queries, collections, CRUD operations\n"
            f"7. **Error Handling**: Exception flows and recovery strategies\n"
            f"8. **Dependencies**: Internal and external dependencies\n"
        )

        tokens = self.estimator.estimate_tokens(system_prompt + user_prompt)
        return PromptPayload(
            prompt_type="lld",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            context_json=context_json,
            estimated_tokens=tokens,
        )

    def _code_comment_prompt(self, ctx: ContextResult) -> PromptPayload:
        target_name = ctx.target_node.name if ctx.target_node else "Unknown"
        context_json = ctx.to_dict()

        system_prompt = (
            "You are a senior developer adding inline code comments. "
            "Add clear, concise comments explaining: purpose, parameters, return values, "
            "side effects, and business context. Do NOT modify the code logic. "
            "Comments should help a new developer understand the codebase quickly."
        )

        source = ctx.source_code or "(source code not available)"
        user_prompt = (
            f"Add comprehensive inline comments to: **{target_name}**\n\n"
            f"## Source Code\n```\n{source}\n```\n\n"
            f"## Context (for understanding business meaning)\n"
            f"```json\n{json.dumps(context_json, indent=2, ensure_ascii=False, default=str)}\n```\n\n"
            f"Return the fully commented source code."
        )

        tokens = self.estimator.estimate_tokens(system_prompt + user_prompt)
        return PromptPayload(
            prompt_type="code-comment",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            context_json=context_json,
            estimated_tokens=tokens,
        )

    def _architecture_prompt(self, ctx: ContextResult) -> PromptPayload:
        target_name = ctx.target_node.name if ctx.target_node else "Unknown"
        context_json = ctx.to_dict()

        system_prompt = (
            "You are an enterprise architect generating architecture documentation. "
            "Focus on system topology, service interactions, and deployment architecture. "
            "Use the provided knowledge graph context as the SOLE source of truth."
        )

        user_prompt = (
            f"Generate architecture documentation for: **{target_name}**\n\n"
            f"## Provided Context\n"
            f"```json\n{json.dumps(context_json, indent=2, ensure_ascii=False, default=str)}\n```\n\n"
            f"## Required Sections\n"
            f"1. **Architecture Overview**: System topology and patterns\n"
            f"2. **Service Map**: Services and their interactions\n"
            f"3. **Data Architecture**: Data stores, flows, and lineage\n"
            f"4. **Integration Points**: APIs, events, and external systems\n"
            f"5. **Domain Model**: Business domains and bounded contexts\n"
        )

        tokens = self.estimator.estimate_tokens(system_prompt + user_prompt)
        return PromptPayload(
            prompt_type="architecture",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            context_json=context_json,
            estimated_tokens=tokens,
        )

    def _business_prompt(self, ctx: ContextResult) -> PromptPayload:
        target_name = ctx.target_node.name if ctx.target_node else "Unknown"
        context_json = ctx.to_dict()

        system_prompt = (
            "You are a business analyst generating business documentation for a telecom enterprise system. "
            "Focus on business workflows, capabilities, domain meaning, and telecom-specific context. "
            "Use the provided knowledge graph context as the SOLE source of truth."
        )

        user_prompt = (
            f"Generate business documentation for: **{target_name}**\n\n"
            f"## Provided Context\n"
            f"```json\n{json.dumps(context_json, indent=2, ensure_ascii=False, default=str)}\n```\n\n"
            f"## Required Sections\n"
            f"1. **Business Purpose**: What business capability this component supports\n"
            f"2. **Telecom Domain**: Relevant telecom domain and TMF alignment\n"
            f"3. **Business Workflows**: End-to-end business processes\n"
            f"4. **Stakeholders**: Who uses or is affected by this component\n"
            f"5. **Business Rules**: Key business rules implemented\n"
            f"6. **Impact Analysis**: What happens if this component fails\n"
        )

        tokens = self.estimator.estimate_tokens(system_prompt + user_prompt)
        return PromptPayload(
            prompt_type="business",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            context_json=context_json,
            estimated_tokens=tokens,
        )
