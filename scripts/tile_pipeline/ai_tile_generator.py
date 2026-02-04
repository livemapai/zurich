"""
AI-powered tile generation using Gemini with multi-image conditioning.

Generates stylized map tiles (winter, cyberpunk, watercolor, etc.) by sending:
1. Blender render (512x512) - accurate 3D geometry/shadows
2. Satellite image (512x512) - realistic textures/colors
3. Global style prompt - consistent across ALL tiles
4. Minimal local context - let images define what's there

Tile Continuity Strategy:
- GLOBAL prompts are identical for all tiles in a style
- LOCAL context is minimal (just says "match the reference images")
- This ensures adjacent tiles have consistent lighting, colors, and style

Usage:
    from .ai_tile_generator import generate_stylized_tile, list_ai_styles

    # Generate a winter-themed tile
    result = generate_stylized_tile(
        tile_coord="16/34322/22950",
        style="winter",
    )

    # List available styles
    styles = list_ai_styles()
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
import requests

from .config import PipelineConfig
from .sources.satellite import fetch_satellite_tile, wgs84_to_tile
from .tile_renderer import TileCoord


# =============================================================================
# STYLE PRESETS
# =============================================================================


@dataclass
class StylePreset:
    """AI style preset for tile generation.

    Contains prompts designed for CROSS-TILE CONSISTENCY.
    The style_prompt and atmosphere_prompt are GLOBAL (same for all tiles).
    Local context is minimal to ensure adjacent tiles look coherent.

    The reference_image provides a "golden example" tile showing the exact
    camera angle and visual style to match. This helps ensure consistent
    top-down orthographic views across all generated tiles.
    """

    name: str
    description: str = ""

    # GLOBAL SECTION - identical for every tile in this style
    style_prompt: str = ""          # Main style description
    atmosphere_prompt: str = ""     # Lighting/mood description
    detail_instructions: str = ""   # How to render details

    # Color palette for consistency
    dominant_colors: list[str] = field(default_factory=list)

    # Generation parameters
    temperature: float = 0.5        # Lower = more consistent (was 0.7)

    # Reference image for style/camera consistency (3-image pipeline)
    reference_image: Optional[str] = None  # Path relative to project root

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "style_prompt": self.style_prompt,
            "atmosphere_prompt": self.atmosphere_prompt,
            "detail_instructions": self.detail_instructions,
            "dominant_colors": self.dominant_colors,
            "temperature": self.temperature,
            "reference_image": self.reference_image,
        }


# Predefined AI styles optimized for tile continuity
# All styles use lower temperatures (0.5-0.6) for more consistent results
# Reference images provide "golden examples" for camera angle and visual style
STYLES: dict[str, StylePreset] = {
    "winter": StylePreset(
        name="Winter Zurich",
        description="Snow-covered cityscape with cold afternoon light",
        style_prompt=(
            "Transform this into a winter scene with fresh snow. "
            "Cover all rooftops, streets, and open areas with clean white snow. "
            "Trees should have snow on branches. The scene should feel crisp and cold."
        ),
        atmosphere_prompt=(
            "Cold afternoon light from the southwest. "
            "Soft shadows on the snow. Muted colors: whites, ice blues, soft grays. "
            "The sky should be pale winter gray-blue."
        ),
        detail_instructions=(
            "Apply 70% consistent snow coverage on all horizontal surfaces. "
            "Keep building walls their original colors but slightly desaturated. "
            "Snow should have subtle blue shadows."
        ),
        dominant_colors=["#FFFFFF", "#E8F0F8", "#B8C8D8", "#8898A8"],
        temperature=0.5,  # Lowered for consistency
        reference_image="public/tiles/style-references/winter-reference.webp",
    ),
    "cyberpunk": StylePreset(
        name="Cyberpunk Night",
        description="Neon-lit dystopian cityscape at night",
        style_prompt=(
            "Transform this into a cyberpunk night scene. "
            "Buildings should have glowing windows in neon colors. "
            "Streets should be wet and reflective. Add neon signage glow."
        ),
        atmosphere_prompt=(
            "Night scene with neon lighting. "
            "Wet streets reflecting pink and cyan neon. "
            "Dark sky with orange-pink light pollution glow on horizon."
        ),
        detail_instructions=(
            "80% of windows should glow in cyan, pink, or purple. "
            "Streets wet and shiny. "
            "Add subtle fog/haze between buildings for depth."
        ),
        dominant_colors=["#FF00FF", "#00FFFF", "#8B00FF", "#000033", "#FFFF00"],
        temperature=0.5,  # Lowered from 0.8 for consistency
        reference_image="public/tiles/style-references/cyberpunk-reference.webp",
    ),
    "watercolor": StylePreset(
        name="Watercolor Painting",
        description="Artistic watercolor style with soft edges",
        style_prompt=(
            "Transform this into a watercolor painting. "
            "Use soft edges and visible brush strokes. "
            "Colors should bleed slightly at boundaries."
        ),
        atmosphere_prompt=(
            "Soft diffuse lighting like an overcast day. "
            "Muted, slightly desaturated colors. "
            "Gentle shadows with soft edges."
        ),
        detail_instructions=(
            "Maintain building shapes but soften edges. "
            "Use paper texture effect. "
            "Let colors blend at boundaries like wet-on-wet watercolor."
        ),
        dominant_colors=["#E8DCC8", "#7BA3A8", "#C4A87C", "#8B7355"],
        temperature=0.6,  # Lowered from 0.9 for consistency
        reference_image="public/tiles/style-references/watercolor-reference.webp",
    ),
    "autumn": StylePreset(
        name="Autumn Foliage",
        description="Fall colors with golden afternoon light",
        style_prompt=(
            "Transform this into an autumn scene. "
            "All trees should have fall foliage in red, orange, gold, and brown. "
            "Some fallen leaves on streets and sidewalks."
        ),
        atmosphere_prompt=(
            "Warm golden afternoon light from the west. "
            "Long warm shadows. Rich, saturated fall colors. "
            "Slightly hazy autumn atmosphere."
        ),
        detail_instructions=(
            "Trees 100% autumn colors - mix of red, orange, yellow, brown. "
            "Grass slightly yellow-brown. "
            "Add scattered leaves on ground near trees."
        ),
        dominant_colors=["#D4652F", "#E8A530", "#8B4513", "#CD853F", "#228B22"],
        temperature=0.5,  # Lowered for consistency
        reference_image="public/tiles/style-references/autumn-reference.webp",
    ),
    "blueprint": StylePreset(
        name="Blueprint",
        description="Technical blueprint-style with white lines on blue",
        style_prompt=(
            "Transform this into an architectural blueprint. "
            "Show buildings as white outlines on dark blue background. "
            "Remove all textures, keep only structural lines."
        ),
        atmosphere_prompt=(
            "Flat technical lighting with no shadows. "
            "Pure blue background. White and light blue lines only. "
            "No gradients, no textures."
        ),
        detail_instructions=(
            "Convert all structures to white line drawings. "
            "Building edges should be crisp white lines. "
            "Background must be solid dark blue (#002266)."
        ),
        dominant_colors=["#002266", "#FFFFFF", "#4488CC", "#88AADD"],
        temperature=0.4,  # Even lower for technical precision
        reference_image="public/tiles/style-references/blueprint-reference.webp",
    ),
    "retro": StylePreset(
        name="80s Retro",
        description="Vaporwave aesthetics with pink/cyan gradients",
        style_prompt=(
            "Transform this into 80s retro vaporwave style. "
            "Add pink and cyan color grading. "
            "Geometric grid patterns on surfaces."
        ),
        atmosphere_prompt=(
            "Sunset lighting with pink and orange sky. "
            "Strong pink/magenta and cyan color cast. "
            "Chrome reflections on buildings."
        ),
        detail_instructions=(
            "Apply heavy pink-cyan color grading to all surfaces. "
            "Add subtle grid line overlay on streets. "
            "Buildings should have chrome/metallic sheen."
        ),
        dominant_colors=["#FF6EC7", "#00FFFF", "#FF00FF", "#FFB347", "#1A1A2E"],
        temperature=0.5,  # Lowered from 0.8 for consistency
        reference_image="public/tiles/style-references/retro-reference.webp",
    ),
}


def get_style(name: str) -> StylePreset:
    """Get an AI style preset by name.

    Args:
        name: Style name (case-insensitive)

    Returns:
        StylePreset instance

    Raises:
        ValueError: If style name is not found
    """
    name_lower = name.lower()
    if name_lower not in STYLES:
        available = ", ".join(sorted(STYLES.keys()))
        raise ValueError(f"Unknown AI style '{name}'. Available: {available}")
    return STYLES[name_lower]


def list_ai_styles() -> dict[str, str]:
    """List all available AI styles with descriptions.

    Returns:
        Dict mapping style name to description
    """
    return {name: style.description for name, style in STYLES.items()}


# =============================================================================
# AI TILE GENERATOR
# =============================================================================


@dataclass
class GenerationResult:
    """Result from an AI tile generation operation."""

    image: NDArray[np.uint8]  # RGB (H, W, 3)
    style: str
    tile_coord: str
    processing_time_ms: int
    cached: bool = False
    model: str = ""
    metadata: Optional[dict] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "style": self.style,
            "tile_coord": self.tile_coord,
            "processing_time_ms": self.processing_time_ms,
            "cached": self.cached,
            "model": self.model,
            "image_shape": list(self.image.shape),
        }


class AITileGenerator:
    """Generates stylized tiles using Gemini AI with multi-image conditioning.

    Uses a two-image approach for best results:
    1. Blender render - provides accurate 3D geometry and shadow positions
    2. Satellite image - provides realistic textures and surface materials

    The AI combines these with a global style prompt to generate
    consistent stylized tiles.
    """

    # Gemini API configuration
    API_BASE = "https://generativelanguage.googleapis.com/v1beta"
    # Gemini 2.5 Flash Image (aka "nano-banana") - fast, cost-efficient image generation
    DEFAULT_MODEL = "models/gemini-2.5-flash-image"
    FALLBACK_MODEL = "models/gemini-2.0-flash"

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        timeout: int = 180,
        model: Optional[str] = None,
    ):
        """Initialize AI tile generator.

        Args:
            api_key: Google AI API key (defaults to GOOGLE_API_KEY env var)
            cache_dir: Directory for caching results
            timeout: API timeout in seconds
            model: Model to use (default: gemini-2.0-flash-exp)
        """
        self.api_key = (
            api_key
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
        )
        self.cache_dir = cache_dir or Path(".cache")
        self.timeout = timeout
        self.model = model or self.DEFAULT_MODEL

        if not self.api_key:
            raise ValueError(
                "AI Tile Generator requires Google AI API key. "
                "Set GOOGLE_API_KEY environment variable."
            )

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, tile_coord: str, style: str) -> str:
        """Generate a cache key for tile+style combination."""
        combined = f"{tile_coord}_{style}_{self.model}"
        return hashlib.md5(combined.encode()).hexdigest()[:16]

    def _cache_path(self, cache_key: str) -> Path:
        """Get cache file path."""
        return self.cache_dir / "ai_tiles" / f"{cache_key}.png"

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

    def _load_reference_image(self, reference_path: Optional[str]) -> Optional[NDArray[np.uint8]]:
        """Load a style reference image for the 3-image pipeline.

        Args:
            reference_path: Path to reference image (relative to project root)

        Returns:
            RGB image array or None if not found/specified
        """
        if not reference_path:
            return None

        # Try to find the reference image
        ref_path = Path(reference_path)
        if not ref_path.is_absolute():
            # Try relative to current working directory
            if not ref_path.exists():
                # Try relative to common project locations
                for base in [Path("."), Path(__file__).parent.parent.parent]:
                    candidate = base / reference_path
                    if candidate.exists():
                        ref_path = candidate
                        break

        if not ref_path.exists():
            # Log but don't fail - fall back to 2-image pipeline
            return None

        try:
            with Image.open(ref_path) as img:
                # Ensure 512x512
                if img.size != (512, 512):
                    img = img.resize((512, 512), Image.LANCZOS)
                return np.array(img.convert("RGB"))
        except Exception:
            return None

    def _build_prompt(self, style: StylePreset, tile_coord: str, has_reference: bool = False) -> str:
        """Build the full prompt using narrative description and photography terminology.

        The prompt is designed for CROSS-TILE CONSISTENCY using Nano Banana best practices:
        - Narrative paragraphs (73% more effective than keyword lists)
        - Photography/technical terms for precise camera control
        - Explicit aspect ratio instructions
        - Clear role assignment for each reference image

        Args:
            style: The style preset to apply
            tile_coord: Tile coordinate for context
            has_reference: Whether a reference image is included (3-image pipeline)
        """
        # Build color palette string
        colors = ", ".join(style.dominant_colors) if style.dominant_colors else "natural colors"

        if has_reference:
            # 3-IMAGE PIPELINE PROMPT (with style reference)
            prompt = f"""You are recoloring a map tile for a seamless tileset. This is a precise recoloring task where the geometry must remain pixel-perfect.

Study the three reference images carefully:

The first image is a Blender 3D render showing this exact geometric layout from a strict top-down orthographic projection at 90° nadir angle. This is your geometric truth - every building footprint, every street edge, every tree position must be preserved with absolute fidelity in your output. Do not add, remove, move, or distort any structures.

The second image is satellite photography showing real-world textures and materials. Use this only for understanding surface materials - rooftops, vegetation types, pavement textures - but never for geometry. The satellite view may have slight perspective distortion that you must ignore.

The third image is your style reference showing exactly how the final output should look. Match this exact visual style, color palette, and atmosphere. Most importantly, match this exact camera angle - a planimetric top-down view with zero perspective distortion where all parallel lines remain perfectly parallel.

Camera specification: Orthographic projection looking straight down, equivalent to infinite focal length or parallel projection. The camera sensor is perfectly parallel to the ground plane. There must be no 3D tilt, no isometric angle, no bird's eye perspective - only true nadir view as in the Blender render and style reference.

Apply the {style.name} style: {style.style_prompt}

Atmosphere and lighting: {style.atmosphere_prompt}

Color palette to use: {colors}

Your output must be exactly 512×512 pixels maintaining this exact aspect ratio. Do not change the input aspect ratio. The result should look as if the third image's color grading and style were painted directly onto the first image's frozen geometry - identical building shapes, identical street layouts, only the colors and textures transformed.

Do not include any text, labels, watermarks, or UI elements. This tile must seamlessly connect with adjacent tiles in the grid."""

        else:
            # 2-IMAGE PIPELINE PROMPT (fallback without reference)
            prompt = f"""You are recoloring a map tile for a seamless tileset. This is a precise recoloring task where the geometry must remain pixel-perfect.

Study the two reference images carefully:

The first image is a Blender 3D render showing this exact geometric layout from a strict top-down orthographic projection at 90° nadir angle. This is your geometric truth - every building footprint, every street edge, every tree position must be preserved with absolute fidelity in your output. Do not add, remove, move, or distort any structures.

The second image is satellite photography showing real-world textures and materials. Use this only for understanding surface materials - rooftops, vegetation types, pavement textures - but never for geometry. The satellite view may have slight perspective distortion that you must ignore.

Camera specification: Orthographic projection looking straight down, equivalent to infinite focal length or parallel projection. The camera sensor is perfectly parallel to the ground plane. There must be no 3D tilt, no isometric angle, no bird's eye perspective - only true nadir view matching the Blender render exactly.

Apply the {style.name} style: {style.style_prompt}

Atmosphere and lighting: {style.atmosphere_prompt}

Color palette to use: {colors}

Your output must be exactly 512×512 pixels maintaining this exact aspect ratio. Do not change the input aspect ratio. The result should look as if the style's color grading were painted directly onto the first image's frozen geometry - identical building shapes, identical street layouts, only the colors and textures transformed.

Do not include any text, labels, watermarks, or UI elements. This tile must seamlessly connect with adjacent tiles in the grid."""

        return prompt

    def generate(
        self,
        blender_image: NDArray[np.uint8],
        satellite_image: NDArray[np.uint8],
        style: str | StylePreset,
        tile_coord: Optional[str] = None,
        use_cache: bool = True,
    ) -> GenerationResult:
        """Generate a stylized tile from Blender render and satellite image.

        Args:
            blender_image: Blender-rendered tile (H, W, 3)
            satellite_image: Satellite imagery tile (H, W, 3)
            style: Style name or StylePreset object
            tile_coord: Tile coordinate string for caching (e.g., "16/34322/22950")
            use_cache: Whether to use cached results

        Returns:
            GenerationResult with generated image
        """
        # Resolve style
        if isinstance(style, str):
            style_preset = get_style(style)
            style_name = style
        else:
            style_preset = style
            style_name = style.name.lower().replace(" ", "_")

        tile_coord = tile_coord or "unknown"

        # Check cache
        if use_cache:
            cache_key = self._get_cache_key(tile_coord, style_name)
            cached = self._load_from_cache(cache_key)
            if cached is not None:
                return GenerationResult(
                    image=cached,
                    style=style_name,
                    tile_coord=tile_coord,
                    processing_time_ms=0,
                    cached=True,
                    model=self.model,
                    metadata={"from_cache": True},
                )

        start_time = time.time()

        # Convert images to base64
        blender_b64 = self.image_to_base64(blender_image, format="PNG")
        satellite_b64 = self.image_to_base64(satellite_image, format="JPEG")

        # Try to load reference image for 3-image pipeline
        reference_image = self._load_reference_image(style_preset.reference_image)
        has_reference = reference_image is not None

        # Build prompt (aware of whether we have a reference image)
        prompt = self._build_prompt(style_preset, tile_coord, has_reference=has_reference)

        # Build multi-image Gemini request
        # Image order: Blender (geometry) → Satellite (textures) → Reference (style, last for aspect ratio)
        # Text prompt comes AFTER images per Gemini best practices
        url = f"{self.API_BASE}/{self.model}:generateContent?key={self.api_key}"

        # Build parts list based on whether we have a reference image
        parts = [
            {
                "inline_data": {
                    "mime_type": "image/png",
                    "data": blender_b64,
                }
            },
            {
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": satellite_b64,
                }
            },
        ]

        # Add reference image if available (placed last for aspect ratio preservation)
        if has_reference:
            reference_b64 = self.image_to_base64(reference_image, format="PNG")
            parts.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": reference_b64,
                }
            })

        # Text prompt comes last (after all images)
        parts.append({"text": prompt})

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseModalities": ["image", "text"],
                "temperature": style_preset.temperature,
            }
        }

        # Make API request
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
        )

        # Handle errors
        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "No details"
            raise ValueError(
                f"Gemini API error {response.status_code}: {error_detail}"
            )

        result = response.json()

        # Extract image from response
        generated_image = None
        text_response = None

        if "candidates" in result:
            for candidate in result["candidates"]:
                if "content" in candidate and "parts" in candidate["content"]:
                    for part in candidate["content"]["parts"]:
                        if "inlineData" in part:
                            b64_data = part["inlineData"]["data"]
                            generated_image = self.base64_to_image(b64_data)
                        elif "text" in part:
                            text_response = part["text"]

        if generated_image is None:
            error_msg = (
                f"Gemini ({self.model}) did not return an image. "
                "The model may not support image generation."
            )
            if text_response:
                error_msg += f"\nModel response: {text_response[:300]}"
            raise ValueError(error_msg)

        # Resize to 512x512 if needed
        if generated_image.shape[:2] != (512, 512):
            pil_img = Image.fromarray(generated_image)
            pil_img = pil_img.resize((512, 512), Image.LANCZOS)
            generated_image = np.array(pil_img)

        processing_time = int((time.time() - start_time) * 1000)

        # Cache result
        if use_cache:
            cache_key = self._get_cache_key(tile_coord, style_name)
            self._save_to_cache(cache_key, generated_image)

        return GenerationResult(
            image=generated_image,
            style=style_name,
            tile_coord=tile_coord,
            processing_time_ms=processing_time,
            cached=False,
            model=self.model,
            metadata={
                "prompt_length": len(prompt),
                "text_response": text_response,
                "used_reference": has_reference,
                "image_count": 3 if has_reference else 2,
            },
        )


# =============================================================================
# TILE LOADING HELPERS
# =============================================================================


def load_blender_tile(
    tile_coord: str,
    tiles_dir: Optional[Path] = None,
) -> Optional[NDArray[np.uint8]]:
    """Load a pre-rendered Blender tile.

    Args:
        tile_coord: Tile coordinate string (e.g., "16/34322/22950")
        tiles_dir: Directory containing rendered tiles

    Returns:
        RGB image array or None if not found
    """
    if tiles_dir is None:
        tiles_dir = Path("public/tiles/photorealistic")

    tile_path = tiles_dir / f"{tile_coord}.webp"
    if not tile_path.exists():
        # Try PNG fallback
        tile_path = tiles_dir / f"{tile_coord}.png"

    if not tile_path.exists():
        return None

    with Image.open(tile_path) as img:
        return np.array(img.convert("RGB"))


def load_satellite_tile(
    tile_coord: str,
    config: Optional[PipelineConfig] = None,
) -> NDArray[np.uint8]:
    """Load a satellite tile for the given coordinate.

    Args:
        tile_coord: Tile coordinate string (e.g., "16/34322/22950")
        config: Pipeline configuration

    Returns:
        RGB image array (512x512)
    """
    # Parse tile coordinate
    parts = tile_coord.split("/")
    if len(parts) != 3:
        raise ValueError(f"Invalid tile coordinate format: {tile_coord}")

    z, x, y = int(parts[0]), int(parts[1]), int(parts[2])

    return fetch_satellite_tile(z, x, y, config=config, target_size=512)


def parse_tile_coord(coord_str: str) -> TileCoord:
    """Parse a tile coordinate string.

    Args:
        coord_str: Tile coordinate string (e.g., "16/34322/22950")

    Returns:
        TileCoord object
    """
    parts = coord_str.split("/")
    if len(parts) != 3:
        raise ValueError(f"Invalid tile coordinate format: {coord_str}")

    return TileCoord(int(parts[0]), int(parts[1]), int(parts[2]))


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def generate_stylized_tile(
    tile_coord: str,
    style: str,
    blender_tiles_dir: Optional[Path] = None,
    config: Optional[PipelineConfig] = None,
    api_key: Optional[str] = None,
    use_cache: bool = True,
) -> GenerationResult:
    """Convenience function to generate a stylized tile.

    Loads the Blender render and satellite image, then generates
    a stylized tile using the AI.

    Args:
        tile_coord: Tile coordinate string (e.g., "16/34322/22950")
        style: Style name (see list_ai_styles())
        blender_tiles_dir: Directory with Blender-rendered tiles
        config: Pipeline configuration
        api_key: Optional API key override
        use_cache: Whether to use cached results

    Returns:
        GenerationResult with generated image

    Raises:
        FileNotFoundError: If Blender tile not found
        ValueError: If API call fails
    """
    # Load Blender tile
    blender_image = load_blender_tile(tile_coord, blender_tiles_dir)
    if blender_image is None:
        raise FileNotFoundError(
            f"Blender tile not found: {tile_coord}. "
            "Render it first with: python -m scripts.tile_pipeline.cli render"
        )

    # Load satellite tile
    satellite_image = load_satellite_tile(tile_coord, config)

    # Generate stylized tile
    generator = AITileGenerator(api_key=api_key)
    return generator.generate(
        blender_image=blender_image,
        satellite_image=satellite_image,
        style=style,
        tile_coord=tile_coord,
        use_cache=use_cache,
    )


def check_api_availability() -> bool:
    """Check if the Google AI API key is available.

    Returns:
        True if API key is set
    """
    return bool(
        os.environ.get("GOOGLE_API_KEY") or
        os.environ.get("GEMINI_API_KEY")
    )


def print_setup_instructions() -> None:
    """Print instructions for setting up the API key."""
    print("\n" + "=" * 60)
    print("AI Tile Generator Setup")
    print("=" * 60)

    if check_api_availability():
        print("\n   Status: CONFIGURED")
        print("   Google AI API key found.")
    else:
        print("\n   Status: NOT CONFIGURED")
        print("")
        print("   To enable AI tile generation:")
        print("   1. Visit https://aistudio.google.com/apikey")
        print("   2. Create an API key")
        print("   3. Set environment variable:")
        print("      export GOOGLE_API_KEY='your-api-key'")
        print("")
        print("   Cost: Free tier (1,500 requests/day)")

    print("\n" + "=" * 60)


def generate_tiles_for_area(
    style: str,
    zoom: int = 16,
    bounds: Optional[tuple[float, float, float, float]] = None,
    output_dir: Optional[Path] = None,
    use_cache: bool = True,
    progress: bool = True,
    workers: int = 1,
) -> list[Path]:
    """Generate AI-stylized tiles for an area.

    Args:
        style: Style name (winter, cyberpunk, etc.)
        zoom: Zoom level
        bounds: (west, south, east, north) or None for all available tiles
        output_dir: Output directory (default: public/tiles/ai-{style})
        use_cache: Use cached results
        progress: Show progress bar
        workers: Number of parallel workers (default: 1 for sequential)

    Returns:
        List of generated tile paths
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from tqdm import tqdm

    if output_dir is None:
        output_dir = Path(f"public/tiles/ai-{style}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all available Blender tiles
    blender_dir = Path("public/tiles/photorealistic")

    if bounds:
        # Calculate tiles in bounds
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
        # Find all tiles at this zoom level
        zoom_dir = blender_dir / str(zoom)
        if not zoom_dir.exists():
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

    print(f"Generating {len(tile_coords)} AI tiles in '{style}' style...")
    print(f"Output: {output_dir}")
    print(f"Estimated cost: ${len(tile_coords) * 0.039:.2f}")
    if workers > 1:
        print(f"Workers: {workers} (parallel)")

    generator = AITileGenerator()

    def process_tile(coord: str) -> Optional[Path]:
        """Process a single tile - returns output path or None on failure."""
        try:
            output_path = output_dir / f"{coord}.webp"

            # Load images
            blender_image = load_blender_tile(coord, blender_dir)
            if blender_image is None:
                return None

            satellite_image = load_satellite_tile(coord)

            # Generate
            result = generator.generate(
                blender_image=blender_image,
                satellite_image=satellite_image,
                style=style,
                tile_coord=coord,
                use_cache=False,  # We already filtered cached tiles
            )

            # Save to output directory
            output_path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(result.image).save(output_path, quality=90)
            return output_path

        except Exception as e:
            print(f"Error generating {coord}: {e}")
            return None

    generated_paths = []

    if workers > 1:
        # Parallel execution with ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(process_tile, coord): coord for coord in tile_coords}

            with tqdm(total=len(futures), disable=not progress) as pbar:
                for future in as_completed(futures):
                    result = future.result()
                    if result is not None:
                        generated_paths.append(result)
                    pbar.update(1)
    else:
        # Sequential execution (original behavior)
        iterator = tqdm(tile_coords) if progress else tile_coords
        for coord in iterator:
            result = process_tile(coord)
            if result is not None:
                generated_paths.append(result)

    # Add cached paths to result
    if use_cache and 'cached_paths' in dir():
        generated_paths = cached_paths + generated_paths

    print(f"Generated {len(generated_paths)} tiles")
    return generated_paths


if __name__ == "__main__":
    print_setup_instructions()
    print("\nAvailable styles:")
    for name, desc in list_ai_styles().items():
        print(f"  {name}: {desc}")
