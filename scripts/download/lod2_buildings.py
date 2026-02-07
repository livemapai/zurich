#!/usr/bin/env python3
"""
Download LOD2 3D building data from Stadt Zürich Open Data Portal.

Data source: https://www.ogd.stadt-zuerich.ch/geoportal_data_static/BEBAUUNG_3D_1500.zip
Format: OBJ (Wavefront) in ZIP
CRS: LV95 (EPSG:2056) - needs conversion to WGS84
License: CC0 (public domain)

The LOD2 dataset contains actual roof geometry (gabled, hipped, flat roofs)
instead of simple box extrusions. This enables realistic roof texturing.
"""

import io
import json
import zipfile
from pathlib import Path
from typing import Optional
import requests
from tqdm import tqdm

# LOD2 3D building data URL
LOD2_URL = "https://www.ogd.stadt-zuerich.ch/geoportal_data_static/BEBAUUNG_3D_1500.zip"

# Output directories
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "lod2-buildings"
METADATA_PATH = OUTPUT_DIR / "metadata.json"

# City center bounding box in LV95 coordinates
# Covers: Hauptbahnhof, Altstadt, Bellevue, ETH area
CITY_CENTER_BOUNDS_LV95 = {
    "min_e": 2682000,  # ~8.52° E
    "max_e": 2685000,  # ~8.56° E
    "min_n": 1246500,  # ~47.36° N
    "max_n": 1249500,  # ~47.39° N
}


def download_lod2_zip(cache_path: Optional[Path] = None) -> bytes:
    """
    Download the LOD2 ZIP file from Stadt Zürich.

    Args:
        cache_path: Optional path to cache the downloaded ZIP

    Returns:
        ZIP file content as bytes
    """
    # Check cache first
    if cache_path and cache_path.exists():
        print(f"Using cached ZIP: {cache_path}")
        return cache_path.read_bytes()

    print(f"Downloading LOD2 data from Stadt Zürich...")
    print(f"URL: {LOD2_URL}")
    print("This may take a few minutes (~500MB)...")

    response = requests.get(LOD2_URL, stream=True)
    response.raise_for_status()

    # Get total size for progress bar
    total_size = int(response.headers.get('content-length', 0))

    # Download with progress bar
    chunks = []
    with tqdm(total=total_size, unit='B', unit_scale=True, desc="Downloading") as pbar:
        for chunk in response.iter_content(chunk_size=8192):
            chunks.append(chunk)
            pbar.update(len(chunk))

    content = b''.join(chunks)

    # Cache if path provided
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(content)
        print(f"Cached ZIP to: {cache_path}")

    return content


def extract_vertex_bounds(obj_content: str) -> Optional[dict]:
    """
    Extract the bounding box of vertices from OBJ content.

    NOTE: Stadt Zürich LOD2 uses a rotated coordinate system:
    - X = LV95 Easting (correct)
    - Y = Elevation in meters
    - Z = -LV95 Northing (inverted!)

    This function converts to standard LV95 format.

    Args:
        obj_content: OBJ file content as string

    Returns:
        Dict with min_e, max_e, min_n, max_n, min_z, max_z or None if no vertices
    """
    min_e = min_n = min_z = float('inf')
    max_e = max_n = max_z = float('-inf')
    vertex_count = 0

    for line in obj_content.split('\n'):
        line = line.strip()
        if line.startswith('v '):
            parts = line.split()
            if len(parts) >= 4:
                try:
                    # OBJ format: v X Y Z
                    # Where: X=Easting, Y=Elevation, Z=-Northing
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])

                    # Convert to standard LV95: E=X, N=-Z, Elevation=Y
                    e = x
                    n = -z  # Invert Z to get Northing
                    elev = y

                    min_e = min(min_e, e)
                    max_e = max(max_e, e)
                    min_n = min(min_n, n)
                    max_n = max(max_n, n)
                    min_z = min(min_z, elev)
                    max_z = max(max_z, elev)
                    vertex_count += 1
                except ValueError:
                    continue

    if vertex_count == 0:
        return None

    return {
        "min_e": min_e, "max_e": max_e,
        "min_n": min_n, "max_n": max_n,
        "min_z": min_z, "max_z": max_z,
        "vertex_count": vertex_count,
    }


def is_in_bounds(bounds: dict, filter_bounds: dict) -> bool:
    """
    Check if a building's bounds overlap with filter bounds.

    Args:
        bounds: Building bounds dict
        filter_bounds: Filter region bounds dict

    Returns:
        True if building overlaps with filter region
    """
    # Check if building center is within bounds
    center_e = (bounds["min_e"] + bounds["max_e"]) / 2
    center_n = (bounds["min_n"] + bounds["max_n"]) / 2

    return (filter_bounds["min_e"] <= center_e <= filter_bounds["max_e"] and
            filter_bounds["min_n"] <= center_n <= filter_bounds["max_n"])


def extract_lod2_buildings(
    zip_content: bytes,
    output_dir: Path,
    filter_bounds: Optional[dict] = None,
    max_buildings: Optional[int] = None,
) -> dict:
    """
    Extract OBJ files from the LOD2 ZIP archive.

    Args:
        zip_content: ZIP file content as bytes
        output_dir: Directory to extract OBJ files
        filter_bounds: Optional LV95 bounding box to filter buildings
        max_buildings: Optional maximum number of buildings to extract

    Returns:
        Metadata dict with extraction statistics
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "source_url": LOD2_URL,
        "crs": "EPSG:2056",
        "filter_bounds": filter_bounds,
        "buildings": [],
        "total_in_zip": 0,
        "extracted": 0,
        "skipped_out_of_bounds": 0,
        "skipped_invalid": 0,
    }

    print(f"Extracting OBJ files to {output_dir}...")

    with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
        # Find all OBJ files that are actual buildings (not fences, walls, etc.)
        # Building types include: Gebaeude, Wohnhaus, Kirche, etc.
        all_obj_files = [f for f in zf.namelist() if f.lower().endswith('.obj')]
        metadata["total_in_zip"] = len(all_obj_files)
        print(f"Found {len(all_obj_files)} total OBJ files in archive")

        # Filter for building files only (exclude fences, walls, bridges, etc.)
        # Strategy: EXCLUDE known non-building types rather than requiring specific keywords
        # This catches all building types: Gebaeude, Sakralbau, Gastgewerbe, etc.
        exclude_keywords = [
            'zaun',        # Fences
            'mauer',       # Walls
            'fence',
            'wall',
            'befestigung', # Fortifications
            'bruecke',     # Bridges
            'steg',        # Footbridges/piers
            'bohlenweg',   # Wooden walkways
        ]

        obj_files = []
        for f in all_obj_files:
            name = f.lower()
            # Exclude if has fence/wall/bridge keyword
            has_exclude = any(kw in name for kw in exclude_keywords)

            if not has_exclude:
                obj_files.append(f)

        print(f"Filtered to {len(obj_files)} building files (excluding fences, walls, bridges)")

        for obj_path in tqdm(obj_files, desc="Extracting"):
            # Check max limit
            if max_buildings and metadata["extracted"] >= max_buildings:
                break

            try:
                # Read OBJ content
                obj_content = zf.read(obj_path).decode('utf-8', errors='replace')

                # Extract vertex bounds
                bounds = extract_vertex_bounds(obj_content)
                if not bounds:
                    metadata["skipped_invalid"] += 1
                    continue

                # Filter by bounds if specified
                if filter_bounds and not is_in_bounds(bounds, filter_bounds):
                    metadata["skipped_out_of_bounds"] += 1
                    continue

                # Extract building ID from filename
                filename = Path(obj_path).name
                building_id = Path(filename).stem

                # Write OBJ file
                output_path = output_dir / filename
                output_path.write_text(obj_content)

                # Record metadata
                metadata["buildings"].append({
                    "id": building_id,
                    "filename": filename,
                    "bounds": bounds,
                    "height": bounds["max_z"] - bounds["min_z"],
                })
                metadata["extracted"] += 1

            except Exception as e:
                print(f"Error extracting {obj_path}: {e}")
                metadata["skipped_invalid"] += 1
                continue

    return metadata


def download_lod2_buildings(
    output_dir: Optional[Path] = None,
    filter_bounds: Optional[dict] = None,
    city_center_only: bool = True,
    max_buildings: Optional[int] = None,
    cache_zip: bool = True,
) -> Path:
    """
    Download and extract LOD2 building data.

    Args:
        output_dir: Directory to save extracted files (default: data/raw/lod2-buildings)
        filter_bounds: Custom LV95 bounding box to filter buildings
        city_center_only: If True, use city center bounds (default: True)
        max_buildings: Maximum number of buildings to extract
        cache_zip: Whether to cache the downloaded ZIP file

    Returns:
        Path to output directory with extracted OBJ files
    """
    output_dir = output_dir or OUTPUT_DIR

    # Determine filter bounds
    if filter_bounds:
        bounds = filter_bounds
    elif city_center_only:
        bounds = CITY_CENTER_BOUNDS_LV95
        print(f"Filtering to city center bounds:")
        print(f"  E: {bounds['min_e']} to {bounds['max_e']}")
        print(f"  N: {bounds['min_n']} to {bounds['max_n']}")
    else:
        bounds = None
        print("No bounds filter - extracting all buildings")

    # Download ZIP
    cache_path = output_dir.parent / "lod2-buildings.zip" if cache_zip else None
    zip_content = download_lod2_zip(cache_path)

    # Extract OBJ files
    metadata = extract_lod2_buildings(
        zip_content,
        output_dir,
        filter_bounds=bounds,
        max_buildings=max_buildings,
    )

    # Save metadata
    metadata_path = output_dir / "metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"\n=== Extraction Summary ===")
    print(f"Total in archive: {metadata['total_in_zip']}")
    print(f"Extracted: {metadata['extracted']}")
    print(f"Skipped (out of bounds): {metadata['skipped_out_of_bounds']}")
    print(f"Skipped (invalid): {metadata['skipped_invalid']}")
    print(f"\nOutput directory: {output_dir}")
    print(f"Metadata: {metadata_path}")

    return output_dir


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download LOD2 3D building data from Stadt Zürich"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output directory for extracted OBJ files"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Extract all buildings (not just city center)"
    )
    parser.add_argument(
        "--max-buildings", "-n",
        type=int,
        help="Maximum number of buildings to extract"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Don't cache the downloaded ZIP file"
    )
    parser.add_argument(
        "--bounds",
        nargs=4,
        type=float,
        metavar=("MIN_E", "MAX_E", "MIN_N", "MAX_N"),
        help="Custom LV95 bounding box (easting/northing)"
    )

    args = parser.parse_args()

    # Parse custom bounds if provided
    filter_bounds = None
    if args.bounds:
        filter_bounds = {
            "min_e": args.bounds[0],
            "max_e": args.bounds[1],
            "min_n": args.bounds[2],
            "max_n": args.bounds[3],
        }

    download_lod2_buildings(
        output_dir=args.output,
        filter_bounds=filter_bounds,
        city_center_only=not args.all and not filter_bounds,
        max_buildings=args.max_buildings,
        cache_zip=not args.no_cache,
    )


if __name__ == "__main__":
    main()
