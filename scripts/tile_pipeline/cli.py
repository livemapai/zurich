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
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
