#!/usr/bin/env python3
"""Unified LLM Client - Supports Hermes Proxy, Ollama, and other OpenAI-compatible APIs."""

import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class GenerationResult:
    """Result from LLM generation."""
    text: str
    logprobs: Optional[List[float]] = None
    tokens: Optional[List[int]] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None


@dataclass
class EmbeddingResult:
    """Result from embedding generation."""
    embeddings: List[List[float]]
    model: str
    usage: Optional[Dict[str, int]] = None


class BaseLLMClient(ABC):
    """Abstract base for LLM clients."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str = None,
        temperature: float = 0.8,
        top_p: float = 0.9,
        max_tokens: int = 256,
        logprobs: bool = True,
        stop: List[str] = None,
        system_prompt: str = None,
    ) -> GenerationResult:
        pass

    @abstractmethod
    async def generate_batch(
        self,
        prompts: List[str],
        num_candidates: int = 1,
        **kwargs
    ) -> List[List[GenerationResult]]:
        pass

    @abstractmethod
    async def get_embeddings(
        self,
        texts: List[str],
        model: str = None,
    ) -> EmbeddingResult:
        pass

    @abstractmethod
    def get_available_models(self) -> Dict[str, List[str]]:
        pass

    def _extract_code(self, text: str) -> str:
        """Extract Python code from markdown fences or prose."""
        import re

        # Try to find code in ```python ... ``` fences
        code_blocks = re.findall(r'```python\n(.*?)\n```', text, re.DOTALL)
        if code_blocks:
            return code_blocks[0].strip()

        # Try any ``` ... ``` fences
        code_blocks = re.findall(r'```\n(.*?)\n```', text, re.DOTALL)
        if code_blocks:
            return code_blocks[0].strip()

        # If text starts with explanation, try to find first Python statement
        if "def " in text or "import " in text or "from " in text:
            lines = text.split('\n')
            for i, line in enumerate(lines):
                stripped = line.strip()
                if (stripped.startswith("def ") or
                    stripped.startswith("import ") or
                    stripped.startswith("from ") or
                    stripped.startswith("class ")):
                    return '\n'.join(lines[i:]).strip()

        # Strip common prose prefixes: "Sure!", "Certainly!", "Here's", "Let's", "###"
        lines = text.split('\n')
        code_lines = []
        in_code = False
        for line in lines:
            stripped = line.strip()
            if not in_code:
                if (stripped.startswith("def ") or
                    stripped.startswith("import ") or
                    stripped.startswith("from ") or
                    stripped.startswith("class ") or
                    stripped.startswith("#")):
                    in_code = True
                    code_lines.append(line)
            else:
                code_lines.append(line)

        if code_lines:
            return '\n'.join(code_lines).strip()

        return text.strip()


class HermesProxyClient(BaseLLMClient):
    """
    Hermes Proxy Client - Uses Hermes's OpenAI-compatible proxy.

    The proxy (started via `hermes proxy`) provides an OpenAI-compatible API
    backed by whatever providers the Hermes instance is configured with
    (config.yaml, OAuth, env vars).

    Proxy URL priority:
    1. Explicit proxy_url parameter
    2. HERMES_PROXY_URL environment variable
    3. Default: http://localhost:8645/v1
    """

    def __init__(self, proxy_url: Optional[str] = None):
        self.proxy_url = proxy_url or os.environ.get("HERMES_PROXY_URL") or "http://localhost:8645/v1"
        self._client = None
        print(f"Hermes Proxy Client initialized: {self.proxy_url}")

    def _get_client(self):
        """Lazy-initialize the OpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                base_url=self.proxy_url,
                api_key="hermes-proxy",  # placeholder, proxy ignores it
            )
        return self._client

    async def generate(
        self,
        prompt: str,
        model: str = None,
        temperature: float = 0.8,
        top_p: float = 0.9,
        max_tokens: int = 256,
        logprobs: bool = True,
        stop: List[str] = None,
        system_prompt: str = None,
    ) -> GenerationResult:
        client = self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # If model is None or "default", the proxy uses the configured default
        # coding model from config.yaml (llm.models.coding)
        response = await client.chat.completions.create(
            model=model or "default",
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            logprobs=logprobs,
            stop=stop,
        )

        choice = response.choices[0]

        # Extract logprobs if available
        logprobs_list = None
        if logprobs and choice.logprobs and choice.logprobs.content:
            logprobs_list = [lp.logprob for lp in choice.logprobs.content]

        # Handle models that output in reasoning field (e.g., qwen3.5 on Ollama)
        text = choice.message.content or ""
        if not text:
            reasoning = getattr(choice.message, 'reasoning', None)
            if reasoning:
                text = reasoning

        text = self._extract_code(text)

        return GenerationResult(
            text=text,
            logprobs=logprobs_list,
            finish_reason=choice.finish_reason,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            } if response.usage else None,
            model=response.model,
        )

    async def generate_batch(
        self,
        prompts: List[str],
        num_candidates: int = 1,
        **kwargs
    ) -> List[List[GenerationResult]]:
        results = []
        for prompt in prompts:
            candidates = []
            for _ in range(num_candidates):
                result = await self.generate(prompt, **kwargs)
                candidates.append(result)
            results.append(candidates)
        return results

    async def get_embeddings(
        self,
        texts: List[str],
        model: str = None,
    ) -> EmbeddingResult:
        client = self._get_client()
        model = model or "text-embedding-3-small"

        response = await client.embeddings.create(
            model=model,
            input=texts,
        )

        return EmbeddingResult(
            embeddings=[d.embedding for d in response.data],
            model=model,
            usage={"total_tokens": response.usage.total_tokens} if response.usage else None,
        )

    def get_available_models(self) -> Dict[str, List[str]]:
        return {
            "proxy": [
                "default",           # Uses config.yaml default coding model
                "nvidia/nemotron-3-ultra-550b-a55b",
                "qwen/qwen3.8-max",
                "deepseek/deepseek-v4-flash-0731",
                "anthropic/claude-opus-5",
                "openai/gpt-4o",
            ]
        }


class OllamaClient(BaseLLMClient):
    """
    Ollama Client - Direct connection to local Ollama server.

    Requires Ollama running at http://127.0.0.1:11434 (default)
    with models pulled (e.g., `ollama pull qwen2.5-coder:7b-instruct`).
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434/v1",
        default_model: str = "qwen2.5-coder:7b-instruct",
    ):
        self.base_url = base_url
        self.default_model = default_model
        self._client = None
        print(f"Ollama Client initialized: {base_url}, default model: {default_model}")

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(base_url=self.base_url, api_key="ollama")
        return self._client

    async def generate(
        self,
        prompt: str,
        model: str = None,
        temperature: float = 0.8,
        top_p: float = 0.9,
        max_tokens: int = 256,
        logprobs: bool = True,
        stop: List[str] = None,
        system_prompt: str = None,
    ) -> GenerationResult:
        client = self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            logprobs=logprobs,
            stop=stop,
        )

        choice = response.choices[0]

        logprobs_list = None
        if logprobs and choice.logprobs and choice.logprobs.content:
            logprobs_list = [lp.logprob for lp in choice.logprobs.content]

        text = choice.message.content or ""
        # Handle models that output in reasoning field (e.g., qwen3 on Ollama)
        if not text:
            reasoning = getattr(choice.message, 'reasoning', None)
            if reasoning:
                text = reasoning

        text = self._extract_code(text)

        return GenerationResult(
            text=text,
            logprobs=logprobs_list,
            finish_reason=choice.finish_reason,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            } if response.usage else None,
            model=response.model,
        )

    async def generate_batch(
        self,
        prompts: List[str],
        num_candidates: int = 1,
        **kwargs
    ) -> List[List[GenerationResult]]:
        results = []
        for prompt in prompts:
            candidates = []
            for _ in range(num_candidates):
                result = await self.generate(prompt, **kwargs)
                candidates.append(result)
            results.append(candidates)
        return results

    async def get_embeddings(
        self,
        texts: List[str],
        model: str = None,
    ) -> EmbeddingResult:
        client = self._get_client()
        model = model or "nomic-embed-text"

        response = await client.embeddings.create(
            model=model,
            input=texts,
        )

        return EmbeddingResult(
            embeddings=[d.embedding for d in response.data],
            model=model,
            usage={"total_tokens": response.usage.total_tokens} if response.usage else None,
        )

    def get_available_models(self) -> Dict[str, List[str]]:
        # Could query /api/tags but return sensible defaults
        return {
            "ollama": [
                "qwen2.5-coder:7b-instruct",
                "qwen2.5-coder:1.5b-instruct",
                "deepseek-r1:7b",
                "qwen3.5:4b",
                "llama3.1:8b",
                "specforge-128k:latest",
                "smollm2:135m",
            ]
        }


class LLMClientFactory:
    """Factory for creating LLM clients based on provider type."""

    @staticmethod
    def create(
        provider: str = "auto",
        **kwargs
    ) -> BaseLLMClient:
        """
        Create an LLM client.

        Args:
            provider: "hermes" | "ollama" | "auto"
            **kwargs: Provider-specific arguments:
                - hermes: proxy_url
                - ollama: base_url, default_model
        """
        provider = provider.lower()

        if provider == "auto":
            # Auto-detect: check HERMES_PROXY_URL, else try Ollama
            if os.environ.get("HERMES_PROXY_URL"):
                return HermesProxyClient()
            # Check if Ollama is available
            import httpx
            try:
                resp = httpx.get("http://127.0.0.1:11434/api/tags", timeout=2.0)
                if resp.status_code == 200:
                    return OllamaClient()
            except Exception:
                pass
            # Fallback to Hermes proxy default
            return HermesProxyClient()

        elif provider == "hermes":
            return HermesProxyClient(kwargs.get("proxy_url"))

        elif provider == "ollama":
            return OllamaClient(
                base_url=kwargs.get("base_url", "http://127.0.0.1:11434/v1"),
                default_model=kwargs.get("default_model", "qwen2.5-coder:7b-instruct"),
            )

        else:
            raise ValueError(f"Unknown provider: {provider}. Use 'hermes', 'ollama', or 'auto'")


# Backward compatibility
HermesLLMClient = HermesProxyClient
create_hermes_client = lambda proxy_url=None: HermesProxyClient(proxy_url)


# Convenience function
def create_llm_client(
    provider: str = "auto",
    **kwargs
) -> BaseLLMClient:
    """Create an LLM client for the GRG agent."""
    return LLMClientFactory.create(provider, **kwargs)