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
