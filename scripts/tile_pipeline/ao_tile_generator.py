"""
AO Tile Generator - Creates ambient occlusion tiles from Blender shadow buffers.

This generates tiles in the standard web map tile format (z/x/y) that can be:
1. Served from a static file server or CDN
2. Loaded as overlay tiles in deck.gl
3. Cached just like satellite imagery

The tile coordinate system matches your satellite tiles, so they align perfectly.

Usage:
    # Generate AO tiles for a specific area
    python ao_tile_generator.py --bounds 8.52,47.36,8.56,47.40 --zoom 16

    # Process existing shadow buffers into tile format
    python ao_tile_generator.py --input-dir blender_output/ --output-dir public/tiles/ao/
"""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

import numpy as np
from PIL import Image


@dataclass
class TileCoord:
    """Web map tile coordinates (z/x/y)."""

    z: int  # Zoom level
    x: int  # Column (0 = west)
    y: int  # Row (0 = north in TMS, south in XYZ)

    @property
    def bounds_wgs84(self) -> Tuple[float, float, float, float]:
        """Get tile bounds in WGS84 (west, south, east, north)."""
        n = 2**self.z
        west = self.x / n * 360 - 180
        east = (self.x + 1) / n * 360 - 180

        # Y coordinate: 0 is at top (north) in standard web tiles
        north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * self.y / n))))
        south = math.degrees(
            math.atan(math.sinh(math.pi * (1 - 2 * (self.y + 1) / n)))
        )

        return (west, south, east, north)

    @classmethod
    def from_wgs84(cls, lon: float, lat: float, zoom: int) -> "TileCoord":
        """Get tile containing a WGS84 point."""
        n = 2**zoom
        x = int((lon + 180) / 360 * n)
        y = int(
            (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
        )
        return cls(z=zoom, x=x, y=y)

    def __str__(self) -> str:
        return f"{self.z}/{self.x}/{self.y}"


def get_tiles_in_bounds(
    west: float,
    south: float,
    east: float,
    north: float,
    zoom: int,
) -> Iterator[TileCoord]:
    """Iterate over all tiles that intersect the given bounds."""
    # Get corner tiles
    nw = TileCoord.from_wgs84(west, north, zoom)
    se = TileCoord.from_wgs84(east, south, zoom)

    for x in range(nw.x, se.x + 1):
        for y in range(nw.y, se.y + 1):
            yield TileCoord(z=zoom, x=x, y=y)


@dataclass
class AOTileConfig:
    """Configuration for AO tile generation."""

    # Tile settings
    tile_size: int = 512  # Output tile size in pixels
    zoom: int = 16  # Zoom level to generate

    # Blender render settings
    blender_samples: int = 16  # Cycles samples (16 is fast, good for AO)
    shadow_darkness: float = 0.6  # How dark shadows appear

    # Output format
    output_format: str = "webp"  # webp, png, or jpg
    quality: int = 85  # For lossy formats

    # What to include in tiles
    include_ao: bool = True  # Ground ambient occlusion
    include_edges: bool = False  # Building edge overlay
    include_shadows: bool = False  # Time-specific shadows


class AOTileGenerator:
    """
    Generates ambient occlusion tiles from Blender shadow buffers.

    The workflow:
    1. For each tile coordinate, gather building/tree data
    2. Render shadow buffer with Blender
    3. Extract AO texture from shadow buffer
    4. Save as web tile (z/x/y.webp)

    Example:
        generator = AOTileGenerator(config)
        generator.generate_tiles(
            bounds=(8.52, 47.36, 8.56, 47.40),
            output_dir="public/tiles/ao"
        )
    """

    def __init__(self, config: Optional[AOTileConfig] = None):
        self.config = config or AOTileConfig()

    def generate_tiles(
        self,
        bounds: Tuple[float, float, float, float],
        output_dir: str,
        buildings_path: Optional[str] = None,
        trees_path: Optional[str] = None,
    ) -> List[str]:
        """
        Generate AO tiles for the given bounds.

        Args:
            bounds: (west, south, east, north) in WGS84
            output_dir: Base directory for tiles (will create z/x/y structure)
            buildings_path: Path to buildings GeoJSON
            trees_path: Path to trees GeoJSON

        Returns:
            List of generated tile paths
        """
        output_dir = Path(output_dir)
        generated = []

        # Get all tiles in bounds
        tiles = list(get_tiles_in_bounds(*bounds, self.config.zoom))
        print(f"Generating {len(tiles)} AO tiles at zoom {self.config.zoom}")

        for i, tile in enumerate(tiles):
            print(f"  [{i+1}/{len(tiles)}] Processing tile {tile}...")

            try:
                tile_path = self._generate_single_tile(
                    tile, output_dir, buildings_path, trees_path
                )
                generated.append(str(tile_path))
            except Exception as e:
                print(f"    Error: {e}")

        print(f"Generated {len(generated)} tiles")
        return generated

    def _generate_single_tile(
        self,
        tile: TileCoord,
        output_dir: Path,
        buildings_path: Optional[str],
        trees_path: Optional[str],
    ) -> Path:
        """Generate a single AO tile."""
        from .blender_shadows import BlenderConfig, BlenderShadowRenderer, SunPosition
        from .extract_intermediates import create_ao_texture
        from .sources.vector import VectorSource, query_features_in_tile

        # Create output path
        tile_dir = output_dir / str(tile.z) / str(tile.x)
        tile_dir.mkdir(parents=True, exist_ok=True)

        ext = self.config.output_format
        tile_path = tile_dir / f"{tile.y}.{ext}"

        # Skip if already exists
        if tile_path.exists():
            print(f"    Skipping (exists): {tile_path}")
            return tile_path

        # Get tile bounds
        bounds = tile.bounds_wgs84

        # Load data for this tile
        buildings = []
        trees = []

        if buildings_path:
            buildings_source = VectorSource(Path(buildings_path), "height")
            buildings = query_features_in_tile(
                buildings_source, bounds, buffer_meters=200, min_height=1.0
            )
            print(f"    Buildings: {len(buildings)}")

        if trees_path:
            trees_source = VectorSource(Path(trees_path), "estimated_height")
            trees = query_features_in_tile(
                trees_source, bounds, buffer_meters=100, min_height=2.0
            )
            print(f"    Trees: {len(trees)}")

        # Render shadow buffer with Blender
        config = BlenderConfig(
            image_size=self.config.tile_size,
            samples=self.config.blender_samples,
            shadow_darkness=self.config.shadow_darkness,
        )
        renderer = BlenderShadowRenderer(config=config)

        # Use overhead sun for AO (simulates ambient light from above)
        # Multiple sun positions could be averaged for better AO
        sun = SunPosition(azimuth=180, altitude=60)

        shadow_buffer = renderer.render(
            buildings=buildings,
            trees=trees,
            elevation=None,  # Could add DEM here
            bounds=bounds,
            sun=sun,
        )

        # Extract AO texture
        ao_texture = create_ao_texture(shadow_buffer)

        # Save tile
        self._save_tile(ao_texture, tile_path)

        return tile_path

    def _save_tile(self, ao_texture: np.ndarray, path: Path) -> None:
        """Save AO texture as tile image."""
        # Convert to uint8
        img_array = (ao_texture * 255).astype(np.uint8)
        img = Image.fromarray(img_array, mode="L")

        # Resize if needed
        if img.size != (self.config.tile_size, self.config.tile_size):
            img = img.resize(
                (self.config.tile_size, self.config.tile_size),
                Image.Resampling.LANCZOS,
            )

        # Save with appropriate format
        if self.config.output_format == "webp":
            img.save(path, "WEBP", quality=self.config.quality)
        elif self.config.output_format == "png":
            img.save(path, "PNG", optimize=True)
        elif self.config.output_format == "jpg":
            img.save(path, "JPEG", quality=self.config.quality)


def convert_shadow_buffer_to_tile(
    shadow_buffer_path: str,
    tile_coord: TileCoord,
    output_dir: str,
    output_format: str = "webp",
) -> str:
    """
    Convert an existing shadow buffer image to a properly-named tile.

    Use this when you've already rendered shadow buffers and want to
    organize them as tiles.

    Args:
        shadow_buffer_path: Path to shadow buffer PNG
        tile_coord: Tile coordinates (z/x/y)
        output_dir: Base tile directory
        output_format: Output format (webp, png, jpg)

    Returns:
        Path to generated tile
    """
    from .extract_intermediates import create_ao_texture, load_shadow_buffer

    # Load and process
    shadow = load_shadow_buffer(shadow_buffer_path)
    ao = create_ao_texture(shadow)

    # Create output path
    output_dir = Path(output_dir)
    tile_dir = output_dir / str(tile_coord.z) / str(tile_coord.x)
    tile_dir.mkdir(parents=True, exist_ok=True)

    tile_path = tile_dir / f"{tile_coord.y}.{output_format}"

    # Save
    img = Image.fromarray((ao * 255).astype(np.uint8), mode="L")
    img.save(tile_path)

    return str(tile_path)


# ============================================================================
# deck.gl Integration
# ============================================================================

DECKGL_TILE_LAYER_EXAMPLE = """
// deck.gl TileLayer for AO tiles
import { TileLayer, BitmapLayer } from 'deck.gl';

const aoTileLayer = new TileLayer({
  id: 'ao-tiles',
  data: '/tiles/ao/{z}/{x}/{y}.webp',
  minZoom: 14,
  maxZoom: 18,
  tileSize: 512,

  renderSubLayers: (props) => {
    const { boundingBox } = props.tile;

    return new BitmapLayer(props, {
      data: null,
      image: props.data,
      bounds: [
        boundingBox[0][0],  // west
        boundingBox[0][1],  // south
        boundingBox[1][0],  // east
        boundingBox[1][1],  // north
      ],
      // Multiply blend to darken the base layer
      parameters: {
        blend: true,
        blendFunc: [GL.DST_COLOR, GL.ZERO],
      },
    });
  },
});
"""

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate AO tiles")
    parser.add_argument(
        "--bounds",
        type=str,
        help="Bounds as west,south,east,north",
        default="8.53,47.37,8.55,47.39",
    )
    parser.add_argument("--zoom", type=int, default=16)
    parser.add_argument("--output-dir", type=str, default="public/tiles/ao")
    parser.add_argument("--buildings", type=str, help="Buildings GeoJSON path")
    parser.add_argument("--trees", type=str, help="Trees GeoJSON path")

    args = parser.parse_args()

    bounds = tuple(map(float, args.bounds.split(",")))

    config = AOTileConfig(zoom=args.zoom)
    generator = AOTileGenerator(config)

    generator.generate_tiles(
        bounds=bounds,
        output_dir=args.output_dir,
        buildings_path=args.buildings,
        trees_path=args.trees,
    )
