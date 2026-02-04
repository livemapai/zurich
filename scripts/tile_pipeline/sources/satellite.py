"""
SWISSIMAGE 10cm satellite imagery fetcher.

Fetches tiles from the Swiss Federal Office of Topography (swisstopo) WMTS
service. SWISSIMAGE provides orthorectified aerial imagery of Switzerland
at 10cm ground resolution.

The WMTS service uses Web Mercator (EPSG:3857) tile coordinates.
"""

import hashlib
import io
from pathlib import Path
from typing import Optional

import numpy as np
from numpy.typing import NDArray
import requests
from PIL import Image

from ..config import PipelineConfig


# Default SWISSIMAGE WMTS URL pattern
DEFAULT_SWISSIMAGE_URL = (
    "https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissimage/default/current/"
    "3857/{z}/{x}/{y}.jpeg"
)


class SatelliteSource:
    """Manages fetching and caching of SWISSIMAGE satellite tiles."""

    def __init__(
        self,
        url_template: str = DEFAULT_SWISSIMAGE_URL,
        cache_dir: Optional[Path] = None,
        timeout: int = 30,
    ):
        """Initialize satellite source.

        Args:
            url_template: URL pattern with {z}, {x}, {y} placeholders
            cache_dir: Directory for tile cache (None = no caching)
            timeout: Request timeout in seconds
        """
        self.url_template = url_template
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ZurichTilePipeline/1.0 (https://github.com/example)"
        })

        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, z: int, x: int, y: int) -> Optional[Path]:
        """Get cache file path for a tile."""
        if not self.cache_dir:
            return None
        return self.cache_dir / "satellite" / f"{z}" / f"{x}" / f"{y}.jpeg"

    def _load_from_cache(self, z: int, x: int, y: int) -> Optional[NDArray[np.uint8]]:
        """Load tile from cache if available."""
        cache_path = self._cache_path(z, x, y)
        if cache_path and cache_path.exists():
            with Image.open(cache_path) as img:
                return np.array(img.convert("RGB"))
        return None

    def _save_to_cache(self, z: int, x: int, y: int, data: bytes) -> None:
        """Save tile data to cache."""
        cache_path = self._cache_path(z, x, y)
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(data)

    def fetch(self, z: int, x: int, y: int) -> NDArray[np.uint8]:
        """Fetch a satellite tile.

        Args:
            z: Zoom level
            x: Tile X coordinate (Web Mercator)
            y: Tile Y coordinate (Web Mercator)

        Returns:
            RGB image as numpy array of shape (256, 256, 3)

        Raises:
            requests.HTTPError: If fetch fails
        """
        # Try cache first
        cached = self._load_from_cache(z, x, y)
        if cached is not None:
            return cached

        # Fetch from WMTS
        url = self.url_template.format(z=z, x=x, y=y)
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()

        # Cache the raw response
        self._save_to_cache(z, x, y, response.content)

        # Parse and return as numpy array
        with Image.open(io.BytesIO(response.content)) as img:
            return np.array(img.convert("RGB"))

    def fetch_and_resize(
        self,
        z: int,
        x: int,
        y: int,
        target_size: int = 512
    ) -> NDArray[np.uint8]:
        """Fetch a tile and resize to target size.

        SWISSIMAGE tiles are 256×256, but our output tiles are 512×512.
        This fetches a 2×2 grid of source tiles and combines them.

        Args:
            z: Zoom level
            x: Tile X coordinate at the OUTPUT zoom level
            y: Tile Y coordinate at the OUTPUT zoom level
            target_size: Output size in pixels

        Returns:
            RGB image as numpy array of shape (target_size, target_size, 3)
        """
        # For 512px output at zoom Z, we need 4 tiles at zoom Z+1
        # Calculate the source tile coordinates
        src_z = z + 1
        src_x_base = x * 2
        src_y_base = y * 2

        # Fetch 2×2 grid
        tiles = []
        for dy in range(2):
            row = []
            for dx in range(2):
                tile = self.fetch(src_z, src_x_base + dx, src_y_base + dy)
                row.append(tile)
            tiles.append(np.concatenate(row, axis=1))

        combined = np.concatenate(tiles, axis=0)

        # Combined is now 512×512 (2×256 each direction)
        return combined


def fetch_satellite_tile(
    z: int,
    x: int,
    y: int,
    config: Optional[PipelineConfig] = None,
    target_size: int = 512,
) -> NDArray[np.uint8]:
    """Convenience function to fetch a satellite tile.

    Args:
        z: Zoom level
        x: Tile X coordinate
        y: Tile Y coordinate
        config: Pipeline configuration (uses defaults if None)
        target_size: Output size in pixels

    Returns:
        RGB image as numpy array
    """
    if config is None:
        config = PipelineConfig()

    source = SatelliteSource(
        url_template=config.sources.swissimage_url,
        cache_dir=config.cache_dir,
    )

    return source.fetch_and_resize(z, x, y, target_size)


def tile_bounds_wgs84(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """Get WGS84 bounds for a Web Mercator tile.

    Args:
        z: Zoom level
        x: Tile X coordinate
        y: Tile Y coordinate

    Returns:
        Tuple of (west, south, east, north) in WGS84 degrees
    """
    n = 2 ** z

    def tile_to_lon(x: int) -> float:
        return x / n * 360.0 - 180.0

    def tile_to_lat(y: int) -> float:
        lat_rad = np.arctan(np.sinh(np.pi * (1 - 2 * y / n)))
        return np.degrees(lat_rad)

    west = tile_to_lon(x)
    east = tile_to_lon(x + 1)
    north = tile_to_lat(y)
    south = tile_to_lat(y + 1)

    return (west, south, east, north)


def wgs84_to_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    """Convert WGS84 coordinates to tile coordinates.

    Args:
        lon: Longitude in degrees
        lat: Latitude in degrees
        z: Zoom level

    Returns:
        Tuple of (x, y) tile coordinates
    """
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = np.radians(lat)
    y = int((1.0 - np.arcsinh(np.tan(lat_rad)) / np.pi) / 2.0 * n)
    return (x, y)
