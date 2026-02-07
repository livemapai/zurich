#!/usr/bin/env python3
"""
Data preparation utilities for vector tile pipeline.

Handles:
- Tree sampling by zoom level
- Wobble distortion using Perlin noise
- Shadow geometry generation
- Street classification
- POI layer combining
"""

import json
import random
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from copy import deepcopy

try:
    from noise import pnoise2
    HAS_NOISE = True
except ImportError:
    HAS_NOISE = False
    print("Warning: 'noise' package not installed. Wobble effect unavailable.")
    print("Install with: pip install noise")


# Coordinate conversion constants for Zurich (47°N)
# 1 degree longitude ≈ 75,500 meters
# 1 degree latitude ≈ 111,320 meters
METERS_PER_DEGREE_LNG = 75500
METERS_PER_DEGREE_LAT = 111320


def load_geojson(path: Path) -> dict:
    """Load GeoJSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_geojson(data: dict, path: Path):
    """Save GeoJSON file with compact formatting."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))


def sample_trees(
    input_path: Path,
    output_path: Path,
    sample_rate: int = 10,
    seed: int = 42,
    verbose: bool = False
) -> int:
    """
    Sample trees for lower zoom levels.

    Args:
        input_path: Path to source trees GeoJSON
        output_path: Path for sampled output
        sample_rate: Keep 1 in N trees (10 = 10%, 5 = 20%)
        seed: Random seed for reproducibility
        verbose: Print progress info

    Returns:
        Number of sampled features
    """
    data = load_geojson(input_path)
    features = data.get("features", [])

    random.seed(seed)
    sampled = [f for i, f in enumerate(features) if i % sample_rate == 0]

    output = {
        "type": "FeatureCollection",
        "features": sampled
    }

    save_geojson(output, output_path)

    if verbose:
        print(f"  Sampled {len(sampled)}/{len(features)} trees (1/{sample_rate})")

    return len(sampled)


def apply_isometric_tilt(
    input_path: Path,
    output_path: Path,
    shear: float = 0.3,
    compress_y: float = 0.85,
    center_lat: float = 47.3769,
    center_lng: float = 8.5417,
    verbose: bool = False
) -> int:
    """
    Apply oblique/isometric projection to GeoJSON.

    Creates SimCity-style pseudo-3D effect by:
    1. Shearing X based on Y coordinate (oblique projection)
    2. Compressing Y axis (foreshortening)

    The transformation is applied relative to a center point to avoid
    coordinate drift at the edges of the dataset.

    Visual effect:
        Normal (top-down):     Oblique (tilted):
        ┌──────┐               ╱──────╲
        │      │              ╱       ╱
        │      │             ╱       ╱
        └──────┘            ╱───────╱

    Recommended parameter values:
        - Subtle:    shear=0.15, compress_y=0.9
        - Standard:  shear=0.3,  compress_y=0.85  (default)
        - Dramatic:  shear=0.45, compress_y=0.75

    Args:
        input_path: Source GeoJSON
        output_path: Output path for tilted geometry
        shear: Oblique shear factor (0.3 = 30% shift, higher = more tilt)
        compress_y: Vertical compression factor (0.85 = 15% shorter)
        center_lat: Center latitude for transformation (Zurich default)
        center_lng: Center longitude for transformation (Zurich default)
        verbose: Print progress info

    Returns:
        Number of processed features
    """
    data = load_geojson(input_path)
    features = data.get("features", [])

    def tilt_coord(coord: List[float]) -> List[float]:
        """Apply isometric tilt to a single coordinate."""
        lng, lat = coord[0], coord[1]

        # Transform relative to center to avoid drift
        rel_lat = lat - center_lat
        rel_lng = lng - center_lng

        # Apply shear: shift X based on Y position
        new_rel_lng = rel_lng + (rel_lat * shear)

        # Apply Y compression for foreshortening effect
        new_rel_lat = rel_lat * compress_y

        # Transform back to absolute coordinates
        new_lng = new_rel_lng + center_lng
        new_lat = new_rel_lat + center_lat

        # Preserve altitude if present
        if len(coord) > 2:
            return [new_lng, new_lat, coord[2]]
        return [new_lng, new_lat]

    def tilt_ring(ring: List[List[float]]) -> List[List[float]]:
        """Apply tilt to polygon ring."""
        return [tilt_coord(c) for c in ring]

    def tilt_geometry(geom: dict) -> dict:
        """Apply tilt to geometry."""
        geom = deepcopy(geom)
        geom_type = geom.get("type")

        if geom_type == "Point":
            geom["coordinates"] = tilt_coord(geom["coordinates"])

        elif geom_type == "LineString":
            geom["coordinates"] = [tilt_coord(c) for c in geom["coordinates"]]

        elif geom_type == "Polygon":
            geom["coordinates"] = [tilt_ring(ring) for ring in geom["coordinates"]]

        elif geom_type == "MultiPolygon":
            geom["coordinates"] = [
                [tilt_ring(ring) for ring in poly]
                for poly in geom["coordinates"]
            ]

        elif geom_type == "MultiLineString":
            geom["coordinates"] = [
                [tilt_coord(c) for c in line]
                for line in geom["coordinates"]
            ]

        return geom

    # Process all features
    tilted_features = []
    for feature in features:
        new_feature = deepcopy(feature)
        if feature.get("geometry"):
            new_feature["geometry"] = tilt_geometry(feature["geometry"])
        tilted_features.append(new_feature)

    output = {
        "type": "FeatureCollection",
        "features": tilted_features
    }

    save_geojson(output, output_path)

    if verbose:
        print(f"  Applied isometric tilt to {len(tilted_features)} features "
              f"(shear: {shear}, compress: {compress_y})")

    return len(tilted_features)


def apply_wobble(
    input_path: Path,
    output_path: Path,
    scale: float = 0.00001,
    octaves: int = 2,
    seed: int = 42,
    verbose: bool = False
) -> int:
    """
    Apply Perlin noise distortion for hand-drawn appearance.

    The wobble creates ~1 meter variation in coordinates using Perlin noise,
    which produces organic, continuous distortion rather than random jitter.

    Args:
        input_path: Source GeoJSON
        output_path: Output path for wobbled geometry
        scale: Distortion scale in degrees (~0.00001 ≈ 1 meter at Zurich)
        octaves: Perlin noise octaves (1-4, higher = more detail)
        seed: Random seed for reproducibility
        verbose: Print progress info

    Returns:
        Number of processed features
    """
    if not HAS_NOISE:
        raise RuntimeError("noise package not installed. Run: pip install noise")

    data = load_geojson(input_path)
    features = data.get("features", [])

    def wobble_coord(coord: List[float], feature_idx: int) -> List[float]:
        """Apply Perlin noise to a single coordinate."""
        lng, lat = coord[0], coord[1]

        # Use coordinate + feature index for unique noise per vertex
        noise_x = pnoise2(
            lng * 10000 + seed,
            lat * 10000,
            octaves=octaves
        )
        noise_y = pnoise2(
            lng * 10000,
            lat * 10000 + seed,
            octaves=octaves
        )

        # Apply scaled distortion
        new_lng = lng + noise_x * scale
        new_lat = lat + noise_y * scale

        # Preserve altitude if present
        if len(coord) > 2:
            return [new_lng, new_lat, coord[2]]
        return [new_lng, new_lat]

    def wobble_ring(ring: List[List[float]], feature_idx: int) -> List[List[float]]:
        """Apply wobble to polygon ring."""
        return [wobble_coord(c, feature_idx) for c in ring]

    def wobble_geometry(geom: dict, feature_idx: int) -> dict:
        """Apply wobble to geometry."""
        geom = deepcopy(geom)
        geom_type = geom.get("type")

        if geom_type == "Point":
            geom["coordinates"] = wobble_coord(geom["coordinates"], feature_idx)

        elif geom_type == "LineString":
            geom["coordinates"] = [
                wobble_coord(c, feature_idx) for c in geom["coordinates"]
            ]

        elif geom_type == "Polygon":
            geom["coordinates"] = [
                wobble_ring(ring, feature_idx) for ring in geom["coordinates"]
            ]

        elif geom_type == "MultiPolygon":
            geom["coordinates"] = [
                [wobble_ring(ring, feature_idx) for ring in poly]
                for poly in geom["coordinates"]
            ]

        elif geom_type == "MultiLineString":
            geom["coordinates"] = [
                [wobble_coord(c, feature_idx) for c in line]
                for line in geom["coordinates"]
            ]

        return geom

    # Process all features
    wobbled_features = []
    for i, feature in enumerate(features):
        new_feature = deepcopy(feature)
        if feature.get("geometry"):
            new_feature["geometry"] = wobble_geometry(feature["geometry"], i)
        wobbled_features.append(new_feature)

    output = {
        "type": "FeatureCollection",
        "features": wobbled_features
    }

    save_geojson(output, output_path)

    if verbose:
        print(f"  Applied wobble to {len(wobbled_features)} features (scale: {scale})")

    return len(wobbled_features)


def create_shadow_geometry(
    input_path: Path,
    output_path: Path,
    offset_x: float = 3.0,
    offset_y: float = 3.0,
    verbose: bool = False
) -> int:
    """
    Create offset shadow geometry for buildings.

    Generates a copy of building footprints offset by a fixed distance,
    used for drop shadow rendering in MapLibre.

    Args:
        input_path: Source buildings GeoJSON
        output_path: Output path for shadow geometry
        offset_x: X offset in meters (positive = east)
        offset_y: Y offset in meters (positive = south)
        verbose: Print progress info

    Returns:
        Number of shadow features created
    """
    data = load_geojson(input_path)
    features = data.get("features", [])

    # Convert meters to degrees
    offset_lng = offset_x / METERS_PER_DEGREE_LNG
    offset_lat = -offset_y / METERS_PER_DEGREE_LAT  # Negative because south

    def offset_coord(coord: List[float]) -> List[float]:
        """Offset a single coordinate."""
        lng, lat = coord[0], coord[1]
        new_coord = [lng + offset_lng, lat + offset_lat]
        if len(coord) > 2:
            new_coord.append(coord[2])
        return new_coord

    def offset_ring(ring: List[List[float]]) -> List[List[float]]:
        """Offset a polygon ring."""
        return [offset_coord(c) for c in ring]

    def offset_geometry(geom: dict) -> dict:
        """Offset geometry coordinates."""
        geom = deepcopy(geom)
        geom_type = geom.get("type")

        if geom_type == "Polygon":
            geom["coordinates"] = [offset_ring(ring) for ring in geom["coordinates"]]

        elif geom_type == "MultiPolygon":
            geom["coordinates"] = [
                [offset_ring(ring) for ring in poly]
                for poly in geom["coordinates"]
            ]

        return geom

    shadow_features = []
    for feature in features:
        if feature.get("geometry"):
            shadow_feature = {
                "type": "Feature",
                "properties": {
                    "id": feature.get("properties", {}).get("id"),
                    "height": feature.get("properties", {}).get("height"),
                },
                "geometry": offset_geometry(feature["geometry"])
            }
            shadow_features.append(shadow_feature)

    output = {
        "type": "FeatureCollection",
        "features": shadow_features
    }

    save_geojson(output, output_path)

    if verbose:
        print(f"  Created {len(shadow_features)} shadow features (offset: {offset_x}m, {offset_y}m)")

    return len(shadow_features)


# Street type mapping (German -> English class)
STREET_TYPE_MAP = {
    "Hauptstrasse": "primary",
    "Hauptstr": "primary",
    "Verbindungsstrasse": "secondary",
    "Verbindungsstr": "secondary",
    "Quartierstrasse": "residential",
    "Quartierstr": "residential",
    "Erschliessungsstrasse": "residential",
    "Fussweg": "footway",
    "Gehweg": "footway",
    "Fussgangerzone": "pedestrian",
    "Veloweg": "cycleway",
    "Radweg": "cycleway",
    "Trottoir": "sidewalk",
    "Platz": "square",
    "Strassenbreite": "service",
}


def transform_streets(
    input_path: Path,
    output_path: Path,
    verbose: bool = False
) -> int:
    """
    Transform street data, adding English class from German street_type.

    Args:
        input_path: Source streets GeoJSON
        output_path: Output path for transformed streets
        verbose: Print progress info

    Returns:
        Number of transformed features
    """
    data = load_geojson(input_path)
    features = data.get("features", [])

    transformed = []
    class_counts = {}

    for feature in features:
        props = feature.get("properties", {})
        street_type = props.get("street_type", "")

        # Map to English class
        street_class = "other"
        for german, english in STREET_TYPE_MAP.items():
            if german.lower() in street_type.lower():
                street_class = english
                break

        # Track class distribution
        class_counts[street_class] = class_counts.get(street_class, 0) + 1

        # Create new feature with added class
        new_feature = deepcopy(feature)
        new_feature["properties"]["class"] = street_class

        transformed.append(new_feature)

    output = {
        "type": "FeatureCollection",
        "features": transformed
    }

    save_geojson(output, output_path)

    if verbose:
        print(f"  Transformed {len(transformed)} streets")
        print(f"  Class distribution: {class_counts}")

    return len(transformed)


# POI class/subclass mapping
POI_CLASS_MAP = {
    "bench": ("amenity", "bench"),
    "fountain": ("amenity", "fountain"),
    "toilets": ("amenity", "toilets"),
    "street_lamp": ("infrastructure", "street_lamp"),
    "utility_pole": ("infrastructure", "utility_pole"),
}


def combine_poi_layers(
    layer_paths: Dict[str, Path],
    output_path: Path,
    verbose: bool = False
) -> int:
    """
    Combine multiple POI layers into a single layer with class/subclass.

    Args:
        layer_paths: Dict mapping subclass name to file path
        output_path: Output path for combined POI
        verbose: Print progress info

    Returns:
        Number of combined features
    """
    combined_features = []
    layer_counts = {}

    for subclass, path in layer_paths.items():
        if not path.exists():
            if verbose:
                print(f"  Warning: {path.name} not found, skipping")
            continue

        data = load_geojson(path)
        features = data.get("features", [])

        # Get class from mapping
        poi_class, poi_subclass = POI_CLASS_MAP.get(subclass, ("other", subclass))

        for feature in features:
            props = feature.get("properties", {})

            # Build normalized properties
            new_props = {
                "id": props.get("id"),
                "class": poi_class,
                "subclass": poi_subclass,
            }

            # Add optional properties if present
            if props.get("name"):
                new_props["name"] = props["name"]
            if props.get("height"):
                new_props["height"] = props["height"]
            if props.get("elevation"):
                new_props["elevation"] = props["elevation"]

            combined_features.append({
                "type": "Feature",
                "properties": new_props,
                "geometry": feature.get("geometry")
            })

        layer_counts[subclass] = len(features)

    output = {
        "type": "FeatureCollection",
        "features": combined_features
    }

    save_geojson(output, output_path)

    if verbose:
        print(f"  Combined {len(combined_features)} POI features")
        print(f"  Layer counts: {layer_counts}")

    return len(combined_features)


if __name__ == "__main__":
    # Test functions
    import sys

    if len(sys.argv) > 1:
        test_func = sys.argv[1]

        project_root = Path(__file__).parent.parent.parent
        data_dir = project_root / "public" / "data"
        temp_dir = project_root / "temp" / "vector_tiles"
        temp_dir.mkdir(parents=True, exist_ok=True)

        if test_func == "sample":
            sample_trees(
                data_dir / "zurich-trees.geojson",
                temp_dir / "test-trees-sampled.geojson",
                sample_rate=10,
                verbose=True
            )

        elif test_func == "wobble":
            apply_wobble(
                data_dir / "zurich-buildings.geojson",
                temp_dir / "test-buildings-wobbled.geojson",
                scale=0.00001,
                verbose=True
            )

        elif test_func == "shadow":
            create_shadow_geometry(
                data_dir / "zurich-buildings.geojson",
                temp_dir / "test-shadows.geojson",
                verbose=True
            )

        elif test_func == "streets":
            transform_streets(
                data_dir / "zurich-streets.geojson",
                temp_dir / "test-streets.geojson",
                verbose=True
            )

        elif test_func == "tilt":
            apply_isometric_tilt(
                data_dir / "zurich-buildings.geojson",
                temp_dir / "test-buildings-tilted.geojson",
                shear=0.3,
                compress_y=0.85,
                verbose=True
            )

        else:
            print(f"Unknown test: {test_func}")
            print("Available: sample, wobble, shadow, streets, tilt")
