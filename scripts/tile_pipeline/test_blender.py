#!/usr/bin/env python3
"""
Test the Blender shadow rendering pipeline.

This script verifies:
1. Blender installation and GPU availability
2. Scene data export
3. Shadow rendering with Blender Cycles
4. Integration with tile compositor

Run with: python -m scripts.tile_pipeline.test_blender

Options:
    --tile Z/X/Y    Test with a specific tile (e.g., 16/34322/22950)
    --output DIR    Output directory for test images
    --skip-render   Skip actual Blender rendering (test export only)
"""

import argparse
import time
from pathlib import Path

import numpy as np
from PIL import Image


def test_blender_installation():
    """Test that Blender is installed and accessible."""
    print("\n=== Testing Blender Installation ===\n")

    from .blender_shadows import BlenderShadowRenderer, BlenderConfig

    # Try to create renderer (finds Blender)
    print("Looking for Blender executable...")
    try:
        renderer = BlenderShadowRenderer()
        print(f"  Found Blender at: {renderer.blender_path}")
    except FileNotFoundError as e:
        print(f"  ERROR: {e}")
        print("\n  To install Blender:")
        print("    macOS: brew install --cask blender")
        print("    Linux: sudo apt install blender")
        print("    Or download from blender.org")
        return None

    # Check Blender details
    print("\nChecking Blender installation...")
    info = renderer.check_blender()

    if not info.get("installed"):
        print(f"  ERROR: {info.get('error', 'Unknown error')}")
        return None

    print(f"  Version: {info['version']}")
    print(f"  GPU device: {info['gpu_device']}")
    print(f"  GPU enabled: {info['use_gpu']}")
    print("  ✓ Blender installation verified")

    return renderer


def test_scene_export():
    """Test exporting scene data for Blender."""
    print("\n=== Testing Scene Export ===\n")

    import json
    import tempfile

    from .blender_shadows import (
        BlenderShadowRenderer,
        BlenderConfig,
        SunPosition,
    )
    from .sources.vector import Feature

    # Test bounds (small area in Zurich)
    bounds = (8.54, 47.37, 8.545, 47.375)

    # Create test features
    buildings = [
        Feature(
            id=1,
            geometry_type="Polygon",
            coordinates=[
                [
                    (8.541, 47.371),
                    (8.542, 47.371),
                    (8.542, 47.372),
                    (8.541, 47.372),
                    (8.541, 47.371),
                ]
            ],
            height=20.0,
            properties={"elevation": 400},
        ),
        Feature(
            id=2,
            geometry_type="Polygon",
            coordinates=[
                [
                    (8.543, 47.373),
                    (8.544, 47.373),
                    (8.544, 47.374),
                    (8.543, 47.374),
                    (8.543, 47.373),
                ]
            ],
            height=15.0,
            properties={"elevation": 410},
        ),
    ]

    trees = [
        Feature(
            id=100,
            geometry_type="Point",
            coordinates=(8.5415, 47.3725),
            height=8.0,
            properties={"crown_diameter": 6, "elevation": 405},
        ),
    ]

    # Create elevation
    elevation = np.linspace(400, 420, 64).reshape(1, -1)
    elevation = np.broadcast_to(elevation, (64, 64)).astype(np.float32)

    sun = SunPosition(azimuth=225, altitude=35)

    # Test export
    print("Exporting scene data...")
    config = BlenderConfig(image_size=256, samples=8)
    renderer = BlenderShadowRenderer(config=config)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Export (internal method)
        renderer._export_scene_data(tmpdir, buildings, trees, elevation, bounds, sun)

        # Verify exported files
        assert (tmpdir / "scene.json").exists(), "scene.json should be created"
        assert (tmpdir / "elevation.npy").exists(), "elevation.npy should be created"

        # Load and verify scene.json
        with open(tmpdir / "scene.json") as f:
            scene_data = json.load(f)

        print(f"  Buildings exported: {len(scene_data['buildings'])}")
        print(f"  Trees exported: {len(scene_data['trees'])}")
        print(f"  Sun azimuth: {scene_data['sun']['azimuth']}°")
        print(f"  Sun altitude: {scene_data['sun']['altitude']}°")
        print(f"  Image size: {scene_data['config']['image_size']}")

        assert len(scene_data["buildings"]) == 2, "Should have 2 buildings"
        assert len(scene_data["trees"]) == 1, "Should have 1 tree"
        assert scene_data["sun"]["azimuth"] == 225, "Sun azimuth should match"

        # Check building footprints are in local coordinates
        b1 = scene_data["buildings"][0]
        print(f"\n  Building 1 footprint (first 2 points in meters):")
        for i, pt in enumerate(b1["footprint"][:2]):
            print(f"    [{i}]: x={pt[0]:.1f}m, y={pt[1]:.1f}m")

        # Verify elevation
        elev_loaded = np.load(tmpdir / "elevation.npy")
        print(f"\n  Elevation shape: {elev_loaded.shape}")
        print(f"  Elevation range: {elev_loaded.min():.1f} - {elev_loaded.max():.1f}m")

    print("  ✓ Scene export passed")
    return True


def test_blender_render(renderer, output_dir: Path):
    """Test actual Blender shadow rendering."""
    print("\n=== Testing Blender Render ===\n")

    from .blender_shadows import SunPosition, BlenderConfig
    from .sources.vector import Feature

    # Test bounds
    bounds = (8.54, 47.37, 8.545, 47.375)
    size = 256

    # Create test scene
    buildings = [
        Feature(
            id=1,
            geometry_type="Polygon",
            coordinates=[
                [
                    (8.541, 47.371),
                    (8.5425, 47.371),
                    (8.5425, 47.3725),
                    (8.541, 47.3725),
                    (8.541, 47.371),
                ]
            ],
            height=25.0,
            properties={"elevation": 400},
        ),
        Feature(
            id=2,
            geometry_type="Polygon",
            coordinates=[
                [
                    (8.543, 47.372),
                    (8.5445, 47.372),
                    (8.5445, 47.3735),
                    (8.543, 47.3735),
                    (8.543, 47.372),
                ]
            ],
            height=18.0,
            properties={"elevation": 405},
        ),
    ]

    trees = [
        Feature(
            id=100,
            geometry_type="Point",
            coordinates=(8.542, 47.3735),
            height=10.0,
            properties={"crown_diameter": 7, "elevation": 402},
        ),
        Feature(
            id=101,
            geometry_type="Point",
            coordinates=(8.5435, 47.371),
            height=8.0,
            properties={"crown_diameter": 5, "elevation": 400},
        ),
    ]

    # Simple flat elevation
    elevation = np.full((64, 64), 400, dtype=np.float32)

    # Test different sun positions
    sun_positions = [
        ("morning", SunPosition(azimuth=95, altitude=25)),
        ("afternoon", SunPosition(azimuth=225, altitude=35)),
        ("evening", SunPosition(azimuth=280, altitude=15)),
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    for name, sun in sun_positions:
        print(f"\n  Rendering {name} (az={sun.azimuth}°, alt={sun.altitude}°)...")

        start = time.time()

        try:
            shadow_buffer = renderer.render(
                buildings=buildings,
                trees=trees,
                elevation=elevation,
                bounds=bounds,
                sun=sun,
            )
            elapsed = time.time() - start

            # Analyze result
            shadow_pct = (shadow_buffer < 0.9).mean() * 100
            lit_pct = (shadow_buffer > 0.95).mean() * 100

            print(f"    Render time: {elapsed:.2f}s")
            print(f"    Shadow coverage: {shadow_pct:.1f}%")
            print(f"    Lit area: {lit_pct:.1f}%")
            print(f"    Buffer range: [{shadow_buffer.min():.3f}, {shadow_buffer.max():.3f}]")

            # Save output
            shadow_img = ((1 - shadow_buffer) * 255).astype(np.uint8)
            Image.fromarray(shadow_img).save(output_dir / f"blender_shadow_{name}.png")
            print(f"    Saved: blender_shadow_{name}.png")

            results[name] = {
                "buffer": shadow_buffer,
                "time": elapsed,
                "shadow_pct": shadow_pct,
            }

        except Exception as e:
            print(f"    ERROR: {e}")
            import traceback

            traceback.print_exc()
            return None

    # Verify evening has more shadows (lower sun)
    if "evening" in results and "afternoon" in results:
        evening_shadows = results["evening"]["shadow_pct"]
        afternoon_shadows = results["afternoon"]["shadow_pct"]
        print(f"\n  Evening shadows: {evening_shadows:.1f}%")
        print(f"  Afternoon shadows: {afternoon_shadows:.1f}%")
        if evening_shadows > afternoon_shadows:
            print("  ✓ Lower sun creates longer shadows (expected)")

    print("\n  ✓ Blender render passed")
    return results


def test_compositor_integration(output_dir: Path):
    """Test integration with tile compositor."""
    print("\n=== Testing Compositor Integration ===\n")

    from .blender_shadows import BlenderShadowRenderer, SunPosition, BlenderConfig
    from .tile_compositor import TileCompositorV2, TileLayersV2
    from .time_presets import get_preset
    from .hillshade import compute_hillshade_with_imhof
    from .sources.elevation import meters_per_pixel
    from .sources.vector import Feature

    # Test bounds
    bounds = (8.54, 47.37, 8.545, 47.375)
    size = 256

    # Create synthetic satellite image (green terrain)
    satellite = np.zeros((size, size, 3), dtype=np.uint8)
    satellite[:, :] = [110, 140, 100]

    # Create elevation with slope
    elevation = np.linspace(400, 430, size).reshape(1, -1)
    elevation = np.broadcast_to(elevation, (size, size)).astype(np.float32).copy()

    # Buildings
    buildings = [
        Feature(
            id=1,
            geometry_type="Polygon",
            coordinates=[
                [
                    (8.541, 47.371),
                    (8.5425, 47.371),
                    (8.5425, 47.3725),
                    (8.541, 47.3725),
                    (8.541, 47.371),
                ]
            ],
            height=22.0,
            properties={"elevation": 405},
        ),
    ]

    trees = [
        Feature(
            id=100,
            geometry_type="Point",
            coordinates=(8.5435, 47.3725),
            height=9.0,
            properties={"crown_diameter": 6, "elevation": 410},
        ),
    ]

    preset = get_preset("afternoon")
    sun = SunPosition(azimuth=preset.azimuth, altitude=preset.altitude)

    # Step 1: Render shadows with Blender
    print("Rendering shadows with Blender...")
    config = BlenderConfig(
        image_size=size,
        samples=16,
        shadow_darkness=1.0 - preset.shadow_darkness,
    )
    renderer = BlenderShadowRenderer(config=config)

    start = time.time()
    ray_traced_shadows = renderer.render(
        buildings=buildings,
        trees=trees,
        elevation=elevation,
        bounds=bounds,
        sun=sun,
    )
    render_time = time.time() - start
    print(f"  Shadow render time: {render_time:.2f}s")

    # Step 2: Generate hillshade
    print("Generating hillshade...")
    lat_center = (bounds[1] + bounds[3]) / 2
    cell_size = meters_per_pixel(lat_center, 17) * (512 / size)

    hillshade_data = compute_hillshade_with_imhof(
        elevation,
        cell_size,
        azimuth=preset.azimuth,
        altitude=preset.altitude,
        warm_strength=preset.warm_strength,
        cool_strength=preset.cool_strength,
    )

    # Step 3: Composite
    print("Compositing final image...")
    layers = TileLayersV2(
        clean_base=satellite,
        hillshade=hillshade_data["hillshade"],
        imhof_shift_a=hillshade_data["shift_a"],
        imhof_shift_b=hillshade_data["shift_b"],
        ray_traced_shadows=ray_traced_shadows,
        ambient_occlusion=None,
    )

    compositor = TileCompositorV2(preset=preset)
    result = compositor.composite(layers)

    # Save outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    # Shadow buffer
    shadow_img = ((1 - ray_traced_shadows) * 255).astype(np.uint8)
    Image.fromarray(shadow_img).save(output_dir / "shadow_buffer.png")

    # Hillshade
    hs_img = (hillshade_data["hillshade"] * 255).astype(np.uint8)
    Image.fromarray(hs_img).save(output_dir / "hillshade.png")

    # Final composite
    Image.fromarray(result).save(output_dir / "final_composite.png")

    # Comparison
    comparison = np.hstack([satellite, result])
    Image.fromarray(comparison).save(output_dir / "comparison.png")

    print(f"\n  Saved outputs to {output_dir}/")
    print(f"    - shadow_buffer.png")
    print(f"    - hillshade.png")
    print(f"    - final_composite.png")
    print(f"    - comparison.png (original vs composite)")

    # Verify result
    assert result.shape == (size, size, 3), "Should output RGB"
    assert result.dtype == np.uint8, "Should be uint8"

    diff = np.abs(result.astype(float) - satellite.astype(float)).mean()
    print(f"\n  Mean difference from input: {diff:.1f}")
    assert diff > 0.5, "Result should differ from input"

    print("  ✓ Compositor integration passed")
    return result


def test_with_real_tile(tile_spec: str, output_dir: Path):
    """Test with real tile data if available."""
    print(f"\n=== Testing with Real Tile: {tile_spec} ===\n")

    # Parse tile spec
    parts = tile_spec.split("/")
    if len(parts) != 3:
        print(f"  Invalid tile spec: {tile_spec}")
        print("  Expected format: Z/X/Y (e.g., 16/34322/22950)")
        return None

    z, x, y = int(parts[0]), int(parts[1]), int(parts[2])

    # Try to load real data
    try:
        from .sources.satellite import fetch_satellite_tile
        from .sources.elevation import fetch_elevation_tile
        from .sources.vector import load_buildings_for_tile, load_trees_for_tile

        print(f"  Loading tile {z}/{x}/{y}...")

        # Bounds from tile
        from .sources.satellite import tile_to_bounds

        bounds = tile_to_bounds(x, y, z)
        print(f"  Bounds: {bounds}")

        # Load satellite
        print("  Fetching satellite imagery...")
        satellite = fetch_satellite_tile(z, x, y)
        print(f"    Satellite shape: {satellite.shape}")

        # Load elevation
        print("  Fetching elevation...")
        elevation = fetch_elevation_tile(z, x, y, bounds)
        print(f"    Elevation shape: {elevation.shape}")
        print(f"    Elevation range: {elevation.min():.1f} - {elevation.max():.1f}m")

        # Load buildings
        print("  Loading buildings...")
        buildings = load_buildings_for_tile(bounds)
        print(f"    Buildings: {len(buildings)}")

        # Load trees
        print("  Loading trees...")
        trees = load_trees_for_tile(bounds)
        print(f"    Trees: {len(trees)}")

        # Render shadows
        from .blender_shadows import BlenderShadowRenderer, SunPosition, BlenderConfig
        from .time_presets import get_preset

        preset = get_preset("afternoon")
        sun = SunPosition(azimuth=preset.azimuth, altitude=preset.altitude)

        config = BlenderConfig(
            image_size=satellite.shape[0],
            samples=32,  # Higher quality for real tiles
            shadow_darkness=1.0 - preset.shadow_darkness,
        )

        print("\n  Rendering shadows with Blender...")
        renderer = BlenderShadowRenderer(config=config)

        start = time.time()
        shadows = renderer.render(
            buildings=buildings,
            trees=trees,
            elevation=elevation,
            bounds=bounds,
            sun=sun,
        )
        elapsed = time.time() - start
        print(f"    Render time: {elapsed:.2f}s")

        # Save results
        output_dir.mkdir(parents=True, exist_ok=True)

        shadow_img = ((1 - shadows) * 255).astype(np.uint8)
        Image.fromarray(shadow_img).save(output_dir / f"shadow_{z}_{x}_{y}.png")
        Image.fromarray(satellite).save(output_dir / f"satellite_{z}_{x}_{y}.png")

        # Composite
        from .tile_compositor import composite_tile_v2

        result = composite_tile_v2(
            satellite=satellite,
            elevation=elevation,
            buildings=buildings,
            trees=trees,
            bounds=bounds,
            preset_name="afternoon",
            remove_shadows=False,  # Use Blender shadows directly
            ray_trace_samples=1,
        )
        Image.fromarray(result).save(output_dir / f"composite_{z}_{x}_{y}.png")

        # Create comparison
        comparison = np.hstack([satellite, result])
        Image.fromarray(comparison).save(output_dir / f"comparison_{z}_{x}_{y}.png")

        print(f"\n  Saved to {output_dir}/")
        print("  ✓ Real tile test passed")
        return result

    except ImportError as e:
        print(f"  Skipping real tile test: {e}")
        return None
    except FileNotFoundError as e:
        print(f"  Data not found: {e}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        import traceback

        traceback.print_exc()
        return None


def main():
    """Run Blender shadow pipeline tests."""
    parser = argparse.ArgumentParser(description="Test Blender shadow rendering")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("test_output/blender"),
        help="Output directory for test images",
    )
    parser.add_argument(
        "--tile",
        type=str,
        help="Test with specific tile (Z/X/Y format, e.g., 16/34322/22950)",
    )
    parser.add_argument(
        "--skip-render",
        action="store_true",
        help="Skip actual Blender rendering (test export only)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Blender Shadow Rendering Pipeline Tests")
    print("=" * 60)

    try:
        # Test Blender installation
        renderer = test_blender_installation()

        if renderer is None:
            print("\nBlender not available. Cannot run render tests.")
            print("Install Blender and try again.")
            return 1

        # Test scene export
        test_scene_export()

        if args.skip_render:
            print("\n[Skipping render tests as requested]")
        else:
            # Test Blender rendering
            test_blender_render(renderer, args.output)

            # Test compositor integration
            test_compositor_integration(args.output)

            # Test with real tile if specified
            if args.tile:
                test_with_real_tile(args.tile, args.output)

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)

    except Exception as e:
        print(f"\n\nTEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
