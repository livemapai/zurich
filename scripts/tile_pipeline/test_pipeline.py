#!/usr/bin/env python3
"""
Test script for validating the photorealistic tile pipeline components.

This script allows testing individual components before running the full pipeline.
Each test generates preview images for visual inspection.

Usage:
    # Test all components on a sample tile
    python -m scripts.tile_pipeline.test_pipeline --all

    # Test specific components
    python -m scripts.tile_pipeline.test_pipeline --shadow-analysis
    python -m scripts.tile_pipeline.test_pipeline --shadow-neutralization
    python -m scripts.tile_pipeline.test_pipeline --compositing
    python -m scripts.tile_pipeline.test_pipeline --compare-presets

    # Test on specific tile coordinates
    python -m scripts.tile_pipeline.test_pipeline --all --tile 16/34322/22950
"""

import argparse
from pathlib import Path
from typing import Optional
import sys

import numpy as np
from PIL import Image

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def load_test_tile(
    z: int = 16,
    x: int = 34322,
    y: int = 22950,
    cache_dir: Optional[Path] = None,
) -> np.ndarray:
    """Load a test satellite tile.

    First tries cache, then fetches from SWISSIMAGE.
    """
    from scripts.tile_pipeline.sources.satellite import SatelliteSource
    from scripts.tile_pipeline.config import PipelineConfig

    config = PipelineConfig()
    cache_dir = cache_dir or config.cache_dir

    source = SatelliteSource(cache_dir=cache_dir)
    return source.fetch_and_resize(z, x, y, 512)


def test_shadow_analysis(tile: np.ndarray, output_dir: Path) -> dict:
    """Test shadow detection and analysis.

    Generates:
    - shadow_mask.png: Binary shadow mask
    - shadow_probability.png: Soft shadow probability map
    - shadow_analysis.txt: Analysis report
    """
    from scripts.tile_pipeline.shadow_analyzer import (
        analyze_shadows,
        create_shadow_probability_map,
        estimate_capture_time,
    )

    print("\n=== Testing Shadow Analysis ===")

    # Run analysis
    analysis = analyze_shadows(tile)
    prob_map = create_shadow_probability_map(tile)
    capture_time = estimate_capture_time(analysis)

    # Save shadow mask
    mask_img = Image.fromarray((analysis.shadow_mask * 255).astype(np.uint8))
    mask_img.save(output_dir / "shadow_mask.png")
    print(f"  Saved: {output_dir / 'shadow_mask.png'}")

    # Save probability map (colorized)
    prob_colored = np.zeros((*prob_map.shape, 3), dtype=np.uint8)
    prob_colored[..., 0] = ((1 - prob_map) * 255).astype(np.uint8)  # R: lit areas
    prob_colored[..., 2] = (prob_map * 255).astype(np.uint8)  # B: shadow areas
    prob_img = Image.fromarray(prob_colored)
    prob_img.save(output_dir / "shadow_probability.png")
    print(f"  Saved: {output_dir / 'shadow_probability.png'}")

    # Save analysis report
    report = f"""Shadow Analysis Report
=====================

Shadow Coverage: {analysis.shadow_percentage:.1f}%
Shadow Intensity: {analysis.shadow_intensity:.3f} (0=black, 1=white)
Highlight Intensity: {analysis.highlight_intensity:.3f}
Contrast Ratio: {analysis.contrast_ratio:.2f}x
Shadow Edge Sharpness: {analysis.shadow_edge_sharpness:.4f}

Estimated Sun Position:
  Azimuth: {analysis.estimated_sun_azimuth:.1f}° (0=N, 90=E, 180=S, 270=W)
  Altitude: {analysis.estimated_sun_altitude:.1f}° above horizon

Estimated Capture Time:
  Period: {capture_time['period']}
  Time: ~{capture_time['time_string']} local time
  Confidence: {capture_time['confidence']}

Interpretation:
  - Sun direction: {'Morning' if analysis.estimated_sun_azimuth < 180 else 'Afternoon'} sun from {'East' if analysis.estimated_sun_azimuth < 180 else 'West'}
  - Shadow quality: {'Hard edges' if analysis.shadow_edge_sharpness > 0.05 else 'Soft edges'}
"""

    (output_dir / "shadow_analysis.txt").write_text(report)
    print(f"  Saved: {output_dir / 'shadow_analysis.txt'}")

    print(f"\n  Shadow coverage: {analysis.shadow_percentage:.1f}%")
    print(f"  Estimated sun: {analysis.estimated_sun_azimuth:.0f}° az, {analysis.estimated_sun_altitude:.0f}° alt")
    print(f"  Capture time: ~{capture_time['time_string']} ({capture_time['period']})")

    return {
        "analysis": analysis,
        "probability_map": prob_map,
        "capture_time": capture_time,
    }


def test_shadow_neutralization(
    tile: np.ndarray,
    output_dir: Path,
    analysis_results: Optional[dict] = None,
) -> dict:
    """Test shadow neutralization and relighting.

    Generates:
    - original.png: Original tile
    - neutralized_light.png: Light shadow removal
    - neutralized_medium.png: Medium shadow removal
    - neutralized_aggressive.png: Aggressive shadow removal
    - shadow_free_base.png: Maximum shadow removal
    """
    from scripts.tile_pipeline.shadow_neutralizer import (
        neutralize_shadows,
        adaptive_shadow_removal,
        create_shadow_free_base,
    )

    print("\n=== Testing Shadow Neutralization ===")

    # Save original
    Image.fromarray(tile).save(output_dir / "original.png")
    print(f"  Saved: {output_dir / 'original.png'}")

    # Test different intensity levels
    levels = {
        "light": {"target_shadow_level": 0.38, "temperature_correction": 0.2},
        "medium": {"target_shadow_level": 0.45, "temperature_correction": 0.5},
        "aggressive": {"target_shadow_level": 0.55, "temperature_correction": 0.7},
    }

    results = {"original": tile}

    for name, params in levels.items():
        result = neutralize_shadows(
            tile,
            target_shadow_level=params["target_shadow_level"],
            temperature_correction=params["temperature_correction"],
            detail_enhancement=0.3,
            transition_softness=15.0,
        )
        Image.fromarray(result).save(output_dir / f"neutralized_{name}.png")
        print(f"  Saved: {output_dir / f'neutralized_{name}.png'}")
        results[name] = result

    # Adaptive removal
    adaptive = adaptive_shadow_removal(tile)
    Image.fromarray(adaptive).save(output_dir / "neutralized_adaptive.png")
    print(f"  Saved: {output_dir / 'neutralized_adaptive.png'}")
    results["adaptive"] = adaptive

    # Shadow-free base
    shadow_free = create_shadow_free_base(tile, aggressive=True)
    Image.fromarray(shadow_free).save(output_dir / "shadow_free_base.png")
    print(f"  Saved: {output_dir / 'shadow_free_base.png'}")
    results["shadow_free"] = shadow_free

    print("\n  Compare the results visually to choose the best level.")

    return results


def test_compositing(
    tile: np.ndarray,
    neutralized: np.ndarray,
    output_dir: Path,
    z: int = 16,
    x: int = 34322,
    y: int = 22950,
) -> dict:
    """Test the full compositing pipeline.

    Generates previews with different presets applied to both
    original and neutralized base images.
    """
    from scripts.tile_pipeline.tile_compositor import TileCompositor, TileLayers
    from scripts.tile_pipeline.sources.satellite import tile_bounds_wgs84
    from scripts.tile_pipeline.sources.elevation import ElevationSource
    from scripts.tile_pipeline.hillshade import compute_hillshade_with_imhof
    from scripts.tile_pipeline.shadows import create_shadow_layers
    from scripts.tile_pipeline.time_presets import get_preset, PRESETS
    from scripts.tile_pipeline.config import PipelineConfig

    print("\n=== Testing Compositing ===")

    config = PipelineConfig()
    bounds = tile_bounds_wgs84(z, x, y)

    # Load elevation
    elevation_source = ElevationSource(cache_dir=config.cache_dir)
    elevation = elevation_source.fetch_and_resize(z, x, y, 512)

    results = {}

    # Test each preset on both original and neutralized
    presets_to_test = ["morning_golden", "afternoon", "evening_golden"]

    for preset_name in presets_to_test:
        preset = get_preset(preset_name)

        # Compute hillshade
        from scripts.tile_pipeline.sources.elevation import meters_per_pixel

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

        # Create shadow layers (empty for now - just hillshade test)
        shadow_mask = np.ones((512, 512), dtype=np.float32)

        # Test on original
        layers_original = TileLayers(
            satellite=tile,
            hillshade=hillshade_data["hillshade"],
            imhof_shift_a=hillshade_data["shift_a"],
            imhof_shift_b=hillshade_data["shift_b"],
            building_shadows=shadow_mask,
        )

        compositor = TileCompositor(config, preset)
        result_original = compositor.composite(layers_original)

        filename = f"composite_{preset_name}_original.png"
        Image.fromarray(result_original).save(output_dir / filename)
        print(f"  Saved: {output_dir / filename}")

        # Test on neutralized
        layers_neutralized = TileLayers(
            satellite=neutralized,
            hillshade=hillshade_data["hillshade"],
            imhof_shift_a=hillshade_data["shift_a"],
            imhof_shift_b=hillshade_data["shift_b"],
            building_shadows=shadow_mask,
        )

        result_neutralized = compositor.composite(layers_neutralized)

        filename = f"composite_{preset_name}_neutralized.png"
        Image.fromarray(result_neutralized).save(output_dir / filename)
        print(f"  Saved: {output_dir / filename}")

        results[preset_name] = {
            "original": result_original,
            "neutralized": result_neutralized,
        }

    return results


def test_compare_presets(
    tile: np.ndarray,
    output_dir: Path,
    z: int = 16,
    x: int = 34322,
    y: int = 22950,
) -> None:
    """Create a comparison grid of all presets.

    Generates a single image showing all time presets side by side.
    """
    from scripts.tile_pipeline.tile_renderer import preview_tile
    from scripts.tile_pipeline.time_presets import PRESETS

    print("\n=== Comparing All Presets ===")

    presets = list(PRESETS.keys())
    results = []

    for preset_name in presets:
        try:
            result = preview_tile(
                lat=47.37,  # Zurich center
                lng=8.54,
                zoom=z,
                preset_name=preset_name,
            )
            results.append((preset_name, result))
            print(f"  Generated: {preset_name}")
        except Exception as e:
            print(f"  Failed {preset_name}: {e}")

    # Create comparison grid
    if results:
        cols = min(3, len(results))
        rows = (len(results) + cols - 1) // cols

        tile_h, tile_w = results[0][1].shape[:2]
        label_height = 30

        grid = np.ones((
            rows * (tile_h + label_height),
            cols * tile_w,
            3
        ), dtype=np.uint8) * 255

        for i, (name, img) in enumerate(results):
            row = i // cols
            col = i % cols
            y_start = row * (tile_h + label_height) + label_height
            x_start = col * tile_w
            grid[y_start:y_start + tile_h, x_start:x_start + tile_w] = img

        Image.fromarray(grid).save(output_dir / "preset_comparison.png")
        print(f"\n  Saved comparison grid: {output_dir / 'preset_comparison.png'}")


def create_side_by_side(
    images: list[tuple[str, np.ndarray]],
    output_path: Path,
) -> None:
    """Create a side-by-side comparison image."""
    if not images:
        return

    h, w = images[0][1].shape[:2]
    label_h = 25

    combined = np.ones((h + label_h, w * len(images), 3), dtype=np.uint8) * 255

    for i, (label, img) in enumerate(images):
        combined[label_h:, i * w:(i + 1) * w] = img

    Image.fromarray(combined).save(output_path)


def run_full_test(
    z: int = 16,
    x: int = 34322,
    y: int = 22950,
    output_dir: Optional[Path] = None,
) -> None:
    """Run all tests and generate comprehensive output."""
    output_dir = output_dir or Path("test_output")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nPhotorealistic Tile Pipeline - Test Suite")
    print(f"=========================================")
    print(f"Tile: {z}/{x}/{y}")
    print(f"Output: {output_dir.absolute()}")

    # Load test tile
    print("\nLoading test tile...")
    tile = load_test_tile(z, x, y)
    print(f"  Loaded tile: {tile.shape}")

    # Run tests
    analysis_results = test_shadow_analysis(tile, output_dir)
    neutralization_results = test_shadow_neutralization(tile, output_dir, analysis_results)
    compositing_results = test_compositing(
        tile,
        neutralization_results["adaptive"],
        output_dir,
        z, x, y
    )

    # Create comparison images
    print("\n=== Creating Comparison Images ===")

    # Shadow neutralization comparison
    create_side_by_side([
        ("Original", tile),
        ("Light", neutralization_results["light"]),
        ("Medium", neutralization_results["medium"]),
        ("Aggressive", neutralization_results["aggressive"]),
    ], output_dir / "comparison_neutralization.png")
    print(f"  Saved: {output_dir / 'comparison_neutralization.png'}")

    # Before/after compositing
    for preset_name, results in compositing_results.items():
        create_side_by_side([
            ("Original Base", results["original"]),
            ("Neutralized Base", results["neutralized"]),
        ], output_dir / f"comparison_{preset_name}.png")
        print(f"  Saved: {output_dir / f'comparison_{preset_name}.png'}")

    print("\n" + "=" * 50)
    print("TEST COMPLETE")
    print("=" * 50)
    print(f"\nAll outputs saved to: {output_dir.absolute()}")
    print("\nKey files to review:")
    print("  - shadow_analysis.txt: Analysis report")
    print("  - comparison_neutralization.png: Shadow removal levels")
    print("  - comparison_*.png: Before/after for each preset")


def main():
    parser = argparse.ArgumentParser(
        description="Test photorealistic tile pipeline components"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Run all tests"
    )
    parser.add_argument(
        "--shadow-analysis", action="store_true",
        help="Test shadow detection and analysis"
    )
    parser.add_argument(
        "--shadow-neutralization", action="store_true",
        help="Test shadow neutralization"
    )
    parser.add_argument(
        "--compositing", action="store_true",
        help="Test full compositing pipeline"
    )
    parser.add_argument(
        "--compare-presets", action="store_true",
        help="Compare all time presets"
    )
    parser.add_argument(
        "--tile", type=str, default="16/34322/22950",
        help="Tile coordinates as z/x/y (default: 16/34322/22950)"
    )
    parser.add_argument(
        "--output", type=str, default="test_output",
        help="Output directory (default: test_output)"
    )

    args = parser.parse_args()

    # Parse tile coordinates
    z, x, y = map(int, args.tile.split("/"))
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.all or not any([
        args.shadow_analysis,
        args.shadow_neutralization,
        args.compositing,
        args.compare_presets
    ]):
        run_full_test(z, x, y, output_dir)
    else:
        # Load tile for individual tests
        print("Loading tile...")
        tile = load_test_tile(z, x, y)

        if args.shadow_analysis:
            test_shadow_analysis(tile, output_dir)

        if args.shadow_neutralization:
            test_shadow_neutralization(tile, output_dir)

        if args.compositing:
            from scripts.tile_pipeline.shadow_neutralizer import adaptive_shadow_removal
            neutralized = adaptive_shadow_removal(tile)
            test_compositing(tile, neutralized, output_dir, z, x, y)

        if args.compare_presets:
            test_compare_presets(tile, output_dir, z, x, y)


if __name__ == "__main__":
    main()
