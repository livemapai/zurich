#!/usr/bin/env python3
"""
Download terrain elevation data from swisstopo swissALTI3D.

Data source: https://www.swisstopo.admin.ch/en/height-model-swissalti3d
Format: GeoTIFF
License: Open Government Data
"""

import os
import sys
import requests
from pathlib import Path
from tqdm import tqdm
from typing import Optional


# Zurich bounding box in LV95 (EPSG:2056)
# Approximate: covers greater Zurich area
ZURICH_BOUNDS_LV95 = {
    "min_e": 2676000,  # West
    "max_e": 2690000,  # East
    "min_n": 1241000,  # South
    "max_n": 1255000,  # North
}

# swissALTI3D tile grid (2km x 2km tiles)
TILE_SIZE = 2000  # meters

# Base URL for swissALTI3D tiles
# Note: Actual URL structure may vary - check swisstopo documentation
BASE_URL = "https://data.geo.admin.ch/ch.swisstopo.swissalti3d"

OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "terrain"


def get_tile_indices(bounds: dict) -> list[tuple[int, int]]:
    """Calculate tile indices covering the bounding box."""
    tiles = []

    min_tile_e = int(bounds["min_e"] // TILE_SIZE)
    max_tile_e = int(bounds["max_e"] // TILE_SIZE)
    min_tile_n = int(bounds["min_n"] // TILE_SIZE)
    max_tile_n = int(bounds["max_n"] // TILE_SIZE)

    for e in range(min_tile_e, max_tile_e + 1):
        for n in range(min_tile_n, max_tile_n + 1):
            tiles.append((e * TILE_SIZE, n * TILE_SIZE))

    return tiles


def download_tile(e: int, n: int, output_dir: Path) -> Optional[Path]:
    """
    Download a single terrain tile.

    Args:
        e: Easting coordinate (lower-left corner)
        n: Northing coordinate (lower-left corner)
        output_dir: Directory to save file

    Returns:
        Path to downloaded file, or None if failed
    """
    # Construct tile URL (format may vary)
    # Example: swissalti3d_2019_2684-1248_2_2056_5728.tif
    tile_name = f"swissalti3d_{e}-{n}"
    output_path = output_dir / f"{tile_name}.tif"

    if output_path.exists():
        return output_path

    # Note: Actual download URL needs to be constructed based on
    # swisstopo's current API. This is a placeholder.
    url = f"{BASE_URL}/{tile_name}.tif"

    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))

        with open(output_path, "wb") as f:
            with tqdm(total=total_size, unit="B", unit_scale=True, desc=tile_name) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    pbar.update(len(chunk))

        return output_path

    except requests.exceptions.HTTPError as e:
        print(f"Failed to download {tile_name}: {e}")
        return None


def download_terrain(
    bounds: Optional[dict] = None,
    output_dir: Optional[Path] = None
) -> list[Path]:
    """
    Download terrain tiles covering the specified area.

    Args:
        bounds: LV95 bounding box (default: Zurich area)
        output_dir: Directory to save files

    Returns:
        List of downloaded file paths
    """
    bounds = bounds or ZURICH_BOUNDS_LV95
    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    tiles = get_tile_indices(bounds)
    print(f"Need to download {len(tiles)} terrain tiles")

    downloaded = []

    for e, n in tiles:
        path = download_tile(e, n, output_dir)
        if path:
            downloaded.append(path)

    print(f"\nDownloaded {len(downloaded)}/{len(tiles)} tiles to {output_dir}")
    return downloaded


def create_sample_terrain(output_dir: Optional[Path] = None) -> Path:
    """
    Create a sample terrain file for testing when actual data isn't available.

    This creates a simple elevation grid that can be used for development.
    """
    import numpy as np
    from PIL import Image

    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "sample_terrain.png"

    # Create a 512x512 elevation grid
    # Zurich elevation ranges roughly from 400m to 800m
    size = 512
    x = np.linspace(0, 4 * np.pi, size)
    y = np.linspace(0, 4 * np.pi, size)
    X, Y = np.meshgrid(x, y)

    # Create rolling hills
    elevation = 450 + 50 * np.sin(X) * np.cos(Y) + 30 * np.sin(2 * X)

    # Normalize to 0-255 for RGB encoding
    # Using Mapbox terrain-rgb encoding:
    # elevation = -10000 + ((R * 256 * 256 + G * 256 + B) * 0.1)
    # So: RGB_value = (elevation + 10000) / 0.1

    rgb_value = (elevation + 10000) / 0.1
    r = (rgb_value // (256 * 256)).astype(np.uint8)
    g = ((rgb_value // 256) % 256).astype(np.uint8)
    b = (rgb_value % 256).astype(np.uint8)

    # Stack into RGB image
    rgb = np.stack([r, g, b], axis=-1)
    img = Image.fromarray(rgb, mode='RGB')
    img.save(output_path)

    print(f"Created sample terrain at {output_path}")
    return output_path


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Zurich terrain data")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output directory"
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Create sample terrain for testing"
    )

    args = parser.parse_args()

    if args.sample:
        create_sample_terrain(args.output)
    else:
        download_terrain(output_dir=args.output)


if __name__ == "__main__":
    main()
