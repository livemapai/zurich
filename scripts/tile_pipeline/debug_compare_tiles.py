#!/usr/bin/env python3
"""
Compare source tiles vs styled output tiles to detect geometry shifts.

This creates side-by-side comparisons and edge alignment checks.
"""

from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

TILE_SIZE = 512
OUTPUT_DIR = Path("output/debug_compare")


def load_image(path: Path) -> Image.Image:
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
                    x = int(parts[i + 1])
                    y = int(parts[i + 2].replace(".webp", ""))
                    grid[y][x] = webp_file
                    break
        except (IndexError, ValueError):
            continue
    return grid


def create_edge_strip(img: Image.Image, edge: str, width: int = 64) -> Image.Image:
    """Extract an edge strip from a tile."""
    if edge == "right":
        return img.crop((TILE_SIZE - width, 0, TILE_SIZE, TILE_SIZE))
    elif edge == "left":
        return img.crop((0, 0, width, TILE_SIZE))
    elif edge == "bottom":
        return img.crop((0, TILE_SIZE - width, TILE_SIZE, TILE_SIZE))
    elif edge == "top":
        return img.crop((0, 0, TILE_SIZE, width))
    return img


def compare_tile_edges(
    styled_grid: dict[int, dict[int, Path]],
    output_dir: Path,
):
    """
    Compare edges between adjacent tiles to check for seams.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    all_ys = sorted(styled_grid.keys())
    all_xs = sorted(set(x for row in styled_grid.values() for x in row.keys()))

    print(f"Checking edge alignment for {len(all_xs)}x{len(all_ys)} grid...")

    # Check horizontal seams (right edge of A vs left edge of B)
    horizontal_issues = []
    for y in all_ys:
        xs = sorted(styled_grid[y].keys())
        for i in range(len(xs) - 1):
            x_left = xs[i]
            x_right = xs[i + 1]

            tile_left = load_image(styled_grid[y][x_left])
            tile_right = load_image(styled_grid[y][x_right])

            # Get edge strips
            left_right_edge = create_edge_strip(tile_left, "right", 32)
            right_left_edge = create_edge_strip(tile_right, "left", 32)

            # Create comparison
            comparison = Image.new("RGB", (64 + 10, TILE_SIZE))
            comparison.paste(left_right_edge, (0, 0))
            comparison.paste(right_left_edge, (32 + 10, 0))

            # Draw separator
            draw = ImageDraw.Draw(comparison)
            draw.line([(32, 0), (32, TILE_SIZE)], fill=(255, 0, 0), width=2)
            draw.line([(42, 0), (42, TILE_SIZE)], fill=(255, 0, 0), width=2)

            # Save
            out_path = output_dir / f"h_edge_{y}_{x_left}_{x_right}.png"
            comparison.save(out_path)

            # Calculate difference
            diff = ImageChops.difference(left_right_edge, right_left_edge)
            avg_diff = sum(diff.histogram()) / (32 * TILE_SIZE * 3)

            if avg_diff > 10:  # Threshold for "significant" difference
                horizontal_issues.append((x_left, x_right, y, avg_diff))
                print(f"  H-seam at y={y}, x={x_left}|{x_right}: avg_diff={avg_diff:.1f}")

    # Check vertical seams (bottom edge of A vs top edge of B)
    vertical_issues = []
    for i in range(len(all_ys) - 1):
        y_top = all_ys[i]
        y_bottom = all_ys[i + 1]

        for x in all_xs:
            if x not in styled_grid[y_top] or x not in styled_grid[y_bottom]:
                continue

            tile_top = load_image(styled_grid[y_top][x])
            tile_bottom = load_image(styled_grid[y_bottom][x])

            # Get edge strips
            top_bottom_edge = create_edge_strip(tile_top, "bottom", 32)
            bottom_top_edge = create_edge_strip(tile_bottom, "top", 32)

            # Create comparison
            comparison = Image.new("RGB", (TILE_SIZE, 64 + 10))
            comparison.paste(top_bottom_edge, (0, 0))
            comparison.paste(bottom_top_edge, (0, 32 + 10))

            # Draw separator
            draw = ImageDraw.Draw(comparison)
            draw.line([(0, 32), (TILE_SIZE, 32)], fill=(255, 0, 0), width=2)
            draw.line([(0, 42), (TILE_SIZE, 42)], fill=(255, 0, 0), width=2)

            out_path = output_dir / f"v_edge_{x}_{y_top}_{y_bottom}.png"
            comparison.save(out_path)

            # Calculate difference
            diff = ImageChops.difference(top_bottom_edge, bottom_top_edge)
            avg_diff = sum(diff.histogram()) / (TILE_SIZE * 32 * 3)

            if avg_diff > 10:
                vertical_issues.append((x, y_top, y_bottom, avg_diff))
                print(f"  V-seam at x={x}, y={y_top}|{y_bottom}: avg_diff={avg_diff:.1f}")

    return horizontal_issues, vertical_issues


def create_full_stitch(
    grid: dict[int, dict[int, Path]],
    output_path: Path,
):
    """Stitch all tiles into one large image for visual inspection."""
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

    # Draw grid lines for visibility
    draw = ImageDraw.Draw(result)
    for i in range(1, max_x - min_x + 1):
        x_pos = i * TILE_SIZE
        draw.line([(x_pos, 0), (x_pos, height)], fill=(255, 0, 0), width=2)
    for i in range(1, max_y - min_y + 1):
        y_pos = i * TILE_SIZE
        draw.line([(0, y_pos), (width, y_pos)], fill=(255, 0, 0), width=2)

    result.save(output_path)
    print(f"Saved full stitch to: {output_path}")
    return result


def main():
    # Compare different styled outputs
    styles_to_check = [
        ("nano-winter-stitched", "Pass 1 only (L-shaped)"),
        ("nano-winter-stitched-v2", "Pass 2 (with style reference)"),
    ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for style_name, description in styles_to_check:
        style_dir = Path(f"public/tiles/{style_name}")

        if not style_dir.exists():
            print(f"\n⚠️  {style_name}: Not found, skipping")
            continue

        print(f"\n{'='*60}")
        print(f"Checking: {style_name} ({description})")
        print(f"{'='*60}")

        grid = collect_tile_grid(style_dir)

        if not grid:
            print("  No tiles found")
            continue

        # Create full stitch
        stitch_path = OUTPUT_DIR / f"full_{style_name}.png"
        create_full_stitch(grid, stitch_path)

        # Check edge alignment
        sub_dir = OUTPUT_DIR / style_name
        h_issues, v_issues = compare_tile_edges(grid, sub_dir)

        print(f"\n  Summary:")
        print(f"    Horizontal seam issues: {len(h_issues)}")
        print(f"    Vertical seam issues: {len(v_issues)}")

    # Also create stitch of source tiles for comparison
    source_dir = Path("public/tiles/hybrid-golden_hour")
    if source_dir.exists():
        print(f"\n{'='*60}")
        print(f"Source: hybrid-golden_hour")
        print(f"{'='*60}")
        grid = collect_tile_grid(source_dir)
        stitch_path = OUTPUT_DIR / "full_source.png"
        create_full_stitch(grid, stitch_path)

    print(f"\n\nAll output saved to: {OUTPUT_DIR}")
    print(f"Open with: open {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
