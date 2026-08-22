"""
LLM Provider abstraction for OminiVoice.
NVIDIA Integrate API only (no local LLM).
"""
import os
import json
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict, Any, Optional

import httpx
from pydantic import BaseModel


class LLMProviderError(Exception):
    """Exception raised by LLM providers."""
    pass


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Generate text completion (non-streaming)."""
        pass

    @abstractmethod
    async def stream_reply(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 1.0,
        top_p: float = 0.95,
        max_tokens: int = 16384,
    ) -> AsyncIterator[str]:
        """Stream chat completion tokens."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close any connections."""
        pass


class NvidiaIntegrateProvider(LLMProvider):
    """NVIDIA Integrate API provider for hosted LLMs."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        model: str = "stepfun-ai/step-3.7-flash",
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=120.0,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "text/event-stream",
                },
            )
        return self._client

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        client = self._get_client()
        response = await client.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "top_p": 0.95,
                "max_tokens": max_tokens,
                "stream": False,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    async def stream_reply(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 1.0,
        top_p: float = 0.95,
        max_tokens: int = 16384,
    ) -> AsyncIterator[str]:
        client = self._get_client()
        async with client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
                "stream": True,
                "seed": 42,
            },
            timeout=120.0,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


# Provider registry
_PROVIDERS: Dict[str, LLMProvider] = {}


def get_llm_provider(provider_name: str, model: str) -> LLMProvider:
    """
    Get or create an LLM provider instance.

    Args:
        provider_name: Provider identifier (nvidia_integrate)
        model: Model identifier

    Returns:
        LLMProvider instance

    Raises:
        LLMProviderError: If provider is unknown or not configured
    """
    from app.core.config import settings

    cache_key = f"{provider_name}:{model}"

    if cache_key in _PROVIDERS:
        return _PROVIDERS[cache_key]

    if provider_name == "nvidia_integrate":
        if not settings.NVIDIA_API_KEY or settings.NVIDIA_API_KEY.startswith("nvapi_your"):
            raise LLMProviderError("NVIDIA_API_KEY not configured")
        provider = NvidiaIntegrateProvider(
            api_key=settings.NVIDIA_API_KEY,
            base_url=settings.NVIDIA_BASE_URL,
            model=model,
        )
    else:
        raise LLMProviderError(f"Unknown LLM provider: {provider_name}. Only 'nvidia_integrate' is supported.")

    _PROVIDERS[cache_key] = provider
    return provider


async def close_all_providers() -> None:
    """Close all provider connections."""
    for provider in _PROVIDERS.values():
        await provider.close()
    _PROVIDERS.clear()