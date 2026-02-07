#!/usr/bin/env python3
"""
Download fountain/drinking water data for Lucerne.

Primary: Try lucernewater.ch or opendata.swiss
Fallback: OpenStreetMap Overpass API

Data sources:
- OSM: amenity=drinking_water, amenity=fountain in Lucerne
- ~200 fountains in the city

CRS: WGS84 (EPSG:4326)
License: ODbL (OpenStreetMap)
"""

import json
from pathlib import Path
from typing import Optional

# Lucerne city bounding box (WGS84)
LUCERNE_BBOX = {
    "min_lat": 47.02,
    "max_lat": 47.08,
    "min_lng": 8.28,
    "max_lng": 8.36,
}

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "public" / "data" / "lucerne"


def download_fountains_osm() -> list:
    """
    Download fountains from OpenStreetMap via Overpass API.

    Returns:
        List of fountain features
    """
    import requests

    overpass_url = "https://overpass-api.de/api/interpreter"

    # Query for fountains and drinking water in Lucerne
    query = f"""
    [out:json][timeout:60];
    (
      node["amenity"="drinking_water"]({LUCERNE_BBOX['min_lat']},{LUCERNE_BBOX['min_lng']},{LUCERNE_BBOX['max_lat']},{LUCERNE_BBOX['max_lng']});
      node["amenity"="fountain"]({LUCERNE_BBOX['min_lat']},{LUCERNE_BBOX['min_lng']},{LUCERNE_BBOX['max_lat']},{LUCERNE_BBOX['max_lng']});
      node["man_made"="water_well"]({LUCERNE_BBOX['min_lat']},{LUCERNE_BBOX['min_lng']},{LUCERNE_BBOX['max_lat']},{LUCERNE_BBOX['max_lng']});
    );
    out body;
    """

    print("Fetching fountains from OpenStreetMap...")

    try:
        response = requests.post(
            overpass_url,
            data={"data": query},
            timeout=120
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"OSM Overpass failed: {e}")
        return []

    elements = data.get("elements", [])
    print(f"Received {len(elements)} elements from OSM")

    features = []
    for elem in elements:
        if elem.get("type") != "node":
            continue

        tags = elem.get("tags", {})

        features.append({
            "type": "Feature",
            "properties": {
                "id": f"osm_{elem['id']}",
                "name": tags.get("name") or tags.get("description") or "Brunnen",
                "type": tags.get("amenity") or tags.get("man_made"),
                "drinking_water": tags.get("drinking_water", "yes") == "yes",
                "access": tags.get("access", "yes"),
                "wheelchair": tags.get("wheelchair"),
                "source": "osm",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [
                    round(elem["lon"], 6),
                    round(elem["lat"], 6)
                ]
            }
        })

    return features


def download_fountains(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None
) -> Path:
    """
    Download fountain data for Lucerne.

    Tries official sources first, falls back to OSM.

    Args:
        output_dir: Output directory
        max_features: Limit features

    Returns:
        Path to output GeoJSON
    """
    import requests

    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "lucerne-fountains.geojson"

    features = []

    # Try official sources first
    # (Currently no known direct API - would need investigation)

    # Fallback to OSM
    if not features:
        features = download_fountains_osm()

    # Limit if requested
    if max_features and len(features) > max_features:
        features = features[:max_features]

    output_data = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": features
    }

    with open(output_path, "w") as f:
        json.dump(output_data, f)

    print(f"Wrote {len(features)} fountains to {output_path}")
    return output_path


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Lucerne fountain data")
    parser.add_argument("--output", "-o", type=Path, help="Output directory")
    parser.add_argument("--max-features", "-n", type=int, help="Maximum features")

    args = parser.parse_args()
    download_fountains(output_dir=args.output, max_features=args.max_features)


if __name__ == "__main__":
    main()
