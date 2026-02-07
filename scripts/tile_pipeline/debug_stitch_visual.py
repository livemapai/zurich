#!/usr/bin/env python3
"""
Visual debug: Compare stitching vs cropping in Pass 2.

This script:
1. Loads source tiles from hybrid-golden_hour
2. Loads styled tiles from a v2 output (if available)
3. Simulates the Pass 2 stitching process
4. Creates visual comparison images showing:
   - The 2×2 context we would send to LLM
   - The crop boundaries
   - What we extract

Run: python3 scripts/tile_pipeline/debug_stitch_visual.py
"""

import io
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TILE_SIZE = 512
OUTPUT_DIR = Path("output/debug_stitch")


def load_image(path: Path) -> Image.Image:
    """Load an image file and convert to RGB."""
    with Image.open(path) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        return img.copy()


def collect_tile_grid(source_dir: Path) -> dict[int, dict[int, Path]]:
    grid: dict[int, dict[int, Path]] = defaultdict(dict)
    for webp_file in source_dir.rglob("*.webp"):
        if "_backup" in webp_file.name:
            continue
        try:
            parts = webp_file.parts
            for i, part in enumerate(parts):
                if part.isdigit() and len(part) <= 2:
                    z = int(part)
                    x = int(parts[i + 1])
                    y = int(parts[i + 2].replace(".webp", ""))
                    grid[y][x] = webp_file
                    break
        except (IndexError, ValueError):
            continue
    return grid


def stitch_2x2(tl: Image.Image, tr: Image.Image, bl: Image.Image, br: Image.Image) -> Image.Image:
    """Combine 4 tiles in 2×2 grid → 1024×1024."""
    result = Image.new("RGB", (1024, 1024))
    result.paste(tl.resize((TILE_SIZE, TILE_SIZE)), (0, 0))
    result.paste(tr.resize((TILE_SIZE, TILE_SIZE)), (TILE_SIZE, 0))
    result.paste(bl.resize((TILE_SIZE, TILE_SIZE)), (0, TILE_SIZE))
    result.paste(br.resize((TILE_SIZE, TILE_SIZE)), (TILE_SIZE, TILE_SIZE))
    return result


def draw_crop_region(img: Image.Image, position: str) -> Image.Image:
    """Draw crop region boundaries on the image."""
    img = img.copy()
    draw = ImageDraw.Draw(img)

    positions = {
        'tl': (0, 0, TILE_SIZE, TILE_SIZE),
        'tr': (TILE_SIZE, 0, TILE_SIZE * 2, TILE_SIZE),
        'bl': (0, TILE_SIZE, TILE_SIZE, TILE_SIZE * 2),
        'br': (TILE_SIZE, TILE_SIZE, TILE_SIZE * 2, TILE_SIZE * 2),
    }

    # Draw all quadrant boundaries
    draw.line([(512, 0), (512, 1024)], fill=(255, 0, 0), width=3)  # Vertical center
    draw.line([(0, 512), (1024, 512)], fill=(255, 0, 0), width=3)  # Horizontal center

    # Highlight the target crop region
    crop = positions[position]
    draw.rectangle(crop, outline=(0, 255, 0), width=5)

    # Add labels
    labels = {
        'tl': (256, 256),
        'tr': (768, 256),
        'bl': (256, 768),
        'br': (768, 768),
    }

    for pos, (cx, cy) in labels.items():
        text = "RAW" if pos == position else "styled"
        draw.text((cx - 30, cy - 10), text, fill=(255, 255, 0))
        draw.text((cx - 20, cy + 10), pos.upper(), fill=(255, 255, 0))

    return img


def visualize_pass2_step(
    tile_x: int,
    tile_y: int,
    position: str,
    source_grid: dict[int, dict[int, Path]],
    styled_grid: dict[int, dict[int, Path]] | None = None,
    output_dir: Path = OUTPUT_DIR,
):
    """Create visual debug for one Pass 2 step."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine which tiles we need based on position
    if position == 'br':
        coords = {
            'tl': (tile_x - 1, tile_y - 1),
            'tr': (tile_x, tile_y - 1),
            'bl': (tile_x - 1, tile_y),
            'br': (tile_x, tile_y),  # RAW
        }
    elif position == 'bl':
        coords = {
            'tl': (tile_x, tile_y - 1),
            'tr': (tile_x + 1, tile_y - 1),
            'bl': (tile_x, tile_y),  # RAW
            'br': (tile_x + 1, tile_y),
        }
    elif position == 'tr':
        coords = {
            'tl': (tile_x - 1, tile_y),
            'tr': (tile_x, tile_y),  # RAW
            'bl': (tile_x - 1, tile_y + 1),
            'br': (tile_x, tile_y + 1),
        }
    elif position == 'tl':
        coords = {
            'tl': (tile_x, tile_y),  # RAW
            'tr': (tile_x + 1, tile_y),
            'bl': (tile_x, tile_y + 1),
            'br': (tile_x + 1, tile_y + 1),
        }

    print(f"\nVisualizing tile ({tile_x}, {tile_y}) with position='{position}'")
    print(f"  2×2 Grid coordinates:")
    for pos, (x, y) in coords.items():
        is_raw = pos == position
        print(f"    {pos.upper()}: ({x}, {y}) {'← RAW' if is_raw else ''}")

    # Load tiles
    tiles = {}
    for pos, (x, y) in coords.items():
        if y in source_grid and x in source_grid[y]:
            tiles[pos] = load_image(source_grid[y][x])
            print(f"  Loaded {pos}: {source_grid[y][x]}")
        else:
            # Create placeholder
            tiles[pos] = Image.new("RGB", (512, 512), (128, 128, 128))
            print(f"  Missing {pos}: ({x}, {y}) - using placeholder")

    # Create stitched 2×2 context
    stitched = stitch_2x2(tiles['tl'], tiles['tr'], tiles['bl'], tiles['br'])

    # Draw crop region
    stitched_annotated = draw_crop_region(stitched, position)

    # Crop the target region
    crop_coords = {
        'tl': (0, 0, TILE_SIZE, TILE_SIZE),
        'tr': (TILE_SIZE, 0, TILE_SIZE * 2, TILE_SIZE),
        'bl': (0, TILE_SIZE, TILE_SIZE, TILE_SIZE * 2),
        'br': (TILE_SIZE, TILE_SIZE, TILE_SIZE * 2, TILE_SIZE * 2),
    }
    cropped = stitched.crop(crop_coords[position])

    # Compare with original source tile
    original = tiles[position]

    # Create comparison image
    comparison = Image.new("RGB", (1024 + 512 * 2 + 40, 1024 + 60), (40, 40, 40))

    # Add stitched image
    comparison.paste(stitched_annotated, (10, 50))

    # Add cropped tile
    comparison.paste(cropped, (1024 + 20, 50))

    # Add original source tile
    comparison.paste(original, (1024 + 512 + 30, 50))

    # Add labels
    draw = ImageDraw.Draw(comparison)
    draw.text((10, 10), f"Tile ({tile_x},{tile_y}) - Position: '{position}'", fill=(255, 255, 255))
    draw.text((10, 30), "2×2 Context (stitched)", fill=(200, 200, 200))
    draw.text((1024 + 20, 30), f"Cropped '{position}'", fill=(200, 200, 200))
    draw.text((1024 + 512 + 30, 30), "Original Source", fill=(200, 200, 200))

    # Save
    output_path = output_dir / f"pass2_{tile_x}_{tile_y}_{position}.png"
    comparison.save(output_path)
    print(f"  Saved: {output_path}")

    # Also save just the stitched context
    context_path = output_dir / f"context_{tile_x}_{tile_y}_{position}.png"
    stitched_annotated.save(context_path)

    # Check if cropped matches original
    import hashlib
    cropped_hash = hashlib.md5(cropped.tobytes()).hexdigest()[:8]
    original_hash = hashlib.md5(original.tobytes()).hexdigest()[:8]
    match = cropped_hash == original_hash
    print(f"  Cropped hash: {cropped_hash}, Original hash: {original_hash}, Match: {match}")

    return match


def main():
    source_dir = Path("public/tiles/hybrid-golden_hour")

    if not source_dir.exists():
        print(f"Source directory not found: {source_dir}")
        return

    source_grid = collect_tile_grid(source_dir)

    if not source_grid:
        print("No tiles found in source directory")
        return

    all_ys = sorted(source_grid.keys())
    all_xs = sorted(set(x for row in source_grid.values() for x in row.keys()))

    print(f"Source grid: x=[{min(all_xs)}..{max(all_xs)}], y=[{min(all_ys)}..{max(all_ys)}]")
    print(f"Testing Pass 2 stitch-crop consistency...")

    # Test a few key tiles
    test_cases = []

    # First row - should use 'tl' or 'tr' (no above neighbors)
    if len(all_ys) > 0:
        y = all_ys[0]
        xs = sorted(source_grid[y].keys())
        if len(xs) > 0:
            # First tile in first row - should be 'tl'
            test_cases.append((xs[0], y, 'tl'))
        if len(xs) > 1:
            # Second tile in first row - should be 'tr'
            test_cases.append((xs[1], y, 'tr'))

    # Interior tiles - should use 'br'
    if len(all_ys) > 1:
        y = all_ys[1]
        xs = sorted(source_grid[y].keys())
        if len(xs) > 1:
            # Second tile in second row - should be 'br'
            test_cases.append((xs[1], y, 'br'))

    # First column of non-first row - should be 'bl'
    if len(all_ys) > 1:
        y = all_ys[1]
        xs = sorted(source_grid[y].keys())
        if len(xs) > 0:
            test_cases.append((xs[0], y, 'bl'))

    print(f"\nTest cases: {test_cases}")

    all_match = True
    for x, y, expected_pos in test_cases:
        match = visualize_pass2_step(x, y, expected_pos, source_grid)
        all_match = all_match and match

    print(f"\n{'='*50}")
    if all_match:
        print("✅ All stitch-crop operations are consistent!")
        print("   The cropped region matches the original source tile.")
    else:
        print("❌ Some stitch-crop operations are INCONSISTENT!")
        print("   Check the output images for details.")

    print(f"\nOutput images saved to: {OUTPUT_DIR}")
    print(f"Open with: open {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
