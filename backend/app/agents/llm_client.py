"""
LLM client wrapper — returns a LangChain model with fallback chain.
Primary model: Groq (llama-3.3-70b-versatile)
Fallback model: Google Gemini (gemini-3.5-flash)
"""

import logging
from typing import Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from app.config import settings

logger = logging.getLogger(__name__)


def _make_llm(temperature: float = 0.1) -> Any:
    """
    Build an LLM client with fallback chain:
    1. Primary: Groq (llama-3.3-70b-versatile)
    2. Fallback: Google Gemini (gemini-3.5-flash)
    """
    candidates = []

    # 1. Groq Primary: llama-3.3-70b-versatile
    if settings.groq_api_key:
        try:
            candidates.append(
                ChatGroq(
                    model_name="llama-3.3-70b-versatile",
                    groq_api_key=settings.groq_api_key,
                    temperature=temperature,
                    max_tokens=8192,
                )
            )
        except Exception as e:
            logger.warning(f"Could not init Groq llama-3.3-70b-versatile model: {e}")

    # 2. Fallback: Google Gemini (gemini-3.5-flash)
    if settings.gemini_api_key:
        try:
            candidates.append(
                ChatGoogleGenerativeAI(
                    model="gemini-3.5-flash",
                    google_api_key=settings.gemini_api_key,
                    temperature=temperature,
                    max_output_tokens=8192,
                )
            )
        except Exception as e:
            logger.warning(f"Could not init Gemini model: {e}")

    if not candidates:
        # Default fallback if no API keys are provided in environment
        return ChatGoogleGenerativeAI(
            model="gemini-3.5-flash",
            google_api_key=settings.gemini_api_key or "mock-key",
            temperature=temperature,
        )

    primary = candidates[0]
    fallbacks = candidates[1:]

    if fallbacks:
        return primary.with_fallbacks(fallbacks)
    return primary


def get_llm(temperature: float = 0.1) -> Any:
    """Return an LLM client with fallback chain."""
    return _make_llm(temperature)


def get_creative_llm() -> Any:
    """Higher temperature for report writing with fallback chain."""
    return _make_llm(temperature=0.3)
