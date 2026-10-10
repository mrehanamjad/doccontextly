"""LLM provider abstraction layer.

Supports: Groq, OpenAI, OpenRouter, any OpenAI-compatible.
"""

from abc import ABC, abstractmethod
from langchain_core.language_models import BaseChatModel
from app.core.config import settings
from app.core.logger import logger


class BaseLLMProvider(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    def get_llm(self) -> BaseChatModel:
        ...


class GroqProvider(BaseLLMProvider):
    def get_llm(self) -> BaseChatModel:
        from langchain_groq import ChatGroq
        logger.info(f"Initializing Groq LLM: {settings.LLM_MODEL}")
        return ChatGroq(
            model=settings.LLM_MODEL,
            temperature=0.2,
            max_tokens=settings.MAX_TOKENS,
            groq_api_key=settings.GROQ_API_KEY,
            reasoning_format="hidden"
        )


class OpenAIProvider(BaseLLMProvider):
    def get_llm(self) -> BaseChatModel:
        from langchain_community.chat_models import ChatOpenAI
        logger.info(f"Initializing OpenAI LLM: {settings.LLM_MODEL}")
        return ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0.1,
            max_tokens=settings.MAX_TOKENS,
            api_key=settings.OPENAI_API_KEY,
        )


class OpenRouterProvider(BaseLLMProvider):
    def get_llm(self) -> BaseChatModel:
        from langchain_community.chat_models import ChatOpenAI
        logger.info(f"Initializing OpenRouter LLM: {settings.LLM_MODEL}")
        return ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0.1,
            max_tokens=settings.MAX_TOKENS,
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            
        )

class OpenAICompatibleProvider(BaseLLMProvider):
    """Any OpenAI-compatible API (Vyce AI by default)."""

    def get_llm(self) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        if not settings.CUSTOM_LLM_API_KEY:
            raise ValueError("CUSTOM_LLM_API_KEY is not configured in .env")

        model = settings.CUSTOM_LLM_MODEL or settings.LLM_MODEL
        logger.info(f"Initializing OpenAI-compatible LLM: {model} @ {settings.CUSTOM_LLM_BASE_URL}")
        return ChatOpenAI(
            model=model,
            temperature=0.1,
            max_tokens=settings.MAX_TOKENS,
            api_key=settings.CUSTOM_LLM_API_KEY,
            base_url=settings.CUSTOM_LLM_BASE_URL,
        )


class OllamaProvider(BaseLLMProvider):
    """Local models served by Ollama."""

    def get_llm(self) -> BaseChatModel:
        from langchain_ollama import ChatOllama

        logger.info(f"Initializing Ollama LLM: {settings.OLLAMA_MODEL} @ {settings.OLLAMA_BASE_URL}")
        return ChatOllama(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.1,
            num_predict=settings.MAX_TOKENS,   
        )


_PROVIDERS: dict[str, type[BaseLLMProvider]] = {
    "groq": GroqProvider,
    "openai": OpenAIProvider,
    "openrouter": OpenRouterProvider,
    "custom": OpenAICompatibleProvider,  
    "ollama": OllamaProvider,
}


def get_llm_provider(provider_name: str | None = None) -> BaseLLMProvider:
    """Factory function — returns an LLM provider instance."""
    name = (provider_name or settings.LLM_PROVIDER).lower()
    provider_cls = _PROVIDERS.get(name)
    if not provider_cls:
        raise ValueError(f"Unknown LLM provider: {name}. Available: {list(_PROVIDERS.keys())}")
    return provider_cls()
