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

V2 Pipeline adds:
- AI-powered shadow removal (LaMa inpainting)
- Ray-traced shadows from 3D scene (trimesh)
- Time-of-day color grading

Usage:
    # Preview single tile
    python -m scripts.tile_pipeline.cli preview --lat 47.376 --lng 8.54 --zoom 16

    # Render region
    python -m scripts.tile_pipeline.cli render --bounds "8.52,47.37,8.56,47.39"

    # List presets
    python -m scripts.tile_pipeline.cli presets

    # Test ray tracing pipeline
    python -m scripts.tile_pipeline.test_raytracing
"""

from .config import PipelineConfig
from .tile_renderer import TileRenderer, preview_tile
from .tile_compositor import (
    TileCompositor,
    composite_tile,
    # V2 exports
    TileCompositorV2,
    composite_tile_v2,
    preview_v2_pipeline,
)
from .time_presets import TimePreset, get_preset, list_presets, PRESETS
from .areas import Area, AREAS, get_area, get_area_bounds, list_areas, estimate_tiles

# V2 Pipeline components
from .shadow_remover import ShadowRemover, remove_shadows, RemovalMethod
from .scene_builder import SceneBuilder, build_tile_scene
from .raytracer import TileRaytracer, SunPosition, render_tile_shadows

__all__ = [
    # Original API
    "PipelineConfig",
    "TileRenderer",
    "TileCompositor",
    "TimePreset",
    "preview_tile",
    "composite_tile",
    "get_preset",
    "list_presets",
    "PRESETS",
    # Areas
    "Area",
    "AREAS",
    "get_area",
    "get_area_bounds",
    "list_areas",
    "estimate_tiles",
    # V2 API
    "TileCompositorV2",
    "composite_tile_v2",
    "preview_v2_pipeline",
    "ShadowRemover",
    "remove_shadows",
    "RemovalMethod",
    "SceneBuilder",
    "build_tile_scene",
    "TileRaytracer",
    "SunPosition",
    "render_tile_shadows",
]
__version__ = "0.2.0"
