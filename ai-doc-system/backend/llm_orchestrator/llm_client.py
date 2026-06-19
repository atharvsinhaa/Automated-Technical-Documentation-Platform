"""
llm_orchestrator/llm_client.py
────────────────────────────────────────────────────────────────
LLM client implementations for the Enterprise Documentation System.

Provides:
  1. BaseLLMClient  — abstract interface
  2. StubLLMClient  — mock for testing (no LLM required)
  3. OllamaLLMClient — production-grade local Ollama integration

Supports: qwen2.5:14b, qwen2.5:7b, qwen2.5-coder, deepseek-coder,
          llama3, mistral, and any Ollama-hosted model.

Fully offline — zero cloud APIs, zero SaaS dependencies.
"""

from __future__ import annotations

import json
import re
import time
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()


# ──────────────────────────────────────────────────────────────
#  ABSTRACT BASE
# ──────────────────────────────────────────────────────────────

class BaseLLMClient(ABC):
    """
    Abstract base class for offline LLM clients.

    To integrate your local LLM, subclass this and implement `generate()`.
    """

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.15,
    ) -> str:
        """
        Send a prompt to the LLM and return the generated text.

        Args:
            system_prompt: The system/role instruction.
            user_prompt: The user message with context + task.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature (low = deterministic).

        Returns:
            The LLM's text response.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the LLM backend is reachable."""
        ...

    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        ...


# ──────────────────────────────────────────────────────────────
#  PRODUCTION: Ollama Local Integration
# ──────────────────────────────────────────────────────────────

class OllamaLLMClient(BaseLLMClient):
    """
    Production-grade integration with Ollama for local LLM inference.

    Connects to a local Ollama instance (http://localhost:11434)
    and supports any model hosted by Ollama.

    Recommended models for enterprise documentation:
        - qwen2.5:14b      (best quality, needs ~16GB VRAM)
        - qwen2.5:7b       (good quality, needs ~8GB VRAM)
        - qwen2.5-coder    (optimized for code understanding)
        - deepseek-coder   (strong code + architecture reasoning)
        - llama3            (general purpose)

    Features:
        - Retry with exponential backoff
        - Configurable timeout for long generations
        - Token-safe prompt handling
        - Structured error reporting
        - Long-context support (Ollama's num_ctx)
    """

    # Models known to handle enterprise documentation well
    RECOMMENDED_MODELS = [
        "qwen2.5:14b",
        "qwen2.5:7b",
        "qwen2.5-coder",
        "deepseek-coder",
        "llama3",
        "mistral",
    ]

    def __init__(
        self,
        model:          str   = "qwen2.5:7b",
        host:           str   = "http://localhost:11434",
        temperature:    float = 0.15,
        max_tokens:     int   = 4096,
        context_window: int   = 32768,
        timeout_sec:    int   = 600,
        max_retries:    int   = 3,
        retry_delay:    float = 2.0,
        verbose:        bool  = True,
    ):
        """
        Initialize the Ollama LLM client.

        Args:
            model:          Ollama model name (e.g. "qwen2.5:7b")
            host:           Ollama server URL
            temperature:    Sampling temperature (0.1–0.2 for deterministic docs)
            max_tokens:     Maximum tokens to generate per response
            context_window: Context window size (num_ctx for Ollama)
            timeout_sec:    HTTP timeout in seconds (600s = 10min for long docs)
            max_retries:    Number of retry attempts on failure
            retry_delay:    Initial delay between retries (exponential backoff)
            verbose:        Print status messages
        """
        self.model = model
        self.host = host.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.context_window = context_window
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.verbose = verbose

        self._validate_setup()

    def _validate_setup(self):
        """Validate Ollama is reachable and model is available."""
        if self.verbose:
            print(f"[ollama] Connecting to {self.host}…")

        if not self.is_available():
            print(
                f"[ollama] ⚠ WARNING: Ollama is not reachable at {self.host}\n"
                f"[ollama]   Ensure Ollama is running: ollama serve\n"
                f"[ollama]   Then pull the model: ollama pull {self.model}"
            )
            return

        # Check if model is pulled
        available_models = self._list_models()
        model_base = self.model.split(":")[0]
        found = any(
            model_base in m.get("name", "")
            for m in available_models
        )

        if found:
            if self.verbose:
                print(f"[ollama] ✓ Connected. Model '{self.model}' is available.")
        else:
            model_names = [m.get("name", "") for m in available_models[:10]]
            print(
                f"[ollama] ⚠ Model '{self.model}' not found locally.\n"
                f"[ollama]   Available models: {model_names}\n"
                f"[ollama]   Pull it: ollama pull {self.model}"
            )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 0,
        temperature: float = 0.0,
    ) -> str:
        """
        Generate text using the local Ollama instance.

        Uses the /api/chat endpoint for system + user message support.
        Implements retry with exponential backoff on failures.
        """
        import requests

        # Use instance defaults if not overridden
        gen_max_tokens = max_tokens if max_tokens > 0 else self.max_tokens
        gen_temperature = temperature if temperature > 0 else self.temperature

        # Build the request payload (chat API for system + user messages)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": gen_temperature,
                "num_predict": gen_max_tokens,
                "num_ctx": self.context_window,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            },
        }

        url = f"{self.host}/api/chat"

        # Retry loop with exponential backoff
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if self.verbose:
                    prompt_chars = len(system_prompt) + len(user_prompt)
                    print(
                        f"  [ollama] Sending to {self.model} "
                        f"(~{prompt_chars:,} chars, attempt {attempt}/{self.max_retries})…"
                    )

                t0 = time.time()
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout_sec,
                )

                if response.status_code != 200:
                    error_text = response.text[:500]
                    raise OllamaError(
                        f"Ollama returned HTTP {response.status_code}: {error_text}"
                    )

                data = response.json()
                elapsed = time.time() - t0

                # Extract the response text
                message = data.get("message", {})
                text = message.get("content", "")

                if not text:
                    raise OllamaError(
                        f"Ollama returned empty response. "
                        f"Raw: {json.dumps(data)[:300]}"
                    )

                # Log stats
                if self.verbose:
                    eval_count = data.get("eval_count", 0)
                    eval_duration = data.get("eval_duration", 0)
                    tokens_per_sec = (
                        eval_count / (eval_duration / 1e9)
                        if eval_duration > 0 else 0
                    )
                    print(
                        f"  [ollama] ✓ Generated {len(text):,} chars "
                        f"({eval_count} tokens, {tokens_per_sec:.1f} tok/s, "
                        f"{elapsed:.1f}s)"
                    )

                return text

            except requests.exceptions.Timeout:
                last_error = OllamaError(
                    f"Ollama request timed out after {self.timeout_sec}s. "
                    f"Try increasing --timeout or reducing --token-budget."
                )
                if self.verbose:
                    print(f"  [ollama] ⚠ Timeout on attempt {attempt}")

            except requests.exceptions.ConnectionError:
                last_error = OllamaError(
                    f"Cannot connect to Ollama at {self.host}. "
                    f"Is Ollama running? Try: ollama serve"
                )
                if self.verbose:
                    print(f"  [ollama] ⚠ Connection refused on attempt {attempt}")

            except OllamaError as e:
                last_error = e
                if self.verbose:
                    print(f"  [ollama] ⚠ Error on attempt {attempt}: {e}")

            except Exception as e:
                last_error = OllamaError(f"Unexpected error: {e}")
                if self.verbose:
                    print(f"  [ollama] ⚠ Unexpected error on attempt {attempt}: {e}")

            # Exponential backoff before retry
            if attempt < self.max_retries:
                delay = self.retry_delay * (2 ** (attempt - 1))
                if self.verbose:
                    print(f"  [ollama] Retrying in {delay:.1f}s…")
                time.sleep(delay)

        # All retries exhausted
        raise last_error or OllamaError("All retries exhausted")

    def is_available(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            import requests
            r = requests.get(f"{self.host}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def model_name(self) -> str:
        """Return the model identifier."""
        return f"ollama/{self.model}"

    def _list_models(self):
        """List all locally available Ollama models."""
        try:
            import requests
            r = requests.get(f"{self.host}/api/tags", timeout=5)
            if r.status_code == 200:
                return r.json().get("models", [])
        except Exception:
            pass
        return []

    def list_available_models(self):
        """Public method to list available models (for CLI --list-models)."""
        models = self._list_models()
        if not models:
            print("[ollama] No models found. Pull one with: ollama pull qwen2.5:7b")
            return []
        print(f"[ollama] Available models ({len(models)}):")
        for m in models:
            name = m.get("name", "unknown")
            size_gb = m.get("size", 0) / (1024**3)
            print(f"  - {name} ({size_gb:.1f} GB)")
        return models


class OllamaError(Exception):
    """Raised when Ollama communication fails."""
    pass


# ──────────────────────────────────────────────────────────────
#  STUB: For testing without a running LLM
# ──────────────────────────────────────────────────────────────

class StubLLMClient(BaseLLMClient):
    """
    Stub LLM client that generates mock documentation.

    Use this to test the full pipeline end-to-end without
    an actual LLM running. The output clearly marks itself
    as stub-generated so there's no confusion.
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        """Generate mock documentation based on the prompt type."""
        if self.verbose:
            print(f"  [llm-stub] Generating mock response…")

        prompt_type = self._detect_prompt_type(system_prompt)
        target = self._extract_target(user_prompt)

        if prompt_type == "hld":
            return self._mock_hld(target)
        elif prompt_type == "lld":
            return self._mock_lld(target)
        elif prompt_type == "code-comment":
            return self._mock_code_comment(target, user_prompt)
        else:
            return self._mock_generic(target)

    def is_available(self) -> bool:
        return True

    def model_name(self) -> str:
        return "stub-llm-v1 (mock)"

    def _detect_prompt_type(self, system_prompt: str) -> str:
        sp = system_prompt.lower()
        if "high-level design" in sp or "hld" in sp:
            return "hld"
        elif "low-level design" in sp or "lld" in sp:
            return "lld"
        elif "inline code comment" in sp or "code comment" in sp:
            return "code-comment"
        return "documentation"

    def _extract_target(self, user_prompt: str) -> str:
        match = re.search(r"\*\*(.+?)\*\*", user_prompt)
        if match:
            return match.group(1)
        return "Unknown Component"

    def _mock_hld(self, target: str) -> str:
        return (
            f"# High-Level Design: {target}\n\n"
            f"> ⚠️ **STUB OUTPUT** — Replace StubLLMClient with OllamaLLMClient.\n\n"
            f"## 1. System Overview\n\n"
            f"**{target}** handles core business logic.\n\n"
            f"## 2. Service Boundaries\n\nIdentified from knowledge graph.\n\n"
            f"## 3. Data Flow\n\nAPI → Service → Database.\n\n"
            f"---\n*Stub Mode — run with `--model qwen2.5:7b` for real output*\n"
        )

    def _mock_lld(self, target: str) -> str:
        return (
            f"# Low-Level Design: {target}\n\n"
            f"> ⚠️ **STUB OUTPUT** — Replace StubLLMClient with OllamaLLMClient.\n\n"
            f"## 1. Module Overview\n\n"
            f"**{target}** implements core logic.\n\n"
            f"## 2. Function Structure\n\nExtracted from knowledge graph.\n\n"
            f"## 3. Execution Flow\n\n1. Entry → 2. Process → 3. Return.\n\n"
            f"---\n*Stub Mode — run with `--model qwen2.5:7b` for real output*\n"
        )

    def _mock_code_comment(self, target: str, user_prompt: str) -> str:
        source = "(source code not available in stub mode)"
        if "## Source Code" in user_prompt:
            parts = user_prompt.split("## Source Code")
            if len(parts) > 1:
                source = parts[1].split("## Context")[0].strip()[:500]

        return (
            f"# Code Comments: {target}\n\n"
            f"> ⚠️ **STUB OUTPUT** — Replace StubLLMClient with OllamaLLMClient.\n\n"
            f"```\n{source}\n```\n\n"
            f"---\n*Stub Mode — run with `--model qwen2.5:7b` for real output*\n"
        )

    def _mock_generic(self, target: str) -> str:
        return (
            f"# Documentation: {target}\n\n"
            f"> ⚠️ **STUB OUTPUT**\n\n"
            f"---\n*Stub Mode*\n"
        )


# ──────────────────────────────────────────────────────────────
#  FACTORY: Create the right client from CLI args
# ──────────────────────────────────────────────────────────────

def create_llm_client(
    model:       str   = "",
    ollama_host: str   = "",
    temperature: float = 0.15,
    max_tokens:  int   = 4096,
    context_window: int = 32768,
    timeout:     int   = 600,
    max_retries: int   = 3,
    verbose:     bool  = True,
) -> BaseLLMClient:
    """
    Factory function to create the appropriate LLM client.

    If `model` is set, creates OllamaLLMClient.
    If `model` is empty or "stub", creates StubLLMClient.
    """
    if not model or model.lower() == "stub":
        if verbose:
            print("[llm] Using StubLLMClient (mock mode)")
        return StubLLMClient(verbose=verbose)

    if verbose:
        print(f"[llm] Using OllamaLLMClient with model={model}")

    if not ollama_host:
        ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    return OllamaLLMClient(
        model=model,
        host=ollama_host,
        temperature=temperature,
        max_tokens=max_tokens,
        context_window=context_window,
        timeout_sec=timeout,
        max_retries=max_retries,
        verbose=verbose,
    )
