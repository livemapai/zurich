#!/usr/bin/env python3
"""
Download and process building data from Canton Lucerne Geodatenshop.

Data source: https://daten.geo.lu.ch/produkt/gebmomit_ds_v1
Format: ESRI FileGDB (manual download) or WFS (limited)
CRS: LV95 (EPSG:2056) → WGS84 (EPSG:4326)
License: Open Data Kanton Luzern

Buildings are LoD2 quality with detailed roof structures.

Usage:
    # Process pre-downloaded FileGDB
    python lucerne_buildings.py --input /path/to/gebmomit_ds_v1.gdb

    # Try WFS (may have feature limits)
    python lucerne_buildings.py --wfs

Note: FileGDB must be manually downloaded from:
    https://daten.geo.lu.ch/download/gebmomit_ds_v1
    Select "ESRI FileGDB" format, "Solids" variant
"""

import json
import warnings
from pathlib import Path
from typing import Optional

import numpy as np

# Suppress geopandas warnings about CRS
warnings.filterwarnings('ignore', message='.*CRS.*')

# Lucerne bounds in WGS84 (approximate city area)
LUCERNE_BOUNDS = {
    "min_lng": 8.20,
    "max_lng": 8.45,
    "min_lat": 46.95,
    "max_lat": 47.10,
}

# Lucerne bounds in LV95 (for BBOX filtering)
LUCERNE_BOUNDS_LV95 = {
    "min_e": 2655000,
    "max_e": 2680000,
    "min_n": 1200000,
    "max_n": 1225000,
}

# WFS endpoint (may have feature limits)
WFS_URL = "https://geo.lu.ch/wfs/gebmomit_ds_v1"
FEATURE_TYPE = "GEBMOMIT_V1_MP2"  # 3D MultiPatch buildings

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "public" / "data" / "lucerne"


def download_buildings_wfs(
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None,
    bbox: Optional[tuple] = None
) -> Path:
    """
    Download building data via WFS.

    Note: WFS may have feature count limits. For full dataset,
    use --input with a manually downloaded FileGDB.

    Args:
        output_dir: Directory to save file
        max_features: Limit number of features
        bbox: Bounding box (minE, minN, maxE, maxN) in LV95

    Returns:
        Path to output GeoJSON file
    """
    import requests

    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "lucerne-buildings.geojson"

    # Use default Lucerne bbox if not provided
    if bbox is None:
        bbox = (
            LUCERNE_BOUNDS_LV95["min_e"],
            LUCERNE_BOUNDS_LV95["min_n"],
            LUCERNE_BOUNDS_LV95["max_e"],
            LUCERNE_BOUNDS_LV95["max_n"],
        )

    # Build WFS request
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": FEATURE_TYPE,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",  # Request WGS84 directly
        "BBOX": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:2056",
    }

    if max_features:
        params["COUNT"] = str(max_features)

    print(f"Fetching Lucerne buildings from WFS...")
    print(f"URL: {WFS_URL}")
    print(f"BBOX: {bbox}")
    if max_features:
        print(f"Limiting to {max_features} features")

    try:
        response = requests.get(WFS_URL, params=params, timeout=300)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"WFS request failed: {e}")
        print("\nTo download full dataset, manually download from:")
        print("  https://daten.geo.lu.ch/download/gebmomit_ds_v1")
        print("Then run: python lucerne_buildings.py --input /path/to/file.gdb")
        raise

    features = data.get("features", [])
    print(f"Received {len(features)} features from WFS")

    # Process and standardize features
    standardized = _standardize_features(features, source="wfs")

    output_data = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": standardized
    }

    with open(output_path, "w") as f:
        json.dump(output_data, f)

    print(f"Wrote {len(standardized)} buildings to {output_path}")
    return output_path


def process_filegdb(
    input_path: Path,
    output_dir: Optional[Path] = None,
    max_features: Optional[int] = None,
    city_only: bool = True
) -> Path:
    """
    Process buildings from a downloaded FileGDB.

    The FileGDB contains 3D MultiPatch geometry. We extract:
    - 2D footprints from the geometry
    - Height from DACHRANDHOEHE - PROFHOEHE
    - Building type from ART

    Args:
        input_path: Path to .gdb directory
        output_dir: Output directory
        max_features: Limit features (for testing)
        city_only: Filter to city of Lucerne bounds

    Returns:
        Path to output GeoJSON
    """
    import geopandas as gpd
    from pyproj import Transformer
    from shapely.geometry import Polygon, MultiPolygon
    from shapely.ops import unary_union

    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "lucerne-buildings.geojson"

    print(f"Reading FileGDB: {input_path}")

    # List layers in the GDB
    import fiona
    layers = fiona.listlayers(str(input_path))
    print(f"Available layers: {layers}")

    # Find the building layer (usually contains 'GEBAEUDE' or 'MP')
    building_layer = None
    for layer in layers:
        if 'GEBAEUDE' in layer.upper() or 'MP' in layer.upper():
            building_layer = layer
            break

    if not building_layer:
        building_layer = layers[0]  # Use first layer as fallback
    print(f"Using layer: {building_layer}")

    # Read the GDB
    gdf = gpd.read_file(str(input_path), layer=building_layer)
    print(f"Read {len(gdf)} features")

    # Filter to city bounds if requested
    if city_only:
        # Create a bounding box in LV95
        from shapely.geometry import box
        city_bbox = box(
            LUCERNE_BOUNDS_LV95["min_e"],
            LUCERNE_BOUNDS_LV95["min_n"],
            LUCERNE_BOUNDS_LV95["max_e"],
            LUCERNE_BOUNDS_LV95["max_n"]
        )
        gdf = gdf[gdf.geometry.intersects(city_bbox)]
        print(f"Filtered to city bounds: {len(gdf)} features")

    # Limit features if requested
    if max_features:
        gdf = gdf.head(max_features)
        print(f"Limited to {len(gdf)} features")

    # Transform to WGS84
    transformer = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)

    features = []
    for idx, row in gdf.iterrows():
        geom = row.geometry

        # Extract 2D footprint from 3D geometry
        footprint = _extract_footprint(geom)
        if footprint is None or footprint.is_empty:
            continue

        # Transform coordinates
        try:
            transformed = _transform_geometry(footprint, transformer)
            if transformed is None or transformed.is_empty:
                continue
        except Exception as e:
            print(f"Warning: Failed to transform geometry {idx}: {e}")
            continue

        # Calculate height
        roof_height = row.get('DACHRANDHOEHE') or row.get('dachrandhoehe') or 0
        ground_height = row.get('PROFHOEHE') or row.get('profhoehe') or 0
        if isinstance(roof_height, (int, float)) and isinstance(ground_height, (int, float)):
            height = max(0, roof_height - ground_height)
        else:
            height = 10.0  # Default height

        # Build feature
        feature = {
            "type": "Feature",
            "properties": {
                "id": str(row.get('EGID') or row.get('egid') or f"building_{idx}"),
                "egid": row.get('EGID') or row.get('egid'),
                "height": round(float(height), 1),
                "elevation": round(float(ground_height), 1) if isinstance(ground_height, (int, float)) else 0,
                "art": row.get('ART') or row.get('art'),
                "source": "canton_lucerne_geodatenshop",
            },
            "geometry": transformed.__geo_interface__
        }
        features.append(feature)

    print(f"Processed {len(features)} buildings")

    output_data = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": features
    }

    with open(output_path, "w") as f:
        json.dump(output_data, f)

    print(f"Wrote {len(features)} buildings to {output_path}")
    return output_path


def _extract_footprint(geom):
    """Extract 2D footprint from a 3D geometry."""
    from shapely.geometry import Polygon, MultiPolygon
    from shapely.ops import unary_union

    if geom is None:
        return None

    # Handle MultiPolygon (typical for LoD2 buildings)
    if geom.geom_type == 'MultiPolygon':
        # Take the union of all polygons and get exterior
        try:
            union = unary_union(geom)
            if union.geom_type == 'Polygon':
                return Polygon([(p[0], p[1]) for p in union.exterior.coords])
            elif union.geom_type == 'MultiPolygon':
                # Take largest polygon
                largest = max(union.geoms, key=lambda p: p.area)
                return Polygon([(p[0], p[1]) for p in largest.exterior.coords])
        except Exception:
            pass

        # Fallback: use first polygon
        first_poly = geom.geoms[0]
        return Polygon([(p[0], p[1]) for p in first_poly.exterior.coords])

    elif geom.geom_type == 'Polygon':
        # Remove Z coordinate if present
        return Polygon([(p[0], p[1]) for p in geom.exterior.coords])

    elif geom.geom_type in ('MultiSurface', 'PolyhedralSurface', 'Solid'):
        # 3D geometry - try to get boundary
        try:
            boundary = geom.boundary
            return _extract_footprint(boundary)
        except Exception:
            return None

    return None


def _transform_geometry(geom, transformer):
    """Transform a shapely geometry from LV95 to WGS84."""
    from shapely.geometry import Polygon, MultiPolygon
    from shapely.ops import transform

    def transform_coords(x, y):
        return transformer.transform(x, y)

    return transform(transform_coords, geom)


def _standardize_features(features: list, source: str = "wfs") -> list:
    """Standardize feature properties from WFS response."""
    standardized = []

    for i, feature in enumerate(features):
        props = feature.get("properties", {})
        geom = feature.get("geometry")

        if not geom:
            continue

        # Extract height (various possible field names)
        roof_height = (
            props.get("DACHRANDHOEHE") or
            props.get("dachrandhoehe") or
            props.get("hoehe") or
            0
        )
        ground_height = (
            props.get("PROFHOEHE") or
            props.get("profhoehe") or
            0
        )

        if isinstance(roof_height, (int, float)) and isinstance(ground_height, (int, float)):
            height = max(0, roof_height - ground_height)
        else:
            height = 10.0

        standardized.append({
            "type": "Feature",
            "properties": {
                "id": str(props.get("EGID") or props.get("egid") or f"building_{i}"),
                "egid": props.get("EGID") or props.get("egid"),
                "height": round(float(height), 1),
                "elevation": round(float(ground_height), 1) if isinstance(ground_height, (int, float)) else 0,
                "art": props.get("ART") or props.get("art"),
                "source": source,
            },
            "geometry": geom
        })

    return standardized


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download/process Lucerne building data"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        help="Path to downloaded FileGDB (.gdb)"
    )
    parser.add_argument(
        "--wfs",
        action="store_true",
        help="Use WFS instead of FileGDB (may have limits)"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output directory"
    )
    parser.add_argument(
        "--max-features", "-n",
        type=int,
        help="Maximum features to process"
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Don't filter to city bounds"
    )

    args = parser.parse_args()

    if args.input:
        process_filegdb(
            input_path=args.input,
            output_dir=args.output,
            max_features=args.max_features,
            city_only=not args.no_filter
        )
    elif args.wfs:
        download_buildings_wfs(
            output_dir=args.output,
            max_features=args.max_features
        )
    else:
        print("Please specify --input <path.gdb> or --wfs")
        print("\nTo download the full dataset:")
        print("1. Visit https://daten.geo.lu.ch/download/gebmomit_ds_v1")
        print("2. Select 'ESRI FileGDB' format")
        print("3. Download and extract")
        print("4. Run: python lucerne_buildings.py --input /path/to/gebmomit_ds_v1.gdb")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
