#!/usr/bin/env python3
"""
Debug script to trace Pass 2 position selection in nano_stitcher_v2.py
"""

from collections import defaultdict
from pathlib import Path

# Simulate the grid from hybrid-golden_hour
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


def trace_pass2_positions(grid: dict[int, dict[int, Path]]):
    """Trace which position would be selected for each tile in Pass 2."""
    all_ys = sorted(grid.keys())
    min_x = min(x for row in grid.values() for x in row.keys())
    max_x = max(x for row in grid.values() for x in row.keys())
    min_y = min(all_ys)
    max_y = max(all_ys)

    print(f"Grid: x=[{min_x}..{max_x}], y=[{min_y}..{max_y}]")
    print(f"Grid dimensions: {max_x - min_x + 1}×{max_y - min_y + 1}")
    print()

    # Simulate Pass 1 completion - all tiles are "styled"
    styled = {y: {x: f"P1({x},{y})" for x in row.keys()} for y, row in grid.items()}

    # Now trace Pass 2
    print("Pass 2 Position Selection:")
    print("=" * 60)

    positions_used = defaultdict(list)

    for y in all_ys:
        for x in sorted(grid[y].keys()):
            styled_above = styled.get(y - 1, {}).get(x)
            styled_below = styled.get(y + 1, {}).get(x)
            styled_left = styled.get(y, {}).get(x - 1)
            styled_right = styled.get(y, {}).get(x + 1)

            position = None
            context_desc = ""

            if styled_above and styled_left and styled.get(y - 1, {}).get(x - 1):
                position = 'br'
                context_desc = f"above-left=({x-1},{y-1}) above=({x},{y-1}) left=({x-1},{y}) RAW=({x},{y})"
            elif styled_above and styled_right and styled.get(y - 1, {}).get(x + 1):
                position = 'bl'
                context_desc = f"above=({x},{y-1}) above-right=({x+1},{y-1}) RAW=({x},{y}) right=({x+1},{y})"
            elif styled_below and styled_left and styled.get(y + 1, {}).get(x - 1):
                position = 'tr'
                context_desc = f"left=({x-1},{y}) RAW=({x},{y}) below-left=({x-1},{y+1}) below=({x},{y+1})"
            elif styled_below and styled_right and styled.get(y + 1, {}).get(x + 1):
                position = 'tl'
                context_desc = f"RAW=({x},{y}) right=({x+1},{y}) below=({x},{y+1}) below-right=({x+1},{y+1})"

            if position:
                positions_used[position].append((x, y))
                print(f"  [{x},{y}] → position='{position}'")
                print(f"           Context: {context_desc}")
            else:
                print(f"  [{x},{y}] → SKIP (no valid 2×2 context)")

            # Simulate Pass 2 updating styled dict (in real code this happens)
            styled[y][x] = f"P2({x},{y})"

    print()
    print("Position Usage Summary:")
    for pos in ['tl', 'tr', 'bl', 'br']:
        tiles = positions_used[pos]
        print(f"  '{pos}': {len(tiles)} tiles - {tiles}")

    print()
    print("Expected 2×2 Grid Layouts:")
    print("-" * 40)
    print("'tl' - RAW at top-left:")
    print("  [RAW]   [right]")
    print("  [below] [below-right]")
    print()
    print("'tr' - RAW at top-right:")
    print("  [left]       [RAW]")
    print("  [below-left] [below]")
    print()
    print("'bl' - RAW at bottom-left:")
    print("  [above]      [above-right]")
    print("  [RAW]        [right]")
    print()
    print("'br' - RAW at bottom-right:")
    print("  [above-left] [above]")
    print("  [left]       [RAW]")


if __name__ == "__main__":
    source = Path("public/tiles/hybrid-golden_hour")
    if source.exists():
        grid = collect_tile_grid(source)
        trace_pass2_positions(grid)
    else:
        # Simulate the 4x3 grid from v2 output
        print("Simulating 4x3 grid (x=34321-34324, y=22949-22951):")
        grid = {
            22949: {34321: Path("a"), 34322: Path("b"), 34323: Path("c"), 34324: Path("d")},
            22950: {34321: Path("e"), 34322: Path("f"), 34323: Path("g"), 34324: Path("h")},
            22951: {34321: Path("i"), 34322: Path("j"), 34323: Path("k"), 34324: Path("l")},
        }
        trace_pass2_positions(grid)
