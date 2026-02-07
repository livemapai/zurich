#!/usr/bin/env python3
"""
Generate all semantic tiles for Zurich city coverage.

Usage:
    python -m scripts.tile_pipeline.generate_all_semantic [--start-x X] [--start-y Y]
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


def generate_semantic_tile(zoom: int, x: int, y: int) -> bool:
    """Generate a single semantic tile."""
    tile_spec = f"{zoom}/{x}/{y}"
    output_path = Path(f"public/tiles/semantic/{tile_spec}.webp")

    # Skip if already exists
    if output_path.exists():
        print(f"  [SKIP] {tile_spec} - already exists")
        return True

    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "scripts.tile_pipeline.cli",
                "render-semantic",
                "--tile", tile_spec,
            ],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout per tile
        )

        if result.returncode == 0 and output_path.exists():
            print(f"  [OK] {tile_spec}")
            return True
        else:
            print(f"  [FAIL] {tile_spec}: {result.stderr[:200] if result.stderr else 'Unknown error'}")
            return False

    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {tile_spec}")
        return False
    except Exception as e:
        print(f"  [ERROR] {tile_spec}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Generate all semantic tiles for Zurich")
    parser.add_argument("--start-x", type=int, default=34308, help="Starting X tile")
    parser.add_argument("--start-y", type=int, default=22935, help="Starting Y tile")
    parser.add_argument("--end-x", type=int, default=34337, help="Ending X tile")
    parser.add_argument("--end-y", type=int, default=22965, help="Ending Y tile")
    parser.add_argument("--zoom", type=int, default=16, help="Zoom level")
    args = parser.parse_args()

    zoom = args.zoom
    x_range = range(args.start_x, args.end_x + 1)
    y_range = range(args.start_y, args.end_y + 1)

    total = len(x_range) * len(y_range)
    generated = 0
    skipped = 0
    failed = 0

    start_time = time.time()

    print(f"Generating semantic tiles for Zurich")
    print(f"  Zoom: {zoom}")
    print(f"  X range: {args.start_x} to {args.end_x}")
    print(f"  Y range: {args.start_y} to {args.end_y}")
    print(f"  Total tiles: {total}")
    print()

    # Create output directory
    Path("public/tiles/semantic").mkdir(parents=True, exist_ok=True)

    count = 0
    for x in x_range:
        for y in y_range:
            count += 1
            tile_path = Path(f"public/tiles/semantic/{zoom}/{x}/{y}.webp")

            if tile_path.exists():
                skipped += 1
                print(f"[{count}/{total}] Skipping {zoom}/{x}/{y} (exists)")
                continue

            print(f"[{count}/{total}] Generating {zoom}/{x}/{y}...")

            if generate_semantic_tile(zoom, x, y):
                if tile_path.exists():
                    generated += 1
                else:
                    skipped += 1  # Was already counted as skip
            else:
                failed += 1

            # Progress estimate
            elapsed = time.time() - start_time
            if generated > 0:
                per_tile = elapsed / (generated + failed)
                remaining = (total - count) * per_tile
                print(f"    Estimated remaining: {remaining/60:.1f} minutes")

    elapsed = time.time() - start_time
    print()
    print(f"Complete!")
    print(f"  Generated: {generated}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {failed}")
    print(f"  Time: {elapsed/60:.1f} minutes")


if __name__ == "__main__":
    main()
