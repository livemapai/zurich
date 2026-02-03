#!/usr/bin/env python3
"""
Download tree data from Stadt Zürich Open Data Portal via WFS.

Data source: https://data.stadt-zuerich.ch/dataset/geo_baumkataster
Format: GeoJSON (via WFS)
CRS: WGS84 (EPSG:4326)
License: CC0

~80,000 trees with species, height, and crown diameter.
"""

import json
import requests
from pathlib import Path
from typing import Optional


# WFS endpoint for direct GeoJSON access
WFS_URL = "https://www.ogd.stadt-zuerich.ch/wfs/geoportal/Baumkataster"
FEATURE_TYPE = "baumkataster_baumstandorte"

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "raw"


def download_trees_wfs(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None
) -> Path:
    """
    Download tree GeoJSON via WFS.

    Args:
        output_dir: Directory to save file (default: data/raw)
        max_features: Limit number of features (for testing)

    Returns:
        Path to downloaded GeoJSON file
    """
    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "trees-wfs.geojson"

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

    print(f"Fetching trees from WFS...")
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
    for i, feature in enumerate(features):
        props = feature.get("properties", {})
        geometry = feature.get("geometry")

        # Skip if no geometry
        if not geometry:
            continue

        # Extract tree properties with sensible defaults
        height = props.get("baumhoehe") or props.get("hoehe") or 10.0
        crown_diameter = props.get("kronendurchmesser") or 5.0
        trunk_diameter = props.get("stammdurchmesser") or 0.3

        # Try to get species info (varies by dataset version)
        species = (
            props.get("baumgattunglat") or
            props.get("baumnamelat") or
            props.get("baumart_lat")
        )
        species_de = (
            props.get("baumgattung") or
            props.get("baumname") or
            props.get("baumart")
        )

        standardized_features.append({
            "type": "Feature",
            "properties": {
                "id": props.get("baum_id") or props.get("objid") or f"tree_{i}",
                "species": species,
                "species_de": species_de,
                "height": float(height) if height else 10.0,
                "crown_diameter": float(crown_diameter) if crown_diameter else 5.0,
                "trunk_diameter": float(trunk_diameter) if trunk_diameter else 0.3,
                "year_planted": props.get("pflanzjahr"),
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

    print(f"Wrote {len(standardized_features)} trees to {output_path}")
    return output_path


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Zurich tree data via WFS")
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

    download_trees_wfs(
        output_dir=args.output,
        max_features=args.max_features
    )


if __name__ == "__main__":
    main()
