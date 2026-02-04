#!/usr/bin/env python3
"""
Command-line interface for the photorealistic tile pipeline.

Usage:
    # Preview single tile at location
    python -m scripts.tile_pipeline.cli preview --lat 47.376 --lng 8.54 --zoom 16

    # Render tiles around a coordinate (200m radius by default)
    python -m scripts.tile_pipeline.cli render --lat 47.378 --lng 8.54 --radius 300

    # Render a predefined area
    python -m scripts.tile_pipeline.cli render --area hauptbahnhof --preset afternoon

    # Render custom bounds
    python -m scripts.tile_pipeline.cli render --bounds "8.52,47.37,8.56,47.39" --max-zoom 16

    # List available areas
    python -m scripts.tile_pipeline.cli areas

    # List available presets
    python -m scripts.tile_pipeline.cli presets
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def cmd_preview(args: argparse.Namespace) -> int:
    """Preview a single tile."""
    from .tile_renderer import preview_tile, preview_tile_rendered, TileCoord
    from .sources.satellite import wgs84_to_tile
    from .config import PipelineConfig
    from .time_presets import list_presets

    mode = getattr(args, "mode", "satellite")
    style = getattr(args, "style", "default")

    print(f"Rendering preview tile at ({args.lat}, {args.lng}) zoom {args.zoom}")
    print(f"Mode: {mode}")
    print(f"Time preset: {args.preset}")

    # Check Blender if needed (rendered mode or --use-blender)
    needs_blender = mode == "rendered" or args.use_blender
    if needs_blender:
        from .blender_shadows import BlenderShadowRenderer
        try:
            renderer = BlenderShadowRenderer()
            info = renderer.check_blender()
            if info.get("installed"):
                print(f"✓ Blender {info['version']} found at {info['path']}")
                print(f"  GPU device: {info['gpu_device']}")
                if mode == "rendered":
                    print(f"  Style: {style}")
                print(f"  Samples: {args.blender_samples}")
            else:
                print(f"✗ Blender check failed: {info.get('error', 'unknown')}")
                return 1
        except FileNotFoundError as e:
            print(f"✗ Blender not found: {e}")
            print("  Install: brew install --cask blender")
            return 1

    config = PipelineConfig()
    if args.output_dir:
        config.output.output_dir = Path(args.output_dir)

    try:
        if mode == "rendered":
            # Use full Blender rendering (no satellite)
            image = preview_tile_rendered(
                lat=args.lat,
                lng=args.lng,
                zoom=args.zoom,
                preset_name=args.preset,
                style_name=style,
                config=config,
                samples=args.blender_samples,
            )
        else:
            # Satellite mode (original)
            image = preview_tile(
                lat=args.lat,
                lng=args.lng,
                zoom=args.zoom,
                preset_name=args.preset,
                config=config,
                use_blender=args.use_blender,
                blender_samples=args.blender_samples,
            )

        # Save or display
        if args.output:
            output_path = Path(args.output)
        else:
            x, y = wgs84_to_tile(args.lng, args.lat, args.zoom)
            mode_suffix = f"_{mode}" if mode == "rendered" else ""
            style_suffix = f"_{style}" if mode == "rendered" else ""
            blender_suffix = "_blender" if args.use_blender and mode != "rendered" else ""
            output_path = Path(
                f"preview_{args.zoom}_{x}_{y}_{args.preset}{mode_suffix}{style_suffix}{blender_suffix}.png"
            )

        Image.fromarray(image).save(output_path)
        print(f"Saved to: {output_path}")

        # Print tile info
        x, y = wgs84_to_tile(args.lng, args.lat, args.zoom)
        coord = TileCoord(args.zoom, x, y)
        bounds = coord.bounds
        print(f"Tile: {coord}")
        print(f"Bounds: W={bounds[0]:.4f}, S={bounds[1]:.4f}, E={bounds[2]:.4f}, N={bounds[3]:.4f}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_render(args: argparse.Namespace) -> int:
    """Render tiles for a region."""
    from .tile_renderer import TileRenderer, RenderedTileRenderer, estimate_render_time
    from .config import PipelineConfig
    from .areas import get_area_bounds, get_area

    mode = getattr(args, "mode", "satellite")
    style = getattr(args, "style", "default")

    # Check Blender if needed (rendered mode or --use-blender)
    needs_blender = mode == "rendered" or args.use_blender
    if needs_blender:
        from .blender_shadows import BlenderShadowRenderer
        try:
            renderer = BlenderShadowRenderer()
            info = renderer.check_blender()
            if info.get("installed"):
                print(f"✓ Blender {info['version']} found at {info['path']}")
                print(f"  GPU device: {info['gpu_device']}")
            else:
                print(f"✗ Blender check failed: {info.get('error', 'unknown')}")
                return 1
        except FileNotFoundError as e:
            print(f"✗ Blender not found: {e}")
            print("  Install: brew install --cask blender")
            return 1

    config = PipelineConfig()
    if args.output_dir:
        config.output.output_dir = Path(args.output_dir)

    # Parse bounds - priority: --area > --lat/--lng > --bounds > default
    if args.area:
        try:
            area = get_area(args.area)
            bounds = area.bounds
            print(f"Using area: {area.name} - {area.description}")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    elif args.lat is not None and args.lng is not None:
        # Convert lat/lng + radius to bounds
        # At Zürich latitude (~47°N):
        # 1° latitude ≈ 111,320m
        # 1° longitude ≈ 75,500m (cos(47°) * 111,320)
        import math
        lat_deg_per_m = 1 / 111320
        lng_deg_per_m = 1 / (111320 * math.cos(math.radians(args.lat)))

        radius = args.radius
        lat_offset = radius * lat_deg_per_m
        lng_offset = radius * lng_deg_per_m

        bounds = (
            args.lng - lng_offset,  # west
            args.lat - lat_offset,  # south
            args.lng + lng_offset,  # east
            args.lat + lat_offset,  # north
        )
        print(f"Using center: ({args.lat}, {args.lng}) with {radius}m radius")
    elif args.bounds:
        try:
            parts = [float(x.strip()) for x in args.bounds.split(",")]
            if len(parts) != 4:
                raise ValueError("Bounds must have 4 values")
            bounds = tuple(parts)
        except ValueError as e:
            print(f"Invalid bounds format: {e}", file=sys.stderr)
            print("Expected: west,south,east,north (e.g., 8.52,47.37,8.56,47.39)")
            return 1
    else:
        bounds = config.bounds

    min_zoom = args.min_zoom if args.min_zoom is not None else config.min_zoom
    max_zoom = args.max_zoom if args.max_zoom is not None else config.max_zoom

    print(f"Rendering tiles for region: {bounds}")
    print(f"Zoom levels: {min_zoom} - {max_zoom}")
    print(f"Mode: {mode}")
    print(f"Time preset: {args.preset}")
    print(f"Output: {config.output.output_dir}")
    if mode == "rendered":
        print(f"Style: {style}")
        print(f"Samples: {args.blender_samples}")
    elif args.use_blender:
        print(f"Blender shadows: enabled ({args.blender_samples} samples)")

    # Create appropriate renderer based on mode
    if mode == "rendered":
        renderer = RenderedTileRenderer(
            config=config,
            preset_name=args.preset,
            style_name=style,
            samples=args.blender_samples,
        )
    else:
        renderer = TileRenderer(
            config,
            args.preset,
            use_blender=args.use_blender,
            blender_samples=args.blender_samples,
        )

    # Count tiles
    total_tiles = renderer.count_tiles(bounds, min_zoom, max_zoom)
    print(f"Total tiles: {total_tiles}")
    print(f"Estimated time: {estimate_render_time(total_tiles, workers=args.workers)}")

    if args.dry_run:
        print("Dry run - not rendering")
        return 0

    # Confirm if many tiles
    if total_tiles > 100 and not args.yes:
        response = input(f"Render {total_tiles} tiles? [y/N] ")
        if response.lower() != "y":
            print("Cancelled")
            return 0

    # Render
    try:
        if args.workers > 1:
            paths = renderer.render_parallel(
                bounds=bounds,
                min_zoom=min_zoom,
                max_zoom=max_zoom,
                workers=args.workers,
                progress=True,
            )
        else:
            paths = renderer.render_all(
                bounds=bounds,
                min_zoom=min_zoom,
                max_zoom=max_zoom,
                progress=True,
            )

        print(f"Rendered {len(paths)} tiles")
        return 0

    except KeyboardInterrupt:
        print("\nCancelled")
        return 130

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_presets(args: argparse.Namespace) -> int:
    """List available time presets."""
    from .time_presets import PRESETS

    print("Available time presets:\n")
    for name, preset in sorted(PRESETS.items()):
        print(f"  {name}")
        print(f"    {preset.description}")
        print(f"    Sun: azimuth={preset.azimuth}°, altitude={preset.altitude}°")
        print()

    return 0


def cmd_styles(args: argparse.Namespace) -> int:
    """List available render styles."""
    from .materials import STYLES

    print("Available render styles (for --mode rendered):\n")
    for name, style in sorted(STYLES.items()):
        print(f"  {name}")
        print(f"    {style.description}")
        # Show key colors
        wall = style.building_wall
        roof = style.building_roof
        foliage = style.tree_foliage
        print(f"    Buildings: wall=({wall[0]:.2f},{wall[1]:.2f},{wall[2]:.2f}), "
              f"roof=({roof[0]:.2f},{roof[1]:.2f},{roof[2]:.2f})")
        print(f"    Trees: foliage=({foliage[0]:.2f},{foliage[1]:.2f},{foliage[2]:.2f})")
        print(f"    Lighting: sun={style.sun_strength}, ambient={style.ambient_strength}")
        print()

    print("Usage: python -m scripts.tile_pipeline.cli render --area hb --mode rendered --style <name>")

    return 0


def cmd_areas(args: argparse.Namespace) -> int:
    """List predefined Zürich areas."""
    from .areas import AREAS, estimate_tiles

    print("Predefined Zürich areas:\n")

    # Group by category
    categories = {
        "Central": ["hauptbahnhof", "bellevue", "limmatquai", "niederdorf", "bahnhofstrasse"],
        "University": ["eth", "polyterrasse"],
        "Churches & Museums": ["grossmuenster", "fraumuenster", "landesmuseum"],
        "Districts": ["zurich_west", "oerlikon", "seefeld", "enge", "wiedikon", "altstetten", "wipkingen"],
        "Lakefront": ["buerkliplatz", "utoquai"],
        "Demo/Test": ["demo_small", "demo_medium", "city_center"],
        "Full Coverage": ["full_zurich"],
    }

    for category, keys in categories.items():
        print(f"  {category}:")
        for key in keys:
            if key in AREAS:
                area = AREAS[key]
                tiles = estimate_tiles(area.bounds, 16)
                print(f"    {key:20s}  ~{tiles:3d} tiles (z16)  {area.description}")
        print()

    print("Usage: python -m scripts.tile_pipeline.cli render --area <name>")

    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Show information about data sources."""
    from .config import PipelineConfig

    config = PipelineConfig()

    print("Data Sources:")
    print(f"  Satellite: {config.sources.swissimage_url}")
    print(f"  Elevation: {config.sources.elevation_url}")
    print(f"  Buildings: {config.sources.buildings_path}")
    print(f"  Trees: {config.sources.trees_path}")

    print("\nChecking availability:")

    # Check buildings
    buildings_path = config.sources.buildings_path
    if buildings_path.exists():
        import json
        with open(buildings_path) as f:
            data = json.load(f)
            count = len(data.get("features", []))
        print(f"  Buildings: {count} features")
    else:
        print(f"  Buildings: NOT FOUND at {buildings_path}")

    # Check trees
    trees_path = config.sources.trees_path
    if trees_path.exists():
        import json
        with open(trees_path) as f:
            data = json.load(f)
            count = len(data.get("features", []))
        print(f"  Trees: {count} features")
    else:
        print(f"  Trees: NOT FOUND at {trees_path}")

    print("\nDefault Zurich bounds:")
    print(f"  West: {config.bounds[0]}")
    print(f"  South: {config.bounds[1]}")
    print(f"  East: {config.bounds[2]}")
    print(f"  North: {config.bounds[3]}")

    return 0


# =============================================================================
# SPATIAL QUERY COMMANDS
# =============================================================================


def cmd_shadow(args: argparse.Namespace) -> int:
    """Query shadow at a 3D point."""
    from datetime import datetime, timezone
    from .query import get_shadow_at
    import json as json_module

    # Parse time
    try:
        time = datetime.strptime(f"{args.date} {args.time}", "%Y-%m-%d %H:%M")
        # Add UTC timezone for pysolar
        time = time.replace(tzinfo=timezone.utc)
    except ValueError as e:
        print(f"Error parsing date/time: {e}", file=sys.stderr)
        return 1

    # Calculate height from floor if specified
    height = args.height
    if args.floor is not None:
        height = (args.floor * 3.0) + 1.5  # 3m per floor + 1.5m standing

    try:
        result = get_shadow_at(args.lat, args.lng, time, height=height)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    if args.json:
        print(json_module.dumps(result.to_dict(), indent=2))
    else:
        pct = int(result.shadow * 100)
        status = "shaded" if pct > 50 else "sunny"
        height_desc = f"floor {args.floor}" if args.floor is not None else f"{height}m"
        print(f"📍 ({result.latitude:.5f}, {result.longitude:.5f}) at {height_desc}")
        print(f"🕐 {result.time.strftime('%Y-%m-%d %H:%M')}")
        if result.source == "night":
            print(f"🌙 Sun below horizon (night)")
        else:
            icon = "🌥️" if pct > 50 else "☀️"
            print(f"{icon} Shadow: {pct}% ({status})")

    return 0


def cmd_balcony(args: argparse.Namespace) -> int:
    """Analyze sun exposure for a balcony throughout the day."""
    from datetime import datetime, timezone
    from .query import get_balcony_sun_exposure
    import json as json_module

    try:
        date = datetime.strptime(args.date, "%Y-%m-%d")
        date = date.replace(tzinfo=timezone.utc)
    except ValueError as e:
        print(f"Error parsing date: {e}", file=sys.stderr)
        return 1

    try:
        result = get_balcony_sun_exposure(args.lat, args.lng, args.floor, date)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    if args.json:
        print(json_module.dumps(result, indent=2))
    else:
        print(f"🏠 Balcony sun analysis")
        print(f"📍 ({args.lat:.5f}, {args.lng:.5f})")
        print(f"🏢 Floor {args.floor} ({result['balcony_height_m']:.1f}m above ground)")
        print(f"📅 {args.date}")
        print()
        print(f"☀️ Total sun: {result['total_sun_hours']:.1f} hours")
        if result['best_time']:
            print(f"✨ Best time: {result['best_time']}")
        print()
        if result['sunny_periods']:
            print("Sunny periods:")
            for start, end in result['sunny_periods']:
                print(f"  ☀️ {start} - {end}")
        else:
            print("⛅ No direct sun on this day")
        print()
        print("Timeline:")
        for point in result['timeline']:
            # Create visual bar
            sun_level = 1 - point['shadow']
            bar_filled = int(sun_level * 20)
            bar_empty = 20 - bar_filled
            bar = "█" * bar_filled + "░" * bar_empty
            icon = "☀️" if point['shadow'] < 0.5 else "🌥️"
            print(f"  {point['time']} {bar} {icon}")

    return 0


def cmd_shadow_timeline(args: argparse.Namespace) -> int:
    """Query shadow timeline for a point."""
    from datetime import datetime, timezone
    from .query import get_shadow_timeline
    import json as json_module

    try:
        date = datetime.strptime(args.date, "%Y-%m-%d")
        date = date.replace(tzinfo=timezone.utc)
    except ValueError as e:
        print(f"Error parsing date: {e}", file=sys.stderr)
        return 1

    # Calculate height from floor if specified
    height = args.height
    if args.floor is not None:
        height = (args.floor * 3.0) + 1.5

    try:
        results = get_shadow_timeline(args.lat, args.lng, date, height=height)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    if args.json:
        print(json_module.dumps([r.to_dict() for r in results], indent=2))
    else:
        height_desc = f"floor {args.floor}" if args.floor is not None else f"{height}m"
        print(f"📍 Shadow timeline for ({args.lat:.5f}, {args.lng:.5f}) at {height_desc}")
        print(f"📅 {args.date}")
        print()

        # Calculate sun hours
        sunny_count = sum(1 for r in results if r.shadow < 0.5)
        total_sun_hours = sunny_count  # 1-hour intervals by default
        print(f"☀️ Total sun: ~{total_sun_hours} hours")
        print()

        for r in results:
            # Create visual bar (inverted: sun level)
            sun_level = 1 - r.shadow
            bar_filled = int(sun_level * 20)
            bar_empty = 20 - bar_filled
            bar = "█" * bar_filled + "░" * bar_empty

            pct = int(r.shadow * 100)
            if r.source == "night":
                status = "🌙"
            elif pct > 50:
                status = "🌥️"
            else:
                status = "☀️"

            print(f"  {r.time.strftime('%H:%M')} {bar} {pct:3d}% {status}")

    return 0


def cmd_nearest(args: argparse.Namespace) -> int:
    """Find nearest amenity."""
    from .query import find_nearest_amenity
    import json as json_module

    try:
        result = find_nearest_amenity(args.lat, args.lng, args.type)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if result is None:
        print(f"No {args.type} found within 500m")
        return 1

    if args.json:
        print(json_module.dumps(result.to_dict(), indent=2))
    else:
        icon = {'bench': '🪑', 'fountain': '⛲', 'toilet': '🚻'}.get(args.type, '📍')
        print(f"{icon} Nearest {args.type}:")
        print(f"   Location: ({result.latitude:.5f}, {result.longitude:.5f})")
        print(f"   Distance: {result.distance_m}m")
        if result.properties:
            for key, value in result.properties.items():
                if value and key not in ('id', 'ogc_fid'):
                    print(f"   {key}: {value}")

    return 0


def cmd_find_amenities(args: argparse.Namespace) -> int:
    """Find amenities within radius."""
    from .query import find_amenities_within
    import json as json_module

    try:
        results = find_amenities_within(
            args.lat, args.lng, args.type,
            radius_m=args.radius,
            limit=args.limit
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not results:
        print(f"No {args.type} found within {args.radius}m")
        return 1

    if args.json:
        print(json_module.dumps([r.to_dict() for r in results], indent=2))
    else:
        icon = {'bench': '🪑', 'fountain': '⛲', 'toilet': '🚻'}.get(args.type, '📍')
        print(f"{icon} Found {len(results)} {args.type}(s) within {args.radius}m:")
        print()
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result.distance_m}m away")
            print(f"     ({result.latitude:.5f}, {result.longitude:.5f})")

    return 0


# =============================================================================
# ROUTE-BUILDING QUERY COMMANDS
# =============================================================================


def cmd_route_buildings(args: argparse.Namespace) -> int:
    """Query buildings along a transit route."""
    from .query import get_buildings_along_route, list_routes
    import json as json_module

    if args.list:
        # List all routes
        routes = list_routes(route_type=args.type)

        # Sort by specified feature
        sort_key = args.sort_by or "buildings"
        sort_map = {
            "buildings": lambda r: r.building_count,
            "benches": lambda r: r.bench_count,
            "fountains": lambda r: r.fountain_count,
            "toilets": lambda r: r.toilet_count,
            "trees": lambda r: r.tree_count,
            "length": lambda r: r.path_length_km,
        }
        if sort_key in sort_map:
            routes.sort(key=sort_map[sort_key], reverse=True)

        if args.json:
            print(json_module.dumps([r.to_dict() for r in routes], indent=2))
        else:
            sort_label = sort_key.replace("_", " ")
            print(f"Transit routes sorted by {sort_label} ({len(routes)} total):\n")

            # Group by type
            by_type = {}
            for r in routes:
                if r.route_type not in by_type:
                    by_type[r.route_type] = []
                by_type[r.route_type].append(r)

            for rtype, rlist in sorted(by_type.items()):
                # Re-sort each group
                rlist.sort(key=sort_map.get(sort_key, lambda r: r.building_count), reverse=True)
                print(f"  {rtype.upper()} ({len(rlist)} routes):")
                for r in rlist[:args.limit]:
                    print(f"    {r.route_name:6s}  "
                          f"{r.building_count:5d} 🏠  "
                          f"{r.bench_count:3d} 🪑  "
                          f"{r.fountain_count:2d} ⛲  "
                          f"{r.toilet_count:2d} 🚻  "
                          f"{r.path_length_km:5.1f} km")
                if len(rlist) > args.limit:
                    print(f"    ... and {len(rlist) - args.limit} more")
                print()

        return 0

    # Query specific route
    if not args.route:
        print("Error: --route or --list required", file=sys.stderr)
        return 1

    result = get_buildings_along_route(
        args.route,
        include_building_ids=args.include_ids,
    )

    if result is None:
        print(f"Route not found: {args.route}", file=sys.stderr)
        # List similar routes
        routes = list_routes()
        similar = [r for r in routes if args.route.lower() in r.route_name.lower()]
        if similar:
            print(f"Did you mean: {', '.join(r.route_name for r in similar[:5])}")
        return 1

    if args.json:
        print(json_module.dumps(result.to_dict(), indent=2))
    else:
        icon = {"tram": "🚋", "bus": "🚌", "rail": "🚂", "funicular": "🚡"}.get(result.route_type, "🚍")
        print(f"{icon} Route {result.route_name} ({result.route_type})")
        print(f"📏 Route length: {result.path_length_km:.1f} km")
        if result.headsigns:
            print(f"🚏 Destinations: {' / '.join(result.headsigns[:2])}")
        if result.route_color:
            print(f"🎨 Color: {result.route_color}")
        print()
        print("Features within 50m:")
        print(f"  🏠 Buildings: {result.building_count}")
        print(f"  🌳 Trees: {result.tree_count}")
        print(f"  🪑 Benches: {result.bench_count}")
        print(f"  ⛲ Fountains: {result.fountain_count}")
        print(f"  🚻 Toilets: {result.toilet_count}")

    return 0


def cmd_route_stats(args: argparse.Namespace) -> int:
    """Show route-building index statistics."""
    from .query import get_route_statistics
    import json as json_module

    stats = get_route_statistics()

    if args.json:
        print(json_module.dumps(stats, indent=2))
    else:
        print("Route-Building Index Statistics")
        print("=" * 40)
        print(f"Total routes: {stats['total_routes']}")
        print(f"Buildings indexed: {stats['total_buildings_indexed']}")
        print(f"Buffer distance: {stats['buffer_m']}m")
        print()
        print(f"Most buildings:  Route {stats['max_buildings_route']} ({stats['max_buildings_count']} buildings)")
        print(f"Least buildings: Route {stats['min_buildings_route']} ({stats['min_buildings_count']} buildings)")
        print(f"Longest route:   Route {stats['max_length_route']} ({stats['max_length_km']} km)")
        print()
        print("By transit type:")
        for ttype, data in sorted(stats.get("by_type", {}).items()):
            avg_buildings = data["total_buildings"] // data["count"] if data["count"] > 0 else 0
            print(f"  {ttype:10s}: {data['count']:3d} routes, "
                  f"{data['total_buildings']:6d} buildings total ({avg_buildings} avg)")
        print()
        print(f"Index created: {stats.get('created', 'Unknown')}")

    return 0


def cmd_compare_routes(args: argparse.Namespace) -> int:
    """Compare multiple transit routes."""
    from .query import compare_routes
    import json as json_module

    if len(args.routes) < 2:
        print("Error: Need at least 2 routes to compare", file=sys.stderr)
        return 1

    result = compare_routes(args.routes)

    if args.json:
        print(json_module.dumps(result, indent=2))
    else:
        print("Route Comparison")
        print("=" * 40)
        for r in result.get("routes", []):
            print(f"  Route {r['route_name']}: {r['building_count']} buildings, "
                  f"{r['path_length_km']:.1f} km")
        print()
        print(f"Shared buildings: {result['shared_building_count']}")
        print(f"Total unique buildings: {result['total_unique_buildings']}")

    return 0


def cmd_path_stats(args: argparse.Namespace) -> int:
    """Analyze what you passed along a path."""
    from .query import analyze_user_path
    import json as json_module

    # Parse path from "lng,lat;lng,lat;..." format
    try:
        coords = []
        for point in args.path.split(";"):
            lng, lat = map(float, point.strip().split(","))
            coords.append((lng, lat))
    except ValueError as e:
        print(f"Error parsing path: {e}", file=sys.stderr)
        print("Expected format: lng,lat;lng,lat;lng,lat")
        return 1

    result = analyze_user_path(coords, buffer_m=args.buffer)

    if args.json:
        print(json_module.dumps(result, indent=2))
    else:
        print("Path Analysis")
        print("=" * 40)
        print(f"📏 Distance: {result['distance_km']:.2f} km")
        print(f"📍 Points: {result['path_points']}")
        print(f"🏠 Buildings passed: {result['buildings_passed']}")
        print(f"↔️ Buffer: {result['buffer_m']}m")

    return 0


# =============================================================================
# AI TILE GENERATION COMMANDS
# =============================================================================


def cmd_ai_styles(args: argparse.Namespace) -> int:
    """List available AI tile generation styles."""
    from .ai_tile_generator import STYLES, check_api_availability

    print("Available AI tile generation styles:\n")

    for name, style in sorted(STYLES.items()):
        print(f"  {name}")
        print(f"    {style.description}")
        if style.dominant_colors:
            colors = " ".join(style.dominant_colors[:4])
            print(f"    Colors: {colors}")
        print()

    # Show API status
    print("-" * 50)
    if check_api_availability():
        print("✓ API key configured (GOOGLE_API_KEY)")
    else:
        print("✗ API key NOT configured")
        print("  Set GOOGLE_API_KEY environment variable")
        print("  Get one at: https://aistudio.google.com/apikey")

    print()
    print("Usage: python -m scripts.tile_pipeline.cli ai-generate --tile 16/34322/22950 --style <name>")

    return 0


def cmd_ai_generate(args: argparse.Namespace) -> int:
    """Generate an AI-stylized tile."""
    from .ai_tile_generator import (
        generate_stylized_tile,
        load_blender_tile,
        check_api_availability,
        list_ai_styles,
    )
    import json as json_module

    # Check API availability
    if not check_api_availability():
        print("Error: GOOGLE_API_KEY not set", file=sys.stderr)
        print("Get an API key at: https://aistudio.google.com/apikey")
        return 1

    # Validate style
    available_styles = list_ai_styles()
    if args.style.lower() not in available_styles:
        print(f"Error: Unknown style '{args.style}'", file=sys.stderr)
        print(f"Available styles: {', '.join(sorted(available_styles.keys()))}")
        return 1

    # Check that Blender tile exists
    blender_dir = Path(args.blender_dir) if args.blender_dir else None
    blender_image = load_blender_tile(args.tile, blender_dir)
    if blender_image is None:
        print(f"Error: Blender tile not found: {args.tile}", file=sys.stderr)
        print("Render it first with:")
        print(f"  python -m scripts.tile_pipeline.cli render --tile {args.tile}")
        return 1

    print(f"Generating AI tile: {args.tile}")
    print(f"Style: {args.style}")
    print(f"Blender source: {blender_image.shape}")

    try:
        result = generate_stylized_tile(
            tile_coord=args.tile,
            style=args.style,
            blender_tiles_dir=blender_dir,
            use_cache=not args.no_cache,
        )

        # Save output
        if args.output:
            output_path = Path(args.output)
        else:
            safe_style = args.style.lower().replace(" ", "_")
            output_path = Path(f"ai_tile_{args.tile.replace('/', '_')}_{safe_style}.png")

        Image.fromarray(result.image).save(output_path)

        if args.json:
            output_info = result.to_dict()
            output_info["output_path"] = str(output_path)
            print(json_module.dumps(output_info, indent=2))
        else:
            if result.cached:
                print(f"✓ Loaded from cache")
            else:
                print(f"✓ Generated in {result.processing_time_ms}ms")
            print(f"✓ Saved to: {output_path}")
            print(f"  Model: {result.model}")
            print(f"  Size: {result.image.shape[1]}×{result.image.shape[0]}")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"API Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_set_style_reference(args: argparse.Namespace) -> int:
    """Set the reference image for a style."""
    import shutil
    from .ai_tile_generator import STYLES

    # Validate style
    style_lower = args.style.lower()
    if style_lower not in STYLES:
        print(f"Error: Unknown style '{args.style}'", file=sys.stderr)
        print(f"Available styles: {', '.join(sorted(STYLES.keys()))}")
        return 1

    # Check source image exists
    source_path = Path(args.image)
    if not source_path.exists():
        print(f"Error: Image not found: {args.image}", file=sys.stderr)
        return 1

    # Destination path
    dest_dir = Path("public/tiles/style-references")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{style_lower}-reference.webp"

    # Copy/convert the image
    try:
        # Open and resize to 512x512 if needed, save as webp
        img = Image.open(source_path)
        if img.size != (512, 512):
            img = img.resize((512, 512), Image.LANCZOS)
        img = img.convert("RGB")
        img.save(dest_path, quality=90)

        print(f"✓ Set reference image for '{args.style}' style")
        print(f"  Source: {source_path}")
        print(f"  Saved: {dest_path}")
        print(f"  Size: 512×512")

        # Show style info
        style = STYLES[style_lower]
        print(f"\nStyle: {style.name}")
        print(f"  {style.description}")
        print(f"  Temperature: {style.temperature}")

        return 0

    except Exception as e:
        print(f"Error processing image: {e}", file=sys.stderr)
        return 1


def cmd_sd_styles(args: argparse.Namespace) -> int:
    """List available SD (Stable Diffusion) tile generation styles."""
    from .sd_tile_generator import SD_STYLES, check_sd_api_availability

    print("Available SD (Stable Diffusion) tile generation styles:\n")

    for name, style in sorted(SD_STYLES.items()):
        print(f"  {name}")
        print(f"    {style.description}")
        print(f"    Seed: {style.seed} (deterministic)")
        print(f"    ControlNet Scale: {style.controlnet_conditioning_scale}")
        print()

    # Show API status
    print("-" * 50)
    if check_sd_api_availability():
        print("   Replicate API token configured (REPLICATE_API_TOKEN)")
    else:
        print("✗ Replicate API token NOT configured")
        print("  Set REPLICATE_API_TOKEN environment variable")
        print("  Get one at: https://replicate.com/account/api-tokens")

    print()
    print("Usage: python -m scripts.tile_pipeline.cli sd-generate --tile 16/34322/22950 --style <name>")

    return 0


def cmd_sd_generate(args: argparse.Namespace) -> int:
    """Generate an SD-stylized tile using ControlNet Depth."""
    from .sd_tile_generator import (
        SDTileGenerator,
        load_depth_tile,
        check_sd_api_availability,
        list_sd_styles,
    )
    from .ai_tile_generator import load_blender_tile
    import json as json_module

    # Check API availability
    if not check_sd_api_availability():
        print("Error: REPLICATE_API_TOKEN not set", file=sys.stderr)
        print("Get an API token at: https://replicate.com/account/api-tokens")
        return 1

    # Validate style
    available_styles = list_sd_styles()
    if args.style.lower() not in available_styles:
        print(f"Error: Unknown style '{args.style}'", file=sys.stderr)
        print(f"Available styles: {', '.join(sorted(available_styles.keys()))}")
        return 1

    # Load Blender RGB tile (required)
    blender_dir = Path(args.blender_dir) if args.blender_dir else None
    blender_image = load_blender_tile(args.tile, blender_dir)
    if blender_image is None:
        print(f"Error: Blender tile not found: {args.tile}", file=sys.stderr)
        print("Generate Blender tiles first with:")
        print(f"  python -m scripts.tile_pipeline.cli render --area city_center")
        return 1

    # Load depth tile (optional - will be estimated if not found)
    depth_dir = Path(args.depth_dir) if args.depth_dir else None
    depth_map = load_depth_tile(args.tile, depth_dir)
    if depth_map is None:
        print("Note: No depth tile found - will estimate depth using MiDaS")

    print(f"Generating SD tile: {args.tile}")
    print(f"Style: {args.style}")
    print(f"Seed: {args.seed}")
    if depth_map is not None:
        print(f"Depth map: {depth_map.shape}")
    else:
        print(f"Depth map: Will estimate from Blender tile")

    try:
        generator = SDTileGenerator()
        result = generator.generate(
            blender_image=blender_image,
            depth_map=depth_map,
            style=args.style,
            tile_coord=args.tile,
            seed=args.seed,
            use_cache=not args.no_cache,
        )

        # Save output
        if args.output:
            output_path = Path(args.output)
        else:
            safe_style = args.style.lower().replace(" ", "_")
            output_path = Path(f"sd_tile_{args.tile.replace('/', '_')}_{safe_style}.png")

        Image.fromarray(result.image).save(output_path)

        if args.json:
            output_info = result.to_dict()
            output_info["output_path"] = str(output_path)
            print(json_module.dumps(output_info, indent=2))
        else:
            if result.cached:
                print(f"✓ Loaded from cache")
            else:
                print(f"✓ Generated in {result.processing_time_ms}ms")
            print(f"✓ Saved to: {output_path}")
            print(f"  Model: {result.model}")
            print(f"  Seed: {result.seed}")
            print(f"  Size: {result.image.shape[1]}×{result.image.shape[0]}")

        return 0

    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Install with: pip install replicate")
        return 1
    except ValueError as e:
        print(f"API Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_sd_generate_area(args: argparse.Namespace) -> int:
    """Generate SD-stylized tiles for an area."""
    from .sd_tile_generator import (
        generate_sd_tiles_for_area,
        check_sd_api_availability,
        list_sd_styles,
    )
    from .areas import get_area

    # Check API availability
    if not check_sd_api_availability():
        print("Error: REPLICATE_API_TOKEN not set", file=sys.stderr)
        print("Get an API token at: https://replicate.com/account/api-tokens")
        return 1

    # Validate style
    available_styles = list_sd_styles()
    if args.style.lower() not in available_styles:
        print(f"Error: Unknown style '{args.style}'", file=sys.stderr)
        print(f"Available styles: {', '.join(sorted(available_styles.keys()))}")
        return 1

    # Get bounds
    bounds = None
    if args.area:
        try:
            area = get_area(args.area)
            bounds = area.bounds
            print(f"Area: {area.name} - {area.description}")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Set directories
    output_dir = Path(args.output_dir) if args.output_dir else None
    depth_dir = Path(args.depth_dir) if args.depth_dir else None
    blender_dir = Path(args.blender_dir) if args.blender_dir else None

    try:
        paths = generate_sd_tiles_for_area(
            style=args.style,
            zoom=args.zoom,
            bounds=bounds,
            output_dir=output_dir,
            depth_dir=depth_dir,
            blender_dir=blender_dir,
            seed=args.seed,
            use_cache=not args.no_cache,
            progress=True,
        )

        print(f"\n✓ Generated {len(paths)} SD tiles")
        if paths:
            print(f"  Output: {paths[0].parent}")

        return 0

    except KeyboardInterrupt:
        print("\nCancelled")
        return 130
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Install with: pip install replicate")
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_satellite_styles(args: argparse.Namespace) -> int:
    """List available satellite style transfer styles (InstructPix2Pix)."""
    from .sd_tile_generator import IMG2IMG_STYLES, check_sd_api_availability

    print("Available satellite style transfer styles (InstructPix2Pix - RECOMMENDED):\n")
    print("These styles transform real satellite imagery while preserving structure.")
    print("InstructPix2Pix is designed for image editing, not generation.\n")

    for name, style in sorted(IMG2IMG_STYLES.items()):
        print(f"  {name}")
        print(f"    {style.description}")
        print(f"    Image guidance: {style.image_guidance_scale} (higher = more faithful to original)")
        print(f"    Seed: {style.seed}")
        print()

    # Show API status
    print("-" * 50)
    if check_sd_api_availability():
        print("✓ Replicate API token configured (REPLICATE_API_TOKEN)")
    else:
        print("✗ Replicate API token NOT configured")
        print("  Set REPLICATE_API_TOKEN environment variable")
        print("  Get one at: https://replicate.com/account/api-tokens")

    print()
    print("Usage: python -m scripts.tile_pipeline.cli satellite-style --tile 16/34322/22950 --style <name>")
    print("       python -m scripts.tile_pipeline.cli satellite-style-area --area city_center --style winter")

    return 0


def cmd_satellite_style(args: argparse.Namespace) -> int:
    """Generate a satellite-styled tile using InstructPix2Pix."""
    from .sd_tile_generator import (
        SatelliteStyleTransfer,
        load_satellite_tile,
        check_sd_api_availability,
        list_img2img_styles,
    )
    import json as json_module

    # Check API availability
    if not check_sd_api_availability():
        print("Error: REPLICATE_API_TOKEN not set", file=sys.stderr)
        print("Get an API token at: https://replicate.com/account/api-tokens")
        return 1

    # Validate style
    available_styles = list_img2img_styles()
    if args.style.lower() not in available_styles:
        print(f"Error: Unknown style '{args.style}'", file=sys.stderr)
        print(f"Available styles: {', '.join(sorted(available_styles.keys()))}")
        return 1

    # Load satellite tile
    satellite_image = load_satellite_tile(args.tile)
    if satellite_image is None:
        print(f"Fetching satellite tile: {args.tile}")
        # Try to fetch it
        satellite_image = load_satellite_tile(args.tile)
        if satellite_image is None:
            print(f"Error: Could not fetch satellite tile: {args.tile}", file=sys.stderr)
            return 1

    print(f"Transforming satellite tile: {args.tile}")
    print(f"Style: {args.style}")
    print(f"Seed: {args.seed}")
    print(f"Image guidance scale: {args.image_guidance if args.image_guidance else 'default (1.8)'}")
    print(f"Input shape: {satellite_image.shape}")

    try:
        transfer = SatelliteStyleTransfer()
        result = transfer.transform(
            satellite_image=satellite_image,
            style=args.style,
            tile_coord=args.tile,
            seed=args.seed,
            image_guidance_scale=args.image_guidance,
            use_cache=not args.no_cache,
        )

        # Save output
        if args.output:
            output_path = Path(args.output)
        else:
            safe_style = args.style.lower().replace(" ", "_")
            output_path = Path(f"satellite_tile_{args.tile.replace('/', '_')}_{safe_style}.png")

        Image.fromarray(result.image).save(output_path)

        if args.json:
            output_info = result.to_dict()
            output_info["output_path"] = str(output_path)
            print(json_module.dumps(output_info, indent=2))
        else:
            if result.cached:
                print(f"✓ Loaded from cache")
            else:
                print(f"✓ Generated in {result.processing_time_ms}ms")
            print(f"✓ Saved to: {output_path}")
            print(f"  Model: {result.model}")
            print(f"  Seed: {result.seed}")
            print(f"  Image guidance scale: {result.image_guidance_scale}")
            print(f"  Size: {result.image.shape[1]}×{result.image.shape[0]}")

        return 0

    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Install with: pip install replicate")
        return 1
    except ValueError as e:
        print(f"API Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_satellite_style_area(args: argparse.Namespace) -> int:
    """Generate satellite-styled tiles for an area."""
    from .sd_tile_generator import (
        generate_satellite_styled_tiles,
        check_sd_api_availability,
        list_img2img_styles,
    )
    from .areas import get_area

    # Check API availability
    if not check_sd_api_availability():
        print("Error: REPLICATE_API_TOKEN not set", file=sys.stderr)
        print("Get an API token at: https://replicate.com/account/api-tokens")
        return 1

    # Validate style
    available_styles = list_img2img_styles()
    if args.style.lower() not in available_styles:
        print(f"Error: Unknown style '{args.style}'", file=sys.stderr)
        print(f"Available styles: {', '.join(sorted(available_styles.keys()))}")
        return 1

    # Get bounds
    bounds = None
    if args.area:
        try:
            area = get_area(args.area)
            bounds = area.bounds
            print(f"Area: {area.name} - {area.description}")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Set output directory
    output_dir = Path(args.output_dir) if args.output_dir else None

    try:
        paths = generate_satellite_styled_tiles(
            style=args.style,
            zoom=args.zoom,
            bounds=bounds,
            output_dir=output_dir,
            seed=args.seed,
            image_guidance_scale=args.image_guidance,
            use_cache=not args.no_cache,
            progress=True,
            rate_limit_delay=args.rate_limit,
        )

        print(f"\n✓ Generated {len(paths)} satellite-styled tiles")
        if paths:
            print(f"  Output: {paths[0].parent}")

        return 0

    except KeyboardInterrupt:
        print("\nCancelled")
        return 130
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Install with: pip install replicate")
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_hybrid_snow(args: argparse.Namespace) -> int:
    """Generate a single hybrid snow tile (satellite + procedural snow)."""
    from .hybrid_snow import generate_hybrid_snow_tile
    import json as json_module

    print(f"Generating hybrid snow tile: {args.tile}")
    print(f"Snow intensity: {args.intensity}")
    print(f"Blend mode: {args.blend_mode}")

    try:
        # Parse tile coordinate
        parts = args.tile.split("/")
        z, x, y = int(parts[0]), int(parts[1]), int(parts[2])

        output_path = Path(args.output) if args.output else None

        result = generate_hybrid_snow_tile(
            z=z,
            x=x,
            y=y,
            snow_intensity=args.intensity,
            blend_mode=args.blend_mode,
            color_grade=not args.no_color_grade,
            output_path=output_path,
        )

        # Save if no output path specified
        if output_path is None:
            output_path = Path(f"hybrid_snow_{args.tile.replace('/', '_')}.png")
            Image.fromarray(result.image).save(output_path)

        if args.json:
            output_info = result.to_dict()
            output_info["output_path"] = str(output_path)
            print(json_module.dumps(output_info, indent=2))
        else:
            print(f"✓ Generated in {result.processing_time_ms}ms")
            print(f"✓ Saved to: {output_path}")
            print(f"  Method: procedural snow + satellite")
            print(f"  Snow intensity: {result.snow_intensity}")
            print(f"  Blend mode: {result.blend_mode}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_hybrid_snow_area(args: argparse.Namespace) -> int:
    """Generate hybrid snow tiles for an area."""
    from .hybrid_snow import generate_hybrid_snow_tiles
    from .areas import get_area

    # Get bounds
    bounds = None
    if args.area:
        try:
            area = get_area(args.area)
            bounds = area.bounds
            print(f"Area: {area.name} - {area.description}")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    output_dir = Path(args.output_dir) if args.output_dir else None

    try:
        paths = generate_hybrid_snow_tiles(
            style="hybrid-winter",
            zoom=args.zoom,
            bounds=bounds,
            output_dir=output_dir,
            snow_intensity=args.intensity,
            blend_mode=args.blend_mode,
            progress=True,
        )

        print(f"\n✓ Generated {len(paths)} hybrid snow tiles")
        if paths:
            print(f"  Output: {paths[0].parent}")

        return 0

    except KeyboardInterrupt:
        print("\nCancelled")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


# =============================================================================
# DATA-DRIVEN STYLED RENDERING COMMANDS
# =============================================================================


def cmd_render_styled(args: argparse.Namespace) -> int:
    """Render tile with data-driven materials and optional LLM style."""
    from .blender_renderer import render_styled_tile
    from .style_presets import get_style_preset, list_style_presets
    from .sources.satellite import wgs84_to_tile
    from .sources.vector import load_buildings, load_trees, query_features_in_tile
    from .config import PipelineConfig

    # Validate inputs
    if not args.tile and (args.lat is None or args.lng is None):
        print("Error: Specify either --tile or both --lat and --lng", file=sys.stderr)
        return 1

    # Parse tile coordinate
    if args.tile:
        parts = args.tile.split("/")
        if len(parts) != 3:
            print(f"Error: Invalid tile format '{args.tile}'. Use z/x/y (e.g., 16/34322/22949)", file=sys.stderr)
            return 1
        zoom, x, y = int(parts[0]), int(parts[1]), int(parts[2])
    else:
        zoom = args.zoom
        x, y = wgs84_to_tile(args.lng, args.lat, zoom)

    print(f"Rendering styled tile: {zoom}/{x}/{y}")
    print(f"Style preset: {args.preset}")

    # Validate preset
    try:
        preset = get_style_preset(args.preset)
        print(f"  Season: {preset.season}")
        print(f"  Use building types: {preset.use_building_types}")
        print(f"  Use tree species: {preset.use_tree_species}")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(f"\nAvailable presets:")
        for name, desc in list_style_presets().items():
            print(f"  {name}: {desc}")
        return 1

    # LLM style (optional)
    llm_style = None
    if args.llm_prompt and not args.no_llm_variation:
        print(f"  LLM prompt: {args.llm_prompt}")
        try:
            from .llm_variation import generate_llm_style
            llm_style = generate_llm_style(args.llm_prompt, seed=args.seed, use_cache=True)
            print(f"  LLM style generated (cached)")
        except Exception as e:
            print(f"  Warning: LLM style generation failed ({e}), using preset only")

    # Load config and data
    config = PipelineConfig()

    # Calculate tile bounds (WGS84)
    import math
    n = 2 ** zoom
    west = x / n * 360.0 - 180.0
    east = (x + 1) / n * 360.0 - 180.0
    north = math.atan(math.sinh(math.pi * (1 - 2 * y / n))) * 180.0 / math.pi
    south = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))) * 180.0 / math.pi
    bounds = (west, south, east, north)

    print(f"  Bounds: {west:.6f}, {south:.6f}, {east:.6f}, {north:.6f}")

    # Load vector data
    print("Loading data...")
    try:
        buildings_source = load_buildings(config.sources.buildings_path)
        trees_source = load_trees(config.sources.trees_path)
        buildings = query_features_in_tile(buildings_source, bounds, buffer_meters=50)
        trees = query_features_in_tile(trees_source, bounds, buffer_meters=20)
        print(f"  Buildings: {len(buildings)}")
        print(f"  Trees: {len(trees)}")
    except FileNotFoundError as e:
        print(f"Error: Data file not found: {e}", file=sys.stderr)
        print("Run: python scripts/run-pipeline.py --real-data")
        return 1

    # Elevation is optional - skip for now (flat terrain)
    elevation = None

    # Render
    print(f"Rendering with Blender ({args.samples} samples)...")
    try:
        image = render_styled_tile(
            buildings=buildings,
            trees=trees,
            elevation=elevation,
            bounds=bounds,
            style_preset=args.preset,
            llm_style=llm_style.to_dict() if llm_style else None,
            image_size=512,
            samples=args.samples,
            use_gpu=True,
        )

        # Save output
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = Path(f"styled_{args.preset}_{zoom}_{x}_{y}.png")

        Image.fromarray(image).save(output_path)
        print(f"✓ Saved to: {output_path}")
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Install Blender: brew install --cask blender")
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def cmd_style_presets(args: argparse.Namespace) -> int:
    """List available data-driven style presets."""
    from .style_presets import (
        STYLE_PRESETS,
        get_seasonal_presets,
        get_creative_presets,
    )

    print("Available Style Presets")
    print("=" * 60)

    print("\nSEASONAL PRESETS (data-driven tree colors):")
    for name in get_seasonal_presets():
        preset = STYLE_PRESETS[name]
        print(f"  {name:15} - {preset.description}")

    print("\nTIME-OF-DAY PRESETS:")
    for name in ["golden_hour", "night", "overcast"]:
        if name in STYLE_PRESETS:
            preset = STYLE_PRESETS[name]
            print(f"  {name:15} - {preset.description}")

    print("\nCREATIVE PRESETS (LLM-enhanced):")
    for name in get_creative_presets():
        preset = STYLE_PRESETS[name]
        print(f"  {name:15} - {preset.description}")

    print("\nOTHER PRESETS:")
    shown = set(get_seasonal_presets() + get_creative_presets() + ["golden_hour", "night", "overcast"])
    for name, preset in STYLE_PRESETS.items():
        if name not in shown:
            print(f"  {name:15} - {preset.description}")

    print("\nUsage:")
    print("  python -m scripts.tile_pipeline.cli render-styled --tile 16/34322/22949 --preset autumn")
    print("  python -m scripts.tile_pipeline.cli render-styled --lat 47.376 --lng 8.54 --preset winter")

    return 0


def cmd_llm_style(args: argparse.Namespace) -> int:
    """Generate LLM style parameters from a prompt."""
    from .llm_variation import generate_llm_style
    import json as json_module

    print(f"Generating LLM style for: '{args.prompt}'")
    print(f"Seed: {args.seed}")

    try:
        style = generate_llm_style(
            prompt=args.prompt,
            seed=args.seed,
            use_cache=not args.no_cache,
        )

        print("\n✓ Style generated successfully")
        print("\nStyle Parameters:")
        print("-" * 40)

        style_dict = style.to_dict()
        for key, value in style_dict.items():
            if isinstance(value, (list, tuple)):
                value_str = f"[{', '.join(f'{v:.3f}' if isinstance(v, float) else str(v) for v in value)}]"
            elif isinstance(value, float):
                value_str = f"{value:.3f}"
            else:
                value_str = str(value)
            print(f"  {key}: {value_str}")

        # Save to file if requested
        if args.output:
            output_path = Path(args.output)
            with open(output_path, "w") as f:
                json_module.dump(style_dict, f, indent=2)
            print(f"\n✓ Saved to: {output_path}")

        return 0

    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("\nTo use LLM style generation, set one of:")
        print("  export GOOGLE_API_KEY=your_key")
        print("  export ANTHROPIC_API_KEY=your_key")
        print("  export OPENAI_API_KEY=your_key")
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def cmd_batch_render_styled(args: argparse.Namespace) -> int:
    """Batch render styled tiles for the StylesViewer.

    Renders all tiles in the viewer coverage area and updates the manifest.
    """
    import json as json_module
    import math
    from datetime import datetime
    from .blender_renderer import render_styled_tile
    from .style_presets import get_style_preset, STYLE_PRESETS
    from .sources.vector import load_buildings, load_trees, query_features_in_tile
    from .config import PipelineConfig

    # Default bounds match the ai-styles coverage area
    DEFAULT_BOUNDS = (8.525391, 47.361153, 8.563843, 47.387193)  # west, south, east, north
    ZOOM = 16

    # Parse bounds
    if args.bounds:
        parts = [float(x.strip()) for x in args.bounds.split(",")]
        if len(parts) != 4:
            print("Error: Bounds must be 4 values: west,south,east,north", file=sys.stderr)
            return 1
        bounds = tuple(parts)
    else:
        bounds = DEFAULT_BOUNDS

    west, south, east, north = bounds

    # Get style preset
    preset_name = args.preset
    try:
        preset = get_style_preset(preset_name)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Calculate tile range
    def lng_to_tile_x(lng: float, zoom: int) -> int:
        return int((lng + 180.0) / 360.0 * (2 ** zoom))

    def lat_to_tile_y(lat: float, zoom: int) -> int:
        lat_rad = math.radians(lat)
        return int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * (2 ** zoom))

    x_min = lng_to_tile_x(west, ZOOM)
    x_max = lng_to_tile_x(east, ZOOM)
    y_min = lat_to_tile_y(north, ZOOM)  # Note: y increases downward
    y_max = lat_to_tile_y(south, ZOOM)

    total_tiles = (x_max - x_min + 1) * (y_max - y_min + 1)

    print(f"=== Batch Render: {preset_name} ===")
    print(f"Preset: {preset.name} - {preset.description}")
    print(f"Season: {preset.season}, Time: {preset.time_of_day}")
    print(f"Bounds: {west:.6f}, {south:.6f}, {east:.6f}, {north:.6f}")
    print(f"Tile range: x={x_min}-{x_max}, y={y_min}-{y_max}")
    print(f"Total tiles: {total_tiles}")
    print()

    # Output directory
    style_dir_name = f"hybrid-{preset_name}"
    output_dir = Path(args.output_dir) if args.output_dir else Path(f"public/tiles/{style_dir_name}")
    tile_dir = output_dir / str(ZOOM)

    print(f"Output directory: {output_dir}")

    # Load config and data sources
    config = PipelineConfig()
    print("Loading data sources...")
    buildings_source = load_buildings(config.sources.buildings_path)
    trees_source = load_trees(config.sources.trees_path)

    # LLM style (optional)
    llm_style = None
    if args.llm_prompt:
        try:
            from .llm_variation import generate_llm_style
            llm_style = generate_llm_style(args.llm_prompt, seed=args.seed, use_cache=True)
            print(f"LLM style loaded from prompt: {args.llm_prompt}")
        except Exception as e:
            print(f"Warning: LLM style failed ({e}), using preset only")

    # Render each tile
    rendered = 0
    skipped = 0
    errors = 0

    for y in range(y_min, y_max + 1):
        for x in range(x_min, x_max + 1):
            tile_path = tile_dir / str(x) / f"{y}.webp"

            # Skip existing tiles unless --force
            if tile_path.exists() and not args.force:
                skipped += 1
                print(f"  Skip {ZOOM}/{x}/{y} (exists)")
                continue

            # Calculate tile bounds
            n = 2 ** ZOOM
            tile_west = x / n * 360.0 - 180.0
            tile_east = (x + 1) / n * 360.0 - 180.0
            tile_north = math.atan(math.sinh(math.pi * (1 - 2 * y / n))) * 180.0 / math.pi
            tile_south = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))) * 180.0 / math.pi
            tile_bounds = (tile_west, tile_south, tile_east, tile_north)

            # Query data for this tile
            buildings = query_features_in_tile(buildings_source, tile_bounds, buffer_meters=50)
            trees = query_features_in_tile(trees_source, tile_bounds, buffer_meters=20)

            print(f"  Render {ZOOM}/{x}/{y} ({len(buildings)} buildings, {len(trees)} trees)...", end="", flush=True)

            try:
                image = render_styled_tile(
                    buildings=buildings,
                    trees=trees,
                    elevation=None,
                    bounds=tile_bounds,
                    style_preset=preset_name,
                    llm_style=llm_style.to_dict() if llm_style else None,
                    image_size=512,
                    samples=args.samples,
                    use_gpu=True,
                )

                # Save as WebP
                tile_path.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(image).save(tile_path, "WEBP", quality=90)
                rendered += 1
                print(" ✓")

            except Exception as e:
                errors += 1
                print(f" ✗ {e}")
                if args.verbose:
                    import traceback
                    traceback.print_exc()

    print()
    print(f"=== Complete ===")
    print(f"Rendered: {rendered}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")

    # Update manifest
    if not args.no_manifest and rendered > 0:
        manifest_path = Path("public/tiles/ai-styles.json")
        if manifest_path.exists():
            with open(manifest_path) as f:
                manifest = json_module.load(f)
        else:
            manifest = {"styles": [], "satellite": {}, "defaultBounds": list(bounds), "defaultZoom": ZOOM}

        # Get style colors for manifest
        style_colors = _get_style_colors(preset_name)

        # Create/update entry
        style_entry = {
            "name": style_dir_name,
            "displayName": f"{preset.name} (Blender)",
            "description": preset.description,
            "colors": style_colors,
            "tiles": rendered + skipped,
            "totalTiles": total_tiles,
            "bounds": list(bounds),
            "zoom": ZOOM,
            "generatedAt": datetime.now().isoformat(),
            "generator": "blender-hybrid",
        }

        # Update or add
        existing_idx = next((i for i, s in enumerate(manifest["styles"]) if s["name"] == style_dir_name), None)
        if existing_idx is not None:
            manifest["styles"][existing_idx] = style_entry
        else:
            manifest["styles"].append(style_entry)

        manifest["generatedAt"] = datetime.now().isoformat()

        with open(manifest_path, "w") as f:
            json_module.dump(manifest, f, indent=2)

        print(f"✓ Updated manifest: {manifest_path}")

    return 0 if errors == 0 else 1


def _get_style_colors(preset_name: str) -> list:
    """Get representative colors for a style preset."""
    color_map = {
        "spring": ["#FFB7C5", "#90EE90", "#87CEEB"],  # Pink blossoms, green, blue sky
        "summer": ["#228B22", "#87CEEB", "#F5DEB3"],  # Green, blue sky, wheat
        "autumn": ["#FF6B35", "#FFD700", "#8B4513"],  # Orange, gold, brown
        "winter": ["#FFFFFF", "#E8F0F8", "#C4D6E8"],  # Snow whites and blues
        "golden_hour": ["#FFD700", "#FF8C00", "#FF6347"],  # Golds and oranges
        "night": ["#1a1a2e", "#16213e", "#0f3460"],  # Dark blues
        "cyberpunk": ["#FF00FF", "#00FFFF", "#1a0a2e"],  # Magenta, cyan, purple
        "isometric": ["#228B22", "#A0522D", "#87CEEB"],  # Green, sienna, sky
        "isometric_golden": ["#FFD700", "#FF8C00", "#8B4513"],  # Golden warm tones
        "default": ["#A0A0A0", "#808080", "#606060"],  # Grays
    }
    return color_map.get(preset_name, ["#808080", "#606060", "#404040"])


def cmd_render_depth(args: argparse.Namespace) -> int:
    """Render depth tiles for ControlNet conditioning."""
    from .tile_renderer import TileRenderer, TileCoord
    from .config import PipelineConfig
    from .areas import get_area
    from .blender_shadows import BlenderShadowRenderer

    # Check Blender availability
    try:
        renderer = BlenderShadowRenderer()
        info = renderer.check_blender()
        if info.get("installed"):
            print(f"✓ Blender {info['version']} found")
        else:
            print(f"✗ Blender not found: {info.get('error', 'unknown')}")
            return 1
    except FileNotFoundError as e:
        print(f"✗ Blender not found: {e}")
        print("  Install: brew install --cask blender")
        return 1

    config = PipelineConfig()

    # Parse bounds
    if args.area:
        try:
            area = get_area(args.area)
            bounds = area.bounds
            print(f"Using area: {area.name}")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    elif args.lat is not None and args.lng is not None:
        import math
        lat_deg_per_m = 1 / 111320
        lng_deg_per_m = 1 / (111320 * math.cos(math.radians(args.lat)))
        radius = args.radius
        bounds = (
            args.lng - radius * lng_deg_per_m,
            args.lat - radius * lat_deg_per_m,
            args.lng + radius * lng_deg_per_m,
            args.lat + radius * lat_deg_per_m,
        )
        print(f"Using center: ({args.lat}, {args.lng}) with {radius}m radius")
    else:
        bounds = config.bounds

    zoom = args.zoom
    output_dir = Path(args.output_dir) if args.output_dir else Path("public/tiles/depth")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Rendering depth tiles")
    print(f"Zoom: {zoom}")
    print(f"Output: {output_dir}")

    # This is a simplified depth-only render
    # In production, you'd create a specialized DepthTileRenderer
    # For now, we'll indicate this feature needs the full pipeline
    print("\nNote: Depth rendering requires scene data export + Blender render.")
    print("This command will be fully implemented with the depth pipeline.")
    print("\nTo render depth manually:")
    print("  1. Export scene with: render --area <area> --mode depth")
    print("  2. Use Blender to render depth pass")

    return 0


def cmd_ai_generate_area(args: argparse.Namespace) -> int:
    """Generate AI-stylized tiles for an area."""
    from .ai_tile_generator import (
        generate_tiles_for_area,
        check_api_availability,
        list_ai_styles,
    )
    from .areas import get_area

    # Check API availability
    if not check_api_availability():
        print("Error: GOOGLE_API_KEY not set", file=sys.stderr)
        print("Get an API key at: https://aistudio.google.com/apikey")
        return 1

    # Validate style
    available_styles = list_ai_styles()
    if args.style.lower() not in available_styles:
        print(f"Error: Unknown style '{args.style}'", file=sys.stderr)
        print(f"Available styles: {', '.join(sorted(available_styles.keys()))}")
        return 1

    # Get bounds
    bounds = None
    if args.area:
        try:
            area = get_area(args.area)
            bounds = area.bounds
            print(f"Area: {area.name} - {area.description}")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Set output directory
    output_dir = Path(args.output_dir) if args.output_dir else None

    # Handle workers flag
    workers = getattr(args, 'workers', 1)

    try:
        paths = generate_tiles_for_area(
            style=args.style,
            zoom=args.zoom,
            bounds=bounds,
            output_dir=output_dir,
            use_cache=not args.no_cache,
            progress=True,
            workers=workers,
        )

        print(f"\n✓ Generated {len(paths)} tiles")
        if paths:
            print(f"  Output: {paths[0].parent}")

        return 0

    except KeyboardInterrupt:
        print("\nCancelled")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Photorealistic tile rendering pipeline for Zurich",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Preview command
    preview_parser = subparsers.add_parser("preview", help="Preview a single tile")
    preview_parser.add_argument("--lat", type=float, required=True, help="Latitude")
    preview_parser.add_argument("--lng", type=float, required=True, help="Longitude")
    preview_parser.add_argument("--zoom", type=int, default=16, help="Zoom level")
    preview_parser.add_argument("--preset", default="afternoon", help="Time preset for lighting")
    preview_parser.add_argument("--mode", choices=["satellite", "rendered"], default="satellite",
                               help="Render mode: satellite (with imagery) or rendered (pure 3D)")
    preview_parser.add_argument("--style", default="default",
                               help="Visual style for rendered mode (see 'styles' command)")
    preview_parser.add_argument("--output", "-o", help="Output file path")
    preview_parser.add_argument("--output-dir", help="Output directory")
    preview_parser.add_argument("--use-blender", action="store_true",
                               help="Use Blender Cycles for GPU ray-traced shadows (satellite mode)")
    preview_parser.add_argument("--blender-samples", type=int, default=64,
                               help="Blender Cycles samples (higher=better, slower)")

    # Render command
    render_parser = subparsers.add_parser("render", help="Render tiles for region")
    render_parser.add_argument("--area", help="Predefined area name (see 'areas' command)")
    render_parser.add_argument("--bounds", help="Bounds as west,south,east,north")
    render_parser.add_argument("--lat", type=float, help="Center latitude (use with --lng and --radius)")
    render_parser.add_argument("--lng", type=float, help="Center longitude (use with --lat and --radius)")
    render_parser.add_argument("--radius", type=float, default=200, help="Radius in meters around center point (default: 200)")
    render_parser.add_argument("--min-zoom", type=int, help="Minimum zoom level")
    render_parser.add_argument("--max-zoom", type=int, help="Maximum zoom level")
    render_parser.add_argument("--preset", default="afternoon", help="Time preset for lighting")
    render_parser.add_argument("--mode", choices=["satellite", "rendered"], default="satellite",
                              help="Render mode: satellite (with imagery) or rendered (pure 3D)")
    render_parser.add_argument("--style", default="default",
                              help="Visual style for rendered mode (see 'styles' command)")
    render_parser.add_argument("--output-dir", help="Output directory")
    render_parser.add_argument("--workers", type=int, default=4, help="Parallel workers")
    render_parser.add_argument("--use-blender", action="store_true",
                              help="Use Blender Cycles for shadows (satellite mode only)")
    render_parser.add_argument("--blender-samples", type=int, default=64,
                              help="Blender Cycles samples (higher=better, slower)")
    render_parser.add_argument("--dry-run", action="store_true", help="Count tiles only")
    render_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")

    # Presets command
    subparsers.add_parser("presets", help="List available time presets")

    # Styles command
    subparsers.add_parser("styles", help="List available render styles (for --mode rendered)")

    # Areas command
    subparsers.add_parser("areas", help="List predefined Zürich areas")

    # Info command
    subparsers.add_parser("info", help="Show data source information")

    # =========================================================================
    # SPATIAL QUERY COMMANDS
    # =========================================================================

    from datetime import datetime

    # shadow command - Query shadow at a 3D point
    shadow_parser = subparsers.add_parser(
        "shadow",
        help="Query shadow at a 3D point",
        description="Check if a location is in sun or shade at a specific time."
    )
    shadow_parser.add_argument("--lat", type=float, required=True, help="Latitude (WGS84)")
    shadow_parser.add_argument("--lng", type=float, required=True, help="Longitude (WGS84)")
    shadow_parser.add_argument("--time", default="12:00", help="Time HH:MM (default: 12:00)")
    shadow_parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"),
                              help="Date YYYY-MM-DD (default: today)")
    shadow_parser.add_argument("--height", type=float, default=1.7,
                              help="Height in meters above ground (default: 1.7m standing)")
    shadow_parser.add_argument("--floor", type=int,
                              help="Floor number (overrides --height, assumes 3m/floor + 1.5m)")
    shadow_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # balcony command - Analyze sun exposure for a balcony
    balcony_parser = subparsers.add_parser(
        "balcony",
        help="Analyze sun exposure for a balcony",
        description="Calculate how much sun a balcony gets throughout the day."
    )
    balcony_parser.add_argument("--lat", type=float, required=True, help="Latitude (WGS84)")
    balcony_parser.add_argument("--lng", type=float, required=True, help="Longitude (WGS84)")
    balcony_parser.add_argument("--floor", type=int, required=True,
                               help="Floor number (0=ground floor)")
    balcony_parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"),
                               help="Date YYYY-MM-DD (default: today)")
    balcony_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # shadow-timeline command - Get shadow throughout a day
    timeline_parser = subparsers.add_parser(
        "shadow-timeline",
        help="Get shadow timeline for a point",
        description="See how shadow changes throughout the day at a location."
    )
    timeline_parser.add_argument("--lat", type=float, required=True, help="Latitude (WGS84)")
    timeline_parser.add_argument("--lng", type=float, required=True, help="Longitude (WGS84)")
    timeline_parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"),
                                help="Date YYYY-MM-DD (default: today)")
    timeline_parser.add_argument("--height", type=float, default=1.7,
                                help="Height in meters (default: 1.7m standing)")
    timeline_parser.add_argument("--floor", type=int,
                                help="Floor number (overrides --height)")
    timeline_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # nearest command - Find nearest amenity
    nearest_parser = subparsers.add_parser(
        "nearest",
        help="Find nearest amenity",
        description="Find the nearest bench, fountain, or toilet."
    )
    nearest_parser.add_argument("--lat", type=float, required=True, help="Latitude (WGS84)")
    nearest_parser.add_argument("--lng", type=float, required=True, help="Longitude (WGS84)")
    nearest_parser.add_argument("--type", required=True, choices=["bench", "fountain", "toilet"],
                               help="Type of amenity to find")
    nearest_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # find command - Find amenities within radius
    find_parser = subparsers.add_parser(
        "find",
        help="Find amenities within radius",
        description="Find all benches, fountains, or toilets within a radius."
    )
    find_parser.add_argument("--lat", type=float, required=True, help="Latitude (WGS84)")
    find_parser.add_argument("--lng", type=float, required=True, help="Longitude (WGS84)")
    find_parser.add_argument("--type", required=True, choices=["bench", "fountain", "toilet"],
                            help="Type of amenity to find")
    find_parser.add_argument("--radius", type=float, default=200,
                            help="Search radius in meters (default: 200)")
    find_parser.add_argument("--limit", type=int, default=10,
                            help="Maximum results (default: 10)")
    find_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # =========================================================================
    # ROUTE-BUILDING QUERY COMMANDS
    # =========================================================================

    # route-buildings command - Query buildings along a transit route
    route_parser = subparsers.add_parser(
        "route-buildings",
        help="Query buildings along a transit route",
        description="Count buildings within 50m of a transit route (tram, bus, etc.)"
    )
    route_parser.add_argument("--route", "-r", help="Route short name (e.g., '4', '11', '910')")
    route_parser.add_argument("--list", "-l", action="store_true",
                             help="List all routes with feature counts")
    route_parser.add_argument("--type", choices=["tram", "bus", "rail", "funicular"],
                             help="Filter by transit type")
    route_parser.add_argument("--sort-by", "-s",
                             choices=["buildings", "benches", "fountains", "toilets", "trees", "length"],
                             default="buildings",
                             help="Sort routes by feature (default: buildings)")
    route_parser.add_argument("--include-ids", action="store_true",
                             help="Include building IDs in output")
    route_parser.add_argument("--limit", type=int, default=20,
                             help="Limit routes shown when listing (default: 20)")
    route_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # route-stats command - Show route-building index statistics
    stats_parser = subparsers.add_parser(
        "route-stats",
        help="Show route-building index statistics",
        description="Display summary statistics about the route-building spatial index."
    )
    stats_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # compare-routes command - Compare multiple routes
    compare_parser = subparsers.add_parser(
        "compare-routes",
        help="Compare multiple transit routes",
        description="Compare building coverage between multiple routes."
    )
    compare_parser.add_argument("routes", nargs="+",
                               help="Route names to compare (e.g., '4 11 15')")
    compare_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # path-stats command - Analyze what you passed along a path
    path_parser = subparsers.add_parser(
        "path-stats",
        help="Analyze what you passed along a path",
        description="Given a GPS path, count buildings and features passed."
    )
    path_parser.add_argument("--path", "-p", required=True,
                            help="Path as 'lng,lat;lng,lat;...' coordinates")
    path_parser.add_argument("--buffer", type=float, default=20,
                            help="Buffer distance in meters (default: 20)")
    path_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # =========================================================================
    # AI TILE GENERATION COMMANDS
    # =========================================================================

    # ai-styles command - List AI tile generation styles
    subparsers.add_parser(
        "ai-styles",
        help="List available AI tile generation styles",
        description="Show all available styles for AI tile generation (winter, cyberpunk, etc.)"
    )

    # ai-generate command - Generate AI-stylized tile
    ai_gen_parser = subparsers.add_parser(
        "ai-generate",
        help="Generate an AI-stylized tile",
        description="Transform a Blender-rendered tile into a stylized version using Gemini AI."
    )
    ai_gen_parser.add_argument("--tile", "-t", required=True,
                               help="Tile coordinate (e.g., '16/34322/22950')")
    ai_gen_parser.add_argument("--style", "-s", required=True,
                               help="Style name (use 'ai-styles' to list available)")
    ai_gen_parser.add_argument("--output", "-o",
                               help="Output file path (default: ai_tile_<coord>_<style>.png)")
    ai_gen_parser.add_argument("--blender-dir",
                               help="Directory with Blender tiles (default: public/tiles/photorealistic)")
    ai_gen_parser.add_argument("--no-cache", action="store_true",
                               help="Skip cache and regenerate")
    ai_gen_parser.add_argument("--json", action="store_true",
                               help="Output result as JSON")

    # ai-generate-area command - Generate AI tiles for an area
    ai_area_parser = subparsers.add_parser(
        "ai-generate-area",
        help="Generate AI-stylized tiles for an area",
        description="Generate AI tiles for all Blender-rendered tiles in an area."
    )
    ai_area_parser.add_argument("--style", "-s", required=True,
                                help="Style name (use 'ai-styles' to list available)")
    ai_area_parser.add_argument("--area", "-a",
                                help="Predefined area name (e.g., 'city_center')")
    ai_area_parser.add_argument("--zoom", "-z", type=int, default=16,
                                help="Zoom level (default: 16)")
    ai_area_parser.add_argument("--output-dir",
                                help="Output directory (default: public/tiles/ai-<style>)")
    ai_area_parser.add_argument("--no-cache", action="store_true",
                                help="Skip cache and regenerate all")
    ai_area_parser.add_argument("--workers", "-w", type=int, default=1,
                                help="Number of parallel workers (default: 1)")

    # set-style-reference command - Set reference image for a style
    set_ref_parser = subparsers.add_parser(
        "set-style-reference",
        help="Set the reference image for an AI style",
        description="Copy and set a tile as the 'golden example' for a style."
    )
    set_ref_parser.add_argument("--style", "-s", required=True,
                                help="Style name (e.g., 'cyberpunk', 'winter')")
    set_ref_parser.add_argument("--image", "-i", required=True,
                                help="Path to the reference image (will be resized to 512x512)")

    # =========================================================================
    # STABLE DIFFUSION TILE GENERATION COMMANDS
    # =========================================================================

    # sd-styles command - List SD tile generation styles
    subparsers.add_parser(
        "sd-styles",
        help="List available SD (Stable Diffusion) tile generation styles",
        description="Show all available styles for SD tile generation with ControlNet Depth."
    )

    # sd-generate command - Generate SD-stylized tile
    sd_gen_parser = subparsers.add_parser(
        "sd-generate",
        help="Generate an SD-stylized tile using ControlNet Depth",
        description="Transform a tile using Stable Diffusion + ControlNet for consistent geometry."
    )
    sd_gen_parser.add_argument("--tile", "-t", required=True,
                               help="Tile coordinate (e.g., '16/34322/22950')")
    sd_gen_parser.add_argument("--style", "-s", required=True,
                               help="Style name (use 'sd-styles' to list available)")
    sd_gen_parser.add_argument("--seed", type=int, default=42,
                               help="Random seed for deterministic output (default: 42)")
    sd_gen_parser.add_argument("--output", "-o",
                               help="Output file path (default: sd_tile_<coord>_<style>.png)")
    sd_gen_parser.add_argument("--depth-dir",
                               help="Directory with depth tiles (default: public/tiles/depth)")
    sd_gen_parser.add_argument("--blender-dir",
                               help="Directory with Blender tiles (default: public/tiles/photorealistic)")
    sd_gen_parser.add_argument("--no-cache", action="store_true",
                               help="Skip cache and regenerate")
    sd_gen_parser.add_argument("--json", action="store_true",
                               help="Output result as JSON")

    # sd-generate-area command - Generate SD tiles for an area
    sd_area_parser = subparsers.add_parser(
        "sd-generate-area",
        help="Generate SD-stylized tiles for an area",
        description="Generate SD tiles for all depth tiles in an area using ControlNet."
    )
    sd_area_parser.add_argument("--style", "-s", required=True,
                                help="Style name (use 'sd-styles' to list available)")
    sd_area_parser.add_argument("--area", "-a",
                                help="Predefined area name (e.g., 'city_center')")
    sd_area_parser.add_argument("--zoom", "-z", type=int, default=16,
                                help="Zoom level (default: 16)")
    sd_area_parser.add_argument("--seed", type=int, default=42,
                                help="Random seed for deterministic output (default: 42)")
    sd_area_parser.add_argument("--output-dir",
                                help="Output directory (default: public/tiles/sd-<style>)")
    sd_area_parser.add_argument("--depth-dir",
                                help="Directory with depth tiles (default: public/tiles/depth)")
    sd_area_parser.add_argument("--blender-dir",
                                help="Directory with Blender tiles (default: public/tiles/photorealistic)")
    sd_area_parser.add_argument("--no-cache", action="store_true",
                                help="Skip cache and regenerate all")

    # =========================================================================
    # SATELLITE STYLE TRANSFER COMMANDS (RECOMMENDED)
    # =========================================================================

    # satellite-styles command - List satellite style transfer styles
    subparsers.add_parser(
        "satellite-styles",
        help="List available satellite style transfer styles (img2img - RECOMMENDED)",
        description="Show styles that transform satellite imagery while preserving structure."
    )

    # satellite-style command - Transform a single satellite tile
    sat_gen_parser = subparsers.add_parser(
        "satellite-style",
        help="Transform a satellite tile using InstructPix2Pix (RECOMMENDED)",
        description="Transform real satellite imagery with style while preserving structure."
    )
    sat_gen_parser.add_argument("--tile", "-t", required=True,
                                help="Tile coordinate (e.g., '16/34322/22950')")
    sat_gen_parser.add_argument("--style", "-s", required=True,
                                help="Style name (use 'satellite-styles' to list available)")
    sat_gen_parser.add_argument("--seed", type=int, default=42,
                                help="Random seed for deterministic output (default: 42)")
    sat_gen_parser.add_argument("--image-guidance", type=float,
                                help="Image guidance scale (higher = more faithful, default: 1.8)")
    sat_gen_parser.add_argument("--output", "-o",
                                help="Output file path (default: satellite_tile_<coord>_<style>.png)")
    sat_gen_parser.add_argument("--no-cache", action="store_true",
                                help="Skip cache and regenerate")
    sat_gen_parser.add_argument("--json", action="store_true",
                                help="Output result as JSON")

    # satellite-style-area command - Transform satellite tiles for an area
    sat_area_parser = subparsers.add_parser(
        "satellite-style-area",
        help="Transform satellite tiles for an area using img2img (RECOMMENDED)",
        description="Transform all satellite tiles in an area with style transfer."
    )
    sat_area_parser.add_argument("--style", "-s", required=True,
                                 help="Style name (use 'satellite-styles' to list available)")
    sat_area_parser.add_argument("--area", "-a",
                                 help="Predefined area name (e.g., 'city_center')")
    sat_area_parser.add_argument("--zoom", "-z", type=int, default=16,
                                 help="Zoom level (default: 16)")
    sat_area_parser.add_argument("--seed", type=int, default=42,
                                 help="Random seed for deterministic output (default: 42)")
    sat_area_parser.add_argument("--image-guidance", type=float,
                                 help="Image guidance scale (higher = more faithful, default: 1.8)")
    sat_area_parser.add_argument("--output-dir",
                                 help="Output directory (default: public/tiles/sd-<style>)")
    sat_area_parser.add_argument("--no-cache", action="store_true",
                                 help="Skip cache and regenerate all")
    sat_area_parser.add_argument("--rate-limit", type=float, default=12.0,
                                 help="Seconds between API calls (default: 12)")

    # =========================================================================
    # HYBRID SNOW COMMANDS (SATELLITE + PROCEDURAL SNOW)
    # =========================================================================

    # hybrid-snow command - Generate a single hybrid snow tile
    hybrid_parser = subparsers.add_parser(
        "hybrid-snow",
        help="Generate hybrid snow tile (satellite + procedural snow, FREE)",
        description="Composite satellite imagery with procedural snow overlay. No API cost!"
    )
    hybrid_parser.add_argument("--tile", "-t", required=True,
                               help="Tile coordinate (e.g., '16/34322/22950')")
    hybrid_parser.add_argument("--intensity", "-i", type=float, default=0.7,
                               help="Snow intensity (0.0-1.0, default: 0.7)")
    hybrid_parser.add_argument("--blend-mode", choices=["screen", "soft_light", "overlay", "add"],
                               default="soft_light", help="Blend mode (default: soft_light)")
    hybrid_parser.add_argument("--no-color-grade", action="store_true",
                               help="Skip winter color grading")
    hybrid_parser.add_argument("--output", "-o",
                               help="Output file path")
    hybrid_parser.add_argument("--json", action="store_true",
                               help="Output result as JSON")

    # hybrid-snow-area command - Generate hybrid snow tiles for an area
    hybrid_area_parser = subparsers.add_parser(
        "hybrid-snow-area",
        help="Generate hybrid snow tiles for an area (FREE, instant)",
        description="Composite satellite imagery with procedural snow overlay for an area."
    )
    hybrid_area_parser.add_argument("--area", "-a", required=True,
                                    help="Predefined area name (e.g., 'city_center')")
    hybrid_area_parser.add_argument("--zoom", "-z", type=int, default=16,
                                    help="Zoom level (default: 16)")
    hybrid_area_parser.add_argument("--intensity", "-i", type=float, default=0.7,
                                    help="Snow intensity (0.0-1.0, default: 0.7)")
    hybrid_area_parser.add_argument("--blend-mode", choices=["screen", "soft_light", "overlay", "add"],
                                    default="soft_light", help="Blend mode (default: soft_light)")
    hybrid_area_parser.add_argument("--output-dir",
                                    help="Output directory (default: public/tiles/hybrid-winter)")

    # =========================================================================
    # DATA-DRIVEN STYLED RENDERING COMMANDS
    # =========================================================================
    # These commands use your rich dataset (65k buildings, 80k trees) with
    # per-object materials and optional LLM-generated creative styles.

    # render-styled command - Render with data-driven materials
    styled_parser = subparsers.add_parser(
        "render-styled",
        help="Render tile with data-driven materials (building types, tree species)",
        description="""
Render tiles using data-driven materials:
- Per-building type colors (residential=warm, commercial=cool, industrial=gray)
- Per-tree species colors (maples=red in autumn, oaks=gold, spruces=green always)
- Optional LLM-generated style variations

Examples:
  # Autumn rendering with species-accurate tree colors
  python -m scripts.tile_pipeline.cli render-styled --tile 16/34322/22949 --preset autumn

  # Winter with snow
  python -m scripts.tile_pipeline.cli render-styled --lat 47.376 --lng 8.54 --preset winter

  # Cyberpunk with LLM style (requires API key)
  python -m scripts.tile_pipeline.cli render-styled --tile 16/34322/22949 --preset cyberpunk --llm-prompt "neon rain night"
        """,
    )
    styled_parser.add_argument("--tile", help="Tile coordinate as z/x/y (e.g., 16/34322/22949)")
    styled_parser.add_argument("--lat", type=float, help="Latitude (alternative to --tile)")
    styled_parser.add_argument("--lng", type=float, help="Longitude (alternative to --tile)")
    styled_parser.add_argument("--zoom", "-z", type=int, default=16, help="Zoom level (default: 16)")
    styled_parser.add_argument("--preset", "-p", default="default",
                               help="Style preset: spring, summer, autumn, winter, golden_hour, night, cyberpunk, etc.")
    styled_parser.add_argument("--llm-prompt", help="Optional LLM prompt for creative style (requires API key)")
    styled_parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    styled_parser.add_argument("-o", "--output", help="Output file path")
    styled_parser.add_argument("--samples", type=int, default=64, help="Blender render samples")
    styled_parser.add_argument("--no-llm-variation", action="store_true",
                               help="Disable LLM color variations (use pure fixed colors)")

    # style-presets command - List available style presets
    subparsers.add_parser(
        "style-presets",
        help="List available data-driven style presets",
    )

    # llm-style command - Generate LLM style parameters
    llm_parser = subparsers.add_parser(
        "llm-style",
        help="Generate LLM style parameters from a prompt (requires API key)",
    )
    llm_parser.add_argument("prompt", help="Creative style prompt (e.g., 'cyberpunk rain night')")
    llm_parser.add_argument("--seed", type=int, default=42, help="Random seed")
    llm_parser.add_argument("-o", "--output", help="Output JSON file for style parameters")
    llm_parser.add_argument("--no-cache", action="store_true", help="Bypass cache")

    # batch-render-styled command - Batch render for StylesViewer
    batch_styled_parser = subparsers.add_parser(
        "batch-render-styled",
        help="Batch render styled tiles for StylesViewer (updates manifest)",
        description="""
Batch render all tiles in an area using data-driven materials.
Outputs to public/tiles/hybrid-{preset}/ and updates ai-styles.json manifest.

Examples:
  # Render autumn style for the full coverage area
  python -m scripts.tile_pipeline.cli batch-render-styled --preset autumn

  # Render winter with custom bounds
  python -m scripts.tile_pipeline.cli batch-render-styled --preset winter --bounds "8.53,47.37,8.55,47.38"

  # Render isometric golden hour with LLM variation
  python -m scripts.tile_pipeline.cli batch-render-styled --preset isometric_golden --llm-prompt "warm sunset glow"
        """,
    )
    batch_styled_parser.add_argument("--preset", "-p", required=True,
                                     help="Style preset: autumn, winter, golden_hour, cyberpunk, isometric_golden, etc.")
    batch_styled_parser.add_argument("--bounds",
                                     help="Custom bounds: west,south,east,north (default: viewer coverage area)")
    batch_styled_parser.add_argument("--llm-prompt",
                                     help="Optional LLM prompt for creative variation")
    batch_styled_parser.add_argument("--seed", type=int, default=42,
                                     help="Random seed for reproducibility (default: 42)")
    batch_styled_parser.add_argument("--samples", type=int, default=64,
                                     help="Blender render samples (default: 64)")
    batch_styled_parser.add_argument("--output-dir",
                                     help="Custom output directory (default: public/tiles/hybrid-{preset})")
    batch_styled_parser.add_argument("--force", "-f", action="store_true",
                                     help="Force re-render existing tiles")
    batch_styled_parser.add_argument("--no-manifest", action="store_true",
                                     help="Skip manifest update")
    batch_styled_parser.add_argument("-v", "--verbose", action="store_true",
                                     help="Verbose output with stack traces")

    # render-depth command - Render depth tiles for ControlNet
    depth_parser = subparsers.add_parser(
        "render-depth",
        help="Render depth tiles for ControlNet conditioning (LEGACY)",
        description="Generate depth pass tiles using Blender for SD ControlNet pipeline."
    )
    depth_parser.add_argument("--area", help="Predefined area name")
    depth_parser.add_argument("--lat", type=float, help="Center latitude")
    depth_parser.add_argument("--lng", type=float, help="Center longitude")
    depth_parser.add_argument("--radius", type=float, default=200,
                              help="Radius in meters (default: 200)")
    depth_parser.add_argument("--zoom", "-z", type=int, default=16,
                              help="Zoom level (default: 16)")
    depth_parser.add_argument("--output-dir",
                              help="Output directory (default: public/tiles/depth)")

    args = parser.parse_args()

    if args.command == "preview":
        return cmd_preview(args)
    elif args.command == "render":
        return cmd_render(args)
    elif args.command == "presets":
        return cmd_presets(args)
    elif args.command == "styles":
        return cmd_styles(args)
    elif args.command == "areas":
        return cmd_areas(args)
    elif args.command == "info":
        return cmd_info(args)
    # Spatial query commands
    elif args.command == "shadow":
        return cmd_shadow(args)
    elif args.command == "balcony":
        return cmd_balcony(args)
    elif args.command == "shadow-timeline":
        return cmd_shadow_timeline(args)
    elif args.command == "nearest":
        return cmd_nearest(args)
    elif args.command == "find":
        return cmd_find_amenities(args)
    # Route-building query commands
    elif args.command == "route-buildings":
        return cmd_route_buildings(args)
    elif args.command == "route-stats":
        return cmd_route_stats(args)
    elif args.command == "compare-routes":
        return cmd_compare_routes(args)
    elif args.command == "path-stats":
        return cmd_path_stats(args)
    # AI tile generation commands
    elif args.command == "ai-styles":
        return cmd_ai_styles(args)
    elif args.command == "ai-generate":
        return cmd_ai_generate(args)
    elif args.command == "ai-generate-area":
        return cmd_ai_generate_area(args)
    elif args.command == "set-style-reference":
        return cmd_set_style_reference(args)
    # SD tile generation commands (legacy ControlNet)
    elif args.command == "sd-styles":
        return cmd_sd_styles(args)
    elif args.command == "sd-generate":
        return cmd_sd_generate(args)
    elif args.command == "sd-generate-area":
        return cmd_sd_generate_area(args)
    elif args.command == "render-depth":
        return cmd_render_depth(args)
    # Satellite style transfer commands (recommended img2img)
    elif args.command == "satellite-styles":
        return cmd_satellite_styles(args)
    elif args.command == "satellite-style":
        return cmd_satellite_style(args)
    elif args.command == "satellite-style-area":
        return cmd_satellite_style_area(args)
    # Hybrid snow commands (satellite + procedural snow)
    elif args.command == "hybrid-snow":
        return cmd_hybrid_snow(args)
    elif args.command == "hybrid-snow-area":
        return cmd_hybrid_snow_area(args)
    # Data-driven styled rendering commands
    elif args.command == "render-styled":
        return cmd_render_styled(args)
    elif args.command == "style-presets":
        return cmd_style_presets(args)
    elif args.command == "llm-style":
        return cmd_llm_style(args)
    elif args.command == "batch-render-styled":
        return cmd_batch_render_styled(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
