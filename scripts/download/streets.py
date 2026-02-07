#!/usr/bin/env python3
"""
Download street centerline data from Stadt Zürich Open Data Portal via WFS.

Data source: https://data.stadt-zuerich.ch/dataset/geo_verkehrsachsensystem_stadt_zuerich
Format: GeoJSON (via WFS)
CRS: WGS84 (EPSG:4326)
License: CC0

Note: Streets are centerlines (LineString), not polygons.
The tile pipeline will buffer these to road width based on street type.
"""

import json
import requests
from pathlib import Path
from typing import Optional


# WFS endpoint for Verkehrsachsensystem (traffic axis system)
WFS_URL = "https://www.ogd.stadt-zuerich.ch/wfs/geoportal/Verkehrsachsensystem_Stadt_Zuerich"
FEATURE_TYPE = "vas_basis"

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "raw"

# Street type to width mapping (meters)
# Based on typical Swiss road widths
STREET_WIDTH_BY_TYPE = {
    # Major roads
    "Hauptstrasse": 12.0,
    "Hauptverkehrsstrasse": 12.0,
    "Verbindungsstrasse": 10.0,
    # Secondary roads
    "Quartierstrasse": 6.0,
    "Sammelstrasse": 8.0,
    "Erschliessungsstrasse": 6.0,
    # Minor roads
    "Wohnstrasse": 5.0,
    "Privatstrasse": 4.0,
    "Stichweg": 3.0,
    # Pedestrian/Bike
    "Fussgängerzone": 4.0,
    "Fussgaengerzone": 4.0,
    "Fussweg": 2.0,
    "Veloweg": 2.5,
    "Velowege": 2.5,
    # Default
    "default": 6.0,
}


def get_street_width(street_type: Optional[str]) -> float:
    """Get street width based on type classification.

    Args:
        street_type: Street type classification from WFS data

    Returns:
        Width in meters
    """
    if not street_type:
        return STREET_WIDTH_BY_TYPE["default"]

    # Try exact match first
    if street_type in STREET_WIDTH_BY_TYPE:
        return STREET_WIDTH_BY_TYPE[street_type]

    # Try partial match (street types often have suffixes)
    for type_key, width in STREET_WIDTH_BY_TYPE.items():
        if type_key.lower() in street_type.lower():
            return width

    return STREET_WIDTH_BY_TYPE["default"]


def download_streets_wfs(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None
) -> Path:
    """
    Download street GeoJSON via WFS.

    Args:
        output_dir: Directory to save file (default: data/raw)
        max_features: Limit number of features (for testing)

    Returns:
        Path to downloaded GeoJSON file
    """
    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "streets-wfs.geojson"

    # Build WFS request
    params = {
        "SERVICE": "WFS",
        "REQUEST": "GetFeature",
        "typename": FEATURE_TYPE,
        "outputFormat": "application/vnd.geo+json",
        "srsName": "EPSG:4326",
    }

    if max_features:
        params["count"] = str(max_features)

    print(f"Fetching streets from WFS...")
    print(f"URL: {WFS_URL}")
    if max_features:
        print(f"Limiting to {max_features} features")

    response = requests.get(WFS_URL, params=params, timeout=300)
    response.raise_for_status()

    data = response.json()
    features = data.get("features", [])
    print(f"Received {len(features)} features")

    # Standardize properties for our pipeline
    standardized_features = []
    for feature in features:
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})

        # Skip non-line geometries
        if geom.get("type") not in ("LineString", "MultiLineString"):
            continue

        # Extract street name and type
        street_name = props.get("strassenname") or props.get("name", "")
        street_type = props.get("strklassort") or props.get("kategorie", "")

        # Calculate width based on type
        width = get_street_width(street_type)

        standardized_features.append({
            "type": "Feature",
            "properties": {
                "id": props.get("objectid") or f"street_{len(standardized_features)}",
                "street_name": street_name,
                "street_type": street_type,
                "width": width,
                # Preserve original classification for reference
                "original_class": props.get("strklassort", ""),
            },
            "geometry": geom
        })

    output_data = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": "EPSG:4326"}
        },
        "features": standardized_features
    }

    with open(output_path, "w") as f:
        json.dump(output_data, f)

    print(f"Wrote {len(standardized_features)} streets to {output_path}")

    # Print summary by type
    type_counts = {}
    for feat in standardized_features:
        st = feat["properties"]["street_type"] or "unknown"
        type_counts[st] = type_counts.get(st, 0) + 1

    print("\nStreet types summary:")
    for st, count in sorted(type_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  {st}: {count}")

    return output_path


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Zurich street data via WFS")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output directory"
    )
    parser.add_argument(
        "--max-features", "-n",
        type=int,
        help="Maximum features to download (for testing)"
    )

    args = parser.parse_args()

    download_streets_wfs(
        output_dir=args.output,
        max_features=args.max_features
    )


if __name__ == "__main__":
    main()
