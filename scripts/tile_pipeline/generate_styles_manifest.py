#!/usr/bin/env python3
"""
Generate AI Styles Manifest

Scans public/tiles/ai-* directories to create a manifest file
containing metadata about available AI-generated tile styles.

Usage:
    python -m scripts.tile_pipeline.generate_styles_manifest
    python -m scripts.tile_pipeline.generate_styles_manifest -o public/tiles/ai-styles.json
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import TypedDict, Optional
import argparse


class StyleMetadata(TypedDict):
    name: str
    displayName: str
    description: str
    colors: list[str]
    tiles: int
    totalTiles: int
    bounds: list[float]  # [west, south, east, north]
    zoom: int
    generatedAt: Optional[str]
    generator: str  # "gemini" for ai-*, "controlnet" for sd-*


# Style definitions - must match TypeScript definitions
STYLE_DEFINITIONS = {
    "winter": {
        "displayName": "Winter",
        "description": "Snow-covered cityscape with frosted trees",
        "colors": ["#FFFFFF", "#E8F0F8", "#C4D6E8"],
    },
    "cyberpunk": {
        "displayName": "Cyberpunk",
        "description": "Neon-lit night city with futuristic vibes",
        "colors": ["#FF00FF", "#00FFFF", "#1a0a2e"],
    },
    "watercolor": {
        "displayName": "Watercolor",
        "description": "Artistic hand-painted style",
        "colors": ["#E8DCC8", "#7BA3A8", "#D4A574"],
    },
    "autumn": {
        "displayName": "Autumn",
        "description": "Fall foliage with warm orange tones",
        "colors": ["#D4652F", "#E8A530", "#8B4513"],
    },
    "blueprint": {
        "displayName": "Blueprint",
        "description": "Technical architectural drawing style",
        "colors": ["#002266", "#FFFFFF", "#4488CC"],
    },
    "retro": {
        "displayName": "Retro",
        "description": "80s vaporwave aesthetic",
        "colors": ["#FF6EC7", "#00FFFF", "#9D00FF"],
    },
    "noir": {
        "displayName": "Film Noir",
        "description": "Black and white cinematic style",
        "colors": ["#000000", "#FFFFFF", "#808080"],
    },
    "tropical": {
        "displayName": "Tropical",
        "description": "Lush vegetation with vibrant greens",
        "colors": ["#228B22", "#00CED1", "#FFD700"],
    },
    "night": {
        "displayName": "Night",
        "description": "Nighttime cityscape with street lights",
        "colors": ["#1a1a2e", "#FFD700", "#4169E1"],
    },
    "golden-hour": {
        "displayName": "Golden Hour",
        "description": "Warm sunset lighting with long shadows",
        "colors": ["#FF8C00", "#FFD700", "#FF6347"],
    },
}

# Default coverage bounds for Zurich city center (zoom 16)
# This is the 6x6 tile grid we typically generate
DEFAULT_BOUNDS = [8.530, 47.365, 8.555, 47.385]  # [west, south, east, north]
DEFAULT_TOTAL_TILES = 36  # 6x6 grid


def tile_to_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """Convert tile coordinates to WGS84 bounds."""
    import math

    n = 2**z
    west = x / n * 360 - 180
    east = (x + 1) / n * 360 - 180

    lat_rad_north = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_rad_south = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))

    north = math.degrees(lat_rad_north)
    south = math.degrees(lat_rad_south)

    return (west, south, east, north)


def scan_style_directory(
    tiles_dir: Path,
    style_name: str,
    prefix: str = "ai",
) -> Optional[StyleMetadata]:
    """Scan a style directory and return metadata.

    Args:
        tiles_dir: Base tiles directory
        style_name: Style name (e.g., "winter", "cyberpunk")
        prefix: Directory prefix - "ai" for Gemini, "sd" for Stable Diffusion

    Returns:
        StyleMetadata dict or None if directory doesn't exist
    """
    style_dir = tiles_dir / f"{prefix}-{style_name}"

    if not style_dir.exists():
        return None

    # Find zoom level directories
    zoom_dirs = [d for d in style_dir.iterdir() if d.is_dir() and d.name.isdigit()]

    if not zoom_dirs:
        return None

    # Use the first (typically only) zoom level
    zoom_dir = sorted(zoom_dirs, key=lambda d: int(d.name))[0]
    zoom = int(zoom_dir.name)

    # Count tiles and find bounds
    tile_count = 0
    min_x, max_x = float("inf"), float("-inf")
    min_y, max_y = float("inf"), float("-inf")
    latest_mtime = 0

    for x_dir in zoom_dir.iterdir():
        if not x_dir.is_dir() or not x_dir.name.isdigit():
            continue

        x = int(x_dir.name)
        min_x = min(min_x, x)
        max_x = max(max_x, x)

        for tile_file in x_dir.iterdir():
            if tile_file.suffix in (".webp", ".png", ".jpg"):
                tile_count += 1
                y_str = tile_file.stem
                if y_str.isdigit():
                    y = int(y_str)
                    min_y = min(min_y, y)
                    max_y = max(max_y, y)

                # Track latest modification time
                mtime = tile_file.stat().st_mtime
                if mtime > latest_mtime:
                    latest_mtime = mtime

    if tile_count == 0:
        return None

    # Calculate bounds from tile coordinates
    west, south, _, _ = tile_to_bounds(zoom, int(min_x), int(max_y) + 1)
    _, _, east, north = tile_to_bounds(zoom, int(max_x) + 1, int(min_y))

    # Get style definition or use defaults
    style_def = STYLE_DEFINITIONS.get(
        style_name,
        {
            "displayName": style_name.title(),
            "description": f"{style_name.title()} style tiles",
            "colors": ["#888888", "#CCCCCC"],
        },
    )

    # Format generation timestamp
    generated_at = datetime.fromtimestamp(latest_mtime).isoformat() if latest_mtime else None

    # Determine generator type and adjust display name
    generator = "controlnet" if prefix == "sd" else "gemini"
    generator_suffix = " (ControlNet)" if prefix == "sd" else ""
    display_name = style_def["displayName"] + generator_suffix

    # Use prefixed name for unique identification
    full_name = f"{prefix}-{style_name}"

    return StyleMetadata(
        name=full_name,  # e.g., "ai-winter" or "sd-winter"
        displayName=display_name,  # e.g., "Winter" or "Winter (ControlNet)"
        description=style_def["description"],
        colors=style_def["colors"],
        tiles=tile_count,
        totalTiles=DEFAULT_TOTAL_TILES,
        bounds=[round(west, 6), round(south, 6), round(east, 6), round(north, 6)],
        zoom=zoom,
        generatedAt=generated_at,
        generator=generator,  # "gemini" or "controlnet"
    )


def generate_manifest(tiles_dir: Path) -> dict:
    """Generate the complete styles manifest.

    Scans both ai-* (Gemini) and sd-* (Stable Diffusion ControlNet) directories.
    """
    styles = []

    # Scan for all ai-* directories (Gemini-generated)
    for item in sorted(tiles_dir.iterdir()):
        if item.is_dir() and item.name.startswith("ai-"):
            style_name = item.name[3:]  # Remove "ai-" prefix
            metadata = scan_style_directory(tiles_dir, style_name, prefix="ai")
            if metadata:
                styles.append(metadata)
                print(f"  Found: ai-{style_name} ({metadata['tiles']} tiles, Gemini)")

    # Scan for all sd-* directories (Stable Diffusion ControlNet)
    for item in sorted(tiles_dir.iterdir()):
        if item.is_dir() and item.name.startswith("sd-"):
            style_name = item.name[3:]  # Remove "sd-" prefix
            metadata = scan_style_directory(tiles_dir, style_name, prefix="sd")
            if metadata:
                styles.append(metadata)
                print(f"  Found: sd-{style_name} ({metadata['tiles']} tiles, ControlNet)")

    # Sort by displayName (groups AI and SD versions of same style together)
    styles.sort(key=lambda s: (s["displayName"].replace(" (ControlNet)", ""), s["generator"]))

    return {
        "styles": styles,
        "satellite": {
            "name": "satellite",
            "displayName": "Satellite",
            "description": "Real satellite imagery from Swisstopo",
            "colors": ["#3D6B3D", "#5A4A3A", "#6B8E6B"],
            "url": "https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissimage/default/current/3857/{z}/{x}/{y}.jpeg",
            "tileSize": 256,
        },
        "generatedAt": datetime.now().isoformat(),
        "defaultBounds": DEFAULT_BOUNDS,
        "defaultZoom": 16,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate AI styles manifest")
    parser.add_argument(
        "-o",
        "--output",
        default="public/tiles/ai-styles.json",
        help="Output file path (default: public/tiles/ai-styles.json)",
    )
    parser.add_argument(
        "--tiles-dir",
        default="public/tiles",
        help="Tiles directory (default: public/tiles)",
    )
    args = parser.parse_args()

    # Resolve paths relative to project root
    project_root = Path(__file__).parent.parent.parent
    tiles_dir = project_root / args.tiles_dir
    output_file = project_root / args.output

    print(f"Scanning tiles directory: {tiles_dir}")

    if not tiles_dir.exists():
        print(f"Error: Tiles directory not found: {tiles_dir}")
        return 1

    manifest = generate_manifest(tiles_dir)

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Write manifest
    with open(output_file, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest written to: {output_file}")
    print(f"Found {len(manifest['styles'])} AI styles")

    return 0


if __name__ == "__main__":
    exit(main())
