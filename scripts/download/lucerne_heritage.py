#!/usr/bin/env python3
"""
Download heritage building data (Denkmalverzeichnis) from Canton Lucerne.

Data source: https://opendata.swiss/de/dataset/kantonales-denkmalverzeichnis-und-bauinventar1
Format: WFS or Shapefile
CRS: LV95 (EPSG:2056) → WGS84 (EPSG:4326)
License: Open Data Kanton Luzern

~960 protected monuments and historic buildings.

These buildings can be rendered with special styling to highlight
their heritage status in the 3D viewer.
"""

import json
from pathlib import Path
from typing import Optional

# WFS endpoint for heritage buildings
WFS_URL = "https://geo.lu.ch/wfs/bauinventar_oereb"
FEATURE_TYPES = [
    "kantonales_denkmalverzeichnis",
    "bauinventar",
]

# Lucerne bounds in LV95
LUCERNE_BOUNDS_LV95 = {
    "min_e": 2655000,
    "max_e": 2680000,
    "min_n": 1200000,
    "max_n": 1225000,
}

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "public" / "data" / "lucerne"


def download_heritage_wfs(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None,
    city_only: bool = True
) -> Path:
    """
    Download heritage building data via WFS.

    Args:
        output_dir: Output directory
        max_features: Limit features
        city_only: Filter to city bounds

    Returns:
        Path to output GeoJSON
    """
    import requests
    from pyproj import Transformer

    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "lucerne-heritage.geojson"

    transformer = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)

    all_features = []

    for feature_type in FEATURE_TYPES:
        params = {
            "SERVICE": "WFS",
            "VERSION": "2.0.0",
            "REQUEST": "GetFeature",
            "TYPENAMES": feature_type,
            "outputFormat": "application/json",
            "srsName": "EPSG:2056",  # Native CRS
        }

        if city_only:
            bbox = (
                LUCERNE_BOUNDS_LV95["min_e"],
                LUCERNE_BOUNDS_LV95["min_n"],
                LUCERNE_BOUNDS_LV95["max_e"],
                LUCERNE_BOUNDS_LV95["max_n"],
            )
            params["BBOX"] = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:2056"

        if max_features:
            params["COUNT"] = str(max_features)

        print(f"Fetching {feature_type} from WFS...")

        try:
            response = requests.get(WFS_URL, params=params, timeout=120)
            response.raise_for_status()
            data = response.json()
            features = data.get("features", [])
            print(f"  → Received {len(features)} features")
            all_features.extend(features)
        except Exception as e:
            print(f"  → Failed: {e}")
            continue

    print(f"Total heritage features: {len(all_features)}")

    # Standardize and transform features
    standardized = []
    for i, feature in enumerate(all_features):
        props = feature.get("properties", {})
        geom = feature.get("geometry")

        if not geom:
            continue

        # Transform geometry to WGS84
        transformed_geom = _transform_geometry(geom, transformer)
        if not transformed_geom:
            continue

        # Extract heritage properties
        standardized.append({
            "type": "Feature",
            "properties": {
                "id": str(props.get("id") or props.get("objectid") or f"heritage_{i}"),
                "name": props.get("bezeichnung") or props.get("name") or "Denkmal",
                "address": props.get("adresse") or props.get("standort"),
                "municipality": props.get("gemeinde"),
                "year_built": props.get("baujahr") or props.get("erstellungsjahr"),
                "protection_status": props.get("schutzstatus") or props.get("kategorie"),
                "is_heritage": True,
                "description": props.get("beschreibung") or props.get("bemerkung"),
                "source": "canton_lucerne_denkmalverzeichnis",
            },
            "geometry": transformed_geom
        })

    output_data = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": standardized
    }

    with open(output_path, "w") as f:
        json.dump(output_data, f)

    print(f"Wrote {len(standardized)} heritage buildings to {output_path}")
    return output_path


def _transform_geometry(geom: dict, transformer) -> dict:
    """Transform geometry coordinates from LV95 to WGS84."""
    from shapely.geometry import shape, mapping
    from shapely.ops import transform

    try:
        shapely_geom = shape(geom)

        def transform_coords(x, y):
            return transformer.transform(x, y)

        transformed = transform(transform_coords, shapely_geom)
        return mapping(transformed)
    except Exception:
        return None


def download_heritage_fallback(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None
) -> Path:
    """
    Fallback: Download heritage data from opendata.swiss.

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
    output_path = output_dir / "lucerne-heritage.geojson"

    print("Trying opendata.swiss for heritage data...")

    # Try to find the dataset
    api_url = "https://opendata.swiss/api/3/action/package_show"
    dataset_ids = [
        "kantonales-denkmalverzeichnis-und-bauinventar1",
        "denkmalverzeichnis-luzern",
    ]

    data = None
    for dataset_id in dataset_ids:
        try:
            response = requests.get(api_url, params={"id": dataset_id}, timeout=30)
            if response.ok:
                result = response.json().get("result", {})
                resources = result.get("resources", [])
                for resource in resources:
                    fmt = resource.get("format", "").lower()
                    if fmt in ("geojson", "json"):
                        data_url = resource.get("url")
                        try:
                            resp = requests.get(data_url, timeout=60)
                            if resp.ok:
                                data = resp.json()
                                break
                        except Exception:
                            continue
                if data:
                    break
        except Exception:
            continue

    if not data:
        print("Could not fetch heritage data from opendata.swiss")
        # Create empty file
        output_data = {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
            "features": []
        }
        with open(output_path, "w") as f:
            json.dump(output_data, f)
        return output_path

    # Process features
    features = data.get("features", [])
    transformer = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)

    standardized = []
    for i, feature in enumerate(features):
        if max_features and i >= max_features:
            break

        props = feature.get("properties", {})
        geom = feature.get("geometry")

        if not geom:
            continue

        # Transform if needed
        transformed_geom = _transform_geometry(geom, transformer)

        standardized.append({
            "type": "Feature",
            "properties": {
                "id": str(props.get("id") or f"heritage_{i}"),
                "name": props.get("bezeichnung") or props.get("name") or "Denkmal",
                "is_heritage": True,
            },
            "geometry": transformed_geom or geom
        })

    output_data = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": standardized
    }

    with open(output_path, "w") as f:
        json.dump(output_data, f)

    print(f"Wrote {len(standardized)} heritage buildings to {output_path}")
    return output_path


def download_heritage(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None,
    city_only: bool = True
) -> Path:
    """
    Download heritage building data.

    Tries WFS first, falls back to opendata.swiss.

    Args:
        output_dir: Output directory
        max_features: Limit features
        city_only: Filter to city bounds

    Returns:
        Path to output GeoJSON
    """
    try:
        return download_heritage_wfs(
            output_dir=output_dir,
            max_features=max_features,
            city_only=city_only
        )
    except Exception as e:
        print(f"WFS failed: {e}")
        return download_heritage_fallback(
            output_dir=output_dir,
            max_features=max_features
        )


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Lucerne heritage building data")
    parser.add_argument("--output", "-o", type=Path, help="Output directory")
    parser.add_argument("--max-features", "-n", type=int, help="Maximum features")
    parser.add_argument("--no-filter", action="store_true", help="Don't filter to city bounds")

    args = parser.parse_args()
    download_heritage(
        output_dir=args.output,
        max_features=args.max_features,
        city_only=not args.no_filter
    )


if __name__ == "__main__":
    main()
