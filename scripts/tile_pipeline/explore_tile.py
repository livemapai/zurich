#!/usr/bin/env python3
"""
Interactive tile exploration and analysis script.

Use this script to explore individual tiles, test different parameters,
and build understanding before committing to the full pipeline.

Usage:
    # Fetch and analyze a tile
    python -m scripts.tile_pipeline.explore_tile analyze --lat 47.37 --lng 8.54

    # Compare shadow detection methods
    python -m scripts.tile_pipeline.explore_tile shadows --tile 16/34322/22950

    # Test neutralization parameters
    python -m scripts.tile_pipeline.explore_tile neutralize --input original.png --output test.png

    # Quick preview with a preset
    python -m scripts.tile_pipeline.explore_tile preview --preset evening_golden
"""

import argparse
import json
from pathlib import Path
from typing import Optional
import sys

import numpy as np
from PIL import Image

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def cmd_analyze(args):
    """Analyze a satellite tile for shadows and lighting."""
    from scripts.tile_pipeline.sources.satellite import SatelliteSource, wgs84_to_tile, tile_bounds_wgs84
    from scripts.tile_pipeline.shadow_analyzer import (
        analyze_shadows,
        create_shadow_probability_map,
        estimate_capture_time,
    )
    from scripts.tile_pipeline.config import PipelineConfig

    config = PipelineConfig()

    # Get tile coordinates
    x, y = wgs84_to_tile(args.lng, args.lat, args.zoom)
    bounds = tile_bounds_wgs84(args.zoom, x, y)

    print(f"\n📍 Location: {args.lat}°N, {args.lng}°E")
    print(f"📦 Tile: {args.zoom}/{x}/{y}")
    print(f"🗺️  Bounds: {bounds[0]:.4f}°W to {bounds[2]:.4f}°E, {bounds[1]:.4f}°S to {bounds[3]:.4f}°N")

    # Fetch tile
    print("\nFetching satellite tile...")
    source = SatelliteSource(cache_dir=config.cache_dir)
    tile = source.fetch_and_resize(args.zoom, x, y, 512)

    # Save original
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    Image.fromarray(tile).save(output_dir / "satellite.png")
    print(f"  Saved: {output_dir / 'satellite.png'}")

    # Analyze
    print("\nAnalyzing shadows...")
    analysis = analyze_shadows(tile)
    capture_time = estimate_capture_time(analysis)

    # Print analysis
    print("\n" + "=" * 50)
    print("SHADOW ANALYSIS RESULTS")
    print("=" * 50)

    print(f"""
📊 Shadow Statistics:
   Coverage: {analysis.shadow_percentage:.1f}% of image
   Shadow darkness: {(1 - analysis.shadow_intensity) * 100:.0f}%
   Highlight brightness: {analysis.highlight_intensity * 100:.0f}%
   Contrast ratio: {analysis.contrast_ratio:.1f}x

☀️ Estimated Sun Position:
   Azimuth: {analysis.estimated_sun_azimuth:.0f}° ({"NE" if analysis.estimated_sun_azimuth < 90 else "SE" if analysis.estimated_sun_azimuth < 180 else "SW" if analysis.estimated_sun_azimuth < 270 else "NW"})
   Altitude: {analysis.estimated_sun_altitude:.0f}° above horizon

⏰ Estimated Capture:
   Time: ~{capture_time['time_string']} ({capture_time['period']})
   Confidence: {capture_time['confidence']}

💡 Recommendations:
""")

    # Generate recommendations
    if analysis.shadow_percentage > 30:
        print("   ⚠️  High shadow coverage - consider aggressive neutralization")
    elif analysis.shadow_percentage > 15:
        print("   ℹ️  Moderate shadows - medium neutralization recommended")
    else:
        print("   ✓  Low shadow coverage - light enhancement sufficient")

    if analysis.contrast_ratio > 5:
        print("   ⚠️  High contrast - be careful not to blow out highlights")

    # Save analysis as JSON
    analysis_data = {
        "tile": f"{args.zoom}/{x}/{y}",
        "location": {"lat": args.lat, "lng": args.lng},
        "shadow_percentage": float(analysis.shadow_percentage),
        "shadow_intensity": float(analysis.shadow_intensity),
        "contrast_ratio": float(analysis.contrast_ratio),
        "estimated_sun_azimuth": float(analysis.estimated_sun_azimuth),
        "estimated_sun_altitude": float(analysis.estimated_sun_altitude),
        "estimated_capture_time": capture_time,
    }

    with open(output_dir / "analysis.json", "w") as f:
        json.dump(analysis_data, f, indent=2)
    print(f"\n  Saved: {output_dir / 'analysis.json'}")

    # Save shadow probability map
    prob_map = create_shadow_probability_map(tile)
    prob_vis = (prob_map * 255).astype(np.uint8)
    Image.fromarray(prob_vis).save(output_dir / "shadow_probability.png")
    print(f"  Saved: {output_dir / 'shadow_probability.png'}")


def cmd_neutralize(args):
    """Test shadow neutralization with different parameters."""
    from scripts.tile_pipeline.shadow_neutralizer import neutralize_shadows

    # Load input image
    img = np.array(Image.open(args.input).convert("RGB"))

    print(f"\n🔧 Neutralization Parameters:")
    print(f"   Target shadow level: {args.target}")
    print(f"   Temperature correction: {args.temperature}")
    print(f"   Detail enhancement: {args.detail}")
    print(f"   Transition softness: {args.softness}")

    # Process
    result = neutralize_shadows(
        img,
        target_shadow_level=args.target,
        temperature_correction=args.temperature,
        detail_enhancement=args.detail,
        transition_softness=args.softness,
    )

    # Save
    Image.fromarray(result).save(args.output)
    print(f"\n✓ Saved: {args.output}")


def cmd_preview(args):
    """Quick preview with a preset."""
    from scripts.tile_pipeline.tile_renderer import preview_tile
    from scripts.tile_pipeline.time_presets import PRESETS, get_preset

    print(f"\n📍 Location: {args.lat}°N, {args.lng}°E")
    print(f"🎨 Preset: {args.preset}")

    preset = get_preset(args.preset)
    print(f"   Sun azimuth: {preset.azimuth}°")
    print(f"   Sun altitude: {preset.altitude}°")

    # Generate preview
    result = preview_tile(
        lat=args.lat,
        lng=args.lng,
        zoom=args.zoom,
        preset_name=args.preset,
    )

    # Save
    output = Path(args.output)
    Image.fromarray(result).save(output)
    print(f"\n✓ Saved: {output}")


def cmd_compare(args):
    """Compare original vs processed tile."""
    from scripts.tile_pipeline.shadow_neutralizer import adaptive_shadow_removal
    from scripts.tile_pipeline.tile_compositor import TileCompositor, TileLayers
    from scripts.tile_pipeline.sources.satellite import SatelliteSource, wgs84_to_tile, tile_bounds_wgs84
    from scripts.tile_pipeline.sources.elevation import ElevationSource, meters_per_pixel
    from scripts.tile_pipeline.hillshade import compute_hillshade_with_imhof
    from scripts.tile_pipeline.time_presets import get_preset
    from scripts.tile_pipeline.config import PipelineConfig

    config = PipelineConfig()
    z, x, y = args.zoom, None, None

    # Get tile coordinates
    x, y = wgs84_to_tile(args.lng, args.lat, z)
    bounds = tile_bounds_wgs84(z, x, y)

    print(f"\n📦 Tile: {z}/{x}/{y}")

    # Fetch data
    satellite_source = SatelliteSource(cache_dir=config.cache_dir)
    elevation_source = ElevationSource(cache_dir=config.cache_dir)

    satellite = satellite_source.fetch_and_resize(z, x, y, 512)
    elevation = elevation_source.fetch_and_resize(z, x, y, 512)

    # Neutralize
    print("Neutralizing shadows...")
    neutralized = adaptive_shadow_removal(satellite)

    # Get preset
    preset = get_preset(args.preset)

    # Compute hillshade
    lat_center = (bounds[1] + bounds[3]) / 2
    cell_size = meters_per_pixel(lat_center, 17)

    hillshade_data = compute_hillshade_with_imhof(
        elevation,
        cell_size,
        azimuth=preset.azimuth,
        altitude=preset.altitude,
        warm_strength=preset.warm_strength,
        cool_strength=preset.cool_strength,
    )

    # Composite both versions
    shadow_mask = np.ones((512, 512), dtype=np.float32)
    compositor = TileCompositor(config, preset)

    # Original
    layers_orig = TileLayers(
        satellite=satellite,
        hillshade=hillshade_data["hillshade"],
        imhof_shift_a=hillshade_data["shift_a"],
        imhof_shift_b=hillshade_data["shift_b"],
        building_shadows=shadow_mask,
    )
    result_orig = compositor.composite(layers_orig)

    # Neutralized
    layers_neut = TileLayers(
        satellite=neutralized,
        hillshade=hillshade_data["hillshade"],
        imhof_shift_a=hillshade_data["shift_a"],
        imhof_shift_b=hillshade_data["shift_b"],
        building_shadows=shadow_mask,
    )
    result_neut = compositor.composite(layers_neut)

    # Create comparison
    comparison = np.hstack([result_orig, result_neut])

    output = Path(args.output)
    Image.fromarray(comparison).save(output)
    print(f"\n✓ Saved comparison: {output}")
    print("   Left: Original base | Right: Neutralized base")


def cmd_list_presets(args):
    """List all available time presets."""
    from scripts.tile_pipeline.time_presets import PRESETS

    print("\n🎨 Available Time Presets:\n")

    for name, preset in PRESETS.items():
        print(f"  {name}")
        print(f"    Sun: {preset.azimuth}° azimuth, {preset.altitude}° altitude")
        print(f"    Shadows: {preset.shadow_darkness * 100:.0f}% darkness")
        print(f"    Warmth: {preset.warm_strength:.1f} warm, {preset.cool_strength:.1f} cool")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Explore and analyze tiles for the photorealistic pipeline"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Analyze command
    p_analyze = subparsers.add_parser("analyze", help="Analyze a tile")
    p_analyze.add_argument("--lat", type=float, default=47.37, help="Latitude")
    p_analyze.add_argument("--lng", type=float, default=8.54, help="Longitude")
    p_analyze.add_argument("--zoom", type=int, default=16, help="Zoom level")
    p_analyze.add_argument("--output", type=str, default="explore_output", help="Output dir")
    p_analyze.set_defaults(func=cmd_analyze)

    # Neutralize command
    p_neut = subparsers.add_parser("neutralize", help="Test neutralization")
    p_neut.add_argument("--input", type=str, required=True, help="Input image")
    p_neut.add_argument("--output", type=str, default="neutralized.png", help="Output image")
    p_neut.add_argument("--target", type=float, default=0.45, help="Target shadow level")
    p_neut.add_argument("--temperature", type=float, default=0.5, help="Temperature correction")
    p_neut.add_argument("--detail", type=float, default=0.3, help="Detail enhancement")
    p_neut.add_argument("--softness", type=float, default=15.0, help="Transition softness")
    p_neut.set_defaults(func=cmd_neutralize)

    # Preview command
    p_preview = subparsers.add_parser("preview", help="Quick preview")
    p_preview.add_argument("--lat", type=float, default=47.37, help="Latitude")
    p_preview.add_argument("--lng", type=float, default=8.54, help="Longitude")
    p_preview.add_argument("--zoom", type=int, default=16, help="Zoom level")
    p_preview.add_argument("--preset", type=str, default="afternoon", help="Time preset")
    p_preview.add_argument("--output", type=str, default="preview.png", help="Output image")
    p_preview.set_defaults(func=cmd_preview)

    # Compare command
    p_compare = subparsers.add_parser("compare", help="Compare original vs processed")
    p_compare.add_argument("--lat", type=float, default=47.37, help="Latitude")
    p_compare.add_argument("--lng", type=float, default=8.54, help="Longitude")
    p_compare.add_argument("--zoom", type=int, default=16, help="Zoom level")
    p_compare.add_argument("--preset", type=str, default="afternoon", help="Time preset")
    p_compare.add_argument("--output", type=str, default="comparison.png", help="Output image")
    p_compare.set_defaults(func=cmd_compare)

    # List presets command
    p_presets = subparsers.add_parser("presets", help="List time presets")
    p_presets.set_defaults(func=cmd_list_presets)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
