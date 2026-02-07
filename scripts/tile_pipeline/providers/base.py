"""
LiteLLM-based provider wrapper for tile style transformation.

This module wraps LiteLLM's image_edit function with tile-specific
preprocessing (resize to 512x512, RGB conversion) and our system prompt.

Supported providers:
- gemini: Google Gemini 2.5 Flash Image (free tier available)
- openai: OpenAI GPT Image 1 ($0.02-$0.19 per image)
- vertex: Google Vertex AI Gemini (requires GCP project)

Usage:
    from providers.base import TileStyler

    styler = TileStyler(provider="gemini")
    result = styler.style_tile(
        tile_bytes=image_data,
        prompt="cyberpunk neon night",
    )
"""

import base64
import io
import os
from dataclasses import dataclass
from typing import Optional

import litellm
from PIL import Image


# Model mappings for each provider
PROVIDER_MODELS = {
    "gemini": "gemini/gemini-2.5-flash-image",
    "openai": "gpt-image-1",
    "openai-1.5": "gpt-image-1.5",
    "vertex": "vertex_ai/gemini-2.5-flash",
    "stability": "stability/stable-style-transfer-v1:0",
}

# Default system prompt for tile styling
DEFAULT_SYSTEM_PROMPT = """You are a cinematic map tile artist. You will receive an image of a 3D-rendered
map tile showing an urban scene from a STRAIGHT-DOWN TOP VIEW (orthographic, like satellite imagery).

CAMERA ANGLE: This is a 90° nadir view - the camera looks STRAIGHT DOWN at the ground.
You are seeing ROOFTOPS of buildings, not walls. Trees appear as circular canopies from above.
This is NOT isometric - there is NO tilt or angle. Think Google Maps satellite view.

SCENE ELEMENTS (what you're looking at from above):
- BUILDINGS: Flat rooftop shapes (rectangles, L-shapes). You see roofs, not walls.
- TREES: Round/fluffy circular shapes - these are tree canopies viewed from directly above.
- STREETS: The flat gray/brown strips between buildings are roads.
- GRASS/PARKS: Flat green areas are lawns or parks.

CRITICAL REQUIREMENTS:
1. PRESERVE GEOMETRY - All shapes and positions must remain EXACTLY the same.
   Do not add, remove, move, or distort anything.

2. KEEP TOP-DOWN VIEW - Do NOT add any perspective, tilt, or isometric angle.
   The camera must stay looking straight down. No 3D perspective effects.

3. TILE CONTINUITY - This tile connects seamlessly with neighbors in a map grid.
   Edge colors must be consistent for tiling.

4. NO TEXT/LABELS - Do not add any text, watermarks, or UI elements.

5. OUTPUT SIZE - Return exactly 512×512 pixels.

BE BOLD WITH STYLE: While geometry and camera angle are frozen, you have FULL creative freedom with:
- Colors, lighting, and atmosphere
- Surface textures and materials
- Glow effects, reflections, and mood
- Making the scene dramatic and cinematic

Transform this tile into something visually stunning while keeping the straight-down view."""


@dataclass
class StyleResult:
    """Result from a style generation request."""
    image_bytes: bytes
    provider: str
    model: str


class TileStyler:
    """Wrapper around LiteLLM for tile-specific style transformation.

    Handles:
    - Image preprocessing (resize to 512x512, RGB conversion)
    - System prompt injection
    - Provider selection via simple string ID
    - Response parsing to raw bytes
    """

    def __init__(
        self,
        provider: str = "gemini",
        api_key: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        """Initialize the styler with a specific provider.

        Args:
            provider: Provider ID ('gemini', 'openai', 'vertex', 'stability')
            api_key: Optional API key (otherwise uses environment variables)
            system_prompt: Optional custom system prompt
        """
        if provider not in PROVIDER_MODELS:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Supported: {', '.join(PROVIDER_MODELS.keys())}"
            )

        self.provider = provider
        self.model = PROVIDER_MODELS[provider]
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

        # Set API key if provided
        if api_key:
            self._set_api_key(provider, api_key)

    def _set_api_key(self, provider: str, api_key: str) -> None:
        """Set the API key for the given provider."""
        env_vars = {
            "gemini": "GEMINI_API_KEY",
            "openai": "OPENAI_API_KEY",
            "openai-1.5": "OPENAI_API_KEY",
            "vertex": "GOOGLE_APPLICATION_CREDENTIALS",
            "stability": "STABILITY_API_KEY",
        }
        if provider in env_vars:
            os.environ[env_vars[provider]] = api_key

    def _preprocess_image(self, image_bytes: bytes) -> bytes:
        """Preprocess image for tile styling: resize to 512x512, convert to RGB PNG."""
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Convert to RGB if needed
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            # Resize if needed
            if img.size != (512, 512):
                img = img.resize((512, 512), Image.LANCZOS)
            # Save as PNG
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return buffer.getvalue()

    def style_tile(
        self,
        tile_bytes: bytes,
        prompt: str,
        mood_bytes: Optional[bytes] = None,
        temperature: float = 0.5,
    ) -> StyleResult:
        """Generate a styled version of the input tile.

        Args:
            tile_bytes: Input image bytes (any format PIL can read)
            prompt: Style instructions (e.g., "cyberpunk neon night")
            mood_bytes: Optional reference image for mood/color matching
            temperature: Creativity (0.0-1.0), only used by some providers

        Returns:
            StyleResult with generated image bytes

        Raises:
            ValueError: If API key is missing
            RuntimeError: If the API returns an error
        """
        # Preprocess the tile
        processed_tile = self._preprocess_image(tile_bytes)

        # Build the full prompt with system instructions
        full_prompt = f"{self.system_prompt}\n\nNow apply this style:\n{prompt}"

        # Prepare image input(s)
        images = [io.BytesIO(processed_tile)]
        if mood_bytes:
            processed_mood = self._preprocess_image(mood_bytes)
            images.append(io.BytesIO(processed_mood))
            full_prompt += "\n\nUse the color palette and mood from the reference image provided."

        # Call LiteLLM
        try:
            response = litellm.image_edit(
                model=self.model,
                image=images if len(images) > 1 else images[0],
                prompt=full_prompt,
                size="512x512" if self.provider not in ("stability",) else "1024x1024",
                response_format="b64_json",
            )
        except Exception as e:
            raise RuntimeError(f"LiteLLM error ({self.provider}): {e}") from e

        # Extract image bytes from response
        if hasattr(response, "data") and response.data:
            b64_data = response.data[0].b64_json
            if b64_data:
                return StyleResult(
                    image_bytes=base64.b64decode(b64_data),
                    provider=self.provider,
                    model=self.model,
                )

        raise RuntimeError(f"No image returned from {self.provider}")


def list_providers() -> dict[str, str]:
    """Return available providers and their models."""
    return PROVIDER_MODELS.copy()
