#!/usr/bin/env python3
"""
Nano Banana Styler with Style Reference

Like nano_styler.py but uses the FIRST generated tile as a style reference
for all subsequent tiles to ensure consistent coloring across the map.

The reference is ONLY for artistic style (colors, shading, mood) -
the geometry always comes from the current input tile.
"""

import argparse
import base64
import io
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
MODEL = "models/gemini-2.5-flash-image"

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

REQUIREMENTS:
1. PRESERVE LAYOUT - Keep the same buildings, streets, and trees in roughly the same positions.
   Don't add or remove structures, but you MAY add artistic imperfection to lines -
   slight wobbles, sketchy strokes, hand-drawn character. The STRUCTURE stays, the LINES can dance.

2. KEEP TOP-DOWN VIEW - Maintain the overhead perspective. No isometric or 3D tilt.

3. TILE EDGES - Keep edge areas consistent for tiling with neighbors.

4. NO TEXT/LABELS - No text, watermarks, or UI elements.

5. OUTPUT SIZE - Return exactly 512×512 pixels.

ARTISTIC FREEDOM: You have FULL creative freedom with:
- Line quality: sketchy, bold, varied pressure, hand-wobbled - make it feel DRAWN
- Colors, lighting, shadows, and atmosphere
- Surface textures, hatching, crosshatching
- Depth through shading - buildings should feel 3D with cast shadows
- Making the scene artistically rich and emotionally resonant

Transform this tile into a beautiful hand-crafted artwork. This is Zurich - draw it with love."""

REFERENCE_PROMPT = """
⚠️ CRITICAL - TWO IMAGES WITH DIFFERENT PURPOSES:

IMAGE 1 = STYLE REFERENCE ONLY
- Extract ONLY: colors, shading style, line quality, artistic mood
- DO NOT COPY: any buildings, streets, trees, or shapes
- This is a DIFFERENT part of the city - ignore its geography entirely
- Think of it as a "color swatch" or "mood board" - not a template

IMAGE 2 = YOUR ACTUAL INPUT (DRAW THIS!)
- This is the tile you must style
- ALL buildings, streets, and trees come from THIS image
- The output must show EXACTLY these shapes, not the reference shapes
- If you see a park here, draw a park. If you see dense buildings, draw those.

THE TEST: Your output should look NOTHING like Image 1's layout.
It should have Image 1's COLORS applied to Image 2's BUILDINGS.

WHY THIS MATTERS: These tiles form a map. Each tile shows a different neighborhood.
If you copy Image 1's geometry, the map will be broken with repeated areas.
"""


def encode_image(image_path: Path) -> str:
    """Encode image to base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def encode_pil_image(img: Image.Image, format: str = "PNG") -> str:
    """Encode PIL image to base64."""
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def generate_styled_tile(
    input_image: Path,
    user_prompt: str,
    api_key: str,
    temperature: float = 0.5,
    reference_image: Path = None,
    quiet: bool = False,
) -> bytes:
    """Generate a styled tile using Gemini, optionally with a style reference."""

    parts = []

    # Build the prompt
    if reference_image:
        # With reference: two images
        full_prompt = f"""{SYSTEM_PROMPT}
{REFERENCE_PROMPT}

IMAGES PROVIDED:
- IMAGE 1: Style reference (colors/mood ONLY - ignore its buildings!)
- IMAGE 2: THE TILE TO STYLE (draw THESE buildings with IMAGE 1's colors)

YOUR OUTPUT: Must show IMAGE 2's exact layout colored like IMAGE 1.
Do NOT reproduce IMAGE 1's buildings - they are from a different area!

{user_prompt}"""

        parts.append({"text": full_prompt})

        # Add reference image first
        ref_b64 = encode_image(reference_image)
        parts.append({
            "inline_data": {
                "mime_type": "image/webp" if str(reference_image).endswith('.webp') else "image/png",
                "data": ref_b64,
            }
        })

        # Add input image second
        input_b64 = encode_image(input_image)
        parts.append({
            "inline_data": {
                "mime_type": "image/webp" if str(input_image).endswith('.webp') else "image/png",
                "data": input_b64,
            }
        })
    else:
        # No reference: single image (first tile)
        full_prompt = f"""{SYSTEM_PROMPT}

This is the FIRST tile of the map - establish the artistic style that subsequent tiles will match.

{user_prompt}"""

        parts.append({"text": full_prompt})

        input_b64 = encode_image(input_image)
        parts.append({
            "inline_data": {
                "mime_type": "image/webp" if str(input_image).endswith('.webp') else "image/png",
                "data": input_b64,
            }
        })

    url = f"{API_BASE}/{MODEL}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["image", "text"],
            "temperature": temperature,
        },
    }

    if not quiet:
        ref_info = " (with style ref)" if reference_image else " (first tile - establishing style)"
        print(f"  Sending request{ref_info}...")

    response = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=180,
    )

    if response.status_code != 200:
        raise Exception(f"API error {response.status_code}: {response.text[:500]}")

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise Exception("No candidates in response")

    parts = candidates[0].get("content", {}).get("parts", [])
    for part in parts:
        if "inlineData" in part:
            image_data = part["inlineData"]["data"]
            return base64.b64decode(image_data)

    raise Exception("No image in response")


def process_batch_with_reference(
    source_dir: Path,
    style_name: str,
    prompt: str,
    api_key: str,
    temperature: float = 0.5,
    display_name: str = None,
    description: str = None,
    colors: list = None,
):
    """Process all tiles, using first generated tile as style reference for rest."""

    # Find all tiles
    tiles = sorted(source_dir.glob("**/*.webp"))
    if not tiles:
        print(f"No tiles found in {source_dir}")
        return

    output_dir = Path(f"public/tiles/{style_name}")
    output_dir.mkdir(parents=True, exist_ok=True)

    total = len(tiles)
    generated = 0
    failed = 0
    reference_tile = None  # Will be set after first tile is generated

    print(f"\n🍌 Nano Banana Styler with Reference")
    print(f"{'─' * 50}")
    print(f"  Source:     {source_dir}")
    print(f"  Style:      {style_name}")
    print(f"  Tiles:      {total}")
    print(f"  Prompt:     {prompt[:60]}{'...' if len(prompt) > 60 else ''}")
    print(f"  Output:     {output_dir}")
    print(f"  Mode:       First tile sets style, rest use it as reference")
    print(f"{'─' * 50}\n")

    for i, tile_path in enumerate(tiles, 1):
        # Extract coordinate from path
        parts = tile_path.parts
        z_idx = next((j for j, p in enumerate(parts) if p.isdigit()), None)
        if z_idx is None:
            continue
        coord = f"{parts[z_idx]}/{parts[z_idx+1]}/{tile_path.stem}"

        output_path = output_dir / f"{coord}.webp"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Skip if already exists
        if output_path.exists():
            print(f"  [{i}/{total}] {coord} - skipped (exists)")
            if reference_tile is None:
                reference_tile = output_path  # Use existing as reference
            continue

        try:
            import time
            start = time.time()

            # Generate with or without reference
            result_bytes = generate_styled_tile(
                input_image=tile_path,
                user_prompt=prompt,
                api_key=api_key,
                temperature=temperature,
                reference_image=reference_tile,  # None for first tile
                quiet=True,
            )

            elapsed = time.time() - start

            # Save result
            img = Image.open(io.BytesIO(result_bytes))
            img.save(output_path, "WEBP", quality=90)

            ref_marker = "★" if reference_tile is None else "→"
            print(f"  [{i}/{total}] {coord} - {ref_marker} generated ({elapsed:.1f}s)")

            # Set reference after first tile
            if reference_tile is None:
                reference_tile = output_path
                print(f"           ↳ Style reference established")

            generated += 1

        except Exception as e:
            print(f"  [{i}/{total}] {coord} - ✗ failed: {e}")
            failed += 1

    # Update manifest
    if generated > 0:
        update_manifest(
            style_name,
            display_name or style_name.replace("-", " ").title(),
            description or prompt[:80],
            colors or ["#2B2B2B", "#FFFFFF", "#808080"],
            output_dir,
        )
        print(f"  Updated manifest: public/tiles/ai-styles.json")

    print(f"\n{'─' * 50}")
    print(f"  ✅ Generated: {generated}/{total} tiles")
    if failed > 0:
        print(f"  ❌ Failed: {failed} tiles")
    print(f"  📁 Output: {output_dir}")
    print(f"  🎨 All tiles use consistent style from first tile")
    print(f"{'─' * 50}\n")


def update_manifest(style_name: str, display_name: str, description: str,
                   colors: list, output_dir: Path):
    """Update ai-styles.json manifest with new style."""
    manifest_path = Path("public/tiles/ai-styles.json")

    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
    else:
        manifest = {"styles": [], "generatedAt": None}

    # Count tiles and find bounds
    tiles = list(output_dir.glob("**/*.webp"))
    if not tiles:
        return

    # Extract bounds from tile coordinates
    x_coords = []
    y_coords = []
    zoom = 16

    for tile in tiles:
        parts = tile.parts
        z_idx = next((j for j, p in enumerate(parts) if p.isdigit()), None)
        if z_idx:
            zoom = int(parts[z_idx])
            x_coords.append(int(parts[z_idx + 1]))
            y_coords.append(int(tile.stem))

    if x_coords and y_coords:
        # Convert tile coords to lat/lng bounds
        def tile_to_lng(x, z):
            return x / (2 ** z) * 360.0 - 180.0

        def tile_to_lat(y, z):
            import math
            n = math.pi - 2.0 * math.pi * y / (2 ** z)
            return math.degrees(math.atan(math.sinh(n)))

        min_x, max_x = min(x_coords), max(x_coords) + 1
        min_y, max_y = min(y_coords), max(y_coords) + 1

        bounds = [
            tile_to_lng(min_x, zoom),
            tile_to_lat(max_y, zoom),
            tile_to_lng(max_x, zoom),
            tile_to_lat(min_y, zoom),
        ]
    else:
        bounds = [8.53, 47.365, 8.555, 47.385]

    # Create/update style entry
    style_entry = {
        "name": style_name,
        "displayName": display_name,
        "description": description,
        "colors": colors,
        "tiles": len(tiles),
        "totalTiles": len(tiles),
        "bounds": bounds,
        "zoom": zoom,
        "generatedAt": datetime.now().isoformat(),
        "generator": "nano-banana-ref",
    }

    # Update or add
    existing_idx = next(
        (i for i, s in enumerate(manifest["styles"]) if s["name"] == style_name),
        None
    )
    if existing_idx is not None:
        manifest["styles"][existing_idx] = style_entry
    else:
        manifest["styles"].append(style_entry)

    manifest["generatedAt"] = datetime.now().isoformat()

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Nano Banana Styler with Reference - First tile sets style for all",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python nano_styler_ref.py \\
    --batch public/tiles/hybrid-golden_hour \\
    --style-name pencil-consistent \\
    --prompt "Hand-drawn pencil sketch with deep shadows"

The first tile is generated without reference (establishing the style).
All subsequent tiles use the first tile as a STYLE REFERENCE for consistency.
The geometry always comes from each input tile - only the artistic style is referenced.
""",
    )

    parser.add_argument("--batch", "-b", type=Path, required=True,
                       help="Source directory for batch processing")
    parser.add_argument("--style-name", "-s", type=str, required=True,
                       help="Style name for output")
    parser.add_argument("--display-name", type=str,
                       help="Display name for manifest")
    parser.add_argument("--description", type=str,
                       help="Description for manifest")
    parser.add_argument("--colors", type=str, nargs="+",
                       help="Color palette (hex values)")
    parser.add_argument("--prompt", "-p", type=str, required=True,
                       help="Style instructions")
    parser.add_argument("--temperature", type=float, default=0.5,
                       help="Temperature (0.0-1.0)")
    parser.add_argument("--api-key", type=str,
                       help="Google AI API key")

    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("GOOGLE_AI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: No API key. Set GOOGLE_AI_API_KEY or use --api-key", file=sys.stderr)
        sys.exit(1)

    process_batch_with_reference(
        source_dir=args.batch,
        style_name=args.style_name,
        prompt=args.prompt,
        api_key=api_key,
        temperature=args.temperature,
        display_name=args.display_name,
        description=args.description,
        colors=args.colors,
    )


if __name__ == "__main__":
    main()
