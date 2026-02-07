"""
Provider abstraction for multi-platform tile styling.

Uses LiteLLM under the hood to support multiple AI providers:
- Gemini (Google AI Studio / Vertex AI)
- OpenAI (GPT Image 1 / 1.5)
- Stability AI (style transfer)

Example:
    from providers import TileStyler, list_providers

    # List available providers
    print(list_providers())  # {'gemini': 'gemini/gemini-2.5-flash-image', ...}

    # Use a specific provider
    styler = TileStyler(provider="gemini")
    result = styler.style_tile(tile_bytes, prompt="watercolor painting")
"""

from .base import TileStyler, StyleResult, list_providers, PROVIDER_MODELS

__all__ = ["TileStyler", "StyleResult", "list_providers", "PROVIDER_MODELS"]
