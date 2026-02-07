#!/usr/bin/env python3
"""
Extract roof faces from LOD2 OBJ building meshes.

This script:
1. Parses OBJ files with vertices and faces
2. Computes face normals to classify roof vs wall
3. Extracts roof properties (slope, orientation)
4. Outputs GeoJSON with 3D roof polygons for texturing

Roof classification:
- Roof faces: normal.z > 0.3 (facing upward)
- Wall faces: |normal.z| < 0.3 (mostly vertical)

Output GeoJSON includes:
- 3D polygon coordinates (lng, lat, elevation)
- Roof type (gabled, flat, hipped) inferred from geometry
- Slope angle and compass orientation
- Material assignment based on building type
"""

import json
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import numpy as np
from tqdm import tqdm

# Import coordinate transformer
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from convert.transform_coords import transform_coordinate


@dataclass
class RoofFace:
    """A single roof face (polygon) with properties."""
    vertices: list  # List of [lng, lat, elevation] WGS84 coords
    normal: tuple  # (nx, ny, nz) normalized
    slope_angle: float  # Degrees from horizontal
    orientation: str  # N, NE, E, SE, S, SW, W, NW, or FLAT
    area_m2: float
    centroid_lv95: tuple  # (e, n, z) for debugging


@dataclass
class BuildingRoofs:
    """All roof faces for a building."""
    building_id: str
    roof_faces: list  # List of RoofFace
    roof_type: str  # gabled, hipped, flat, complex
    total_area_m2: float
    height: float  # Building height
    base_elevation: float


def compute_face_normal(vertices: np.ndarray) -> np.ndarray:
    """
    Compute the normal vector for a face defined by vertices.

    Uses Newell's method for robust computation on non-planar faces.

    Args:
        vertices: Nx3 array of vertex coordinates

    Returns:
        Normalized (nx, ny, nz) array
    """
    n = len(vertices)
    if n < 3:
        return np.array([0, 0, 1])

    normal = np.zeros(3)

    for i in range(n):
        v_curr = vertices[i]
        v_next = vertices[(i + 1) % n]

        normal[0] += (v_curr[1] - v_next[1]) * (v_curr[2] + v_next[2])
        normal[1] += (v_curr[2] - v_next[2]) * (v_curr[0] + v_next[0])
        normal[2] += (v_curr[0] - v_next[0]) * (v_curr[1] + v_next[1])

    length = np.linalg.norm(normal)
    if length < 1e-10:
        return np.array([0, 0, 1])

    return normal / length


def compute_face_area(vertices: np.ndarray) -> float:
    """
    Compute the area of a polygon in 3D space.

    Uses the shoelace formula generalized to 3D.

    Args:
        vertices: Nx3 array of vertex coordinates

    Returns:
        Area in square meters (assuming metric coords)
    """
    n = len(vertices)
    if n < 3:
        return 0.0

    # Compute cross products for each triangle fan from centroid
    centroid = vertices.mean(axis=0)
    total_area = 0.0

    for i in range(n):
        v1 = vertices[i] - centroid
        v2 = vertices[(i + 1) % n] - centroid
        cross = np.cross(v1, v2)
        total_area += np.linalg.norm(cross)

    return total_area / 2.0


def normal_to_orientation(normal: np.ndarray) -> str:
    """
    Convert a normal vector to compass orientation.

    Args:
        normal: (nx, ny, nz) normalized vector

    Returns:
        Compass direction (N, NE, E, SE, S, SW, W, NW, FLAT)
    """
    # If pointing mostly up, it's flat
    if abs(normal[2]) > 0.95:
        return "FLAT"

    # Calculate horizontal direction (LV95: x=east, y=north)
    angle = math.atan2(normal[0], normal[1])  # Angle from north
    degrees = math.degrees(angle)

    # Normalize to 0-360
    if degrees < 0:
        degrees += 360

    # Map to 8 compass directions
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    index = int((degrees + 22.5) / 45) % 8
    return directions[index]


def slope_from_normal(normal: np.ndarray) -> float:
    """
    Compute slope angle from normal vector.

    Args:
        normal: (nx, ny, nz) normalized vector

    Returns:
        Slope angle in degrees (0 = flat, 90 = vertical)
    """
    z = abs(normal[2])
    z = min(1.0, max(0.0, z))  # Clamp to valid range
    return math.degrees(math.acos(z))


def infer_roof_type(roof_faces: list[RoofFace]) -> str:
    """
    Infer the roof type from the collection of roof faces.

    Args:
        roof_faces: List of RoofFace objects

    Returns:
        Roof type string: gabled, hipped, flat, mansard, complex
    """
    if not roof_faces:
        return "flat"

    # Count orientations
    orientations = [f.orientation for f in roof_faces]
    unique_orientations = set(orientations)

    # Calculate average slope
    avg_slope = np.mean([f.slope_angle for f in roof_faces])

    # Mostly flat
    if avg_slope < 10:
        return "flat"

    # Two opposite directions = gabled
    opposite_pairs = [
        ({"N", "S"}), ({"E", "W"}), ({"NE", "SW"}), ({"NW", "SE"})
    ]
    for pair in opposite_pairs:
        if pair.issubset(unique_orientations) and len(unique_orientations) <= 3:
            return "gabled"

    # Four directions = hipped
    if len(unique_orientations) >= 4 and "FLAT" not in unique_orientations:
        return "hipped"

    # Multiple slopes in same direction = mansard
    slopes = [f.slope_angle for f in roof_faces]
    if max(slopes) - min(slopes) > 20 and len(unique_orientations) <= 4:
        return "mansard"

    return "complex"


def parse_obj_with_faces(filepath: Path) -> tuple[np.ndarray, list[list[int]]]:
    """
    Parse an OBJ file and extract vertices and faces.

    NOTE: Stadt Zürich LOD2 uses a rotated coordinate system:
    - X = LV95 Easting
    - Y = Elevation in meters
    - Z = -LV95 Northing (inverted!)

    This function converts to standard LV95 format (E, N, Elevation).

    Args:
        filepath: Path to OBJ file

    Returns:
        Tuple of (vertices Nx3 array in LV95 [E, N, Z], faces list of vertex indices)
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
                # Vertex: v X Y Z where X=Easting, Y=Elevation, Z=-Northing
                try:
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    # Convert to LV95: E=X, N=-Z, Elevation=Y
                    e = x
                    n = -z  # Invert Z to get Northing
                    elev = y
                    vertices.append([e, n, elev])
                except (ValueError, IndexError):
                    continue

            elif parts[0] == 'f':
                # Face: f v1 v2 v3 ... (1-indexed, may have v/vt/vn format)
                face_verts = []
                for p in parts[1:]:
                    try:
                        v_idx = int(p.split('/')[0]) - 1  # Convert to 0-indexed
                        face_verts.append(v_idx)
                    except (ValueError, IndexError):
                        continue
                if len(face_verts) >= 3:
                    faces.append(face_verts)

    return np.array(vertices), faces


def extract_roof_faces_from_obj(
    filepath: Path,
    building_id: str,
    roof_threshold: float = 0.3,
) -> Optional[BuildingRoofs]:
    """
    Extract roof faces from a single OBJ file.

    Args:
        filepath: Path to OBJ file
        building_id: ID for the building
        roof_threshold: Minimum normal.z to classify as roof (default 0.3)

    Returns:
        BuildingRoofs object or None if extraction failed
    """
    try:
        vertices, faces = parse_obj_with_faces(filepath)

        if len(vertices) == 0 or len(faces) == 0:
            return None

        # Get building bounds
        z_coords = vertices[:, 2]
        base_elevation = float(np.min(z_coords))
        height = float(np.max(z_coords) - base_elevation)

        roof_faces = []

        for face_indices in faces:
            # Get face vertices
            face_verts = vertices[face_indices]

            # Compute normal
            normal = compute_face_normal(face_verts)

            # Classify: roof if normal points upward
            if normal[2] > roof_threshold:
                # This is a roof face
                slope = slope_from_normal(normal)
                orientation = normal_to_orientation(normal)
                area = compute_face_area(face_verts)
                centroid = face_verts.mean(axis=0)

                # Convert vertices to WGS84
                wgs84_verts = []
                for v in face_verts:
                    lng, lat = transform_coordinate(v[0], v[1])
                    wgs84_verts.append([lng, lat, float(v[2])])

                roof_face = RoofFace(
                    vertices=wgs84_verts,
                    normal=tuple(normal),
                    slope_angle=slope,
                    orientation=orientation,
                    area_m2=area,
                    centroid_lv95=tuple(centroid),
                )
                roof_faces.append(roof_face)

        if not roof_faces:
            return None

        # Infer roof type
        roof_type = infer_roof_type(roof_faces)
        total_area = sum(f.area_m2 for f in roof_faces)

        return BuildingRoofs(
            building_id=building_id,
            roof_faces=roof_faces,
            roof_type=roof_type,
            total_area_m2=total_area,
            height=height,
            base_elevation=base_elevation,
        )

    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return None


def building_roofs_to_geojson_features(building: BuildingRoofs) -> list[dict]:
    """
    Convert BuildingRoofs to GeoJSON Feature list.

    Each roof face becomes a separate feature with 3D coordinates.

    Args:
        building: BuildingRoofs object

    Returns:
        List of GeoJSON Feature dicts
    """
    features = []

    for i, face in enumerate(building.roof_faces):
        # Close the polygon if needed
        coords = face.vertices.copy()
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        # Assign material based on roof type and slope
        if face.slope_angle < 10:
            material = "roof_flat"
        elif building.roof_type in ["gabled", "hipped", "mansard"]:
            material = "roof_terracotta"  # Traditional Swiss tiles
        else:
            material = "roof_slate"  # Default for complex roofs

        feature = {
            "type": "Feature",
            "properties": {
                "building_id": building.building_id,
                "face_index": i,
                "roof_type": building.roof_type,
                "slope_angle": round(face.slope_angle, 1),
                "orientation": face.orientation,
                "area_m2": round(face.area_m2, 2),
                "material": material,
                "height": round(building.height, 2),
                "base_elevation": round(building.base_elevation, 2),
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords],
            }
        }
        features.append(feature)

    return features


def extract_all_roof_faces(
    input_dir: Path,
    output_path: Path,
    max_buildings: Optional[int] = None,
) -> dict:
    """
    Extract roof faces from all OBJ files in a directory.

    Args:
        input_dir: Directory containing OBJ files
        output_path: Output GeoJSON file path
        max_buildings: Maximum buildings to process

    Returns:
        Statistics dict
    """
    obj_files = list(input_dir.glob("*.obj"))
    print(f"Found {len(obj_files)} OBJ files in {input_dir}")

    if max_buildings:
        obj_files = obj_files[:max_buildings]
        print(f"Processing first {max_buildings} buildings")

    stats = {
        "total_buildings": len(obj_files),
        "buildings_with_roofs": 0,
        "total_roof_faces": 0,
        "roof_types": {},
        "orientations": {},
        "avg_slope": 0.0,
    }

    all_features = []
    all_slopes = []

    for filepath in tqdm(obj_files, desc="Extracting roofs"):
        building_id = filepath.stem
        building = extract_roof_faces_from_obj(filepath, building_id)

        if building and building.roof_faces:
            features = building_roofs_to_geojson_features(building)
            all_features.extend(features)

            stats["buildings_with_roofs"] += 1
            stats["total_roof_faces"] += len(building.roof_faces)

            # Track roof types
            rt = building.roof_type
            stats["roof_types"][rt] = stats["roof_types"].get(rt, 0) + 1

            # Track orientations
            for face in building.roof_faces:
                o = face.orientation
                stats["orientations"][o] = stats["orientations"].get(o, 0) + 1
                all_slopes.append(face.slope_angle)

    if all_slopes:
        stats["avg_slope"] = round(np.mean(all_slopes), 1)

    # Create GeoJSON FeatureCollection
    geojson = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": "EPSG:4326"}
        },
        "metadata": {
            "source": "Stadt Zürich LOD2 3D-Dachmodell",
            "stats": stats,
        },
        "features": all_features,
    }

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(geojson, f)

    print(f"\n=== Extraction Statistics ===")
    print(f"Total buildings processed: {stats['total_buildings']}")
    print(f"Buildings with roofs: {stats['buildings_with_roofs']}")
    print(f"Total roof faces: {stats['total_roof_faces']}")
    print(f"Average slope: {stats['avg_slope']}°")
    print(f"\nRoof types:")
    for rt, count in sorted(stats["roof_types"].items(), key=lambda x: -x[1]):
        print(f"  {rt}: {count}")
    print(f"\nOrientations:")
    for o, count in sorted(stats["orientations"].items(), key=lambda x: -x[1]):
        print(f"  {o}: {count}")
    print(f"\nOutput: {output_path}")

    return stats


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract roof faces from LOD2 OBJ buildings"
    )
    parser.add_argument(
        "input_dir",
        type=Path,
        nargs="?",
        default=Path("data/raw/lod2-buildings"),
        help="Input directory with OBJ files"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("data/processed/zurich-roofs.geojson"),
        help="Output GeoJSON file"
    )
    parser.add_argument(
        "--max-buildings", "-n",
        type=int,
        help="Maximum buildings to process"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print statistics only (from existing GeoJSON)"
    )

    args = parser.parse_args()

    if args.stats:
        # Print stats from existing file
        if args.output.exists():
            with open(args.output) as f:
                data = json.load(f)
            stats = data.get("metadata", {}).get("stats", {})
            print(f"Statistics from {args.output}:")
            print(json.dumps(stats, indent=2))
        else:
            print(f"File not found: {args.output}")
    else:
        extract_all_roof_faces(
            args.input_dir,
            args.output,
            args.max_buildings,
        )


if __name__ == "__main__":
    main()
