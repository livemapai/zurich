"""
Generate textures informed by satellite imagery analysis.

This module creates building textures using:
1. Satellite imagery analysis to extract actual Zurich colors and styles
2. Gemini 2.5 Flash Image to generate seamless textures matching those colors

The key insight is that the LLM sees real Zurich satellite data and generates
textures that match the actual color palette of the city, ensuring visual coherence.

Architecture:
    Satellite Tile → VisionBlenderGenerator → VisionAnalysis
                                                   ↓
                                         Extracted colors & style
                                                   ↓
                   Gemini 2.5 Flash ← "Generate texture matching these colors"
                          ↓
                    Textured PNG (albedo)

Usage:
    from .texture_generator import (
        generate_texture_from_satellite,
        generate_all_textures_from_reference,
        analyze_satellite_for_textures,
    )

    # Generate textures informed by a satellite reference tile
    sat_tile = fetch_satellite_tile(16, 34322, 22950)
    textures = generate_all_textures_from_reference(sat_tile)

    # Or generate a single texture type
    path = generate_texture_from_satellite(
        texture_type="residential_plaster",
        satellite_tile=sat_tile,
    )
"""

import base64
import hashlib
import io
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray
from PIL import Image
import requests

# Cache and output directories
CACHE_DIR = Path(".texture_cache")
TEXTURE_DIR = Path("scripts/tile_pipeline/assets/textures")


# =============================================================================
# TEXTURE TYPE DEFINITIONS
# =============================================================================

@dataclass
class TextureSpec:
    """Specification for a texture type."""

    name: str
    base_prompt: str
    color_source: str  # "roof" or "ground" - which satellite colors to use
    resolution: int = 1024
    description: str = ""


# Base prompts for each texture type
# These prompts are designed for Gemini 2.5 Flash Image to generate
# seamless, tileable textures suitable for PBR materials
TEXTURE_SPECS: Dict[str, TextureSpec] = {
    "residential_plaster": TextureSpec(
        name="Residential Plaster",
        base_prompt=(
            "seamless tileable texture, Swiss residential stucco wall, "
            "fine plaster grain, 4k, PBR material, flat even lighting, "
            "no shadows, square format, architectural texture"
        ),
        color_source="ground",  # Wall colors from ground tones
        description="Warm cream/beige stucco typical of Swiss residential buildings",
    ),
    "commercial_facade": TextureSpec(
        name="Commercial Facade",
        base_prompt=(
            "seamless tileable texture, modern commercial building facade, "
            "glass and metal panels, clean lines, 4k, flat lighting, square format, "
            "architectural texture, no reflections"
        ),
        color_source="ground",
        description="Modern glass and metal for commercial buildings",
    ),
    "industrial_concrete": TextureSpec(
        name="Industrial Concrete",
        base_prompt=(
            "seamless tileable texture, industrial concrete wall, "
            "exposed aggregate, slight weathering, 4k, flat lighting, "
            "square format, no shadows"
        ),
        color_source="ground",
        description="Weathered concrete for industrial structures",
    ),
    "historic_plaster": TextureSpec(
        name="Historic Plaster",
        base_prompt=(
            "seamless tileable texture, historic European building facade, "
            "aged plaster wall, subtle cracks, ornate, 4k, flat lighting, "
            "square format, architectural detail"
        ),
        color_source="ground",
        description="Aged plaster for historic Altstadt buildings",
    ),
    "roof_terracotta": TextureSpec(
        name="Terracotta Roof Tiles",
        base_prompt=(
            "seamless tileable texture, terracotta roof tiles top view, "
            "clay tiles, overlapping, 4k, flat lighting, overhead view, "
            "square format, no shadows"
        ),
        color_source="roof",
        description="Traditional Swiss terracotta roof tiles",
    ),
    "roof_slate": TextureSpec(
        name="Slate Roof Tiles",
        base_prompt=(
            "seamless tileable texture, slate roof tiles top view, "
            "natural slate, dark gray, 4k, flat lighting, overhead view, "
            "square format, no shadows"
        ),
        color_source="roof",
        description="Dark slate roofing tiles",
    ),
    "roof_flat": TextureSpec(
        name="Flat Roof Surface",
        base_prompt=(
            "seamless tileable texture, flat roof membrane surface, "
            "modern building rooftop, gravel or membrane, 4k, flat lighting, "
            "overhead view, square format"
        ),
        color_source="roof",
        description="Modern flat roof surface (gravel or membrane)",
    ),
    "sidewalk_concrete": TextureSpec(
        name="Sidewalk Concrete",
        base_prompt=(
            "seamless tileable texture, European sidewalk paving, "
            "concrete pavers, slightly weathered, 4k, flat lighting, "
            "top view, square format"
        ),
        color_source="ground",
        description="Concrete paver texture for sidewalks",
    ),
}


# =============================================================================
# COLOR ANALYSIS HELPERS
# =============================================================================

def describe_colors(colors: List[Tuple[float, float, float]]) -> str:
    """Convert RGB tuples to natural language color descriptions.

    Args:
        colors: List of RGB tuples in 0-1 range

    Returns:
        Human-readable color description string
    """
    if not colors:
        return "neutral Swiss architectural tones"

    descriptions = []
    for r, g, b in colors[:3]:  # Limit to 3 most dominant colors
        # Determine color name based on RGB values
        brightness = (r + g + b) / 3

        # Check for specific Zurich-typical colors
        if r > 0.7 and g > 0.6 and b > 0.5:
            if r - g > 0.1:
                descriptions.append("warm cream")
            else:
                descriptions.append("cream/beige")
        elif r > 0.5 and g < 0.4 and b < 0.4:
            descriptions.append("terracotta red")
        elif r > 0.6 and g > 0.4 and b < 0.35:
            descriptions.append("warm ochre")
        elif r < 0.35 and g < 0.35 and b < 0.35:
            descriptions.append("dark charcoal")
        elif abs(r - g) < 0.1 and abs(g - b) < 0.1:
            # Grayscale
            if brightness > 0.7:
                descriptions.append("light gray")
            elif brightness > 0.4:
                descriptions.append(f"medium gray ({int(brightness * 100)}%)")
            else:
                descriptions.append("dark slate gray")
        elif g > r and g > b:
            descriptions.append("greenish-gray")
        else:
            # Fallback to RGB description
            descriptions.append(f"RGB({int(r*255)},{int(g*255)},{int(b*255)})")

    return ", ".join(descriptions)


def rgb_to_hex(color: Tuple[float, float, float]) -> str:
    """Convert RGB 0-1 tuple to hex color string."""
    r, g, b = [int(c * 255) for c in color]
    return f"#{r:02x}{g:02x}{b:02x}"


# =============================================================================
# SATELLITE ANALYSIS
# =============================================================================

def analyze_satellite_for_textures(
    satellite_tile: NDArray[np.uint8],
) -> Dict[str, any]:
    """
    Analyze satellite imagery to extract color palette and style hints.

    Uses the existing VisionBlenderGenerator infrastructure when available,
    or falls back to direct image analysis.

    Args:
        satellite_tile: Satellite image array (H, W, 3) uint8

    Returns:
        Dictionary with:
        - roof_colors: List of dominant roof RGB tuples (0-1 range)
        - ground_colors: List of dominant ground RGB tuples (0-1 range)
        - season: Detected season string
        - weather: Detected weather string
        - time_of_day: Detected time of day string
    """
    try:
        # Try to use the full VisionBlenderGenerator for LLM-based analysis
        from .vision_blender import VisionBlenderGenerator

        generator = VisionBlenderGenerator()
        analysis = generator._analyze_satellite(satellite_tile)

        return {
            "roof_colors": list(analysis.dominant_roof_colors),
            "ground_colors": list(analysis.dominant_ground_colors),
            "season": analysis.apparent_season,
            "weather": analysis.weather,
            "time_of_day": analysis.time_of_day,
            "observations": analysis.observations,
        }
    except Exception as e:
        # Fallback to simple histogram-based color extraction
        print(f"VisionBlenderGenerator not available ({e}), using fallback analysis")
        return _analyze_satellite_fallback(satellite_tile)


def _analyze_satellite_fallback(
    satellite_tile: NDArray[np.uint8],
) -> Dict[str, any]:
    """Fallback satellite analysis using simple color extraction.

    Extracts dominant colors by sampling and clustering.
    """
    # Convert to float 0-1 range
    img = satellite_tile.astype(np.float32) / 255.0

    # Sample pixels for analysis (center region for buildings)
    h, w = img.shape[:2]
    center_region = img[h//4:3*h//4, w//4:3*w//4]

    # Extract dominant colors using simple binning
    # Reshape to pixel list
    pixels = center_region.reshape(-1, 3)

    # Simple color quantization
    from collections import Counter

    # Quantize to fewer colors
    quantized = (pixels * 8).astype(int)  # 8 levels per channel
    color_tuples = [tuple(c) for c in quantized]
    color_counts = Counter(color_tuples)

    # Get top colors and convert back to 0-1 range
    top_colors = []
    for color, _ in color_counts.most_common(5):
        rgb = tuple(c / 8.0 for c in color)
        top_colors.append(rgb)

    # Heuristically separate roof (typically darker/redder) from ground colors
    roof_colors = [c for c in top_colors if c[0] > 0.4 or sum(c) < 1.2][:3]
    ground_colors = [c for c in top_colors if c not in roof_colors][:3]

    # Fallback defaults if extraction failed
    if not roof_colors:
        roof_colors = [(0.55, 0.35, 0.28)]  # Terracotta
    if not ground_colors:
        ground_colors = [(0.85, 0.82, 0.78)]  # Cream

    return {
        "roof_colors": roof_colors,
        "ground_colors": ground_colors,
        "season": "summer",  # Default
        "weather": "clear",
        "time_of_day": "afternoon",
        "observations": "Fallback analysis - extracted dominant colors from image",
    }


# =============================================================================
# PROMPT BUILDING
# =============================================================================

def build_informed_prompt(
    texture_spec: TextureSpec,
    satellite_analysis: Dict[str, any],
) -> str:
    """
    Build a texture generation prompt informed by satellite analysis.

    Injects real Zurich colors and atmospheric conditions into the base prompt.

    Args:
        texture_spec: The texture specification with base prompt
        satellite_analysis: Analysis dict from analyze_satellite_for_textures

    Returns:
        Complete prompt string for Gemini
    """
    # Extract relevant colors based on texture type
    if texture_spec.color_source == "roof":
        colors = satellite_analysis.get("roof_colors", [])
    else:
        colors = satellite_analysis.get("ground_colors", [])

    color_desc = describe_colors(colors) if colors else ""

    # Build the informed prompt
    prompt_parts = [texture_spec.base_prompt]

    if color_desc:
        prompt_parts.append(f"Color palette should closely match: {color_desc}")

    # Add color hex codes for precision
    if colors:
        hex_colors = [rgb_to_hex(c) for c in colors[:3]]
        prompt_parts.append(f"Use these exact tones: {', '.join(hex_colors)}")

    # Seasonal adjustments
    season = satellite_analysis.get("season", "summer")
    if season == "winter":
        prompt_parts.append("subtle weathering, cool tones, slight frost texture")
    elif season == "autumn":
        prompt_parts.append("warm earthy tones, slight weathering from rain")
    elif season == "spring":
        prompt_parts.append("fresh clean appearance, slight moisture marks")

    # Weather-based adjustments
    weather = satellite_analysis.get("weather", "clear")
    if weather == "overcast":
        prompt_parts.append("muted tones, diffuse appearance")

    # Final instructions for seamlessness
    prompt_parts.append(
        "CRITICAL: The texture must be perfectly seamless and tileable. "
        "Edges must wrap seamlessly when tiled. No visible seams."
    )

    return ", ".join(prompt_parts)


# =============================================================================
# GEMINI API INTEGRATION
# =============================================================================

def _call_gemini_for_texture(
    prompt: str,
    reference_image: Optional[NDArray[np.uint8]] = None,
    temperature: float = 0.6,
    timeout: int = 180,
) -> bytes:
    """
    Call Gemini 2.5 Flash Image API to generate a texture.

    Args:
        prompt: Text prompt describing the texture
        reference_image: Optional satellite crop to condition generation
        temperature: Generation temperature (lower = more consistent)
        timeout: Request timeout in seconds

    Returns:
        PNG image data as bytes

    Raises:
        ValueError: If API key not found or generation fails
    """
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "Texture generation requires Google AI API key. "
            "Set GOOGLE_API_KEY environment variable."
        )

    # Use Gemini 2.5 Flash Image model
    model = "models/gemini-2.5-flash-image"
    api_base = "https://generativelanguage.googleapis.com/v1beta"
    url = f"{api_base}/{model}:generateContent?key={api_key}"

    # Build request parts
    parts = []

    # Add reference image if provided
    if reference_image is not None:
        # Convert to base64
        img = Image.fromarray(reference_image)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")

        parts.append({
            "inline_data": {
                "mime_type": "image/png",
                "data": b64_data,
            }
        })

        # Adjust prompt for image conditioning
        prompt = (
            f"Study the reference image for color palette and style. "
            f"Then generate: {prompt}"
        )

    # Add text prompt
    parts.append({"text": prompt})

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["image", "text"],
            "temperature": temperature,
        }
    }

    # Make API request
    response = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )

    if response.status_code != 200:
        error_detail = response.text[:500] if response.text else "No details"
        raise ValueError(f"Gemini API error {response.status_code}: {error_detail}")

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
                        generated_image = base64.b64decode(b64_data)
                    elif "text" in part:
                        text_response = part["text"]

    if generated_image is None:
        error_msg = "Gemini did not return an image."
        if text_response:
            error_msg += f" Response: {text_response[:200]}"
        raise ValueError(error_msg)

    return generated_image


# =============================================================================
# TEXTURE GENERATION
# =============================================================================

def generate_texture_from_satellite(
    texture_type: str,
    satellite_tile: Optional[NDArray[np.uint8]] = None,
    satellite_analysis: Optional[Dict] = None,
    use_cache: bool = True,
    save_to_assets: bool = True,
) -> Path:
    """
    Generate a texture using Gemini, informed by satellite imagery.

    Args:
        texture_type: Type of texture (e.g., "residential_plaster")
        satellite_tile: Optional satellite image to analyze
        satellite_analysis: Pre-computed analysis (if satellite_tile not provided)
        use_cache: Whether to use cached textures
        save_to_assets: Whether to save to assets directory

    Returns:
        Path to generated texture file

    Raises:
        ValueError: If texture_type is unknown
    """
    # Validate texture type
    if texture_type not in TEXTURE_SPECS:
        available = ", ".join(sorted(TEXTURE_SPECS.keys()))
        raise ValueError(f"Unknown texture type '{texture_type}'. Available: {available}")

    texture_spec = TEXTURE_SPECS[texture_type]

    # Get or compute satellite analysis
    if satellite_analysis is None and satellite_tile is not None:
        satellite_analysis = analyze_satellite_for_textures(satellite_tile)
    elif satellite_analysis is None:
        # Use default Zurich colors
        satellite_analysis = {
            "roof_colors": [(0.55, 0.35, 0.28), (0.45, 0.42, 0.40)],
            "ground_colors": [(0.92, 0.88, 0.82), (0.85, 0.82, 0.78)],
            "season": "summer",
            "weather": "clear",
            "time_of_day": "afternoon",
        }

    # Build informed prompt
    prompt = build_informed_prompt(texture_spec, satellite_analysis)

    # Generate cache key from prompt and analysis
    cache_key = hashlib.md5(
        json.dumps({
            "prompt": prompt,
            "analysis_hash": str(sorted(satellite_analysis.items())),
        }, sort_keys=True).encode()
    ).hexdigest()[:12]

    cache_path = CACHE_DIR / f"{texture_type}_{cache_key}.png"

    # Check cache
    if use_cache and cache_path.exists():
        print(f"  Using cached texture: {cache_path}")
        return cache_path

    print(f"  Generating texture: {texture_type}")
    print(f"    Prompt: {prompt[:100]}...")

    # Generate with Gemini
    start_time = time.time()

    # Optionally pass a crop of the satellite tile as reference
    reference_crop = None
    if satellite_tile is not None:
        # Use center crop as reference
        h, w = satellite_tile.shape[:2]
        crop_size = min(h, w) // 2
        y_start = (h - crop_size) // 2
        x_start = (w - crop_size) // 2
        reference_crop = satellite_tile[y_start:y_start+crop_size, x_start:x_start+crop_size]

    image_data = _call_gemini_for_texture(
        prompt=prompt,
        reference_image=reference_crop,
    )

    elapsed = time.time() - start_time
    print(f"    Generated in {elapsed:.1f}s")

    # Ensure cache directory exists
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(image_data)

    # Also save to assets directory if requested
    if save_to_assets:
        output_path = TEXTURE_DIR / texture_type / "albedo.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_data)
        print(f"    Saved to: {output_path}")

    return cache_path


def generate_all_textures_from_reference(
    reference_satellite: NDArray[np.uint8],
    texture_types: Optional[List[str]] = None,
    use_cache: bool = True,
) -> Dict[str, Path]:
    """
    Generate all texture types using a reference satellite tile.

    The satellite image informs the color palette for all textures,
    ensuring visual consistency with actual Zurich.

    Args:
        reference_satellite: Satellite tile to analyze for colors
        texture_types: List of texture types to generate (default: all)
        use_cache: Whether to use cached textures

    Returns:
        Dict mapping texture type to generated file path
    """
    # Analyze reference satellite once
    print("Analyzing reference satellite tile...")
    analysis = analyze_satellite_for_textures(reference_satellite)

    print(f"  Detected colors:")
    print(f"    Roof: {describe_colors(analysis.get('roof_colors', []))}")
    print(f"    Ground: {describe_colors(analysis.get('ground_colors', []))}")
    print(f"  Season: {analysis.get('season', 'unknown')}")
    print(f"  Weather: {analysis.get('weather', 'unknown')}")

    # Determine which textures to generate
    types_to_generate = texture_types or list(TEXTURE_SPECS.keys())

    print(f"\nGenerating {len(types_to_generate)} textures...")

    generated = {}
    for texture_type in types_to_generate:
        try:
            path = generate_texture_from_satellite(
                texture_type=texture_type,
                satellite_analysis=analysis,
                use_cache=use_cache,
            )
            generated[texture_type] = path
            print(f"  ✓ {texture_type}")
        except Exception as e:
            print(f"  ✗ {texture_type}: {e}")

    return generated


# =============================================================================
# TEXTURE LISTING AND INFO
# =============================================================================

def list_texture_types() -> Dict[str, str]:
    """List all available texture types with descriptions.

    Returns:
        Dict mapping texture type name to description
    """
    return {name: spec.description for name, spec in TEXTURE_SPECS.items()}


def get_texture_spec(texture_type: str) -> TextureSpec:
    """Get the specification for a texture type.

    Args:
        texture_type: Name of the texture type

    Returns:
        TextureSpec dataclass

    Raises:
        ValueError: If texture type not found
    """
    if texture_type not in TEXTURE_SPECS:
        available = ", ".join(sorted(TEXTURE_SPECS.keys()))
        raise ValueError(f"Unknown texture type '{texture_type}'. Available: {available}")
    return TEXTURE_SPECS[texture_type]


def get_cached_texture_path(texture_type: str) -> Optional[Path]:
    """Get path to a cached texture if it exists.

    Args:
        texture_type: Name of the texture type

    Returns:
        Path to texture file or None if not cached
    """
    # Check assets directory first (preferred)
    asset_path = TEXTURE_DIR / texture_type / "albedo.png"
    if asset_path.exists():
        return asset_path

    # Check cache directory
    for cache_file in CACHE_DIR.glob(f"{texture_type}_*.png"):
        return cache_file

    return None


# =============================================================================
# CLI HELPERS
# =============================================================================

def check_api_availability() -> bool:
    """Check if the Google AI API key is available for texture generation.

    Returns:
        True if API key is set
    """
    return bool(
        os.environ.get("GOOGLE_API_KEY") or
        os.environ.get("GEMINI_API_KEY")
    )


def print_status() -> None:
    """Print status of texture generation system."""
    print("\n" + "=" * 60)
    print("Texture Generator Status")
    print("=" * 60)

    if check_api_availability():
        print("\n  API Status: CONFIGURED ✓")
        print("  Google AI API key found.")
    else:
        print("\n  API Status: NOT CONFIGURED ✗")
        print("")
        print("  To enable texture generation:")
        print("  1. Visit https://aistudio.google.com/apikey")
        print("  2. Create an API key")
        print("  3. Set environment variable:")
        print("     export GOOGLE_API_KEY='your-api-key'")

    print("\n  Available Texture Types:")
    for name, desc in list_texture_types().items():
        cached = get_cached_texture_path(name)
        status = "✓ cached" if cached else "  not cached"
        print(f"    {status}  {name}: {desc}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    print_status()
