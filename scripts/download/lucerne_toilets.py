#!/usr/bin/env python3
"""
Download public toilet data for Lucerne from WC Guide XML.

Data source: https://sonnenschauer.net/xml/wcguide-toilets-luzern.xml
Format: Custom XML
License: Unknown (public data)

~80 public toilets in Lucerne area.

WC Guide type codes:
  1 = Public toilet
  2 = Customer toilet (restaurant/shop)
  3 = Train station toilet
  4 = Other

Example XML entry:
<toilet id="123">
    <lat>47.0502</lat>
    <lng>8.3093</lng>
    <name>HB Luzern</name>
    <type>3</type>
    <fee>1</fee>
    <wheelchair>1</wheelchair>
    <hours>24h</hours>
</toilet>
"""

import json
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

# WC Guide XML URL for Lucerne
WCGUIDE_URL = "https://sonnenschauer.net/xml/wcguide-toilets-luzern.xml"

# Fallback: OSM bounding box
LUCERNE_BBOX = {
    "min_lat": 47.02,
    "max_lat": 47.08,
    "min_lng": 8.28,
    "max_lng": 8.36,
}

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "public" / "data" / "lucerne"

# Type mapping
TOILET_TYPES = {
    "1": "public",
    "2": "customer",
    "3": "station",
    "4": "other",
}


def download_toilets_wcguide() -> list:
    """
    Download toilets from WC Guide XML.

    Returns:
        List of toilet features
    """
    import requests

    print(f"Fetching toilets from WC Guide...")
    print(f"URL: {WCGUIDE_URL}")

    try:
        response = requests.get(WCGUIDE_URL, timeout=30)
        response.raise_for_status()
        xml_content = response.content
    except Exception as e:
        print(f"WC Guide download failed: {e}")
        return []

    # Parse XML
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"XML parse error: {e}")
        return []

    features = []

    # Find all toilet elements (various possible structures)
    toilets = root.findall(".//toilet") or root.findall(".//wc") or root.findall(".//item")

    if not toilets:
        # Try root children directly
        toilets = list(root)

    print(f"Found {len(toilets)} toilet entries")

    for toilet in toilets:
        try:
            # Extract coordinates
            lat = toilet.findtext("lat") or toilet.findtext("latitude") or toilet.get("lat")
            lng = toilet.findtext("lng") or toilet.findtext("lon") or toilet.findtext("longitude") or toilet.get("lng")

            if not lat or not lng:
                continue

            lat = float(lat)
            lng = float(lng)

            # Extract properties
            toilet_id = toilet.get("id") or toilet.findtext("id") or f"wc_{len(features)}"
            name = toilet.findtext("name") or toilet.findtext("title") or "WC"
            toilet_type = toilet.findtext("type") or "1"
            fee = toilet.findtext("fee") or toilet.findtext("price") or "0"
            wheelchair = toilet.findtext("wheelchair") or toilet.findtext("accessible") or "0"
            hours = toilet.findtext("hours") or toilet.findtext("opening_hours") or ""

            features.append({
                "type": "Feature",
                "properties": {
                    "id": str(toilet_id),
                    "name": name,
                    "category": TOILET_TYPES.get(toilet_type, "public"),
                    "fee": fee not in ("0", "false", "no", ""),
                    "accessible": wheelchair in ("1", "true", "yes"),
                    "hours": hours,
                    "source": "wcguide",
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(lng, 6), round(lat, 6)]
                }
            })

        except (ValueError, TypeError) as e:
            print(f"Warning: Failed to parse toilet entry: {e}")
            continue

    return features


def download_toilets_osm() -> list:
    """
    Fallback: Download toilets from OpenStreetMap.

    Returns:
        List of toilet features
    """
    import requests

    overpass_url = "https://overpass-api.de/api/interpreter"

    query = f"""
    [out:json][timeout:60];
    (
      node["amenity"="toilets"]({LUCERNE_BBOX['min_lat']},{LUCERNE_BBOX['min_lng']},{LUCERNE_BBOX['max_lat']},{LUCERNE_BBOX['max_lng']});
    );
    out body;
    """

    print("Fetching toilets from OpenStreetMap...")

    try:
        response = requests.post(overpass_url, data={"data": query}, timeout=120)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"OSM Overpass failed: {e}")
        return []

    features = []
    for elem in data.get("elements", []):
        if elem.get("type") != "node":
            continue

        tags = elem.get("tags", {})

        features.append({
            "type": "Feature",
            "properties": {
                "id": f"osm_{elem['id']}",
                "name": tags.get("name") or "WC",
                "category": "public",
                "fee": tags.get("fee") == "yes",
                "accessible": tags.get("wheelchair") in ("yes", "limited"),
                "hours": tags.get("opening_hours", ""),
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


def download_toilets(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None
) -> Path:
    """
    Download toilet data for Lucerne.

    Tries WC Guide XML first, falls back to OSM.

    Args:
        output_dir: Output directory
        max_features: Limit features

    Returns:
        Path to output GeoJSON
    """
    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "lucerne-toilets.geojson"

    # Try WC Guide first
    features = download_toilets_wcguide()

    # Fallback to OSM if no results
    if not features:
        print("WC Guide returned no results, trying OSM...")
        features = download_toilets_osm()

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

    print(f"Wrote {len(features)} toilets to {output_path}")
    return output_path


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Lucerne toilet data")
    parser.add_argument("--output", "-o", type=Path, help="Output directory")
    parser.add_argument("--max-features", "-n", type=int, help="Maximum features")

    args = parser.parse_args()
    download_toilets(output_dir=args.output, max_features=args.max_features)


if __name__ == "__main__":
    main()
