#!/usr/bin/env python3
"""
Test the LOD2 roof integration pipeline end-to-end.

This script:
1. Downloads a small sample of LOD2 building data
2. Extracts roof faces from the OBJ files
3. Outputs GeoJSON ready for deck.gl visualization

Usage:
    python scripts/test_lod2_pipeline.py
    python scripts/test_lod2_pipeline.py --max-buildings 20
    python scripts/test_lod2_pipeline.py --skip-download  # Use cached data
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser(description="Test LOD2 roof pipeline")
    parser.add_argument(
        "--max-buildings", "-n",
        type=int,
        default=30,
        help="Maximum buildings to process (default: 30)"
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download, use existing OBJ files"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=PROJECT_ROOT / "public" / "data",
        help="Output directory for GeoJSON"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("LOD2 ROOF PIPELINE TEST")
    print("=" * 60)

    # Paths
    obj_dir = PROJECT_ROOT / "data" / "raw" / "lod2-buildings"
    metadata_path = obj_dir / "metadata.json"
    output_path = args.output_dir / "zurich-roofs.geojson"

    # Step 1: Download LOD2 data
    if not args.skip_download:
        print("\n[Step 1/3] Downloading LOD2 building data...")
        print("-" * 40)

        from scripts.download.lod2_buildings import download_lod2_buildings

        try:
            download_lod2_buildings(
                output_dir=obj_dir,
                city_center_only=True,
                max_buildings=args.max_buildings,
                cache_zip=True,
            )
        except Exception as e:
            print(f"Error downloading LOD2 data: {e}")
            print("Tip: If the download fails, you can manually download from:")
            print("  https://www.ogd.stadt-zuerich.ch/geoportal_data_static/BEBAUUNG_3D_1500.zip")
            return 1
    else:
        print("\n[Step 1/3] Skipping download (using cached data)")
        if not obj_dir.exists():
            print(f"Error: OBJ directory not found: {obj_dir}")
            print("Run without --skip-download first.")
            return 1

    # Check we have OBJ files
    obj_files = list(obj_dir.glob("*.obj"))
    if not obj_files:
        print(f"Error: No OBJ files found in {obj_dir}")
        return 1

    print(f"Found {len(obj_files)} OBJ files")

    # Step 2: Extract roof faces
    print("\n[Step 2/3] Extracting roof faces from OBJ files...")
    print("-" * 40)

    from scripts.process.extract_roof_faces import extract_all_roof_faces

    try:
        stats = extract_all_roof_faces(
            input_dir=obj_dir,
            output_path=output_path,
            max_buildings=args.max_buildings,
        )
    except Exception as e:
        print(f"Error extracting roof faces: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Step 3: Verify output
    print("\n[Step 3/3] Verifying output...")
    print("-" * 40)

    if not output_path.exists():
        print(f"Error: Output file not created: {output_path}")
        return 1

    # Load and display sample
    with open(output_path) as f:
        data = json.load(f)

    features = data.get("features", [])
    print(f"Output file: {output_path}")
    print(f"Total roof faces: {len(features)}")

    if features:
        # Show sample feature
        sample = features[0]
        print("\nSample roof face:")
        print(f"  Building ID: {sample['properties']['building_id']}")
        print(f"  Roof type: {sample['properties']['roof_type']}")
        print(f"  Slope angle: {sample['properties']['slope_angle']}°")
        print(f"  Orientation: {sample['properties']['orientation']}")
        print(f"  Material: {sample['properties']['material']}")
        print(f"  Area: {sample['properties']['area_m2']} m²")

        # Show coordinate sample
        coords = sample['geometry']['coordinates'][0][0]
        print(f"  First vertex: [{coords[0]:.6f}, {coords[1]:.6f}, {coords[2]:.1f}]")

    # Summary
    print("\n" + "=" * 60)
    print("PIPELINE TEST COMPLETE")
    print("=" * 60)
    print(f"\nTo view in deck.gl:")
    print(f"  1. The GeoJSON is at: {output_path}")
    print(f"  2. Load it with the RoofsLayer in your viewer")
    print(f"\nRoof statistics:")
    print(f"  Buildings processed: {stats.get('total_buildings', 0)}")
    print(f"  Buildings with roofs: {stats.get('buildings_with_roofs', 0)}")
    print(f"  Total roof faces: {stats.get('total_roof_faces', 0)}")
    print(f"  Average slope: {stats.get('avg_slope', 0):.1f}°")

    # Show roof type distribution
    roof_types = stats.get("roof_types", {})
    if roof_types:
        print("\nRoof type distribution:")
        for rt, count in sorted(roof_types.items(), key=lambda x: -x[1]):
            pct = count / stats.get('buildings_with_roofs', 1) * 100
            print(f"  {rt}: {count} ({pct:.0f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
