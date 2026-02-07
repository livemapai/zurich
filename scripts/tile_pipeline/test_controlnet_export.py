#!/usr/bin/env python3
"""
Test ControlNet export modes (depth, normal, edge).

Renders a sample tile using all ControlNet conditioning modes to verify
the export pipeline works correctly.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
from PIL import Image

from scripts.tile_pipeline.blender_renderer import BlenderTileRenderer, ColorRenderConfig
from scripts.tile_pipeline.blender_shadows import SunPosition
from scripts.tile_pipeline.sources.vector import VectorSource, query_features_in_tile
from scripts.tile_pipeline.sources.satellite import tile_bounds_wgs84


def main():
    """Render a sample tile in all ControlNet modes."""

    # Use tile F from our test grid (center of Zurich)
    # Tile coordinates: z=16, x=34322, y=22950
    z, x, y = 16, 34322, 22950
    bounds = tile_bounds_wgs84(z, x, y)

    print(f"=" * 60)
    print(f"  ControlNet Export Test")
    print(f"=" * 60)
    print(f"  Tile: {z}/{x}/{y}")
    print(f"  Bounds: {bounds[0]:.4f}, {bounds[1]:.4f} → {bounds[2]:.4f}, {bounds[3]:.4f}")
    print(f"=" * 60)

    # Load building and tree data
    print("\n📦 Loading data sources...")

    buildings_path = Path("public/data/zurich-buildings.geojson")
    trees_path = Path("public/data/zurich-trees.geojson")

    if not buildings_path.exists():
        print(f"  ✗ Buildings not found: {buildings_path}")
        return 1

    buildings_src = VectorSource(buildings_path, height_field="height")
    buildings = query_features_in_tile(buildings_src, bounds)
    print(f"  ✓ Buildings: {len(buildings)} features")

    trees = []
    if trees_path.exists():
        trees_src = VectorSource(trees_path, height_field="estimated_height")
        trees = query_features_in_tile(trees_src, bounds)
        print(f"  ✓ Trees: {len(trees)} features")

    # Load streets
    streets_path = Path("public/data/zurich-streets.geojson")
    streets = []
    if streets_path.exists():
        streets_src = VectorSource(streets_path, height_field="width")
        streets = query_features_in_tile(streets_src, bounds)
        print(f"  ✓ Streets: {len(streets)} features")

    # Load water bodies
    water_path = Path("public/data/zurich-water.geojson")
    water_bodies = []
    if water_path.exists():
        water_src = VectorSource(water_path, height_field="width")
        water_bodies = query_features_in_tile(water_src, bounds)
        print(f"  ✓ Water: {len(water_bodies)} features")

    # Create renderer
    print("\n🔧 Initializing Blender renderer...")
    config = ColorRenderConfig.for_mac()
    config.image_size = 512
    config.samples = 32
    renderer = BlenderTileRenderer(config=config)

    # Check Blender
    check = renderer.check_blender()
    if not check.get("installed"):
        print(f"  ✗ Blender not found: {check.get('error')}")
        return 1
    print(f"  ✓ Blender {check['version']} at {check['path']}")

    # Output directory
    output_dir = Path("scripts/tile_pipeline/assets/controlnet_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    # No elevation for simplicity
    elevation = None

    # Render all modes
    modes = [
        ("color", "Full color render", lambda: renderer.render(
            buildings, trees, elevation, bounds,
            sun=SunPosition(azimuth=225, altitude=35),
            streets=streets, water_bodies=water_bodies,
        )),
        ("depth", "Depth pass (Z-buffer)", lambda: renderer.render_depth(
            buildings, trees, elevation, bounds,
            streets=streets, water_bodies=water_bodies,
        )),
        ("normal", "Normal pass (surface orientations)", lambda: renderer.render_normal(
            buildings, trees, elevation, bounds,
            streets=streets, water_bodies=water_bodies,
        )),
        ("edge", "Edge pass (Freestyle lines)", lambda: renderer.render_edge(
            buildings, trees, elevation, bounds,
            streets=streets, water_bodies=water_bodies,
        )),
    ]

    results = []
    for mode_name, description, render_func in modes:
        print(f"\n🎨 Rendering {mode_name}...")
        print(f"   {description}")

        try:
            image = render_func()

            # Save image
            output_path = output_dir / f"tile_{mode_name}.png"
            Image.fromarray(image).save(output_path)
            print(f"   ✓ Saved: {output_path}")
            results.append(str(output_path))

        except Exception as e:
            print(f"   ✗ Error: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n" + "=" * 60)
    print(f"  ✅ Rendered {len(results)} passes to: {output_dir}")
    print(f"=" * 60)

    # Return paths for opening
    for path in results:
        print(path)

    return 0


def _render_depth(renderer, buildings, trees, elevation, bounds):
    """Render depth pass using the existing depth mode."""
    import tempfile
    import json
    from pathlib import Path

    from scripts.tile_pipeline.blender_shadows import SceneBounds

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        scene_bounds = SceneBounds(*bounds)

        # Convert buildings
        building_data = []
        for feature in buildings:
            if feature.geometry_type not in ("Polygon", "MultiPolygon"):
                continue
            height = feature.height if feature.height > 0 else 10.0
            base_z = feature.properties.get("elevation", 0)

            if feature.geometry_type == "Polygon":
                polygons = [feature.coordinates]
            else:
                polygons = feature.coordinates

            for polygon in polygons:
                if len(polygon) == 0 or len(polygon[0]) < 3:
                    continue
                footprint = [
                    list(scene_bounds.wgs84_to_local(lon, lat))
                    for lon, lat in polygon[0]
                ]
                building_data.append({
                    "footprint": footprint,
                    "height": height,
                    "elevation": base_z,
                })

        # Convert trees
        tree_data = []
        for feature in trees:
            if feature.geometry_type != "Point":
                continue
            lon, lat = feature.coordinates
            x, y = scene_bounds.wgs84_to_local(lon, lat)
            height = feature.height if feature.height > 0 else 8.0
            crown_diam = feature.properties.get("crown_diameter", 6.0)
            base_z = feature.properties.get("elevation", 0)
            tree_data.append({
                "position": [x, y, base_z],
                "height": height,
                "crown_radius": crown_diam / 2,
            })

        # Save scene.json
        scene_data = {
            "mode": "depth",
            "bounds": bounds,
            "bounds_meters": {
                "width": scene_bounds.width_meters,
                "height": scene_bounds.height_meters,
            },
            "config": {
                "image_size": renderer.config.image_size,
                "samples": 1,
                "use_gpu": renderer.config.use_gpu,
                "device": renderer.config.device,
                "tile_size": renderer.config.tile_size,
            },
            "buildings": building_data,
            "trees": tree_data,
        }

        with open(tmpdir / "scene.json", "w") as f:
            json.dump(scene_data, f)

        # Save flat elevation
        import numpy as np
        flat = np.zeros((128, 128), dtype=np.float32)
        np.save(tmpdir / "elevation.npy", flat)

        # Run blender
        output_path = tmpdir / "render.png"
        renderer._run_blender(tmpdir, output_path)

        # Load result
        from PIL import Image
        img = Image.open(output_path).convert("RGB")
        return np.array(img, dtype=np.uint8)


if __name__ == "__main__":
    sys.exit(main())
