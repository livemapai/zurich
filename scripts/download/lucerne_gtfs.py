#!/usr/bin/env python3
"""
Download and process VBL GTFS data for animated transit visualization.

Downloads Swiss national GTFS from opentransportdata.swiss, filters for
VBL (Verkehrsbetriebe Luzern) routes, and processes for deck.gl TripsLayer.

Data source: https://opentransportdata.swiss/de/dataset/timetable-2024-gtfs2020
License: Open Data (ODbl)

VBL operates ~148 bus routes in the Lucerne region.

Output format for TripsLayer (parallel arrays for efficiency):
{
  "trips": [{
    "route_id": "10",
    "route_short_name": "10",
    "route_type": 3,  # Bus
    "route_color": "#00a1e0",
    "headsign": "Emmenbrücke",
    "path": [[8.30, 47.05, 436.5], ...],  // [lng, lat, elevation]
    "timestamps": [28800, 28920, ...]  // seconds since midnight
  }],
  "metadata": { "trip_count": 1200, "generated": "..." }
}
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
from typing import NamedTuple, Callable, Optional

import requests

# Add parent directory to path for terrain elevation sampling
sys.path.insert(0, str(Path(__file__).parent.parent))

# Elevation getter is lazy-loaded for --no-elevation mode
_elevation_getter: Callable[[float, float], float] | None = None


def get_elevation_lazy(lon: float, lat: float) -> float:
    """Lazy-load elevation getter on first use."""
    global _elevation_getter
    if _elevation_getter is None:
        try:
            from terrain.add_elevations import get_elevation
            _elevation_getter = get_elevation
        except ImportError:
            # Fallback to Lucerne base elevation
            _elevation_getter = lambda lon, lat: LUCERNE_BASE_ELEVATION + 2.0
    return _elevation_getter(lon, lat)


# Swiss GTFS download URLs
# Primary: geOps mirror (updated daily from opentransportdata.swiss)
# Alternative: Official opentransportdata.swiss (requires discovering current URL)
GTFS_URLS = [
    "https://gtfs.geops.ch/dl/gtfs_complete.zip",  # geOps mirror - reliable
    "https://gtfs.geops.ch/dl/gtfs_bus.zip",  # Bus-only (smaller, VBL is bus)
]

# VBL agency identifiers
VBL_AGENCY_NAMES = [
    "VBL",
    "Verkehrsbetriebe Luzern",
    "vbl",
]

# Lucerne base elevation
LUCERNE_BASE_ELEVATION = 436.0

# Lucerne bounding box for filtering
LUCERNE_BBOX = {
    "min_lat": 46.95,
    "max_lat": 47.10,
    "min_lng": 8.20,
    "max_lng": 8.45,
}

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "public" / "data" / "lucerne"


class Stop(NamedTuple):
    """Stop with location and timing information."""
    stop_id: str
    stop_name: str
    lat: float
    lon: float


class StopTime(NamedTuple):
    """Stop time entry for a trip."""
    trip_id: str
    arrival_time: int
    departure_time: int
    stop_id: str
    stop_sequence: int


class ShapePoint(NamedTuple):
    """Shape point with distance traveled."""
    shape_id: str
    lat: float
    lon: float
    sequence: int
    dist_traveled: float


def parse_gtfs_time(time_str: str) -> int | None:
    """Parse GTFS time string (HH:MM:SS) to seconds since midnight."""
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
    """Calculate distance between two points in meters."""
    R = 6371000
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
    """Find the index and distance of the nearest shape point to a stop."""
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
    """Interpolate timestamps for all shape points between stops."""
    FLAT_MODE_ELEVATION = LUCERNE_BASE_ELEVATION + 2.0

    if not shape_points or not stop_times:
        return {'path': [], 'timestamps': []}

    sorted_stops = sorted(stop_times, key=lambda x: x.stop_sequence)

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

    stop_matches.sort(key=lambda x: x['shape_idx'])

    path = []
    timestamps = []

    for i in range(len(stop_matches) - 1):
        start_match = stop_matches[i]
        end_match = stop_matches[i + 1]

        start_idx = start_match['shape_idx']
        end_idx = end_match['shape_idx']
        start_time = start_match['departure_time']
        end_time = end_match['arrival_time']

        if start_idx >= end_idx:
            continue

        segment_start_dist = start_match['dist_traveled']
        segment_end_dist = end_match['dist_traveled']
        total_segment_dist = segment_end_dist - segment_start_dist

        if total_segment_dist <= 0:
            total_segment_dist = 0
            for j in range(start_idx, end_idx):
                total_segment_dist += haversine_distance(
                    shape_points[j].lat, shape_points[j].lon,
                    shape_points[j+1].lat, shape_points[j+1].lon
                )

        cumulative_dist = 0
        for j in range(start_idx, end_idx + 1):
            sp = shape_points[j]

            if j == start_idx:
                timestamp = start_time
            elif j == end_idx:
                timestamp = end_time
            else:
                if total_segment_dist > 0:
                    progress = cumulative_dist / total_segment_dist
                else:
                    progress = (j - start_idx) / (end_idx - start_idx)
                timestamp = int(start_time + progress * (end_time - start_time))

            if 0 <= timestamp < 30 * 3600:
                if use_elevation:
                    elevation = get_elevation_lazy(sp.lon, sp.lat)
                else:
                    elevation = FLAT_MODE_ELEVATION

                coord = [round(sp.lon, 4), round(sp.lat, 4), round(elevation, 1)]
                path.append(coord)
                timestamps.append(timestamp)

            if j < end_idx:
                next_sp = shape_points[j + 1]
                cumulative_dist += haversine_distance(sp.lat, sp.lon, next_sp.lat, next_sp.lon)

    # Deduplicate consecutive points
    if path:
        deduped_path = [path[0]]
        deduped_timestamps = [timestamps[0]]
        for i in range(1, len(path)):
            if timestamps[i] != deduped_timestamps[-1] or path[i][:2] != deduped_path[-1][:2]:
                deduped_path.append(path[i])
                deduped_timestamps.append(timestamps[i])
        path, timestamps = deduped_path, deduped_timestamps

    return {'path': path, 'timestamps': timestamps}


def construct_path_from_stops(
    stop_times: list[StopTime],
    stops: dict[str, Stop],
    use_elevation: bool = True
) -> dict:
    """Construct path directly from stop coordinates when shapes.txt is unavailable.

    This provides a simpler line-based visualization that connects stops directly.
    """
    FLAT_MODE_ELEVATION = LUCERNE_BASE_ELEVATION + 2.0

    if not stop_times:
        return {'path': [], 'timestamps': []}

    sorted_stops = sorted(stop_times, key=lambda x: x.stop_sequence)

    path = []
    timestamps = []

    for st in sorted_stops:
        stop = stops.get(st.stop_id)
        if not stop:
            continue

        if use_elevation:
            elevation = get_elevation_lazy(stop.lon, stop.lat)
        else:
            elevation = FLAT_MODE_ELEVATION

        # Use departure time for intermediate stops, arrival for last
        timestamp = st.departure_time if st.departure_time else st.arrival_time

        if timestamp is not None and 0 <= timestamp < 30 * 3600:
            coord = [round(stop.lon, 4), round(stop.lat, 4), round(elevation, 1)]
            path.append(coord)
            timestamps.append(timestamp)

    # Deduplicate
    if path:
        deduped_path = [path[0]]
        deduped_timestamps = [timestamps[0]]
        for i in range(1, len(path)):
            if timestamps[i] != deduped_timestamps[-1] or path[i][:2] != deduped_path[-1][:2]:
                deduped_path.append(path[i])
                deduped_timestamps.append(timestamps[i])
        path, timestamps = deduped_path, deduped_timestamps

    return {'path': path, 'timestamps': timestamps}


def is_in_lucerne_area(lat: float, lon: float) -> bool:
    """Check if coordinates are within Lucerne bounding box."""
    return (
        LUCERNE_BBOX["min_lat"] <= lat <= LUCERNE_BBOX["max_lat"] and
        LUCERNE_BBOX["min_lng"] <= lon <= LUCERNE_BBOX["max_lng"]
    )


def download_and_process_gtfs(
    output_path: Path,
    limit_trips: int = 0,
    use_elevation: bool = True
) -> dict:
    """
    Download Swiss GTFS and extract VBL transit data.

    Args:
        output_path: Path to save JSON output
        limit_trips: Maximum trips per route (0 = no limit)
        use_elevation: Whether to sample terrain elevation

    Returns:
        Metadata dictionary
    """
    print("Downloading Swiss GTFS data...")

    content = None
    for url in GTFS_URLS:
        print(f"Trying: {url}")
        try:
            response = requests.get(url, timeout=300, allow_redirects=True)
            response.raise_for_status()
            content = response.content
            print(f"  → Success!")
            break
        except Exception as e:
            print(f"  → Failed: {e}")
            continue

    if content is None:
        raise RuntimeError(f"Failed to download GTFS from any source: {GTFS_URLS}")

    print(f"  → Downloaded {len(content) / 1024 / 1024:.1f} MB")

    zf = zipfile.ZipFile(io.BytesIO(content))

    # Read agencies and find VBL
    print("Finding VBL agency...")
    vbl_agency_ids = set()
    with zf.open('agency.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig'))
        for row in reader:
            agency_name = row.get('agency_name', '')
            if any(vbl_name.lower() in agency_name.lower() for vbl_name in VBL_AGENCY_NAMES):
                vbl_agency_ids.add(row['agency_id'])
                print(f"  → Found VBL: {agency_name} (ID: {row['agency_id']})")

    if not vbl_agency_ids:
        print("Warning: VBL agency not found, filtering by Lucerne area instead")

    # Read routes
    print("Parsing routes...")
    routes = {}
    with zf.open('routes.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig'))
        for row in reader:
            agency_id = row.get('agency_id', '')
            if vbl_agency_ids and agency_id not in vbl_agency_ids:
                continue

            route_type = int(row.get('route_type', 3))
            routes[row['route_id']] = {
                'route_id': row['route_id'],
                'route_type': route_type,
                'route_short_name': row.get('route_short_name', ''),
                'route_long_name': row.get('route_long_name', ''),
                'route_color': '#' + (row.get('route_color', '') or '0088cc'),
            }
    print(f"  → Found {len(routes)} VBL routes")

    # Read stops
    print("Parsing stops...")
    stops = {}
    with zf.open('stops.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig'))
        for row in reader:
            lat = float(row['stop_lat'])
            lon = float(row['stop_lon'])
            # Keep all stops if VBL agency found, otherwise filter by area
            if vbl_agency_ids or is_in_lucerne_area(lat, lon):
                stops[row['stop_id']] = Stop(
                    stop_id=row['stop_id'],
                    stop_name=row.get('stop_name', ''),
                    lat=lat,
                    lon=lon
                )
    print(f"  → Found {len(stops)} stops")

    # Read trips
    print("Parsing trips...")
    trips = {}
    route_trip_counts = defaultdict(int)
    with zf.open('trips.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig'))
        for row in reader:
            route_id = row['route_id']
            if route_id not in routes:
                continue

            if limit_trips > 0 and route_trip_counts[route_id] >= limit_trips:
                continue

            trips[row['trip_id']] = {
                'trip_id': row['trip_id'],
                'route_id': route_id,
                'shape_id': row.get('shape_id', ''),
                'headsign': row.get('trip_headsign', ''),
            }
            route_trip_counts[route_id] += 1
    print(f"  → Found {len(trips)} trips")

    # Read stop_times
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

    # Read shapes (optional - some GTFS exports don't include shapes.txt)
    print("Parsing shapes...")
    shapes = defaultdict(list)
    has_shapes = 'shapes.txt' in zf.namelist()

    if has_shapes:
        shape_ids_used = {trip['shape_id'] for trip in trips.values() if trip.get('shape_id')}
        with zf.open('shapes.txt') as f:
            reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig'))
            for row in reader:
                shape_id = row['shape_id']
                if shape_id not in shape_ids_used:
                    continue

                shapes[shape_id].append(ShapePoint(
                    shape_id=shape_id,
                    lat=float(row['shape_pt_lat']),
                    lon=float(row['shape_pt_lon']),
                    sequence=int(row['shape_pt_sequence']),
                    dist_traveled=float(row.get('shape_dist_traveled', 0) or 0)
                ))

        for shape_id in shapes:
            shapes[shape_id].sort(key=lambda x: x.sequence)
        print(f"  → Loaded {len(shapes)} shapes")
    else:
        print("  → shapes.txt not found, will construct paths from stops")

    # Process trips
    print("Interpolating waypoints...")
    output_trips = []
    skipped_no_shape = 0
    skipped_no_waypoints = 0

    for trip_id, trip in trips.items():
        stop_times = trip_stop_times.get(trip_id, [])
        if not stop_times:
            skipped_no_waypoints += 1
            continue

        # If we have shapes, use them
        shape_id = trip.get('shape_id')
        if has_shapes and shape_id and shape_id in shapes:
            shape_points = shapes[shape_id]
            waypoint_data = interpolate_waypoints(shape_points, stop_times, stops, use_elevation)
        else:
            # Construct path directly from stop coordinates
            waypoint_data = construct_path_from_stops(stop_times, stops, use_elevation)
            if not has_shapes:
                pass  # Expected when no shapes
            else:
                skipped_no_shape += 1

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

    output = {
        'trips': output_trips,
        'metadata': {
            'trip_count': len(output_trips),
            'route_count': len(set(t['route_id'] for t in output_trips)),
            'generated': datetime.now().isoformat(),
            'source': 'VBL GTFS (opentransportdata.swiss)',
            'license': 'ODbl',
            'has_elevation': use_elevation
        }
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(output, f, separators=(',', ':'))

    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"  → Saved to {output_path} ({size_mb:.1f} MB)")

    total_waypoints = sum(len(t['path']) for t in output_trips)
    print(f"  → Total waypoints: {total_waypoints:,}")

    return output['metadata']


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Download and process VBL GTFS data')
    parser.add_argument(
        '--output', type=str,
        default=str(OUTPUT_DIR / 'lucerne-vbl-trips.json'),
        help='Output JSON file path'
    )
    parser.add_argument(
        '--limit', type=int, default=0,
        help='Limit trips per route (0 = no limit)'
    )
    parser.add_argument(
        '--no-elevation', action='store_true',
        help='Skip terrain elevation sampling'
    )

    args = parser.parse_args()

    use_elevation = not args.no_elevation
    mode_str = "with terrain elevation" if use_elevation else "flat (no elevation)"

    print("VBL GTFS Transit Trips Download")
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


if __name__ == "__main__":
    main()
