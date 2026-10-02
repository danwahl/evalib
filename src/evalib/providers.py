"""Model providers."""


def provider(model: str) -> str:
    """The provider slug of an Inspect model id, e.g. "openai" for
    "openrouter/openai/gpt-5"."""
    parts = model.split("/")
    return parts[-2] if len(parts) > 1 else ""
