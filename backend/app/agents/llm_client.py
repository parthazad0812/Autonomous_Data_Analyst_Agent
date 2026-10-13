"""
LLM client wrapper — returns a LangChain model with fallback chain.
Primary model: Google Gemini (settings.default_model)
When it is busy or out of quota: Gemini lite (settings.gemini_light_model)
Last fallback: Groq (settings.groq_model)

Gemini-credit savings:
- Gemini fails over to Groq after 2 retries instead of LangChain's default 6
  (which spent minutes backing off on quota errors).
- A daily-quota error opens a circuit breaker: later calls in the cooldown window
  go straight to Groq instead of re-hitting an exhausted Gemini quota.
- Light planning calls (get_llm(light=True)) use settings.gemini_light_model,
  a separate free-tier quota bucket from the main model.
"""

import logging
import re
import time
from typing import Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from app.config import settings

logger = logging.getLogger(__name__)

# Circuit breaker: model name -> epoch seconds until which that Gemini model is skipped.
_gemini_disabled_until: dict[str, float] = {}
# Number of requests sent to Gemini in this process (for monitoring credit use).
gemini_request_count: int = 0


def _is_daily_quota_error(err: Exception) -> bool:
    """Daily-quota 429s say 'PerDay' in the quota id and/or 'retry in <N>h'.
    Per-minute 429s share the same metric name but ask to retry in seconds."""
    text = str(err)
    if "exceeded your current quota" not in text and "RESOURCE_EXHAUSTED" not in text:
        return False
    return "PerDay" in text or re.search(r"retry in \d+h", text) is not None


class GeminiQuotaExhausted(RuntimeError):
    """Raised without calling Gemini while the daily-quota breaker is open (triggers fallback)."""


def _model_key(model: str) -> str:
    return model.removeprefix("models/")  # the client reports "models/<name>"


def _gemini_available(model: str) -> bool:
    return time.time() >= _gemini_disabled_until.get(_model_key(model), 0.0)


class _QuotaAwareGemini(ChatGoogleGenerativeAI):
    """Counts Gemini requests and trips a per-model circuit breaker on a daily-quota error.
    The breaker is checked on every call, so agents that reuse one client across
    code-fix retries also stop hitting an exhausted quota."""

    def _generate(self, *args, **kwargs):
        global gemini_request_count
        if not _gemini_available(self.model):
            raise GeminiQuotaExhausted(f"{self.model} daily quota exhausted (breaker open)")
        gemini_request_count += 1
        logger.info("gemini request #%d (model=%s)", gemini_request_count, self.model)
        try:
            return super()._generate(*args, **kwargs)
        except Exception as e:
            if _is_daily_quota_error(e):
                _gemini_disabled_until[_model_key(self.model)] = time.time() + settings.gemini_quota_cooldown_seconds
                logger.warning("Gemini %s daily quota exhausted; skipping it (next fallback) for %ss",
                               self.model, settings.gemini_quota_cooldown_seconds)
            raise


class _BudgetedGroq(ChatGroq):
    """Groq's free tier rejects a request when prompt + max_tokens exceeds its tokens-per-minute
    limit (HTTP 413). Size max_tokens from the actual prompt, and shrink once on a 413."""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        prompt_chars = sum(len(str(m.content)) for m in messages)
        est_prompt_tokens = int(prompt_chars / 3) + 200  # conservative for code-heavy text
        kwargs["max_tokens"] = max(1024, min(6000, settings.groq_tpm_limit - est_prompt_tokens))
        try:
            return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        except Exception as e:
            m = re.search(r"Limit (\d+), Requested (\d+)", str(e))
            if not m:
                raise
            over = int(m.group(2)) - int(m.group(1))
            kwargs["max_tokens"] = kwargs["max_tokens"] - over - 100
            if kwargs["max_tokens"] < 512:
                raise
            logger.info("Groq request too large by %d tokens; retrying with max_tokens=%d",
                        over, kwargs["max_tokens"])
            return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def _make_llm(temperature: float = 0.1, light: bool = False) -> Any:
    """
    Build an LLM client with fallback chain:
    1. Primary: Google Gemini (settings.default_model, or gemini_light_model if light)
    2. If the main model is busy (503) or out of quota: Gemini lite (settings.gemini_light_model)
    3. Fallback: Groq (settings.groq_model)
    """
    candidates = []

    # 1-2. Gemini main, then lite (each skipped while its daily-quota breaker is open).
    #      The main model gets a single retry so a busy model hands over to lite quickly.
    gemini_models = [settings.gemini_light_model] if light else [settings.default_model, settings.gemini_light_model]
    for i, gemini_model in enumerate(dict.fromkeys(gemini_models)):
        if not (settings.gemini_api_key and _gemini_available(gemini_model)):
            continue
        try:
            candidates.append(
                _QuotaAwareGemini(
                    model=gemini_model,
                    google_api_key=settings.gemini_api_key,
                    temperature=temperature,
                    max_output_tokens=8192,
                    max_retries=1 if i == 0 and len(gemini_models) > 1 else 2,
                )
            )
        except Exception as e:
            logger.warning(f"Could not init Gemini model {gemini_model}: {e}")

    # 2. Fallback: Groq. Its free tier counts prompt + requested max_tokens against a
    #    tokens-per-minute limit, so _BudgetedGroq sizes max_tokens per request.
    if settings.groq_api_key:
        try:
            candidates.append(
                _BudgetedGroq(
                    model_name=settings.groq_model,
                    groq_api_key=settings.groq_api_key,
                    temperature=temperature,
                    max_tokens=4096,
                    max_retries=3,
                    model_kwargs={"reasoning_effort": "low"},
                )
            )
        except Exception as e:
            logger.warning(f"Could not init Groq {settings.groq_model} model: {e}")

    if not candidates:
        raise RuntimeError(
            "No LLM API keys configured. Set GEMINI_API_KEY and/or GROQ_API_KEY in environment variables."
        )

    primary = candidates[0]
    fallbacks = candidates[1:]

    if fallbacks:
        return primary.with_fallbacks(fallbacks)
    return primary


def get_llm(temperature: float = 0.1, light: bool = False) -> Any:
    """Return an LLM client with fallback chain."""
    return _make_llm(temperature, light)


def get_creative_llm() -> Any:
    """Higher temperature for report writing with fallback chain."""
    return _make_llm(temperature=0.3)
