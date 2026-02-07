#!/usr/bin/env python3
"""
Download and merge tree data from Canton Lucerne and Stadt Luzern.

Data sources:
1. Canton LIDAR trees (~10M in canton, filtered to city):
   https://daten.geo.lu.ch/produkt/einzbaum_ds_v1

2. City curated trees (~11K with species info):
   https://opendata.swiss/de/dataset/baume-standort-und-informationen

Merge strategy:
- City trees take priority (better attributes: species, planting year)
- Canton LIDAR trees within 10m of city trees are removed (duplicates)
- Result: ~15-25K merged trees in city bounds

CRS: LV95 (EPSG:2056) → WGS84 (EPSG:4326)
License: Open Data
"""

import json
from pathlib import Path
from typing import Optional

# Lucerne city bounds in LV95
LUCERNE_BOUNDS_LV95 = {
    "min_e": 2665000,
    "max_e": 2670000,
    "min_n": 1210000,
    "max_n": 1215000,
}

# WFS endpoints
LIDAR_WFS_URL = "https://geo.lu.ch/wfs/einzbaum_ds_v1"
LIDAR_FEATURE_TYPE = "einzelbaeume"

# City trees - opendata.swiss API
OPENDATA_API = "https://opendata.swiss/api/3/action/package_show"
CITY_TREES_DATASET = "baume-standort-und-informationen"

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "public" / "data" / "lucerne"


def download_lidar_trees(
    bbox: Optional[tuple] = None,
    max_features: Optional[int] = None
) -> list:
    """
    Download LIDAR-detected trees from Canton Lucerne WFS.

    The canton has ~10M trees detected from LIDAR. We filter to
    city bounds to get a manageable subset.

    Args:
        bbox: (minE, minN, maxE, maxN) in LV95
        max_features: Limit features (for testing)

    Returns:
        List of standardized tree features
    """
    import requests
    from pyproj import Transformer

    if bbox is None:
        bbox = (
            LUCERNE_BOUNDS_LV95["min_e"],
            LUCERNE_BOUNDS_LV95["min_n"],
            LUCERNE_BOUNDS_LV95["max_e"],
            LUCERNE_BOUNDS_LV95["max_n"],
        )

    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": LIDAR_FEATURE_TYPE,
        "outputFormat": "application/json",
        "srsName": "EPSG:2056",  # Native CRS
        "BBOX": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:2056",
    }

    if max_features:
        params["COUNT"] = str(max_features)

    print(f"Fetching LIDAR trees from Canton Lucerne WFS...")
    print(f"BBOX: {bbox}")

    try:
        response = requests.get(LIDAR_WFS_URL, params=params, timeout=300)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Warning: LIDAR trees WFS failed: {e}")
        return []

    features = data.get("features", [])
    print(f"Received {len(features)} LIDAR trees")

    # Transform to WGS84 and standardize
    transformer = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)
    standardized = []

    for i, feature in enumerate(features):
        props = feature.get("properties", {})
        geom = feature.get("geometry")

        if not geom or geom.get("type") != "Point":
            continue

        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue

        # Transform coordinates
        try:
            lng, lat = transformer.transform(coords[0], coords[1])
        except Exception:
            continue

        # Get elevation from Z coordinate or property
        elevation = coords[2] if len(coords) > 2 else props.get("Z") or 0

        standardized.append({
            "type": "Feature",
            "properties": {
                "id": f"lidar_{i}",
                "source": "canton_lidar",
                "height": props.get("HOEHE") or props.get("hoehe") or 10.0,
                "crown_diameter": props.get("KRONENDURCHMESSER") or props.get("kronendurchmesser") or 5.0,
                "elevation": float(elevation),
                # LIDAR doesn't have species info
                "species": None,
                "species_de": None,
                "year_planted": None,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [round(lng, 6), round(lat, 6)]
            },
            "_coords_lv95": coords[:2]  # Keep for deduplication
        })

    return standardized


def download_city_trees(max_features: Optional[int] = None) -> list:
    """
    Download curated city trees from Stadt Luzern via opendata.swiss.

    These trees have rich metadata: species, planting year, etc.

    Args:
        max_features: Limit features

    Returns:
        List of standardized tree features
    """
    import requests
    from pyproj import Transformer

    print(f"Fetching city trees from opendata.swiss...")

    # First get the dataset metadata to find the resource URL
    try:
        response = requests.get(
            OPENDATA_API,
            params={"id": CITY_TREES_DATASET},
            timeout=30
        )
        response.raise_for_status()
        dataset = response.json().get("result", {})
    except Exception as e:
        print(f"Warning: Could not fetch dataset metadata: {e}")
        return []

    # Find JSON or GeoJSON resource
    resources = dataset.get("resources", [])
    data_url = None
    for resource in resources:
        format_type = resource.get("format", "").lower()
        if format_type in ("json", "geojson"):
            data_url = resource.get("url")
            break

    # Try WFS if no JSON resource
    if not data_url:
        for resource in resources:
            if "wfs" in resource.get("url", "").lower():
                data_url = resource.get("url")
                break

    if not data_url:
        print("Warning: Could not find city trees data URL")
        # Try known WFS endpoint
        data_url = "https://www.stadtluzern.ch/wfs/baeume"

    print(f"Downloading from: {data_url}")

    try:
        # Check if it's a WFS or direct JSON
        if "wfs" in data_url.lower():
            params = {
                "SERVICE": "WFS",
                "REQUEST": "GetFeature",
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
            }
            if max_features:
                params["COUNT"] = str(max_features)
            response = requests.get(data_url, params=params, timeout=120)
        else:
            response = requests.get(data_url, timeout=120)

        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Warning: Could not download city trees: {e}")
        return []

    features = data.get("features", data.get("results", []))
    if isinstance(data, list):
        features = data

    print(f"Received {len(features)} city trees")

    transformer = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)
    standardized = []

    for i, feature in enumerate(features):
        if max_features and i >= max_features:
            break

        props = feature.get("properties", feature)
        geom = feature.get("geometry")

        if not geom:
            # Try to get coordinates from properties
            x = props.get("x") or props.get("X") or props.get("e") or props.get("E")
            y = props.get("y") or props.get("Y") or props.get("n") or props.get("N")
            if x and y:
                # Likely LV95 coordinates
                try:
                    lng, lat = transformer.transform(float(x), float(y))
                    geom = {"type": "Point", "coordinates": [lng, lat]}
                except Exception:
                    continue
            else:
                continue

        if geom.get("type") != "Point":
            continue

        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue

        # Check if coordinates need transformation (LV95 vs WGS84)
        if coords[0] > 180:  # Likely LV95
            try:
                lng, lat = transformer.transform(coords[0], coords[1])
                coords = [lng, lat]
            except Exception:
                continue

        standardized.append({
            "type": "Feature",
            "properties": {
                "id": str(props.get("baum_id") or props.get("id") or f"city_{i}"),
                "source": "city_curated",
                "height": props.get("baumhoehe") or props.get("hoehe") or 10.0,
                "crown_diameter": props.get("kronendurchmesser") or 5.0,
                "trunk_diameter": props.get("stammdurchmesser") or 0.3,
                "species": props.get("baumgattunglat") or props.get("baumart_lat"),
                "species_de": props.get("baumgattung") or props.get("baumart"),
                "year_planted": props.get("pflanzjahr"),
            },
            "geometry": {
                "type": "Point",
                "coordinates": [round(coords[0], 6), round(coords[1], 6)]
            }
        })

    return standardized


def merge_trees(
    lidar_trees: list,
    city_trees: list,
    dedup_radius: float = 10.0
) -> list:
    """
    Merge LIDAR and city trees, removing duplicates.

    City trees take priority. LIDAR trees within dedup_radius
    meters of a city tree are considered duplicates.

    Args:
        lidar_trees: Trees from LIDAR detection
        city_trees: Curated city trees
        dedup_radius: Radius in meters for duplicate detection

    Returns:
        Merged list of trees
    """
    from math import radians, cos, sin, sqrt, atan2

    def haversine(lat1, lon1, lat2, lon2):
        """Calculate distance in meters."""
        R = 6371000
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        return 2 * R * atan2(sqrt(a), sqrt(1-a))

    print(f"Merging {len(city_trees)} city trees + {len(lidar_trees)} LIDAR trees...")
    print(f"Deduplication radius: {dedup_radius}m")

    # Build spatial index for city trees
    city_coords = []
    for tree in city_trees:
        coords = tree.get("geometry", {}).get("coordinates", [])
        if len(coords) >= 2:
            city_coords.append((coords[1], coords[0]))  # (lat, lng)

    # Filter LIDAR trees that are not near city trees
    merged = list(city_trees)  # Start with all city trees
    duplicates = 0

    for tree in lidar_trees:
        coords = tree.get("geometry", {}).get("coordinates", [])
        if len(coords) < 2:
            continue

        lat, lng = coords[1], coords[0]

        # Check if near any city tree
        is_duplicate = False
        for city_lat, city_lng in city_coords:
            dist = haversine(lat, lng, city_lat, city_lng)
            if dist < dedup_radius:
                is_duplicate = True
                duplicates += 1
                break

        if not is_duplicate:
            # Remove internal dedup helper
            if "_coords_lv95" in tree:
                del tree["_coords_lv95"]
            merged.append(tree)

    print(f"Removed {duplicates} duplicate LIDAR trees")
    print(f"Final merged count: {len(merged)} trees")

    return merged


def download_trees(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None,
    lidar_only: bool = False,
    city_only: bool = False
) -> Path:
    """
    Download and merge tree data from both sources.

    Args:
        output_dir: Output directory
        max_features: Limit per source
        lidar_only: Only download LIDAR trees
        city_only: Only download city trees

    Returns:
        Path to output GeoJSON
    """
    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "lucerne-trees.geojson"

    lidar_trees = []
    city_trees = []

    if not city_only:
        lidar_trees = download_lidar_trees(max_features=max_features)

    if not lidar_only:
        city_trees = download_city_trees(max_features=max_features)

    # Merge sources
    if lidar_only:
        trees = lidar_trees
    elif city_only:
        trees = city_trees
    else:
        trees = merge_trees(lidar_trees, city_trees)

    output_data = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": trees
    }

    with open(output_path, "w") as f:
        json.dump(output_data, f)

    print(f"Wrote {len(trees)} trees to {output_path}")
    return output_path


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download Lucerne tree data"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output directory"
    )
    parser.add_argument(
        "--max-features", "-n",
        type=int,
        help="Maximum features per source"
    )
    parser.add_argument(
        "--lidar-only",
        action="store_true",
        help="Only download LIDAR trees"
    )
    parser.add_argument(
        "--city-only",
        action="store_true",
        help="Only download city curated trees"
    )

    args = parser.parse_args()

    download_trees(
        output_dir=args.output,
        max_features=args.max_features,
        lidar_only=args.lidar_only,
        city_only=args.city_only
    )


if __name__ == "__main__":
    main()
