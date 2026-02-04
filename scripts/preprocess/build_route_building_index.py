#!/usr/bin/env python3
"""
Build spatial index mapping transit routes to nearby features.

This preprocessing step creates an index that enables instant queries like:
- "How many buildings does Tram 4 pass?"
- "Which tram passes the most benches?"
- "What route has the best fountain coverage?"

The index stores feature IDs (not full data) to keep file size small
and enable joining with source data at query time.

Performance:
- Preprocessing: ~30 seconds for 365 routes × all features
- Query time: <10ms after index is loaded
- Index size: ~3-4 MB

Usage:
    python -m scripts.preprocess.build_route_building_index

    # Custom buffer distance
    python -m scripts.preprocess.build_route_building_index --buffer 100

    # Verbose progress
    python -m scripts.preprocess.build_route_building_index -v
"""

import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple

try:
    from shapely.geometry import LineString, Polygon, Point, shape
    from shapely.strtree import STRtree
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False

from .extract_routes import extract_routes, get_route_type_name


# Default paths
DEFAULT_BUILDINGS_PATH = Path("public/data/zurich-buildings.geojson")
DEFAULT_TREES_PATH = Path("public/data/zurich-trees.geojson")
DEFAULT_BENCHES_PATH = Path("public/data/zurich-benches.geojson")
DEFAULT_FOUNTAINS_PATH = Path("public/data/zurich-fountains.geojson")
DEFAULT_TOILETS_PATH = Path("public/data/zurich-toilets.geojson")
DEFAULT_TRIPS_PATH = Path("public/data/zurich-tram-trips.json")
DEFAULT_OUTPUT_PATH = Path("public/data/route-building-index.json")

# Zurich-specific constants
METERS_PER_DEGREE_LAT = 111320
METERS_PER_DEGREE_LNG_ZURICH = 75500


def meters_to_degrees(meters: float, is_lat: bool = False) -> float:
    """Convert meters to approximate degrees at Zurich latitude."""
    if is_lat:
        return meters / METERS_PER_DEGREE_LAT
    else:
        return meters / METERS_PER_DEGREE_LNG_ZURICH


def path_length_km(path: List[List[float]]) -> float:
    """Calculate approximate path length in kilometers."""
    if len(path) < 2:
        return 0.0

    total = 0.0
    for i in range(len(path) - 1):
        lng1, lat1 = path[i][0], path[i][1]
        lng2, lat2 = path[i + 1][0], path[i + 1][1]

        R = 6371  # Earth radius in km
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lng2 - lng1)

        a = math.sin(delta_phi / 2) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        total += R * c

    return total


@dataclass
class FeatureLayer:
    """A loaded feature layer with spatial index."""
    name: str
    geometries: List[Any]
    ids: List[int]
    tree: Any  # STRtree
    count: int

    @classmethod
    def load(cls, path: Path, name: str) -> Optional["FeatureLayer"]:
        """Load a GeoJSON file and create spatial index."""
        if not path.exists():
            return None

        with open(path) as f:
            data = json.load(f)

        features = data.get("features", [])
        geometries = []
        ids = []

        for i, feature in enumerate(features):
            geom_dict = feature.get("geometry")
            if not geom_dict:
                continue

            try:
                geom = shape(geom_dict)
                if not geom.is_valid:
                    geom = geom.buffer(0)

                fid = feature.get("properties", {}).get("id", i)
                if isinstance(fid, str) and fid.isdigit():
                    fid = int(fid)
                elif not isinstance(fid, int):
                    fid = i

                geometries.append(geom)
                ids.append(fid)

            except Exception:
                continue

        if not geometries:
            return None

        tree = STRtree(geometries)

        return cls(
            name=name,
            geometries=geometries,
            ids=ids,
            tree=tree,
            count=len(geometries),
        )


@dataclass
class RouteIndex:
    """Index entry for a single route."""
    route_short_name: str
    route_id: str
    route_color: str
    route_type: int
    route_type_name: str
    headsigns: List[str]
    path_length_km: float
    path_bounds: Tuple[float, float, float, float]

    # Feature counts and IDs
    building_count: int = 0
    building_ids: List[int] = field(default_factory=list)
    tree_count: int = 0
    tree_ids: List[int] = field(default_factory=list)
    bench_count: int = 0
    bench_ids: List[int] = field(default_factory=list)
    fountain_count: int = 0
    fountain_ids: List[int] = field(default_factory=list)
    toilet_count: int = 0
    toilet_ids: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route_short_name": self.route_short_name,
            "route_id": self.route_id,
            "route_color": self.route_color,
            "route_type": self.route_type,
            "route_type_name": self.route_type_name,
            "headsigns": self.headsigns,
            "path_length_km": round(self.path_length_km, 2),
            "path_bounds": self.path_bounds,
            # Buildings
            "building_count": self.building_count,
            "building_ids": self.building_ids,
            # Trees
            "tree_count": self.tree_count,
            "tree_ids": self.tree_ids,
            # Amenities
            "bench_count": self.bench_count,
            "bench_ids": self.bench_ids,
            "fountain_count": self.fountain_count,
            "fountain_ids": self.fountain_ids,
            "toilet_count": self.toilet_count,
            "toilet_ids": self.toilet_ids,
        }


@dataclass
class SpatialIndex:
    """Complete spatial index for route-feature relationships."""
    routes: Dict[str, RouteIndex] = field(default_factory=dict)
    building_routes: Dict[int, List[str]] = field(default_factory=dict)
    bench_routes: Dict[int, List[str]] = field(default_factory=dict)
    fountain_routes: Dict[int, List[str]] = field(default_factory=dict)
    toilet_routes: Dict[int, List[str]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "routes": {name: idx.to_dict() for name, idx in self.routes.items()},
            "building_routes": {str(k): v for k, v in self.building_routes.items()},
            "bench_routes": {str(k): v for k, v in self.bench_routes.items()},
            "fountain_routes": {str(k): v for k, v in self.fountain_routes.items()},
            "toilet_routes": {str(k): v for k, v in self.toilet_routes.items()},
            "metadata": self.metadata,
        }


def query_features_in_buffer(
    buffered_line: Any,
    layer: FeatureLayer,
) -> List[int]:
    """Query features that intersect a buffered line."""
    candidate_indices = layer.tree.query(buffered_line)

    intersecting_ids = []
    for idx in candidate_indices:
        geom = layer.geometries[idx]
        if buffered_line.intersects(geom):
            intersecting_ids.append(layer.ids[idx])

    return sorted(intersecting_ids)


def process_route(
    route_name: str,
    route_info: Dict[str, Any],
    layers: Dict[str, FeatureLayer],
    buffer_m: float = 50,
) -> Optional[RouteIndex]:
    """Process a single route and find intersecting features."""
    path = route_info.get("path", [])
    if len(path) < 2:
        return None

    coords = [(p[0], p[1]) for p in path]
    line = LineString(coords)

    if not line.is_valid:
        return None

    minx, miny, maxx, maxy = line.bounds

    buffer_deg = meters_to_degrees(buffer_m, is_lat=False)
    buffered = line.buffer(buffer_deg)

    # Create base index
    index = RouteIndex(
        route_short_name=route_name,
        route_id=route_info.get("route_id", ""),
        route_color=route_info.get("route_color", ""),
        route_type=route_info.get("route_type", -1),
        route_type_name=get_route_type_name(route_info.get("route_type", -1)),
        headsigns=route_info.get("headsigns", []),
        path_length_km=path_length_km(path),
        path_bounds=(round(minx, 6), round(miny, 6), round(maxx, 6), round(maxy, 6)),
    )

    # Query each feature layer
    if "buildings" in layers:
        ids = query_features_in_buffer(buffered, layers["buildings"])
        index.building_count = len(ids)
        index.building_ids = ids

    if "trees" in layers:
        ids = query_features_in_buffer(buffered, layers["trees"])
        index.tree_count = len(ids)
        index.tree_ids = ids

    if "benches" in layers:
        ids = query_features_in_buffer(buffered, layers["benches"])
        index.bench_count = len(ids)
        index.bench_ids = ids

    if "fountains" in layers:
        ids = query_features_in_buffer(buffered, layers["fountains"])
        index.fountain_count = len(ids)
        index.fountain_ids = ids

    if "toilets" in layers:
        ids = query_features_in_buffer(buffered, layers["toilets"])
        index.toilet_count = len(ids)
        index.toilet_ids = ids

    return index


def build_index(
    trips_path: Path = DEFAULT_TRIPS_PATH,
    buildings_path: Path = DEFAULT_BUILDINGS_PATH,
    trees_path: Path = DEFAULT_TREES_PATH,
    benches_path: Path = DEFAULT_BENCHES_PATH,
    fountains_path: Path = DEFAULT_FOUNTAINS_PATH,
    toilets_path: Path = DEFAULT_TOILETS_PATH,
    buffer_m: float = 50,
    verbose: bool = False,
) -> SpatialIndex:
    """
    Build the complete route-feature spatial index.

    Args:
        trips_path: Path to GTFS trips JSON
        buildings_path: Path to buildings GeoJSON
        trees_path: Path to trees GeoJSON
        benches_path: Path to benches GeoJSON
        fountains_path: Path to fountains GeoJSON
        toilets_path: Path to toilets GeoJSON
        buffer_m: Buffer distance in meters (default: 50m)
        verbose: Print progress

    Returns:
        SpatialIndex with route→feature and feature→route mappings
    """
    if not SHAPELY_AVAILABLE:
        raise ImportError("shapely is required. Install with: pip install shapely")

    start_time = time.time()

    # Step 1: Extract routes
    if verbose:
        print("Step 1: Extracting routes from GTFS...")
    routes = extract_routes(trips_path)
    if verbose:
        print(f"  Found {len(routes)} unique routes")

    # Step 2: Load all feature layers
    if verbose:
        print("Step 2: Loading feature layers...")

    layers: Dict[str, FeatureLayer] = {}

    layer_paths = [
        ("buildings", buildings_path),
        ("trees", trees_path),
        ("benches", benches_path),
        ("fountains", fountains_path),
        ("toilets", toilets_path),
    ]

    for name, path in layer_paths:
        layer = FeatureLayer.load(path, name)
        if layer:
            layers[name] = layer
            if verbose:
                print(f"  {name}: {layer.count} features")
        elif verbose:
            print(f"  {name}: not found at {path}")

    # Step 3: Process each route
    if verbose:
        print(f"Step 3: Processing routes (buffer={buffer_m}m)...")

    index = SpatialIndex()

    # Reverse indexes
    building_routes: Dict[int, Set[str]] = defaultdict(set)
    bench_routes: Dict[int, Set[str]] = defaultdict(set)
    fountain_routes: Dict[int, Set[str]] = defaultdict(set)
    toilet_routes: Dict[int, Set[str]] = defaultdict(set)

    total = len(routes)
    processed = 0

    for route_name, route_info in routes.items():
        result = process_route(route_name, route_info, layers, buffer_m)

        if result:
            index.routes[route_name] = result

            # Build reverse indexes
            for bid in result.building_ids:
                building_routes[bid].add(route_name)
            for bid in result.bench_ids:
                bench_routes[bid].add(route_name)
            for bid in result.fountain_ids:
                fountain_routes[bid].add(route_name)
            for bid in result.toilet_ids:
                toilet_routes[bid].add(route_name)

        processed += 1
        if verbose and processed % 50 == 0:
            print(f"  Processed {processed}/{total} routes...")

    # Convert sets to sorted lists
    index.building_routes = {bid: sorted(r) for bid, r in building_routes.items()}
    index.bench_routes = {bid: sorted(r) for bid, r in bench_routes.items()}
    index.fountain_routes = {bid: sorted(r) for bid, r in fountain_routes.items()}
    index.toilet_routes = {bid: sorted(r) for bid, r in toilet_routes.items()}

    # Add metadata
    elapsed = time.time() - start_time
    index.metadata = {
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "buffer_m": buffer_m,
        "total_routes": len(index.routes),
        "total_buildings_indexed": len(index.building_routes),
        "total_benches_indexed": len(index.bench_routes),
        "total_fountains_indexed": len(index.fountain_routes),
        "total_toilets_indexed": len(index.toilet_routes),
        "feature_layers": {
            name: layer.count for name, layer in layers.items()
        },
        "source_files": {
            "trips": str(trips_path),
            "buildings": str(buildings_path),
            "trees": str(trees_path),
            "benches": str(benches_path),
            "fountains": str(fountains_path),
            "toilets": str(toilets_path),
        },
        "processing_time_sec": round(elapsed, 2),
    }

    if verbose:
        print(f"\nCompleted in {elapsed:.1f} seconds")
        print(f"  Routes indexed: {len(index.routes)}")
        print(f"  Buildings with route coverage: {len(index.building_routes)}")
        print(f"  Benches with route coverage: {len(index.bench_routes)}")
        print(f"  Fountains with route coverage: {len(index.fountain_routes)}")
        print(f"  Toilets with route coverage: {len(index.toilet_routes)}")

    return index


def main():
    """Build and save the route-feature index."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Build spatial index mapping transit routes to features"
    )
    parser.add_argument("--trips", type=Path, default=DEFAULT_TRIPS_PATH,
                        help="Path to GTFS trips JSON")
    parser.add_argument("--buildings", type=Path, default=DEFAULT_BUILDINGS_PATH,
                        help="Path to buildings GeoJSON")
    parser.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT_PATH,
                        help="Output path for index JSON")
    parser.add_argument("--buffer", type=float, default=50,
                        help="Buffer distance in meters (default: 50)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")
    parser.add_argument("--dry-run", action="store_true",
                        help="Build index but don't save")
    args = parser.parse_args()

    try:
        index = build_index(
            trips_path=args.trips,
            buildings_path=args.buildings,
            buffer_m=args.buffer,
            verbose=args.verbose,
        )

        if args.dry_run:
            print("\nDry run - not saving")
            print("\nTop 10 routes by building count:")
            sorted_routes = sorted(
                index.routes.values(),
                key=lambda r: r.building_count,
                reverse=True
            )
            for route in sorted_routes[:10]:
                print(f"  {route.route_short_name:6s}  "
                      f"{route.building_count:5d} buildings  "
                      f"{route.bench_count:3d} benches  "
                      f"{route.fountain_count:3d} fountains  "
                      f"{route.toilet_count:2d} toilets  "
                      f"({route.route_type_name})")

            print("\nTop 10 routes by bench count:")
            sorted_routes = sorted(
                index.routes.values(),
                key=lambda r: r.bench_count,
                reverse=True
            )
            for route in sorted_routes[:10]:
                print(f"  {route.route_short_name:6s}  "
                      f"{route.bench_count:3d} benches  "
                      f"{route.building_count:5d} buildings  "
                      f"({route.route_type_name})")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)

            with open(args.output, "w") as f:
                json.dump(index.to_dict(), f, indent=2)

            file_size_mb = args.output.stat().st_size / (1024 * 1024)
            print(f"\nSaved index to {args.output}")
            print(f"File size: {file_size_mb:.2f} MB")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except ImportError as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
