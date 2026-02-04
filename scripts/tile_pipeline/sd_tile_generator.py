"""
Stable Diffusion tile generator using Replicate API.

Supports two modes:
1. ControlNet Depth (legacy): Generates from depth maps - prone to hallucination
2. Satellite img2img (recommended): Transforms satellite imagery - preserves detail

Key insight: ControlNet Depth is a *generative* model that creates new content,
while img2img is a *transformative* model that modifies existing pixels.
For style transfer of map tiles, img2img with low prompt_strength (0.3-0.5)
produces much better results because:
- Real satellite textures are preserved (no hallucination)
- Structure inherently maintained from source image
- Style changes colors/mood without inventing new details

Architecture (img2img - recommended):
    Satellite Tile → SDXL img2img (strength=0.4) → Styled Tile

Architecture (ControlNet - legacy):
    Blender RGB + Depth Map → SD + ControlNet Depth → Stylized Tile

Usage:
    from .sd_tile_generator import SatelliteStyleTransfer, IMG2IMG_STYLES

    # Recommended: img2img on satellite tiles
    transfer = SatelliteStyleTransfer()
    result = transfer.transform(
        satellite_image=satellite_rgb,
        style="winter",
        seed=42,
    )

    # Legacy: ControlNet Depth (not recommended)
    from .sd_tile_generator import SDTileGenerator, SD_STYLES
    generator = SDTileGenerator()
    result = generator.generate(...)

Requires:
    - REPLICATE_API_TOKEN environment variable
    - replicate Python package (pip install replicate)
"""

import base64
import hashlib
import io
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from numpy.typing import NDArray
from PIL import Image


# =============================================================================
# SD STYLE PRESETS
# =============================================================================


@dataclass
class SDStylePreset:
    """Stable Diffusion style preset optimized for ControlNet Depth (LEGACY).

    NOTE: For new development, use Img2ImgStylePreset instead.
    ControlNet Depth tends to hallucinate detail that doesn't exist in the source.

    Unlike Gemini prompts, SD prompts use keyword-based formatting
    with specific weighting syntax for better control.

    Key differences from Gemini StylePreset:
    - Uses (keyword:weight) syntax for emphasis
    - Negative prompt to exclude unwanted elements
    - Fixed seed per style for deterministic output
    - ControlNet conditioning strength setting
    """

    name: str
    description: str = ""

    # Positive prompt (what we want)
    prompt: str = ""

    # Negative prompt (what to avoid)
    negative_prompt: str = ""

    # Fixed seed for consistency (0 = random)
    seed: int = 42

    # ControlNet Depth conditioning strength (0.0-2.0)
    # Higher = more faithful to depth map geometry
    controlnet_conditioning_scale: float = 1.0

    # Inference steps (20-50 typical)
    num_inference_steps: int = 30

    # Guidance scale (CFG) - how closely to follow prompt
    guidance_scale: float = 7.5

    # Scheduler type
    scheduler: str = "K_EULER_ANCESTRAL"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "seed": self.seed,
            "controlnet_conditioning_scale": self.controlnet_conditioning_scale,
            "num_inference_steps": self.num_inference_steps,
            "guidance_scale": self.guidance_scale,
            "scheduler": self.scheduler,
        }


# Predefined SD styles with fixed seeds for reproducibility
SD_STYLES: dict[str, SDStylePreset] = {
    "winter": SDStylePreset(
        name="SD Winter",
        description="Snow-covered cityscape with ControlNet depth consistency",
        prompt=(
            "(winter scene:1.4), fresh white snow covering rooftops and streets, "
            "(snowy cityscape:1.3), frosted trees, ice blue shadows, "
            "cold afternoon light, muted colors, pristine snow, "
            "top-down aerial view, orthographic projection, map tile, "
            "(high detail:1.2), sharp focus, professional photography"
        ),
        negative_prompt=(
            "perspective, vanishing point, horizon, people, cars, text, "
            "watermark, logo, signature, blurry, low quality, distorted, "
            "warped buildings, incorrect angles, tilted view"
        ),
        seed=42,
        controlnet_conditioning_scale=1.2,  # High for strict geometry
        num_inference_steps=30,
        guidance_scale=7.5,
    ),
    "cyberpunk": SDStylePreset(
        name="SD Cyberpunk",
        description="Neon-lit night city with consistent geometry",
        prompt=(
            "(cyberpunk night city:1.5), neon lights, (cyan and magenta glow:1.3), "
            "wet streets with reflections, glowing windows, "
            "(futuristic dystopian:1.2), dark atmosphere, "
            "top-down aerial view, orthographic projection, map tile, "
            "(high detail:1.2), sharp neon edges, professional"
        ),
        negative_prompt=(
            "perspective, vanishing point, horizon, people, text, "
            "watermark, logo, daytime, bright sky, sun, blurry, "
            "low quality, distorted geometry, tilted view"
        ),
        seed=42,
        controlnet_conditioning_scale=1.1,
        num_inference_steps=35,  # More steps for complex lighting
        guidance_scale=8.0,  # Higher CFG for stronger neon colors
    ),
    "autumn": SDStylePreset(
        name="SD Autumn",
        description="Fall foliage with warm golden light",
        prompt=(
            "(autumn foliage:1.4), fall colors, (orange and red trees:1.3), "
            "golden afternoon light, warm tones, fallen leaves, "
            "(seasonal change:1.2), rich saturated colors, "
            "top-down aerial view, orthographic projection, map tile, "
            "(high detail:1.2), sharp focus"
        ),
        negative_prompt=(
            "perspective, vanishing point, horizon, people, cars, text, "
            "watermark, summer, green trees, winter, snow, blurry, "
            "low quality, distorted, tilted view"
        ),
        seed=42,
        controlnet_conditioning_scale=1.0,
        num_inference_steps=30,
        guidance_scale=7.5,
    ),
    "watercolor": SDStylePreset(
        name="SD Watercolor",
        description="Artistic watercolor painting style",
        prompt=(
            "(watercolor painting:1.5), (artistic style:1.3), soft edges, "
            "visible brush strokes, paint bleeding, paper texture, "
            "(muted pastel colors:1.2), artistic interpretation, "
            "top-down aerial view, map illustration, "
            "(hand-painted:1.2), traditional art"
        ),
        negative_prompt=(
            "perspective, vanishing point, horizon, photorealistic, "
            "sharp edges, digital art, 3D render, text, watermark, "
            "low quality, blurry, tilted view"
        ),
        seed=42,
        controlnet_conditioning_scale=0.9,  # Slightly lower for artistic freedom
        num_inference_steps=30,
        guidance_scale=7.0,
    ),
    "blueprint": SDStylePreset(
        name="SD Blueprint",
        description="Technical architectural blueprint style",
        prompt=(
            "(architectural blueprint:1.5), white lines on dark blue background, "
            "(technical drawing:1.4), building outlines, floor plan, "
            "no textures, clean lines, engineering style, "
            "top-down view, orthographic projection, "
            "(precise:1.2), professional CAD drawing"
        ),
        negative_prompt=(
            "perspective, colors, textures, photorealistic, "
            "shading, gradients, people, text labels, "
            "low quality, blurry, tilted view"
        ),
        seed=42,
        controlnet_conditioning_scale=1.3,  # Very high for precise lines
        num_inference_steps=25,  # Fewer steps for simpler output
        guidance_scale=9.0,  # High CFG for strict style adherence
    ),
    "retro": SDStylePreset(
        name="SD Retro",
        description="80s vaporwave aesthetic with pink/cyan gradients",
        prompt=(
            "(80s retro vaporwave:1.5), (pink and cyan gradient:1.4), "
            "synthwave aesthetic, chrome reflections, neon grid, "
            "(sunset colors:1.2), geometric patterns, "
            "top-down aerial view, orthographic projection, map tile, "
            "(high detail:1.2), sharp focus"
        ),
        negative_prompt=(
            "perspective, vanishing point, horizon, realistic, "
            "text, watermark, modern, minimalist, "
            "low quality, blurry, tilted view"
        ),
        seed=42,
        controlnet_conditioning_scale=1.0,
        num_inference_steps=30,
        guidance_scale=8.0,
    ),
}


def get_sd_style(name: str) -> SDStylePreset:
    """Get an SD style preset by name.

    Args:
        name: Style name (case-insensitive)

    Returns:
        SDStylePreset instance

    Raises:
        ValueError: If style name is not found
    """
    name_lower = name.lower()
    if name_lower not in SD_STYLES:
        available = ", ".join(sorted(SD_STYLES.keys()))
        raise ValueError(f"Unknown SD style '{name}'. Available: {available}")
    return SD_STYLES[name_lower]


def list_sd_styles() -> dict[str, str]:
    """List all available SD styles with descriptions.

    Returns:
        Dict mapping style name to description
    """
    return {name: style.description for name, style in SD_STYLES.items()}


# =============================================================================
# IMG2IMG STYLE PRESETS (RECOMMENDED FOR SATELLITE TILES)
# =============================================================================


@dataclass
class Img2ImgStylePreset:
    """Style preset for InstructPix2Pix transformation of satellite tiles.

    InstructPix2Pix is specifically designed for image editing while preserving
    structure. It uses instruction-based prompts ("make it winter") rather than
    descriptive prompts, and has an image_guidance_scale parameter that controls
    how much to preserve from the original.

    Key parameters:
    - image_guidance_scale: How much to preserve original (higher = more faithful)
      - 1.2-1.5: More stylization, some structure loss
      - 1.5-1.8: Good balance (RECOMMENDED)
      - 1.8-2.2: Subtle changes, excellent structure
    - guidance_scale: How closely to follow the instruction
    """

    name: str
    description: str = ""

    # Instruction prompt (e.g., "make it winter with snow")
    prompt: str = ""

    # How much to preserve original image (higher = more faithful to original)
    # Recommended: 1.5-2.0 for map tiles
    image_guidance_scale: float = 1.8

    # Fixed seed for deterministic output
    seed: int = 42

    # Inference steps (30-50 typical)
    num_inference_steps: int = 50

    # Guidance scale (CFG) - how closely to follow instruction
    guidance_scale: float = 7.5

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "prompt": self.prompt,
            "image_guidance_scale": self.image_guidance_scale,
            "seed": self.seed,
            "num_inference_steps": self.num_inference_steps,
            "guidance_scale": self.guidance_scale,
        }


# InstructPix2Pix styles with instruction-based prompts for satellite tile transformation
# These use "make it X" style prompts which InstructPix2Pix understands best
IMG2IMG_STYLES: dict[str, Img2ImgStylePreset] = {
    "winter": Img2ImgStylePreset(
        name="Winter",
        description="Snow-covered cityscape with cold blue tones",
        prompt="make it a winter scene with snow on rooftops and streets, cold blue tones",
        image_guidance_scale=1.8,  # Good structure preservation
        seed=42,
        num_inference_steps=50,
        guidance_scale=7.5,
    ),
    "cyberpunk": Img2ImgStylePreset(
        name="Cyberpunk",
        description="Neon-lit night city with cyan and magenta glow",
        prompt="make it nighttime with neon lights, cyberpunk style, cyan and magenta glow",
        image_guidance_scale=1.8,
        seed=42,
        num_inference_steps=50,
        guidance_scale=7.5,
    ),
    "autumn": Img2ImgStylePreset(
        name="Autumn",
        description="Fall foliage with warm golden tones",
        prompt="make it autumn with orange and red fall foliage, warm golden light",
        image_guidance_scale=1.8,
        seed=42,
        num_inference_steps=50,
        guidance_scale=7.5,
    ),
    "night": Img2ImgStylePreset(
        name="Night",
        description="Nighttime with street lights and building lights",
        prompt="make it nighttime with street lights glowing and lit windows",
        image_guidance_scale=1.8,
        seed=42,
        num_inference_steps=50,
        guidance_scale=7.5,
    ),
    "golden-hour": Img2ImgStylePreset(
        name="Golden Hour",
        description="Warm sunset lighting with long shadows",
        prompt="make it golden hour sunset lighting with warm orange tones",
        image_guidance_scale=1.8,
        seed=42,
        num_inference_steps=50,
        guidance_scale=7.5,
    ),
    "retro": Img2ImgStylePreset(
        name="Retro",
        description="80s vaporwave aesthetic with pink/cyan gradients",
        prompt="make it 80s retro vaporwave style with pink and cyan colors",
        image_guidance_scale=1.6,  # Slightly more stylization for artistic effect
        seed=42,
        num_inference_steps=50,
        guidance_scale=8.0,
    ),
    "noir": Img2ImgStylePreset(
        name="Noir",
        description="Black and white film noir style",
        prompt="make it black and white film noir style with dramatic shadows",
        image_guidance_scale=1.8,
        seed=42,
        num_inference_steps=50,
        guidance_scale=7.5,
    ),
    "tropical": Img2ImgStylePreset(
        name="Tropical",
        description="Lush green tropical vegetation",
        prompt="make it tropical with lush green vegetation and vibrant colors",
        image_guidance_scale=1.8,
        seed=42,
        num_inference_steps=50,
        guidance_scale=7.5,
    ),
}


def get_img2img_style(name: str) -> Img2ImgStylePreset:
    """Get an img2img style preset by name.

    Args:
        name: Style name (case-insensitive)

    Returns:
        Img2ImgStylePreset instance

    Raises:
        ValueError: If style name is not found
    """
    name_lower = name.lower()
    if name_lower not in IMG2IMG_STYLES:
        available = ", ".join(sorted(IMG2IMG_STYLES.keys()))
        raise ValueError(f"Unknown img2img style '{name}'. Available: {available}")
    return IMG2IMG_STYLES[name_lower]


def list_img2img_styles() -> dict[str, str]:
    """List all available img2img styles with descriptions.

    Returns:
        Dict mapping style name to description
    """
    return {name: style.description for name, style in IMG2IMG_STYLES.items()}


# =============================================================================
# SATELLITE STYLE TRANSFER (RECOMMENDED)
# =============================================================================


@dataclass
class SatelliteStyleResult:
    """Result from a satellite tile style transfer operation."""

    image: NDArray[np.uint8]  # RGB (H, W, 3)
    style: str
    tile_coord: str
    processing_time_ms: int
    cached: bool = False
    seed: int = 0
    image_guidance_scale: float = 0.0
    model: str = "instruct-pix2pix"
    metadata: Optional[dict] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "style": self.style,
            "tile_coord": self.tile_coord,
            "processing_time_ms": self.processing_time_ms,
            "cached": self.cached,
            "seed": self.seed,
            "image_guidance_scale": self.image_guidance_scale,
            "model": self.model,
            "image_shape": list(self.image.shape),
        }


class SatelliteStyleTransfer:
    """Transforms satellite tiles using InstructPix2Pix for structure-preserving style transfer.

    This is the RECOMMENDED approach for stylizing map tiles because:
    1. InstructPix2Pix is specifically designed for image EDITING, not generation
    2. Uses instruction prompts ("make it winter") which preserve structure
    3. image_guidance_scale parameter controls structure preservation (higher = more faithful)
    4. Deterministic seeds ensure consistency across tiles

    Unlike SDXL img2img which shifts pixels, InstructPix2Pix maintains
    geographic accuracy while applying style transformations.

    Example:
        transfer = SatelliteStyleTransfer()
        result = transfer.transform(
            satellite_image=np.array(Image.open("satellite.png")),
            style="winter",
            tile_coord="16/34322/22950",
            seed=42,
        )
    """

    # InstructPix2Pix - designed for image editing with structure preservation
    INSTRUCT_PIX2PIX_MODEL = "timothybrooks/instruct-pix2pix:30c1d0b916a6f8efce20493f5d61ee27491ab2a60437c13c588468b9810ec23f"

    def __init__(
        self,
        api_token: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        timeout: int = 300,
    ):
        """Initialize satellite style transfer.

        Args:
            api_token: Replicate API token (defaults to REPLICATE_API_TOKEN env var)
            cache_dir: Directory for caching results
            timeout: API timeout in seconds
        """
        self.api_token = api_token or os.environ.get("REPLICATE_API_TOKEN")
        self.cache_dir = cache_dir or Path(".cache")
        self.timeout = timeout

        if not self.api_token:
            raise ValueError(
                "Satellite Style Transfer requires Replicate API token. "
                "Set REPLICATE_API_TOKEN environment variable. "
                "Get one at: https://replicate.com/account/api-tokens"
            )

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Lazy import replicate
        self._replicate = None

    @property
    def replicate(self):
        """Lazy import of replicate module."""
        if self._replicate is None:
            try:
                import replicate
                self._replicate = replicate
            except ImportError:
                raise ImportError(
                    "Replicate package not installed. "
                    "Install with: pip install replicate"
                )
        return self._replicate

    def _get_cache_key(self, tile_coord: str, style: str, seed: int) -> str:
        """Generate a cache key for tile+style+seed combination."""
        combined = f"{tile_coord}_{style}_pix2pix_{seed}"
        return hashlib.md5(combined.encode()).hexdigest()[:16]

    def _cache_path(self, cache_key: str) -> Path:
        """Get cache file path."""
        return self.cache_dir / "satellite_styled" / f"{cache_key}.png"

    def _load_from_cache(self, cache_key: str) -> Optional[NDArray[np.uint8]]:
        """Load a cached result."""
        cache_path = self._cache_path(cache_key)
        if cache_path.exists():
            with Image.open(cache_path) as img:
                return np.array(img.convert("RGB"))
        return None

    def _save_to_cache(self, cache_key: str, image: NDArray[np.uint8]) -> None:
        """Save a result to cache."""
        cache_path = self._cache_path(cache_key)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(image).save(cache_path)

    @staticmethod
    def image_to_data_uri(image: NDArray[np.uint8], format: str = "PNG") -> str:
        """Convert numpy array to data URI string for Replicate."""
        img = Image.fromarray(image)
        buffer = io.BytesIO()
        img.save(buffer, format=format)
        b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        mime = f"image/{format.lower()}"
        return f"data:{mime};base64,{b64}"

    @staticmethod
    def url_to_image(url: str) -> NDArray[np.uint8]:
        """Download image from URL and convert to numpy array."""
        import requests
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        img = Image.open(io.BytesIO(response.content))
        return np.array(img.convert("RGB"))

    def transform(
        self,
        satellite_image: NDArray[np.uint8],
        style: str | Img2ImgStylePreset,
        tile_coord: Optional[str] = None,
        seed: Optional[int] = None,
        image_guidance_scale: Optional[float] = None,
        use_cache: bool = True,
    ) -> SatelliteStyleResult:
        """Transform a satellite tile using InstructPix2Pix style transfer.

        Args:
            satellite_image: Satellite RGB image (H, W, 3)
            style: Style name or Img2ImgStylePreset object
            tile_coord: Tile coordinate string for caching (e.g., "16/34322/22950")
            seed: Random seed (None = use style's default seed)
            image_guidance_scale: Override style's image_guidance_scale (higher = more faithful)
            use_cache: Whether to use cached results

        Returns:
            SatelliteStyleResult with transformed image
        """
        # Resolve style
        if isinstance(style, str):
            style_preset = get_img2img_style(style)
            style_name = style
        else:
            style_preset = style
            style_name = style.name.lower().replace(" ", "-")

        tile_coord = tile_coord or "unknown"
        actual_seed = seed if seed is not None else style_preset.seed
        actual_image_guidance = image_guidance_scale if image_guidance_scale is not None else style_preset.image_guidance_scale

        # Check cache
        if use_cache:
            cache_key = self._get_cache_key(tile_coord, style_name, actual_seed)
            cached = self._load_from_cache(cache_key)
            if cached is not None:
                return SatelliteStyleResult(
                    image=cached,
                    style=style_name,
                    tile_coord=tile_coord,
                    processing_time_ms=0,
                    cached=True,
                    seed=actual_seed,
                    image_guidance_scale=actual_image_guidance,
                    model="instruct-pix2pix",
                    metadata={"from_cache": True},
                )

        start_time = time.time()

        # Ensure image is 512x512
        if satellite_image.shape[:2] != (512, 512):
            pil_img = Image.fromarray(satellite_image)
            pil_img = pil_img.resize((512, 512), Image.LANCZOS)
            satellite_image = np.array(pil_img)

        # Convert to data URI for Replicate
        image_uri = self.image_to_data_uri(satellite_image, format="PNG")

        # Run InstructPix2Pix via Replicate
        try:
            output = self.replicate.run(
                self.INSTRUCT_PIX2PIX_MODEL,
                input={
                    "image": image_uri,
                    "prompt": style_preset.prompt,
                    "num_inference_steps": style_preset.num_inference_steps,
                    "guidance_scale": style_preset.guidance_scale,
                    "image_guidance_scale": actual_image_guidance,
                    "seed": actual_seed,
                },
            )

            # Handle output - Replicate returns URL(s)
            if isinstance(output, list):
                output_url = output[0]
            else:
                output_url = output

            # Download generated image
            generated_image = self.url_to_image(output_url)

        except Exception as e:
            raise ValueError(f"Replicate API error: {e}")

        # Ensure output is 512x512
        if generated_image.shape[:2] != (512, 512):
            pil_img = Image.fromarray(generated_image)
            pil_img = pil_img.resize((512, 512), Image.LANCZOS)
            generated_image = np.array(pil_img)

        processing_time = int((time.time() - start_time) * 1000)

        # Cache result
        if use_cache:
            cache_key = self._get_cache_key(tile_coord, style_name, actual_seed)
            self._save_to_cache(cache_key, generated_image)

        return SatelliteStyleResult(
            image=generated_image,
            style=style_name,
            tile_coord=tile_coord,
            processing_time_ms=processing_time,
            cached=False,
            seed=actual_seed,
            image_guidance_scale=actual_image_guidance,
            model="instruct-pix2pix",
            metadata={
                "prompt": style_preset.prompt,
                "image_guidance_scale": actual_image_guidance,
                "steps": style_preset.num_inference_steps,
                "guidance": style_preset.guidance_scale,
            },
        )


# =============================================================================
# SD TILE GENERATOR (LEGACY - CONTROLNET DEPTH)
# =============================================================================


@dataclass
class SDGenerationResult:
    """Result from an SD tile generation operation."""

    image: NDArray[np.uint8]  # RGB (H, W, 3)
    style: str
    tile_coord: str
    processing_time_ms: int
    cached: bool = False
    seed: int = 0
    model: str = ""
    metadata: Optional[dict] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "style": self.style,
            "tile_coord": self.tile_coord,
            "processing_time_ms": self.processing_time_ms,
            "cached": self.cached,
            "seed": self.seed,
            "model": self.model,
            "image_shape": list(self.image.shape),
        }


class SDTileGenerator:
    """Generates stylized tiles using Stable Diffusion + ControlNet via Replicate.

    Uses ControlNet Depth to maintain geometric consistency while applying
    style transformations. Fixed seeds ensure reproducible output.

    Key features:
    - Deterministic output with fixed seeds
    - ControlNet Depth locks building positions and heights
    - Lower latency and cost than Gemini
    - Better control over style parameters

    Example:
        generator = SDTileGenerator()
        result = generator.generate(
            blender_image=np.array(Image.open("tile.png")),
            depth_map=np.array(Image.open("depth.png")),
            style="cyberpunk",
            seed=42,
        )
    """

    # Replicate model IDs (verified February 2026)
    # SDXL + ControlNet Depth for style transfer with geometry preservation
    CONTROLNET_MODEL = "lucataco/sdxl-controlnet-depth:465fb41789dc2203a9d7158be11d1d2570606a039c65e0e236fd329b5eecb10c"

    # Depth estimation model (MiDaS) - ~$0.00022 per run
    DEPTH_ESTIMATION_MODEL = "cjwbw/midas:a6ba5798f04f80d3b314de0f0a62277f21ab3503c60c84d4817de83c5edfdae0"

    def __init__(
        self,
        api_token: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        timeout: int = 300,
        use_sdxl: bool = True,
    ):
        """Initialize SD tile generator.

        Args:
            api_token: Replicate API token (defaults to REPLICATE_API_TOKEN env var)
            cache_dir: Directory for caching results
            timeout: API timeout in seconds
            use_sdxl: Use SDXL model (True) or SD 1.5 (False)
        """
        self.api_token = api_token or os.environ.get("REPLICATE_API_TOKEN")
        self.cache_dir = cache_dir or Path(".cache")
        self.timeout = timeout
        self.use_sdxl = use_sdxl

        if not self.api_token:
            raise ValueError(
                "SD Tile Generator requires Replicate API token. "
                "Set REPLICATE_API_TOKEN environment variable. "
                "Get one at: https://replicate.com/account/api-tokens"
            )

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Lazy import replicate
        self._replicate = None

    @property
    def replicate(self):
        """Lazy import of replicate module."""
        if self._replicate is None:
            try:
                import replicate
                self._replicate = replicate
            except ImportError:
                raise ImportError(
                    "Replicate package not installed. "
                    "Install with: pip install replicate"
                )
        return self._replicate

    def _get_cache_key(self, tile_coord: str, style: str, seed: int) -> str:
        """Generate a cache key for tile+style+seed combination."""
        combined = f"{tile_coord}_{style}_sd_{seed}"
        return hashlib.md5(combined.encode()).hexdigest()[:16]

    def _cache_path(self, cache_key: str) -> Path:
        """Get cache file path."""
        return self.cache_dir / "sd_tiles" / f"{cache_key}.png"

    def _load_from_cache(self, cache_key: str) -> Optional[NDArray[np.uint8]]:
        """Load a cached result."""
        cache_path = self._cache_path(cache_key)
        if cache_path.exists():
            with Image.open(cache_path) as img:
                return np.array(img.convert("RGB"))
        return None

    def _save_to_cache(self, cache_key: str, image: NDArray[np.uint8]) -> None:
        """Save a result to cache."""
        cache_path = self._cache_path(cache_key)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(image).save(cache_path)

    @staticmethod
    def image_to_data_uri(image: NDArray[np.uint8], format: str = "PNG") -> str:
        """Convert numpy array to data URI string for Replicate."""
        img = Image.fromarray(image)
        buffer = io.BytesIO()
        img.save(buffer, format=format)
        b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        mime = f"image/{format.lower()}"
        return f"data:{mime};base64,{b64}"

    @staticmethod
    def url_to_image(url: str) -> NDArray[np.uint8]:
        """Download image from URL and convert to numpy array."""
        import requests
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        img = Image.open(io.BytesIO(response.content))
        return np.array(img.convert("RGB"))

    def estimate_depth(self, rgb_image: NDArray[np.uint8]) -> NDArray[np.uint8]:
        """Estimate depth map from RGB image using MiDaS model.

        This is used when pre-rendered depth tiles don't exist.
        The MiDaS model produces high-quality depth estimation that
        works well with ControlNet Depth.

        Args:
            rgb_image: RGB image array (H, W, 3)

        Returns:
            Grayscale depth map (H, W) where white=far, black=near
        """
        # Convert to data URI
        rgb_uri = self.image_to_data_uri(rgb_image, format="PNG")

        print("    Estimating depth with MiDaS...")
        try:
            output = self.replicate.run(
                self.DEPTH_ESTIMATION_MODEL,
                input={
                    "image": rgb_uri,
                    "model_type": "dpt_beit_large_512",  # Best quality
                },
            )

            # Download depth map
            if isinstance(output, str):
                depth_url = output
            elif isinstance(output, list):
                depth_url = output[0]
            else:
                depth_url = str(output)

            depth_image = self.url_to_image(depth_url)

            # Convert to grayscale if needed
            if len(depth_image.shape) == 3:
                depth_gray = np.mean(depth_image, axis=2).astype(np.uint8)
            else:
                depth_gray = depth_image

            return depth_gray

        except Exception as e:
            print(f"    Warning: Depth estimation failed: {e}")
            # Return a flat depth map as fallback (mid-gray)
            return np.full((512, 512), 128, dtype=np.uint8)

    def generate(
        self,
        blender_image: NDArray[np.uint8],
        depth_map: Optional[NDArray[np.uint8]],
        style: str | SDStylePreset,
        tile_coord: Optional[str] = None,
        seed: Optional[int] = None,
        use_cache: bool = True,
    ) -> SDGenerationResult:
        """Generate a stylized tile using SD + ControlNet Depth.

        Args:
            blender_image: Blender-rendered tile RGB (H, W, 3) - used as reference
            depth_map: Depth pass from Blender (H, W) or (H, W, 3) grayscale.
                      If None, depth will be estimated from blender_image using MiDaS.
            style: Style name or SDStylePreset object
            tile_coord: Tile coordinate string for caching (e.g., "16/34322/22950")
            seed: Random seed (None = use style's default seed)
            use_cache: Whether to use cached results

        Returns:
            SDGenerationResult with generated image
        """
        # Resolve style
        if isinstance(style, str):
            style_preset = get_sd_style(style)
            style_name = style
        else:
            style_preset = style
            style_name = style.name.lower().replace(" ", "_").replace("sd_", "")

        tile_coord = tile_coord or "unknown"
        actual_seed = seed if seed is not None else style_preset.seed

        # Check cache
        if use_cache:
            cache_key = self._get_cache_key(tile_coord, style_name, actual_seed)
            cached = self._load_from_cache(cache_key)
            if cached is not None:
                return SDGenerationResult(
                    image=cached,
                    style=style_name,
                    tile_coord=tile_coord,
                    processing_time_ms=0,
                    cached=True,
                    seed=actual_seed,
                    model="sd-controlnet-depth",
                    metadata={"from_cache": True},
                )

        start_time = time.time()

        # Estimate depth if not provided
        if depth_map is None:
            depth_map = self.estimate_depth(blender_image)

        # Ensure depth map is grayscale
        if len(depth_map.shape) == 3:
            # Convert RGB depth to grayscale
            depth_gray = np.mean(depth_map, axis=2).astype(np.uint8)
        else:
            depth_gray = depth_map

        # Convert to RGB (ControlNet expects RGB input)
        depth_rgb = np.stack([depth_gray, depth_gray, depth_gray], axis=2)

        # Resize to 512x512 if needed
        if depth_rgb.shape[:2] != (512, 512):
            pil_depth = Image.fromarray(depth_rgb)
            pil_depth = pil_depth.resize((512, 512), Image.LANCZOS)
            depth_rgb = np.array(pil_depth)

        # Convert to data URI for Replicate
        depth_uri = self.image_to_data_uri(depth_rgb, format="PNG")

        # Run ControlNet Depth model via Replicate
        # Note: lucataco/sdxl-controlnet-depth uses these parameters:
        # - image, prompt, num_inference_steps, condition_scale, seed
        try:
            output = self.replicate.run(
                self.CONTROLNET_MODEL,
                input={
                    "image": depth_uri,
                    "prompt": style_preset.prompt,
                    "num_inference_steps": style_preset.num_inference_steps,
                    "condition_scale": min(1.0, style_preset.controlnet_conditioning_scale),  # Clamp to 0-1
                    "seed": actual_seed,
                },
            )

            # Handle output - Replicate returns URL(s)
            if isinstance(output, list):
                output_url = output[0]
            else:
                output_url = output

            # Download generated image
            generated_image = self.url_to_image(output_url)

        except Exception as e:
            raise ValueError(f"Replicate API error: {e}")

        # Resize to 512x512 if needed
        if generated_image.shape[:2] != (512, 512):
            pil_img = Image.fromarray(generated_image)
            pil_img = pil_img.resize((512, 512), Image.LANCZOS)
            generated_image = np.array(pil_img)

        processing_time = int((time.time() - start_time) * 1000)

        # Cache result
        if use_cache:
            cache_key = self._get_cache_key(tile_coord, style_name, actual_seed)
            self._save_to_cache(cache_key, generated_image)

        return SDGenerationResult(
            image=generated_image,
            style=style_name,
            tile_coord=tile_coord,
            processing_time_ms=processing_time,
            cached=False,
            seed=actual_seed,
            model="sd-controlnet-depth",
            metadata={
                "prompt": style_preset.prompt[:100] + "...",
                "controlnet_scale": style_preset.controlnet_conditioning_scale,
                "steps": style_preset.num_inference_steps,
                "guidance": style_preset.guidance_scale,
            },
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def load_depth_tile(
    tile_coord: str,
    depth_dir: Optional[Path] = None,
) -> Optional[NDArray[np.uint8]]:
    """Load a pre-rendered depth tile.

    Args:
        tile_coord: Tile coordinate string (e.g., "16/34322/22950")
        depth_dir: Directory containing depth tiles

    Returns:
        Grayscale depth image array or None if not found
    """
    if depth_dir is None:
        depth_dir = Path("public/tiles/depth")

    tile_path = depth_dir / f"{tile_coord}.png"
    if not tile_path.exists():
        return None

    with Image.open(tile_path) as img:
        return np.array(img.convert("L"))  # Grayscale


def check_sd_api_availability() -> bool:
    """Check if the Replicate API token is available.

    Returns:
        True if API token is set
    """
    return bool(os.environ.get("REPLICATE_API_TOKEN"))


def print_sd_setup_instructions() -> None:
    """Print instructions for setting up the Replicate API."""
    print("\n" + "=" * 60)
    print("SD Tile Generator Setup (Replicate)")
    print("=" * 60)

    if check_sd_api_availability():
        print("\n   Status: CONFIGURED")
        print("   Replicate API token found.")
    else:
        print("\n   Status: NOT CONFIGURED")
        print("")
        print("   To enable SD tile generation:")
        print("   1. Visit https://replicate.com/account/api-tokens")
        print("   2. Create an API token")
        print("   3. Set environment variable:")
        print("      export REPLICATE_API_TOKEN='r8_your_token_here'")
        print("")
        print("   Cost: ~$0.01 per tile (pay per use)")
        print("   Install: pip install replicate")

    print("\n" + "=" * 60)


def generate_sd_tiles_for_area(
    style: str,
    zoom: int = 16,
    bounds: Optional[tuple[float, float, float, float]] = None,
    output_dir: Optional[Path] = None,
    depth_dir: Optional[Path] = None,
    blender_dir: Optional[Path] = None,
    seed: Optional[int] = None,
    use_cache: bool = True,
    progress: bool = True,
    rate_limit_delay: float = 12.0,  # Seconds between API calls for rate limiting
    skip_depth_estimation: bool = True,  # Skip MiDaS to halve API calls (better for rate limits)
) -> list[Path]:
    """Generate SD-stylized tiles for an area.

    Args:
        style: Style name (winter, cyberpunk, etc.)
        zoom: Zoom level
        bounds: (west, south, east, north) or None for all available tiles
        output_dir: Output directory (default: public/tiles/sd-{style})
        depth_dir: Directory containing depth tiles (default: public/tiles/depth)
        blender_dir: Directory containing Blender RGB tiles (default: public/tiles/photorealistic)
        seed: Random seed (None = use style default)
        use_cache: Use cached results
        progress: Show progress bar

    Returns:
        List of generated tile paths

    Note:
        If depth tiles don't exist, depth will be estimated from the Blender RGB
        tiles using MiDaS depth estimation. This adds ~2-3 seconds per tile but
        removes the need for pre-rendered depth passes.
    """
    from tqdm import tqdm
    from .ai_tile_generator import load_blender_tile
    from .sources.satellite import wgs84_to_tile

    if output_dir is None:
        output_dir = Path(f"public/tiles/sd-{style}")

    if depth_dir is None:
        depth_dir = Path("public/tiles/depth")

    if blender_dir is None:
        blender_dir = Path("public/tiles/photorealistic")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Check if depth tiles exist - if not, we'll use Blender tiles and estimate depth
    depth_available = depth_dir.exists() and any(depth_dir.glob("**/*.png"))

    # Find all available Blender RGB tiles (primary source)
    if bounds:
        west, south, east, north = bounds
        x_min, y_max = wgs84_to_tile(west, south, zoom)
        x_max, y_min = wgs84_to_tile(east, north, zoom)

        tile_coords = []
        for y in range(y_min, y_max + 1):
            for x in range(x_min, x_max + 1):
                coord = f"{zoom}/{x}/{y}"
                blender_path = blender_dir / f"{coord}.webp"
                if blender_path.exists():
                    tile_coords.append(coord)
    else:
        # Find all Blender tiles at this zoom level
        zoom_dir = blender_dir / str(zoom)
        if not zoom_dir.exists():
            print(f"No Blender tiles found at zoom {zoom}")
            print(f"Generate them first with: python -m scripts.tile_pipeline.cli render --area city_center")
            return []

        tile_coords = []
        for x_dir in zoom_dir.iterdir():
            if x_dir.is_dir():
                for tile_file in x_dir.glob("*.webp"):
                    y = tile_file.stem
                    coord = f"{zoom}/{x_dir.name}/{y}"
                    tile_coords.append(coord)

    if not tile_coords:
        print(f"No Blender tiles found at zoom {zoom}")
        return []

    if not depth_available:
        if skip_depth_estimation:
            print("Note: Using Blender grayscale as pseudo-depth (preserves structure, no extra API call)")
        else:
            print("Note: No depth tiles found - will estimate depth using MiDaS (~2-3s extra per tile)")

    # Filter out tiles that already exist (if using cache)
    if use_cache:
        coords_to_generate = []
        cached_paths = []
        for coord in tile_coords:
            output_path = output_dir / f"{coord}.webp"
            if output_path.exists():
                cached_paths.append(output_path)
            else:
                coords_to_generate.append(coord)

        if cached_paths:
            print(f"Found {len(cached_paths)} cached tiles")
        tile_coords = coords_to_generate

    if not tile_coords:
        print("All tiles already cached!")
        return cached_paths if use_cache else []

    # Get style preset for seed
    style_preset = get_sd_style(style)
    actual_seed = seed if seed is not None else style_preset.seed

    print(f"Generating {len(tile_coords)} SD tiles in '{style}' style...")
    print(f"Output: {output_dir}")
    print(f"Seed: {actual_seed} (deterministic)")
    print(f"Estimated cost: ${len(tile_coords) * 0.01:.2f}")

    generator = SDTileGenerator()
    generated_paths = []

    iterator = tqdm(tile_coords) if progress else tile_coords
    for coord in iterator:
        try:
            output_path = output_dir / f"{coord}.webp"

            # Load Blender RGB tile (required)
            blender_image = load_blender_tile(coord, blender_dir)
            if blender_image is None:
                print(f"Warning: Blender tile not found: {coord}")
                continue

            # Load depth tile or use Blender grayscale as pseudo-depth
            if depth_available:
                depth_map = load_depth_tile(coord, depth_dir)
            elif skip_depth_estimation:
                # Use Blender image as grayscale pseudo-depth (preserves structure, no API call)
                depth_map = np.mean(blender_image, axis=2).astype(np.uint8)
            else:
                depth_map = None  # Will estimate with MiDaS (uses extra API call)

            # Generate
            result = generator.generate(
                blender_image=blender_image,
                depth_map=depth_map,
                style=style,
                tile_coord=coord,
                seed=actual_seed,
                use_cache=False,  # We already filtered cached tiles
            )

            # Save to output directory
            output_path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(result.image).save(output_path, quality=90)
            generated_paths.append(output_path)

            # Rate limiting: wait between API calls to avoid 429 errors
            # Replicate limits to 6 req/min with <$5 credit
            if rate_limit_delay > 0:
                time.sleep(rate_limit_delay)

        except Exception as e:
            print(f"Error generating {coord}: {e}")
            # Also rate limit on errors to avoid hammering the API
            if rate_limit_delay > 0:
                time.sleep(rate_limit_delay)
            continue

    # Add cached paths to result
    if use_cache and 'cached_paths' in dir():
        generated_paths = cached_paths + generated_paths

    print(f"Generated {len(generated_paths)} tiles")
    return generated_paths


def generate_satellite_styled_tiles(
    style: str,
    zoom: int = 16,
    bounds: Optional[tuple[float, float, float, float]] = None,
    output_dir: Optional[Path] = None,
    satellite_dir: Optional[Path] = None,
    seed: Optional[int] = None,
    image_guidance_scale: Optional[float] = None,
    use_cache: bool = True,
    progress: bool = True,
    rate_limit_delay: float = 12.0,  # Seconds between API calls
) -> list[Path]:
    """Generate satellite-styled tiles for an area using InstructPix2Pix.

    This is the RECOMMENDED approach for AI tile generation.
    It uses satellite imagery as input and transforms it with InstructPix2Pix,
    preserving structure while applying style changes.

    Args:
        style: Style name (winter, cyberpunk, etc.)
        zoom: Zoom level
        bounds: (west, south, east, north) or None for all available tiles
        output_dir: Output directory (default: public/tiles/sd-{style})
        satellite_dir: Directory containing satellite tiles (default: auto-fetch)
        seed: Random seed (None = use style default)
        image_guidance_scale: Override style's image_guidance_scale (higher = more faithful)
        use_cache: Use cached results
        progress: Show progress bar
        rate_limit_delay: Seconds between API calls (rate limiting)

    Returns:
        List of generated tile paths
    """
    from tqdm import tqdm
    from .sources.satellite import SatelliteSource, wgs84_to_tile
    from .config import PipelineConfig

    if output_dir is None:
        output_dir = Path(f"public/tiles/sd-{style}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get style preset
    style_preset = get_img2img_style(style)
    actual_seed = seed if seed is not None else style_preset.seed
    actual_image_guidance = image_guidance_scale if image_guidance_scale is not None else style_preset.image_guidance_scale

    # Initialize satellite source for fetching tiles
    config = PipelineConfig()
    satellite_source = SatelliteSource(
        url_template=config.sources.swissimage_url,
        cache_dir=config.cache_dir,
    )

    # Determine which tiles to generate
    if bounds:
        west, south, east, north = bounds
        x_min, y_max = wgs84_to_tile(west, south, zoom)
        x_max, y_min = wgs84_to_tile(east, north, zoom)

        tile_coords = []
        for y in range(y_min, y_max + 1):
            for x in range(x_min, x_max + 1):
                coord = f"{zoom}/{x}/{y}"
                tile_coords.append(coord)
    else:
        # Check for existing satellite tiles in cache
        cache_sat_dir = config.cache_dir / "satellite" / str(zoom)
        if not cache_sat_dir.exists():
            print(f"No satellite tiles found at zoom {zoom}")
            print("Specify --bounds or --area to download tiles")
            return []

        tile_coords = []
        for x_dir in cache_sat_dir.iterdir():
            if x_dir.is_dir():
                for tile_file in x_dir.glob("*.jpeg"):
                    y = tile_file.stem
                    coord = f"{zoom}/{x_dir.name}/{y}"
                    tile_coords.append(coord)

    if not tile_coords:
        print("No tiles to generate")
        return []

    # Filter out tiles that already exist (if using cache)
    if use_cache:
        coords_to_generate = []
        cached_paths = []
        for coord in tile_coords:
            output_path = output_dir / f"{coord}.webp"
            if output_path.exists():
                cached_paths.append(output_path)
            else:
                coords_to_generate.append(coord)

        if cached_paths:
            print(f"Found {len(cached_paths)} cached tiles")
        tile_coords = coords_to_generate

    if not tile_coords:
        print("All tiles already cached!")
        return cached_paths if use_cache else []

    print(f"Generating {len(tile_coords)} satellite-styled tiles in '{style}' style...")
    print(f"Output: {output_dir}")
    print(f"Seed: {actual_seed} (deterministic)")
    print(f"Image guidance scale: {actual_image_guidance} (higher = more faithful)")
    print(f"Estimated cost: ${len(tile_coords) * 0.01:.2f}")

    transfer = SatelliteStyleTransfer()
    generated_paths = []

    iterator = tqdm(tile_coords) if progress else tile_coords
    for coord in iterator:
        try:
            output_path = output_dir / f"{coord}.webp"

            # Parse tile coordinate
            parts = coord.split("/")
            z, x, y = int(parts[0]), int(parts[1]), int(parts[2])

            # Fetch satellite tile (512x512)
            satellite_image = satellite_source.fetch_and_resize(z, x, y, target_size=512)

            # Transform with InstructPix2Pix
            result = transfer.transform(
                satellite_image=satellite_image,
                style=style,
                tile_coord=coord,
                seed=actual_seed,
                image_guidance_scale=actual_image_guidance,
                use_cache=False,  # We already filtered cached tiles
            )

            # Save to output directory
            output_path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(result.image).save(output_path, quality=90)
            generated_paths.append(output_path)

            # Rate limiting
            if rate_limit_delay > 0:
                time.sleep(rate_limit_delay)

        except Exception as e:
            print(f"Error generating {coord}: {e}")
            if rate_limit_delay > 0:
                time.sleep(rate_limit_delay)
            continue

    # Add cached paths to result
    if use_cache and 'cached_paths' in dir():
        generated_paths = cached_paths + generated_paths

    print(f"Generated {len(generated_paths)} tiles")
    return generated_paths


def load_satellite_tile(
    tile_coord: str,
    satellite_dir: Optional[Path] = None,
) -> Optional[NDArray[np.uint8]]:
    """Load a satellite tile from cache or fetch it.

    Args:
        tile_coord: Tile coordinate string (e.g., "16/34322/22950")
        satellite_dir: Custom satellite tiles directory

    Returns:
        RGB image array or None if not found
    """
    from .sources.satellite import SatelliteSource
    from .config import PipelineConfig

    config = PipelineConfig()

    if satellite_dir is None:
        satellite_dir = config.cache_dir / "satellite"

    # Try loading from local directory first
    tile_path = satellite_dir / f"{tile_coord}.jpeg"
    if tile_path.exists():
        with Image.open(tile_path) as img:
            return np.array(img.convert("RGB"))

    # Try fetching
    try:
        parts = tile_coord.split("/")
        z, x, y = int(parts[0]), int(parts[1]), int(parts[2])

        source = SatelliteSource(
            url_template=config.sources.swissimage_url,
            cache_dir=config.cache_dir,
        )
        return source.fetch_and_resize(z, x, y, target_size=512)
    except Exception:
        return None


if __name__ == "__main__":
    print_sd_setup_instructions()
    print("\nAvailable SD styles (ControlNet - legacy):")
    for name, desc in list_sd_styles().items():
        print(f"  {name}: {desc}")
    print("\nAvailable img2img styles (Satellite - recommended):")
    for name, desc in list_img2img_styles().items():
        print(f"  {name}: {desc}")
