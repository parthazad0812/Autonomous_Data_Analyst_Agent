"""
LLM client wrapper — returns a LangChain ChatGoogleGenerativeAI instance.
Used by all agents for code generation and text synthesis.

Model: gemini-3.5-flash (thinking disabled via thinking_level='none' for speed).
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings


def _make_llm(temperature: float = 0.1) -> ChatGoogleGenerativeAI:
    """Build a Gemini 3.5 Flash LLM client."""
    return ChatGoogleGenerativeAI(
        model=settings.default_model,
        google_api_key=settings.gemini_api_key,
        temperature=temperature,
        max_output_tokens=8192,
    )


def get_llm(temperature: float = 0.1) -> ChatGoogleGenerativeAI:
    """Return a Gemini LLM client (thinking disabled for speed)."""
    return _make_llm(temperature)


def get_creative_llm() -> ChatGoogleGenerativeAI:
    """Higher temperature for report writing (thinking disabled for speed)."""
    return _make_llm(temperature=0.3)
