"""
LLM client wrapper — returns a LangChain model with multi-provider fallback chain.
Primary model: Groq (openai/gpt-oss-120b)
Fallback 1: Google Gemini (gemini-3.5-flash)
Fallback 2: Groq (llama-3.3-70b-versatile)
"""

import logging
from typing import Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from app.config import settings

logger = logging.getLogger(__name__)


def _make_llm(temperature: float = 0.1) -> Any:
    """
    Build an LLM client with multi-provider fallback chain:
    1. Groq (openai/gpt-oss-120b)
    2. Google Gemini (gemini-3.5-flash)
    3. Groq (llama-3.3-70b-versatile)
    """
    candidates = []

    # 1. Groq Primary: openai/gpt-oss-120b
    if settings.groq_api_key:
        try:
            candidates.append(
                ChatGroq(
                    model_name="openai/gpt-oss-120b",
                    groq_api_key=settings.groq_api_key,
                    temperature=temperature,
                    max_tokens=8192,
                )
            )
        except Exception as e:
            logger.warning(f"Could not init Groq gpt-oss-120b model: {e}")

    # 2. Google Gemini
    if settings.gemini_api_key:
        try:
            candidates.append(
                ChatGoogleGenerativeAI(
                    model=settings.default_model if "gemini" in settings.default_model else "gemini-3.5-flash",
                    google_api_key=settings.gemini_api_key,
                    temperature=temperature,
                    max_output_tokens=8192,
                )
            )
        except Exception as e:
            logger.warning(f"Could not init Gemini model: {e}")

    # 3. Groq Fallback: llama-3.3-70b-versatile
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
