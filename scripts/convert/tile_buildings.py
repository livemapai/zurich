#!/usr/bin/env python3
"""
Tile building GeoJSON into spatial grid for efficient loading.

Creates a tile index and individual tile files that can be loaded on demand.
"""

import json
from pathlib import Path
from collections import defaultdict
from typing import Optional
from tqdm import tqdm


def get_tile_key(lng: float, lat: float, tile_size: float = 0.01) -> tuple[int, int]:
    """
    Get tile key for a coordinate.

    Args:
        lng: Longitude
        lat: Latitude
        tile_size: Size of tile in degrees (default: ~1km at Zurich)

    Returns:
        (tile_x, tile_y) indices
    """
    tile_x = int(lng / tile_size)
    tile_y = int(lat / tile_size)
    return (tile_x, tile_y)


def get_feature_centroid(feature: dict) -> tuple[float, float]:
    """Get the centroid of a feature's geometry."""
    geom = feature["geometry"]
    coords = geom["coordinates"]

    if geom["type"] == "Polygon":
        ring = coords[0]
    elif geom["type"] == "MultiPolygon":
        ring = coords[0][0]
    else:
        raise ValueError(f"Unsupported geometry: {geom['type']}")

    # Simple centroid (average of coordinates)
    xs = [c[0] for c in ring]
    ys = [c[1] for c in ring]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def tile_geojson(
    input_path: Path,
    output_dir: Path,
    tile_size: float = 0.01
) -> dict:
    """
    Tile a GeoJSON file into spatial grid.

    Args:
        input_path: Input GeoJSON file
        output_dir: Output directory for tiles
        tile_size: Tile size in degrees

    Returns:
        Tile index dict
    """
    print(f"Reading {input_path}...")
    with open(input_path, 'r') as f:
        data = json.load(f)

    features = data["features"]
    print(f"Tiling {len(features)} features...")

    # Group features by tile
    tiles = defaultdict(list)

    for feature in tqdm(features, desc="Grouping"):
        try:
            centroid = get_feature_centroid(feature)
            tile_key = get_tile_key(centroid[0], centroid[1], tile_size)
            tiles[tile_key].append(feature)
        except Exception as e:
            print(f"Error processing feature: {e}")

    # Write tile files
    output_dir.mkdir(parents=True, exist_ok=True)
    tile_index = {
        "tileSize": tile_size,
        "tiles": {}
    }

    for (tile_x, tile_y), tile_features in tqdm(tiles.items(), desc="Writing tiles"):
        tile_name = f"tile_{tile_x}_{tile_y}.geojson"
        tile_path = output_dir / tile_name

        tile_geojson = {
            "type": "FeatureCollection",
            "features": tile_features
        }

        with open(tile_path, 'w') as f:
            json.dump(tile_geojson, f)

        # Calculate tile bounds
        all_coords = []
        for feature in tile_features:
            coords = feature["geometry"]["coordinates"]
            if feature["geometry"]["type"] == "Polygon":
                all_coords.extend(coords[0])
            elif feature["geometry"]["type"] == "MultiPolygon":
                for poly in coords:
                    all_coords.extend(poly[0])

        if all_coords:
            min_lng = min(c[0] for c in all_coords)
            max_lng = max(c[0] for c in all_coords)
            min_lat = min(c[1] for c in all_coords)
            max_lat = max(c[1] for c in all_coords)

            tile_index["tiles"][f"{tile_x},{tile_y}"] = {
                "file": tile_name,
                "featureCount": len(tile_features),
                "bounds": [min_lng, min_lat, max_lng, max_lat]
            }

    # Write index
    index_path = output_dir / "tile-index.json"
    with open(index_path, 'w') as f:
        json.dump(tile_index, f, indent=2)

    print(f"Created {len(tiles)} tiles in {output_dir}")
    print(f"Tile index: {index_path}")

    return tile_index


def merge_to_single_file(
    input_path: Path,
    output_path: Path
) -> int:
    """
    Create a single merged GeoJSON file for direct loading.

    For smaller datasets or when tiling isn't needed.
    """
    print(f"Reading {input_path}...")
    with open(input_path, 'r') as f:
        data = json.load(f)

    # Write minified (no indentation for smaller file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(data, f, separators=(',', ':'))

    features = len(data["features"])
    size = output_path.stat().st_size / (1024 * 1024)
    print(f"Wrote {features} features ({size:.1f} MB) to {output_path}")

    return features


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Tile GeoJSON for efficient loading")
    parser.add_argument(
        "input",
        type=Path,
        help="Input GeoJSON file"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output directory for tiles"
    )
    parser.add_argument(
        "--tile-size",
        type=float,
        default=0.01,
        help="Tile size in degrees (default: 0.01 ≈ 1km)"
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Create single merged file instead of tiles"
    )

    args = parser.parse_args()

    if args.single:
        output_path = args.output or Path("public/data/zurich-buildings.geojson")
        merge_to_single_file(args.input, output_path)
    else:
        output_dir = args.output or Path("public/data/tiles/buildings")
        tile_geojson(args.input, output_dir, args.tile_size)


if __name__ == "__main__":
    main()
