#!/usr/bin/env python3
"""
Download bench data from Stadt Zürich Open Data Portal via WFS.

Data source: https://data.stadt-zuerich.ch/dataset/geo_sitzbankkataster_ogd
Format: GeoJSON (via WFS)
CRS: WGS84 (EPSG:4326)
License: CC0

~4,000-6,000 benches maintained by Grün Stadt Zürich and Tiefbauamt.
"""

import json
import requests
from pathlib import Path
from typing import Optional


# WFS endpoint for direct GeoJSON access
WFS_URL = "https://www.ogd.stadt-zuerich.ch/wfs/geoportal/Sitzbankkataster_OGD"
FEATURE_TYPE = "bankstandorte_ogd"  # lowercase as per WFS capabilities

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "raw"


def download_benches_wfs(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None
) -> Path:
    """
    Download bench GeoJSON via WFS.

    Args:
        output_dir: Directory to save file (default: data/raw)
        max_features: Limit number of features (for testing)

    Returns:
        Path to downloaded GeoJSON file
    """
    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "benches-wfs.geojson"

    # Build WFS request
    params = {
        "SERVICE": "WFS",
        "REQUEST": "GetFeature",
        "typename": FEATURE_TYPE,
        "outputFormat": "application/vnd.geo+json",  # Must match WFS capabilities
        "srsName": "EPSG:4326",
    }

    if max_features:
        params["count"] = str(max_features)

    print(f"Fetching benches from WFS...")
    print(f"URL: {WFS_URL}")
    if max_features:
        print(f"Limiting to {max_features} features")

    response = requests.get(WFS_URL, params=params, timeout=120)
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

        # Extract bench properties with sensible defaults
        standardized_features.append({
            "type": "Feature",
            "properties": {
                "id": str(props.get("OBJID") or props.get("OBJECTID") or f"bench_{i}"),
                "address": props.get("ADRESSE") or "Sitzbank",
                "model": props.get("SITZBANKMODELLE"),
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

    print(f"Wrote {len(standardized_features)} benches to {output_path}")
    return output_path


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Zurich bench data via WFS")
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

    download_benches_wfs(
        output_dir=args.output,
        max_features=args.max_features
    )


if __name__ == "__main__":
    main()
