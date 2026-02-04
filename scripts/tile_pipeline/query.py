"""
Spatial queries for the Zurich 3D project.

Provides shadow and amenity queries using the existing tile pipeline
infrastructure (scene_builder, raytracer). Enables questions like:
- "Will my balcony get sun at 4pm?"
- "Find the nearest bench"
- "What's the shadow timeline for this spot?"

Uses the existing ray tracing infrastructure for accurate shadow computation
against 65k buildings and 80k trees.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import json

import numpy as np

from .raytracer import SunPosition, TileRaytracer, RayTracerConfig
from .scene_builder import SceneBuilder, SceneBounds
from .sources.vector import VectorSource, Feature


# Default data paths
DEFAULT_BUILDINGS_PATH = Path("public/data/zurich-buildings.geojson")
DEFAULT_TREES_PATH = Path("public/data/zurich-trees.geojson")
DEFAULT_BENCHES_PATH = Path("public/data/zurich-benches.geojson")
DEFAULT_FOUNTAINS_PATH = Path("public/data/zurich-fountains.geojson")
DEFAULT_TOILETS_PATH = Path("public/data/zurich-toilets.geojson")

# Zurich coordinates for sun calculations
ZURICH_LAT = 47.376
ZURICH_LNG = 8.54


@dataclass
class ShadowResult:
    """Result of a shadow query at a single 3D point."""

    latitude: float
    longitude: float
    time: datetime
    shadow: float  # 0.0 = full sun, 1.0 = full shade
    height: float = 1.7  # Height above ground in meters
    source: Optional[str] = None  # 'building', 'tree', or None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "time": self.time.isoformat(),
            "shadow": self.shadow,
            "height": self.height,
            "source": self.source,
        }


@dataclass
class AmenityResult:
    """Result of an amenity search."""

    type: str  # 'bench', 'fountain', 'toilet'
    latitude: float
    longitude: float
    distance_m: float
    properties: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "distance_m": self.distance_m,
            "properties": self.properties,
        }


def _build_local_scene(
    lat: float,
    lng: float,
    radius_deg: float = 0.002,  # ~200m
    buildings_path: Path = DEFAULT_BUILDINGS_PATH,
    trees_path: Path = DEFAULT_TREES_PATH,
    include_trees: bool = True,
) -> tuple:
    """Build a local 3D scene around a query point.

    Args:
        lat: Latitude (WGS84)
        lng: Longitude (WGS84)
        radius_deg: Query radius in degrees (~0.002 = ~200m)
        buildings_path: Path to buildings GeoJSON
        trees_path: Path to trees GeoJSON
        include_trees: Whether to include trees in scene

    Returns:
        Tuple of (mesh, scene_bounds)
    """
    # Create bounds around query point
    bounds = (
        lng - radius_deg,  # west
        lat - radius_deg,  # south
        lng + radius_deg,  # east
        lat + radius_deg,  # north
    )

    # Load buildings in bounds
    buildings_source = VectorSource(buildings_path, height_field="height")
    buildings = list(buildings_source.query(bounds, min_height=1))

    # Load trees if requested
    trees = []
    if include_trees and trees_path.exists():
        trees_source = VectorSource(trees_path, height_field="estimated_height")
        trees = list(trees_source.query(bounds))

    # Build scene
    builder = SceneBuilder(bounds, image_size=256)  # Small for point queries
    builder.add_ground_plane(z=0)

    if buildings:
        builder.add_buildings(buildings)

    if trees:
        builder.add_trees(trees)

    mesh = builder.build()

    return mesh, builder.bounds


def get_shadow_at(
    lat: float,
    lng: float,
    time: datetime,
    height: float = 1.7,  # Height above ground in meters (default: standing person)
    buildings_path: Path = DEFAULT_BUILDINGS_PATH,
    trees_path: Path = DEFAULT_TREES_PATH,
) -> ShadowResult:
    """
    Get shadow intensity at a 3D point for a given time.

    Uses ray tracing against building and tree geometry.
    Height is CRITICAL for balcony queries!

    Args:
        lat: Latitude (WGS84)
        lng: Longitude (WGS84)
        time: Datetime for sun position calculation (must be timezone-aware or UTC)
        height: Height above ground in meters (e.g., 15m for 5th floor balcony)
        buildings_path: Path to buildings GeoJSON
        trees_path: Path to trees GeoJSON

    Returns:
        ShadowResult with shadow intensity 0-1

    Examples:
        # Ground level (standing person)
        get_shadow_at(47.376, 8.54, time, height=1.7)

        # 3rd floor balcony (~9m)
        get_shadow_at(47.376, 8.54, time, height=9.0)

        # 10th floor (~30m) - probably sunny!
        get_shadow_at(47.376, 8.54, time, height=30.0)
    """
    # 1. Calculate sun position
    sun = SunPosition.from_datetime(lat, lng, time)

    # Check if sun is below horizon
    if sun.altitude <= 0:
        return ShadowResult(
            latitude=lat,
            longitude=lng,
            time=time,
            height=height,
            shadow=1.0,  # Full shadow (night)
            source="night",
        )

    # 2. Build local scene (only trees below query height matter)
    include_trees = height < 25  # Trees typically < 20m
    mesh, scene_bounds = _build_local_scene(
        lat, lng,
        buildings_path=buildings_path,
        trees_path=trees_path,
        include_trees=include_trees,
    )

    # 3. Set up ray tracer for single-point query
    config = RayTracerConfig(
        image_size=4,  # Tiny grid, we only need one point
        samples_per_pixel=1,
        ray_offset=0.05,
    )

    # 4. Convert query point to local coordinates
    local_x, local_y = scene_bounds.wgs84_to_local(lng, lat)

    # 5. Cast single ray from query point towards sun
    # Create ray origin at query position and height
    ray_origin = np.array([[local_x, local_y, height]])
    ray_direction = sun.ray_direction

    # Create intersector
    import trimesh
    try:
        intersector = trimesh.ray.ray_pyembree.RayMeshIntersector(mesh)
    except (ImportError, AttributeError):
        intersector = trimesh.ray.ray_triangle.RayMeshIntersector(mesh)

    # Cast ray
    directions = np.array([ray_direction / np.linalg.norm(ray_direction)])
    hits = intersector.intersects_any(ray_origin, directions)

    shadow = 1.0 if hits[0] else 0.0

    return ShadowResult(
        latitude=lat,
        longitude=lng,
        time=time,
        height=height,
        shadow=shadow,
        source="building" if shadow > 0 else None,
    )


def get_shadow_timeline(
    lat: float,
    lng: float,
    date: datetime,
    height: float = 1.7,
    interval_minutes: int = 60,
    start_hour: int = 6,
    end_hour: int = 20,
    buildings_path: Path = DEFAULT_BUILDINGS_PATH,
    trees_path: Path = DEFAULT_TREES_PATH,
) -> List[ShadowResult]:
    """
    Get shadow timeline for a point throughout a day.

    Efficient implementation that builds the scene once and reuses it
    for all time samples.

    Args:
        lat: Latitude (WGS84)
        lng: Longitude (WGS84)
        date: Date for timeline (time component ignored)
        height: Height above ground in meters
        interval_minutes: Minutes between samples (default: 60)
        start_hour: Start hour (default: 6)
        end_hour: End hour (default: 20)
        buildings_path: Path to buildings GeoJSON
        trees_path: Path to trees GeoJSON

    Returns:
        List of ShadowResult for each time point
    """
    # Build scene once
    include_trees = height < 25
    mesh, scene_bounds = _build_local_scene(
        lat, lng,
        buildings_path=buildings_path,
        trees_path=trees_path,
        include_trees=include_trees,
    )

    # Convert query point to local coordinates
    local_x, local_y = scene_bounds.wgs84_to_local(lng, lat)
    ray_origin = np.array([[local_x, local_y, height]])

    # Create intersector once
    import trimesh
    try:
        intersector = trimesh.ray.ray_pyembree.RayMeshIntersector(mesh)
    except (ImportError, AttributeError):
        intersector = trimesh.ray.ray_triangle.RayMeshIntersector(mesh)

    results = []

    # Sample throughout the day
    for hour in range(start_hour, end_hour + 1):
        for minute in range(0, 60, interval_minutes):
            if hour == end_hour and minute > 0:
                break

            time = date.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # Calculate sun position
            sun = SunPosition.from_datetime(lat, lng, time)

            # Check if sun is below horizon
            if sun.altitude <= 0:
                results.append(ShadowResult(
                    latitude=lat,
                    longitude=lng,
                    time=time,
                    height=height,
                    shadow=1.0,
                    source="night",
                ))
                continue

            # Cast ray
            ray_direction = sun.ray_direction / np.linalg.norm(sun.ray_direction)
            directions = np.array([ray_direction])
            hits = intersector.intersects_any(ray_origin, directions)

            shadow = 1.0 if hits[0] else 0.0

            results.append(ShadowResult(
                latitude=lat,
                longitude=lng,
                time=time,
                height=height,
                shadow=shadow,
                source="building" if shadow > 0 else None,
            ))

    return results


def get_balcony_sun_exposure(
    lat: float,
    lng: float,
    floor: int,  # Floor number (0 = ground, 1 = first floor, etc.)
    date: datetime,
    floor_height: float = 3.0,  # Typical floor height in meters
    buildings_path: Path = DEFAULT_BUILDINGS_PATH,
    trees_path: Path = DEFAULT_TREES_PATH,
) -> Dict[str, Any]:
    """
    Calculate sun exposure for a balcony throughout the day.

    This is the "Will my balcony get sun?" function.

    Args:
        lat: Latitude
        lng: Longitude
        floor: Floor number (0 = ground floor)
        date: Date for calculation
        floor_height: Height per floor in meters (default: 3m)
        buildings_path: Path to buildings GeoJSON
        trees_path: Path to trees GeoJSON

    Returns:
        Dictionary with sun exposure analysis:
        - total_sun_hours: Total hours of direct sun
        - sunny_periods: List of (start_time, end_time) periods
        - best_time: Time with most direct sun
        - shadow_sources: What's blocking the sun
    """
    # Calculate balcony height
    balcony_height = (floor * floor_height) + 1.5  # +1.5m for railing/standing

    # Get timeline with 30-minute intervals
    results = get_shadow_timeline(
        lat, lng, date,
        height=balcony_height,
        interval_minutes=30,
        buildings_path=buildings_path,
        trees_path=trees_path,
    )

    # Analyze results
    sunny_samples = [r for r in results if r.shadow < 0.5]
    total_sun_hours = len(sunny_samples) * 0.5  # Each sample is 30 min

    # Find continuous sunny periods
    sunny_periods = []
    current_period_start = None

    for r in results:
        if r.shadow < 0.5:  # Sunny
            if current_period_start is None:
                current_period_start = r.time
        else:  # Shaded
            if current_period_start is not None:
                sunny_periods.append((current_period_start, r.time))
                current_period_start = None

    # Close final period if still sunny
    if current_period_start is not None:
        sunny_periods.append((current_period_start, results[-1].time))

    # Find best time (middle of longest sunny period)
    best_time = None
    if sunny_periods:
        longest = max(sunny_periods, key=lambda p: (p[1] - p[0]).total_seconds())
        mid_seconds = (longest[1] - longest[0]).total_seconds() / 2
        from datetime import timedelta
        best_time = longest[0] + timedelta(seconds=mid_seconds)

    return {
        "latitude": lat,
        "longitude": lng,
        "floor": floor,
        "balcony_height_m": balcony_height,
        "date": date.strftime("%Y-%m-%d"),
        "total_sun_hours": total_sun_hours,
        "sunny_periods": [
            (s.strftime("%H:%M"), e.strftime("%H:%M"))
            for s, e in sunny_periods
        ],
        "best_time": best_time.strftime("%H:%M") if best_time else None,
        "timeline": [
            {"time": r.time.strftime("%H:%M"), "shadow": r.shadow}
            for r in results
        ],
    }


def find_nearest_amenity(
    lat: float,
    lng: float,
    amenity_type: str,  # 'bench', 'fountain', 'toilet'
    max_distance_m: float = 500,
) -> Optional[AmenityResult]:
    """
    Find nearest amenity of given type.

    Args:
        lat: Latitude
        lng: Longitude
        amenity_type: One of 'bench', 'fountain', 'toilet'
        max_distance_m: Maximum search distance in meters

    Returns:
        AmenityResult or None if not found within distance
    """
    import math

    path_map = {
        "bench": DEFAULT_BENCHES_PATH,
        "fountain": DEFAULT_FOUNTAINS_PATH,
        "toilet": DEFAULT_TOILETS_PATH,
    }

    if amenity_type not in path_map:
        raise ValueError(f"Unknown amenity type: {amenity_type}. Must be one of: {list(path_map.keys())}")

    amenity_path = path_map[amenity_type]

    if not amenity_path.exists():
        raise FileNotFoundError(f"Amenity data not found: {amenity_path}")

    # Load amenities
    with open(amenity_path) as f:
        data = json.load(f)

    features = data.get("features", [])

    if not features:
        return None

    # Calculate distance using haversine formula
    def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance in meters between two WGS84 points."""
        R = 6371000  # Earth radius in meters

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lng2 - lng1)

        a = math.sin(delta_phi / 2) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    # Find nearest
    nearest = None
    nearest_distance = float("inf")

    for feature in features:
        geom = feature.get("geometry", {})
        if geom.get("type") != "Point":
            continue

        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue

        feat_lng, feat_lat = coords[0], coords[1]
        distance = haversine_distance(lat, lng, feat_lat, feat_lng)

        if distance < nearest_distance:
            nearest_distance = distance
            nearest = feature

    if nearest is None or nearest_distance > max_distance_m:
        return None

    geom = nearest["geometry"]
    props = nearest.get("properties", {})

    return AmenityResult(
        type=amenity_type,
        latitude=geom["coordinates"][1],
        longitude=geom["coordinates"][0],
        distance_m=round(nearest_distance, 1),
        properties=props,
    )


def find_amenities_within(
    lat: float,
    lng: float,
    amenity_type: str,
    radius_m: float = 200,
    limit: int = 10,
) -> List[AmenityResult]:
    """
    Find all amenities of given type within radius.

    Args:
        lat: Latitude
        lng: Longitude
        amenity_type: One of 'bench', 'fountain', 'toilet'
        radius_m: Search radius in meters
        limit: Maximum number of results

    Returns:
        List of AmenityResult, sorted by distance
    """
    import math

    path_map = {
        "bench": DEFAULT_BENCHES_PATH,
        "fountain": DEFAULT_FOUNTAINS_PATH,
        "toilet": DEFAULT_TOILETS_PATH,
    }

    if amenity_type not in path_map:
        raise ValueError(f"Unknown amenity type: {amenity_type}")

    amenity_path = path_map[amenity_type]

    if not amenity_path.exists():
        return []

    with open(amenity_path) as f:
        data = json.load(f)

    features = data.get("features", [])

    def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        R = 6371000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lng2 - lng1)
        a = math.sin(delta_phi / 2) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    results = []

    for feature in features:
        geom = feature.get("geometry", {})
        if geom.get("type") != "Point":
            continue

        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue

        feat_lng, feat_lat = coords[0], coords[1]
        distance = haversine_distance(lat, lng, feat_lat, feat_lng)

        if distance <= radius_m:
            results.append(AmenityResult(
                type=amenity_type,
                latitude=feat_lat,
                longitude=feat_lng,
                distance_m=round(distance, 1),
                properties=feature.get("properties", {}),
            ))

    # Sort by distance and limit
    results.sort(key=lambda r: r.distance_m)
    return results[:limit]


# =============================================================================
# ROUTE-BUILDING QUERIES
# =============================================================================

# Path to the preprocessed route-building index
DEFAULT_ROUTE_INDEX_PATH = Path("public/data/route-building-index.json")

# Cache for loaded index
_ROUTE_INDEX_CACHE: Optional[Dict[str, Any]] = None


def _load_route_index(
    index_path: Path = DEFAULT_ROUTE_INDEX_PATH,
    force_reload: bool = False,
) -> Dict[str, Any]:
    """
    Load and cache the route-building spatial index.

    The index is loaded once and cached for subsequent queries.
    """
    global _ROUTE_INDEX_CACHE

    if _ROUTE_INDEX_CACHE is not None and not force_reload:
        return _ROUTE_INDEX_CACHE

    if not index_path.exists():
        raise FileNotFoundError(
            f"Route-building index not found: {index_path}\n"
            "Run: python -m scripts.preprocess.build_route_building_index"
        )

    with open(index_path) as f:
        _ROUTE_INDEX_CACHE = json.load(f)

    return _ROUTE_INDEX_CACHE


@dataclass
class RouteBuildingResult:
    """Result of a route-building query."""

    route_name: str
    route_type: str  # 'tram', 'bus', 'rail', etc.
    route_color: str
    building_count: int
    path_length_km: float
    headsigns: List[str]
    # Amenity counts
    tree_count: int = 0
    bench_count: int = 0
    fountain_count: int = 0
    toilet_count: int = 0
    # Optional IDs
    building_ids: Optional[List[int]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "route_name": self.route_name,
            "route_type": self.route_type,
            "route_color": self.route_color,
            "building_count": self.building_count,
            "tree_count": self.tree_count,
            "bench_count": self.bench_count,
            "fountain_count": self.fountain_count,
            "toilet_count": self.toilet_count,
            "path_length_km": self.path_length_km,
            "headsigns": self.headsigns,
        }
        if self.building_ids is not None:
            result["building_ids"] = self.building_ids
        return result


def get_buildings_along_route(
    route_name: str,
    include_building_ids: bool = False,
    index_path: Path = DEFAULT_ROUTE_INDEX_PATH,
) -> Optional[RouteBuildingResult]:
    """
    Get buildings along a transit route.

    Args:
        route_name: Route short name (e.g., "4", "11", "910")
        include_building_ids: Include list of building IDs (larger response)
        index_path: Path to route-building index

    Returns:
        RouteBuildingResult or None if route not found

    Example:
        >>> result = get_buildings_along_route("4")
        >>> print(f"Tram 4 passes {result.building_count} buildings over {result.path_length_km}km")
    """
    index = _load_route_index(index_path)
    routes = index.get("routes", {})

    if route_name not in routes:
        return None

    route = routes[route_name]

    return RouteBuildingResult(
        route_name=route["route_short_name"],
        route_type=route.get("route_type_name", "unknown"),
        route_color=route.get("route_color", ""),
        building_count=route["building_count"],
        tree_count=route.get("tree_count", 0),
        bench_count=route.get("bench_count", 0),
        fountain_count=route.get("fountain_count", 0),
        toilet_count=route.get("toilet_count", 0),
        path_length_km=route.get("path_length_km", 0),
        headsigns=route.get("headsigns", []),
        building_ids=route.get("building_ids") if include_building_ids else None,
    )


def get_routes_for_building(
    building_id: int,
    index_path: Path = DEFAULT_ROUTE_INDEX_PATH,
) -> List[str]:
    """
    Get transit routes that pass a specific building.

    Args:
        building_id: Building ID from zurich-buildings.geojson
        index_path: Path to route-building index

    Returns:
        List of route names that pass within 50m of the building

    Example:
        >>> routes = get_routes_for_building(12345)
        >>> print(f"Building served by: {', '.join(routes)}")
    """
    index = _load_route_index(index_path)
    building_routes = index.get("building_routes", {})

    # Building IDs are stored as strings in JSON
    return building_routes.get(str(building_id), [])


def list_routes(
    route_type: Optional[str] = None,
    index_path: Path = DEFAULT_ROUTE_INDEX_PATH,
) -> List[RouteBuildingResult]:
    """
    List all routes in the index.

    Args:
        route_type: Filter by type ('tram', 'bus', 'rail', etc.)
        index_path: Path to route-building index

    Returns:
        List of RouteBuildingResult sorted by building count

    Example:
        >>> trams = list_routes(route_type="tram")
        >>> for r in trams[:5]:
        ...     print(f"{r.route_name}: {r.building_count} buildings")
    """
    index = _load_route_index(index_path)
    routes = index.get("routes", {})

    results = []
    for route in routes.values():
        type_name = route.get("route_type_name", "unknown")
        if route_type and type_name != route_type:
            continue

        results.append(RouteBuildingResult(
            route_name=route["route_short_name"],
            route_type=type_name,
            route_color=route.get("route_color", ""),
            building_count=route["building_count"],
            tree_count=route.get("tree_count", 0),
            bench_count=route.get("bench_count", 0),
            fountain_count=route.get("fountain_count", 0),
            toilet_count=route.get("toilet_count", 0),
            path_length_km=route.get("path_length_km", 0),
            headsigns=route.get("headsigns", []),
        ))

    # Sort by building count descending
    results.sort(key=lambda r: r.building_count, reverse=True)
    return results


def compare_routes(
    route_names: List[str],
    index_path: Path = DEFAULT_ROUTE_INDEX_PATH,
) -> Dict[str, Any]:
    """
    Compare multiple routes.

    Args:
        route_names: List of route names to compare
        index_path: Path to route-building index

    Returns:
        Comparison including shared buildings, unique buildings per route

    Example:
        >>> comparison = compare_routes(["4", "11", "15"])
        >>> print(f"Shared buildings: {comparison['shared_building_count']}")
    """
    index = _load_route_index(index_path)
    routes_data = index.get("routes", {})

    results = {
        "routes": [],
        "shared_buildings": [],
        "shared_building_count": 0,
        "total_unique_buildings": 0,
    }

    # Collect building sets for each route
    building_sets = []
    for name in route_names:
        if name not in routes_data:
            continue

        route = routes_data[name]
        building_ids = set(route.get("building_ids", []))
        building_sets.append(building_ids)

        results["routes"].append({
            "route_name": name,
            "building_count": route["building_count"],
            "path_length_km": route.get("path_length_km", 0),
        })

    if len(building_sets) >= 2:
        # Find shared buildings (intersection of all sets)
        shared = building_sets[0]
        for s in building_sets[1:]:
            shared = shared.intersection(s)
        results["shared_buildings"] = sorted(shared)
        results["shared_building_count"] = len(shared)

        # Find total unique (union of all)
        total = set()
        for s in building_sets:
            total = total.union(s)
        results["total_unique_buildings"] = len(total)

    return results


def get_route_statistics(
    index_path: Path = DEFAULT_ROUTE_INDEX_PATH,
) -> Dict[str, Any]:
    """
    Get aggregate statistics about the route-building index.

    Returns:
        Dictionary with summary statistics

    Example:
        >>> stats = get_route_statistics()
        >>> print(f"Total routes: {stats['total_routes']}")
        >>> print(f"Route with most buildings: {stats['max_buildings_route']}")
    """
    index = _load_route_index(index_path)
    routes = index.get("routes", {})
    metadata = index.get("metadata", {})

    # Find extremes
    max_buildings_route = None
    max_buildings = 0
    min_buildings_route = None
    min_buildings = float('inf')
    max_length_route = None
    max_length = 0

    by_type = {}

    for name, route in routes.items():
        bc = route["building_count"]
        length = route.get("path_length_km", 0)
        rt = route.get("route_type_name", "unknown")

        if bc > max_buildings:
            max_buildings = bc
            max_buildings_route = name

        if bc < min_buildings:
            min_buildings = bc
            min_buildings_route = name

        if length > max_length:
            max_length = length
            max_length_route = name

        if rt not in by_type:
            by_type[rt] = {"count": 0, "total_buildings": 0, "total_km": 0}
        by_type[rt]["count"] += 1
        by_type[rt]["total_buildings"] += bc
        by_type[rt]["total_km"] += length

    return {
        "total_routes": len(routes),
        "total_buildings_indexed": metadata.get("total_buildings_indexed", 0),
        "buffer_m": metadata.get("buffer_m", 50),
        "max_buildings_route": max_buildings_route,
        "max_buildings_count": max_buildings,
        "min_buildings_route": min_buildings_route,
        "min_buildings_count": min_buildings if min_buildings != float('inf') else 0,
        "max_length_route": max_length_route,
        "max_length_km": round(max_length, 2),
        "by_type": by_type,
        "created": metadata.get("created"),
    }


def analyze_user_path(
    path_coords: List[Tuple[float, float]],
    buffer_m: float = 20,
    buildings_path: Path = DEFAULT_BUILDINGS_PATH,
) -> Dict[str, Any]:
    """
    Analyze what a user passed along their path.

    Given GPS coordinates, count buildings and other features passed.

    Args:
        path_coords: List of (lng, lat) tuples representing user's path
        buffer_m: Buffer distance in meters (default: 20m)
        buildings_path: Path to buildings GeoJSON

    Returns:
        Dictionary with counts of passed features

    Example:
        >>> path = [(8.54, 47.37), (8.55, 47.38), (8.56, 47.39)]
        >>> result = analyze_user_path(path)
        >>> print(f"You passed {result['buildings_passed']} buildings")
    """
    try:
        from shapely.geometry import LineString, shape
        from shapely.strtree import STRtree
    except ImportError:
        raise ImportError("shapely is required. Install with: pip install shapely")

    if len(path_coords) < 2:
        return {
            "buildings_passed": 0,
            "distance_km": 0,
            "error": "Path must have at least 2 points",
        }

    # Convert to LineString
    line = LineString(path_coords)

    # Buffer the line
    # At Zurich: ~75500m per degree longitude, ~111320m per degree latitude
    buffer_deg = buffer_m / 75500  # approximate
    buffered = line.buffer(buffer_deg)

    # Calculate path length
    import math
    total_km = 0
    for i in range(len(path_coords) - 1):
        lng1, lat1 = path_coords[i]
        lng2, lat2 = path_coords[i + 1]
        R = 6371
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lng2 - lng1)
        a = math.sin(delta_phi / 2) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        total_km += R * c

    # Load and count buildings
    buildings_passed = 0
    if buildings_path.exists():
        with open(buildings_path) as f:
            buildings_data = json.load(f)

        geometries = []
        for feature in buildings_data.get("features", []):
            try:
                geom = shape(feature["geometry"])
                if geom.is_valid:
                    geometries.append(geom)
            except Exception:
                continue

        if geometries:
            tree = STRtree(geometries)
            candidates = tree.query(buffered)
            for idx in candidates:
                if buffered.intersects(geometries[idx]):
                    buildings_passed += 1

    return {
        "buildings_passed": buildings_passed,
        "distance_km": round(total_km, 2),
        "buffer_m": buffer_m,
        "path_points": len(path_coords),
    }
