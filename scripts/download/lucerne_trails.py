#!/usr/bin/env python3
"""
Download hiking trail (Wanderwege) data from Canton Lucerne.

Data source: https://daten.geo.lu.ch/produkt/wandrweg_ds_v1
Format: WFS or GPKG
CRS: LV95 (EPSG:2056) → WGS84 (EPSG:4326)
License: Open Data Kanton Luzern

~5,215 hiking trail segments with difficulty and surface info.

Trail types (Swiss hiking classification):
- Yellow: Regular hiking trails (Wanderwege)
- White-red-white: Mountain hiking trails (Bergwanderwege)
- White-blue-white: Alpine hiking trails (Alpinwanderwege)
"""

import json
from pathlib import Path
from typing import Optional

# WFS endpoint for hiking trails
WFS_URL = "https://geo.lu.ch/wfs/wandrweg_ds_v1"
FEATURE_TYPE = "wanderwege"

# Lucerne city area bounds in LV95 (extended for trails)
LUCERNE_BOUNDS_LV95 = {
    "min_e": 2650000,
    "max_e": 2690000,
    "min_n": 1195000,
    "max_n": 1230000,
}

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "public" / "data" / "lucerne"

# Trail color mapping
TRAIL_COLORS = {
    "gelb": "#ffcc00",
    "rot-weiss": "#ff0000",
    "blau-weiss": "#0066cc",
    "yellow": "#ffcc00",
    "red-white": "#ff0000",
    "blue-white": "#0066cc",
}


def download_trails_wfs(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None,
    bbox: Optional[tuple] = None
) -> Path:
    """
    Download hiking trail data via WFS.

    Args:
        output_dir: Output directory
        max_features: Limit features
        bbox: Bounding box (minE, minN, maxE, maxN) in LV95

    Returns:
        Path to output GeoJSON
    """
    import requests
    from pyproj import Transformer

    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "lucerne-trails.geojson"

    if bbox is None:
        bbox = (
            LUCERNE_BOUNDS_LV95["min_e"],
            LUCERNE_BOUNDS_LV95["min_n"],
            LUCERNE_BOUNDS_LV95["max_e"],
            LUCERNE_BOUNDS_LV95["max_n"],
        )

    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": FEATURE_TYPE,
        "outputFormat": "application/json",
        "srsName": "EPSG:2056",
        "BBOX": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:2056",
    }

    if max_features:
        params["COUNT"] = str(max_features)

    print(f"Fetching hiking trails from WFS...")
    print(f"URL: {WFS_URL}")
    print(f"BBOX: {bbox}")

    try:
        response = requests.get(WFS_URL, params=params, timeout=120)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"WFS request failed: {e}")
        # Create empty file
        output_data = {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
            "features": []
        }
        with open(output_path, "w") as f:
            json.dump(output_data, f)
        return output_path

    features = data.get("features", [])
    print(f"Received {len(features)} trail segments")

    # Transform to WGS84
    transformer = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)

    standardized = []
    for i, feature in enumerate(features):
        props = feature.get("properties", {})
        geom = feature.get("geometry")

        if not geom:
            continue

        # Transform geometry
        transformed_geom = _transform_geometry(geom, transformer)
        if not transformed_geom:
            continue

        # Determine trail type and color
        trail_type = (
            props.get("wanderwegtyp") or
            props.get("typ") or
            props.get("kategorie") or
            "wanderweg"
        ).lower()

        color = TRAIL_COLORS.get(trail_type, "#ffcc00")

        # Determine difficulty
        if "alpin" in trail_type or "blau" in trail_type:
            difficulty = "alpine"
        elif "berg" in trail_type or "rot" in trail_type:
            difficulty = "mountain"
        else:
            difficulty = "hiking"

        standardized.append({
            "type": "Feature",
            "properties": {
                "id": str(props.get("id") or props.get("objectid") or f"trail_{i}"),
                "name": props.get("name") or props.get("bezeichnung"),
                "trail_type": trail_type,
                "difficulty": difficulty,
                "surface": props.get("belag") or props.get("oberflaeche"),
                "length_m": props.get("laenge") or props.get("length"),
                "color": color,
                "municipality": props.get("gemeinde"),
                "source": "canton_lucerne_wanderwege",
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

    print(f"Wrote {len(standardized)} trail segments to {output_path}")
    return output_path


def _transform_geometry(geom: dict, transformer) -> dict:
    """Transform geometry coordinates from LV95 to WGS84."""
    geom_type = geom.get("type")
    coords = geom.get("coordinates", [])

    if geom_type == "LineString":
        transformed_coords = [
            list(transformer.transform(c[0], c[1]))
            for c in coords
        ]
        return {"type": "LineString", "coordinates": transformed_coords}

    elif geom_type == "MultiLineString":
        transformed_coords = [
            [list(transformer.transform(c[0], c[1])) for c in line]
            for line in coords
        ]
        return {"type": "MultiLineString", "coordinates": transformed_coords}

    elif geom_type == "Point":
        lng, lat = transformer.transform(coords[0], coords[1])
        return {"type": "Point", "coordinates": [lng, lat]}

    else:
        # For complex geometries, use shapely
        try:
            from shapely.geometry import shape, mapping
            from shapely.ops import transform

            shapely_geom = shape(geom)

            def transform_coords(x, y):
                return transformer.transform(x, y)

            transformed = transform(transform_coords, shapely_geom)
            return mapping(transformed)
        except Exception:
            return None


def download_trails(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None
) -> Path:
    """
    Download hiking trail data.

    Args:
        output_dir: Output directory
        max_features: Limit features

    Returns:
        Path to output GeoJSON
    """
    return download_trails_wfs(
        output_dir=output_dir,
        max_features=max_features
    )


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Lucerne hiking trail data")
    parser.add_argument("--output", "-o", type=Path, help="Output directory")
    parser.add_argument("--max-features", "-n", type=int, help="Maximum features")

    args = parser.parse_args()
    download_trails(output_dir=args.output, max_features=args.max_features)


if __name__ == "__main__":
    main()
