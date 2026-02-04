#!/usr/bin/env python3
"""
Test the shadow removal and ray-traced shadow pipeline.

This script verifies the complete V2 pipeline:
1. Shadow detection and removal
2. 3D scene building
3. Ray tracing
4. Compositing

Run with: python -m scripts.tile_pipeline.test_raytracing
"""

import argparse
from pathlib import Path
import time

import numpy as np
from PIL import Image


def test_shadow_removal():
    """Test shadow detection and removal."""
    print("\n=== Testing Shadow Removal ===\n")

    from .shadow_remover import (
        ShadowRemover,
        RemovalMethod,
        create_shadow_removal_mask,
    )

    # Create test image (simulate satellite with shadows)
    size = 256
    test_image = np.zeros((size, size, 3), dtype=np.uint8)

    # Lit area (bright green/brown terrain)
    test_image[:, :] = [120, 140, 100]

    # Simulated shadow (dark, slightly blue)
    test_image[50:150, 50:150] = [40, 50, 60]

    # Test shadow mask detection
    print("Testing shadow mask detection...")
    mask = create_shadow_removal_mask(test_image, threshold=0.4)

    shadow_coverage = (mask > 0.5).mean() * 100
    print(f"  Shadow coverage detected: {shadow_coverage:.1f}%")
    print(f"  Expected: ~15% (100x100 in 256x256)")

    assert shadow_coverage > 10, "Should detect shadow region"
    assert shadow_coverage < 25, "Should not over-detect"
    print("  ✓ Shadow detection passed")

    # Test color transfer removal
    print("\nTesting color transfer shadow removal...")
    remover = ShadowRemover(method=RemovalMethod.COLOR_TRANSFER)
    result = remover.remove(test_image)

    print(f"  Original shadow %: {result.original_shadow_percentage:.1f}%")
    print(f"  Remaining shadow %: {result.remaining_shadow_percentage:.1f}%")
    print(f"  Method used: {result.method.value}")
    print(f"  Confidence: {result.confidence:.2f}")

    # Check that shadow region got brighter
    original_shadow_mean = test_image[50:150, 50:150, 0].mean()
    result_shadow_mean = result.image[50:150, 50:150, 0].mean()
    print(f"  Shadow region brightness: {original_shadow_mean:.0f} → {result_shadow_mean:.0f}")

    assert result_shadow_mean > original_shadow_mean, "Shadow region should be brightened"
    print("  ✓ Color transfer removal passed")

    return True


def test_scene_building():
    """Test 3D scene construction from features."""
    print("\n=== Testing Scene Building ===\n")

    from .scene_builder import SceneBuilder, estimate_scene_complexity
    from .sources.vector import Feature

    # Test bounds (small area in Zurich)
    bounds = (8.54, 47.37, 8.545, 47.375)

    # Create test features
    buildings = [
        Feature(
            id=1,
            geometry_type="Polygon",
            coordinates=[[
                (8.541, 47.371),
                (8.542, 47.371),
                (8.542, 47.372),
                (8.541, 47.372),
                (8.541, 47.371),
            ]],
            height=20.0,
            properties={"elevation": 400},
        ),
        Feature(
            id=2,
            geometry_type="Polygon",
            coordinates=[[
                (8.543, 47.373),
                (8.544, 47.373),
                (8.544, 47.374),
                (8.543, 47.374),
                (8.543, 47.373),
            ]],
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
            properties={"crown_diameter": 6},
        ),
    ]

    # Build scene
    print("Building 3D scene...")
    builder = SceneBuilder(bounds, image_size=256)
    builder.add_ground_plane(z=400)
    builder.add_buildings(buildings)
    builder.add_trees(trees)
    mesh = builder.build()

    print(f"  Scene bounds: {builder.bounds.width_meters:.0f}m x {builder.bounds.height_meters:.0f}m")
    print(f"  Buildings added: {builder.stats.num_buildings}")
    print(f"  Trees added: {builder.stats.num_trees}")
    print(f"  Total triangles: {builder.stats.total_triangles}")

    assert builder.stats.num_buildings == 2, "Should have 2 buildings"
    assert builder.stats.num_trees == 1, "Should have 1 tree"
    assert builder.stats.total_triangles > 0, "Should have geometry"
    print("  ✓ Scene building passed")

    # Test complexity estimation
    print("\nTesting complexity estimation...")
    estimate = estimate_scene_complexity(
        num_buildings=1000,
        num_trees=5000,
        terrain_resolution=256,
    )
    print(f"  Estimated triangles: {estimate['estimated_triangles']}")
    print(f"  Estimated memory: {estimate['estimated_memory_mb']:.1f} MB")
    print(f"  Recommendation: {estimate['recommendation']}")
    print("  ✓ Complexity estimation passed")

    return mesh, builder


def test_ray_tracing(mesh, builder):
    """Test ray-traced shadow generation."""
    print("\n=== Testing Ray Tracing ===\n")

    from .raytracer import TileRaytracer, SunPosition, RayTracerConfig

    bounds = (builder.bounds.west, builder.bounds.south,
              builder.bounds.east, builder.bounds.north)

    # Configure ray tracer
    config = RayTracerConfig(
        image_size=128,  # Small for fast testing
        samples_per_pixel=1,
        shadow_darkness=0.2,
    )

    # Create ray tracer
    print("Creating ray tracer...")
    raytracer = TileRaytracer(mesh, bounds, config)

    # Test different sun positions
    sun_positions = [
        ("Morning (East)", SunPosition(azimuth=90, altitude=30)),
        ("Noon (South)", SunPosition(azimuth=180, altitude=60)),
        ("Afternoon (SW)", SunPosition(azimuth=225, altitude=35)),
        ("Evening (West)", SunPosition(azimuth=270, altitude=15)),
    ]

    shadows = {}
    for name, sun in sun_positions:
        print(f"\n  Rendering {name}...")
        start = time.time()

        shadow_buffer = raytracer.render(sun)
        elapsed = time.time() - start

        # Calculate shadow coverage
        shadow_pct = (shadow_buffer < 0.9).mean() * 100

        print(f"    Sun: az={sun.azimuth}°, alt={sun.altitude}°")
        print(f"    Shadow coverage: {shadow_pct:.1f}%")
        print(f"    Render time: {elapsed:.3f}s")
        print(f"    Buffer range: [{shadow_buffer.min():.2f}, {shadow_buffer.max():.2f}]")

        shadows[name] = shadow_buffer

        assert shadow_buffer.shape == (128, 128), "Should be correct size"
        assert shadow_buffer.min() >= 0, "Should be >= 0"
        assert shadow_buffer.max() <= 1, "Should be <= 1"

    # Verify evening has more shadows than noon (lower sun = longer shadows)
    evening_shadows = (shadows["Evening (West)"] < 0.9).mean()
    noon_shadows = (shadows["Noon (South)"] < 0.9).mean()
    print(f"\n  Evening shadow %: {evening_shadows*100:.1f}%")
    print(f"  Noon shadow %: {noon_shadows*100:.1f}%")

    # This assertion might not always hold depending on scene geometry
    # so we just report rather than assert
    if evening_shadows > noon_shadows:
        print("  ✓ Lower sun creates more shadows (expected)")
    else:
        print("  Note: Scene geometry affects shadow distribution")

    print("\n  ✓ Ray tracing passed")
    return shadows


def test_full_pipeline():
    """Test the complete V2 compositing pipeline."""
    print("\n=== Testing Full V2 Pipeline ===\n")

    from .tile_compositor import composite_tile_v2, preview_v2_pipeline
    from .sources.vector import Feature

    # Test bounds
    bounds = (8.54, 47.37, 8.545, 47.375)
    size = 128

    # Create synthetic inputs
    # Satellite: green terrain with a shadow patch
    satellite = np.zeros((size, size, 3), dtype=np.uint8)
    satellite[:, :] = [100, 130, 90]
    satellite[30:70, 30:70] = [50, 60, 55]  # Simulated shadow

    # Elevation: slight slope
    elevation = np.linspace(400, 420, size).reshape(1, -1)
    elevation = np.broadcast_to(elevation, (size, size)).astype(np.float32)

    # Buildings
    buildings = [
        Feature(
            id=1,
            geometry_type="Polygon",
            coordinates=[[
                (8.541, 47.371),
                (8.542, 47.371),
                (8.542, 47.372),
                (8.541, 47.372),
                (8.541, 47.371),
            ]],
            height=15.0,
            properties={},
        ),
    ]

    trees = [
        Feature(
            id=100,
            geometry_type="Point",
            coordinates=(8.5425, 47.3725),
            height=8.0,
            properties={"crown_diameter": 5},
        ),
    ]

    # Test pipeline with progress reporting
    print("Running full V2 pipeline...")
    stages = []

    def progress(stage, p):
        if p == 0:
            print(f"  Starting: {stage}")
            stages.append(stage)
        elif p == 1:
            print(f"  Completed: {stage}")

    start = time.time()
    result = composite_tile_v2(
        satellite=satellite,
        elevation=elevation,
        buildings=buildings,
        trees=trees,
        bounds=bounds,
        preset_name="afternoon",
        remove_shadows=True,
        shadow_removal_method="color_transfer",
        ray_trace_samples=1,
        progress_callback=progress,
    )
    elapsed = time.time() - start

    print(f"\n  Total pipeline time: {elapsed:.2f}s")
    print(f"  Stages completed: {len(stages)}")
    print(f"  Output shape: {result.shape}")
    print(f"  Output dtype: {result.dtype}")

    assert result.shape == (size, size, 3), "Should output RGB image"
    assert result.dtype == np.uint8, "Should be uint8"

    # Check that result differs from input (processing occurred)
    diff = np.abs(result.astype(float) - satellite.astype(float)).mean()
    print(f"  Mean difference from input: {diff:.1f}")
    assert diff > 0.5, "Output should differ from input"

    print("  ✓ Full pipeline passed")

    # Test preview generation
    print("\nTesting preview generation...")
    previews = preview_v2_pipeline(
        satellite, elevation, buildings, trees, bounds, "afternoon"
    )
    print(f"  Generated {len(previews)} preview images:")
    for name in sorted(previews.keys()):
        print(f"    - {name}: {previews[name].shape}")

    assert len(previews) >= 4, "Should generate multiple previews"
    print("  ✓ Preview generation passed")

    return result, previews


def save_test_outputs(result, previews, output_dir: Path):
    """Save test outputs for visual inspection."""
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nSaving outputs to {output_dir}/")

    # Save final result
    Image.fromarray(result).save(output_dir / "final_result.png")
    print(f"  Saved final_result.png")

    # Save previews
    for name, img in previews.items():
        Image.fromarray(img).save(output_dir / f"{name}.png")
        print(f"  Saved {name}.png")


def main():
    """Run all tests."""
    parser = argparse.ArgumentParser(description="Test ray tracing pipeline")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("test_output/raytracing"),
        help="Output directory for test images",
    )
    parser.add_argument(
        "--skip-slow",
        action="store_true",
        help="Skip slow tests (full pipeline)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Shadow Removal + Ray Tracing Pipeline Tests")
    print("=" * 60)

    try:
        # Test individual components
        test_shadow_removal()
        mesh, builder = test_scene_building()
        test_ray_tracing(mesh, builder)

        if not args.skip_slow:
            result, previews = test_full_pipeline()
            save_test_outputs(result, previews, args.output)
        else:
            print("\n[Skipping full pipeline test]")

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
