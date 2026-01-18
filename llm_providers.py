#!/usr/bin/env python3
"""
LLM Provider Abstraction Layer

Provides a pluggable architecture for switching between different LLM providers
(OpenAI, Google AI) without modifying agent code.

Usage:
    from llm_providers import get_provider, get_llm
    
    # Get a provider directly
    provider = get_provider("openai")
    llm = provider.create_chat_llm("gpt-5.2-mini", temperature=0)
    
    # Or use the convenience function with settings
    llm = get_llm(provider="openai", model="gpt-5.2-mini", temperature=0)
"""

import os
from abc import ABC, abstractmethod
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    name: str = "base"
    display_name: str = "Base Provider"
    
    @abstractmethod
    def create_chat_llm(
        self, 
        model: str, 
        temperature: float = 0,
        api_key: Optional[str] = None
    ) -> BaseChatModel:
        """Create a chat LLM instance.
        
        Args:
            model: Model name/identifier
            temperature: Sampling temperature (0 = deterministic)
            api_key: Optional API key (uses env var if not provided)
            
        Returns:
            A LangChain BaseChatModel instance
        """
        pass
    
    @abstractmethod
    def validate_connection(
        self, 
        model: str, 
        api_key: Optional[str] = None
    ) -> tuple[bool, str]:
        """Validate that the provider/model/key combination works.
        
        Args:
            model: Model name to test
            api_key: Optional API key to test
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        pass
    
    @abstractmethod
    def list_available_models(self) -> list[dict]:
        """List available models for this provider.
        
        Returns:
            List of dicts with 'id', 'name', and optional 'description'
        """
        pass
    
    def get_env_var_name(self) -> str:
        """Get the environment variable name for this provider's API key."""
        return f"{self.name.upper()}_API_KEY"


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM provider using langchain-openai."""
    
    name = "openai"
    display_name = "OpenAI"
    
    MODELS = [
        {"id": "gpt-5.2", "name": "GPT-5.2", "description": "Most capable model"},
        {"id": "gpt-5-mini", "name": "GPT-5 Mini", "description": "Fast and efficient"},
        {"id": "gpt-4o", "name": "GPT-4o", "description": "Previous generation flagship"},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "description": "Previous generation efficient"},
    ]
    
    def create_chat_llm(
        self, 
        model: str, 
        temperature: float = 0,
        api_key: Optional[str] = None
    ) -> BaseChatModel:
        from langchain_openai import ChatOpenAI
        
        kwargs = {
            "model": model,
            "temperature": temperature,
        }
        if api_key:
            kwargs["api_key"] = api_key
            
        return ChatOpenAI(**kwargs)
    
    def validate_connection(
        self, 
        model: str, 
        api_key: Optional[str] = None
    ) -> tuple[bool, str]:
        try:
            llm = self.create_chat_llm(model, api_key=api_key)
            # Make a minimal test call
            response = llm.invoke("Say 'ok'")
            return True, f"Connection successful. Model {model} is working."
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                return False, "Invalid API key. Please check your OPENAI_API_KEY."
            elif "model" in error_msg.lower():
                return False, f"Model '{model}' not found. Please check the model name."
            else:
                return False, f"Connection failed: {error_msg}"
    
    def list_available_models(self) -> list[dict]:
        return self.MODELS.copy()
    
    def get_env_var_name(self) -> str:
        return "OPENAI_API_KEY"


class GoogleAIProvider(BaseLLMProvider):
    """Google AI (Gemini) provider using langchain-google-genai."""
    
    name = "google"
    display_name = "Google AI (Gemini)"
    
    MODELS = [
        {"id": "gemini-3-flash-preview", "name": "Gemini 3 Flash", "description": "Fastest, free tier available"},
        {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "description": "Most capable Gemini model"},
        {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "description": "Previous generation fast model"},
    ]
    
    def create_chat_llm(
        self, 
        model: str, 
        temperature: float = 0,
        api_key: Optional[str] = None
    ) -> BaseChatModel:
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        kwargs = {
            "model": model,
            "temperature": temperature,
        }
        if api_key:
            kwargs["google_api_key"] = api_key
            
        return ChatGoogleGenerativeAI(**kwargs)
    
    def validate_connection(
        self, 
        model: str, 
        api_key: Optional[str] = None
    ) -> tuple[bool, str]:
        try:
            llm = self.create_chat_llm(model, api_key=api_key)
            # Make a minimal test call
            response = llm.invoke("Say 'ok'")
            return True, f"Connection successful. Model {model} is working."
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                return False, "Invalid API key. Please check your GOOGLE_API_KEY."
            elif "model" in error_msg.lower():
                return False, f"Model '{model}' not found. Please check the model name."
            else:
                return False, f"Connection failed: {error_msg}"
    
    def list_available_models(self) -> list[dict]:
        return self.MODELS.copy()
    
    def get_env_var_name(self) -> str:
        return "GOOGLE_API_KEY"


# Provider registry
_PROVIDERS: dict[str, type[BaseLLMProvider]] = {
    "openai": OpenAIProvider,
    "google": GoogleAIProvider,
}


def get_provider(provider_name: str) -> BaseLLMProvider:
    """Get a provider instance by name.
    
    Args:
        provider_name: One of 'openai', 'google'
        
    Returns:
        Provider instance
        
    Raises:
        ValueError: If provider name is not recognized
    """
    if provider_name not in _PROVIDERS:
        available = ", ".join(_PROVIDERS.keys())
        raise ValueError(f"Unknown provider '{provider_name}'. Available: {available}")
    
    return _PROVIDERS[provider_name]()


def list_providers() -> list[dict]:
    """List all available providers.
    
    Returns:
        List of dicts with 'id', 'name', and 'env_var'
    """
    providers = []
    for name, cls in _PROVIDERS.items():
        instance = cls()
        providers.append({
            "id": name,
            "name": instance.display_name,
            "env_var": instance.get_env_var_name(),
        })
    return providers


def get_llm(
    provider: str = "openai",
    model: str = "gpt-5.2-mini",
    temperature: float = 0,
    api_key: Optional[str] = None,
) -> BaseChatModel:
    """Convenience function to get an LLM instance.
    
    Args:
        provider: Provider name ('openai', 'google')
        model: Model identifier
        temperature: Sampling temperature
        api_key: Optional API key (uses env var if not provided)
        
    Returns:
        A LangChain BaseChatModel instance
    """
    provider_instance = get_provider(provider)
    return provider_instance.create_chat_llm(model, temperature, api_key)
