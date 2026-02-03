# Phase 2: Data Pipeline

## Context
This phase creates Python scripts to download and process Zurich open data. The pipeline converts building OBJ files and terrain data into GeoJSON format suitable for deck.gl.

## Prerequisites
- Phase 0 completed
- Python 3.10+ installed
- pip available

## Data Sources

| Data | Source | Format | License |
|------|--------|--------|---------|
| 3D Buildings | data.stadt-zuerich.ch | OBJ (Wavefront) | CC0 |
| Terrain | swisstopo swissALTI3D | GeoTIFF | Open |

**URLs:**
- Buildings: `https://data.stadt-zuerich.ch/dataset/geo_3d_blockmodell_lod1`
- Terrain: `https://www.swisstopo.admin.ch/en/height-model-swissalti3d`

## Tasks

### Task 2.1: Create Python Requirements
**Goal:** Define Python dependencies for data processing.

**Create file:** `scripts/requirements.txt`
```
# Data processing
numpy>=1.26.0
requests>=2.31.0

# Coordinate transformation
pyproj>=3.6.0

# 3D mesh processing
trimesh>=4.0.0
scipy>=1.11.0

# Raster/terrain processing
rasterio>=1.3.0
pillow>=10.0.0

# GeoJSON handling
shapely>=2.0.0
geojson>=3.0.0

# Progress bars
tqdm>=4.66.0

# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
```

**Verification:**
- [ ] File exists at `scripts/requirements.txt`

---

### Task 2.1b: Create Package Structure
**Goal:** Create Python package __init__.py files for proper imports.

**Create files:**
```bash
touch scripts/__init__.py
touch scripts/download/__init__.py
touch scripts/convert/__init__.py
touch scripts/validate/__init__.py
touch scripts/tests/__init__.py
```

Each file should be empty (or contain a simple docstring):

**File:** `scripts/__init__.py`
```python
"""Zurich 3D data processing scripts."""
```

**File:** `scripts/download/__init__.py`
```python
"""Data download scripts."""
```

**File:** `scripts/convert/__init__.py`
```python
"""Data conversion scripts."""
```

**File:** `scripts/validate/__init__.py`
```python
"""Data validation scripts."""
```

**File:** `scripts/tests/__init__.py`
```python
"""Test suite for data pipeline."""
```

**Verification:**
- [ ] All `__init__.py` files exist

---

### Task 2.2: Create Download Script for Buildings
**Goal:** Download building OBJ files from Stadt Zürich open data portal.

**Create file:** `scripts/download/buildings.py`
```python
#!/usr/bin/env python3
"""
Download 3D building data from Stadt Zürich Open Data Portal.

Data source: https://data.stadt-zuerich.ch/dataset/geo_3d_blockmodell_lod1
Format: OBJ (Wavefront)
License: CC0
"""

import os
import sys
import requests
from pathlib import Path
from tqdm import tqdm
from typing import Optional


# Constants
DATA_URL = "https://data.stadt-zuerich.ch/dataset/geo_3d_blockmodell_lod1"
API_URL = "https://data.stadt-zuerich.ch/api/3/action/package_show"
DATASET_ID = "geo_3d_blockmodell_lod1"

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "buildings"


def get_dataset_resources() -> list[dict]:
    """Fetch available resources from the dataset API."""
    params = {"id": DATASET_ID}
    response = requests.get(API_URL, params=params)
    response.raise_for_status()

    result = response.json()
    if not result.get("success"):
        raise Exception(f"API error: {result}")

    return result["result"]["resources"]


def download_file(url: str, output_path: Path, chunk_size: int = 8192) -> None:
    """Download a file with progress bar."""
    response = requests.get(url, stream=True)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))

    with open(output_path, "wb") as f:
        with tqdm(total=total_size, unit="B", unit_scale=True) as pbar:
            for chunk in response.iter_content(chunk_size=chunk_size):
                f.write(chunk)
                pbar.update(len(chunk))


def download_buildings(
    output_dir: Optional[Path] = None,
    max_files: Optional[int] = None
) -> list[Path]:
    """
    Download building OBJ files.

    Args:
        output_dir: Directory to save files (default: data/raw/buildings)
        max_files: Maximum number of files to download (for testing)

    Returns:
        List of downloaded file paths
    """
    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching resource list from {DATASET_ID}...")
    resources = get_dataset_resources()

    # Filter for OBJ files
    obj_resources = [r for r in resources if r["format"].upper() == "OBJ"]
    print(f"Found {len(obj_resources)} OBJ files")

    if max_files:
        obj_resources = obj_resources[:max_files]
        print(f"Limiting to {max_files} files")

    downloaded = []

    for resource in obj_resources:
        name = resource["name"]
        url = resource["url"]
        output_path = output_dir / f"{name}.obj"

        if output_path.exists():
            print(f"Skipping {name} (already exists)")
            downloaded.append(output_path)
            continue

        print(f"Downloading {name}...")
        try:
            download_file(url, output_path)
            downloaded.append(output_path)
        except Exception as e:
            print(f"Error downloading {name}: {e}")

    print(f"\nDownloaded {len(downloaded)} files to {output_dir}")
    return downloaded


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Zurich building data")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output directory"
    )
    parser.add_argument(
        "--max-files", "-n",
        type=int,
        help="Maximum files to download (for testing)"
    )

    args = parser.parse_args()

    download_buildings(
        output_dir=args.output,
        max_files=args.max_files
    )


if __name__ == "__main__":
    main()
```

**Verification:**
- [ ] File exists at `scripts/download/buildings.py`
- [ ] File is executable: `chmod +x scripts/download/buildings.py`

---

### Task 2.3: Create Download Script for Terrain
**Goal:** Download terrain elevation data from swisstopo.

**Create file:** `scripts/download/terrain.py`
```python
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
```

**Verification:**
- [ ] File exists at `scripts/download/terrain.py`

---

### Task 2.4: Create OBJ to GeoJSON Converter
**Goal:** Convert OBJ mesh files to GeoJSON polygons with height.

**Create file:** `scripts/convert/obj-to-geojson.py`
```python
#!/usr/bin/env python3
"""
Convert OBJ building meshes to GeoJSON polygons.

This script extracts the footprint and height from 3D building meshes
and outputs GeoJSON suitable for deck.gl's SolidPolygonLayer.
"""

import json
from pathlib import Path
from typing import Optional
import numpy as np
from tqdm import tqdm


def parse_obj_file(filepath: Path) -> dict:
    """
    Parse an OBJ file and extract vertices and faces.

    Returns:
        dict with 'vertices' (Nx3 array) and 'faces' (list of vertex indices)
    """
    vertices = []
    faces = []

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split()
            if not parts:
                continue

            if parts[0] == 'v':
                # Vertex: v x y z
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                vertices.append([x, y, z])

            elif parts[0] == 'f':
                # Face: f v1 v2 v3 ... (1-indexed)
                face_verts = []
                for p in parts[1:]:
                    # Handle v/vt/vn format
                    v_idx = int(p.split('/')[0]) - 1  # Convert to 0-indexed
                    face_verts.append(v_idx)
                faces.append(face_verts)

    return {
        'vertices': np.array(vertices),
        'faces': faces
    }


def extract_footprint(vertices: np.ndarray, faces: list) -> tuple[np.ndarray, float, float]:
    """
    Extract the building footprint (XY polygon) and height information.

    Args:
        vertices: Nx3 array of vertex coordinates
        faces: List of face vertex indices

    Returns:
        (footprint_coords, base_elevation, height)
    """
    if len(vertices) == 0:
        return np.array([]), 0, 0

    # Find the base (minimum Z) and top (maximum Z)
    z_coords = vertices[:, 2]
    base_elevation = float(np.min(z_coords))
    top_elevation = float(np.max(z_coords))
    height = top_elevation - base_elevation

    # Extract vertices at (or near) the base level
    tolerance = 0.5  # meters
    base_mask = np.abs(z_coords - base_elevation) < tolerance
    base_vertices = vertices[base_mask]

    if len(base_vertices) < 3:
        # Fallback: project all vertices to XY
        base_vertices = vertices

    # Get XY coordinates
    xy_coords = base_vertices[:, :2]

    # Find convex hull for footprint
    try:
        from scipy.spatial import ConvexHull
        hull = ConvexHull(xy_coords)
        footprint = xy_coords[hull.vertices]
    except Exception:
        # Fallback: use all unique XY points
        footprint = np.unique(xy_coords, axis=0)

    return footprint, base_elevation, height


def convert_obj_to_feature(
    filepath: Path,
    feature_id: str
) -> Optional[dict]:
    """
    Convert a single OBJ file to a GeoJSON feature.

    Args:
        filepath: Path to OBJ file
        feature_id: ID for the feature

    Returns:
        GeoJSON Feature dict, or None if conversion failed
    """
    try:
        obj_data = parse_obj_file(filepath)
        footprint, base_elevation, height = extract_footprint(
            obj_data['vertices'],
            obj_data['faces']
        )

        if len(footprint) < 3:
            return None

        # Close the polygon (first point = last point)
        if not np.array_equal(footprint[0], footprint[-1]):
            footprint = np.vstack([footprint, footprint[0]])

        # Convert to list for JSON
        coordinates = footprint.tolist()

        return {
            "type": "Feature",
            "properties": {
                "id": feature_id,
                "height": round(height, 2),
                "baseElevation": round(base_elevation, 2),
                "source": filepath.name
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [coordinates]  # GeoJSON: [[ring]]
            }
        }

    except Exception as e:
        print(f"Error converting {filepath}: {e}")
        return None


def convert_directory(
    input_dir: Path,
    output_path: Path,
    max_files: Optional[int] = None
) -> int:
    """
    Convert all OBJ files in a directory to a single GeoJSON file.

    NOTE: Coordinates are in LV95 (EPSG:2056).
    Run transform-coords.py to convert to WGS84.

    Args:
        input_dir: Directory containing OBJ files
        output_path: Output GeoJSON file path
        max_files: Maximum number of files to process

    Returns:
        Number of features converted
    """
    obj_files = list(input_dir.glob("*.obj"))
    print(f"Found {len(obj_files)} OBJ files in {input_dir}")

    if max_files:
        obj_files = obj_files[:max_files]
        print(f"Processing first {max_files} files")

    features = []

    for i, filepath in enumerate(tqdm(obj_files, desc="Converting")):
        feature_id = f"building_{i:06d}"
        feature = convert_obj_to_feature(filepath, feature_id)
        if feature:
            features.append(feature)

    # Create FeatureCollection
    geojson = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {
                "name": "EPSG:2056"  # Swiss LV95
            }
        },
        "features": features
    }

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(geojson, f, indent=2)

    print(f"Wrote {len(features)} features to {output_path}")
    return len(features)


def create_sample_buildings(output_path: Path, count: int = 100) -> int:
    """
    Create sample building GeoJSON for testing.

    Creates random rectangular buildings in the Zurich area.
    """
    import random

    # Zurich center in LV95
    center_e = 2683000
    center_n = 1248000
    spread = 2000  # meters

    features = []

    for i in range(count):
        # Random position
        e = center_e + random.uniform(-spread, spread)
        n = center_n + random.uniform(-spread, spread)

        # Random building size
        width = random.uniform(10, 50)
        depth = random.uniform(10, 50)
        height = random.uniform(5, 80)

        # Create rectangular footprint
        coords = [
            [e, n],
            [e + width, n],
            [e + width, n + depth],
            [e, n + depth],
            [e, n]  # Close polygon
        ]

        features.append({
            "type": "Feature",
            "properties": {
                "id": f"sample_{i:04d}",
                "height": round(height, 2),
                "baseElevation": 400 + random.uniform(0, 50)
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords]
            }
        })

    geojson = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": "EPSG:2056"}
        },
        "features": features
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(geojson, f, indent=2)

    print(f"Created {count} sample buildings at {output_path}")
    return count


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Convert OBJ files to GeoJSON")
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        help="Input directory with OBJ files"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("data/processed/buildings-lv95.geojson"),
        help="Output GeoJSON file"
    )
    parser.add_argument(
        "--max-files", "-n",
        type=int,
        help="Maximum files to process"
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Create sample buildings for testing"
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=100,
        help="Number of sample buildings"
    )

    args = parser.parse_args()

    if args.sample:
        create_sample_buildings(args.output, args.sample_count)
    elif args.input:
        convert_directory(args.input, args.output, args.max_files)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

**Verification:**
- [ ] File exists at `scripts/convert/obj-to-geojson.py`

---

### Task 2.5: Create Coordinate Transformation Script
**Goal:** Convert LV95 (EPSG:2056) coordinates to WGS84 (EPSG:4326).

**Create file:** `scripts/convert/transform-coords.py`
```python
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
```

**Verification:**
- [ ] File exists at `scripts/convert/transform-coords.py`

---

### Task 2.6: Create Building Tiling Script
**Goal:** Split large building dataset into spatial tiles for efficient loading.

**Create file:** `scripts/convert/tile-buildings.py`
```python
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
```

**Verification:**
- [ ] File exists at `scripts/convert/tile-buildings.py`

---

### Task 2.7: Create Data Validation Script
**Goal:** Validate processed GeoJSON files for correctness.

**Create file:** `scripts/validate/check-data.py`
```python
#!/usr/bin/env python3
"""
Validate GeoJSON data for deck.gl compatibility.

Checks:
- Valid GeoJSON structure
- Coordinates in expected range (WGS84 for Zurich)
- Required properties present
- Building heights are reasonable
"""

import json
from pathlib import Path
from typing import Optional
import sys


# Expected bounds for Zurich in WGS84 (from DATA_SOURCES.md)
ZURICH_BOUNDS = {
    "min_lng": 8.448,
    "max_lng": 8.626,
    "min_lat": 47.320,
    "max_lat": 47.435
}


class ValidationError:
    def __init__(self, feature_id: str, issue: str, details: str = ""):
        self.feature_id = feature_id
        self.issue = issue
        self.details = details

    def __str__(self):
        return f"[{self.feature_id}] {self.issue}: {self.details}"


def validate_coordinate(lng: float, lat: float, bounds: dict = ZURICH_BOUNDS) -> Optional[str]:
    """Check if coordinate is within expected bounds."""
    if lng < bounds["min_lng"] or lng > bounds["max_lng"]:
        return f"Longitude {lng} outside bounds [{bounds['min_lng']}, {bounds['max_lng']}]"
    if lat < bounds["min_lat"] or lat > bounds["max_lat"]:
        return f"Latitude {lat} outside bounds [{bounds['min_lat']}, {bounds['max_lat']}]"
    return None


def validate_feature(feature: dict, index: int) -> list[ValidationError]:
    """Validate a single GeoJSON feature."""
    errors = []
    feature_id = feature.get("properties", {}).get("id", f"feature_{index}")

    # Check geometry exists
    if "geometry" not in feature:
        errors.append(ValidationError(feature_id, "Missing geometry"))
        return errors

    geom = feature["geometry"]

    # Check geometry type
    if geom["type"] not in ["Polygon", "MultiPolygon"]:
        errors.append(ValidationError(
            feature_id,
            "Unexpected geometry type",
            f"Got {geom['type']}, expected Polygon or MultiPolygon"
        ))
        return errors

    # Check coordinates
    if "coordinates" not in geom:
        errors.append(ValidationError(feature_id, "Missing coordinates"))
        return errors

    coords = geom["coordinates"]

    # Get sample coordinates to check
    sample_coords = []
    if geom["type"] == "Polygon":
        if coords and coords[0]:
            sample_coords = coords[0][:5]  # First 5 coords of outer ring
    elif geom["type"] == "MultiPolygon":
        if coords and coords[0] and coords[0][0]:
            sample_coords = coords[0][0][:5]

    # Validate sample coordinates
    for coord in sample_coords:
        if len(coord) < 2:
            errors.append(ValidationError(feature_id, "Invalid coordinate", str(coord)))
            continue

        lng, lat = coord[0], coord[1]

        # Check if coordinates are swapped (lat, lng instead of lng, lat)
        if lng > 40 and lat < 10:
            errors.append(ValidationError(
                feature_id,
                "Coordinates appear swapped",
                f"[{lng}, {lat}] looks like [lat, lng]"
            ))
            break

        # Check bounds
        bounds_error = validate_coordinate(lng, lat)
        if bounds_error:
            errors.append(ValidationError(feature_id, "Coordinate out of bounds", bounds_error))
            break

    # Check properties
    props = feature.get("properties", {})

    # Height validation (if present)
    if "height" in props:
        height = props["height"]
        if not isinstance(height, (int, float)):
            errors.append(ValidationError(feature_id, "Invalid height type", str(type(height))))
        elif height < 0:
            errors.append(ValidationError(feature_id, "Negative height", str(height)))
        elif height > 500:
            errors.append(ValidationError(feature_id, "Unrealistic height", f"{height}m"))

    return errors


def validate_geojson(filepath: Path, sample_size: int = 1000) -> tuple[bool, list[ValidationError]]:
    """
    Validate a GeoJSON file.

    Args:
        filepath: Path to GeoJSON file
        sample_size: Number of features to validate (0 = all)

    Returns:
        (is_valid, list of errors)
    """
    errors = []

    # Check file exists
    if not filepath.exists():
        return False, [ValidationError("file", "File not found", str(filepath))]

    # Try to parse
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [ValidationError("file", "Invalid JSON", str(e))]

    # Check structure
    if data.get("type") != "FeatureCollection":
        return False, [ValidationError("file", "Not a FeatureCollection")]

    if "features" not in data or not isinstance(data["features"], list):
        return False, [ValidationError("file", "Missing or invalid features array")]

    features = data["features"]
    total = len(features)

    # Sample features if too many
    if sample_size > 0 and total > sample_size:
        import random
        indices = random.sample(range(total), sample_size)
        sample = [(i, features[i]) for i in indices]
        print(f"Validating {sample_size} of {total} features...")
    else:
        sample = list(enumerate(features))
        print(f"Validating all {total} features...")

    # Validate features
    for index, feature in sample:
        feature_errors = validate_feature(feature, index)
        errors.extend(feature_errors)

        # Stop if too many errors
        if len(errors) > 100:
            errors.append(ValidationError(
                "validation",
                "Too many errors",
                "Stopping after 100 errors"
            ))
            break

    is_valid = len(errors) == 0
    return is_valid, errors


def print_summary(filepath: Path, is_valid: bool, errors: list[ValidationError]) -> None:
    """Print validation summary."""
    print(f"\n{'='*60}")
    print(f"File: {filepath}")
    print(f"Status: {'✓ VALID' if is_valid else '✗ INVALID'}")

    if errors:
        print(f"\nFound {len(errors)} issues:")
        for error in errors[:20]:  # Show first 20
            print(f"  • {error}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")

    print(f"{'='*60}\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate GeoJSON data")
    parser.add_argument(
        "file",
        type=Path,
        help="GeoJSON file to validate"
    )
    parser.add_argument(
        "--sample", "-n",
        type=int,
        default=1000,
        help="Number of features to sample (0 = all)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error code if validation fails"
    )

    args = parser.parse_args()

    is_valid, errors = validate_geojson(args.file, args.sample)
    print_summary(args.file, is_valid, errors)

    if args.strict and not is_valid:
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Verification:**
- [ ] File exists at `scripts/validate/check-data.py`

---

### Task 2.8: Create Pipeline Runner Script
**Goal:** Orchestrate the complete data pipeline.

**Create file:** `scripts/run-pipeline.py`
```python
#!/usr/bin/env python3
"""
Run the complete data pipeline for Zurich 3D buildings.

Steps:
1. Download building data (or create samples)
2. Convert OBJ to GeoJSON
3. Transform coordinates LV95 → WGS84
4. Create tiles or merged file
5. Validate output
"""

import subprocess
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"Step: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)

    result = subprocess.run(cmd)
    success = result.returncode == 0

    if not success:
        print(f"❌ Failed: {description}")
    else:
        print(f"✓ Completed: {description}")

    return success


def run_pipeline(use_samples: bool = True, create_tiles: bool = False):
    """
    Run the data pipeline.

    Args:
        use_samples: Use sample data instead of downloading real data
        create_tiles: Create tiled output instead of single file
    """
    python = sys.executable

    steps = []

    if use_samples:
        # Create sample buildings
        steps.append((
            [python, str(SCRIPTS_DIR / "convert/obj-to-geojson.py"),
             "--sample", "--sample-count", "500",
             "-o", str(PROJECT_ROOT / "data/processed/buildings-lv95.geojson")],
            "Create sample buildings (LV95)"
        ))
    else:
        # Download real data
        steps.append((
            [python, str(SCRIPTS_DIR / "download/buildings.py"),
             "-o", str(PROJECT_ROOT / "data/raw/buildings"),
             "-n", "10"],  # Limit for testing
            "Download building data"
        ))

        # Convert OBJ to GeoJSON
        steps.append((
            [python, str(SCRIPTS_DIR / "convert/obj-to-geojson.py"),
             str(PROJECT_ROOT / "data/raw/buildings"),
             "-o", str(PROJECT_ROOT / "data/processed/buildings-lv95.geojson")],
            "Convert OBJ to GeoJSON"
        ))

    # Transform coordinates
    steps.append((
        [python, str(SCRIPTS_DIR / "convert/transform-coords.py"),
         str(PROJECT_ROOT / "data/processed/buildings-lv95.geojson"),
         "-o", str(PROJECT_ROOT / "data/processed/buildings-wgs84.geojson")],
        "Transform coordinates to WGS84"
    ))

    # Create tiles or single file
    if create_tiles:
        steps.append((
            [python, str(SCRIPTS_DIR / "convert/tile-buildings.py"),
             str(PROJECT_ROOT / "data/processed/buildings-wgs84.geojson"),
             "-o", str(PROJECT_ROOT / "public/data/tiles/buildings")],
            "Create spatial tiles"
        ))
    else:
        steps.append((
            [python, str(SCRIPTS_DIR / "convert/tile-buildings.py"),
             str(PROJECT_ROOT / "data/processed/buildings-wgs84.geojson"),
             "--single",
             "-o", str(PROJECT_ROOT / "public/data/zurich-buildings.geojson")],
            "Create merged GeoJSON"
        ))

    # Validate output
    output_file = (
        PROJECT_ROOT / "public/data/tiles/buildings/tile-index.json"
        if create_tiles
        else PROJECT_ROOT / "public/data/zurich-buildings.geojson"
    )
    steps.append((
        [python, str(SCRIPTS_DIR / "validate/check-data.py"),
         str(output_file if output_file.exists() else PROJECT_ROOT / "public/data/zurich-buildings.geojson"),
         "--sample", "100"],
        "Validate output"
    ))

    # Run all steps
    for cmd, description in steps:
        if not run_command(cmd, description):
            print(f"\n❌ Pipeline failed at: {description}")
            return False

    print("\n" + "="*60)
    print("✓ Pipeline completed successfully!")
    print("="*60)
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run data pipeline")
    parser.add_argument(
        "--real-data",
        action="store_true",
        help="Download real data instead of using samples"
    )
    parser.add_argument(
        "--tiles",
        action="store_true",
        help="Create tiled output instead of single file"
    )

    args = parser.parse_args()

    success = run_pipeline(
        use_samples=not args.real_data,
        create_tiles=args.tiles
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

**Verification:**
- [ ] File exists at `scripts/run-pipeline.py`

---

### Task 2.9: Create Test Suite
**Goal:** Create unit tests for the data pipeline to ensure correctness.

**Create file:** `scripts/tests/test_transform_coords.py`
```python
#!/usr/bin/env python3
"""Tests for coordinate transformation."""
import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from convert.transform_coords import transform_coordinate, transform_ring


# Known reference points (from DATA_SOURCES.md)
ZURICH_CENTER_LV95 = (2683000, 1248000)
ZURICH_CENTER_WGS84 = (8.541694, 47.376888)


class TestTransformCoordinate:
    """Tests for single coordinate transformation."""

    def test_zurich_center_transformation(self):
        """Test transformation of Zurich city center."""
        lng, lat = transform_coordinate(*ZURICH_CENTER_LV95)
        assert abs(lng - ZURICH_CENTER_WGS84[0]) < 0.001
        assert abs(lat - ZURICH_CENTER_WGS84[1]) < 0.001

    def test_result_within_zurich_bounds(self):
        """Test transformed coords are in WGS84 Zurich bounds."""
        lng, lat = transform_coordinate(2680000, 1245000)
        assert 8.448 <= lng <= 8.626, f"Longitude {lng} out of bounds"
        assert 47.320 <= lat <= 47.435, f"Latitude {lat} out of bounds"

    def test_returns_tuple_of_floats(self):
        """Test return type is tuple of floats."""
        result = transform_coordinate(2683000, 1248000)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(v, float) for v in result)

    def test_precision_is_reasonable(self):
        """Test coordinates have reasonable precision (7 decimal places)."""
        lng, lat = transform_coordinate(2683000, 1248000)
        # Should have at most 7 decimal places
        assert len(str(lng).split('.')[-1]) <= 7
        assert len(str(lat).split('.')[-1]) <= 7


class TestTransformRing:
    """Tests for polygon ring transformation."""

    def test_transforms_all_coordinates(self):
        """Test all coordinates in ring are transformed."""
        ring = [
            [2683000, 1248000],
            [2683100, 1248000],
            [2683100, 1248100],
            [2683000, 1248100],
            [2683000, 1248000],  # Closed ring
        ]
        result = transform_ring(ring)

        assert len(result) == len(ring)
        # All should be in WGS84 range
        for coord in result:
            assert 8.0 < coord[0] < 9.0  # Longitude
            assert 47.0 < coord[1] < 48.0  # Latitude

    def test_preserves_ring_closure(self):
        """Test closed ring remains closed after transformation."""
        ring = [
            [2683000, 1248000],
            [2683100, 1248000],
            [2683000, 1248000],
        ]
        result = transform_ring(ring)
        assert result[0] == result[-1]
```

**Create file:** `scripts/tests/test_obj_to_geojson.py`
```python
#!/usr/bin/env python3
"""Tests for OBJ to GeoJSON conversion."""
import pytest
import numpy as np
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from convert.obj_to_geojson import (
    parse_obj_file,
    extract_footprint,
    convert_obj_to_feature,
    create_sample_buildings,
)


SAMPLE_CUBE_OBJ = """# Simple cube 1x1x1
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
v 0 0 1
v 1 0 1
v 1 1 1
v 0 1 1
f 1 2 3 4
f 5 6 7 8
"""


class TestParseObjFile:
    """Tests for OBJ file parsing."""

    def test_parses_vertices(self):
        """Test vertex parsing from OBJ."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.obj', delete=False) as f:
            f.write(SAMPLE_CUBE_OBJ)
            f.flush()
            result = parse_obj_file(Path(f.name))

        assert 'vertices' in result
        assert len(result['vertices']) == 8

    def test_parses_faces(self):
        """Test face parsing from OBJ."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.obj', delete=False) as f:
            f.write(SAMPLE_CUBE_OBJ)
            f.flush()
            result = parse_obj_file(Path(f.name))

        assert 'faces' in result
        assert len(result['faces']) == 2

    def test_vertex_coordinates_correct(self):
        """Test vertex coordinates are parsed correctly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.obj', delete=False) as f:
            f.write(SAMPLE_CUBE_OBJ)
            f.flush()
            result = parse_obj_file(Path(f.name))

        vertices = result['vertices']
        # First vertex should be [0, 0, 0]
        assert np.allclose(vertices[0], [0, 0, 0])
        # Last vertex should be [0, 1, 1]
        assert np.allclose(vertices[-1], [0, 1, 1])

    def test_handles_comments(self):
        """Test that comments are ignored."""
        obj_with_comments = """# This is a comment
        v 1 2 3
        # Another comment
        v 4 5 6
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.obj', delete=False) as f:
            f.write(obj_with_comments)
            f.flush()
            result = parse_obj_file(Path(f.name))

        assert len(result['vertices']) == 2


class TestExtractFootprint:
    """Tests for building footprint extraction."""

    def test_extracts_base_elevation(self):
        """Test base elevation is minimum Z."""
        vertices = np.array([
            [0, 0, 10],
            [1, 0, 10],
            [1, 1, 10],
            [0, 1, 10],
            [0, 0, 20],
            [1, 0, 20],
            [1, 1, 20],
            [0, 1, 20],
        ])
        _, base_elevation, _ = extract_footprint(vertices, [])

        assert base_elevation == 10.0

    def test_calculates_height(self):
        """Test height is difference between max and min Z."""
        vertices = np.array([
            [0, 0, 100],
            [1, 0, 100],
            [0, 0, 150],
            [1, 0, 150],
        ])
        _, _, height = extract_footprint(vertices, [])

        assert height == 50.0

    def test_empty_vertices_returns_empty(self):
        """Test empty input returns empty footprint."""
        vertices = np.array([])
        footprint, base, height = extract_footprint(vertices.reshape(0, 3), [])

        assert len(footprint) == 0
        assert base == 0
        assert height == 0


class TestCreateSampleBuildings:
    """Tests for sample building generation."""

    def test_creates_correct_count(self):
        """Test correct number of buildings are created."""
        import json

        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            output_path = Path(f.name)

        create_sample_buildings(output_path, count=50)

        with open(output_path) as f:
            data = json.load(f)

        assert len(data['features']) == 50

    def test_features_have_required_properties(self):
        """Test features have height and baseElevation."""
        import json

        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            output_path = Path(f.name)

        create_sample_buildings(output_path, count=10)

        with open(output_path) as f:
            data = json.load(f)

        for feature in data['features']:
            assert 'height' in feature['properties']
            assert 'baseElevation' in feature['properties']
            assert feature['properties']['height'] > 0

    def test_output_is_valid_geojson(self):
        """Test output is valid GeoJSON FeatureCollection."""
        import json

        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            output_path = Path(f.name)

        create_sample_buildings(output_path, count=5)

        with open(output_path) as f:
            data = json.load(f)

        assert data['type'] == 'FeatureCollection'
        assert 'features' in data
        assert all(f['type'] == 'Feature' for f in data['features'])
```

**Create file:** `scripts/tests/test_validation.py`
```python
#!/usr/bin/env python3
"""Tests for GeoJSON validation."""
import pytest
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from validate.check_data import (
    validate_coordinate,
    validate_feature,
    validate_geojson,
    ZURICH_BOUNDS,
)


class TestValidateCoordinate:
    """Tests for coordinate validation."""

    def test_valid_zurich_coordinate(self):
        """Test valid Zurich coordinate passes."""
        error = validate_coordinate(8.54, 47.37)
        assert error is None

    def test_invalid_longitude_too_low(self):
        """Test longitude below bounds fails."""
        error = validate_coordinate(8.0, 47.37)
        assert error is not None
        assert "Longitude" in error

    def test_invalid_longitude_too_high(self):
        """Test longitude above bounds fails."""
        error = validate_coordinate(9.0, 47.37)
        assert error is not None
        assert "Longitude" in error

    def test_invalid_latitude_too_low(self):
        """Test latitude below bounds fails."""
        error = validate_coordinate(8.54, 47.0)
        assert error is not None
        assert "Latitude" in error

    def test_invalid_latitude_too_high(self):
        """Test latitude above bounds fails."""
        error = validate_coordinate(8.54, 48.0)
        assert error is not None
        assert "Latitude" in error

    def test_bounds_edge_values_pass(self):
        """Test coordinates at exact bounds pass."""
        # Test minimum bounds
        error = validate_coordinate(
            ZURICH_BOUNDS["min_lng"],
            ZURICH_BOUNDS["min_lat"]
        )
        assert error is None

        # Test maximum bounds
        error = validate_coordinate(
            ZURICH_BOUNDS["max_lng"],
            ZURICH_BOUNDS["max_lat"]
        )
        assert error is None


class TestValidateFeature:
    """Tests for feature validation."""

    def test_valid_feature_passes(self):
        """Test valid feature has no errors."""
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[8.54, 47.37], [8.55, 47.37], [8.55, 47.38], [8.54, 47.37]]]
            },
            "properties": {
                "id": "test_1",
                "height": 20.0
            }
        }
        errors = validate_feature(feature, 0)
        assert len(errors) == 0

    def test_missing_geometry_fails(self):
        """Test feature without geometry fails."""
        feature = {
            "type": "Feature",
            "properties": {"id": "test_1"}
        }
        errors = validate_feature(feature, 0)
        assert len(errors) > 0
        assert any("Missing geometry" in str(e) for e in errors)

    def test_negative_height_fails(self):
        """Test negative building height is caught."""
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[8.54, 47.37], [8.55, 47.37], [8.54, 47.37]]]
            },
            "properties": {"height": -5}
        }
        errors = validate_feature(feature, 0)
        assert any("Negative height" in str(e) for e in errors)

    def test_unrealistic_height_fails(self):
        """Test unrealistic height (>500m) is caught."""
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[8.54, 47.37], [8.55, 47.37], [8.54, 47.37]]]
            },
            "properties": {"height": 600}
        }
        errors = validate_feature(feature, 0)
        assert any("Unrealistic height" in str(e) for e in errors)

    def test_swapped_coordinates_detected(self):
        """Test lat/lng swap is detected."""
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                # Swapped: [lat, lng] instead of [lng, lat]
                "coordinates": [[[47.37, 8.54], [47.38, 8.55], [47.37, 8.54]]]
            },
            "properties": {}
        }
        errors = validate_feature(feature, 0)
        assert any("swapped" in str(e).lower() for e in errors)


class TestValidateGeojson:
    """Tests for full GeoJSON file validation."""

    def test_valid_file_passes(self):
        """Test valid GeoJSON file passes validation."""
        data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[8.54, 47.37], [8.55, 47.37], [8.55, 47.38], [8.54, 47.37]]]
                    },
                    "properties": {"id": "test_1", "height": 20}
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            json.dump(data, f)
            filepath = Path(f.name)

        is_valid, errors = validate_geojson(filepath, sample_size=0)
        assert is_valid
        assert len(errors) == 0

    def test_missing_file_fails(self):
        """Test missing file returns error."""
        is_valid, errors = validate_geojson(Path("/nonexistent/file.geojson"))
        assert not is_valid
        assert any("not found" in str(e).lower() for e in errors)

    def test_invalid_json_fails(self):
        """Test invalid JSON returns error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            f.write("not valid json {{{")
            filepath = Path(f.name)

        is_valid, errors = validate_geojson(filepath)
        assert not is_valid
        assert any("Invalid JSON" in str(e) for e in errors)

    def test_not_feature_collection_fails(self):
        """Test non-FeatureCollection fails."""
        data = {"type": "Feature", "geometry": None, "properties": {}}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            json.dump(data, f)
            filepath = Path(f.name)

        is_valid, errors = validate_geojson(filepath)
        assert not is_valid
        assert any("FeatureCollection" in str(e) for e in errors)
```

**Create file:** `scripts/tests/conftest.py`
```python
#!/usr/bin/env python3
"""Pytest configuration and shared fixtures."""
import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_obj_content():
    """Sample OBJ file content for testing."""
    return """# Sample building
v 2683000 1248000 400
v 2683010 1248000 400
v 2683010 1248010 400
v 2683000 1248010 400
v 2683000 1248000 420
v 2683010 1248000 420
v 2683010 1248010 420
v 2683000 1248010 420
f 1 2 3 4
f 5 6 7 8
f 1 2 6 5
f 2 3 7 6
f 3 4 8 7
f 4 1 5 8
"""


@pytest.fixture
def sample_geojson():
    """Sample GeoJSON for testing."""
    return {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": "EPSG:4326"}
        },
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": "building_001",
                    "height": 20.0,
                    "baseElevation": 400.0
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [8.541, 47.376],
                        [8.542, 47.376],
                        [8.542, 47.377],
                        [8.541, 47.377],
                        [8.541, 47.376]
                    ]]
                }
            }
        ]
    }
```

**Verification:**
- [ ] `scripts/tests/test_transform_coords.py` exists
- [ ] `scripts/tests/test_obj_to_geojson.py` exists
- [ ] `scripts/tests/test_validation.py` exists
- [ ] `scripts/tests/conftest.py` exists
- [ ] All tests pass: `cd scripts && pytest tests/ -v`

---

## Verification Checklist

After completing all tasks:

### Core Files
- [ ] `scripts/requirements.txt` exists
- [ ] `scripts/run-pipeline.py` exists

### Package Structure
- [ ] `scripts/__init__.py` exists
- [ ] `scripts/download/__init__.py` exists
- [ ] `scripts/convert/__init__.py` exists
- [ ] `scripts/validate/__init__.py` exists
- [ ] `scripts/tests/__init__.py` exists

### Download Scripts
- [ ] `scripts/download/buildings.py` exists
- [ ] `scripts/download/terrain.py` exists

### Convert Scripts
- [ ] `scripts/convert/obj-to-geojson.py` exists
- [ ] `scripts/convert/transform-coords.py` exists
- [ ] `scripts/convert/tile-buildings.py` exists

### Validation Scripts
- [ ] `scripts/validate/check-data.py` exists

### Test Suite
- [ ] `scripts/tests/conftest.py` exists
- [ ] `scripts/tests/test_transform_coords.py` exists
- [ ] `scripts/tests/test_obj_to_geojson.py` exists
- [ ] `scripts/tests/test_validation.py` exists
- [ ] All tests pass: `cd scripts && pytest tests/ -v`

## Running the Pipeline

### Setup
```bash
cd /Users/claudioromano/Documents/livemap/zuri-3d
pip install -r scripts/requirements.txt
```

### Run Tests First
```bash
cd scripts
pytest tests/ -v
```

### Create Sample Data (For Development)
```bash
python scripts/run-pipeline.py
```

### Create Real Data
```bash
python scripts/run-pipeline.py --real-data
```

### Output
```
public/data/
└── zurich-buildings.geojson    # ~500 sample buildings
```

## Files Created

```
scripts/
├── __init__.py
├── requirements.txt
├── run-pipeline.py
├── download/
│   ├── __init__.py
│   ├── buildings.py
│   └── terrain.py
├── convert/
│   ├── __init__.py
│   ├── obj-to-geojson.py
│   ├── transform-coords.py
│   └── tile-buildings.py
├── validate/
│   ├── __init__.py
│   └── check-data.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_transform_coords.py
    ├── test_obj_to_geojson.py
    └── test_validation.py
```

## Next Phase
After running the pipeline, read and execute: `.claude/plans/phases/03-core-app.md`
