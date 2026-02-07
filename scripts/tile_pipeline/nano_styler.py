#!/usr/bin/env python3
"""
Nano Banana Tile Styler - CLI for styling tiles with multiple AI providers.

Supports Gemini, OpenAI GPT Image, and other providers via LiteLLM abstraction.

Usage:
    # Single tile (experimentation)
    python scripts/tile_pipeline/nano_styler.py \\
        --tile public/tiles/hybrid-golden_hour/16/34322/22949.webp \\
        --prompt "cyberpunk neon night" \\
        --output output/test.png

    # With specific provider
    python scripts/tile_pipeline/nano_styler.py \\
        --provider openai \\
        --tile public/tiles/hybrid-golden_hour/16/34322/22949.webp \\
        --prompt "cyberpunk neon night"

    # Batch mode (generate full style)
    python scripts/tile_pipeline/nano_styler.py \\
        --batch public/tiles/hybrid-golden_hour \\
        --style-name nano-cyberpunk \\
        --prompt "cyberpunk neon night with glowing rooftops"

    # List available providers
    python scripts/tile_pipeline/nano_styler.py --list-providers

Providers:
    - gemini: Google Gemini 2.5 Flash Image (free tier, GOOGLE_API_KEY)
    - openai: OpenAI GPT Image 1 (paid, OPENAI_API_KEY)
    - openai-1.5: OpenAI GPT Image 1.5 (paid, OPENAI_API_KEY)
    - vertex: Google Vertex AI Gemini (requires GCP project)
    - stability: Stability AI style transfer
"""

import argparse
import base64
import io
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

import requests
from PIL import Image

# Try to import the provider abstraction
PROVIDERS_AVAILABLE = False
try:
    from tile_providers import TileStyler, list_providers, PROVIDER_MODELS
    PROVIDERS_AVAILABLE = True
except ImportError:
    # Fall back to direct API calls for Gemini only
    PROVIDER_MODELS = {"gemini": "direct-api"}


# Gemini API configuration (fallback when litellm not installed)
API_BASE = "https://generativelanguage.googleapis.com/v1beta"
MODEL = "models/gemini-2.5-flash-image"

# System prompt for tile styling
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

# Semantic conditioning prompt addition
SEMANTIC_PROMPT_ADDITION = """

SEMANTIC MAP PROVIDED:
A second image shows a semantic map of the same scene with class-colored elements:
- ROOFTOPS: Red-brown (terracotta = residential), dark gray (slate = historic), medium gray (flat = commercial)
- WATER: Blue areas (lakes, rivers)
- TREES: Green circular shapes
- STREETS: Dark gray strips
- GROUND: Light green grass

Use this semantic map to understand the scene structure. Apply your style consistently
to each element type - all terracotta roofs should receive similar treatment, all water
should look cohesive, etc. The semantic map helps you distinguish between element types
that might look similar in the rendered image."""


def load_image(path: Path) -> bytes:
    """Load an image file and return its bytes."""
    with Image.open(path) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        if img.size != (512, 512):
            img = img.resize((512, 512), Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()


def image_to_base64(image_bytes: bytes) -> str:
    """Convert image bytes to base64 string."""
    return base64.b64encode(image_bytes).decode("utf-8")


def generate_styled_tile_direct(
    tile_bytes: bytes,
    prompt: str,
    mood_bytes: Optional[bytes] = None,
    semantic_bytes: Optional[bytes] = None,
    temperature: float = 0.5,
    api_key: Optional[str] = None,
    quiet: bool = False,
) -> bytes:
    """Generate a styled tile using direct Gemini API calls (fallback)."""
    api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("API key required. Set GOOGLE_API_KEY environment variable.")

    tile_b64 = image_to_base64(tile_bytes)

    parts = [{"inline_data": {"mime_type": "image/png", "data": tile_b64}}]

    # Add semantic map if provided
    if semantic_bytes:
        semantic_b64 = image_to_base64(semantic_bytes)
        parts.append({"inline_data": {"mime_type": "image/png", "data": semantic_b64}})

    user_prompt = f"Now apply this style:\n{prompt}"
    if mood_bytes:
        mood_b64 = image_to_base64(mood_bytes)
        parts.append({"inline_data": {"mime_type": "image/png", "data": mood_b64}})
        user_prompt += "\n\nUse the color palette and mood from the reference image provided."

    # Build full prompt with semantic addition if semantic map provided
    base_prompt = SYSTEM_PROMPT
    if semantic_bytes:
        base_prompt += SEMANTIC_PROMPT_ADDITION
    full_prompt = f"{base_prompt}\n\n{user_prompt}"
    parts.append({"text": full_prompt})

    url = f"{API_BASE}/{MODEL}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["image", "text"],
            "temperature": temperature,
        },
    }

    if not quiet:
        print(f"  Sending request to {MODEL}...")

    response = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=180,
    )

    if response.status_code != 200:
        error_detail = response.text[:500] if response.text else "No details"
        raise ValueError(f"Gemini API error {response.status_code}: {error_detail}")

    result = response.json()

    if "candidates" in result:
        for candidate in result["candidates"]:
            if "content" in candidate and "parts" in candidate["content"]:
                for part in candidate["content"]["parts"]:
                    if "inlineData" in part:
                        return base64.b64decode(part["inlineData"]["data"])

    raise ValueError("Gemini did not return an image in the response")


def generate_styled_tile(
    tile_path: Path,
    prompt: str,
    provider: str = "gemini",
    mood_path: Optional[Path] = None,
    semantic_path: Optional[Path] = None,
    temperature: float = 0.5,
    api_key: Optional[str] = None,
    quiet: bool = False,
) -> bytes:
    """Generate a styled tile using the specified provider.

    Args:
        tile_path: Path to the input tile image
        prompt: Style instructions
        provider: AI provider to use
        mood_path: Optional path to mood/color reference image
        semantic_path: Optional path to semantic conditioning tile
        temperature: Creativity parameter (0.0-1.0)
        api_key: Optional API key override
        quiet: Suppress progress output

    Returns:
        Styled tile image bytes
    """
    tile_bytes = load_image(tile_path)
    mood_bytes = load_image(mood_path) if mood_path else None
    semantic_bytes = load_image(semantic_path) if semantic_path else None

    # Use LiteLLM if available
    if PROVIDERS_AVAILABLE:
        if not quiet:
            print(f"  Using provider: {provider} ({PROVIDER_MODELS.get(provider, 'unknown')})")
            if semantic_bytes:
                print(f"  Semantic conditioning: enabled")

        styler = TileStyler(provider=provider, api_key=api_key)
        result = styler.style_tile(
            tile_bytes=tile_bytes,
            prompt=prompt,
            mood_bytes=mood_bytes,
            temperature=temperature,
        )
        return result.image_bytes

    # Fall back to direct API for Gemini only
    if provider != "gemini":
        raise ValueError(
            f"Provider '{provider}' requires litellm. Install with: pip install litellm"
        )

    return generate_styled_tile_direct(
        tile_bytes=tile_bytes,
        prompt=prompt,
        mood_bytes=mood_bytes,
        semantic_bytes=semantic_bytes,
        temperature=temperature,
        api_key=api_key,
        quiet=quiet,
    )


def find_tiles(source_dir: Path) -> Iterator[tuple[Path, str]]:
    """Find all tiles in a directory and yield (path, coord) tuples."""
    for webp_file in sorted(source_dir.rglob("*.webp")):
        # Skip backup files
        if "_backup" in webp_file.name:
            continue
        # Extract coordinate from path: .../16/34322/22949.webp -> 16/34322/22949
        parts = webp_file.parts
        try:
            # Find the zoom level (should be a number like 16)
            for i, part in enumerate(parts):
                if part.isdigit() and len(part) <= 2:  # zoom levels are 1-2 digits
                    coord = "/".join(parts[i:]).replace(".webp", "")
                    yield webp_file, coord
                    break
        except (IndexError, ValueError):
            continue


def update_manifest(style_name: str, display_name: str, description: str,
                   tiles_count: int, bounds: tuple, colors: list[str],
                   provider: str = "gemini"):
    """Update ai-styles.json manifest with new style."""
    manifest_path = Path("public/tiles/ai-styles.json")

    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
    else:
        manifest = {"styles": [], "generatedAt": "", "defaultBounds": list(bounds), "defaultZoom": 16}

    # Remove existing style with same name
    manifest["styles"] = [s for s in manifest["styles"] if s["name"] != style_name]

    # Add new style
    manifest["styles"].append({
        "name": style_name,
        "displayName": display_name,
        "description": description,
        "colors": colors,
        "tiles": tiles_count,
        "totalTiles": tiles_count,
        "bounds": list(bounds),
        "zoom": 16,
        "generatedAt": datetime.now().isoformat(),
        "generator": f"nano-banana-{provider}",
    })

    manifest["generatedAt"] = datetime.now().isoformat()

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"  Updated manifest: {manifest_path}")


def run_batch(
    source_dir: Path,
    style_name: str,
    prompt: str,
    provider: str = "gemini",
    temperature: float = 0.5,
    mood_path: Optional[Path] = None,
    api_key: Optional[str] = None,
    display_name: Optional[str] = None,
    description: Optional[str] = None,
    colors: Optional[list[str]] = None,
):
    """Process all tiles in a directory."""
    output_dir = Path(f"public/tiles/{style_name}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect all tiles
    tiles = list(find_tiles(source_dir))
    total = len(tiles)

    if total == 0:
        print(f"❌ No tiles found in {source_dir}")
        sys.exit(1)

    print(f"\n🍌 Nano Banana Batch Styler")
    print(f"{'─' * 50}")
    print(f"  Provider:   {provider}")
    print(f"  Source:     {source_dir}")
    print(f"  Style:      {style_name}")
    print(f"  Tiles:      {total}")
    print(f"  Prompt:     {prompt[:60]}{'...' if len(prompt) > 60 else ''}")
    print(f"  Output:     {output_dir}")
    print(f"{'─' * 50}\n")

    # Track bounds for manifest
    min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
    generated = 0
    failed = 0

    for i, (tile_path, coord) in enumerate(tiles, 1):
        # Parse coord for bounds tracking
        parts = coord.split("/")
        if len(parts) == 3:
            z, x, y = int(parts[0]), int(parts[1]), int(parts[2])
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)

        output_path = output_dir / f"{coord}.webp"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Skip if already exists
        if output_path.exists():
            print(f"  [{i}/{total}] {coord} - skipped (exists)")
            generated += 1
            continue

        print(f"  [{i}/{total}] {coord} - generating...", end=" ", flush=True)

        try:
            start = time.time()
            result_bytes = generate_styled_tile(
                tile_path=tile_path,
                prompt=prompt,
                provider=provider,
                mood_path=mood_path,
                temperature=temperature,
                api_key=api_key,
                quiet=True,
            )

            # Convert to WebP for consistency
            img = Image.open(io.BytesIO(result_bytes))
            img.save(output_path, "WEBP", quality=90)

            elapsed = time.time() - start
            print(f"✓ ({elapsed:.1f}s)")
            generated += 1

        except Exception as e:
            print(f"✗ Error: {e}")
            failed += 1
            continue

    # Calculate bounds in WGS84
    # Tile to lat/lng conversion
    import math
    def tile_to_latlng(x: int, y: int, z: int) -> tuple[float, float]:
        n = 2 ** z
        lon = x / n * 360.0 - 180.0
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
        return lat, lon

    if min_x != float('inf'):
        _, west = tile_to_latlng(min_x, min_y, 16)
        north, _ = tile_to_latlng(min_x, min_y, 16)
        _, east = tile_to_latlng(max_x + 1, max_y + 1, 16)
        south, _ = tile_to_latlng(max_x + 1, max_y + 1, 16)
        bounds = (west, south, east, north)
    else:
        bounds = (8.53, 47.365, 8.555, 47.385)  # Default Zurich bounds

    # Update manifest
    update_manifest(
        style_name=style_name,
        display_name=display_name or style_name.replace("-", " ").title(),
        description=description or prompt[:100],
        tiles_count=generated,
        bounds=bounds,
        colors=colors or ["#FF00FF", "#00FFFF", "#1a0a2e"],
        provider=provider,
    )

    print(f"\n{'─' * 50}")
    print(f"  ✅ Generated: {generated}/{total} tiles")
    if failed:
        print(f"  ❌ Failed: {failed} tiles")
    print(f"  📁 Output: {output_dir}")
    print(f"{'─' * 50}\n")


def run_single(args):
    """Run single tile mode."""
    if not args.tile.exists():
        print(f"Error: Tile not found: {args.tile}", file=sys.stderr)
        sys.exit(1)

    if args.mood and not args.mood.exists():
        print(f"Error: Mood image not found: {args.mood}", file=sys.stderr)
        sys.exit(1)

    if args.semantic and not args.semantic.exists():
        print(f"Error: Semantic tile not found: {args.semantic}", file=sys.stderr)
        sys.exit(1)

    if args.output is None:
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = output_dir / f"styled_{timestamp}.png"

    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n🍌 Nano Banana Tile Styler")
    print(f"{'─' * 40}")
    print(f"  Provider: {args.provider}")
    print(f"  Tile:     {args.tile}")
    print(f"  Prompt:   {args.prompt[:50]}{'...' if len(args.prompt) > 50 else ''}")
    if args.mood:
        print(f"  Mood:     {args.mood}")
    if args.semantic:
        print(f"  Semantic: {args.semantic}")
    print(f"  Temp:     {args.temperature}")
    print(f"  Output:   {args.output}")
    print(f"{'─' * 40}")

    try:
        result_bytes = generate_styled_tile(
            tile_path=args.tile,
            prompt=args.prompt,
            provider=args.provider,
            mood_path=args.mood,
            semantic_path=args.semantic,
            temperature=args.temperature,
            api_key=args.api_key,
        )

        with open(args.output, "wb") as f:
            f.write(result_bytes)

        print(f"\n✅ Saved to: {args.output}")
        print(f"   Open with: open {args.output}")

    except ValueError as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("\n❌ Error: Request timed out (180s)", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Nano Banana Tile Styler - Style tiles with multiple AI providers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single tile with Gemini (default)
  python scripts/tile_pipeline/nano_styler.py \\
      --tile public/tiles/hybrid-golden_hour/16/34322/22949.webp \\
      --prompt "cyberpunk neon night"

  # Single tile with OpenAI
  python scripts/tile_pipeline/nano_styler.py \\
      --provider openai \\
      --tile public/tiles/hybrid-golden_hour/16/34322/22949.webp \\
      --prompt "cyberpunk neon night"

  # Batch mode
  python scripts/tile_pipeline/nano_styler.py \\
      --batch public/tiles/hybrid-golden_hour \\
      --style-name nano-cyberpunk \\
      --prompt "cyberpunk neon night with glowing rooftops"

  # List providers
  python scripts/tile_pipeline/nano_styler.py --list-providers

Environment variables:
  GOOGLE_API_KEY or GEMINI_API_KEY - for Gemini provider
  OPENAI_API_KEY - for OpenAI provider
        """,
    )

    # Provider selection
    parser.add_argument(
        "--provider", "-P",
        type=str,
        default="gemini",
        choices=list(PROVIDER_MODELS.keys()),
        help="AI provider to use (default: gemini)"
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="List available providers and exit"
    )

    # Single tile mode
    parser.add_argument("--tile", "-t", type=Path, help="Single tile to process")
    parser.add_argument("--output", "-o", type=Path, help="Output path for single tile")

    # Batch mode
    parser.add_argument("--batch", "-b", type=Path, help="Source directory for batch processing")
    parser.add_argument("--style-name", "-s", type=str, help="Style name for batch output")
    parser.add_argument("--display-name", type=str, help="Display name for manifest")
    parser.add_argument("--description", type=str, help="Description for manifest")
    parser.add_argument("--colors", type=str, nargs="+", help="Color palette (hex values)")

    # Common options
    parser.add_argument("--prompt", "-p", type=str, help="Style instructions")
    parser.add_argument("--mood", "-m", type=Path, help="Mood/color reference image")
    parser.add_argument("--semantic", type=Path, help="Semantic conditioning tile (from render-semantic)")
    parser.add_argument("--temperature", type=float, default=0.5, help="Temperature (0.0-1.0)")
    parser.add_argument("--api-key", type=str, help="API key (overrides environment variable)")

    args = parser.parse_args()

    # Handle --list-providers
    if args.list_providers:
        print("\n📋 Available Providers:")
        print(f"{'─' * 50}")
        for provider_id, model in PROVIDER_MODELS.items():
            env_var = {
                "gemini": "GOOGLE_API_KEY",
                "openai": "OPENAI_API_KEY",
                "openai-1.5": "OPENAI_API_KEY",
                "vertex": "GOOGLE_APPLICATION_CREDENTIALS",
                "stability": "STABILITY_API_KEY",
            }.get(provider_id, "?")
            print(f"  {provider_id:12} → {model}")
            print(f"                 Env: {env_var}")
        if not PROVIDERS_AVAILABLE:
            print(f"\n⚠️  Note: litellm not installed. Only 'gemini' available via direct API.")
            print(f"   Install with: pip install litellm")
        print(f"{'─' * 50}\n")
        return

    # Validate mode
    if not args.tile and not args.batch:
        print("Error: Either --tile or --batch required", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    if not args.prompt:
        print("Error: --prompt is required", file=sys.stderr)
        sys.exit(1)

    # Determine mode
    if args.batch:
        if not args.style_name:
            print("Error: --style-name required for batch mode", file=sys.stderr)
            sys.exit(1)
        run_batch(
            source_dir=args.batch,
            style_name=args.style_name,
            prompt=args.prompt,
            provider=args.provider,
            temperature=args.temperature,
            mood_path=args.mood,
            api_key=args.api_key,
            display_name=args.display_name,
            description=args.description,
            colors=args.colors,
        )
    elif args.tile:
        run_single(args)


if __name__ == "__main__":
    main()
