"""Provider selection is explicit. No automatic switch across quotas or models."""

from .openrouter import OpenRouter


def create_client(settings):
    if settings.provider == "openrouter":
        return OpenRouter(settings)
    if settings.provider == "groq":
        from .groq import Groq
        return Groq(settings)
    raise ValueError("LLM_PROVIDER must be openrouter or groq")
