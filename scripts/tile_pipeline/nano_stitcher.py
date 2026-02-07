#!/usr/bin/env python3
"""
Nano Banana Context-Aware Tile Stitcher - Generate consistent tiles with seamless edges.

Solves the seam problem by using context-aware stitching:
- 2-tile horizontal context (1024×512) for seed and horizontal expansion
- L-shaped 3-tile context (1024×1024) for vertical expansion

Processing Order:
    For a 4×3 grid:
         x=0   x=1   x=2   x=3
    y=0  [1]═══[2]───[3]───[4]   ← Horizontal: seed pair, then expand right
    y=1  [5]   [6]   [7]   [8]   ← L-shaped: use above + left for each
    y=2  [9]  [10]  [11]  [12]

Usage:
    python scripts/tile_pipeline/nano_stitcher.py \\
        --source public/tiles/hybrid-golden_hour \\
        --style-name nano-winter-stitched \\
        --prompt "Winter snow scene with white rooftops"
"""

import argparse
import base64
import io
import json
import math
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterator

import requests
from PIL import Image

# Gemini API configuration
API_BASE = "https://generativelanguage.googleapis.com/v1beta"
MODEL = "models/gemini-2.5-flash-image"

# Tile dimensions
TILE_SIZE = 512
HORIZONTAL_SIZE = (1024, 512)  # 2 tiles side-by-side
GRID_2X2_SIZE = (1024, 1024)   # 2×2 tiles

# Base system prompt (shared understanding of map tiles)
BASE_PROMPT = """You are a cinematic map tile artist styling urban scenes from a STRAIGHT-DOWN TOP VIEW.

CAMERA: 90° nadir view - looking STRAIGHT DOWN. NOT isometric. Think Google Maps satellite.

SCENE ELEMENTS (from above):
- BUILDINGS: Flat rooftop shapes (rectangles, L-shapes). You see ROOFS, not walls.
- TREES: Round/fluffy circles - tree canopies from above.
- STREETS: Flat gray/brown strips between buildings.
- GRASS/PARKS: Flat green areas.

CRITICAL:
1. PRESERVE GEOMETRY - All shapes/positions stay EXACTLY the same.
2. KEEP TOP-DOWN VIEW - No perspective, no tilt, no isometric angle.
3. NO TEXT/LABELS - No watermarks or UI elements."""


# =============================================================================
# IMAGE STITCHING & CUTTING FUNCTIONS
# =============================================================================

def stitch_horizontal(img_a: Image.Image, img_b: Image.Image) -> Image.Image:
    """Combine 2 tiles side-by-side → 1024×512."""
    result = Image.new("RGB", HORIZONTAL_SIZE)
    result.paste(img_a.resize((TILE_SIZE, TILE_SIZE)), (0, 0))
    result.paste(img_b.resize((TILE_SIZE, TILE_SIZE)), (TILE_SIZE, 0))
    return result


def stitch_2x2(
    top_left: Image.Image,
    top_right: Image.Image,
    bottom_left: Image.Image,
    bottom_right: Image.Image,
) -> Image.Image:
    """Combine 4 tiles in 2×2 grid → 1024×1024."""
    result = Image.new("RGB", GRID_2X2_SIZE)
    result.paste(top_left.resize((TILE_SIZE, TILE_SIZE)), (0, 0))
    result.paste(top_right.resize((TILE_SIZE, TILE_SIZE)), (TILE_SIZE, 0))
    result.paste(bottom_left.resize((TILE_SIZE, TILE_SIZE)), (0, TILE_SIZE))
    result.paste(bottom_right.resize((TILE_SIZE, TILE_SIZE)), (TILE_SIZE, TILE_SIZE))
    return result


def cut_horizontal(img: Image.Image) -> tuple[Image.Image, Image.Image]:
    """Split 1024×512 → 2 tiles (left, right)."""
    # Ensure correct size
    if img.size != HORIZONTAL_SIZE:
        img = img.resize(HORIZONTAL_SIZE, Image.LANCZOS)

    left = img.crop((0, 0, TILE_SIZE, TILE_SIZE))
    right = img.crop((TILE_SIZE, 0, TILE_SIZE * 2, TILE_SIZE))
    return left, right


def cut_2x2(img: Image.Image) -> tuple[Image.Image, Image.Image, Image.Image, Image.Image]:
    """Split 1024×1024 → 4 tiles (top_left, top_right, bottom_left, bottom_right)."""
    # Ensure correct size
    if img.size != GRID_2X2_SIZE:
        img = img.resize(GRID_2X2_SIZE, Image.LANCZOS)

    top_left = img.crop((0, 0, TILE_SIZE, TILE_SIZE))
    top_right = img.crop((TILE_SIZE, 0, TILE_SIZE * 2, TILE_SIZE))
    bottom_left = img.crop((0, TILE_SIZE, TILE_SIZE, TILE_SIZE * 2))
    bottom_right = img.crop((TILE_SIZE, TILE_SIZE, TILE_SIZE * 2, TILE_SIZE * 2))
    return top_left, top_right, bottom_left, bottom_right


def load_image(path: Path) -> Image.Image:
    """Load an image file and convert to RGB."""
    with Image.open(path) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        return img.copy()


def image_to_bytes(img: Image.Image, format: str = "PNG") -> bytes:
    """Convert PIL Image to bytes."""
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    return buffer.getvalue()


def image_to_base64(img: Image.Image) -> str:
    """Convert PIL Image to base64 string."""
    return base64.b64encode(image_to_bytes(img)).decode("utf-8")


# =============================================================================
# TILE GRID COLLECTION
# =============================================================================

def collect_tile_grid(source_dir: Path) -> dict[int, dict[int, Path]]:
    """
    Organize tiles into 2D grid by x,y coordinates.

    Returns: {y: {x: path}} nested dict for easy grid access.
    """
    grid: dict[int, dict[int, Path]] = defaultdict(dict)

    for webp_file in source_dir.rglob("*.webp"):
        # Skip backup files
        if "_backup" in webp_file.name:
            continue

        try:
            # Extract coordinates: .../16/34322/22949.webp
            parts = webp_file.parts
            for i, part in enumerate(parts):
                if part.isdigit() and len(part) <= 2:  # zoom level
                    z = int(part)
                    x = int(parts[i + 1])
                    y = int(parts[i + 2].replace(".webp", ""))
                    grid[y][x] = webp_file
                    break
        except (IndexError, ValueError):
            continue

    return grid


def get_grid_bounds(grid: dict[int, dict[int, Path]]) -> tuple[int, int, int, int]:
    """Get min/max x,y from grid. Returns (min_x, min_y, max_x, max_y)."""
    all_y = list(grid.keys())
    all_x = [x for y_dict in grid.values() for x in y_dict.keys()]

    if not all_y or not all_x:
        raise ValueError("Empty grid")

    return min(all_x), min(all_y), max(all_x), max(all_y)


# =============================================================================
# GEMINI API CALLS
# =============================================================================

def call_gemini(
    image: Image.Image,
    prompt: str,
    expected_size: tuple[int, int],
    temperature: float = 0.3,
    api_key: str | None = None,
) -> Image.Image:
    """Call Gemini API with image and prompt, return styled image."""
    api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("API key required. Set GOOGLE_API_KEY environment variable.")

    img_b64 = image_to_base64(image)

    url = f"{API_BASE}/{MODEL}:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "image/png", "data": img_b64}},
                {"text": prompt},
            ]
        }],
        "generationConfig": {
            "responseModalities": ["image", "text"],
            "temperature": temperature,
        },
    }

    response = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=300,  # 5 minutes for larger images
    )

    if response.status_code != 200:
        error_detail = response.text[:500] if response.text else "No details"
        raise ValueError(f"Gemini API error {response.status_code}: {error_detail}")

    result = response.json()

    # Extract image from response
    if "candidates" in result:
        for candidate in result["candidates"]:
            if "content" in candidate and "parts" in candidate["content"]:
                for part in candidate["content"]["parts"]:
                    if "inlineData" in part:
                        img_bytes = base64.b64decode(part["inlineData"]["data"])
                        img = Image.open(io.BytesIO(img_bytes))
                        if img.mode != "RGB":
                            img = img.convert("RGB")
                        # Resize to expected if different
                        if img.size != expected_size:
                            img = img.resize(expected_size, Image.LANCZOS)
                        return img

    raise ValueError("Gemini did not return an image in the response")


# =============================================================================
# GENERATION FUNCTIONS WITH CONTEXT
# =============================================================================

def generate_seed_pair(
    raw_a: Image.Image,
    raw_b: Image.Image,
    user_prompt: str,
    temperature: float = 0.3,
    api_key: str | None = None,
) -> tuple[Image.Image, Image.Image]:
    """
    Style 2 tiles together as seed pair.
    Returns (styled_a, styled_b).
    """
    stitched = stitch_horizontal(raw_a, raw_b)

    prompt = f"""{BASE_PROMPT}

You are styling 2 map tiles side-by-side (1024×512 total).

Style BOTH tiles with consistent colors, lighting, and atmosphere.
They must blend seamlessly at the center edge.

Style: {user_prompt}

Return exactly 1024×512 pixels."""

    result = call_gemini(stitched, prompt, HORIZONTAL_SIZE, temperature, api_key)
    return cut_horizontal(result)


def generate_horizontal(
    styled_left: Image.Image,
    raw_right: Image.Image,
    user_prompt: str,
    temperature: float = 0.3,
    api_key: str | None = None,
) -> Image.Image:
    """
    Expand horizontally: style right tile to match styled left.
    Returns styled right tile only.
    """
    stitched = stitch_horizontal(styled_left, raw_right)

    prompt = f"""{BASE_PROMPT}

You are styling a map tile to match its neighbor (1024×512 total).

LEFT tile: Already styled - DO NOT CHANGE IT
RIGHT tile: Raw - STYLE IT to match the left tile exactly

Match colors, lighting, atmosphere. The center edge must blend seamlessly.

Style reference: {user_prompt}

Return exactly 1024×512 pixels. Keep LEFT unchanged, style only RIGHT."""

    result = call_gemini(stitched, prompt, HORIZONTAL_SIZE, temperature, api_key)
    _, right = cut_horizontal(result)
    return right


def generate_l_shaped(
    styled_tl: Image.Image,
    styled_tr: Image.Image,
    styled_bl: Image.Image,
    raw_br: Image.Image,
    user_prompt: str,
    temperature: float = 0.3,
    api_key: str | None = None,
) -> Image.Image:
    """
    Expand with L-shaped context (2×2 grid).
    Returns styled bottom-right tile only.
    """
    stitched = stitch_2x2(styled_tl, styled_tr, styled_bl, raw_br)

    prompt = f"""{BASE_PROMPT}

You are styling a tile to match its neighbors in a 2×2 grid (1024×1024 total).

TOP-LEFT: Already styled - DO NOT CHANGE
TOP-RIGHT: Already styled - DO NOT CHANGE
BOTTOM-LEFT: Already styled - DO NOT CHANGE
BOTTOM-RIGHT: Raw - STYLE IT to match the other three

Match colors, lighting, atmosphere. All edges must blend seamlessly.

Style reference: {user_prompt}

Return exactly 1024×1024 pixels. Change only BOTTOM-RIGHT."""

    result = call_gemini(stitched, prompt, GRID_2X2_SIZE, temperature, api_key)
    _, _, _, bottom_right = cut_2x2(result)
    return bottom_right


def generate_vertical_pair(
    styled_top: Image.Image,
    raw_bottom: Image.Image,
    user_prompt: str,
    temperature: float = 0.3,
    api_key: str | None = None,
) -> Image.Image:
    """
    For single-column case: style bottom tile to match styled top.
    Uses vertical 2-tile stitch (512×1024).
    """
    # Vertical stitch
    result_img = Image.new("RGB", (TILE_SIZE, TILE_SIZE * 2))
    result_img.paste(styled_top.resize((TILE_SIZE, TILE_SIZE)), (0, 0))
    result_img.paste(raw_bottom.resize((TILE_SIZE, TILE_SIZE)), (0, TILE_SIZE))

    prompt = f"""{BASE_PROMPT}

You are styling a map tile to match its neighbor (512×1024 total, vertical stack).

TOP tile: Already styled - DO NOT CHANGE IT
BOTTOM tile: Raw - STYLE IT to match the top tile exactly

Match colors, lighting, atmosphere. The center edge must blend seamlessly.

Style reference: {user_prompt}

Return exactly 512×1024 pixels. Keep TOP unchanged, style only BOTTOM."""

    result = call_gemini(result_img, prompt, (TILE_SIZE, TILE_SIZE * 2), temperature, api_key)

    # Cut bottom
    bottom = result.crop((0, TILE_SIZE, TILE_SIZE, TILE_SIZE * 2))
    return bottom


# =============================================================================
# MAIN PROCESSING ORCHESTRATION
# =============================================================================

def process_grid(
    grid: dict[int, dict[int, Path]],
    output_dir: Path,
    user_prompt: str,
    temperature: float = 0.3,
    api_key: str | None = None,
) -> int:
    """
    Process entire grid with context-aware stitching.
    Returns number of tiles generated.
    """
    min_x, min_y, max_x, max_y = get_grid_bounds(grid)

    width = max_x - min_x + 1
    height = max_y - min_y + 1
    total_tiles = sum(len(row) for row in grid.values())

    print(f"  Grid: {width}×{height} ({total_tiles} tiles)")
    print(f"  X range: {min_x} to {max_x}")
    print(f"  Y range: {min_y} to {max_y}")

    # Storage for styled tiles
    styled: dict[int, dict[int, Image.Image]] = defaultdict(dict)
    generated = 0

    # Helper to get output path
    def get_output_path(x: int, y: int) -> Path:
        # Assume zoom 16 (most common)
        return output_dir / "16" / str(x) / f"{y}.webp"

    # Helper to check if already exists
    def tile_exists(x: int, y: int) -> bool:
        return get_output_path(x, y).exists()

    # Helper to save tile
    def save_tile(x: int, y: int, img: Image.Image):
        path = get_output_path(x, y)
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, "WEBP", quality=90)

    # Helper to load styled tile from disk if exists
    def load_styled(x: int, y: int) -> Image.Image | None:
        if (y, x) in [(y_, x_) for y_ in styled for x_ in styled[y_]]:
            return styled[y][x]
        path = get_output_path(x, y)
        if path.exists():
            return load_image(path)
        return None

    # ==========================================================================
    # PHASE 1: First row - seed pair + horizontal expansion
    # ==========================================================================

    first_row_y = min_y
    first_row_xs = sorted(grid[first_row_y].keys())

    if len(first_row_xs) == 0:
        print("  ❌ No tiles in first row")
        return 0

    print(f"\n  Phase 1: First row (y={first_row_y})")

    if len(first_row_xs) == 1:
        # Single tile in row - just style it alone
        x = first_row_xs[0]
        if not tile_exists(x, first_row_y):
            print(f"    [{x},{first_row_y}] Single tile...", end=" ", flush=True)
            raw = load_image(grid[first_row_y][x])
            # Use seed pair logic but with same tile duplicated (will cut left)
            styled_a, _ = generate_seed_pair(raw, raw, user_prompt, temperature, api_key)
            styled[first_row_y][x] = styled_a
            save_tile(x, first_row_y, styled_a)
            generated += 1
            print("✓")
        else:
            styled[first_row_y][x] = load_image(get_output_path(x, first_row_y))
            print(f"    [{x},{first_row_y}] Exists, skipped")

    else:
        # Multiple tiles - seed pair then horizontal expansion
        x0, x1 = first_row_xs[0], first_row_xs[1]

        # Check if seed pair already done
        if tile_exists(x0, first_row_y) and tile_exists(x1, first_row_y):
            styled[first_row_y][x0] = load_image(get_output_path(x0, first_row_y))
            styled[first_row_y][x1] = load_image(get_output_path(x1, first_row_y))
            print(f"    [{x0},{first_row_y}]+[{x1},{first_row_y}] Seed pair exists, skipped")
        else:
            print(f"    [{x0},{first_row_y}]+[{x1},{first_row_y}] Seed pair...", end=" ", flush=True)
            start = time.time()
            raw_a = load_image(grid[first_row_y][x0])
            raw_b = load_image(grid[first_row_y][x1])
            styled_a, styled_b = generate_seed_pair(raw_a, raw_b, user_prompt, temperature, api_key)
            styled[first_row_y][x0] = styled_a
            styled[first_row_y][x1] = styled_b
            save_tile(x0, first_row_y, styled_a)
            save_tile(x1, first_row_y, styled_b)
            generated += 2
            print(f"✓ ({time.time() - start:.1f}s)")

        # Horizontal expansion for remaining tiles
        for i in range(2, len(first_row_xs)):
            x = first_row_xs[i]
            x_prev = first_row_xs[i - 1]

            if tile_exists(x, first_row_y):
                styled[first_row_y][x] = load_image(get_output_path(x, first_row_y))
                print(f"    [{x},{first_row_y}] Exists, skipped")
                continue

            print(f"    [{x},{first_row_y}] Horizontal expand...", end=" ", flush=True)
            start = time.time()

            styled_left = styled[first_row_y].get(x_prev) or load_styled(x_prev, first_row_y)
            if styled_left is None:
                print("✗ Missing left neighbor!")
                continue

            raw_right = load_image(grid[first_row_y][x])
            new_styled = generate_horizontal(styled_left, raw_right, user_prompt, temperature, api_key)
            styled[first_row_y][x] = new_styled
            save_tile(x, first_row_y, new_styled)
            generated += 1
            print(f"✓ ({time.time() - start:.1f}s)")

    # ==========================================================================
    # PHASE 2: Remaining rows - L-shaped context
    # ==========================================================================

    remaining_ys = sorted([y for y in grid.keys() if y != first_row_y])

    for row_idx, y in enumerate(remaining_ys):
        y_above = first_row_y if row_idx == 0 else remaining_ys[row_idx - 1]
        row_xs = sorted(grid[y].keys())

        print(f"\n  Phase 2: Row y={y} (above: y={y_above})")

        for col_idx, x in enumerate(row_xs):
            if tile_exists(x, y):
                styled[y][x] = load_image(get_output_path(x, y))
                print(f"    [{x},{y}] Exists, skipped")
                continue

            raw_tile = load_image(grid[y][x])

            # First column of row - use vertical expansion if no left neighbor
            if col_idx == 0:
                # Check if we have a tile above
                styled_above = load_styled(x, y_above)

                if styled_above is None:
                    # No above tile, style alone
                    print(f"    [{x},{y}] Single (no above)...", end=" ", flush=True)
                    start = time.time()
                    styled_a, _ = generate_seed_pair(raw_tile, raw_tile, user_prompt, temperature, api_key)
                    styled[y][x] = styled_a
                    save_tile(x, y, styled_a)
                    generated += 1
                    print(f"✓ ({time.time() - start:.1f}s)")
                else:
                    # Vertical expansion
                    print(f"    [{x},{y}] Vertical expand...", end=" ", flush=True)
                    start = time.time()
                    new_styled = generate_vertical_pair(styled_above, raw_tile, user_prompt, temperature, api_key)
                    styled[y][x] = new_styled
                    save_tile(x, y, new_styled)
                    generated += 1
                    print(f"✓ ({time.time() - start:.1f}s)")

            else:
                # L-shaped context: above-left, above, left, new
                x_left = row_xs[col_idx - 1]

                styled_above_left = load_styled(x_left, y_above)
                styled_above = load_styled(x, y_above)
                styled_left = load_styled(x_left, y)

                # Check what context we have
                if styled_above_left and styled_above and styled_left:
                    # Full L-shaped context
                    print(f"    [{x},{y}] L-shaped expand...", end=" ", flush=True)
                    start = time.time()
                    new_styled = generate_l_shaped(
                        styled_above_left, styled_above, styled_left, raw_tile,
                        user_prompt, temperature, api_key
                    )
                    styled[y][x] = new_styled
                    save_tile(x, y, new_styled)
                    generated += 1
                    print(f"✓ ({time.time() - start:.1f}s)")

                elif styled_left:
                    # Only left neighbor - horizontal expansion
                    print(f"    [{x},{y}] Horizontal expand (partial)...", end=" ", flush=True)
                    start = time.time()
                    new_styled = generate_horizontal(styled_left, raw_tile, user_prompt, temperature, api_key)
                    styled[y][x] = new_styled
                    save_tile(x, y, new_styled)
                    generated += 1
                    print(f"✓ ({time.time() - start:.1f}s)")

                elif styled_above:
                    # Only above neighbor - vertical expansion
                    print(f"    [{x},{y}] Vertical expand (partial)...", end=" ", flush=True)
                    start = time.time()
                    new_styled = generate_vertical_pair(styled_above, raw_tile, user_prompt, temperature, api_key)
                    styled[y][x] = new_styled
                    save_tile(x, y, new_styled)
                    generated += 1
                    print(f"✓ ({time.time() - start:.1f}s)")

                else:
                    # No context available - style alone
                    print(f"    [{x},{y}] Single (no context)...", end=" ", flush=True)
                    start = time.time()
                    styled_a, _ = generate_seed_pair(raw_tile, raw_tile, user_prompt, temperature, api_key)
                    styled[y][x] = styled_a
                    save_tile(x, y, styled_a)
                    generated += 1
                    print(f"✓ ({time.time() - start:.1f}s)")

    return generated


# =============================================================================
# MANIFEST UPDATE
# =============================================================================

def tile_to_latlng(x: int, y: int, z: int) -> tuple[float, float]:
    """Convert tile coordinates to lat/lng."""
    n = 2 ** z
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon


def update_manifest(
    style_name: str,
    display_name: str,
    description: str,
    tiles_count: int,
    bounds: tuple,
    colors: list[str],
):
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
        "generator": "nano-stitcher",
    })

    manifest["generatedAt"] = datetime.now().isoformat()

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"  Updated manifest: {manifest_path}")


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Nano Banana Context-Aware Tile Stitcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate winter style with stitched consistency
  python scripts/tile_pipeline/nano_stitcher.py \\
      --source public/tiles/hybrid-golden_hour \\
      --style-name nano-winter-stitched \\
      --prompt "Winter snow: white rooftops, gray streets, blue shadows"

  # Lower temperature for more consistency
  python scripts/tile_pipeline/nano_stitcher.py \\
      --source public/tiles/hybrid-golden_hour \\
      --style-name nano-cyberpunk-stitched \\
      --prompt "Cyberpunk neon night with glowing rooftops" \\
      --temperature 0.2
        """,
    )

    parser.add_argument(
        "--source", "-s",
        type=Path,
        required=True,
        help="Source directory containing raw tiles",
    )
    parser.add_argument(
        "--style-name", "-n",
        type=str,
        required=True,
        help="Output style name (creates public/tiles/<style-name>/)",
    )
    parser.add_argument(
        "--prompt", "-p",
        type=str,
        required=True,
        help="Style description/instructions",
    )
    parser.add_argument(
        "--temperature", "-t",
        type=float,
        default=0.3,
        help="Generation temperature (0.0-1.0, lower = more consistent)",
    )
    parser.add_argument(
        "--display-name",
        type=str,
        help="Display name for manifest (defaults to style-name)",
    )
    parser.add_argument(
        "--description",
        type=str,
        help="Description for manifest (defaults to prompt)",
    )
    parser.add_argument(
        "--colors",
        type=str,
        nargs="+",
        help="Color palette hex values for manifest",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="Google AI API key (or set GOOGLE_API_KEY env var)",
    )

    args = parser.parse_args()

    if not args.source.exists():
        print(f"❌ Source directory not found: {args.source}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(f"public/tiles/{args.style_name}")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🍌 Nano Banana Context-Aware Stitcher")
    print(f"{'═' * 50}")
    print(f"  Source:      {args.source}")
    print(f"  Output:      {output_dir}")
    print(f"  Style:       {args.style_name}")
    print(f"  Temperature: {args.temperature}")
    print(f"  Prompt:      {args.prompt[:50]}{'...' if len(args.prompt) > 50 else ''}")
    print(f"{'═' * 50}")

    # Collect grid
    print("\n📦 Collecting tiles...")
    grid = collect_tile_grid(args.source)

    if not grid:
        print("❌ No tiles found in source directory", file=sys.stderr)
        sys.exit(1)

    total_tiles = sum(len(row) for row in grid.values())
    print(f"  Found {total_tiles} tiles")

    # Process grid
    print("\n🎨 Processing with context-aware stitching...")
    try:
        generated = process_grid(
            grid=grid,
            output_dir=output_dir,
            user_prompt=args.prompt,
            temperature=args.temperature,
            api_key=args.api_key,
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Calculate bounds for manifest
    min_x, min_y, max_x, max_y = get_grid_bounds(grid)
    _, west = tile_to_latlng(min_x, min_y, 16)
    north, _ = tile_to_latlng(min_x, min_y, 16)
    _, east = tile_to_latlng(max_x + 1, max_y + 1, 16)
    south, _ = tile_to_latlng(max_x + 1, max_y + 1, 16)
    bounds = (west, south, east, north)

    # Update manifest
    update_manifest(
        style_name=args.style_name,
        display_name=args.display_name or args.style_name.replace("-", " ").title(),
        description=args.description or args.prompt[:100],
        tiles_count=generated,
        bounds=bounds,
        colors=args.colors or ["#FFFFFF", "#87CEEB", "#4169E1"],
    )

    print(f"\n{'═' * 50}")
    print(f"  ✅ Generated: {generated} tiles")
    print(f"  📁 Output: {output_dir}")
    print(f"{'═' * 50}\n")


if __name__ == "__main__":
    main()
