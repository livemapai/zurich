"""
Tile rendering and I/O management.

Handles tile coordinate calculations, iteration over tile grids,
output file writing, and parallel processing coordination.
"""

import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Callable

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from tqdm import tqdm

from .config import PipelineConfig
from .sources.satellite import SatelliteSource, tile_bounds_wgs84, wgs84_to_tile
from .sources.elevation import ElevationSource
from .sources.vector import VectorSource, query_features_in_tile
from .tile_compositor import composite_tile, composite_tile_v2
from .time_presets import get_preset


@dataclass
class TileCoord:
    """Web Mercator tile coordinates."""

    z: int
    x: int
    y: int

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """Get WGS84 bounds (west, south, east, north)."""
        return tile_bounds_wgs84(self.z, self.x, self.y)

    def __str__(self) -> str:
        return f"{self.z}/{self.x}/{self.y}"


class TileRenderer:
    """Manages tile rendering for a region."""

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        preset_name: str = "afternoon",
        use_blender: bool = False,
        blender_samples: int = 16,
    ):
        """Initialize renderer.

        Args:
            config: Pipeline configuration
            preset_name: Time preset for lighting
            use_blender: Use Blender Cycles for GPU ray-traced shadows
            blender_samples: Render samples when using Blender (16-64 typical)
        """
        self.config = config or PipelineConfig()
        self.preset_name = preset_name
        self.preset = get_preset(preset_name)
        self.use_blender = use_blender
        self.blender_samples = blender_samples

        # Initialize data sources
        self.satellite = SatelliteSource(
            url_template=self.config.sources.swissimage_url,
            cache_dir=self.config.cache_dir,
        )
        self.elevation = ElevationSource(
            url_template=self.config.sources.elevation_url,
            cache_dir=self.config.cache_dir,
        )

        # Vector sources loaded lazily
        self._buildings: Optional[VectorSource] = None
        self._trees: Optional[VectorSource] = None

    @property
    def buildings(self) -> Optional[VectorSource]:
        """Lazy-load buildings."""
        if self._buildings is None:
            buildings_path = self.config.sources.buildings_path
            if buildings_path.exists():
                self._buildings = VectorSource(buildings_path, "height")
        return self._buildings

    @property
    def trees(self) -> Optional[VectorSource]:
        """Lazy-load trees."""
        if self._trees is None:
            trees_path = self.config.sources.trees_path
            if trees_path.exists():
                self._trees = VectorSource(trees_path, "estimated_height")
        return self._trees

    def tiles_in_bounds(
        self,
        bounds: tuple[float, float, float, float],
        zoom: int,
    ) -> Iterator[TileCoord]:
        """Iterate over all tiles within bounds at a zoom level.

        Args:
            bounds: (west, south, east, north) in WGS84
            zoom: Zoom level

        Yields:
            TileCoord for each tile
        """
        west, south, east, north = bounds

        # Get corner tiles
        x_min, y_max = wgs84_to_tile(west, south, zoom)
        x_max, y_min = wgs84_to_tile(east, north, zoom)

        # Iterate grid
        for y in range(y_min, y_max + 1):
            for x in range(x_min, x_max + 1):
                yield TileCoord(zoom, x, y)

    def count_tiles(
        self,
        bounds: tuple[float, float, float, float],
        min_zoom: int,
        max_zoom: int,
    ) -> int:
        """Count total tiles to render."""
        total = 0
        for z in range(min_zoom, max_zoom + 1):
            for _ in self.tiles_in_bounds(bounds, z):
                total += 1
        return total

    def render_tile(self, coord: TileCoord) -> NDArray[np.uint8]:
        """Render a single tile.

        Args:
            coord: Tile coordinates

        Returns:
            Composited RGB image
        """
        size = self.config.output.tile_size

        # Fetch base layers
        satellite = self.satellite.fetch_and_resize(coord.z, coord.x, coord.y, size)
        elevation = self.elevation.fetch_and_resize(coord.z, coord.x, coord.y, size)

        # Query vector features
        bounds = coord.bounds
        building_features = []
        tree_features = []

        if self.buildings:
            building_features = query_features_in_tile(
                self.buildings,
                bounds,
                buffer_meters=200,  # Long shadows can extend far
                min_height=1.0,
            )

        if self.trees:
            tree_features = query_features_in_tile(
                self.trees,
                bounds,
                buffer_meters=100,
                min_height=2.0,
            )

        # Branch: V2 pipeline (Blender) or V1 pipeline (trimesh)
        if self.use_blender:
            return composite_tile_v2(
                satellite,
                elevation,
                building_features,
                tree_features,
                bounds,
                self.config,
                self.preset_name,
                remove_shadows=True,
                use_blender=True,
                blender_samples=self.blender_samples,
            )
        else:
            return composite_tile(
                satellite,
                elevation,
                building_features,
                tree_features,
                bounds,
                self.config,
                self.preset_name,
            )

    def save_tile(
        self,
        image: NDArray[np.uint8],
        coord: TileCoord,
        output_dir: Optional[Path] = None,
    ) -> Path:
        """Save a rendered tile to disk.

        Args:
            image: RGB image array
            coord: Tile coordinates
            output_dir: Output directory (uses config default if None)

        Returns:
            Path to saved file
        """
        output_dir = output_dir or self.config.output.output_dir
        fmt = self.config.output.format

        # Create directory structure
        tile_path = output_dir / str(coord.z) / str(coord.x) / f"{coord.y}.{fmt}"
        tile_path.parent.mkdir(parents=True, exist_ok=True)

        # Save image
        img = Image.fromarray(image)

        if fmt == "webp":
            img.save(tile_path, "WEBP", quality=self.config.output.quality)
        elif fmt == "jpeg":
            img.save(tile_path, "JPEG", quality=self.config.output.quality)
        else:
            img.save(tile_path, "PNG")

        return tile_path

    def render_and_save(
        self,
        coord: TileCoord,
        output_dir: Optional[Path] = None,
    ) -> Path:
        """Render and save a single tile.

        Args:
            coord: Tile coordinates
            output_dir: Output directory

        Returns:
            Path to saved tile
        """
        image = self.render_tile(coord)
        return self.save_tile(image, coord, output_dir)

    def render_all(
        self,
        bounds: Optional[tuple[float, float, float, float]] = None,
        min_zoom: Optional[int] = None,
        max_zoom: Optional[int] = None,
        progress: bool = True,
        on_tile_complete: Optional[Callable[[TileCoord, Path], None]] = None,
    ) -> list[Path]:
        """Render all tiles in region.

        Args:
            bounds: Region bounds (uses config default if None)
            min_zoom: Minimum zoom level (uses config default if None)
            max_zoom: Maximum zoom level (uses config default if None)
            progress: Show progress bar
            on_tile_complete: Callback after each tile

        Returns:
            List of paths to rendered tiles
        """
        bounds = bounds or self.config.bounds
        min_zoom = min_zoom if min_zoom is not None else self.config.min_zoom
        max_zoom = max_zoom if max_zoom is not None else self.config.max_zoom

        # Collect all tiles
        tiles = []
        for z in range(min_zoom, max_zoom + 1):
            for coord in self.tiles_in_bounds(bounds, z):
                tiles.append(coord)

        # Render with progress
        paths = []
        iterator = tqdm(tiles, desc="Rendering tiles", disable=not progress)

        for coord in iterator:
            try:
                path = self.render_and_save(coord)
                paths.append(path)
                if on_tile_complete:
                    on_tile_complete(coord, path)
            except Exception as e:
                print(f"Error rendering {coord}: {e}")

        return paths

    def render_parallel(
        self,
        bounds: Optional[tuple[float, float, float, float]] = None,
        min_zoom: Optional[int] = None,
        max_zoom: Optional[int] = None,
        workers: Optional[int] = None,
        progress: bool = True,
    ) -> list[Path]:
        """Render all tiles using parallel workers.

        Args:
            bounds: Region bounds
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            workers: Number of parallel workers (uses config default if None)
            progress: Show progress bar

        Returns:
            List of paths to rendered tiles
        """
        bounds = bounds or self.config.bounds
        min_zoom = min_zoom if min_zoom is not None else self.config.min_zoom
        max_zoom = max_zoom if max_zoom is not None else self.config.max_zoom
        workers = workers or self.config.workers

        # Collect all tiles
        tiles = []
        for z in range(min_zoom, max_zoom + 1):
            for coord in self.tiles_in_bounds(bounds, z):
                tiles.append(coord)

        paths = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self.render_and_save, coord): coord
                for coord in tiles
            }

            iterator = tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Rendering tiles",
                disable=not progress,
            )

            for future in iterator:
                try:
                    path = future.result()
                    paths.append(path)
                except Exception as e:
                    coord = futures[future]
                    print(f"Error rendering {coord}: {e}")

        return paths


class RenderedTileRenderer(TileRenderer):
    """Renders tiles using pure Blender 3D rendering (no satellite imagery).

    This renderer bypasses satellite imagery entirely and renders complete
    tiles from 3D vector data (buildings, trees, terrain) using Blender
    Cycles with colored materials.

    Advantages over satellite mode:
    - No double-shadow problem (shadows are rendered directly)
    - Consistent visual style across all tiles
    - Works without internet connection (after initial data download)
    - Customizable colors and lighting
    """

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        preset_name: str = "afternoon",
        style_name: str = "default",
        samples: int = 64,
    ):
        """Initialize rendered tile renderer.

        Args:
            config: Pipeline configuration
            preset_name: Time preset for lighting/sun position
            style_name: Visual style name (see materials.py)
            samples: Blender Cycles render samples
        """
        # Initialize base class (but we won't use satellite/blender shadow features)
        super().__init__(config, preset_name, use_blender=False, blender_samples=samples)

        self.style_name = style_name
        self.samples = samples

        # Lazy-loaded Blender renderer
        self._blender_renderer = None

    @property
    def blender_renderer(self):
        """Lazy-load Blender tile renderer."""
        if self._blender_renderer is None:
            from .blender_renderer import BlenderTileRenderer, ColorRenderConfig

            render_config = ColorRenderConfig(
                image_size=self.config.output.tile_size,
                samples=self.samples,
                use_gpu=True,
            )
            self._blender_renderer = BlenderTileRenderer(config=render_config)
        return self._blender_renderer

    def render_tile(self, coord: TileCoord) -> NDArray[np.uint8]:
        """Render a single tile using Blender.

        Args:
            coord: Tile coordinates

        Returns:
            Rendered RGB image
        """
        from .blender_shadows import SunPosition
        from .materials import get_style

        bounds = coord.bounds

        # Query vector features
        building_features = []
        tree_features = []

        if self.buildings:
            building_features = query_features_in_tile(
                self.buildings,
                bounds,
                buffer_meters=200,
                min_height=1.0,
            )

        if self.trees:
            tree_features = query_features_in_tile(
                self.trees,
                bounds,
                buffer_meters=100,
                min_height=2.0,
            )

        # Fetch elevation for terrain
        size = self.config.output.tile_size
        elevation = self.elevation.fetch_and_resize(coord.z, coord.x, coord.y, size)

        # Get sun position from preset
        sun = SunPosition(
            azimuth=self.preset.azimuth,
            altitude=self.preset.altitude,
        )

        # Get style
        style = get_style(self.style_name)

        # Render with Blender
        return self.blender_renderer.render(
            buildings=building_features,
            trees=tree_features,
            elevation=elevation,
            bounds=bounds,
            sun=sun,
            style=style,
        )


def preview_tile(
    lat: float,
    lng: float,
    zoom: int = 16,
    preset_name: str = "afternoon",
    config: Optional[PipelineConfig] = None,
    use_blender: bool = False,
    blender_samples: int = 16,
) -> NDArray[np.uint8]:
    """Quick preview of a single tile at a location.

    Args:
        lat: Latitude
        lng: Longitude
        zoom: Zoom level
        preset_name: Time preset name
        config: Pipeline configuration
        use_blender: Use Blender Cycles for GPU ray-traced shadows
        blender_samples: Render samples when using Blender

    Returns:
        Rendered RGB image
    """
    x, y = wgs84_to_tile(lng, lat, zoom)
    coord = TileCoord(zoom, x, y)

    renderer = TileRenderer(
        config,
        preset_name,
        use_blender=use_blender,
        blender_samples=blender_samples,
    )
    return renderer.render_tile(coord)


def preview_tile_rendered(
    lat: float,
    lng: float,
    zoom: int = 16,
    preset_name: str = "afternoon",
    style_name: str = "default",
    config: Optional[PipelineConfig] = None,
    samples: int = 64,
) -> NDArray[np.uint8]:
    """Preview a single tile using rendered mode (pure Blender 3D).

    Args:
        lat: Latitude
        lng: Longitude
        zoom: Zoom level
        preset_name: Time preset name for sun position
        style_name: Visual style name
        config: Pipeline configuration
        samples: Blender render samples

    Returns:
        Rendered RGB image
    """
    x, y = wgs84_to_tile(lng, lat, zoom)
    coord = TileCoord(zoom, x, y)

    renderer = RenderedTileRenderer(
        config=config,
        preset_name=preset_name,
        style_name=style_name,
        samples=samples,
    )
    return renderer.render_tile(coord)


def estimate_render_time(
    tile_count: int,
    seconds_per_tile: float = 2.0,
    workers: int = 4,
) -> str:
    """Estimate total render time.

    Args:
        tile_count: Number of tiles
        seconds_per_tile: Average time per tile
        workers: Number of parallel workers

    Returns:
        Human-readable time estimate
    """
    total_seconds = (tile_count * seconds_per_tile) / workers

    if total_seconds < 60:
        return f"{total_seconds:.0f} seconds"
    elif total_seconds < 3600:
        return f"{total_seconds / 60:.1f} minutes"
    else:
        return f"{total_seconds / 3600:.1f} hours"
