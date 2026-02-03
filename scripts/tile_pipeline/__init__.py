"""
Photorealistic Tile Rendering Pipeline

Combines multiple Swiss geodata sources to produce high-quality map tiles:
- SWISSIMAGE 10cm satellite imagery
- swissALTI3D 0.5m terrain elevation
- Stadt Zürich building footprints with heights
- Baumkataster tree positions
- Calculated hillshades, shadows, and ambient occlusion

Based on Eduard Imhof's Swiss cartographic traditions with modern
compositing techniques in LAB color space.
"""

from .config import PipelineConfig
from .tile_renderer import TileRenderer

__all__ = ["PipelineConfig", "TileRenderer"]
__version__ = "0.1.0"
