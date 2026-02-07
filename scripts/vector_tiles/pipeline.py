#!/usr/bin/env python3
"""
Vector Tile Pipeline for Zurich

Creates PMTiles vector tiles from GeoJSON data using Tippecanoe.
Supports optional "wobble" effect for hand-drawn appearance and
"tilt" effect for isometric/oblique projection.

Usage:
    python -m scripts.vector_tiles.pipeline all           # Full pipeline
    python -m scripts.vector_tiles.pipeline all --wobble  # With hand-drawn effect
    python -m scripts.vector_tiles.pipeline all --tilt    # With isometric projection
    python -m scripts.vector_tiles.pipeline prepare       # Just preprocess data
    python -m scripts.vector_tiles.pipeline generate      # Just create tiles
    python -m scripts.vector_tiles.pipeline convert       # MBTiles -> PMTiles
    python -m scripts.vector_tiles.pipeline style         # Generate style.json
"""

import argparse
import subprocess
import sys
import shutil
import json
from pathlib import Path
from datetime import datetime

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "public" / "data"
OUTPUT_DIR = PROJECT_ROOT / "public" / "tiles" / "vector"
TEMP_DIR = PROJECT_ROOT / "temp" / "vector_tiles"

# Source files
SOURCE_FILES = {
    "water": DATA_DIR / "zurich-water.geojson",
    "buildings": DATA_DIR / "zurich-buildings.geojson",
    "roofs": DATA_DIR / "zurich-roofs.geojson",
    "streets": DATA_DIR / "zurich-streets.geojson",
    "trees": DATA_DIR / "zurich-trees.geojson",
    "tram_tracks": DATA_DIR / "zurich-tram-tracks.geojson",
    "tram_poles": DATA_DIR / "zurich-tram-poles.geojson",
    "lights": DATA_DIR / "zurich-lights.geojson",
    "benches": DATA_DIR / "zurich-benches.geojson",
    "fountains": DATA_DIR / "zurich-fountains.geojson",
    "toilets": DATA_DIR / "zurich-toilets.geojson",
}


def check_prerequisites() -> bool:
    """Check that required tools are installed."""
    print("Checking prerequisites...")

    # Check tippecanoe
    try:
        result = subprocess.run(
            ["tippecanoe", "--version"],
            capture_output=True,
            text=True
        )
        version = result.stdout.strip() or result.stderr.strip()
        print(f"  ✓ tippecanoe: {version}")
    except FileNotFoundError:
        print("  ✗ tippecanoe not found. Install with: brew install tippecanoe")
        return False

    # Check pmtiles
    try:
        result = subprocess.run(
            ["pmtiles"],
            capture_output=True,
            text=True
        )
        print("  ✓ pmtiles CLI available")
    except FileNotFoundError:
        print("  ✗ pmtiles not found. Install with: brew install pmtiles")
        return False

    # Check source files
    missing = []
    for name, path in SOURCE_FILES.items():
        if not path.exists():
            missing.append(name)

    if missing:
        print(f"  ✗ Missing source files: {', '.join(missing)}")
        return False

    print(f"  ✓ All {len(SOURCE_FILES)} source files found")
    return True


def prepare_data(wobble: bool = False, tilt: bool = False, verbose: bool = False):
    """
    Prepare GeoJSON data for tile generation.
    - Sample trees at different zoom levels
    - Optionally apply wobble distortion
    - Optionally apply isometric tilt projection
    """
    from .prepare_data import (
        sample_trees,
        apply_wobble,
        apply_isometric_tilt,
        create_shadow_geometry,
        transform_streets,
        combine_poi_layers
    )

    print("\n" + "=" * 60)
    print("PHASE 1: DATA PREPARATION")
    print("=" * 60)

    # Create temp directory
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Sample trees for different zoom levels
    print("\n[1/5] Sampling trees by zoom level...")
    trees_path = SOURCE_FILES["trees"]
    sample_trees(
        trees_path,
        TEMP_DIR / "trees-z14.geojson",
        sample_rate=10,  # 1 in 10
        verbose=verbose
    )
    sample_trees(
        trees_path,
        TEMP_DIR / "trees-z15.geojson",
        sample_rate=5,   # 1 in 5
        verbose=verbose
    )
    print(f"  Created: trees-z14.geojson, trees-z15.geojson")

    # 2. Transform streets (add class from street_type)
    print("\n[2/5] Transforming street data...")
    transform_streets(
        SOURCE_FILES["streets"],
        TEMP_DIR / "streets-transformed.geojson",
        verbose=verbose
    )
    print(f"  Created: streets-transformed.geojson")

    # 3. Create building shadow geometry
    print("\n[3/5] Generating building shadows...")
    create_shadow_geometry(
        SOURCE_FILES["buildings"],
        TEMP_DIR / "building-shadows.geojson",
        offset_x=3.0,  # meters
        offset_y=3.0,
        verbose=verbose
    )
    print(f"  Created: building-shadows.geojson")

    # 4. Combine POI layers
    print("\n[4/5] Combining POI layers...")
    combine_poi_layers(
        {
            "bench": SOURCE_FILES["benches"],
            "fountain": SOURCE_FILES["fountains"],
            "toilets": SOURCE_FILES["toilets"],
            "street_lamp": SOURCE_FILES["lights"],
            "utility_pole": SOURCE_FILES["tram_poles"],
        },
        TEMP_DIR / "poi-combined.geojson",
        verbose=verbose
    )
    print(f"  Created: poi-combined.geojson")

    # 5. Apply wobble and/or tilt if requested
    layers_to_transform = ["buildings", "building-shadows", "roofs", "streets-transformed"]

    if wobble and tilt:
        print("\n[5/5] Applying wobble + tilt distortion...")
        for layer in layers_to_transform:
            # Determine source path
            if layer in ["buildings", "roofs"]:
                input_path = SOURCE_FILES.get(layer)
            else:
                input_path = TEMP_DIR / f"{layer}.geojson"

            if input_path and input_path.exists():
                # First apply tilt
                tilted_path = TEMP_DIR / f"{layer}-tilted.geojson"
                apply_isometric_tilt(input_path, tilted_path, shear=0.3, compress_y=0.85, verbose=verbose)

                # Then apply wobble to the tilted version
                output_path = TEMP_DIR / f"{layer}-tilted.geojson"
                apply_wobble(tilted_path, output_path, scale=0.00005, octaves=3, verbose=verbose)
        print(f"  Applied wobble + tilt to {len(layers_to_transform)} layers")

    elif tilt:
        print("\n[5/5] Applying isometric tilt...")
        for layer in layers_to_transform:
            if layer in ["buildings", "roofs"]:
                input_path = SOURCE_FILES.get(layer)
            else:
                input_path = TEMP_DIR / f"{layer}.geojson"

            if input_path and input_path.exists():
                output_path = TEMP_DIR / f"{layer}-tilted.geojson"
                apply_isometric_tilt(input_path, output_path, shear=0.3, compress_y=0.85, verbose=verbose)
        print(f"  Applied tilt to {len(layers_to_transform)} layers")

    elif wobble:
        print("\n[5/5] Applying wobble distortion...")
        for layer in layers_to_transform:
            if layer in ["buildings", "roofs"]:
                input_path = SOURCE_FILES.get(layer)
            else:
                input_path = TEMP_DIR / f"{layer}.geojson"

            if input_path and input_path.exists():
                output_path = TEMP_DIR / f"{layer}-wobbled.geojson"
                apply_wobble(input_path, output_path, scale=0.00005, octaves=3, verbose=verbose)
        print(f"  Applied wobble to {len(layers_to_transform)} layers")

    else:
        print("\n[5/5] Skipping effects (use --wobble or --tilt to enable)")

    print("\n✓ Data preparation complete")


def generate_tiles(wobble: bool = False, tilt: bool = False, verbose: bool = False):
    """Run Tippecanoe to create MBTiles."""
    print("\n" + "=" * 60)
    print("PHASE 2: TILE GENERATION (Tippecanoe)")
    print("=" * 60)

    # Determine output name based on effects
    if wobble and tilt:
        output_name = "zurich-wobble-tilt"
        tile_label = "(Wobble + Tilt)"
    elif tilt:
        output_name = "zurich-tilt"
        tile_label = "(Isometric)"
    elif wobble:
        output_name = "zurich-wobble"
        tile_label = "(Wobble)"
    else:
        output_name = "zurich-vector"
        tile_label = ""

    mbtiles_path = OUTPUT_DIR / f"{output_name}.mbtiles"

    # Build tippecanoe command
    cmd = [
        "tippecanoe",
        "-o", str(mbtiles_path),
        "-z18", "-Z0",
        "--force",
        "--no-feature-limit",
        "--no-tile-size-limit",
        "--drop-densest-as-needed",
        "--extend-zooms-if-still-dropping",
        f"--name=Zurich Vector Tiles {tile_label}",
        "--description=Custom vector tiles for Zurich 3D visualization",
        "--attribution=© Stadt Zürich (Open Data), swisstopo",
    ]

    # Add layer definitions with zoom ranges
    layers = _get_layer_definitions(wobble, tilt)
    for layer in layers:
        cmd.extend(layer["args"])

    if verbose:
        print(f"\nCommand: {' '.join(cmd[:10])}...")

    print(f"\nGenerating tiles...")
    print(f"  Output: {mbtiles_path}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=not verbose,
            text=True,
            check=True
        )
        if verbose and result.stdout:
            print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Tippecanoe failed:")
        print(e.stderr)
        sys.exit(1)

    # Get file size
    size_mb = mbtiles_path.stat().st_size / (1024 * 1024)
    print(f"\n✓ MBTiles created: {size_mb:.1f} MB")


def _get_layer_definitions(wobble: bool, tilt: bool = False) -> list:
    """Get Tippecanoe layer definitions."""
    # Determine the suffix based on applied effects
    if wobble and tilt:
        suffix = "-tilted"  # wobble is applied on top of tilt, so file is named -tilted
    elif tilt:
        suffix = "-tilted"
    elif wobble:
        suffix = "-wobbled"
    else:
        suffix = ""

    def temp_or_source(name: str, source_key: str = None) -> Path:
        """Get path from temp (if exists) or source."""
        temp_path = TEMP_DIR / f"{name}{suffix}.geojson"
        if temp_path.exists():
            return temp_path
        temp_path_no_suffix = TEMP_DIR / f"{name}.geojson"
        if temp_path_no_suffix.exists():
            return temp_path_no_suffix
        if source_key:
            return SOURCE_FILES[source_key]
        return SOURCE_FILES.get(name, TEMP_DIR / f"{name}.geojson")

    return [
        # Water (all zoom levels)
        {
            "name": "water",
            "args": [
                f"--named-layer=water:{SOURCE_FILES['water']}",
                "--minimum-zoom=0",
                "--maximum-zoom=18",
            ]
        },
        # Buildings
        {
            "name": "buildings",
            "args": [
                f"--named-layer=buildings:{temp_or_source('buildings', 'buildings')}",
                "--minimum-zoom=12",
                "--maximum-zoom=18",
            ]
        },
        # Building shadows
        {
            "name": "building_shadows",
            "args": [
                f"--named-layer=building_shadows:{temp_or_source('building-shadows')}",
                "--minimum-zoom=14",
                "--maximum-zoom=18",
            ]
        },
        # Roofs (high zoom only)
        {
            "name": "roofs",
            "args": [
                f"--named-layer=roofs:{temp_or_source('roofs', 'roofs')}",
                "--minimum-zoom=16",
                "--maximum-zoom=18",
            ]
        },
        # Streets/Transportation
        {
            "name": "transportation",
            "args": [
                f"--named-layer=transportation:{temp_or_source('streets-transformed')}",
                "--minimum-zoom=12",
                "--maximum-zoom=18",
            ]
        },
        # Tram tracks
        {
            "name": "railway",
            "args": [
                f"--named-layer=railway:{SOURCE_FILES['tram_tracks']}",
                "--minimum-zoom=13",
                "--maximum-zoom=18",
            ]
        },
        # Trees - sampled at z14
        {
            "name": "trees_z14",
            "args": [
                f"--named-layer=trees:{TEMP_DIR / 'trees-z14.geojson'}",
                "--minimum-zoom=14",
                "--maximum-zoom=14",
            ]
        },
        # Trees - sampled at z15
        {
            "name": "trees_z15",
            "args": [
                f"--named-layer=trees:{TEMP_DIR / 'trees-z15.geojson'}",
                "--minimum-zoom=15",
                "--maximum-zoom=15",
            ]
        },
        # Trees - full at z16+
        {
            "name": "trees",
            "args": [
                f"--named-layer=trees:{SOURCE_FILES['trees']}",
                "--minimum-zoom=16",
                "--maximum-zoom=18",
            ]
        },
        # POI (combined amenities)
        {
            "name": "poi",
            "args": [
                f"--named-layer=poi:{TEMP_DIR / 'poi-combined.geojson'}",
                "--minimum-zoom=15",
                "--maximum-zoom=18",
            ]
        },
    ]


def convert_to_pmtiles(wobble: bool = False, tilt: bool = False, verbose: bool = False):
    """Convert MBTiles to PMTiles format."""
    print("\n" + "=" * 60)
    print("PHASE 3: FORMAT CONVERSION (PMTiles)")
    print("=" * 60)

    # Determine output name based on effects
    if wobble and tilt:
        output_name = "zurich-wobble-tilt"
    elif tilt:
        output_name = "zurich-tilt"
    elif wobble:
        output_name = "zurich-wobble"
    else:
        output_name = "zurich-vector"

    mbtiles_path = OUTPUT_DIR / f"{output_name}.mbtiles"
    pmtiles_path = OUTPUT_DIR / f"{output_name}.pmtiles"

    if not mbtiles_path.exists():
        print(f"✗ MBTiles file not found: {mbtiles_path}")
        sys.exit(1)

    print(f"\nConverting: {mbtiles_path.name} -> {pmtiles_path.name}")

    cmd = ["pmtiles", "convert", str(mbtiles_path), str(pmtiles_path)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if verbose and result.stdout:
            print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"\n✗ PMTiles conversion failed:")
        print(e.stderr)
        sys.exit(1)

    # Get file size
    size_mb = pmtiles_path.stat().st_size / (1024 * 1024)
    print(f"\n✓ PMTiles created: {size_mb:.1f} MB")

    # Show tile metadata
    print("\nTile metadata:")
    show_cmd = ["pmtiles", "show", str(pmtiles_path)]
    result = subprocess.run(show_cmd, capture_output=True, text=True)
    for line in result.stdout.split("\n")[:15]:
        print(f"  {line}")


def generate_style(verbose: bool = False):
    """Generate MapLibre style.json."""
    from .generate_style import create_style

    print("\n" + "=" * 60)
    print("PHASE 4: STYLE GENERATION")
    print("=" * 60)

    style_path = OUTPUT_DIR / "zurich-style.json"
    create_style(style_path, verbose=verbose)

    size_kb = style_path.stat().st_size / 1024
    print(f"\n✓ Style created: {style_path.name} ({size_kb:.1f} KB)")


def run_all(wobble: bool = False, tilt: bool = False, verbose: bool = False):
    """Run the complete pipeline."""
    start_time = datetime.now()

    # Determine mode description
    if wobble and tilt:
        mode = "Hand-drawn isometric (wobble + tilt)"
    elif tilt:
        mode = "Isometric projection (tilt)"
    elif wobble:
        mode = "Hand-drawn (wobble)"
    else:
        mode = "Clean geometric"

    print("\n" + "=" * 60)
    print("ZURICH VECTOR TILE PIPELINE")
    print(f"Mode: {mode}")
    print(f"Started: {start_time.strftime('%H:%M:%S')}")
    print("=" * 60)

    if not check_prerequisites():
        sys.exit(1)

    prepare_data(wobble=wobble, tilt=tilt, verbose=verbose)
    generate_tiles(wobble=wobble, tilt=tilt, verbose=verbose)
    convert_to_pmtiles(wobble=wobble, tilt=tilt, verbose=verbose)
    generate_style(verbose=verbose)

    # Clean up temp files (optional)
    # shutil.rmtree(TEMP_DIR)

    elapsed = datetime.now() - start_time
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print(f"Total time: {elapsed.total_seconds():.1f}s")
    print("=" * 60)

    # Determine output name based on effects
    if wobble and tilt:
        output_name = "zurich-wobble-tilt"
    elif tilt:
        output_name = "zurich-tilt"
    elif wobble:
        output_name = "zurich-wobble"
    else:
        output_name = "zurich-vector"

    pmtiles_path = OUTPUT_DIR / f"{output_name}.pmtiles"
    style_path = OUTPUT_DIR / "zurich-style.json"

    print("\nOutput files:")
    if pmtiles_path.exists():
        print(f"  - {pmtiles_path.relative_to(PROJECT_ROOT)}")
    if style_path.exists():
        print(f"  - {style_path.relative_to(PROJECT_ROOT)}")


def main():
    parser = argparse.ArgumentParser(
        description="Vector Tile Pipeline for Zurich",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.vector_tiles.pipeline all                  # Full pipeline
  python -m scripts.vector_tiles.pipeline all --wobble         # Hand-drawn effect
  python -m scripts.vector_tiles.pipeline all --tilt           # Isometric projection
  python -m scripts.vector_tiles.pipeline all --wobble --tilt  # Hand-drawn isometric
  python -m scripts.vector_tiles.pipeline prepare              # Just preprocess
  python -m scripts.vector_tiles.pipeline generate             # Just create tiles
  python -m scripts.vector_tiles.pipeline convert              # MBTiles -> PMTiles
  python -m scripts.vector_tiles.pipeline style                # Generate style.json
        """
    )

    parser.add_argument(
        "command",
        choices=["all", "prepare", "generate", "convert", "style", "check"],
        help="Pipeline command to run"
    )
    parser.add_argument(
        "--wobble",
        action="store_true",
        help="Apply Perlin noise distortion for hand-drawn appearance"
    )
    parser.add_argument(
        "--tilt",
        action="store_true",
        help="Apply isometric/oblique projection for SimCity-style 3D effect"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed output"
    )

    args = parser.parse_args()

    if args.command == "check":
        check_prerequisites()
    elif args.command == "prepare":
        prepare_data(wobble=args.wobble, tilt=args.tilt, verbose=args.verbose)
    elif args.command == "generate":
        generate_tiles(wobble=args.wobble, tilt=args.tilt, verbose=args.verbose)
    elif args.command == "convert":
        convert_to_pmtiles(wobble=args.wobble, tilt=args.tilt, verbose=args.verbose)
    elif args.command == "style":
        generate_style(verbose=args.verbose)
    elif args.command == "all":
        run_all(wobble=args.wobble, tilt=args.tilt, verbose=args.verbose)


if __name__ == "__main__":
    main()
