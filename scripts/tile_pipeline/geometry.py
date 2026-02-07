"""
Geometry utilities for the tile pipeline.

Provides functions for:
- Line buffering (converting centerlines to polygons)
- Coordinate transformation (WGS84 to/from local meters)
- Polygon simplification for performance

Key function: buffer_line_to_polygon() converts street centerlines
to road surface polygons by applying a width buffer.

Usage:
    from .geometry import buffer_line_to_polygon, meters_to_degrees

    # Buffer a street centerline to 6m wide polygon
    road_polygon = buffer_line_to_polygon(
        coordinates=[(8.54, 47.37), (8.55, 47.38)],
        width_meters=6.0,
        cap_style="flat",
    )
"""

import math
from typing import List, Tuple, Optional, Literal

from shapely.geometry import LineString, Polygon, MultiPolygon
from shapely.ops import unary_union


# Earth radius at Zurich latitude (~47°N)
# Used for approximate degree <-> meter conversions
EARTH_RADIUS_M = 6378137.0
ZURICH_LAT = 47.37  # Reference latitude for conversions


def meters_to_degrees_lon(meters: float, latitude: float = ZURICH_LAT) -> float:
    """Convert meters to degrees longitude at given latitude.

    At Zurich (47°N): 1° longitude ≈ 75,500m

    Args:
        meters: Distance in meters
        latitude: Reference latitude in degrees

    Returns:
        Distance in degrees longitude
    """
    lat_rad = math.radians(latitude)
    meters_per_degree = (math.pi / 180.0) * EARTH_RADIUS_M * math.cos(lat_rad)
    return meters / meters_per_degree


def meters_to_degrees_lat(meters: float) -> float:
    """Convert meters to degrees latitude.

    Latitude degrees are nearly constant: 1° latitude ≈ 111,320m

    Args:
        meters: Distance in meters

    Returns:
        Distance in degrees latitude
    """
    meters_per_degree = (math.pi / 180.0) * EARTH_RADIUS_M
    return meters / meters_per_degree


def buffer_line_to_polygon(
    coordinates: List[Tuple[float, float]],
    width_meters: float,
    cap_style: Literal["flat", "round", "square"] = "flat",
    join_style: Literal["round", "mitre", "bevel"] = "round",
    latitude: float = ZURICH_LAT,
) -> Optional[List[Tuple[float, float]]]:
    """Convert a line to a polygon by buffering with specified width.

    This is the main function for converting street centerlines to
    road surface polygons. The buffer is applied in degrees but
    calculated from meters for accuracy.

    Note: Because longitude and latitude have different scales at
    non-equatorial latitudes, we use an average buffer distance.
    For more precision at very large scales, consider projecting
    to a local coordinate system first.

    Args:
        coordinates: List of (lon, lat) coordinate tuples
        width_meters: Total road width in meters (buffer will be half on each side)
        cap_style: End cap style ("flat", "round", "square")
        join_style: Corner join style ("round", "mitre", "bevel")
        latitude: Reference latitude for conversion (default: Zurich)

    Returns:
        List of (lon, lat) tuples forming the outer polygon ring,
        or None if invalid geometry

    Example:
        >>> coords = [(8.540, 47.370), (8.545, 47.375)]
        >>> polygon = buffer_line_to_polygon(coords, width_meters=6.0)
        >>> len(polygon)
        24  # Depends on cap_style and resolution
    """
    if len(coordinates) < 2:
        return None

    try:
        line = LineString(coordinates)

        if line.is_empty or not line.is_valid:
            return None

        # Convert width to degrees (average of lon/lat conversion)
        # Use half width since buffer extends both sides
        half_width_m = width_meters / 2.0
        buffer_lon = meters_to_degrees_lon(half_width_m, latitude)
        buffer_lat = meters_to_degrees_lat(half_width_m)

        # Use average for buffer (slight distortion but acceptable for narrow roads)
        buffer_deg = (buffer_lon + buffer_lat) / 2.0

        # Map cap style to Shapely constants
        cap_map = {"flat": 2, "round": 1, "square": 3}
        join_map = {"round": 1, "mitre": 2, "bevel": 3}

        cap = cap_map.get(cap_style, 2)
        join = join_map.get(join_style, 1)

        # Buffer the line
        buffered = line.buffer(
            buffer_deg,
            cap_style=cap,
            join_style=join,
            resolution=8,  # Segments per quarter circle
        )

        if buffered.is_empty:
            return None

        # Extract coordinates from polygon
        if isinstance(buffered, Polygon):
            return list(buffered.exterior.coords)
        elif isinstance(buffered, MultiPolygon):
            # Return largest polygon if multiple (shouldn't happen for single line)
            largest = max(buffered.geoms, key=lambda p: p.area)
            return list(largest.exterior.coords)

        return None

    except Exception as e:
        # Invalid geometry - skip silently
        return None


def clip_polygon_to_bounds(
    polygon_coords: List[Tuple[float, float]],
    bounds: Tuple[float, float, float, float],
) -> Optional[List[Tuple[float, float]]]:
    """Clip a polygon to rectangular bounds.

    Args:
        polygon_coords: List of (lon, lat) coordinates
        bounds: (west, south, east, north) in WGS84

    Returns:
        Clipped polygon coordinates, or None if completely outside
    """
    from shapely.geometry import Polygon, box

    try:
        poly = Polygon(polygon_coords)
        if not poly.is_valid:
            poly = poly.buffer(0)  # Fix invalid geometry

        clip_box = box(bounds[0], bounds[1], bounds[2], bounds[3])
        clipped = poly.intersection(clip_box)

        if clipped.is_empty:
            return None

        if isinstance(clipped, Polygon):
            return list(clipped.exterior.coords)
        elif isinstance(clipped, MultiPolygon):
            largest = max(clipped.geoms, key=lambda p: p.area)
            return list(largest.exterior.coords)

        return None
    except Exception:
        return None


def buffer_multiline_to_polygon(
    lines: List[List[Tuple[float, float]]],
    width_meters: float,
    cap_style: Literal["flat", "round", "square"] = "flat",
    join_style: Literal["round", "mitre", "bevel"] = "round",
    merge: bool = True,
    latitude: float = ZURICH_LAT,
) -> List[List[Tuple[float, float]]]:
    """Convert multiple lines to polygons, optionally merging overlapping ones.

    Useful for creating continuous road surfaces from multiple segments.

    Args:
        lines: List of coordinate lists, each a line
        width_meters: Road width in meters
        cap_style: End cap style
        join_style: Corner join style
        merge: If True, merge overlapping polygons into one
        latitude: Reference latitude

    Returns:
        List of polygon coordinate lists
    """
    polygons = []

    for coords in lines:
        poly_coords = buffer_line_to_polygon(
            coords, width_meters, cap_style, join_style, latitude
        )
        if poly_coords:
            try:
                poly = Polygon(poly_coords)
                if poly.is_valid and not poly.is_empty:
                    polygons.append(poly)
            except Exception:
                continue

    if not polygons:
        return []

    if merge and len(polygons) > 1:
        try:
            merged = unary_union(polygons)
            if isinstance(merged, Polygon):
                return [list(merged.exterior.coords)]
            elif isinstance(merged, MultiPolygon):
                return [list(p.exterior.coords) for p in merged.geoms]
        except Exception:
            pass

    return [list(p.exterior.coords) for p in polygons]


def simplify_polygon(
    coordinates: List[Tuple[float, float]],
    tolerance_meters: float = 0.5,
    latitude: float = ZURICH_LAT,
) -> List[Tuple[float, float]]:
    """Simplify a polygon using Douglas-Peucker algorithm.

    Reduces vertex count for better rendering performance while
    maintaining visual accuracy.

    Args:
        coordinates: Polygon ring coordinates
        tolerance_meters: Simplification tolerance in meters
        latitude: Reference latitude

    Returns:
        Simplified polygon coordinates
    """
    if len(coordinates) < 4:
        return coordinates

    try:
        poly = Polygon(coordinates)

        # Convert tolerance to degrees
        tol_deg = (
            meters_to_degrees_lon(tolerance_meters, latitude) +
            meters_to_degrees_lat(tolerance_meters)
        ) / 2.0

        simplified = poly.simplify(tol_deg, preserve_topology=True)

        if simplified.is_empty:
            return coordinates

        if isinstance(simplified, Polygon):
            return list(simplified.exterior.coords)

        return coordinates

    except Exception:
        return coordinates


def polygon_area_m2(
    coordinates: List[Tuple[float, float]],
    latitude: float = ZURICH_LAT,
) -> float:
    """Calculate approximate polygon area in square meters.

    Uses spherical approximation suitable for small areas.

    Args:
        coordinates: Polygon ring coordinates (lon, lat)
        latitude: Reference latitude

    Returns:
        Area in square meters
    """
    if len(coordinates) < 3:
        return 0.0

    try:
        poly = Polygon(coordinates)
        area_deg2 = poly.area

        # Convert from square degrees to square meters
        # At Zurich: 1 deg² ≈ (75500m × 111320m) = 8.4 billion m²
        m_per_deg_lon = 1.0 / meters_to_degrees_lon(1.0, latitude)
        m_per_deg_lat = 1.0 / meters_to_degrees_lat(1.0)

        return area_deg2 * m_per_deg_lon * m_per_deg_lat

    except Exception:
        return 0.0


def line_length_m(
    coordinates: List[Tuple[float, float]],
    latitude: float = ZURICH_LAT,
) -> float:
    """Calculate approximate line length in meters.

    Args:
        coordinates: Line coordinates (lon, lat)
        latitude: Reference latitude

    Returns:
        Length in meters
    """
    if len(coordinates) < 2:
        return 0.0

    try:
        line = LineString(coordinates)
        length_deg = line.length

        # Average conversion factor
        m_per_deg = (
            1.0 / meters_to_degrees_lon(1.0, latitude) +
            1.0 / meters_to_degrees_lat(1.0)
        ) / 2.0

        return length_deg * m_per_deg

    except Exception:
        return 0.0


def coords_to_local(
    coordinates: List[Tuple[float, float]],
    origin: Tuple[float, float],
    latitude: float = ZURICH_LAT,
) -> List[Tuple[float, float]]:
    """Convert WGS84 coordinates to local meter-based system.

    Args:
        coordinates: List of (lon, lat) tuples
        origin: Origin point (lon, lat) for local system
        latitude: Reference latitude for conversions

    Returns:
        List of (x, y) tuples in meters from origin
    """
    origin_lon, origin_lat = origin
    m_per_deg_lon = 1.0 / meters_to_degrees_lon(1.0, latitude)
    m_per_deg_lat = 1.0 / meters_to_degrees_lat(1.0)

    return [
        (
            (lon - origin_lon) * m_per_deg_lon,
            (lat - origin_lat) * m_per_deg_lat
        )
        for lon, lat in coordinates
    ]


def local_to_coords(
    local_points: List[Tuple[float, float]],
    origin: Tuple[float, float],
    latitude: float = ZURICH_LAT,
) -> List[Tuple[float, float]]:
    """Convert local meter-based coordinates back to WGS84.

    Args:
        local_points: List of (x, y) tuples in meters
        origin: Origin point (lon, lat) for local system
        latitude: Reference latitude for conversions

    Returns:
        List of (lon, lat) tuples in WGS84
    """
    origin_lon, origin_lat = origin
    deg_per_m_lon = meters_to_degrees_lon(1.0, latitude)
    deg_per_m_lat = meters_to_degrees_lat(1.0)

    return [
        (
            origin_lon + x * deg_per_m_lon,
            origin_lat + y * deg_per_m_lat
        )
        for x, y in local_points
    ]
