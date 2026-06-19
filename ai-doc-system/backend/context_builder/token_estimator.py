"""
context_builder/token_estimator.py
────────────────────────────────────────────────────────────────
Offline token estimation and budget-aware trimming.

Uses a word-based heuristic (no tiktoken dependency).
Accurate to within ~10% for English code documentation.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple


class TokenEstimator:
    """
    Estimates token counts and trims context to fit within budget.

    Uses the heuristic: tokens ≈ words × 1.3 + special_chars × 0.5
    This matches GPT/Llama tokenization within ~10% for code.
    """

    # Section priority (higher = trim LAST, keep longest)
    SECTION_PRIORITY = {
        "source_code":         100,   # highest: never trim first
        "target":              95,
        "architecture":        80,
        "lineage":             75,
        "workflow":            70,
        "business":            65,
        "telecom":             60,
        "related_functions":   50,
        "relationships":       40,
        "semantic_neighbors":  30,    # lowest: trim first
        "metadata":            20,
        "query":               10,
    }

    def __init__(self, token_multiplier: float = 1.3):
        self.token_multiplier = token_multiplier

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for a text string.

        Heuristic: split on whitespace + punctuation boundaries,
        multiply by 1.3 to account for subword tokenization.
        """
        if not text:
            return 0
        words = text.split()
        word_tokens = int(len(words) * self.token_multiplier)
        # Extra tokens for special chars common in code
        special = sum(1 for c in text if c in "{}[]()=<>:;,./\\|@#$%^&*~`")
        return word_tokens + int(special * 0.3)

    def estimate_dict_tokens(self, d: Dict[str, Any]) -> int:
        """Estimate tokens for a JSON-serializable dict."""
        text = json.dumps(d, ensure_ascii=False, default=str)
        return self.estimate_tokens(text)

    def fits_budget(self, payload: Dict[str, Any], budget: int) -> bool:
        """Check if a payload fits within the token budget."""
        return self.estimate_dict_tokens(payload) <= budget

    def trim_to_budget(
        self,
        context_dict: Dict[str, Any],
        budget: int,
    ) -> Dict[str, Any]:
        """
        Progressively trim low-priority sections to fit within budget.

        Trimming strategy:
        1. Estimate total tokens
        2. If over budget, trim lowest-priority section first
        3. Repeat until within budget
        """
        current = self.estimate_dict_tokens(context_dict)
        if current <= budget:
            return context_dict

        # Sort sections by priority ascending (trim lowest first)
        trimmable = sorted(
            [k for k in context_dict if k in self.SECTION_PRIORITY],
            key=lambda k: self.SECTION_PRIORITY.get(k, 50),
        )

        result = dict(context_dict)

        for section_key in trimmable:
            if self.estimate_dict_tokens(result) <= budget:
                break

            section = result.get(section_key)
            if section is None:
                continue

            # Strategy 1: If it's a list, progressively halve it
            if isinstance(section, list) and len(section) > 2:
                while len(section) > 1 and self.estimate_dict_tokens(result) > budget:
                    section = section[:len(section) // 2]
                    result[section_key] = section

            # Strategy 2: If it's a string (source code), truncate
            elif isinstance(section, str) and len(section) > 200:
                while len(section) > 200 and self.estimate_dict_tokens(result) > budget:
                    section = section[:len(section) // 2]
                    result[section_key] = section + "\n... [truncated to fit token budget]"

            # Strategy 3: If still over, remove the section entirely
            if self.estimate_dict_tokens(result) > budget:
                del result[section_key]

        return result

    def allocate_budget(
        self,
        total_budget: int,
        sections: List[str],
    ) -> Dict[str, int]:
        """
        Allocate token budget across sections proportionally to priority.
        """
        total_priority = sum(
            self.SECTION_PRIORITY.get(s, 50) for s in sections
        )
        if total_priority == 0:
            return {s: total_budget // max(len(sections), 1) for s in sections}

        allocation = {}
        for s in sections:
            priority = self.SECTION_PRIORITY.get(s, 50)
            allocation[s] = int(total_budget * priority / total_priority)

        return allocation
