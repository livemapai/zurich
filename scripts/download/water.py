#!/usr/bin/env python3
"""
Download water body data from Canton Zürich Open Data Portal via WFS.

Data source: Canton Zürich Geodaten WFS (OGDZHWFS)
Format: GeoJSON (via WFS)
CRS: WGS84 (EPSG:4326)
License: Open Government Data

Water bodies include:
- Lakes (WB_STEHGEWAESSER_F): Zürichsee, smaller lakes/ponds
- Rivers/Streams (WB_FLIESSGEWAESSER_L): Limmat, Sihl, smaller streams

Note: Rivers are LineStrings (centerlines) that need buffering.
Lakes are Polygons that can be used directly.
"""

import json
import requests
from pathlib import Path
from typing import Optional


# Canton Zürich WFS endpoint
WFS_URL = "https://maps.zh.ch/wfs/OGDZHWFS"

# Feature types
LAKES_FEATURE_TYPE = "WB_STEHGEWAESSER_F"  # Standing water (polygons)
RIVERS_FEATURE_TYPE = "WB_FLIESSGEWAESSER_L"  # Flowing water (lines)

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "raw"

# Default river widths by size classification
RIVER_WIDTH_BY_CLASS = {
    # Major rivers
    "1": 30.0,  # Limmat, Sihl main
    "2": 20.0,  # Major tributaries
    "3": 10.0,  # Medium rivers
    "4": 5.0,   # Small rivers
    "5": 3.0,   # Streams
    "6": 2.0,   # Small streams
    # Default
    "default": 5.0,
}


def get_river_width(size_class: Optional[str], name: Optional[str] = None) -> float:
    """Get river width based on size classification or name.

    Args:
        size_class: River size classification from WFS data
        name: River name (for special handling of known rivers)

    Returns:
        Width in meters
    """
    # Special handling for known major rivers
    if name:
        name_lower = name.lower()
        if "limmat" in name_lower:
            return 35.0
        elif "sihl" in name_lower:
            return 25.0
        elif "zürichsee" in name_lower or "zurichsee" in name_lower:
            return 50.0  # Lake edges

    if size_class and size_class in RIVER_WIDTH_BY_CLASS:
        return RIVER_WIDTH_BY_CLASS[size_class]

    return RIVER_WIDTH_BY_CLASS["default"]


def download_water_wfs(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None,
    include_lakes: bool = True,
    include_rivers: bool = True,
) -> Path:
    """
    Download water body GeoJSON via WFS.

    Args:
        output_dir: Directory to save file (default: data/raw)
        max_features: Limit number of features per type (for testing)
        include_lakes: Download lake polygons
        include_rivers: Download river linestrings

    Returns:
        Path to downloaded GeoJSON file
    """
    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "water-bodies.geojson"

    all_features = []

    # Download lakes (polygons)
    if include_lakes:
        print(f"Fetching lakes from WFS...")
        lake_features = _fetch_wfs_features(
            LAKES_FEATURE_TYPE,
            max_features,
            "lake"
        )
        all_features.extend(lake_features)
        print(f"  Received {len(lake_features)} lake features")

    # Download rivers (linestrings)
    if include_rivers:
        print(f"Fetching rivers from WFS...")
        river_features = _fetch_wfs_features(
            RIVERS_FEATURE_TYPE,
            max_features,
            "river"
        )
        all_features.extend(river_features)
        print(f"  Received {len(river_features)} river features")

    output_data = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": "EPSG:4326"}
        },
        "features": all_features
    }

    with open(output_path, "w") as f:
        json.dump(output_data, f)

    print(f"\nWrote {len(all_features)} water bodies to {output_path}")

    # Print summary by type
    type_counts = {"lake": 0, "river": 0, "stream": 0, "pond": 0}
    for feat in all_features:
        wt = feat["properties"]["water_type"]
        type_counts[wt] = type_counts.get(wt, 0) + 1

    print("\nWater types summary:")
    for wt, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        if count > 0:
            print(f"  {wt}: {count}")

    return output_path


def _fetch_wfs_features(
    feature_type: str,
    max_features: Optional[int],
    water_category: str,
) -> list:
    """Fetch features from WFS endpoint.

    Args:
        feature_type: WFS feature type name
        max_features: Max features to fetch
        water_category: Category for standardization (lake/river)

    Returns:
        List of standardized GeoJSON features
    """
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": feature_type,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
    }

    if max_features:
        params["count"] = str(max_features)

    try:
        response = requests.get(WFS_URL, params=params, timeout=300)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"  Warning: Failed to fetch {feature_type}: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"  Warning: Invalid JSON response for {feature_type}: {e}")
        return []

    features = data.get("features", [])
    standardized = []

    for feature in features:
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})

        if not geom:
            continue

        geom_type = geom.get("type", "")

        # Determine water type based on geometry and properties
        if water_category == "lake":
            water_type = _classify_lake(props, geom)
        else:
            water_type = _classify_river(props, geom)

        # Get name
        name = (
            props.get("name") or
            props.get("gewaessername") or
            props.get("bezeichnung") or
            ""
        )

        # Get width (for rivers/streams)
        if geom_type in ("LineString", "MultiLineString"):
            size_class = props.get("groessenklasse") or props.get("klasse")
            width = get_river_width(size_class, name)
        else:
            width = 0  # Polygons don't need width

        standardized.append({
            "type": "Feature",
            "properties": {
                "id": props.get("objectid") or f"water_{len(standardized)}",
                "name": name,
                "water_type": water_type,
                "width": width,
                # Keep original geometry type for pipeline
                "geometry_type": geom_type,
            },
            "geometry": geom
        })

    return standardized


def _classify_lake(props: dict, geom: dict) -> str:
    """Classify standing water body type.

    Args:
        props: Feature properties
        geom: Feature geometry

    Returns:
        Water type: "lake" or "pond"
    """
    name = (props.get("name") or props.get("gewaessername") or "").lower()

    # Known major lakes
    if "zürichsee" in name or "zurichsee" in name:
        return "lake"
    if "greifensee" in name or "pfäffikersee" in name:
        return "lake"

    # Check area if available (rough heuristic)
    # Large = lake, small = pond
    coords = geom.get("coordinates", [])
    if geom.get("type") == "Polygon" and len(coords) > 0:
        # Very rough area estimate
        ring = coords[0] if len(coords[0]) > 0 else []
        if len(ring) > 20:  # Complex polygon = likely larger
            return "lake"

    return "pond"


def _classify_river(props: dict, geom: dict) -> str:
    """Classify flowing water body type.

    Args:
        props: Feature properties
        geom: Feature geometry

    Returns:
        Water type: "river" or "stream"
    """
    name = (props.get("name") or props.get("gewaessername") or "").lower()

    # Known major rivers
    if "limmat" in name or "sihl" in name:
        return "river"
    if "glatt" in name or "töss" in name:
        return "river"

    # Check size class
    size_class = props.get("groessenklasse") or props.get("klasse") or ""
    if size_class in ("1", "2", "3"):
        return "river"

    return "stream"


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Zurich water body data via WFS")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output directory"
    )
    parser.add_argument(
        "--max-features", "-n",
        type=int,
        help="Maximum features per type to download (for testing)"
    )
    parser.add_argument(
        "--lakes-only",
        action="store_true",
        help="Only download lakes (no rivers)"
    )
    parser.add_argument(
        "--rivers-only",
        action="store_true",
        help="Only download rivers (no lakes)"
    )

    args = parser.parse_args()

    include_lakes = not args.rivers_only
    include_rivers = not args.lakes_only

    download_water_wfs(
        output_dir=args.output,
        max_features=args.max_features,
        include_lakes=include_lakes,
        include_rivers=include_rivers,
    )


if __name__ == "__main__":
    main()
