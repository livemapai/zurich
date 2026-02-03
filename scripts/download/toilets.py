#!/usr/bin/env python3
"""
Download public toilet (Züri WC) data from Stadt Zürich Open Data Portal via WFS.

Data source: https://data.stadt-zuerich.ch/dataset/geo_zueri_wc
Format: GeoJSON (via WFS)
CRS: WGS84 (EPSG:4326)
License: CC0

~200 public toilets maintained by the city of Zurich.
"""

import json
import requests
from pathlib import Path
from typing import Optional


WFS_URL = "https://www.ogd.stadt-zuerich.ch/wfs/geoportal/Zueri_WC"
FEATURE_TYPE = "poi_zueriwc_view"

OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "raw"


def download_toilets_wfs(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None
) -> Path:
    """Download public toilet GeoJSON via WFS."""
    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "toilets-wfs.geojson"

    params = {
        "SERVICE": "WFS",
        "REQUEST": "GetFeature",
        "typename": FEATURE_TYPE,
        "outputFormat": "application/vnd.geo+json",
        "srsName": "EPSG:4326",
    }

    if max_features:
        params["count"] = str(max_features)

    print(f"Fetching toilets from WFS...")
    print(f"URL: {WFS_URL}")
    if max_features:
        print(f"Limiting to {max_features} features")

    response = requests.get(WFS_URL, params=params, timeout=120)
    response.raise_for_status()

    data = response.json()
    features = data.get("features", [])
    print(f"Received {len(features)} features")

    standardized_features = []
    for i, feature in enumerate(features):
        props = feature.get("properties", {})
        geometry = feature.get("geometry")

        if not geometry:
            continue

        standardized_features.append({
            "type": "Feature",
            "properties": {
                "id": str(props.get("objectid") or f"toilet_{i}"),
                "name": props.get("name") or "Züri WC",
                "address": props.get("adresse") or "",
                "category": props.get("kategorie") or "WC",
                "hours": props.get("oeffnungsz") or "",
                "fee": props.get("gebuehren") or "",
                "accessible": "rollstuhl" in (props.get("kategorie") or "").lower(),
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

    print(f"Wrote {len(standardized_features)} toilets to {output_path}")
    return output_path


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Zurich public toilet data via WFS")
    parser.add_argument("--output", "-o", type=Path, help="Output directory")
    parser.add_argument("--max-features", "-n", type=int, help="Maximum features to download")

    args = parser.parse_args()
    download_toilets_wfs(output_dir=args.output, max_features=args.max_features)


if __name__ == "__main__":
    main()
