#!/usr/bin/env python3
"""
Convert GPKG (GeoPackage) to GeoJSON with height properties.

Handles the Stadt Zürich Blockmodell format which contains building polygons
with height attributes (TRAUFE for eaves height, FIRST for ridge height).
"""

import json
from pathlib import Path
from typing import Optional
import geopandas as gpd


def convert_gpkg_to_geojson(
    input_path: Path,
    output_path: Path,
    layer: Optional[str] = None
) -> int:
    """
    Convert GPKG to GeoJSON, preserving height attributes.

    Args:
        input_path: Input GPKG file
        output_path: Output GeoJSON file
        layer: Specific layer to read (default: first layer)

    Returns:
        Number of features converted
    """
    print(f"Reading {input_path}...")

    # Read GPKG (geopandas handles layer selection automatically)
    if layer:
        gdf = gpd.read_file(input_path, layer=layer)
    else:
        gdf = gpd.read_file(input_path)

    print(f"Found {len(gdf)} features")
    print(f"CRS: {gdf.crs}")
    print(f"Columns: {list(gdf.columns)}")

    # Identify height columns
    # Common names: HOEHE, HEIGHT, TRAUFE (eaves), FIRST (ridge), DACHHOEHE
    height_keywords = ['HOEHE', 'HEIGHT', 'TRAUFE', 'FIRST', 'DACH']
    height_cols = [
        c for c in gdf.columns
        if any(h in c.upper() for h in height_keywords)
    ]

    if height_cols:
        print(f"Height columns found: {height_cols}")
    else:
        print("Warning: No height columns found, using default height")

    # Build features with standardized properties
    features = []
    for idx, row in gdf.iterrows():
        # Try to extract height from available columns
        height = None
        for col in height_cols:
            val = row.get(col)
            if val is not None and val == val:  # Check for NaN
                try:
                    height = float(val)
                    break
                except (ValueError, TypeError):
                    continue

        # Use default height if none found
        if height is None:
            height = 10.0

        # Get geometry as GeoJSON dict
        geom = row.geometry.__geo_interface__

        # Build standardized feature
        feature = {
            "type": "Feature",
            "properties": {
                "id": f"building_{idx}",
                "height": height,
            },
            "geometry": geom
        }

        # Preserve original ID if available
        for id_col in ['OBJECTID', 'EGID', 'ID', 'id']:
            if id_col in row.index and row[id_col] is not None:
                feature["properties"]["original_id"] = str(row[id_col])
                break

        features.append(feature)

    # Get EPSG code
    epsg = gdf.crs.to_epsg() if gdf.crs else 2056  # Default to LV95

    # Build GeoJSON structure
    geojson = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {
                "name": f"EPSG:{epsg}"
            }
        },
        "features": features
    }

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(geojson, f)

    print(f"Wrote {len(features)} buildings to {output_path}")
    return len(features)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert GPKG to GeoJSON with height properties"
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Input GPKG file"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output GeoJSON file"
    )
    parser.add_argument(
        "--layer", "-l",
        type=str,
        help="Specific layer to read"
    )

    args = parser.parse_args()

    output_path = args.output
    if not output_path:
        output_path = args.input.parent / f"{args.input.stem}.geojson"

    convert_gpkg_to_geojson(args.input, output_path, args.layer)


if __name__ == "__main__":
    main()
