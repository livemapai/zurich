"""
Full-color Blender tile renderer.

Renders complete tiles using Blender Cycles with colored materials,
bypassing satellite imagery entirely. This produces clean 3D renders
without the double-shadow problem of overlaying computed shadows on
satellite photos that already contain shadows.

Usage:
    from .blender_renderer import BlenderTileRenderer
    from .materials import get_style

    renderer = BlenderTileRenderer()
    image = renderer.render(
        buildings=building_features,
        trees=tree_features,
        elevation=elevation_array,
        bounds=(8.53, 47.37, 8.55, 47.39),
        sun=SunPosition(azimuth=225, altitude=35),
        style=get_style("default"),
    )
"""

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

from .blender_shadows import BlenderConfig, SceneBounds, SunPosition
from .materials import RenderStyle, get_style
from .sources.vector import Feature


def _crop_isometric_tile(image: NDArray[np.uint8], target_size: int = 512) -> NDArray[np.uint8]:
    """Crop center region from larger isometric render.

    This is the second part of the "render-larger-crop-exact" technique for
    isometric tile alignment. When rendering isometric tiles, Blender renders
    at 1.3× resolution (with geometry shearing for position accuracy), then we
    crop the center region to get perfectly aligned tiles.

    Args:
        image: Rendered image array (H, W, 3) - larger than target_size for isometric
        target_size: Desired output size (default 512)

    Returns:
        Cropped image array (target_size, target_size, 3)
    """
    h, w = image.shape[:2]

    # If already correct size, return as-is
    if h == target_size and w == target_size:
        return image

    # Calculate center crop coordinates
    start_y = (h - target_size) // 2
    start_x = (w - target_size) // 2

    # Ensure we don't go out of bounds
    if start_y < 0 or start_x < 0:
        # Image is smaller than target, return as-is (shouldn't happen)
        return image

    return image[start_y:start_y + target_size, start_x:start_x + target_size].copy()


@dataclass
class ColorRenderConfig(BlenderConfig):
    """Configuration for full-color Blender rendering.

    Extends BlenderConfig with color-specific settings.
    """

    # Higher default samples for quality color renders
    samples: int = 64

    # Output settings
    render_ground: bool = True  # Render visible ground plane
    render_sky: bool = True  # Use sky color background

    @classmethod
    def for_mac(cls) -> "ColorRenderConfig":
        """Preset for Mac with Metal GPU."""
        return cls(use_gpu=True, device="METAL", tile_size=512, samples=64)

    @classmethod
    def for_nvidia(cls) -> "ColorRenderConfig":
        """Preset for NVIDIA GPU with OptiX."""
        return cls(use_gpu=True, device="OPTIX", tile_size=256, samples=64)

    @classmethod
    def for_preview(cls) -> "ColorRenderConfig":
        """Fast preview preset (lower quality)."""
        return cls(use_gpu=True, device="METAL", samples=16, tile_size=256)


class BlenderTileRenderer:
    """Renders complete tiles using Blender Cycles.

    Unlike BlenderShadowRenderer which produces shadow-only passes,
    this renderer creates full RGB images with:
    - Colored building walls and roofs
    - Green vegetation (trees)
    - Textured terrain
    - Proper sun lighting and shadows

    Example:
        renderer = BlenderTileRenderer()
        image = renderer.render(
            buildings=building_features,
            trees=tree_features,
            elevation=elevation_array,
            bounds=(8.53, 47.37, 8.55, 47.39),
            sun=SunPosition(azimuth=225, altitude=35),
            style=get_style("zurich"),
        )
    """

    def __init__(
        self,
        blender_path: Optional[str] = None,
        config: Optional[ColorRenderConfig] = None,
    ):
        """Initialize Blender tile renderer.

        Args:
            blender_path: Path to Blender executable. If None, searches PATH.
            config: Render configuration.
        """
        self.blender_path = blender_path or self._find_blender()
        self.config = config or ColorRenderConfig()

    def _find_blender(self) -> str:
        """Find Blender executable in system PATH."""
        locations = [
            "blender",
            "/Applications/Blender.app/Contents/MacOS/Blender",
            "/usr/bin/blender",
            "C:\\Program Files\\Blender Foundation\\Blender\\blender.exe",
        ]

        for path in locations:
            if shutil.which(path):
                return path
            if Path(path).exists():
                return path

        raise FileNotFoundError(
            "Blender executable not found. Install Blender or specify blender_path. "
            "On macOS: brew install --cask blender"
        )

    def render(
        self,
        buildings: List[Feature],
        trees: List[Feature],
        elevation: Optional[NDArray[np.float32]],
        bounds: Tuple[float, float, float, float],
        sun: SunPosition,
        style: Optional[RenderStyle] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        streets: Optional[List[Feature]] = None,
        water_bodies: Optional[List[Feature]] = None,
    ) -> NDArray[np.uint8]:
        """Render a full-color tile.

        Args:
            buildings: Building features with footprints and heights
            trees: Tree features with positions and heights
            elevation: Elevation heightmap (H, W) in meters, or None for flat
            bounds: (west, south, east, north) in WGS84
            sun: Sun position for lighting/shadows
            style: Visual style (uses 'default' if None)
            progress_callback: Optional callback(stage, progress) for updates
            streets: Street features with centerlines and widths (optional)
            water_bodies: Water body features - polygons for lakes, lines for rivers (optional)

        Returns:
            RGB image array (H, W, 3) uint8
        """
        style = style or get_style("default")

        def report(stage: str, progress: float):
            if progress_callback:
                progress_callback(stage, progress)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Step 1: Export scene data with style
            report("export", 0.0)
            self._export_scene_data(
                tmpdir, buildings, trees, elevation, bounds, sun, style,
                streets=streets, water_bodies=water_bodies
            )
            report("export", 1.0)

            # Step 2: Run Blender in color mode
            report("render", 0.0)
            output_path = tmpdir / "render.png"
            self._run_blender(tmpdir, output_path)
            report("render", 0.9)

            # Step 3: Load result
            image = self._load_rendered_image(output_path)
            report("render", 1.0)

            return image

    def _export_scene_data(
        self,
        tmpdir: Path,
        buildings: List[Feature],
        trees: List[Feature],
        elevation: Optional[NDArray[np.float32]],
        bounds: Tuple[float, float, float, float],
        sun: SunPosition,
        style: RenderStyle,
        streets: Optional[List[Feature]] = None,
        water_bodies: Optional[List[Feature]] = None,
        roof_faces: Optional[List[dict]] = None,
    ) -> None:
        """Export all scene data to temporary directory."""
        from .geometry import buffer_line_to_polygon

        scene_bounds = SceneBounds(*bounds)

        # Convert buildings to simple format
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

                building_data.append(
                    {
                        "footprint": footprint,
                        "height": height,
                        "elevation": base_z,
                        # Data-driven: include building type for per-type materials
                        "type": feature.properties.get("art", "default"),
                        "id": feature.id,
                    }
                )

        # Convert trees to simple format
        tree_data = []
        for feature in trees:
            if feature.geometry_type != "Point":
                continue

            lon, lat = feature.coordinates
            x, y = scene_bounds.wgs84_to_local(lon, lat)

            height = feature.height if feature.height > 0 else 8.0
            crown_diam = feature.properties.get("crown_diameter", 6.0)
            base_z = feature.properties.get("elevation", 0)

            tree_data.append(
                {
                    "position": [x, y, base_z],
                    "height": height,
                    "crown_radius": crown_diam / 2,
                    # Data-driven: include species for per-species colors
                    "species": feature.properties.get("baumgattunglat", "")
                              or feature.properties.get("species", ""),
                    "id": feature.id,
                }
            )

        # Convert streets to polygons (buffer centerlines)
        street_data = []
        if streets:
            for feature in streets:
                if feature.geometry_type not in ("LineString", "MultiLineString"):
                    continue

                # Get width from height field (VectorSource uses height_field)
                width = feature.height if feature.height > 0 else 6.0
                base_z = feature.properties.get("elevation", 0) + 0.05  # Slightly above terrain

                # Handle LineString and MultiLineString
                if feature.geometry_type == "LineString":
                    lines = [feature.coordinates]
                else:
                    lines = feature.coordinates

                for line_coords in lines:
                    wgs84_coords = [(c[0], c[1]) for c in line_coords]

                    # Buffer to polygon
                    poly_coords = buffer_line_to_polygon(
                        wgs84_coords,
                        width_meters=width,
                        cap_style="flat",
                        latitude=scene_bounds.lat_center,
                    )

                    if poly_coords and len(poly_coords) >= 3:
                        # Convert to local coordinates
                        footprint = [
                            list(scene_bounds.wgs84_to_local(lon, lat))
                            for lon, lat in poly_coords
                        ]

                        street_data.append({
                            "footprint": footprint,
                            "elevation": base_z,
                            "street_type": feature.properties.get("street_type", "default"),
                            "id": feature.id,
                        })

        # Convert water bodies to polygons
        water_data = []
        if water_bodies:
            for feature in water_bodies:
                base_z = feature.properties.get("elevation", 0) - 0.1  # Slightly below terrain
                water_type = feature.properties.get("water_type", "default")

                if feature.geometry_type == "Polygon":
                    # Lakes/ponds - use directly
                    if len(feature.coordinates) > 0 and len(feature.coordinates[0]) >= 3:
                        footprint = [
                            list(scene_bounds.wgs84_to_local(c[0], c[1]))
                            for c in feature.coordinates[0]
                        ]
                        water_data.append({
                            "footprint": footprint,
                            "elevation": base_z,
                            "water_type": water_type,
                            "id": feature.id,
                        })

                elif feature.geometry_type == "MultiPolygon":
                    for polygon in feature.coordinates:
                        if len(polygon) > 0 and len(polygon[0]) >= 3:
                            footprint = [
                                list(scene_bounds.wgs84_to_local(c[0], c[1]))
                                for c in polygon[0]
                            ]
                            water_data.append({
                                "footprint": footprint,
                                "elevation": base_z,
                                "water_type": water_type,
                                "id": feature.id,
                            })

                elif feature.geometry_type == "LineString":
                    # Rivers/streams - buffer to polygon
                    width = feature.height if feature.height > 0 else 5.0
                    wgs84_coords = [(c[0], c[1]) for c in feature.coordinates]

                    poly_coords = buffer_line_to_polygon(
                        wgs84_coords,
                        width_meters=width,
                        cap_style="round",
                        latitude=scene_bounds.lat_center,
                    )

                    if poly_coords and len(poly_coords) >= 3:
                        footprint = [
                            list(scene_bounds.wgs84_to_local(lon, lat))
                            for lon, lat in poly_coords
                        ]
                        water_data.append({
                            "footprint": footprint,
                            "elevation": base_z,
                            "water_type": water_type,
                            "id": feature.id,
                        })

                elif feature.geometry_type == "MultiLineString":
                    width = feature.height if feature.height > 0 else 5.0
                    for line_coords in feature.coordinates:
                        wgs84_coords = [(c[0], c[1]) for c in line_coords]

                        poly_coords = buffer_line_to_polygon(
                            wgs84_coords,
                            width_meters=width,
                            cap_style="round",
                            latitude=scene_bounds.lat_center,
                        )

                        if poly_coords and len(poly_coords) >= 3:
                            footprint = [
                                list(scene_bounds.wgs84_to_local(lon, lat))
                                for lon, lat in poly_coords
                            ]
                            water_data.append({
                                "footprint": footprint,
                                "elevation": base_z,
                                "water_type": water_type,
                                "id": feature.id,
                            })

        # Save scene.json with color mode and style
        scene_data = {
            "mode": "color",  # Key flag for color rendering
            "bounds": bounds,
            "bounds_meters": {
                "width": scene_bounds.width_meters,
                "height": scene_bounds.height_meters,
            },
            "sun": {
                "azimuth": sun.azimuth,
                "altitude": sun.altitude,
                "angular_size": sun.angular_size,
            },
            "style": style.to_dict(),
            "config": {
                "image_size": self.config.image_size,
                "samples": self.config.samples,
                "use_gpu": self.config.use_gpu,
                "device": self.config.device,
                "tile_size": self.config.tile_size,
                "soft_shadows": self.config.soft_shadows,
                "render_ground": self.config.render_ground,
                "render_sky": self.config.render_sky,
            },
            "buildings": building_data,
            "trees": tree_data,
            "streets": street_data,
            "water_bodies": water_data,
            "roof_faces": roof_faces or [],
        }

        with open(tmpdir / "scene.json", "w") as f:
            json.dump(scene_data, f)

        # Save elevation
        if elevation is not None and elevation.size > 0:
            np.save(tmpdir / "elevation.npy", elevation)
        else:
            flat = np.zeros(
                (self.config.image_size // 4, self.config.image_size // 4),
                dtype=np.float32,
            )
            np.save(tmpdir / "elevation.npy", flat)

    def _run_blender(self, data_dir: Path, output_path: Path) -> None:
        """Run Blender headlessly to render the tile."""
        script_path = Path(__file__).parent / "blender_scene.py"

        if not script_path.exists():
            raise FileNotFoundError(
                f"Blender scene script not found: {script_path}"
            )

        cmd = [
            self.blender_path,
            "--background",
            "--python",
            str(script_path),
            "--",
            "--data-dir",
            str(data_dir),
            "--output",
            str(output_path),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout
            raise RuntimeError(
                f"Blender render failed (exit code {result.returncode}):\n{error_msg}"
            )

    def _load_rendered_image(self, path: Path) -> NDArray[np.uint8]:
        """Load rendered image from file.

        For isometric renders, this also handles the center crop to get
        pixel-perfect tile alignment.
        """
        from PIL import Image

        if not path.exists():
            raise FileNotFoundError(f"Rendered image not found: {path}")

        img = Image.open(path).convert("RGB")
        image = np.array(img, dtype=np.uint8)

        # Check for render metadata (written by blender_scene.py)
        meta_path = path.parent / "render_meta.json"
        if meta_path.exists():
            with open(meta_path) as f:
                render_meta = json.load(f)

            # If isometric render (render_scale > 1.0), crop to target size
            render_scale = render_meta.get("render_scale", 1.0)
            target_size = render_meta.get("target_size", self.config.image_size)

            if render_scale > 1.0:
                image = _crop_isometric_tile(image, target_size)
        else:
            # Fallback: resize to configured size if needed
            target_size = (self.config.image_size, self.config.image_size)
            if img.size != target_size:
                img = img.resize(target_size, Image.Resampling.LANCZOS)
                image = np.array(img, dtype=np.uint8)

        return image

    def render_semantic(
        self,
        buildings: List[Feature],
        trees: List[Feature],
        elevation: Optional[NDArray[np.float32]],
        bounds: Tuple[float, float, float, float],
        progress_callback: Optional[Callable[[str, float], None]] = None,
        streets: Optional[List[Feature]] = None,
        water_bodies: Optional[List[Feature]] = None,
    ) -> NDArray[np.uint8]:
        """Render a semantic conditioning tile.

        Produces a top-down view with class-colored elements:
        - Roofs colored by type (terracotta, slate, flat)
        - Water bodies in blue
        - Trees in green
        - Streets in dark gray
        - Ground in light green

        This semantic map helps LLMs understand scene structure
        for better style transfer results.

        Args:
            buildings: Building features with footprints and heights
            trees: Tree features with positions and heights
            elevation: Elevation heightmap (H, W) in meters, or None for flat
            bounds: (west, south, east, north) in WGS84
            progress_callback: Optional callback(stage, progress) for updates
            streets: Street features (optional)
            water_bodies: Water body features (optional)

        Returns:
            RGB image array (H, W, 3) uint8
        """
        from .materials import (
            SEMANTIC_ROOF_COLORS,
            SEMANTIC_WATER_COLORS,
            SEMANTIC_ELEMENT_COLORS,
            infer_roof_material,
        )

        def report(stage: str, progress: float):
            if progress_callback:
                progress_callback(stage, progress)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Export scene data with semantic mode
            report("export", 0.0)
            self._export_semantic_scene_data(
                tmpdir, buildings, trees, elevation, bounds,
                streets=streets, water_bodies=water_bodies
            )
            report("export", 1.0)

            # Run Blender in semantic mode
            report("render", 0.0)
            output_path = tmpdir / "render.png"
            self._run_blender(tmpdir, output_path)
            report("render", 0.9)

            # Load result
            image = self._load_rendered_image(output_path)
            report("render", 1.0)

            return image

    def _export_semantic_scene_data(
        self,
        tmpdir: Path,
        buildings: List[Feature],
        trees: List[Feature],
        elevation: Optional[NDArray[np.float32]],
        bounds: Tuple[float, float, float, float],
        streets: Optional[List[Feature]] = None,
        water_bodies: Optional[List[Feature]] = None,
    ) -> None:
        """Export scene data for semantic rendering."""
        from .blender_shadows import SceneBounds
        from .geometry import buffer_line_to_polygon
        from .materials import (
            SEMANTIC_ROOF_COLORS,
            SEMANTIC_WATER_COLORS,
            SEMANTIC_ELEMENT_COLORS,
            infer_roof_material,
        )

        scene_bounds = SceneBounds(*bounds)

        # Convert buildings with roof material inference
        building_data = []
        for feature in buildings:
            if feature.geometry_type not in ("Polygon", "MultiPolygon"):
                continue

            height = feature.height if feature.height > 0 else 10.0
            base_z = feature.properties.get("elevation", 0)
            building_type = feature.properties.get("art", "default")
            roof_material = infer_roof_material(building_type)

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
                    "type": building_type,
                    "roof_material": roof_material,
                    "id": feature.id,
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
                "id": feature.id,
            })

        # Convert streets
        street_data = []
        if streets:
            for feature in streets:
                if feature.geometry_type not in ("LineString", "MultiLineString"):
                    continue

                width = feature.height if feature.height > 0 else 6.0
                base_z = feature.properties.get("elevation", 0) + 0.05

                if feature.geometry_type == "LineString":
                    lines = [feature.coordinates]
                else:
                    lines = feature.coordinates

                for line_coords in lines:
                    # Skip very short streets (cause artifacts)
                    if len(line_coords) < 3:
                        continue
                    wgs84_coords = [(c[0], c[1]) for c in line_coords]
                    poly_coords = buffer_line_to_polygon(
                        wgs84_coords,
                        width_meters=width,
                        cap_style="flat",
                        latitude=scene_bounds.lat_center,
                    )

                    if poly_coords and len(poly_coords) >= 3:
                        footprint = [
                            list(scene_bounds.wgs84_to_local(lon, lat))
                            for lon, lat in poly_coords
                        ]
                        street_data.append({
                            "footprint": footprint,
                            "elevation": base_z,
                            "id": feature.id,
                        })

        # Convert water bodies
        water_data = []
        if water_bodies:
            for feature in water_bodies:
                base_z = feature.properties.get("elevation", 0) + 0.2  # ABOVE ground for visibility
                water_type = feature.properties.get("water_type", "default")

                if feature.geometry_type == "Polygon":
                    if len(feature.coordinates) > 0 and len(feature.coordinates[0]) >= 3:
                        footprint = [
                            list(scene_bounds.wgs84_to_local(c[0], c[1]))
                            for c in feature.coordinates[0]
                        ]
                        water_data.append({
                            "footprint": footprint,
                            "elevation": base_z,
                            "water_type": water_type,
                            "id": feature.id,
                        })

                elif feature.geometry_type == "MultiPolygon":
                    for polygon in feature.coordinates:
                        if len(polygon) > 0 and len(polygon[0]) >= 3:
                            footprint = [
                                list(scene_bounds.wgs84_to_local(c[0], c[1]))
                                for c in polygon[0]
                            ]
                            water_data.append({
                                "footprint": footprint,
                                "elevation": base_z,
                                "water_type": water_type,
                                "id": feature.id,
                            })

                elif feature.geometry_type == "LineString":
                    width = feature.height if feature.height > 0 else 5.0
                    wgs84_coords = [(c[0], c[1]) for c in feature.coordinates]
                    poly_coords = buffer_line_to_polygon(
                        wgs84_coords,
                        width_meters=width,
                        cap_style="round",
                        latitude=scene_bounds.lat_center,
                    )
                    if poly_coords and len(poly_coords) >= 3:
                        # CLIP to tile bounds - rivers extend beyond tiles!
                        from .geometry import clip_polygon_to_bounds
                        clipped = clip_polygon_to_bounds(poly_coords, bounds)
                        if clipped and len(clipped) >= 3:
                            footprint = [
                                list(scene_bounds.wgs84_to_local(lon, lat))
                                for lon, lat in clipped
                            ]
                            water_data.append({
                                "footprint": footprint,
                                "elevation": base_z,
                                "water_type": water_type,
                                "id": feature.id,
                            })

        # Build semantic color definitions
        semantic_colors = {
            "roof": {k: list(v) for k, v in SEMANTIC_ROOF_COLORS.items()},
            "water": {k: list(v) for k, v in SEMANTIC_WATER_COLORS.items()},
            "trees": list(SEMANTIC_ELEMENT_COLORS.get("trees", (0.25, 0.48, 0.20))),
            "streets": list(SEMANTIC_ELEMENT_COLORS.get("streets", (0.35, 0.35, 0.38))),
            "ground": list(SEMANTIC_ELEMENT_COLORS.get("ground", (0.45, 0.55, 0.35))),
            "building_wall": list(SEMANTIC_ELEMENT_COLORS.get("building_wall", (0.92, 0.88, 0.82))),
        }

        # Save scene.json with semantic mode
        scene_data = {
            "mode": "semantic",
            "bounds": bounds,
            "bounds_meters": {
                "width": scene_bounds.width_meters,
                "height": scene_bounds.height_meters,
            },
            "sun": {
                "azimuth": 225,
                "altitude": 60,
                "angular_size": 1.0,
            },
            "style": {
                "semantic_colors": semantic_colors,
            },
            "config": {
                "image_size": self.config.image_size,
                "samples": 16,  # Low samples for semantic mode
                "use_gpu": self.config.use_gpu,
                "device": self.config.device,
                "tile_size": self.config.tile_size,
                "soft_shadows": True,
            },
            "buildings": building_data,
            "trees": tree_data,
            "streets": street_data,
            "water_bodies": water_data,
        }

        with open(tmpdir / "scene.json", "w") as f:
            json.dump(scene_data, f)

        # Save elevation
        if elevation is not None and elevation.size > 0:
            np.save(tmpdir / "elevation.npy", elevation)
        else:
            flat = np.zeros(
                (self.config.image_size // 4, self.config.image_size // 4),
                dtype=np.float32,
            )
            np.save(tmpdir / "elevation.npy", flat)

    def render_depth(
        self,
        buildings: List[Feature],
        trees: List[Feature],
        elevation: Optional[NDArray[np.float32]],
        bounds: Tuple[float, float, float, float],
        progress_callback: Optional[Callable[[str, float], None]] = None,
        streets: Optional[List[Feature]] = None,
        water_bodies: Optional[List[Feature]] = None,
    ) -> NDArray[np.uint8]:
        """Render a depth map for ControlNet conditioning.

        Produces a grayscale image where:
        - Black (0) = objects close to camera (rooftops, tall buildings)
        - White (255) = objects far from camera (ground level)

        This depth map preserves 3D structure during AI style transfer,
        maintaining building heights and spatial relationships.

        Args:
            buildings: Building features with footprints and heights
            trees: Tree features with positions and heights
            elevation: Elevation heightmap (H, W) in meters, or None for flat
            bounds: (west, south, east, north) in WGS84
            progress_callback: Optional callback(stage, progress) for updates
            streets: Street features with centerlines and widths (optional)
            water_bodies: Water body features (optional)

        Returns:
            RGB image array (H, W, 3) uint8 with depth-encoded grayscale
        """
        def report(stage: str, progress: float):
            if progress_callback:
                progress_callback(stage, progress)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Export scene data with depth mode
            report("export", 0.0)
            self._export_controlnet_scene_data(
                tmpdir, buildings, trees, elevation, bounds, mode="depth",
                streets=streets, water_bodies=water_bodies
            )
            report("export", 1.0)

            # Run Blender in depth mode
            report("render", 0.0)
            output_path = tmpdir / "render.png"
            self._run_blender(tmpdir, output_path)
            report("render", 0.9)

            # Load result
            image = self._load_rendered_image(output_path)
            report("render", 1.0)

            return image

    def render_normal(
        self,
        buildings: List[Feature],
        trees: List[Feature],
        elevation: Optional[NDArray[np.float32]],
        bounds: Tuple[float, float, float, float],
        progress_callback: Optional[Callable[[str, float], None]] = None,
        streets: Optional[List[Feature]] = None,
        water_bodies: Optional[List[Feature]] = None,
    ) -> NDArray[np.uint8]:
        """Render a world-space normal map for ControlNet conditioning.

        Produces an RGB image where:
        - R = X component of surface normal (-1 to 1 → 0 to 255)
        - G = Y component of surface normal (-1 to 1 → 0 to 255)
        - B = Z component of surface normal (-1 to 1 → 0 to 255)

        This normal map preserves surface orientations during AI style transfer,
        ensuring building facades and roof angles are maintained.

        Args:
            buildings: Building features with footprints and heights
            trees: Tree features with positions and heights
            elevation: Elevation heightmap (H, W) in meters, or None for flat
            bounds: (west, south, east, north) in WGS84
            progress_callback: Optional callback(stage, progress) for updates
            streets: Street features with centerlines and widths (optional)
            water_bodies: Water body features (optional)

        Returns:
            RGB image array (H, W, 3) uint8 with normal-encoded colors
        """
        def report(stage: str, progress: float):
            if progress_callback:
                progress_callback(stage, progress)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Export scene data with normal mode
            report("export", 0.0)
            self._export_controlnet_scene_data(
                tmpdir, buildings, trees, elevation, bounds, mode="normal",
                streets=streets, water_bodies=water_bodies
            )
            report("export", 1.0)

            # Run Blender in normal mode
            report("render", 0.0)
            output_path = tmpdir / "render.png"
            self._run_blender(tmpdir, output_path)
            report("render", 0.9)

            # Load result
            image = self._load_rendered_image(output_path)
            report("render", 1.0)

            return image

    def render_edge(
        self,
        buildings: List[Feature],
        trees: List[Feature],
        elevation: Optional[NDArray[np.float32]],
        bounds: Tuple[float, float, float, float],
        progress_callback: Optional[Callable[[str, float], None]] = None,
        streets: Optional[List[Feature]] = None,
        water_bodies: Optional[List[Feature]] = None,
    ) -> NDArray[np.uint8]:
        """Render an edge/line map for ControlNet Canny/HED conditioning.

        Produces a black-on-white image showing architectural edges:
        - Building silhouettes
        - Roof edges
        - Street edges
        - Sharp geometry transitions

        This edge map preserves geometry structure during AI style transfer,
        similar to a Canny edge detector but extracted directly from 3D.

        Args:
            buildings: Building features with footprints and heights
            trees: Tree features with positions and heights
            elevation: Elevation heightmap (H, W) in meters, or None for flat
            bounds: (west, south, east, north) in WGS84
            progress_callback: Optional callback(stage, progress) for updates
            streets: Street features with centerlines and widths (optional)
            water_bodies: Water body features (optional)

        Returns:
            RGB image array (H, W, 3) uint8 with black lines on white background
        """
        def report(stage: str, progress: float):
            if progress_callback:
                progress_callback(stage, progress)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Export scene data with edge mode
            report("export", 0.0)
            self._export_controlnet_scene_data(
                tmpdir, buildings, trees, elevation, bounds, mode="edge",
                streets=streets, water_bodies=water_bodies
            )
            report("export", 1.0)

            # Run Blender in edge mode
            report("render", 0.0)
            output_path = tmpdir / "render.png"
            self._run_blender(tmpdir, output_path)
            report("render", 0.9)

            # Load result
            image = self._load_rendered_image(output_path)
            report("render", 1.0)

            return image

    def _export_controlnet_scene_data(
        self,
        tmpdir: Path,
        buildings: List[Feature],
        trees: List[Feature],
        elevation: Optional[NDArray[np.float32]],
        bounds: Tuple[float, float, float, float],
        mode: str = "normal",
        streets: Optional[List[Feature]] = None,
        water_bodies: Optional[List[Feature]] = None,
    ) -> None:
        """Export scene data for ControlNet render modes (depth, normal, edge).

        Includes geometry data needed for control signal generation.

        Args:
            tmpdir: Temporary directory for export
            buildings: Building features
            trees: Tree features
            elevation: Elevation array
            bounds: WGS84 bounds
            mode: Render mode ('depth', 'normal', or 'edge')
            streets: Street features (optional)
            water_bodies: Water body features (optional)
        """
        from .geometry import buffer_line_to_polygon

        scene_bounds = SceneBounds(*bounds)

        # Convert buildings to simple format
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

        # Convert trees to simple format
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

        # Convert streets to polygons (buffer centerlines)
        street_data = []
        if streets:
            for feature in streets:
                if feature.geometry_type not in ("LineString", "MultiLineString"):
                    continue

                width = feature.height if feature.height > 0 else 6.0
                base_z = feature.properties.get("elevation", 0) + 0.05

                if feature.geometry_type == "LineString":
                    lines = [feature.coordinates]
                else:
                    lines = feature.coordinates

                for line_coords in lines:
                    wgs84_coords = [(c[0], c[1]) for c in line_coords]

                    poly_coords = buffer_line_to_polygon(
                        wgs84_coords,
                        width_meters=width,
                        cap_style="flat",
                        latitude=scene_bounds.lat_center,
                    )

                    if poly_coords and len(poly_coords) >= 3:
                        footprint = [
                            list(scene_bounds.wgs84_to_local(lon, lat))
                            for lon, lat in poly_coords
                        ]
                        street_data.append({
                            "footprint": footprint,
                            "elevation": base_z,
                        })

        # Convert water bodies
        water_data = []
        if water_bodies:
            for feature in water_bodies:
                base_z = feature.properties.get("elevation", 0) + 0.02

                if feature.geometry_type == "Polygon":
                    if len(feature.coordinates) > 0 and len(feature.coordinates[0]) >= 3:
                        footprint = [
                            list(scene_bounds.wgs84_to_local(c[0], c[1]))
                            for c in feature.coordinates[0]
                        ]
                        water_data.append({
                            "footprint": footprint,
                            "elevation": base_z,
                        })

                elif feature.geometry_type == "MultiPolygon":
                    for polygon in feature.coordinates:
                        if len(polygon) > 0 and len(polygon[0]) >= 3:
                            footprint = [
                                list(scene_bounds.wgs84_to_local(c[0], c[1]))
                                for c in polygon[0]
                            ]
                            water_data.append({
                                "footprint": footprint,
                                "elevation": base_z,
                            })

                elif feature.geometry_type == "LineString":
                    width = feature.height if feature.height > 0 else 5.0
                    wgs84_coords = [(c[0], c[1]) for c in feature.coordinates]
                    poly_coords = buffer_line_to_polygon(
                        wgs84_coords,
                        width_meters=width,
                        cap_style="round",
                        latitude=scene_bounds.lat_center,
                    )
                    if poly_coords and len(poly_coords) >= 3:
                        footprint = [
                            list(scene_bounds.wgs84_to_local(lon, lat))
                            for lon, lat in poly_coords
                        ]
                        water_data.append({
                            "footprint": footprint,
                            "elevation": base_z,
                        })

        # Save scene.json with specified mode
        scene_data = {
            "mode": mode,  # 'depth', 'normal', or 'edge'
            "bounds": bounds,
            "bounds_meters": {
                "width": scene_bounds.width_meters,
                "height": scene_bounds.height_meters,
            },
            "config": {
                "image_size": self.config.image_size,
                "samples": 4,  # Slightly more samples for quality
                "use_gpu": self.config.use_gpu,
                "device": self.config.device,
                "tile_size": self.config.tile_size,
            },
            "buildings": building_data,
            "trees": tree_data,
            "streets": street_data,
            "water_bodies": water_data,
        }

        with open(tmpdir / "scene.json", "w") as f:
            json.dump(scene_data, f)

        # Save elevation
        if elevation is not None and elevation.size > 0:
            np.save(tmpdir / "elevation.npy", elevation)
        else:
            flat = np.zeros(
                (self.config.image_size // 4, self.config.image_size // 4),
                dtype=np.float32,
            )
            np.save(tmpdir / "elevation.npy", flat)

    def check_blender(self) -> dict:
        """Check Blender installation and GPU capabilities."""
        cmd = [
            self.blender_path,
            "--background",
            "--python-expr",
            "import bpy; print('VERSION:', bpy.app.version_string); "
            "import sys; sys.exit(0)",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            return {"installed": False, "error": result.stderr}

        version = "unknown"
        for line in result.stdout.split("\n"):
            if "VERSION:" in line:
                version = line.split("VERSION:")[1].strip()

        return {
            "installed": True,
            "path": self.blender_path,
            "version": version,
            "gpu_device": self.config.device,
            "use_gpu": self.config.use_gpu,
        }


def render_blender_tile(
    buildings: List[Feature],
    trees: List[Feature],
    elevation: Optional[NDArray[np.float32]],
    bounds: Tuple[float, float, float, float],
    sun_azimuth: float,
    sun_altitude: float,
    style_name: str = "default",
    image_size: int = 512,
    samples: int = 64,
    use_gpu: bool = True,
) -> NDArray[np.uint8]:
    """Convenience function to render a tile with Blender.

    Args:
        buildings: Building features
        trees: Tree features
        elevation: Elevation array (optional)
        bounds: (west, south, east, north) in WGS84
        sun_azimuth: Sun azimuth in degrees
        sun_altitude: Sun altitude in degrees
        style_name: Visual style name
        image_size: Output resolution
        samples: Render samples (higher=better quality)
        use_gpu: Use GPU rendering if available

    Returns:
        RGB image array (size, size, 3)

    Example:
        image = render_blender_tile(
            buildings, trees, elevation,
            bounds=(8.53, 47.37, 8.55, 47.39),
            sun_azimuth=225,
            sun_altitude=35,
            style_name="zurich",
        )
    """
    config = ColorRenderConfig(
        image_size=image_size,
        samples=samples,
        use_gpu=use_gpu,
    )

    renderer = BlenderTileRenderer(config=config)
    sun = SunPosition(azimuth=sun_azimuth, altitude=sun_altitude)
    style = get_style(style_name)

    return renderer.render(buildings, trees, elevation, bounds, sun, style)


def render_styled_tile(
    buildings: List[Feature],
    trees: List[Feature],
    elevation: Optional[NDArray[np.float32]],
    bounds: Tuple[float, float, float, float],
    style_preset: str = "default",
    llm_style: Optional[dict] = None,
    image_size: int = 512,
    samples: int = 64,
    use_gpu: bool = True,
) -> NDArray[np.uint8]:
    """Render a tile with data-driven materials and optional LLM style.

    This is the main entry point for hybrid styled rendering that combines:
    - Data-driven per-building materials (based on building type)
    - Data-driven per-tree colors (based on species and season)
    - LLM-generated creative style parameters

    Args:
        buildings: Building features (with type from 'art' property)
        trees: Tree features (with species from 'baumgattunglat' property)
        elevation: Elevation array (optional)
        bounds: (west, south, east, north) in WGS84
        style_preset: Style preset name (spring, summer, autumn, winter, cyberpunk, etc.)
        llm_style: Optional LLM-generated style dict (from llm_variation.py or vision_blender.py)
        image_size: Output resolution
        samples: Render samples (higher=better quality)
        use_gpu: Use GPU rendering if available

    Returns:
        RGB image array (size, size, 3)

    Example:
        # Simple seasonal rendering
        image = render_styled_tile(
            buildings, trees, elevation,
            bounds=(8.53, 47.37, 8.55, 47.39),
            style_preset="autumn",
        )

        # With LLM-generated style
        from .llm_variation import generate_llm_style
        llm_params = generate_llm_style("cyberpunk rain night")
        image = render_styled_tile(
            buildings, trees, elevation,
            bounds=(8.53, 47.37, 8.55, 47.39),
            style_preset="night",
            llm_style=llm_params.to_dict(),
        )
    """
    from .style_presets import get_style_preset
    from .materials import (
        get_building_material,
        get_tree_color,
        BUILDING_TYPE_MATERIALS,
        TREE_SPECIES_COLORS,
    )

    # Get style preset
    preset = get_style_preset(style_preset)

    # Build enhanced style dict for Blender
    style_dict = {
        "name": preset.name,
        "description": preset.description,
        # Base colors (fallback)
        "building_wall": [0.85, 0.82, 0.78],
        "building_roof": [0.45, 0.38, 0.32],
        "building_roughness": 0.8,
        "tree_foliage": [0.28, 0.48, 0.22],
        "tree_trunk": [0.35, 0.25, 0.18],
        "grass": [0.35, 0.50, 0.25],
        "street": [0.35, 0.35, 0.38],
        "sidewalk": [0.70, 0.68, 0.65],
        "water": [0.20, 0.35, 0.50],
        "terrain": [0.45, 0.42, 0.38],
        "terrain_roughness": 0.95,
        # Lighting
        "sun_strength": preset.sun_strength,
        "sun_color": [1.0, 0.98, 0.95],
        "ambient_strength": preset.ambient_strength,
        "sky_color": list(preset.sky_color),
        "default_samples": samples,
        # Data-driven flags
        "use_building_types": preset.use_building_types,
        "use_tree_species": preset.use_tree_species,
        "season": preset.season,
        # Style effects
        "snow_coverage": preset.snow_coverage,
        "rain_wetness": preset.rain_wetness,
        "fog_density": preset.fog_density,
        "saturation": preset.saturation,
        "contrast": preset.contrast,
        "temperature_shift": preset.temperature_shift,
        "brightness": preset.brightness,
        # Isometric view for 3D depth (shows building facades)
        "isometric": "isometric" in style_preset.lower(),
        "isometric_angle": preset.isometric_angle,  # Use preset's angle (default 12°)
    }

    # Add building type materials (including texture references)
    if preset.use_building_types:
        building_type_colors = {}
        for type_name, mat in BUILDING_TYPE_MATERIALS.items():
            building_type_colors[type_name] = {
                "wall": list(mat.wall),
                "roof": list(mat.roof),
                "roughness": mat.wall_roughness,
                "wall_texture": mat.wall_texture,
                "roof_texture": mat.roof_texture,
            }
        style_dict["building_type_colors"] = building_type_colors

    # Add texture settings from preset
    style_dict["use_textures"] = preset.use_textures
    style_dict["texture_scale"] = preset.texture_scale

    # Add roof material colors for LOD2 roof faces
    style_dict["roof_material_colors"] = {
        "roof_terracotta": [0.55, 0.35, 0.28],  # Traditional Swiss terracotta
        "roof_slate": [0.35, 0.35, 0.40],  # Dark slate
        "roof_flat": [0.50, 0.50, 0.52],  # Modern flat roof membrane
    }

    # Add tree species colors
    if preset.use_tree_species:
        style_dict["tree_species_colors"] = {
            genus: {season: list(colors) for season, colors in season_colors.items()}
            for genus, season_colors in TREE_SPECIES_COLORS.items()
        }

    # Add LLM style if provided
    if llm_style:
        style_dict["llm_style"] = llm_style
        # LLM can override sun position
        if llm_style.get("sun_azimuth") is not None:
            style_dict["_sun_azimuth"] = llm_style["sun_azimuth"]
        if llm_style.get("sun_altitude") is not None:
            style_dict["_sun_altitude"] = llm_style["sun_altitude"]

    # Determine sun position
    sun_azimuth = style_dict.get("_sun_azimuth", preset.sun_azimuth or 225)
    sun_altitude = style_dict.get("_sun_altitude", preset.sun_altitude or 35)

    # Create render config
    config = ColorRenderConfig(
        image_size=image_size,
        samples=samples,
        use_gpu=use_gpu,
    )

    # Create style object (for compatibility)
    class DictStyle:
        def __init__(self, d):
            self._dict = d
        def to_dict(self):
            return self._dict

    renderer = BlenderTileRenderer(config=config)
    sun = SunPosition(azimuth=sun_azimuth, altitude=sun_altitude)

    return renderer.render(buildings, trees, elevation, bounds, sun, DictStyle(style_dict))
