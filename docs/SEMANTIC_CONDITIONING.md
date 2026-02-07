# Semantic Conditioning for LLM Style Transfer

This document describes the semantic conditioning system that helps LLMs understand scene structure for better style transfer results.

## Overview

Semantic conditioning provides a second "semantic" image alongside the rendered color tile. This semantic image uses distinct colors for different element types (roofs, water, trees), helping the LLM understand scene structure.

**Benefits:**
- Clearer element boundaries in style transfer
- Consistent treatment of similar elements (all terracotta roofs look similar)
- Better distinction between overlapping features

## Two-Pass Workflow

### Old Approach: Single Color Tile

```
Color Tile → LLM → Styled Output
```

The LLM receives only the rendered color tile and must infer element types from appearance.

### New Approach: Color + Semantic Pair

```
Color Tile ─┐
            ├→ LLM → Styled Output
Semantic Tile ─┘
```

The LLM receives both the rendered tile AND a semantic map, allowing it to:
- Distinguish between similar-looking elements
- Apply consistent styles per element type
- Preserve boundaries more accurately

## Color Palette

### Roof Types

| Roof Type | Color (RGB) | Hex | Typical Buildings |
|-----------|-------------|-----|-------------------|
| Terracotta | `(0.55, 0.35, 0.28)` | #8C5947 | Residential, schools |
| Slate | `(0.35, 0.32, 0.30)` | #59524D | Churches, historic, museums |
| Flat | `(0.45, 0.45, 0.48)` | #73737A | Commercial, industrial, hospitals |

### Water Bodies

| Water Type | Color (RGB) | Hex | Description |
|------------|-------------|-----|-------------|
| Lake | `(0.15, 0.30, 0.45)` | #264D73 | Deep blue (Zürichsee) |
| River | `(0.20, 0.35, 0.50)` | #335980 | Medium blue (Limmat, Sihl) |
| Stream | `(0.25, 0.40, 0.55)` | #40668C | Lighter blue |

### Other Elements

| Element | Color (RGB) | Hex | Description |
|---------|-------------|-----|-------------|
| Trees | `(0.25, 0.48, 0.20)` | #407A33 | Forest green canopies |
| Streets | `(0.35, 0.35, 0.38)` | #595961 | Dark asphalt gray |
| Ground | `(0.45, 0.55, 0.35)` | #738C59 | Grass/lawn green |

## Roof Material Inference

For buildings without explicit roof type, the system infers roof material from building type:

| Building Type | Inferred Roof |
|---------------|---------------|
| `Gebaeude_Wohngebaeude` | terracotta |
| `Gebaeude_Wohngebaeude_mit_Gewerbe` | terracotta |
| `Gebaeude_Schule` | terracotta |
| `Gebaeude_Kirche` | slate |
| `Gebaeude_Verwaltung` | slate |
| `Gebaeude_Museum` | slate |
| `Gebaeude_Theater` | slate |
| `Gebaeude_Handel` | flat |
| `Gebaeude_Buerohaus` | flat |
| `Gebaeude_Industrie` | flat |
| `Gebaeude_Spital` | flat |
| Default | terracotta |

## CLI Usage

### Render Semantic Tile

```bash
# Render a single semantic tile
python -m scripts.tile_pipeline.cli render-semantic \
    --tile 16/34322/22950 \
    --output public/tiles/semantic/
```

### Use with nano_styler.py

```bash
# Style with semantic conditioning
python scripts/tile_pipeline/nano_styler.py \
    --tile public/tiles/hybrid-golden_hour/16/34322/22950.webp \
    --semantic public/tiles/semantic/16/34322/22950.webp \
    --prompt "hand-drawn pencil sketch with deep shadows and crosshatching" \
    --output output/pencil_styled.png
```

### Batch Workflow

```bash
# 1. Generate semantic tiles for an area
for z in 16; do
    for x in 34320 34321 34322 34323 34324 34325; do
        for y in 22949 22950 22951; do
            python -m scripts.tile_pipeline.cli render-semantic --tile $z/$x/$y
        done
    done
done

# 2. Style tiles with semantic conditioning
python scripts/tile_pipeline/nano_styler.py \
    --batch public/tiles/hybrid-golden_hour \
    --style-name pencil-semantic \
    --prompt "hand-drawn pencil sketch" \
    # Add --semantic-dir flag when batch mode supports it
```

## API Usage

### BlenderTileRenderer.render_semantic()

```python
from scripts.tile_pipeline.blender_renderer import BlenderTileRenderer, ColorRenderConfig
from scripts.tile_pipeline.sources.vector import VectorSource

# Load data
vector_source = VectorSource("public/data/zurich-buildings.geojson")
buildings = vector_source.get_features_in_bounds(bounds)

# Configure renderer
config = ColorRenderConfig(image_size=512, samples=16)
renderer = BlenderTileRenderer(config=config)

# Render semantic tile
semantic_image = renderer.render_semantic(
    buildings=buildings,
    trees=trees,
    elevation=None,
    bounds=(8.53, 47.37, 8.55, 47.39),
    streets=streets,
    water_bodies=water,
)
```

### Using Semantic Colors in Custom Code

```python
from scripts.tile_pipeline.materials import (
    infer_roof_material,
    get_semantic_roof_color,
    get_semantic_water_color,
    SEMANTIC_ELEMENT_COLORS,
)

# Get roof color for a building
building_type = "Gebaeude_Wohngebaeude"
roof_color = get_semantic_roof_color(building_type)  # (0.55, 0.35, 0.28)

# Get water color
water_type = "lake"
water_color = get_semantic_water_color(water_type)  # (0.15, 0.30, 0.45)

# Get tree color
tree_color = SEMANTIC_ELEMENT_COLORS["trees"]  # (0.25, 0.48, 0.20)
```

## Technical Details

### Rendering Pipeline

1. **Data Loading**: Buildings, trees, streets, water bodies from GeoJSON
2. **Roof Inference**: Building type → roof material mapping
3. **Material Creation**: Flat diffuse materials for each semantic class
4. **Scene Setup**: Orthographic top-down camera, soft ambient lighting
5. **Blender Render**: Cycles with low samples (16) for fast clean output

### Blender Scene Configuration

- **Camera**: Orthographic, top-down (0° tilt)
- **Lighting**: Soft ambient + high-altitude sun for subtle shadows
- **Materials**: Simple diffuse shaders (no specular/roughness effects)
- **Resolution**: 512×512 pixels
- **Samples**: 16 (low for fast render, no complex shading needed)

## File Structure

```
public/tiles/
├── hybrid-golden_hour/       # Color renders
│   └── 16/34322/22950.webp
├── semantic/                 # Semantic conditioning tiles
│   └── 16/34322/22950.webp
└── pencil-semantic/          # LLM-styled output
    └── 16/34322/22950.webp
```

## Verification

### Visual Check

1. **Color tile**: Buildings have varied colors, shadows, textures
2. **Semantic tile**: Clear class colors, flat shading, no shadows
3. **Overlay**: Pixel-perfect alignment between both

### Alignment Test

```python
import numpy as np
from PIL import Image

color = np.array(Image.open("public/tiles/hybrid-golden_hour/16/34322/22950.webp"))
semantic = np.array(Image.open("public/tiles/semantic/16/34322/22950.webp"))

# Both should be same size
assert color.shape == semantic.shape, "Tiles not aligned!"
```

## Future Improvements

1. **LOD2 Roof Geometry**: Use actual 3D roof shapes for buildings with LOD2 data
2. **Batch Semantic Mode**: Add `--semantic-dir` to nano_styler.py batch mode
3. **Edge Blending**: Smooth transitions at tile edges for seamless tiling
4. **Custom Palettes**: Allow users to define their own semantic color schemes
