#!/usr/bin/env python3
"""
Add terrain-relative elevations to roof faces.

Unlike add_elevations.py which just adds a terrain elevation property,
this script recalculates roof 3D coordinates to be height-above-terrain
values that work correctly with deck.gl's TerrainLayer.

The problem:
- LOD2 roof Z values are absolute elevations from survey data (e.g., 423m)
- WFS buildings use Mapterhorn terrain + height (e.g., 408m + 26m = 434m)
- The two systems don't match, causing roofs to appear ~10m too low

The solution:
- Get Mapterhorn terrain elevation at each roof location
- Calculate roof height above terrain: LOD2_z - LOD2_base_elevation + offset
- Store terrain_elevation property for runtime positioning

Usage:
    python scripts/terrain/add_roof_elevations.py
    python scripts/terrain/add_roof_elevations.py --file public/data/zurich-roofs.geojson
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

# Zurich bounds (expanded to cover LOD2 extent)
ZURICH_BOUNDS = {
    "min_lng": 8.46,
    "max_lng": 8.62,
    "min_lat": 47.32,
    "max_lat": 47.44,
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


def get_terrain_elevation(lng: float, lat: float) -> float:
    """
    Get Mapterhorn terrain elevation at a specific coordinate.

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


def get_polygon_centroid(coords: List[List[float]]) -> Tuple[float, float]:
    """Get centroid of polygon coordinates."""
    if not coords:
        return (8.54, 47.37)  # Default to Zurich center

    sum_lng = sum(c[0] for c in coords)
    sum_lat = sum(c[1] for c in coords)
    return (sum_lng / len(coords), sum_lat / len(coords))


def process_roof_feature(feature: dict) -> bool:
    """
    Process a single roof face feature.

    Adds terrain_elevation property and updates coordinates to be
    height-above-terrain values.

    Returns True if feature was processed successfully.
    """
    geometry = feature.get("geometry")
    properties = feature.get("properties", {})

    if not geometry or geometry.get("type") != "Polygon":
        return False

    coords = geometry.get("coordinates", [[]])[0]
    if not coords:
        return False

    # Get centroid for terrain lookup
    centroid = get_polygon_centroid(coords)
    terrain_elevation = get_terrain_elevation(centroid[0], centroid[1])

    # Get LOD2 base elevation (ground level of building in LOD2 data)
    lod2_base = properties.get("base_elevation", terrain_elevation)

    # Calculate height offset: how much higher/lower LOD2 terrain is vs Mapterhorn
    # LOD2 uses its own terrain model, Mapterhorn might differ
    terrain_offset = lod2_base - terrain_elevation

    # Update coordinates: convert from absolute elevation to height-above-terrain
    # New Z = old_z - lod2_base + small offset for roof thickness
    # This positions the roof at: terrain_elevation + (old_z - lod2_base)
    new_coords = []
    for ring_idx, ring in enumerate(geometry["coordinates"]):
        new_ring = []
        for coord in ring:
            if len(coord) >= 3:
                # Original Z is absolute elevation from LOD2
                # Convert to height above Mapterhorn terrain
                lod2_z = coord[2]
                height_above_lod2_base = lod2_z - lod2_base
                # Final Z is height above terrain for deck.gl positioning
                new_z = height_above_lod2_base
                new_ring.append([coord[0], coord[1], round(new_z, 2)])
            else:
                new_ring.append(coord)
        new_coords.append(new_ring)

    geometry["coordinates"] = new_coords

    # Store terrain elevation for runtime use
    properties["terrain_elevation"] = round(terrain_elevation, 1)
    properties["lod2_terrain_offset"] = round(terrain_offset, 1)

    # Update height property to be relative to terrain
    if "height" in properties:
        # Height should be distance from terrain to top of roof
        old_height = properties.get("height", 0)
        # The max Z in new coordinates represents height above terrain
        max_z = max(c[2] for c in new_coords[0] if len(c) >= 3)
        properties["height"] = round(max_z, 1)

    feature["properties"] = properties

    return True


def add_roof_elevations(input_path: Path, output_path: Optional[Path] = None) -> dict:
    """
    Process roof GeoJSON to add terrain-relative elevations.

    Args:
        input_path: Path to input GeoJSON file
        output_path: Path to output file (defaults to same as input)

    Returns:
        Statistics dict
    """
    output_path = output_path or input_path

    print(f"Reading {input_path}...")
    with open(input_path, 'r') as f:
        data = json.load(f)

    features = data.get("features", [])
    if not features:
        print(f"No features found in {input_path}")
        return {"processed": 0, "skipped": 0}

    print(f"Processing {len(features)} roof faces...")
    processed = 0
    skipped = 0

    for feature in tqdm(features, desc="Adding terrain elevations"):
        if process_roof_feature(feature):
            processed += 1
        else:
            skipped += 1

    print(f"Writing to {output_path}...")
    with open(output_path, 'w') as f:
        json.dump(data, f)

    print(f"\n=== Processing Summary ===")
    print(f"Processed: {processed}")
    print(f"Skipped: {skipped}")
    print(f"Tiles cached: {len(tile_cache)}")

    # Collect statistics
    terrain_elevations = []
    heights = []
    offsets = []

    for f in features:
        props = f.get("properties", {})
        if "terrain_elevation" in props:
            terrain_elevations.append(props["terrain_elevation"])
        if "height" in props:
            heights.append(props["height"])
        if "lod2_terrain_offset" in props:
            offsets.append(props["lod2_terrain_offset"])

    if terrain_elevations:
        print(f"\nTerrain elevation range: {min(terrain_elevations):.1f}m - {max(terrain_elevations):.1f}m")
        print(f"Mean terrain elevation: {sum(terrain_elevations)/len(terrain_elevations):.1f}m")

    if heights:
        print(f"\nRoof height range: {min(heights):.1f}m - {max(heights):.1f}m")
        print(f"Mean roof height: {sum(heights)/len(heights):.1f}m")

    if offsets:
        print(f"\nLOD2-Mapterhorn offset range: {min(offsets):.1f}m - {max(offsets):.1f}m")
        print(f"Mean offset: {sum(offsets)/len(offsets):.1f}m")

    return {
        "processed": processed,
        "skipped": skipped,
        "tiles_cached": len(tile_cache),
    }


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Add terrain-relative elevations to roof faces"
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

    args = parser.parse_args()

    # Default to zurich-roofs.geojson
    data_dir = Path(__file__).parent.parent.parent / "public" / "data"
    default_file = data_dir / "zurich-roofs.geojson"

    input_path = args.file or default_file

    if not input_path.exists():
        print(f"Error: {input_path} not found")
        print("Run the roof extraction pipeline first:")
        print("  python scripts/process/extract_roof_faces.py")
        return

    add_roof_elevations(input_path, args.output)


if __name__ == "__main__":
    main()
