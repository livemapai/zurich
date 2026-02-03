#!/usr/bin/env python3
"""
Download building data from Stadt Zürich Open Data Portal via WFS.

Data source: https://data.stadt-zuerich.ch/dataset/geo_bauten___blockmodell
Format: GeoJSON (via WFS)
CRS: WGS84 (EPSG:4326)
License: CC0
"""

import json
import requests
from pathlib import Path
from typing import Optional


# WFS endpoint for direct GeoJSON access
WFS_URL = "https://www.ogd.stadt-zuerich.ch/wfs/geoportal/Bauten___Blockmodell"
FEATURE_TYPE = "bauten_blockmodell_2d"

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "raw"


def download_buildings_wfs(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None
) -> Path:
    """
    Download building GeoJSON via WFS.

    Args:
        output_dir: Directory to save file (default: data/raw)
        max_features: Limit number of features (for testing)

    Returns:
        Path to downloaded GeoJSON file
    """
    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "buildings-wfs.geojson"

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

    print(f"Fetching buildings from WFS...")
    print(f"URL: {WFS_URL}")
    if max_features:
        print(f"Limiting to {max_features} features")

    response = requests.get(WFS_URL, params=params)
    response.raise_for_status()

    data = response.json()
    features = data.get("features", [])
    print(f"Received {len(features)} features")

    # Standardize properties for our pipeline
    standardized_features = []
    for feature in features:
        props = feature.get("properties", {})

        # Extract height (relative height from ground to ridge)
        height = props.get("h_rel_first_boden") or props.get("h_rel_mean_boden") or 10.0

        standardized_features.append({
            "type": "Feature",
            "properties": {
                "id": props.get("gid") or f"building_{props.get('objectid', 0)}",
                "height": float(height),
                "egid": props.get("egid"),
                "art": props.get("art_txt"),
            },
            "geometry": feature["geometry"]
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

    print(f"Wrote {len(standardized_features)} buildings to {output_path}")
    return output_path


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Zurich building data via WFS")
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

    download_buildings_wfs(
        output_dir=args.output,
        max_features=args.max_features
    )


if __name__ == "__main__":
    main()
