#!/usr/bin/env python3
"""
Download fountain data from Stadt Zürich Open Data Portal via WFS.

Data source: https://data.stadt-zuerich.ch/dataset/geo_brunnen
Format: GeoJSON (via WFS)
CRS: WGS84 (EPSG:4326)
License: CC0

~1,300 fountains with type, material, and artist information.
"""

import json
import requests
from pathlib import Path
from typing import Optional

# WFS endpoint for direct GeoJSON access
WFS_URL = "https://www.ogd.stadt-zuerich.ch/wfs/geoportal/Brunnen"
FEATURE_TYPE = "wvz_brunnen"

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "raw"


def download_fountains_wfs(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None
) -> Path:
    """
    Download fountain GeoJSON via WFS.

    Args:
        output_dir: Directory to save file (default: data/raw)
        max_features: Limit number of features (for testing)

    Returns:
        Path to downloaded GeoJSON file
    """
    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "fountains-wfs.geojson"

    # Build WFS request
    params = {
        "SERVICE": "WFS",
        "REQUEST": "GetFeature",
        "typename": FEATURE_TYPE,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
    }

    if max_features:
        params["count"] = str(max_features)

    print(f"Fetching fountains from WFS...")
    print(f"URL: {WFS_URL}")
    if max_features:
        print(f"Limiting to {max_features} features")

    response = requests.get(WFS_URL, params=params, timeout=60)
    response.raise_for_status()

    data = response.json()
    features = data.get("features", [])
    print(f"Received {len(features)} features")

    # Standardize properties for our pipeline
    standardized_features = []
    for i, feature in enumerate(features):
        props = feature.get("properties", {})
        geometry = feature.get("geometry")

        # Skip if no geometry
        if not geometry:
            continue

        # Extract fountain properties with sensible defaults
        standardized_features.append({
            "type": "Feature",
            "properties": {
                "id": str(props.get("brunnennummer") or props.get("objectid") or f"fountain_{i}"),
                "name": props.get("standort") or "Brunnen",
                "type": props.get("brunnenart"),
                "material": props.get("material_trog"),
                "artist": props.get("architekt_bildhauer"),
                "year": props.get("historisches_baujahr"),
                "photo": props.get("foto"),
                "quartier": props.get("quartier"),
                "water_type": props.get("wasserart"),
            },
            "geometry": geometry
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

    print(f"Wrote {len(standardized_features)} fountains to {output_path}")
    return output_path


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Zurich fountain data via WFS")
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

    download_fountains_wfs(
        output_dir=args.output,
        max_features=args.max_features
    )


if __name__ == "__main__":
    main()
