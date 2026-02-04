#!/usr/bin/env python3
"""
Extract unique route paths from GTFS trips data.

Reads the GTFS trips JSON and extracts one representative path
per unique route (by route_short_name). This is the first step
in building the route-building spatial index.

Output: Dictionary mapping route names to route info including paths.
"""

import json
from pathlib import Path
from typing import Dict, Any


# Default paths
DEFAULT_TRIPS_PATH = Path("public/data/zurich-tram-trips.json")


def extract_routes(
    trips_path: Path = DEFAULT_TRIPS_PATH,
) -> Dict[str, Dict[str, Any]]:
    """
    Extract unique routes from GTFS trips data.

    For each unique route_short_name, takes the first trip's path
    as the representative geometry. All trips on the same route
    follow the same path (with minor variations we can ignore).

    Args:
        trips_path: Path to zurich-tram-trips.json

    Returns:
        Dictionary mapping route names to route info:
        {
            "4": {
                "route_short_name": "4",
                "route_id": "1-4-P-j26-1",
                "route_color": "#E12472",
                "route_type": 0,  # 0=tram, 3=bus
                "headsigns": ["Tiefenbrunnen", "Altstetten"],
                "path": [[lng, lat, elev], ...],
            },
            ...
        }
    """
    if not trips_path.exists():
        raise FileNotFoundError(f"Trips file not found: {trips_path}")

    with open(trips_path) as f:
        data = json.load(f)

    trips = data.get("trips", [])

    if not trips:
        raise ValueError("No trips found in GTFS data")

    # Group by route_short_name
    routes: Dict[str, Dict[str, Any]] = {}
    headsigns: Dict[str, set] = {}

    for trip in trips:
        name = trip.get("route_short_name")
        if not name:
            continue

        # Collect headsigns for this route
        if name not in headsigns:
            headsigns[name] = set()
        hs = trip.get("headsign")
        if hs:
            headsigns[name].add(hs)

        # Take first trip's path as representative
        if name not in routes:
            routes[name] = {
                "route_short_name": name,
                "route_id": trip.get("route_id"),
                "route_color": trip.get("route_color"),
                "route_type": trip.get("route_type"),
                "path": trip.get("path", []),
            }

    # Add headsigns list to each route
    for name, route in routes.items():
        route["headsigns"] = sorted(headsigns.get(name, []))

    return routes


def get_route_type_name(route_type: int) -> str:
    """Convert GTFS route_type to human-readable name."""
    types = {
        0: "tram",
        1: "metro",
        2: "rail",
        3: "bus",
        4: "ferry",
        5: "cable_car",
        6: "gondola",
        7: "funicular",
    }
    return types.get(route_type, "unknown")


def main():
    """Extract and save routes for inspection."""
    import argparse

    parser = argparse.ArgumentParser(description="Extract unique routes from GTFS")
    parser.add_argument("--input", type=Path, default=DEFAULT_TRIPS_PATH,
                        help="Path to GTFS trips JSON")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output path (JSON) - if not specified, prints summary")
    parser.add_argument("--json", action="store_true",
                        help="Print full JSON output")
    args = parser.parse_args()

    routes = extract_routes(args.input)

    if args.output:
        # Save to file
        with open(args.output, "w") as f:
            json.dump(routes, f, indent=2)
        print(f"Saved {len(routes)} routes to {args.output}")
    elif args.json:
        # Print full JSON
        print(json.dumps(routes, indent=2))
    else:
        # Print summary
        print(f"Extracted {len(routes)} unique routes:\n")

        # Group by type
        by_type: Dict[int, list] = {}
        for name, route in routes.items():
            rt = route.get("route_type", -1)
            if rt not in by_type:
                by_type[rt] = []
            by_type[rt].append((name, route))

        for rt, route_list in sorted(by_type.items()):
            type_name = get_route_type_name(rt)
            print(f"  {type_name.upper()} ({len(route_list)} routes):")

            # Sort by name (numeric if possible)
            def sort_key(item):
                name = item[0]
                try:
                    return (0, int(name))
                except ValueError:
                    return (1, name)

            for name, route in sorted(route_list, key=sort_key)[:10]:
                color = route.get("route_color", "N/A")
                path_len = len(route.get("path", []))
                hs = route.get("headsigns", [])[:2]
                hs_str = " / ".join(hs) if hs else "N/A"
                print(f"    {name:6s}  {color:8s}  {path_len:4d} pts  {hs_str}")

            if len(route_list) > 10:
                print(f"    ... and {len(route_list) - 10} more")
            print()


if __name__ == "__main__":
    main()
