"""
Pipeline configuration dataclass for photorealistic tile rendering.

Centralizes all tunable parameters for the compositing pipeline,
including blend opacities, source URLs, and output settings.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class BlendConfig:
    """Opacity and mode settings for each compositing layer."""

    hillshade_opacity: float = 0.6
    hillshade_mode: Literal["soft_light", "overlay", "multiply"] = "soft_light"

    building_shadow_opacity: float = 0.8
    building_shadow_mode: Literal["multiply", "soft_light"] = "multiply"

    tree_shadow_opacity: float = 0.6
    tree_shadow_mode: Literal["multiply", "soft_light"] = "multiply"

    ambient_occlusion_opacity: float = 0.4
    ambient_occlusion_mode: Literal["multiply", "soft_light"] = "multiply"


@dataclass
class SourceConfig:
    """URLs and paths for data sources."""

    # SWISSIMAGE 10cm satellite imagery (WMTS)
    swissimage_url: str = (
        "https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissimage/default/current/"
        "3857/{z}/{x}/{y}.jpeg"
    )

    # Mapterhorn terrain tiles (Terrarium encoding)
    elevation_url: str = "https://tiles.mapterhorn.com/{z}/{x}/{y}.webp"

    # Local GeoJSON files
    buildings_path: Path = field(
        default_factory=lambda: Path("public/data/zurich-buildings.geojson")
    )
    trees_path: Path = field(
        default_factory=lambda: Path("public/data/zurich-trees.geojson")
    )
    streets_path: Path = field(
        default_factory=lambda: Path("data/raw/streets-wfs.geojson")
    )
    water_path: Path = field(
        default_factory=lambda: Path("data/raw/water-bodies.geojson")
    )


@dataclass
class OutputConfig:
    """Output tile settings."""

    tile_size: int = 512
    format: Literal["webp", "png", "jpeg"] = "webp"
    quality: int = 90  # For lossy formats
    output_dir: Path = field(
        default_factory=lambda: Path("public/tiles/photorealistic")
    )


@dataclass
class SunConfig:
    """Sun position for shadow casting (can be overridden by time presets)."""

    azimuth: float = 240.0  # Degrees from north (SW afternoon default)
    altitude: float = 35.0  # Degrees above horizon


@dataclass
class ImhofConfig:
    """Imhof-style color shift parameters for hillshade tinting."""

    # Warm tint for sunlit slopes (yellow-orange)
    warm_hue: tuple[int, int, int] = (255, 245, 220)
    warm_strength: float = 0.3

    # Cool tint for shaded slopes (blue)
    cool_hue: tuple[int, int, int] = (200, 210, 230)
    cool_strength: float = 0.4


@dataclass
class PipelineConfig:
    """Master configuration for the tile rendering pipeline."""

    blend: BlendConfig = field(default_factory=BlendConfig)
    sources: SourceConfig = field(default_factory=SourceConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    sun: SunConfig = field(default_factory=SunConfig)
    imhof: ImhofConfig = field(default_factory=ImhofConfig)

    # Zurich bounds in WGS84
    bounds: tuple[float, float, float, float] = (8.44, 47.32, 8.63, 47.44)

    # Zoom range
    min_zoom: int = 14
    max_zoom: int = 18

    # Processing
    workers: int = 4
    cache_dir: Path = field(default_factory=lambda: Path(".cache/tiles"))

    def __post_init__(self) -> None:
        """Ensure directories exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.output.output_dir.mkdir(parents=True, exist_ok=True)
