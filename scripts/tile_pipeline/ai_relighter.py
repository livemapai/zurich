"""
AI-powered tile relighting using neural models.

Integrates with:
1. IC-Light V2 (via fal.ai) - Specialized neural relighting model
2. Gemini Flash (via Google AI) - Multimodal understanding for image editing

This module provides a unified interface for relighting satellite tiles
with consistent lighting conditions, addressing the limitation of
algorithmic shadow neutralization.

Why AI Relighting?
- Algorithmic approaches can lift shadows but produce washed-out results
- Neural models understand scene semantics and preserve detail
- Can relight based on text prompts ("afternoon sun from southwest")
- Better handling of complex shadow patterns

Architecture:
    Satellite Tile -> AI Model -> Relit Tile
                       |
                  Text Prompt
           ("soft afternoon sun, natural shadows")
"""

import base64
import io
import os
import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image
import requests


class AIModel(Enum):
    """Available AI relighting models."""
    ICLIGHT = "iclight"
    GEMINI = "gemini"


@dataclass
class RelightingResult:
    """Result from an AI relighting operation."""

    image: NDArray[np.uint8]  # RGB (H, W, 3)
    model: AIModel
    prompt: str
    processing_time_ms: int
    cost_estimate: Optional[float] = None
    metadata: Optional[dict] = None


@dataclass
class RelightingPrompt:
    """Structured prompt for relighting operations."""

    # Main lighting description
    lighting: str = "soft afternoon sunlight from the southwest"

    # Shadow behavior
    shadows: str = "natural soft shadows"

    # Quality requirements
    quality: str = "photorealistic, preserve all details"

    # Context for the model
    context: str = "aerial photograph of urban area"

    def to_iclight_prompt(self) -> str:
        """Format prompt for IC-Light model."""
        return f"{self.lighting}, {self.shadows}, {self.quality}"

    def to_gemini_prompt(self) -> str:
        """Format prompt for Gemini model."""
        return (
            f"Edit this {self.context}. "
            f"Relight the scene with {self.lighting}. "
            f"Create {self.shadows}. "
            f"Important: {self.quality}, keep all building edges sharp."
        )


# Pre-defined lighting prompts for different times of day
LIGHTING_PRESETS = {
    "morning_golden": RelightingPrompt(
        lighting="warm golden morning sunlight from the east-southeast",
        shadows="long soft shadows stretching westward",
        quality="warm golden hour tones, photorealistic",
    ),
    "afternoon": RelightingPrompt(
        lighting="bright afternoon sun from the southwest",
        shadows="moderate crisp shadows",
        quality="neutral daylight, sharp details",
    ),
    "evening_golden": RelightingPrompt(
        lighting="warm golden evening sunlight from the west-northwest",
        shadows="long dramatic shadows stretching eastward",
        quality="warm sunset tones, cinematic",
    ),
    "overcast": RelightingPrompt(
        lighting="soft diffuse overcast lighting from above",
        shadows="very subtle ambient shadows only",
        quality="flat even lighting, no harsh shadows",
    ),
    "neutral": RelightingPrompt(
        lighting="neutral uniform lighting from directly above",
        shadows="minimal shadows, almost shadow-free",
        quality="neutral colors, maximum detail visibility",
    ),
}


class BaseRelighter(ABC):
    """Abstract base class for AI relighting providers."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        timeout: int = 120,
    ):
        """Initialize relighter.

        Args:
            cache_dir: Directory for caching results
            timeout: API timeout in seconds
        """
        self.cache_dir = cache_dir
        self.timeout = timeout

        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def relight(
        self,
        image: NDArray[np.uint8],
        prompt: RelightingPrompt,
    ) -> RelightingResult:
        """Relight an image with the given prompt.

        Args:
            image: RGB image array (H, W, 3)
            prompt: Relighting prompt configuration

        Returns:
            RelightingResult with processed image
        """
        pass

    @property
    @abstractmethod
    def model_type(self) -> AIModel:
        """Return the model type."""
        pass

    def _get_cache_key(self, image: NDArray[np.uint8], prompt: str, model_id: str = "") -> str:
        """Generate a cache key for the image+prompt+model combination."""
        # Hash the image data
        img_hash = hashlib.md5(image.tobytes()).hexdigest()[:16]
        # Hash the prompt
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
        # Include model ID if provided (for providers with multiple models)
        model_suffix = f"_{hashlib.md5(model_id.encode()).hexdigest()[:6]}" if model_id else ""
        return f"{self.model_type.value}_{img_hash}_{prompt_hash}{model_suffix}"

    def _load_from_cache(self, cache_key: str) -> Optional[NDArray[np.uint8]]:
        """Load a cached result."""
        if not self.cache_dir:
            return None

        cache_path = self.cache_dir / "ai_relight" / f"{cache_key}.png"
        if cache_path.exists():
            with Image.open(cache_path) as img:
                return np.array(img.convert("RGB"))
        return None

    def _save_to_cache(self, cache_key: str, image: NDArray[np.uint8]) -> None:
        """Save a result to cache."""
        if not self.cache_dir:
            return

        cache_path = self.cache_dir / "ai_relight" / f"{cache_key}.png"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(image).save(cache_path)

    @staticmethod
    def image_to_base64(image: NDArray[np.uint8], format: str = "PNG") -> str:
        """Convert numpy array to base64-encoded image string."""
        img = Image.fromarray(image)
        buffer = io.BytesIO()
        img.save(buffer, format=format)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    @staticmethod
    def base64_to_image(b64_string: str) -> NDArray[np.uint8]:
        """Convert base64-encoded image string to numpy array."""
        image_data = base64.b64decode(b64_string)
        img = Image.open(io.BytesIO(image_data))
        return np.array(img.convert("RGB"))


class ICLightRelighter(BaseRelighter):
    """IC-Light V2 relighting via fal.ai API.

    IC-Light (ICLR 2025) is a state-of-the-art neural relighting model
    that can relight images based on text prompts or background context.

    Cost: ~$0.02-0.05 per image
    API Docs: https://fal.ai/models/fal-ai/iclight-v2

    Requires FAL_KEY environment variable.
    """

    # fal.ai API endpoint for IC-Light V2
    API_URL = "https://queue.fal.run/fal-ai/iclight-v2"

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        timeout: int = 120,
    ):
        """Initialize IC-Light relighter.

        Args:
            api_key: fal.ai API key (defaults to FAL_KEY env var)
            cache_dir: Directory for caching results
            timeout: API timeout in seconds
        """
        super().__init__(cache_dir, timeout)
        self.api_key = api_key or os.environ.get("FAL_KEY")

        if not self.api_key:
            raise ValueError(
                "IC-Light requires fal.ai API key. "
                "Set FAL_KEY environment variable or pass api_key parameter."
            )

    @property
    def model_type(self) -> AIModel:
        return AIModel.ICLIGHT

    def relight(
        self,
        image: NDArray[np.uint8],
        prompt: RelightingPrompt,
    ) -> RelightingResult:
        """Relight image using IC-Light V2.

        Args:
            image: RGB image array (H, W, 3)
            prompt: Relighting prompt configuration

        Returns:
            RelightingResult with processed image
        """
        import time

        prompt_text = prompt.to_iclight_prompt()
        cache_key = self._get_cache_key(image, prompt_text)

        # Check cache
        cached = self._load_from_cache(cache_key)
        if cached is not None:
            return RelightingResult(
                image=cached,
                model=self.model_type,
                prompt=prompt_text,
                processing_time_ms=0,
                metadata={"cached": True},
            )

        start_time = time.time()

        # Prepare image as base64
        image_b64 = self.image_to_base64(image)

        # Call fal.ai API
        headers = {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "prompt": prompt_text,
            "image_url": f"data:image/png;base64,{image_b64}",
            # IC-Light V2 specific options
            "light_source": "Left Light",  # Can be: Left, Right, Top, Bottom
            "num_inference_steps": 25,
            "guidance_scale": 2.0,
        }

        response = requests.post(
            self.API_URL,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()

        result = response.json()

        # Extract the relit image
        if "images" in result and len(result["images"]) > 0:
            # fal.ai returns image URL or base64
            image_output = result["images"][0]
            if image_output.startswith("data:"):
                # Base64 encoded
                b64_data = image_output.split(",")[1]
                relit_image = self.base64_to_image(b64_data)
            else:
                # URL - fetch the image
                img_response = requests.get(image_output, timeout=30)
                img_response.raise_for_status()
                relit_image = np.array(
                    Image.open(io.BytesIO(img_response.content)).convert("RGB")
                )
        else:
            raise ValueError("No image in IC-Light response")

        # Resize to match input if needed
        if relit_image.shape[:2] != image.shape[:2]:
            pil_img = Image.fromarray(relit_image)
            pil_img = pil_img.resize((image.shape[1], image.shape[0]), Image.LANCZOS)
            relit_image = np.array(pil_img)

        processing_time = int((time.time() - start_time) * 1000)

        # Cache result
        self._save_to_cache(cache_key, relit_image)

        return RelightingResult(
            image=relit_image,
            model=self.model_type,
            prompt=prompt_text,
            processing_time_ms=processing_time,
            cost_estimate=0.03,  # Approximate cost per image
            metadata=result,
        )


class GeminiRelighter(BaseRelighter):
    """Google Gemini relighting via Google AI API.

    Uses Gemini's multimodal understanding to edit/relight images.
    Can understand context ("this is an aerial photograph") and apply
    intelligent edits.

    Available models:
    - gemini-2.5-flash-image: Latest image-capable model
    - nano-banana-pro-preview: Experimental image generation

    Cost: Free tier (1,500 requests/day) or very low cost
    API Docs: https://ai.google.dev/gemini-api/docs/image-generation

    Requires GOOGLE_API_KEY or GEMINI_API_KEY environment variable.
    """

    # Google AI Studio base endpoint
    API_BASE = "https://generativelanguage.googleapis.com/v1beta"

    # Default model for image generation
    DEFAULT_MODEL = "models/gemini-2.5-flash-image"

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        timeout: int = 120,
        model: Optional[str] = None,
    ):
        """Initialize Gemini relighter.

        Args:
            api_key: Google AI API key (defaults to GOOGLE_API_KEY or GEMINI_API_KEY)
            cache_dir: Directory for caching results
            timeout: API timeout in seconds
            model: Model to use (default: gemini-2.5-flash-image)
        """
        super().__init__(cache_dir, timeout)
        self.api_key = (
            api_key
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
        )
        self.model = model or self.DEFAULT_MODEL

        if not self.api_key:
            raise ValueError(
                "Gemini requires Google AI API key. "
                "Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable."
            )

    @property
    def model_type(self) -> AIModel:
        return AIModel.GEMINI

    def relight(
        self,
        image: NDArray[np.uint8],
        prompt: RelightingPrompt,
    ) -> RelightingResult:
        """Relight image using Gemini.

        Args:
            image: RGB image array (H, W, 3)
            prompt: Relighting prompt configuration

        Returns:
            RelightingResult with processed image
        """
        import time

        prompt_text = prompt.to_gemini_prompt()
        cache_key = self._get_cache_key(image, prompt_text, model_id=self.model)

        # Check cache
        cached = self._load_from_cache(cache_key)
        if cached is not None:
            return RelightingResult(
                image=cached,
                model=self.model_type,
                prompt=prompt_text,
                processing_time_ms=0,
                metadata={"cached": True},
            )

        start_time = time.time()

        # Prepare image as base64
        image_b64 = self.image_to_base64(image, format="JPEG")

        # Build API request
        url = f"{self.API_BASE}/{self.model}:generateContent?key={self.api_key}"

        headers = {
            "Content-Type": "application/json",
        }

        # Gemini multimodal request format
        # For image generation, we ask the model to generate a modified version
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_b64,
                            }
                        },
                        {
                            "text": prompt_text,
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["image", "text"],
            }
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )

        # Handle errors with more detail
        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "No details"
            raise ValueError(
                f"Gemini API error {response.status_code}: {error_detail}"
            )

        result = response.json()

        # Extract image from response
        relit_image = None
        text_response = None

        if "candidates" in result:
            for candidate in result["candidates"]:
                if "content" in candidate and "parts" in candidate["content"]:
                    for part in candidate["content"]["parts"]:
                        if "inlineData" in part:
                            b64_data = part["inlineData"]["data"]
                            relit_image = self.base64_to_image(b64_data)
                        elif "text" in part:
                            text_response = part["text"]

        if relit_image is None:
            # Model might not support image generation
            error_msg = (
                f"Gemini ({self.model}) did not return an image. "
                "Try a different model like 'models/gemini-2.5-flash-image'."
            )
            if text_response:
                error_msg += f"\nModel response: {text_response[:200]}"
            raise ValueError(error_msg)

        # Resize to match input if needed
        if relit_image.shape[:2] != image.shape[:2]:
            pil_img = Image.fromarray(relit_image)
            pil_img = pil_img.resize((image.shape[1], image.shape[0]), Image.LANCZOS)
            relit_image = np.array(pil_img)

        processing_time = int((time.time() - start_time) * 1000)

        # Cache result
        self._save_to_cache(cache_key, relit_image)

        return RelightingResult(
            image=relit_image,
            model=self.model_type,
            prompt=prompt_text,
            processing_time_ms=processing_time,
            cost_estimate=0.0,  # Free tier
            metadata=result,
        )


def get_relighter(
    model: AIModel,
    cache_dir: Optional[Path] = None,
    api_key: Optional[str] = None,
) -> BaseRelighter:
    """Factory function to get a relighter instance.

    Args:
        model: The AI model to use
        cache_dir: Directory for caching results
        api_key: Optional API key (overrides env vars)

    Returns:
        Configured relighter instance
    """
    if model == AIModel.ICLIGHT:
        return ICLightRelighter(api_key=api_key, cache_dir=cache_dir)
    elif model == AIModel.GEMINI:
        return GeminiRelighter(api_key=api_key, cache_dir=cache_dir)
    else:
        raise ValueError(f"Unknown model: {model}")


def relight_tile(
    image: NDArray[np.uint8],
    preset: str = "afternoon",
    model: AIModel = AIModel.GEMINI,
    cache_dir: Optional[Path] = None,
) -> RelightingResult:
    """Convenience function to relight a satellite tile.

    Args:
        image: RGB image array (H, W, 3)
        preset: Lighting preset name (see LIGHTING_PRESETS)
        model: AI model to use
        cache_dir: Optional cache directory

    Returns:
        RelightingResult with processed image
    """
    if preset not in LIGHTING_PRESETS:
        raise ValueError(
            f"Unknown preset '{preset}'. "
            f"Available presets: {list(LIGHTING_PRESETS.keys())}"
        )

    prompt = LIGHTING_PRESETS[preset]
    relighter = get_relighter(model, cache_dir=cache_dir)

    return relighter.relight(image, prompt)


def check_api_availability() -> dict[str, bool]:
    """Check which AI APIs are available.

    Returns:
        Dictionary of model name -> availability
    """
    availability = {}

    # Check IC-Light (fal.ai)
    fal_key = os.environ.get("FAL_KEY")
    availability["iclight"] = bool(fal_key)

    # Check Gemini
    gemini_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    availability["gemini"] = bool(gemini_key)

    return availability


def print_setup_instructions() -> None:
    """Print instructions for setting up API keys."""
    availability = check_api_availability()

    print("\n" + "=" * 60)
    print("AI Relighting API Setup")
    print("=" * 60)

    print("\n1. IC-Light V2 (via fal.ai)")
    print("-" * 40)
    if availability["iclight"]:
        print("   Status: CONFIGURED")
    else:
        print("   Status: NOT CONFIGURED")
        print("   ")
        print("   To enable:")
        print("   1. Sign up at https://fal.ai")
        print("   2. Get your API key from dashboard")
        print("   3. Set environment variable:")
        print("      export FAL_KEY='your-api-key'")
        print("   ")
        print("   Cost: ~$0.02-0.05 per image")

    print("\n2. Gemini Flash (via Google AI)")
    print("-" * 40)
    if availability["gemini"]:
        print("   Status: CONFIGURED")
    else:
        print("   Status: NOT CONFIGURED")
        print("   ")
        print("   To enable:")
        print("   1. Visit https://aistudio.google.com/apikey")
        print("   2. Create an API key")
        print("   3. Set environment variable:")
        print("      export GOOGLE_API_KEY='your-api-key'")
        print("   ")
        print("   Cost: Free tier (1,500 requests/day)")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    print_setup_instructions()
