#!/usr/bin/env python3
"""
Download public lighting data from Stadt Zürich Open Data Portal via WFS.

Data source: https://data.stadt-zuerich.ch/dataset/geo_oeffentliche_beleuchtung_der_stadt_zuerich
Format: GeoJSON (via WFS)
CRS: WGS84 (EPSG:4326)
License: CC0

~40,000 street lights with height and type information.
"""

import json
import requests
from pathlib import Path
from typing import Optional


# WFS endpoint for direct GeoJSON access
WFS_URL = "https://www.ogd.stadt-zuerich.ch/wfs/geoportal/Oeffentliche_Beleuchtung_der_Stadt_Zuerich"
FEATURE_TYPE = "ewz_brennstelle_p"  # "Brennstelle" = light source point

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "raw"


def download_lights_wfs(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None
) -> Path:
    """
    Download street light GeoJSON via WFS.

    Args:
        output_dir: Directory to save file (default: data/raw)
        max_features: Limit number of features (for testing)

    Returns:
        Path to downloaded GeoJSON file
    """
    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "lights-wfs.geojson"

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

    print(f"Fetching lights from WFS...")
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

        # Extract light properties with sensible defaults
        # Try various possible property names
        height = (
            props.get("hoehe") or
            props.get("masthoehe") or
            props.get("lichtpunkthoehe") or
            6.0  # Default 6m for street lights
        )

        # Power consumption if available
        power = props.get("leistung")
        if power is not None:
            try:
                power = float(power)
            except (ValueError, TypeError):
                power = None

        # Light/lamp type
        lamp_type = (
            props.get("leuchtentyp") or
            props.get("typ") or
            props.get("art")
        )

        standardized_features.append({
            "type": "Feature",
            "properties": {
                "id": str(props.get("objid") or props.get("id") or f"light_{i}"),
                "type": props.get("typ") or props.get("art") or "unknown",
                "height": float(height) if height else 6.0,
                "power": power,
                "lamp_type": lamp_type,
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

    print(f"Wrote {len(standardized_features)} lights to {output_path}")
    return output_path


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Zurich street light data via WFS")
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

    download_lights_wfs(
        output_dir=args.output,
        max_features=args.max_features
    )


if __name__ == "__main__":
    main()
