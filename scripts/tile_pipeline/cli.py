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
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
