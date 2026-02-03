#!/usr/bin/env python3
"""
Add terrain elevation to GeoJSON features.

Fetches Mapterhorn terrain tiles and decodes Terrarium encoding
to compute ground elevation for each feature.

Terrarium encoding: elevation = R × 256 + G + B/256 - 32768 (meters)

Usage:
    python scripts/terrain/add_elevations.py

This script reads GeoJSON files from public/data/ and adds an 'elevation'
property to each feature based on terrain data from Mapterhorn tiles.
"""

import json
import math
import requests
from io import BytesIO
from pathlib import Path
from PIL import Image
from tqdm import tqdm
from typing import Optional, Tuple, List

# Mapterhorn terrain tiles (same source as deck.gl TerrainLayer)
TERRAIN_URL = "https://tiles.mapterhorn.com/{z}/{x}/{y}.webp"
ZOOM = 13  # Good balance between coverage and resolution
TILE_SIZE = 512

# Zurich bounds (approximately)
ZURICH_BOUNDS = {
    "min_lng": 8.48,
    "max_lng": 8.60,
    "min_lat": 47.34,
    "max_lat": 47.42,
}

# Default elevation fallback (Zurich city center)
DEFAULT_ELEVATION = 408

# Tile cache (avoid re-downloading same tiles)
tile_cache: dict[str, Image.Image] = {}


def lng_lat_to_tile(lng: float, lat: float, zoom: int) -> Tuple[int, int]:
    """Convert lng/lat (WGS84) to tile coordinates at given zoom level."""
    x = int((lng + 180) / 360 * (2 ** zoom))
    lat_rad = math.radians(lat)
    y = int((1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * (2 ** zoom))
    return x, y


def lng_lat_to_pixel(lng: float, lat: float, tile_x: int, tile_y: int, zoom: int) -> Tuple[int, int]:
    """Convert lng/lat to pixel position within a specific tile."""
    scale = 2 ** zoom
    world_x = (lng + 180) / 360 * scale
    lat_rad = math.radians(lat)
    world_y = (1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * scale

    pixel_x = int((world_x - tile_x) * TILE_SIZE)
    pixel_y = int((world_y - tile_y) * TILE_SIZE)
    return pixel_x, pixel_y


def decode_terrarium(r: int, g: int, b: int) -> float:
    """
    Decode Terrarium RGB to elevation in meters.

    Terrarium encoding: elevation = R × 256 + G + B/256 - 32768
    """
    return r * 256 + g + b / 256 - 32768


def fetch_tile(x: int, y: int, z: int) -> Optional[Image.Image]:
    """Fetch and cache a terrain tile from Mapterhorn."""
    key = f"{z}/{x}/{y}"

    if key in tile_cache:
        return tile_cache[key]

    url = TERRAIN_URL.format(z=z, x=x, y=y)

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert("RGB")
        tile_cache[key] = img
        return img
    except Exception as e:
        print(f"Warning: Failed to fetch tile {key}: {e}")
        return None


def get_elevation(lng: float, lat: float) -> float:
    """
    Get terrain elevation at a specific coordinate.

    Returns DEFAULT_ELEVATION if tile fetch fails or point is outside bounds.
    """
    # Check bounds
    if not (ZURICH_BOUNDS["min_lng"] <= lng <= ZURICH_BOUNDS["max_lng"] and
            ZURICH_BOUNDS["min_lat"] <= lat <= ZURICH_BOUNDS["max_lat"]):
        return DEFAULT_ELEVATION

    tile_x, tile_y = lng_lat_to_tile(lng, lat, ZOOM)
    tile = fetch_tile(tile_x, tile_y, ZOOM)

    if tile is None:
        return DEFAULT_ELEVATION

    pixel_x, pixel_y = lng_lat_to_pixel(lng, lat, tile_x, tile_y, ZOOM)

    # Clamp to tile bounds
    pixel_x = max(0, min(pixel_x, TILE_SIZE - 1))
    pixel_y = max(0, min(pixel_y, TILE_SIZE - 1))

    r, g, b = tile.getpixel((pixel_x, pixel_y))
    return decode_terrarium(r, g, b)


def get_centroid(coords: List[List[float]]) -> Optional[List[float]]:
    """Get centroid of polygon coordinates (simple average)."""
    if not coords:
        return None

    sum_lng = sum(c[0] for c in coords)
    sum_lat = sum(c[1] for c in coords)
    return [sum_lng / len(coords), sum_lat / len(coords)]


def extract_position(geometry: dict) -> Optional[List[float]]:
    """
    Extract a representative position from GeoJSON geometry.

    Handles: Point, Polygon, MultiPolygon, MultiPoint, MultiLineString
    """
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates")

    if not coords:
        return None

    if geom_type == "Point":
        return coords[:2]  # [lng, lat]

    elif geom_type == "MultiPoint":
        # Take first point
        if coords and len(coords) > 0:
            return coords[0][:2]

    elif geom_type == "Polygon":
        # Get centroid of outer ring
        outer_ring = coords[0] if coords else []
        return get_centroid(outer_ring)

    elif geom_type == "MultiPolygon":
        # Get centroid of first polygon's outer ring
        if coords and len(coords) > 0:
            first_polygon = coords[0]
            outer_ring = first_polygon[0] if first_polygon else []
            return get_centroid(outer_ring)

    elif geom_type in ("LineString", "MultiLineString"):
        # Take midpoint of first line
        if geom_type == "MultiLineString":
            coords = coords[0] if coords else []
        if coords and len(coords) > 0:
            mid_idx = len(coords) // 2
            return coords[mid_idx][:2]

    return None


def add_elevations_to_geojson(input_path: Path, output_path: Optional[Path] = None) -> int:
    """
    Add elevation property to each feature in a GeoJSON file.

    Args:
        input_path: Path to input GeoJSON file
        output_path: Path to output file (defaults to same as input)

    Returns:
        Number of features processed
    """
    output_path = output_path or input_path

    print(f"Reading {input_path}...")
    with open(input_path, 'r') as f:
        data = json.load(f)

    features = data.get("features", [])
    if not features:
        print(f"No features found in {input_path}")
        return 0

    print(f"Processing {len(features)} features...")
    processed = 0
    skipped = 0

    for feature in tqdm(features, desc="Adding elevations"):
        geometry = feature.get("geometry")
        if not geometry:
            skipped += 1
            continue

        position = extract_position(geometry)
        if not position:
            skipped += 1
            continue

        elevation = get_elevation(position[0], position[1])

        # Add elevation to properties
        if "properties" not in feature:
            feature["properties"] = {}
        feature["properties"]["elevation"] = round(elevation, 1)
        processed += 1

    print(f"Writing to {output_path}...")
    with open(output_path, 'w') as f:
        json.dump(data, f)

    print(f"Added elevations to {processed} features ({skipped} skipped)")
    print(f"Tiles cached: {len(tile_cache)}")

    # Print elevation statistics
    elevations = [f["properties"]["elevation"] for f in features if "properties" in f and "elevation" in f["properties"]]
    if elevations:
        print(f"Elevation range: {min(elevations):.1f}m - {max(elevations):.1f}m")
        print(f"Mean elevation: {sum(elevations)/len(elevations):.1f}m")

    return processed


def main():
    """Process all GeoJSON files in public/data/."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Add terrain elevation to GeoJSON features"
    )
    parser.add_argument(
        "--file", "-f",
        type=Path,
        help="Process a specific GeoJSON file"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output file (defaults to overwrite input)"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Process all standard GeoJSON files (buildings, trees, lights)"
    )

    args = parser.parse_args()

    # Default data directory
    data_dir = Path(__file__).parent.parent.parent / "public" / "data"

    if args.file:
        add_elevations_to_geojson(args.file, args.output)
    elif args.all:
        # Process standard files
        files = [
            data_dir / "zurich-buildings.geojson",
            data_dir / "zurich-trees.geojson",
            data_dir / "zurich-lights.geojson",
        ]

        for file_path in files:
            if file_path.exists():
                print(f"\n{'='*60}")
                add_elevations_to_geojson(file_path)
            else:
                print(f"Skipping {file_path} (not found)")
    else:
        # Default: process all three files
        print("Processing buildings, trees, and lights...")
        print("Use --file to process a specific file, or --all for explicit all")

        files = [
            ("zurich-buildings.geojson", "polygon"),
            ("zurich-trees.geojson", "point"),
            ("zurich-lights.geojson", "point"),
        ]

        for filename, _ in files:
            file_path = data_dir / filename
            if file_path.exists():
                print(f"\n{'='*60}")
                add_elevations_to_geojson(file_path)
            else:
                print(f"Skipping {file_path} (not found)")


if __name__ == "__main__":
    main()
