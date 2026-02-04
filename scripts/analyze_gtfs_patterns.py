#!/usr/bin/env python3
"""Analyze VBZ GTFS data for schedule patterns and optimization opportunities.

This script downloads the GTFS feed and performs comprehensive analysis to answer:
1. Can we store ONE path per route+direction and replay it?
2. Are schedules regular enough to use headway tables?
3. What percentage of trips share identical geometry?

Usage:
    python scripts/analyze_gtfs_patterns.py
"""

import csv
import io
import zipfile
from collections import defaultdict
from datetime import datetime
from statistics import mean, median, stdev
from typing import NamedTuple

import requests

# GTFS download URL from Stadt Zürich
GTFS_URL_BASE = "https://data.stadt-zuerich.ch/dataset/vbz_fahrplandaten_gtfs/download"
GTFS_FALLBACK_YEARS = 3

# Route type names
ROUTE_TYPES = {
    0: "Tram",
    1: "Subway",
    2: "Rail",
    3: "Bus",
    4: "Ferry",
    5: "Cable Tram",
    6: "Aerial Lift",
    7: "Funicular",
}


def resolve_gtfs_url() -> tuple[str, bytes]:
    """Resolve the latest available GTFS ZIP and return its content."""
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

    raise RuntimeError(f"Failed to download GTFS data for years {candidate_years}")


class Trip(NamedTuple):
    trip_id: str
    route_id: str
    shape_id: str
    direction_id: str
    headsign: str
    service_id: str


class StopTime(NamedTuple):
    trip_id: str
    arrival_time: int  # seconds since midnight
    departure_time: int
    stop_id: str
    stop_sequence: int


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


def format_time(seconds: int) -> str:
    """Format seconds since midnight as HH:MM:SS."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_duration(seconds: float) -> str:
    """Format duration in seconds as 'Xm Ys'."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def analyze_gtfs():
    """Main analysis function."""

    print("=" * 80)
    print("VBZ GTFS PATTERN ANALYSIS")
    print("=" * 80)
    print()

    # Download GTFS data
    print("Downloading GTFS data from Stadt Zürich...")
    url, content = resolve_gtfs_url()
    print(f"  Source: {url}")
    print(f"  Size: {len(content) / 1024 / 1024:.1f} MB")
    print()

    zf = zipfile.ZipFile(io.BytesIO(content))

    # List all files in the GTFS archive
    print("GTFS Files in Archive:")
    print("-" * 40)
    for name in sorted(zf.namelist()):
        info = zf.getinfo(name)
        print(f"  {name}: {info.file_size / 1024:.1f} KB")
    print()

    # Check for frequencies.txt
    has_frequencies = 'frequencies.txt' in zf.namelist()
    print(f"Has frequencies.txt: {'YES' if has_frequencies else 'NO'}")
    if has_frequencies:
        with zf.open('frequencies.txt') as f:
            reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig'))
            freq_rows = list(reader)
            print(f"  → {len(freq_rows)} frequency entries found")
    print()

    # Parse routes
    print("Parsing routes...")
    routes = {}
    with zf.open('routes.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig'))
        for row in reader:
            route_type = int(row.get('route_type', 3))
            routes[row['route_id']] = {
                'route_id': row['route_id'],
                'route_type': route_type,
                'route_type_name': ROUTE_TYPES.get(route_type, f"Unknown({route_type})"),
                'route_short_name': row.get('route_short_name', ''),
                'route_long_name': row.get('route_long_name', ''),
            }
    print(f"  → {len(routes)} routes")

    # Parse trips
    print("Parsing trips...")
    trips = {}
    with zf.open('trips.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig'))
        for row in reader:
            trips[row['trip_id']] = Trip(
                trip_id=row['trip_id'],
                route_id=row['route_id'],
                shape_id=row.get('shape_id', ''),
                direction_id=row.get('direction_id', '0'),
                headsign=row.get('trip_headsign', ''),
                service_id=row.get('service_id', '')
            )
    print(f"  → {len(trips)} trips")

    # Parse stop_times (for headway analysis)
    print("Parsing stop_times...")
    trip_start_times = {}  # trip_id -> first departure time
    trip_stop_times = defaultdict(list)
    with zf.open('stop_times.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig'))
        for row in reader:
            trip_id = row['trip_id']
            departure_time = parse_gtfs_time(row.get('departure_time', ''))
            if departure_time is not None:
                seq = int(row['stop_sequence'])
                trip_stop_times[trip_id].append((seq, departure_time))

    # Get first stop departure time for each trip
    for trip_id, stop_times in trip_stop_times.items():
        if stop_times:
            stop_times.sort(key=lambda x: x[0])
            trip_start_times[trip_id] = stop_times[0][1]
    print(f"  → {len(trip_start_times)} trips with valid start times")

    # Parse shapes
    print("Parsing shapes...")
    shapes = defaultdict(list)
    with zf.open('shapes.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig'))
        for row in reader:
            shape_id = row['shape_id']
            shapes[shape_id].append((
                int(row['shape_pt_sequence']),
                float(row['shape_pt_lat']),
                float(row['shape_pt_lon'])
            ))

    # Sort shape points
    for shape_id in shapes:
        shapes[shape_id].sort(key=lambda x: x[0])
    print(f"  → {len(shapes)} unique shapes")
    print()

    # ========================================================================
    # ROUTE-LEVEL ANALYSIS
    # ========================================================================
    print("=" * 80)
    print("ROUTE-LEVEL ANALYSIS")
    print("=" * 80)
    print()

    # Group trips by route
    trips_by_route = defaultdict(list)
    for trip in trips.values():
        trips_by_route[trip.route_id].append(trip)

    # Analyze each route type
    route_type_stats = defaultdict(lambda: {'routes': 0, 'trips': 0})
    for route_id, route in routes.items():
        route_type = route['route_type']
        route_type_stats[route_type]['routes'] += 1
        route_type_stats[route_type]['trips'] += len(trips_by_route.get(route_id, []))

    print("Routes by Type:")
    print("-" * 40)
    for route_type in sorted(route_type_stats.keys()):
        stats = route_type_stats[route_type]
        type_name = ROUTE_TYPES.get(route_type, f"Type {route_type}")
        print(f"  {type_name}: {stats['routes']} routes, {stats['trips']} trips")
    print()

    # Trips per route statistics
    trip_counts = [len(trips_by_route.get(r, [])) for r in routes.keys()]
    trip_counts = [c for c in trip_counts if c > 0]  # Filter out routes with no trips

    print("Trips per Route:")
    print("-" * 40)
    print(f"  Min: {min(trip_counts)}")
    print(f"  Max: {max(trip_counts)}")
    print(f"  Mean: {mean(trip_counts):.1f}")
    print(f"  Median: {median(trip_counts):.1f}")
    print()

    # ========================================================================
    # PATH GEOMETRY ANALYSIS
    # ========================================================================
    print("=" * 80)
    print("PATH GEOMETRY ANALYSIS")
    print("=" * 80)
    print()

    # Analyze shape consistency per route+direction
    route_direction_shapes = defaultdict(set)  # (route_id, direction_id) -> set of shape_ids
    route_direction_trips = defaultdict(int)   # (route_id, direction_id) -> trip count

    for trip in trips.values():
        key = (trip.route_id, trip.direction_id)
        if trip.shape_id:
            route_direction_shapes[key].add(trip.shape_id)
        route_direction_trips[key] += 1

    # Count routes with consistent shapes
    consistent_count = 0
    inconsistent_count = 0
    total_trips_consistent = 0
    total_trips_inconsistent = 0

    inconsistent_details = []

    for (route_id, direction_id), shape_ids in route_direction_shapes.items():
        trip_count = route_direction_trips[(route_id, direction_id)]
        if len(shape_ids) == 1:
            consistent_count += 1
            total_trips_consistent += trip_count
        else:
            inconsistent_count += 1
            total_trips_inconsistent += trip_count
            route = routes.get(route_id, {})
            inconsistent_details.append({
                'route_id': route_id,
                'route_name': route.get('route_short_name', route_id),
                'route_type': route.get('route_type_name', 'Unknown'),
                'direction': direction_id,
                'shapes': len(shape_ids),
                'trips': trip_count
            })

    total_rd = consistent_count + inconsistent_count

    print("Shape Consistency per Route+Direction:")
    print("-" * 40)
    print(f"  Route+directions with SAME shape: {consistent_count} ({100*consistent_count/total_rd:.1f}%)")
    print(f"  Route+directions with MULTIPLE shapes: {inconsistent_count} ({100*inconsistent_count/total_rd:.1f}%)")
    print()
    print(f"  Trips sharing geometry (single shape): {total_trips_consistent:,} ({100*total_trips_consistent/(total_trips_consistent+total_trips_inconsistent):.1f}%)")
    print(f"  Trips with variant geometry: {total_trips_inconsistent:,} ({100*total_trips_inconsistent/(total_trips_consistent+total_trips_inconsistent):.1f}%)")
    print()

    if inconsistent_details:
        # Sort by number of shapes (most variant first)
        inconsistent_details.sort(key=lambda x: -x['shapes'])
        print("Routes with Multiple Shapes per Direction (top 15):")
        print("-" * 60)
        print(f"  {'Route':<15} {'Type':<12} {'Dir':<4} {'Shapes':<7} {'Trips':<8}")
        print(f"  {'-'*13:<15} {'-'*10:<12} {'-'*3:<4} {'-'*6:<7} {'-'*6:<8}")
        for detail in inconsistent_details[:15]:
            print(f"  {detail['route_name']:<15} {detail['route_type']:<12} {detail['direction']:<4} {detail['shapes']:<7} {detail['trips']:<8}")
        print()

    # Shape reuse across routes
    shape_usage = defaultdict(list)  # shape_id -> list of (route_id, direction_id)
    for (route_id, direction_id), shape_ids in route_direction_shapes.items():
        for shape_id in shape_ids:
            shape_usage[shape_id].append((route_id, direction_id))

    shared_shapes = {sid: users for sid, users in shape_usage.items() if len(users) > 1}
    print(f"Shapes shared across route+directions: {len(shared_shapes)}")
    print()

    # ========================================================================
    # SCHEDULE PATTERN ANALYSIS
    # ========================================================================
    print("=" * 80)
    print("SCHEDULE PATTERN ANALYSIS")
    print("=" * 80)
    print()

    # Analyze headways per route+direction
    def calculate_headways(trip_times: list[int]) -> list[int]:
        """Calculate headways (gaps) between sorted trip times."""
        sorted_times = sorted(trip_times)
        return [sorted_times[i+1] - sorted_times[i] for i in range(len(sorted_times)-1)]

    route_direction_times = defaultdict(list)  # (route_id, direction_id) -> list of start times
    for trip_id, start_time in trip_start_times.items():
        if trip_id in trips:
            trip = trips[trip_id]
            key = (trip.route_id, trip.direction_id)
            route_direction_times[key].append(start_time)

    # Analyze headway regularity
    headway_analysis = []

    for (route_id, direction_id), times in route_direction_times.items():
        if len(times) < 3:  # Need at least 3 trips for meaningful headway analysis
            continue

        headways = calculate_headways(times)
        if not headways:
            continue

        # Calculate statistics
        avg_headway = mean(headways)
        med_headway = median(headways)
        min_headway = min(headways)
        max_headway = max(headways)

        # Calculate coefficient of variation (CV) to measure regularity
        # CV < 0.1 = very regular, CV > 0.5 = highly irregular
        if len(headways) > 1 and avg_headway > 0:
            headway_stdev = stdev(headways)
            cv = headway_stdev / avg_headway
        else:
            cv = 0

        route = routes.get(route_id, {})
        headway_analysis.append({
            'route_id': route_id,
            'route_name': route.get('route_short_name', route_id),
            'route_type': route.get('route_type', 3),
            'route_type_name': route.get('route_type_name', 'Unknown'),
            'direction': direction_id,
            'trip_count': len(times),
            'avg_headway': avg_headway,
            'med_headway': med_headway,
            'min_headway': min_headway,
            'max_headway': max_headway,
            'cv': cv,
            'is_regular': cv < 0.3,  # Less than 30% variation = regular
            'headways': headways  # Keep for time-of-day analysis
        })

    # Summary statistics
    regular_count = sum(1 for h in headway_analysis if h['is_regular'])
    irregular_count = len(headway_analysis) - regular_count

    print("Headway Regularity Analysis:")
    print("-" * 40)
    print(f"  Route+directions analyzed: {len(headway_analysis)}")
    print(f"  Regular schedules (CV < 0.3): {regular_count} ({100*regular_count/len(headway_analysis):.1f}%)")
    print(f"  Irregular schedules (CV >= 0.3): {irregular_count} ({100*irregular_count/len(headway_analysis):.1f}%)")
    print()

    # Headway distribution by route type
    print("Average Headways by Route Type:")
    print("-" * 40)
    headways_by_type = defaultdict(list)
    for h in headway_analysis:
        headways_by_type[h['route_type']].append(h['avg_headway'])

    for route_type in sorted(headways_by_type.keys()):
        type_name = ROUTE_TYPES.get(route_type, f"Type {route_type}")
        avg = mean(headways_by_type[route_type])
        print(f"  {type_name}: {format_duration(avg)} average headway")
    print()

    # Show sample regular routes
    print("Sample Regular Routes (most consistent headways):")
    print("-" * 70)
    regular_routes = sorted([h for h in headway_analysis if h['is_regular']], key=lambda x: x['cv'])[:10]
    print(f"  {'Route':<12} {'Type':<10} {'Dir':<4} {'Avg Headway':<14} {'CV':<8} {'Trips':<6}")
    print(f"  {'-'*10:<12} {'-'*8:<10} {'-'*3:<4} {'-'*12:<14} {'-'*6:<8} {'-'*5:<6}")
    for h in regular_routes:
        print(f"  {h['route_name']:<12} {h['route_type_name']:<10} {h['direction']:<4} {format_duration(h['avg_headway']):<14} {h['cv']:.3f}   {h['trip_count']:<6}")
    print()

    # Show sample irregular routes
    print("Sample Irregular Routes (most variable headways):")
    print("-" * 70)
    irregular_routes = sorted([h for h in headway_analysis if not h['is_regular']], key=lambda x: -x['cv'])[:10]
    print(f"  {'Route':<12} {'Type':<10} {'Dir':<4} {'Min-Max Headway':<18} {'CV':<8} {'Trips':<6}")
    print(f"  {'-'*10:<12} {'-'*8:<10} {'-'*3:<4} {'-'*16:<18} {'-'*6:<8} {'-'*5:<6}")
    for h in irregular_routes:
        range_str = f"{format_duration(h['min_headway'])} - {format_duration(h['max_headway'])}"
        print(f"  {h['route_name']:<12} {h['route_type_name']:<10} {h['direction']:<4} {range_str:<18} {h['cv']:.3f}   {h['trip_count']:<6}")
    print()

    # ========================================================================
    # TIME-OF-DAY ANALYSIS
    # ========================================================================
    print("=" * 80)
    print("TIME-OF-DAY HEADWAY VARIATION")
    print("=" * 80)
    print()

    # Define time periods
    TIME_PERIODS = [
        ("Early Morning", 5 * 3600, 7 * 3600),    # 05:00 - 07:00
        ("Morning Rush", 7 * 3600, 9 * 3600),     # 07:00 - 09:00
        ("Midday", 9 * 3600, 16 * 3600),          # 09:00 - 16:00
        ("Evening Rush", 16 * 3600, 19 * 3600),   # 16:00 - 19:00
        ("Evening", 19 * 3600, 23 * 3600),        # 19:00 - 23:00
        ("Night", 23 * 3600, 29 * 3600),          # 23:00 - 05:00 (next day)
    ]

    def get_period(time_seconds: int) -> str:
        """Get time period name for a given time."""
        # Normalize to 0-24h for period matching
        normalized = time_seconds % 86400
        for name, start, end in TIME_PERIODS:
            if name == "Night":
                # Night spans midnight
                if normalized >= 23 * 3600 or normalized < 5 * 3600:
                    return name
            elif start <= normalized < end:
                return name
        return "Unknown"

    # Analyze a few key tram routes in detail
    print("Detailed Time-of-Day Analysis for Key Routes:")
    print("-" * 60)

    # Focus on trams (route_type 0) with most trips
    tram_routes = sorted(
        [(r, d, times) for (r, d), times in route_direction_times.items()
         if routes.get(r, {}).get('route_type') == 0 and len(times) > 50],
        key=lambda x: -len(x[2])
    )[:5]

    for route_id, direction_id, times in tram_routes:
        route = routes.get(route_id, {})
        print(f"\n  Route {route.get('route_short_name', route_id)} (Direction {direction_id}):")
        print(f"  Total trips: {len(times)}")

        # Group times by period
        period_times = defaultdict(list)
        for t in times:
            period = get_period(t)
            period_times[period].append(t)

        print(f"  {'Period':<16} {'Trips':<8} {'Avg Headway':<14}")
        print(f"  {'-'*14:<16} {'-'*6:<8} {'-'*12:<14}")

        for period_name, _, _ in TIME_PERIODS:
            period_t = period_times.get(period_name, [])
            if len(period_t) >= 2:
                headways = calculate_headways(period_t)
                if headways:
                    avg = mean(headways)
                    print(f"  {period_name:<16} {len(period_t):<8} {format_duration(avg):<14}")
                else:
                    print(f"  {period_name:<16} {len(period_t):<8} N/A")
            else:
                print(f"  {period_name:<16} {len(period_t):<8} N/A")

    print()

    # ========================================================================
    # KEY FINDINGS & RECOMMENDATIONS
    # ========================================================================
    print("=" * 80)
    print("KEY FINDINGS & RECOMMENDATIONS")
    print("=" * 80)
    print()

    print("1. PATH STORAGE STRATEGY:")
    print("-" * 40)
    pct_consistent = 100 * consistent_count / total_rd
    pct_trips_consistent = 100 * total_trips_consistent / (total_trips_consistent + total_trips_inconsistent)
    print(f"   {pct_consistent:.1f}% of route+directions use a SINGLE shape")
    print(f"   {pct_trips_consistent:.1f}% of ALL trips share geometry within their route+direction")
    print()
    if pct_consistent > 80:
        print("   RECOMMENDATION: YES, store ONE path per route+direction for most routes.")
        print("   For the few routes with variants, store multiple shapes and reference by shape_id.")
    else:
        print("   RECOMMENDATION: Store shape_id references and deduplicate shapes.")
        print("   Many routes have variants (express, short-turns, etc.)")
    print()

    print("2. SCHEDULE REGULARITY:")
    print("-" * 40)
    pct_regular = 100 * regular_count / len(headway_analysis)
    print(f"   {pct_regular:.1f}% of route+directions have regular headways (CV < 0.3)")
    print(f"   frequencies.txt present: {'YES' if has_frequencies else 'NO'}")
    print()
    if pct_regular > 70:
        print("   RECOMMENDATION: Headway-based tables are viable for most routes.")
        print("   Store: route_id, direction_id, period, headway_seconds")
        print("   Irregular routes need explicit departure times.")
    else:
        print("   RECOMMENDATION: Store explicit departure times for most routes.")
        print("   Headways vary too much for simple table-based approach.")
    print()

    print("3. GEOMETRY SHARING:")
    print("-" * 40)
    print(f"   Total unique shapes: {len(shapes)}")
    print(f"   Shapes shared across route+directions: {len(shared_shapes)}")
    if len(shared_shapes) > 0:
        print("   Some routes share track (e.g., trams on same street)")
    print()
    print("   RECOMMENDATION: Deduplicate shape storage at the shape_id level.")
    print("   Reference shapes by ID in trip/route definitions.")
    print()

    print("4. DATA SIZE OPTIMIZATION:")
    print("-" * 40)
    total_shape_points = sum(len(pts) for pts in shapes.values())
    total_trips_count = len(trips)

    # Current approach: each trip stores full path
    current_points = sum(len(shapes.get(trips[t].shape_id, [])) for t in trips if trips[t].shape_id)

    # Optimized approach: unique shapes only
    optimized_points = total_shape_points

    reduction = 100 * (1 - optimized_points / current_points) if current_points > 0 else 0

    print(f"   Total trips: {total_trips_count:,}")
    print(f"   Unique shapes: {len(shapes):,}")
    print(f"   Total shape points (all shapes): {total_shape_points:,}")
    print(f"   Points if stored per-trip: {current_points:,}")
    print(f"   Points if deduplicated: {optimized_points:,}")
    print(f"   Potential size reduction: {reduction:.1f}%")
    print()

    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    analyze_gtfs()
