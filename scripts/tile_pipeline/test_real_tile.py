#!/usr/bin/env python3
"""
Test the V2 pipeline with real satellite imagery and building data.

This script:
1. Fetches a real SWISSIMAGE satellite tile
2. Fetches Mapterhorn elevation data
3. Queries Zurich buildings and trees in the tile bounds
4. Runs shadow removal + ray tracing pipeline
5. Generates comparison images

Usage:
    python -m scripts.tile_pipeline.test_real_tile
    python -m scripts.tile_pipeline.test_real_tile --tile 16/34322/22950
"""

import argparse
from pathlib import Path
import time

import numpy as np
from PIL import Image

from .config import PipelineConfig
from .sources.satellite import fetch_satellite_tile, tile_bounds_wgs84
from .sources.elevation import fetch_elevation_tile
from .sources.vector import VectorSource, query_features_in_tile
from .tile_compositor import composite_tile_v2, preview_v2_pipeline
from .time_presets import get_preset


def run_real_tile_test(
    z: int = 16,
    x: int = 34322,
    y: int = 22950,
    output_dir: Path = Path("test_output/real_tile"),
    preset_name: str = "afternoon",
    ray_trace_samples: int = 1,
):
    """Run the V2 pipeline on a real tile.

    Args:
        z, x, y: Tile coordinates (default: central Zurich)
        output_dir: Where to save output images
        preset_name: Time preset to use
        ray_trace_samples: Number of samples for soft shadows
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    config = PipelineConfig()

    print("=" * 60)
    print(f"Testing V2 Pipeline on Real Tile: {z}/{x}/{y}")
    print("=" * 60)

    # Get tile bounds
    bounds = tile_bounds_wgs84(z, x, y)
    print(f"\nTile bounds (WGS84):")
    print(f"  West:  {bounds[0]:.6f}")
    print(f"  South: {bounds[1]:.6f}")
    print(f"  East:  {bounds[2]:.6f}")
    print(f"  North: {bounds[3]:.6f}")

    # Step 1: Fetch satellite imagery
    print("\n[1/5] Fetching satellite imagery...")
    start = time.time()
    try:
        satellite = fetch_satellite_tile(z, x, y, config, target_size=512)
        print(f"  ✓ Satellite: {satellite.shape}, fetched in {time.time()-start:.2f}s")
    except Exception as e:
        print(f"  ✗ Failed to fetch satellite: {e}")
        # Create placeholder
        satellite = np.zeros((512, 512, 3), dtype=np.uint8)
        satellite[:, :] = [100, 120, 90]  # Gray-green placeholder
        print("  Using placeholder satellite image")

    # Step 2: Fetch elevation
    print("\n[2/5] Fetching elevation data...")
    start = time.time()
    try:
        elevation = fetch_elevation_tile(z, x, y, config, target_size=512)
        print(f"  ✓ Elevation: {elevation.shape}")
        print(f"    Range: {elevation.min():.1f}m to {elevation.max():.1f}m")
        print(f"    Fetched in {time.time()-start:.2f}s")
    except Exception as e:
        print(f"  ✗ Failed to fetch elevation: {e}")
        # Create flat placeholder
        elevation = np.full((512, 512), 400.0, dtype=np.float32)
        print("  Using flat elevation (400m)")

    # Step 3: Load buildings and trees
    print("\n[3/5] Loading building and tree data...")
    buildings_path = Path("public/data/zurich-buildings.geojson")
    trees_path = Path("public/data/zurich-trees.geojson")

    buildings = []
    trees = []

    if buildings_path.exists():
        start = time.time()
        try:
            building_source = VectorSource(buildings_path, height_field="height")
            buildings = query_features_in_tile(
                building_source, bounds,
                buffer_meters=50,  # Include buildings that cast shadows into tile
                min_height=2.0,
            )
            print(f"  ✓ Buildings: {len(buildings)} in tile bounds")
            print(f"    Loaded in {time.time()-start:.2f}s")

            if buildings:
                heights = [b.height for b in buildings if b.height > 0]
                if heights:
                    print(f"    Height range: {min(heights):.1f}m to {max(heights):.1f}m")
        except Exception as e:
            print(f"  ✗ Failed to load buildings: {e}")
    else:
        print(f"  ⚠ Buildings file not found: {buildings_path}")

    if trees_path.exists():
        start = time.time()
        try:
            tree_source = VectorSource(trees_path, height_field="height")
            trees = query_features_in_tile(
                tree_source, bounds,
                buffer_meters=30,
                min_height=3.0,
            )
            print(f"  ✓ Trees: {len(trees)} in tile bounds")
            print(f"    Loaded in {time.time()-start:.2f}s")
        except Exception as e:
            print(f"  ✗ Failed to load trees: {e}")
    else:
        print(f"  ⚠ Trees file not found: {trees_path}")

    # Step 4: Run V2 pipeline
    print(f"\n[4/5] Running V2 pipeline (preset: {preset_name})...")
    preset = get_preset(preset_name)
    print(f"  Sun position: azimuth={preset.azimuth}°, altitude={preset.altitude}°")
    print(f"  Ray trace samples: {ray_trace_samples}")

    stages_times = {}

    def progress(stage, p):
        if p == 0:
            stages_times[stage] = time.time()
            print(f"  Starting: {stage}...")
        elif p == 1:
            elapsed = time.time() - stages_times.get(stage, time.time())
            print(f"  Completed: {stage} ({elapsed:.2f}s)")

    start = time.time()
    try:
        result = composite_tile_v2(
            satellite=satellite,
            elevation=elevation,
            buildings=buildings,
            trees=trees,
            bounds=bounds,
            preset_name=preset_name,
            remove_shadows=True,
            shadow_removal_method="color_transfer",  # Fast fallback
            ray_trace_samples=ray_trace_samples,
            progress_callback=progress,
        )
        total_time = time.time() - start
        print(f"\n  ✓ Total pipeline time: {total_time:.2f}s")
    except Exception as e:
        print(f"\n  ✗ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        result = satellite  # Fall back to original

    # Step 5: Generate comparison images
    print("\n[5/5] Saving output images...")

    # Save main outputs
    Image.fromarray(satellite).save(output_dir / "01_original_satellite.png")
    print(f"  Saved: 01_original_satellite.png")

    Image.fromarray(result).save(output_dir / "02_v2_result.png")
    print(f"  Saved: 02_v2_result.png")

    # Generate pipeline stage previews
    try:
        print("\n  Generating stage previews...")
        previews = preview_v2_pipeline(
            satellite, elevation, buildings, trees, bounds, preset_name
        )
        for name, img in sorted(previews.items()):
            Image.fromarray(img).save(output_dir / f"stage_{name}.png")
            print(f"  Saved: stage_{name}.png")
    except Exception as e:
        print(f"  ⚠ Could not generate previews: {e}")

    # Create side-by-side comparison
    try:
        comparison = np.concatenate([satellite, result], axis=1)
        Image.fromarray(comparison).save(output_dir / "comparison_side_by_side.png")
        print(f"  Saved: comparison_side_by_side.png")
    except Exception as e:
        print(f"  ⚠ Could not create comparison: {e}")

    print(f"\n{'='*60}")
    print(f"Output saved to: {output_dir.absolute()}")
    print(f"{'='*60}")

    return result, satellite


def main():
    parser = argparse.ArgumentParser(description="Test V2 pipeline on real tile")
    parser.add_argument(
        "--tile", "-t",
        default="16/34322/22950",
        help="Tile coordinates as z/x/y (default: 16/34322/22950 - central Zurich)"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("test_output/real_tile"),
        help="Output directory"
    )
    parser.add_argument(
        "--preset", "-p",
        default="afternoon",
        choices=["morning", "afternoon", "evening", "golden_hour"],
        help="Time preset"
    )
    parser.add_argument(
        "--samples", "-s",
        type=int,
        default=1,
        help="Ray trace samples (1=hard shadows, 4+=soft)"
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open output images after generation"
    )

    args = parser.parse_args()

    # Parse tile coordinates
    parts = args.tile.split("/")
    if len(parts) != 3:
        print(f"Invalid tile format: {args.tile}")
        print("Expected format: z/x/y (e.g., 16/34322/22950)")
        return 1

    z, x, y = map(int, parts)

    result, original = run_real_tile_test(
        z=z, x=x, y=y,
        output_dir=args.output,
        preset_name=args.preset,
        ray_trace_samples=args.samples,
    )

    if args.open:
        import subprocess
        subprocess.run(["open", str(args.output)])

    return 0


if __name__ == "__main__":
    exit(main())
