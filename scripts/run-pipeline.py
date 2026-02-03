#!/usr/bin/env python3
"""
Run the complete data pipeline for Zurich 3D buildings.

Steps for sample data:
1. Generate sample buildings (LV95)
2. Transform coordinates LV95 → WGS84
3. Create tiles or merged file
4. Validate output

Steps for real data (--real-data):
1. Download via WFS (already in WGS84)
2. Create tiles or merged file
3. Validate output
"""

import subprocess
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"Step: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)

    result = subprocess.run(cmd)
    success = result.returncode == 0

    if not success:
        print(f"❌ Failed: {description}")
    else:
        print(f"✓ Completed: {description}")

    return success


def run_pipeline(use_samples: bool = True, create_tiles: bool = False):
    """
    Run the data pipeline.

    Args:
        use_samples: Use sample data instead of downloading real data
        create_tiles: Create tiled output instead of single file
    """
    python = sys.executable

    steps = []

    if use_samples:
        # Create sample buildings (LV95)
        steps.append((
            [python, str(SCRIPTS_DIR / "convert/obj_to_geojson.py"),
             "--sample", "--sample-count", "500",
             "-o", str(PROJECT_ROOT / "data/processed/buildings-lv95.geojson")],
            "Create sample buildings (LV95)"
        ))

        # Transform coordinates LV95 → WGS84
        steps.append((
            [python, str(SCRIPTS_DIR / "convert/transform_coords.py"),
             str(PROJECT_ROOT / "data/processed/buildings-lv95.geojson"),
             "-o", str(PROJECT_ROOT / "data/processed/buildings-wgs84.geojson")],
            "Transform coordinates to WGS84"
        ))

        input_file = PROJECT_ROOT / "data/processed/buildings-wgs84.geojson"
    else:
        # Download real data via WFS (already in WGS84)
        steps.append((
            [python, str(SCRIPTS_DIR / "download/buildings.py"),
             "-o", str(PROJECT_ROOT / "data/raw")],
            "Download building data via WFS"
        ))

        # WFS data is already in WGS84, no transformation needed
        input_file = PROJECT_ROOT / "data/raw/buildings-wfs.geojson"

    # Create tiles or single file
    if create_tiles:
        steps.append((
            [python, str(SCRIPTS_DIR / "convert/tile_buildings.py"),
             str(input_file),
             "-o", str(PROJECT_ROOT / "public/data/tiles/buildings")],
            "Create spatial tiles"
        ))
    else:
        steps.append((
            [python, str(SCRIPTS_DIR / "convert/tile_buildings.py"),
             str(input_file),
             "--single",
             "-o", str(PROJECT_ROOT / "public/data/zurich-buildings.geojson")],
            "Create merged GeoJSON"
        ))

    # Validate output
    output_file = (
        PROJECT_ROOT / "public/data/tiles/buildings/tile-index.json"
        if create_tiles
        else PROJECT_ROOT / "public/data/zurich-buildings.geojson"
    )
    steps.append((
        [python, str(SCRIPTS_DIR / "validate/check_data.py"),
         str(output_file if output_file.exists() else PROJECT_ROOT / "public/data/zurich-buildings.geojson"),
         "--sample", "100"],
        "Validate output"
    ))

    # Run all steps
    for cmd, description in steps:
        if not run_command(cmd, description):
            print(f"\n❌ Pipeline failed at: {description}")
            return False

    print("\n" + "="*60)
    print("✓ Pipeline completed successfully!")
    print("="*60)
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run data pipeline")
    parser.add_argument(
        "--real-data",
        action="store_true",
        help="Download real data instead of using samples"
    )
    parser.add_argument(
        "--tiles",
        action="store_true",
        help="Create tiled output instead of single file"
    )

    args = parser.parse_args()

    success = run_pipeline(
        use_samples=not args.real_data,
        create_tiles=args.tiles
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
