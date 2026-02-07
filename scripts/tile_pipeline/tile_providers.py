#!/usr/bin/env python3
"""
AI Provider abstraction for tile styling.

Supports multiple image generation providers:
- gemini: Google Gemini 2.5 Flash Image (direct API)
- openai: OpenAI GPT Image 1 / gpt-image-1
"""

import base64
import io
import os
from dataclasses import dataclass
from typing import Optional

import requests
from PIL import Image

# Provider model mapping
PROVIDER_MODELS = {
    "gemini": "gemini-2.5-flash-image",
    "openai": "gpt-image-1",
}


@dataclass
class StyleResult:
    """Result from styling a tile."""
    image_bytes: bytes
    provider: str
    model: str


def list_providers() -> list[str]:
    """List available providers."""
    return list(PROVIDER_MODELS.keys())


class TileStyler:
    """Unified interface for tile styling with multiple AI providers."""

    SYSTEM_PROMPT = """You are a cinematic map tile artist. You will receive an image of a 3D-rendered
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

    def __init__(self, provider: str = "gemini", api_key: Optional[str] = None):
        self.provider = provider
        if provider == "gemini":
            self.api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        elif provider == "openai":
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        else:
            raise ValueError(f"Unknown provider: {provider}")

        if not self.api_key:
            raise ValueError(f"API key required for {provider}")

    def style_tile(
        self,
        tile_bytes: bytes,
        prompt: str,
        mood_bytes: Optional[bytes] = None,
        temperature: float = 0.5,
    ) -> StyleResult:
        """Style a tile using the configured provider."""
        if self.provider == "gemini":
            return self._style_with_gemini(tile_bytes, prompt, mood_bytes, temperature)
        elif self.provider == "openai":
            return self._style_with_openai(tile_bytes, prompt, mood_bytes)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _style_with_gemini(
        self,
        tile_bytes: bytes,
        prompt: str,
        mood_bytes: Optional[bytes],
        temperature: float,
    ) -> StyleResult:
        """Style using Gemini direct API."""
        API_BASE = "https://generativelanguage.googleapis.com/v1beta"
        MODEL = "models/gemini-2.5-flash-image"

        tile_b64 = base64.b64encode(tile_bytes).decode("utf-8")

        parts = [{"inline_data": {"mime_type": "image/png", "data": tile_b64}}]

        user_prompt = f"Now apply this style:\n{prompt}"
        if mood_bytes:
            mood_b64 = base64.b64encode(mood_bytes).decode("utf-8")
            parts.append({"inline_data": {"mime_type": "image/png", "data": mood_b64}})
            user_prompt += "\n\nUse the color palette and mood from the reference image provided."

        full_prompt = f"{self.SYSTEM_PROMPT}\n\n{user_prompt}"
        parts.append({"text": full_prompt})

        url = f"{API_BASE}/{MODEL}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseModalities": ["image", "text"],
                "temperature": temperature,
            },
        }

        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=180,
        )

        if response.status_code != 200:
            raise ValueError(f"Gemini API error {response.status_code}: {response.text[:500]}")

        result = response.json()

        if "candidates" in result:
            for candidate in result["candidates"]:
                if "content" in candidate and "parts" in candidate["content"]:
                    for part in candidate["content"]["parts"]:
                        if "inlineData" in part:
                            image_bytes = base64.b64decode(part["inlineData"]["data"])
                            return StyleResult(
                                image_bytes=image_bytes,
                                provider="gemini",
                                model="gemini-2.5-flash-image",
                            )

        raise ValueError("Gemini did not return an image")

    def _style_with_openai(
        self,
        tile_bytes: bytes,
        prompt: str,
        mood_bytes: Optional[bytes],
    ) -> StyleResult:
        """Style using OpenAI GPT Image API (image edit)."""
        import openai
        import tempfile
        import os as os_module

        client = openai.OpenAI(api_key=self.api_key)

        # Prepare image for OpenAI (needs to be PNG, RGBA for mask support)
        img = Image.open(io.BytesIO(tile_bytes))
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        if img.size != (512, 512):
            img = img.resize((512, 512), Image.LANCZOS)

        # Save to a temp file with proper extension (OpenAI needs filename)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            img.save(tmp_file, format="PNG")
            tmp_path = tmp_file.name

        # Build the prompt
        full_prompt = f"""{self.SYSTEM_PROMPT}

Apply this artistic style to the map tile:
{prompt}

IMPORTANT: Keep all geometry exactly the same. Only change colors, textures, and artistic style."""

        try:
            # Use the images.edit endpoint for style transfer
            # OpenAI requires a file with proper extension for mime type detection
            # Note: gpt-image-1 only supports 1024x1024, 1024x1536, 1536x1024, and 'auto'
            with open(tmp_path, "rb") as img_file:
                response = client.images.edit(
                    model="gpt-image-1",
                    image=img_file,
                    prompt=full_prompt,
                    size="1024x1024",  # Generate at 1024 then resize
                )

            # Get the result URL and download
            if response.data and len(response.data) > 0:
                if hasattr(response.data[0], 'b64_json') and response.data[0].b64_json:
                    raw_bytes = base64.b64decode(response.data[0].b64_json)
                elif hasattr(response.data[0], 'url') and response.data[0].url:
                    # Download from URL
                    img_response = requests.get(response.data[0].url, timeout=60)
                    raw_bytes = img_response.content
                else:
                    raise ValueError("OpenAI response has no image data")

                # Resize from 1024x1024 to 512x512 for tile consistency
                result_img = Image.open(io.BytesIO(raw_bytes))
                result_img = result_img.resize((512, 512), Image.LANCZOS)

                # Convert back to bytes
                output_buffer = io.BytesIO()
                result_img.save(output_buffer, format="PNG")
                image_bytes = output_buffer.getvalue()

                return StyleResult(
                    image_bytes=image_bytes,
                    provider="openai",
                    model="gpt-image-1",
                )

            raise ValueError("OpenAI did not return an image")
        finally:
            # Clean up temp file
            os_module.unlink(tmp_path)
