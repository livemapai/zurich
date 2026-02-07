#!/usr/bin/env python3
"""
Download bench data from Stadt Luzern via opendata.swiss.

Data source: Stadt Luzern opendata
Format: JSON/WFS
CRS: LV95 (EPSG:2056) → WGS84 (EPSG:4326)
License: Open Data

~500 benches in the city of Lucerne.
"""

import json
from pathlib import Path
from typing import Optional

# Opendata.swiss API
OPENDATA_API = "https://opendata.swiss/api/3/action/package_show"

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "public" / "data" / "lucerne"


def download_benches(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None
) -> Path:
    """
    Download bench data from Stadt Luzern.

    Args:
        output_dir: Output directory
        max_features: Limit features

    Returns:
        Path to output GeoJSON
    """
    import requests
    from pyproj import Transformer

    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "lucerne-benches.geojson"

    print("Fetching Lucerne bench data from opendata.swiss...")

    # Try to find bench dataset - various possible names
    dataset_ids = [
        "sitzbanke-stadt-luzern",
        "stadtmobiliar-luzern",
        "sitzbankkataster-luzern",
    ]

    data = None
    for dataset_id in dataset_ids:
        try:
            response = requests.get(
                OPENDATA_API,
                params={"id": dataset_id},
                timeout=30
            )
            if response.ok:
                result = response.json().get("result")
                if result and result.get("resources"):
                    # Found valid dataset
                    resources = result.get("resources", [])
                    for resource in resources:
                        format_type = resource.get("format", "").lower()
                        if format_type in ("json", "geojson", "csv"):
                            data_url = resource.get("url")
                            try:
                                resp = requests.get(data_url, timeout=60)
                                if resp.ok:
                                    data = resp.json()
                                    print(f"Found data at: {dataset_id}")
                                    break
                            except Exception:
                                continue
                    if data:
                        break
        except Exception:
            continue

    # Fallback: Try OSM Overpass for benches
    if not data:
        print("No official source found, trying OSM Overpass...")
        data = _download_osm_benches()

    if not data:
        print("Warning: Could not find bench data")
        # Create empty file
        output_data = {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
            "features": []
        }
        with open(output_path, "w") as f:
            json.dump(output_data, f)
        return output_path

    features = data.get("features", data if isinstance(data, list) else [])
    print(f"Processing {len(features)} benches...")

    transformer = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)
    standardized = []

    for i, feature in enumerate(features):
        if max_features and i >= max_features:
            break

        props = feature.get("properties", feature)
        geom = feature.get("geometry")

        if not geom:
            # Try coordinates from properties
            x = props.get("x") or props.get("X") or props.get("lng") or props.get("longitude")
            y = props.get("y") or props.get("Y") or props.get("lat") or props.get("latitude")
            if x and y:
                x, y = float(x), float(y)
                if x > 180:  # LV95
                    lng, lat = transformer.transform(x, y)
                else:
                    lng, lat = x, y
                geom = {"type": "Point", "coordinates": [lng, lat]}
            else:
                continue

        if geom.get("type") != "Point":
            continue

        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue

        # Transform if needed
        if coords[0] > 180:
            lng, lat = transformer.transform(coords[0], coords[1])
            coords = [lng, lat]

        standardized.append({
            "type": "Feature",
            "properties": {
                "id": str(props.get("id") or props.get("objectid") or f"bench_{i}"),
                "address": props.get("adresse") or props.get("standort") or "Sitzbank",
                "model": props.get("modell") or props.get("typ"),
                "material": props.get("material"),
                "condition": props.get("zustand"),
            },
            "geometry": {
                "type": "Point",
                "coordinates": [round(coords[0], 6), round(coords[1], 6)]
            }
        })

    output_data = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": standardized
    }

    with open(output_path, "w") as f:
        json.dump(output_data, f)

    print(f"Wrote {len(standardized)} benches to {output_path}")
    return output_path


def _download_osm_benches() -> dict:
    """Fallback: Download benches from OpenStreetMap via Overpass."""
    import requests

    overpass_url = "https://overpass-api.de/api/interpreter"
    query = """
    [out:json][timeout:60];
    area["name"="Luzern"]["admin_level"="8"]->.city;
    (
      node["amenity"="bench"](area.city);
    );
    out body;
    """

    try:
        response = requests.post(overpass_url, data={"data": query}, timeout=120)
        response.raise_for_status()
        data = response.json()

        # Convert OSM format to GeoJSON
        features = []
        for element in data.get("elements", []):
            if element.get("type") == "node":
                features.append({
                    "type": "Feature",
                    "properties": {
                        "id": f"osm_{element['id']}",
                        **element.get("tags", {})
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [element["lon"], element["lat"]]
                    }
                })

        return {"features": features}
    except Exception as e:
        print(f"OSM Overpass failed: {e}")
        return {}


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Lucerne bench data")
    parser.add_argument("--output", "-o", type=Path, help="Output directory")
    parser.add_argument("--max-features", "-n", type=int, help="Maximum features")

    args = parser.parse_args()
    download_benches(output_dir=args.output, max_features=args.max_features)


if __name__ == "__main__":
    main()
