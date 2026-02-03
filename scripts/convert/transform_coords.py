#!/usr/bin/env python3
"""
Transform GeoJSON coordinates from Swiss LV95 (EPSG:2056) to WGS84 (EPSG:4326).

This is required because deck.gl uses WGS84 coordinates.
"""

import json
from pathlib import Path
from typing import Union
from pyproj import Transformer
from tqdm import tqdm


# Create transformer (cached for performance)
transformer = Transformer.from_crs(
    "EPSG:2056",  # Swiss LV95
    "EPSG:4326",  # WGS84
    always_xy=True  # Ensure x=easting, y=northing -> x=lng, y=lat
)


def transform_coordinate(e: float, n: float) -> tuple[float, float]:
    """
    Transform a single coordinate from LV95 to WGS84.

    Args:
        e: Easting (LV95)
        n: Northing (LV95)

    Returns:
        (longitude, latitude) in WGS84
    """
    lng, lat = transformer.transform(e, n)
    return (round(lng, 7), round(lat, 7))


def transform_ring(ring: list[list[float]]) -> list[list[float]]:
    """Transform a polygon ring."""
    return [list(transform_coordinate(coord[0], coord[1])) for coord in ring]


def transform_geometry(geometry: dict) -> dict:
    """Transform a GeoJSON geometry."""
    geom_type = geometry["type"]
    coords = geometry["coordinates"]

    if geom_type == "Point":
        new_coords = list(transform_coordinate(coords[0], coords[1]))

    elif geom_type == "LineString":
        new_coords = [list(transform_coordinate(c[0], c[1])) for c in coords]

    elif geom_type == "Polygon":
        new_coords = [transform_ring(ring) for ring in coords]

    elif geom_type == "MultiPolygon":
        new_coords = [[transform_ring(ring) for ring in polygon] for polygon in coords]

    elif geom_type == "MultiPoint":
        new_coords = [list(transform_coordinate(c[0], c[1])) for c in coords]

    elif geom_type == "MultiLineString":
        new_coords = [[list(transform_coordinate(c[0], c[1])) for c in line] for line in coords]

    else:
        raise ValueError(f"Unsupported geometry type: {geom_type}")

    return {
        "type": geom_type,
        "coordinates": new_coords
    }


def transform_geojson(
    input_path: Path,
    output_path: Path
) -> int:
    """
    Transform a GeoJSON file from LV95 to WGS84.

    Args:
        input_path: Input GeoJSON file (LV95)
        output_path: Output GeoJSON file (WGS84)

    Returns:
        Number of features transformed
    """
    print(f"Reading {input_path}...")
    with open(input_path, 'r') as f:
        data = json.load(f)

    if data["type"] != "FeatureCollection":
        raise ValueError("Expected GeoJSON FeatureCollection")

    features = data["features"]
    print(f"Transforming {len(features)} features...")

    for feature in tqdm(features, desc="Transforming"):
        feature["geometry"] = transform_geometry(feature["geometry"])

    # Update CRS to WGS84
    output_data = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {
                "name": "EPSG:4326"
            }
        },
        "features": features
    }

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(output_data, f)

    print(f"Wrote {len(features)} features to {output_path}")
    return len(features)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Transform GeoJSON from LV95 to WGS84"
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Input GeoJSON file (LV95)"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output GeoJSON file (default: replace -lv95 with -wgs84)"
    )

    args = parser.parse_args()

    output_path = args.output
    if not output_path:
        stem = args.input.stem.replace("-lv95", "")
        output_path = args.input.parent / f"{stem}-wgs84.geojson"

    transform_geojson(args.input, output_path)


if __name__ == "__main__":
    main()
