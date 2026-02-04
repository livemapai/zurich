"""Download and process VBZ GTFS data for animated transit visualization.

Downloads GTFS ZIP from Stadt Zürich Open Data, parses ALL transit routes
(trams, buses, ferries, funiculars, etc.) and interpolates timestamps along
shape points for deck.gl TripsLayer.

Data source: https://data.stadt-zuerich.ch/dataset/vbz_fahrplandaten_gtfs
License: CC0 (Public Domain)

GTFS route_type reference:
  0 = Tram/Light Rail
  1 = Subway/Metro
  2 = Rail
  3 = Bus
  4 = Ferry
  5 = Cable Tram
  6 = Aerial Lift (gondola, aerial tramway)
  7 = Funicular

Output format for TripsLayer (parallel arrays for efficiency):
{
  "trips": [{
    "route_id": "10",
    "route_short_name": "10",
    "route_type": 0,
    "route_color": "#00a1e0",
    "headsign": "Bahnhof Oerlikon",
    "path": [[8.54, 47.37, 410.5], [8.55, 47.38, 412.0]],  // [lng, lat, elevation]
    "timestamps": [28800, 28920]  // seconds since midnight
  }],
  "metadata": { "trip_count": 1200, "generated": "..." }
}

Timestamps use seconds since midnight (0-86400) for float32 precision in WebGL.
"""

import csv
import io
import json
import sys
import zipfile
from collections import defaultdict
from datetime import datetime
from math import radians, cos, sin, sqrt, atan2
from pathlib import Path
from typing import NamedTuple, Callable

import requests

# Add parent directory to path for terrain elevation sampling
sys.path.insert(0, str(Path(__file__).parent.parent))

# Elevation getter is lazy-loaded to allow --no-elevation mode
_elevation_getter: Callable[[float, float], float] | None = None


def get_elevation_lazy(lon: float, lat: float) -> float:
    """Lazy-load elevation getter on first use."""
    global _elevation_getter
    if _elevation_getter is None:
        from terrain.add_elevations import get_elevation
        _elevation_getter = get_elevation
    return _elevation_getter(lon, lat)

# GTFS download URL from Stadt Zürich (year-specific)
GTFS_URL_BASE = "https://data.stadt-zuerich.ch/dataset/vbz_fahrplandaten_gtfs/download"
GTFS_FALLBACK_YEARS = 3


def resolve_gtfs_url() -> tuple[str, bytes]:
    """Resolve the latest available GTFS ZIP and return its content.

    The non-year-specific endpoint can return 500, so we try the current year
    and a small number of previous years until a valid response is found.
    """
    current_year = datetime.now().year
    candidate_years = [current_year - i for i in range(GTFS_FALLBACK_YEARS + 1)]

    for year in candidate_years:
        url = f"{GTFS_URL_BASE}/{year}_google_transit.zip"
        try:
            response = requests.get(url, timeout=120)
            if response.ok:
                return url, response.content
        except requests.RequestException:
            continue

    raise RuntimeError(
        f"Failed to download GTFS data from {GTFS_URL_BASE} for years {candidate_years}"
    )


class Stop(NamedTuple):
    """Stop with location and timing information."""
    stop_id: str
    stop_name: str
    lat: float
    lon: float


class StopTime(NamedTuple):
    """Stop time entry for a trip."""
    trip_id: str
    arrival_time: int  # seconds since midnight
    departure_time: int  # seconds since midnight
    stop_id: str
    stop_sequence: int


class ShapePoint(NamedTuple):
    """Shape point with distance traveled."""
    shape_id: str
    lat: float
    lon: float
    sequence: int
    dist_traveled: float  # meters from start


def parse_gtfs_time(time_str: str) -> int | None:
    """Parse GTFS time string (HH:MM:SS) to seconds since midnight.

    GTFS times can exceed 24:00:00 for trips that span midnight.
    Returns None for empty or invalid time strings.
    """
    if not time_str or not time_str.strip():
        return None
    try:
        parts = time_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2]) if len(parts) > 2 else 0
        return hours * 3600 + minutes * 60 + seconds
    except (ValueError, IndexError):
        return None


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters using Haversine formula."""
    R = 6371000  # Earth's radius in meters

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


def find_nearest_shape_point(
    stop_lat: float,
    stop_lon: float,
    shape_points: list[ShapePoint]
) -> tuple[int, float]:
    """Find the index and distance of the nearest shape point to a stop.

    Returns:
        Tuple of (shape_point_index, distance_in_meters)
    """
    min_dist = float('inf')
    min_idx = 0

    for i, sp in enumerate(shape_points):
        dist = haversine_distance(stop_lat, stop_lon, sp.lat, sp.lon)
        if dist < min_dist:
            min_dist = dist
            min_idx = i

    return min_idx, min_dist


def interpolate_waypoints(
    shape_points: list[ShapePoint],
    stop_times: list[StopTime],
    stops: dict[str, Stop],
    use_elevation: bool = True
) -> dict:
    """Interpolate timestamps for all shape points between stops.

    Algorithm:
    1. Match each stop to its nearest shape point
    2. For shape points between stops, linearly interpolate time based on distance
    3. Return parallel arrays for efficient JSON serialization

    Returns:
        dict with 'path' (list of [lng, lat, elevation]) and 'timestamps' (list of int)
    """
    # Default elevation for flat mode (2m above Zurich base for visual clearance)
    ZURICH_BASE_ELEVATION = 408.0
    FLAT_MODE_ELEVATION = ZURICH_BASE_ELEVATION + 2.0

    if not shape_points or not stop_times:
        return {'path': [], 'timestamps': []}

    # Sort stop times by sequence
    sorted_stops = sorted(stop_times, key=lambda x: x.stop_sequence)

    # Match stops to shape point indices
    stop_matches = []
    for st in sorted_stops:
        stop = stops.get(st.stop_id)
        if not stop:
            continue

        idx, dist = find_nearest_shape_point(stop.lat, stop.lon, shape_points)
        stop_matches.append({
            'shape_idx': idx,
            'arrival_time': st.arrival_time,
            'departure_time': st.departure_time,
            'stop_id': st.stop_id,
            'dist_traveled': shape_points[idx].dist_traveled if shape_points[idx].dist_traveled > 0 else sum(
                haversine_distance(
                    shape_points[i].lat, shape_points[i].lon,
                    shape_points[i+1].lat, shape_points[i+1].lon
                ) for i in range(idx)
            )
        })

    if len(stop_matches) < 2:
        return {'path': [], 'timestamps': []}

    # Sort by shape index to ensure proper ordering
    stop_matches.sort(key=lambda x: x['shape_idx'])

    # Use parallel arrays for efficient JSON output
    path = []
    timestamps = []

    # Process segments between consecutive stops
    for i in range(len(stop_matches) - 1):
        start_match = stop_matches[i]
        end_match = stop_matches[i + 1]

        start_idx = start_match['shape_idx']
        end_idx = end_match['shape_idx']

        # Use departure time from start stop, arrival time at end stop
        start_time = start_match['departure_time']
        end_time = end_match['arrival_time']

        # Handle case where indices are same or inverted
        if start_idx >= end_idx:
            continue

        # Calculate total distance for this segment
        segment_start_dist = start_match['dist_traveled']
        segment_end_dist = end_match['dist_traveled']
        total_segment_dist = segment_end_dist - segment_start_dist

        if total_segment_dist <= 0:
            # Fallback: calculate from coordinates
            total_segment_dist = 0
            for j in range(start_idx, end_idx):
                total_segment_dist += haversine_distance(
                    shape_points[j].lat, shape_points[j].lon,
                    shape_points[j+1].lat, shape_points[j+1].lon
                )

        # Interpolate timestamps for each shape point in this segment
        cumulative_dist = 0
        for j in range(start_idx, end_idx + 1):
            sp = shape_points[j]

            if j == start_idx:
                timestamp = start_time
            elif j == end_idx:
                timestamp = end_time
            else:
                # Linear interpolation based on distance
                if total_segment_dist > 0:
                    progress = cumulative_dist / total_segment_dist
                else:
                    progress = (j - start_idx) / (end_idx - start_idx)
                timestamp = int(start_time + progress * (end_time - start_time))

            # Only add if timestamp is reasonable (within a day + some buffer for overnight trips)
            if 0 <= timestamp < 30 * 3600:  # Up to 30 hours for overnight trips
                # Use 4 decimal precision (~11m accuracy, sufficient for transit visualization)
                # Coordinate format: [lng, lat, elevation] for deck.gl TripsLayer
                if use_elevation:
                    elevation = get_elevation_lazy(sp.lon, sp.lat)
                else:
                    elevation = FLAT_MODE_ELEVATION

                coord = [round(sp.lon, 4), round(sp.lat, 4), round(elevation, 1)]
                path.append(coord)
                timestamps.append(timestamp)

            # Update cumulative distance for next iteration
            if j < end_idx:
                next_sp = shape_points[j + 1]
                cumulative_dist += haversine_distance(sp.lat, sp.lon, next_sp.lat, next_sp.lon)

    # Deduplicate consecutive points with same timestamp or coordinates
    if path:
        deduped_path = [path[0]]
        deduped_timestamps = [timestamps[0]]
        for i in range(1, len(path)):
            # Compare coordinates (first 2 elements) and timestamp
            if timestamps[i] != deduped_timestamps[-1] or path[i][:2] != deduped_path[-1][:2]:
                deduped_path.append(path[i])
                deduped_timestamps.append(timestamps[i])
        path, timestamps = deduped_path, deduped_timestamps

    return {'path': path, 'timestamps': timestamps}


def download_and_process_gtfs(output_path: Path, limit_trips: int = 0, use_elevation: bool = True) -> dict:
    """Download GTFS data and process into TripsLayer format.

    Args:
        output_path: Path to save the JSON output
        limit_trips: Maximum trips per route (0 = no limit, useful for testing)
        use_elevation: Whether to sample terrain elevation for each waypoint

    Returns:
        Metadata dictionary with trip count and generation info
    """
    print("Downloading GTFS data from Stadt Zürich...")
    url, content = resolve_gtfs_url()
    print(f"  → Downloaded from {url}")
    print(f"  → Downloaded {len(content) / 1024 / 1024:.1f} MB")

    # Parse ZIP file in memory
    zf = zipfile.ZipFile(io.BytesIO(content))

    # Read routes.txt - include ALL transit types
    print("Parsing routes...")
    routes = {}
    with zf.open('routes.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig'))
        for row in reader:
            route_type = int(row.get('route_type', 3))  # Default to bus
            routes[row['route_id']] = {
                'route_id': row['route_id'],
                'route_type': route_type,
                'route_short_name': row.get('route_short_name', ''),
                'route_long_name': row.get('route_long_name', ''),
                'route_color': '#' + row.get('route_color', '0088cc'),
            }
    print(f"  → Found {len(routes)} transit routes")

    # Read stops.txt
    print("Parsing stops...")
    stops = {}
    with zf.open('stops.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig'))
        for row in reader:
            stops[row['stop_id']] = Stop(
                stop_id=row['stop_id'],
                stop_name=row.get('stop_name', ''),
                lat=float(row['stop_lat']),
                lon=float(row['stop_lon'])
            )
    print(f"  → Found {len(stops)} stops")

    # Read trips.txt - only for tram routes
    print("Parsing trips...")
    trips = {}
    route_trip_counts = defaultdict(int)
    with zf.open('trips.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig'))
        for row in reader:
            route_id = row['route_id']
            if route_id not in routes:
                continue

            # Optionally limit trips per route
            if limit_trips > 0 and route_trip_counts[route_id] >= limit_trips:
                continue

            trips[row['trip_id']] = {
                'trip_id': row['trip_id'],
                'route_id': route_id,
                'shape_id': row.get('shape_id', ''),
                'headsign': row.get('trip_headsign', ''),
            }
            route_trip_counts[route_id] += 1
    print(f"  → Found {len(trips)} transit trips")

    # Read stop_times.txt - only for our trips
    print("Parsing stop times...")
    trip_stop_times = defaultdict(list)
    skipped_invalid_times = 0
    with zf.open('stop_times.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig'))
        for row in reader:
            trip_id = row['trip_id']
            if trip_id not in trips:
                continue

            arrival_time = parse_gtfs_time(row.get('arrival_time', ''))
            departure_time = parse_gtfs_time(row.get('departure_time', ''))

            # Skip entries with invalid times
            if arrival_time is None or departure_time is None:
                skipped_invalid_times += 1
                continue

            trip_stop_times[trip_id].append(StopTime(
                trip_id=trip_id,
                arrival_time=arrival_time,
                departure_time=departure_time,
                stop_id=row['stop_id'],
                stop_sequence=int(row['stop_sequence'])
            ))
    print(f"  → Loaded stop times for {len(trip_stop_times)} trips")
    if skipped_invalid_times:
        print(f"  → Skipped {skipped_invalid_times} stop times (invalid times)")

    # Read shapes.txt
    print("Parsing shapes...")
    shapes = defaultdict(list)
    shape_ids_used = {trip['shape_id'] for trip in trips.values() if trip.get('shape_id')}
    with zf.open('shapes.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig'))
        for row in reader:
            shape_id = row['shape_id']
            # Only load shapes used by our trips
            if shape_id not in shape_ids_used:
                continue

            shapes[shape_id].append(ShapePoint(
                shape_id=shape_id,
                lat=float(row['shape_pt_lat']),
                lon=float(row['shape_pt_lon']),
                sequence=int(row['shape_pt_sequence']),
                dist_traveled=float(row.get('shape_dist_traveled', 0) or 0)
            ))

    # Sort shape points by sequence
    for shape_id in shapes:
        shapes[shape_id].sort(key=lambda x: x.sequence)
    print(f"  → Loaded {len(shapes)} shapes")

    # Process trips into TripsLayer format
    print("Interpolating waypoints for each trip...")
    output_trips = []
    skipped_no_shape = 0
    skipped_no_waypoints = 0

    for trip_id, trip in trips.items():
        shape_id = trip['shape_id']
        if not shape_id or shape_id not in shapes:
            skipped_no_shape += 1
            continue

        shape_points = shapes[shape_id]
        stop_times = trip_stop_times.get(trip_id, [])

        waypoint_data = interpolate_waypoints(shape_points, stop_times, stops, use_elevation)

        if not waypoint_data['path']:
            skipped_no_waypoints += 1
            continue

        route = routes[trip['route_id']]
        output_trips.append({
            'route_id': route['route_id'],
            'route_type': route['route_type'],
            'route_short_name': route['route_short_name'],
            'route_color': route['route_color'],
            'headsign': trip['headsign'],
            'path': waypoint_data['path'],
            'timestamps': waypoint_data['timestamps']
        })

    print(f"  → Generated {len(output_trips)} trips")
    if skipped_no_shape:
        print(f"  → Skipped {skipped_no_shape} trips (no shape)")
    if skipped_no_waypoints:
        print(f"  → Skipped {skipped_no_waypoints} trips (no waypoints)")

    # Create output
    output = {
        'trips': output_trips,
        'metadata': {
            'trip_count': len(output_trips),
            'route_count': len(set(t['route_id'] for t in output_trips)),
            'generated': datetime.now().isoformat(),
            'source': 'VBZ GTFS (data.stadt-zuerich.ch)',
            'license': 'CC0 Public Domain',
            'has_elevation': use_elevation
        }
    }

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(output, f, separators=(',', ':'))  # Compact JSON

    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"  → Saved to {output_path} ({size_mb:.1f} MB)")

    # Calculate total waypoints for stats
    total_waypoints = sum(len(t['path']) for t in output_trips)
    print(f"  → Total waypoints: {total_waypoints:,}")

    return output['metadata']


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Download and process VBZ GTFS data')
    parser.add_argument('--output', type=str, default='public/data/zurich-tram-trips.json',
                        help='Output JSON file path')
    parser.add_argument('--limit', type=int, default=0,
                        help='Limit trips per route (0 = no limit)')
    parser.add_argument('--no-elevation', action='store_true',
                        help='Skip terrain elevation sampling (faster, smaller files)')
    args = parser.parse_args()

    use_elevation = not args.no_elevation
    mode_str = "with terrain elevation" if use_elevation else "flat (no elevation)"

    print("VBZ GTFS Transit Trips Download")
    print("=" * 40)
    print(f"Mode: {mode_str}")
    if args.limit > 0:
        print(f"Limit: {args.limit} trips per route")

    metadata = download_and_process_gtfs(
        output_path=Path(args.output),
        limit_trips=args.limit,
        use_elevation=use_elevation
    )

    print("=" * 40)
    print(f"Done! {metadata['trip_count']} trips from {metadata['route_count']} routes")
    print(f"Elevation data: {'Yes' if metadata.get('has_elevation') else 'No'}")
