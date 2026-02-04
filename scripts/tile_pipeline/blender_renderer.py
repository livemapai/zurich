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
                tmpdir, buildings, trees, elevation, bounds, sun, style
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
    ) -> None:
        """Export all scene data to temporary directory."""
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
                }
            )

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
        """Load rendered image from file."""
        from PIL import Image

        if not path.exists():
            raise FileNotFoundError(f"Rendered image not found: {path}")

        img = Image.open(path).convert("RGB")

        # Resize to configured size if needed
        target_size = (self.config.image_size, self.config.image_size)
        if img.size != target_size:
            img = img.resize(target_size, Image.Resampling.LANCZOS)

        return np.array(img, dtype=np.uint8)

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
