#!/usr/bin/env python3
"""Create a labeled grid of all tiles for visual inspection."""

from collections import defaultdict
from pathlib import Path
from PIL import Image, ImageDraw

TILE_SIZE = 512

def load_image(path: Path) -> Image.Image:
    with Image.open(path) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        return img.copy()

def create_labeled_grid(style_dir: Path, output_path: Path):
    grid = defaultdict(dict)

    for webp_file in style_dir.rglob("*.webp"):
        if "_backup" in webp_file.name:
            continue
        parts = webp_file.parts
        for i, part in enumerate(parts):
            if part.isdigit() and len(part) <= 2:
                x = int(parts[i + 1])
                y = int(parts[i + 2].replace(".webp", ""))
                grid[y][x] = webp_file
                break

    all_ys = sorted(grid.keys())
    all_xs = sorted(set(x for row in grid.values() for x in row.keys()))

    min_x, max_x = min(all_xs), max(all_xs)
    min_y, max_y = min(all_ys), max(all_ys)

    cols = max_x - min_x + 1
    rows = max_y - min_y + 1

    # Each cell: tile + label area
    cell_h = TILE_SIZE + 30
    width = cols * TILE_SIZE + (cols + 1) * 10
    height = rows * cell_h + (rows + 1) * 10

    result = Image.new("RGB", (width, height), (30, 30, 30))
    draw = ImageDraw.Draw(result)

    for y in all_ys:
        for x in sorted(grid[y].keys()):
            tile = load_image(grid[y][x])
            col = x - min_x
            row = y - min_y
            px = 10 + col * (TILE_SIZE + 10)
            py = 10 + row * (cell_h + 10)

            result.paste(tile.resize((TILE_SIZE, TILE_SIZE)), (px, py + 25))

            # Label
            draw.text((px + 5, py + 5), f"({x}, {y})", fill=(255, 255, 0))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path)
    print(f"Saved: {output_path}")

def main():
    styles = ["nano-cyberpunk-v2", "hybrid-golden_hour"]

    for style in styles:
        style_dir = Path(f"public/tiles/{style}")
        if style_dir.exists():
            output = Path(f"output/grid_{style}.png")
            create_labeled_grid(style_dir, output)

    print(f"Open: open output/")

if __name__ == "__main__":
    main()
