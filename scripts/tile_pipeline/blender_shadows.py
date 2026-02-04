"""
Blender shadow renderer for tile pipeline.

Renders shadow-only passes using Cycles with shadow catchers.
Can run headlessly without GUI.

This module provides GPU-accelerated ray-traced shadow rendering by:
1. Exporting tile data (buildings, trees, elevation) to temporary files
2. Running Blender headlessly with a Python script
3. Reading the rendered shadow buffer back

Usage:
    # From Python
    from blender_shadows import BlenderShadowRenderer
    renderer = BlenderShadowRenderer()
    shadow_buffer = renderer.render(buildings, trees, elevation, bounds, sun_pos)

    # From command line (using Blender executable)
    blender --background --python blender_scene.py -- \\
        --data-dir /tmp/tile_data --output shadow.png
"""

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

from .sources.vector import Feature


@dataclass
class SunPosition:
    """Sun position for shadow rendering.

    Azimuth: Direction sun is coming FROM (0=N, 90=E, 180=S, 270=W)
    Altitude: Angle above horizon (0=horizon, 90=zenith)
    """

    azimuth: float  # Degrees from north (0=N, 90=E, 180=S, 270=W)
    altitude: float  # Degrees above horizon (0=horizon, 90=zenith)
    angular_size: float = 0.533  # Sun's apparent size in degrees (for soft shadows)


@dataclass
class BlenderConfig:
    """Configuration for Blender shadow rendering."""

    # Output settings
    image_size: int = 512
    samples: int = 16  # Low for shadows (16 is usually enough)

    # Shadow appearance
    shadow_darkness: float = 0.7  # 0=invisible, 1=pitch black

    # GPU rendering
    use_gpu: bool = True
    device: str = "METAL"  # CUDA, OPTIX, METAL, or CPU

    # Performance
    tile_size: int = 256  # Render tile size (larger = faster on GPU)

    # Shadow quality
    soft_shadows: bool = True  # Use sun angular size for soft edges

    @classmethod
    def for_mac(cls) -> "BlenderConfig":
        """Preset for Mac with Metal GPU."""
        return cls(use_gpu=True, device="METAL", tile_size=512)

    @classmethod
    def for_nvidia(cls) -> "BlenderConfig":
        """Preset for NVIDIA GPU with OptiX."""
        return cls(use_gpu=True, device="OPTIX", tile_size=256)

    @classmethod
    def for_cpu(cls) -> "BlenderConfig":
        """Preset for CPU-only rendering."""
        return cls(use_gpu=False, device="CPU", samples=8, tile_size=64)


@dataclass
class SceneBounds:
    """Geographic bounds with equirectangular coordinate conversion.

    Uses equirectangular projection (local meters) because deck.gl linearly
    interpolates tile textures over WGS84 bounds. This ensures buildings
    in rendered tiles align with deck.gl's 3D geometry.

    Note: Web Mercator was tried but caused buildings to appear ~68% smaller
    because the 611m Mercator scene was stretched over 414m equivalent bounds.
    """

    west: float
    south: float
    east: float
    north: float

    lat_center: float = field(init=False)
    meters_per_deg_x: float = field(init=False)
    meters_per_deg_y: float = field(init=False)
    width_meters: float = field(init=False)
    height_meters: float = field(init=False)

    def __post_init__(self):
        import math

        self.lat_center = (self.south + self.north) / 2

        # Equirectangular: meters per degree at this latitude
        self.meters_per_deg_y = 111320.0
        self.meters_per_deg_x = 111320.0 * math.cos(math.radians(self.lat_center))

        # Scene dimensions in local meters
        self.width_meters = (self.east - self.west) * self.meters_per_deg_x
        self.height_meters = (self.north - self.south) * self.meters_per_deg_y

    def wgs84_to_local(self, lon: float, lat: float) -> Tuple[float, float]:
        """Convert WGS84 to local scene coordinates (meters from SW corner)."""
        x = (lon - self.west) * self.meters_per_deg_x
        y = (lat - self.south) * self.meters_per_deg_y
        return (x, y)


class BlenderShadowRenderer:
    """Renders shadow buffers using Blender's Cycles engine.

    This renderer calls Blender as a subprocess to leverage GPU-accelerated
    ray tracing for high-quality shadow generation. It:

    1. Exports scene data to temporary files
    2. Runs Blender headlessly with the blender_scene.py script
    3. Reads the rendered shadow image back as a numpy array

    Example:
        renderer = BlenderShadowRenderer()
        shadows = renderer.render(
            buildings=building_features,
            trees=tree_features,
            elevation=elevation_array,
            bounds=(8.53, 47.37, 8.55, 47.39),
            sun=SunPosition(azimuth=225, altitude=35),
        )
    """

    def __init__(
        self,
        blender_path: Optional[str] = None,
        config: Optional[BlenderConfig] = None,
    ):
        """Initialize Blender shadow renderer.

        Args:
            blender_path: Path to Blender executable. If None, searches PATH.
            config: Render configuration.
        """
        self.blender_path = blender_path or self._find_blender()
        self.config = config or BlenderConfig()

    def _find_blender(self) -> str:
        """Find Blender executable in system PATH."""
        # Check common locations
        locations = [
            "blender",  # In PATH
            "/Applications/Blender.app/Contents/MacOS/Blender",  # macOS
            "/usr/bin/blender",  # Linux
            "C:\\Program Files\\Blender Foundation\\Blender\\blender.exe",  # Windows
        ]

        for path in locations:
            if shutil.which(path):
                return path

            # Check if it's a direct path that exists
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
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> NDArray[np.float32]:
        """Render shadow buffer for tile.

        Args:
            buildings: Building features with footprints and heights
            trees: Tree features with positions and heights
            elevation: Elevation heightmap (H, W) in meters, or None for flat
            bounds: (west, south, east, north) in WGS84
            sun: Sun position for shadow direction
            progress_callback: Optional callback(stage, progress) for updates

        Returns:
            Shadow buffer (H, W) float32:
            - 1.0 = fully lit
            - config.shadow_darkness = fully in shadow
        """

        def report(stage: str, progress: float):
            if progress_callback:
                progress_callback(stage, progress)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Step 1: Export scene data
            report("export", 0.0)
            self._export_scene_data(
                tmpdir, buildings, trees, elevation, bounds, sun
            )
            report("export", 1.0)

            # Step 2: Run Blender
            report("render", 0.0)
            output_path = tmpdir / "shadow.png"
            self._run_blender(tmpdir, output_path)
            report("render", 0.9)

            # Step 3: Load result
            shadow_buffer = self._load_shadow_buffer(output_path)
            report("render", 1.0)

            return shadow_buffer

    def _export_scene_data(
        self,
        tmpdir: Path,
        buildings: List[Feature],
        trees: List[Feature],
        elevation: Optional[NDArray[np.float32]],
        bounds: Tuple[float, float, float, float],
        sun: SunPosition,
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

                # Convert outer ring to local coordinates
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

        # Save scene.json
        scene_data = {
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
            "config": {
                "image_size": self.config.image_size,
                "samples": self.config.samples,
                "shadow_darkness": self.config.shadow_darkness,
                "use_gpu": self.config.use_gpu,
                "device": self.config.device,
                "tile_size": self.config.tile_size,
                "soft_shadows": self.config.soft_shadows,
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
            # Create flat elevation
            flat = np.zeros(
                (self.config.image_size // 4, self.config.image_size // 4),
                dtype=np.float32,
            )
            np.save(tmpdir / "elevation.npy", flat)

    def _run_blender(self, data_dir: Path, output_path: Path) -> None:
        """Run Blender headlessly to render shadows."""
        script_path = Path(__file__).parent / "blender_scene.py"

        if not script_path.exists():
            raise FileNotFoundError(
                f"Blender scene script not found: {script_path}"
            )

        cmd = [
            self.blender_path,
            "--background",  # No GUI
            "--python",
            str(script_path),
            "--",  # Arguments after this go to the Python script
            "--data-dir",
            str(data_dir),
            "--output",
            str(output_path),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout
            raise RuntimeError(
                f"Blender render failed (exit code {result.returncode}):\n{error_msg}"
            )

    def _load_shadow_buffer(self, path: Path) -> NDArray[np.float32]:
        """Load rendered shadow buffer from image file."""
        from PIL import Image

        if not path.exists():
            raise FileNotFoundError(f"Shadow image not rendered: {path}")

        # Load as grayscale
        img = Image.open(path).convert("L")

        # Resize to configured size if needed
        if img.size != (self.config.image_size, self.config.image_size):
            img = img.resize(
                (self.config.image_size, self.config.image_size),
                Image.Resampling.BILINEAR,
            )

        # Convert to float32 array
        shadow_raw = np.array(img).astype(np.float32) / 255.0

        # Blender outputs: black=shadow, white=lit
        # We want: 1.0=lit, shadow_darkness=shadow
        shadow_buffer = 1.0 - shadow_raw * (1.0 - self.config.shadow_darkness)

        return shadow_buffer

    def check_blender(self) -> dict:
        """Check Blender installation and GPU capabilities.

        Returns:
            Dictionary with Blender info and capabilities
        """
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


def render_blender_shadows(
    buildings: List[Feature],
    trees: List[Feature],
    elevation: Optional[NDArray[np.float32]],
    bounds: Tuple[float, float, float, float],
    sun_azimuth: float,
    sun_altitude: float,
    image_size: int = 512,
    shadow_darkness: float = 0.7,
    use_gpu: bool = True,
) -> NDArray[np.float32]:
    """Convenience function to render shadows with Blender.

    Args:
        buildings: Building features
        trees: Tree features
        elevation: Elevation array (optional)
        bounds: (west, south, east, north) in WGS84
        sun_azimuth: Sun azimuth in degrees
        sun_altitude: Sun altitude in degrees
        image_size: Output resolution
        shadow_darkness: Shadow darkness (0=invisible, 1=black)
        use_gpu: Use GPU rendering if available

    Returns:
        Shadow buffer (size, size) ready for compositing

    Example:
        shadows = render_blender_shadows(
            buildings, trees, elevation,
            bounds=(8.53, 47.37, 8.55, 47.39),
            sun_azimuth=225,
            sun_altitude=35,
        )
    """
    config = BlenderConfig(
        image_size=image_size,
        shadow_darkness=shadow_darkness,
        use_gpu=use_gpu,
    )

    renderer = BlenderShadowRenderer(config=config)
    sun = SunPosition(azimuth=sun_azimuth, altitude=sun_altitude)

    return renderer.render(buildings, trees, elevation, bounds, sun)
