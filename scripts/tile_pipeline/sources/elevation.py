"""
Terrain elevation data loader with Terrarium decoding.

Fetches elevation tiles from Mapterhorn (or compatible services) that use
the Terrarium encoding format. Terrarium encodes elevation in RGB values:

    elevation = (R × 256 + G + B / 256) - 32768

This gives a range of -32768m to +32767m with ~0.1m precision.
"""

import io
from pathlib import Path
from typing import Optional

import numpy as np
from numpy.typing import NDArray
import requests
from PIL import Image

from ..config import PipelineConfig


# Default Mapterhorn terrain tiles URL
DEFAULT_ELEVATION_URL = "https://tiles.mapterhorn.com/{z}/{x}/{y}.webp"


def decode_terrarium(rgb: NDArray[np.uint8]) -> NDArray[np.float32]:
    """Decode Terrarium-encoded RGB to elevation in meters.

    Terrarium encoding stores elevation as:
        elevation = (R × 256 + G + B / 256) - 32768

    Args:
        rgb: RGB image of shape (H, W, 3) with uint8 values

    Returns:
        Elevation array of shape (H, W) with float32 values in meters
    """
    r = rgb[..., 0].astype(np.float32)
    g = rgb[..., 1].astype(np.float32)
    b = rgb[..., 2].astype(np.float32)

    elevation = (r * 256.0 + g + b / 256.0) - 32768.0
    return elevation


def encode_terrarium(elevation: NDArray[np.float32]) -> NDArray[np.uint8]:
    """Encode elevation to Terrarium RGB format.

    Useful for debugging and visualization.

    Args:
        elevation: Elevation array in meters

    Returns:
        RGB image of shape (H, W, 3)
    """
    # Add offset and clamp
    value = np.clip(elevation + 32768.0, 0, 65535)

    r = (value // 256).astype(np.uint8)
    g = (value % 256).astype(np.uint8)
    b = ((value % 1) * 256).astype(np.uint8)

    return np.stack([r, g, b], axis=-1)


class ElevationSource:
    """Manages fetching and caching of terrain elevation tiles."""

    def __init__(
        self,
        url_template: str = DEFAULT_ELEVATION_URL,
        cache_dir: Optional[Path] = None,
        timeout: int = 30,
    ):
        """Initialize elevation source.

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
            "User-Agent": "ZurichTilePipeline/1.0"
        })

        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, z: int, x: int, y: int) -> Optional[Path]:
        """Get cache file path for a tile."""
        if not self.cache_dir:
            return None
        return self.cache_dir / "elevation" / f"{z}" / f"{x}" / f"{y}.webp"

    def _load_from_cache(self, z: int, x: int, y: int) -> Optional[NDArray[np.uint8]]:
        """Load raw tile from cache if available."""
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

    def fetch_raw(self, z: int, x: int, y: int) -> NDArray[np.uint8]:
        """Fetch raw RGB tile (Terrarium-encoded).

        Args:
            z: Zoom level
            x: Tile X coordinate
            y: Tile Y coordinate

        Returns:
            RGB image as numpy array (Mapterhorn uses 512×512 tiles)
        """
        # Try cache first
        cached = self._load_from_cache(z, x, y)
        if cached is not None:
            return cached

        # Fetch from server
        url = self.url_template.format(z=z, x=x, y=y)
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()

        # Cache the raw response
        self._save_to_cache(z, x, y, response.content)

        # Parse and return as numpy array
        with Image.open(io.BytesIO(response.content)) as img:
            return np.array(img.convert("RGB"))

    def fetch(self, z: int, x: int, y: int) -> NDArray[np.float32]:
        """Fetch and decode elevation tile.

        Args:
            z: Zoom level
            x: Tile X coordinate
            y: Tile Y coordinate

        Returns:
            Elevation array in meters (Mapterhorn uses 512×512 tiles)
        """
        rgb = self.fetch_raw(z, x, y)
        return decode_terrarium(rgb)

    def fetch_and_resize(
        self,
        z: int,
        x: int,
        y: int,
        target_size: int = 512
    ) -> NDArray[np.float32]:
        """Fetch elevation tile and resize to target size.

        Note: Mapterhorn tiles are already 512×512 (unlike standard 256×256),
        so we fetch a single tile and resize if needed.

        Args:
            z: Zoom level at OUTPUT resolution
            x: Tile X coordinate
            y: Tile Y coordinate
            target_size: Output size in pixels

        Returns:
            Elevation array of shape (target_size, target_size)
        """
        # Fetch single tile (Mapterhorn tiles are 512×512)
        elevation = self.fetch(z, x, y)

        # Resize if needed
        if elevation.shape[0] != target_size:
            from PIL import Image
            img = Image.fromarray(elevation)
            img = img.resize((target_size, target_size), Image.Resampling.BILINEAR)
            elevation = np.array(img, dtype=np.float32)

        return elevation


def fetch_elevation_tile(
    z: int,
    x: int,
    y: int,
    config: Optional[PipelineConfig] = None,
    target_size: int = 512,
) -> NDArray[np.float32]:
    """Convenience function to fetch an elevation tile.

    Args:
        z: Zoom level
        x: Tile X coordinate
        y: Tile Y coordinate
        config: Pipeline configuration (uses defaults if None)
        target_size: Output size in pixels

    Returns:
        Elevation array in meters
    """
    if config is None:
        config = PipelineConfig()

    source = ElevationSource(
        url_template=config.sources.elevation_url,
        cache_dir=config.cache_dir,
    )

    return source.fetch_and_resize(z, x, y, target_size)


def compute_slope_aspect(
    elevation: NDArray[np.float32],
    cell_size: float
) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    """Compute slope and aspect from elevation grid.

    Uses a 3×3 moving window (Horn's method).

    Args:
        elevation: Elevation array in meters
        cell_size: Size of each cell in meters

    Returns:
        Tuple of (slope, aspect) arrays in radians
        - slope: 0 = flat, π/2 = vertical
        - aspect: 0 = north, π/2 = east, π = south, 3π/2 = west
    """
    # Pad elevation for edge handling
    padded = np.pad(elevation, 1, mode="edge")

    # Extract neighbors using Horn's method weights
    z1 = padded[:-2, :-2]   # top-left
    z2 = padded[:-2, 1:-1]  # top-center
    z3 = padded[:-2, 2:]    # top-right
    z4 = padded[1:-1, :-2]  # mid-left
    z6 = padded[1:-1, 2:]   # mid-right
    z7 = padded[2:, :-2]    # bottom-left
    z8 = padded[2:, 1:-1]   # bottom-center
    z9 = padded[2:, 2:]     # bottom-right

    # Compute partial derivatives
    dz_dx = ((z3 + 2 * z6 + z9) - (z1 + 2 * z4 + z7)) / (8 * cell_size)
    dz_dy = ((z7 + 2 * z8 + z9) - (z1 + 2 * z2 + z3)) / (8 * cell_size)

    # Slope (radians)
    slope = np.arctan(np.sqrt(dz_dx ** 2 + dz_dy ** 2))

    # Aspect (radians, 0 = north, clockwise)
    aspect = np.arctan2(-dz_dx, dz_dy)
    aspect = np.where(aspect < 0, aspect + 2 * np.pi, aspect)

    return slope, aspect


def meters_per_pixel(lat: float, z: int) -> float:
    """Calculate ground resolution at a given latitude and zoom.

    Args:
        lat: Latitude in degrees
        z: Zoom level

    Returns:
        Meters per pixel
    """
    # Earth circumference at equator
    C = 40075016.686
    return C * np.cos(np.radians(lat)) / (256 * 2 ** z)
