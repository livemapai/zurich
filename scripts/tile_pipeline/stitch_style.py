#!/usr/bin/env python3
"""Quick stitch a style into a single image for viewing."""

import sys
from collections import defaultdict
from pathlib import Path
from PIL import Image, ImageDraw

TILE_SIZE = 512

def load_image(path: Path) -> Image.Image:
    with Image.open(path) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        return img.copy()

def collect_grid(source_dir: Path) -> dict[int, dict[int, Path]]:
    grid: dict[int, dict[int, Path]] = defaultdict(dict)
    for webp_file in source_dir.rglob("*.webp"):
        if "_backup" in webp_file.name:
            continue
        try:
            parts = webp_file.parts
            for i, part in enumerate(parts):
                if part.isdigit() and len(part) <= 2:
                    x = int(parts[i + 1])
                    y = int(parts[i + 2].replace(".webp", ""))
                    grid[y][x] = webp_file
                    break
        except (IndexError, ValueError):
            continue
    return grid

def stitch(grid: dict[int, dict[int, Path]], output_path: Path, draw_grid: bool = True):
    all_ys = sorted(grid.keys())
    all_xs = sorted(set(x for row in grid.values() for x in row.keys()))

    min_x, max_x = min(all_xs), max(all_xs)
    min_y, max_y = min(all_ys), max(all_ys)

    width = (max_x - min_x + 1) * TILE_SIZE
    height = (max_y - min_y + 1) * TILE_SIZE

    result = Image.new("RGB", (width, height), (128, 128, 128))

    for y, row in grid.items():
        for x, path in row.items():
            tile = load_image(path)
            px = (x - min_x) * TILE_SIZE
            py = (y - min_y) * TILE_SIZE
            result.paste(tile.resize((TILE_SIZE, TILE_SIZE)), (px, py))

    if draw_grid:
        draw = ImageDraw.Draw(result)
        for i in range(1, max_x - min_x + 1):
            x_pos = i * TILE_SIZE
            draw.line([(x_pos, 0), (x_pos, height)], fill=(255, 0, 0), width=2)
        for i in range(1, max_y - min_y + 1):
            y_pos = i * TILE_SIZE
            draw.line([(0, y_pos), (width, y_pos)], fill=(255, 0, 0), width=2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path)
    print(f"Saved: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 stitch_style.py <style-name> [--no-grid]")
        sys.exit(1)

    style_name = sys.argv[1]
    draw_grid = "--no-grid" not in sys.argv

    source = Path(f"public/tiles/{style_name}")
    if not source.exists():
        print(f"Not found: {source}")
        sys.exit(1)

    grid = collect_grid(source)
    output = Path(f"output/stitch_{style_name}.png")
    stitch(grid, output, draw_grid)
    print(f"Open with: open {output}")
