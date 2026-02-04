# Photorealistic Tile Pipeline Plan

## Overview

This document outlines the complete pipeline for generating photorealistic map tiles that achieve a 2D/3D hybrid look with accurate shadows and beautiful hillshade effects.

## Problem Statement

### Current Issues with SWISSIMAGE
1. **Baked-in shadows**: Satellite imagery captured during afternoon has shadows already present
2. **Double shadows**: Adding computed shadows on top creates unnaturally dark areas
3. **Inconsistent lighting**: Different capture times across tile mosaic create visible seams
4. **Lost detail**: Shadows obscure ground detail that could be recovered

### Goal
Create tiles that look like high-quality 3D renders:
- Consistent lighting direction across all tiles
- Shadows that match the specified time preset
- Enhanced depth from hillshade without looking "overprocessed"
- Natural color grading (Imhof-style warm/cool tints)

---

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PHOTOREALISTIC TILE PIPELINE                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐  │
│  │   Sources   │───▶│  Analysis   │───▶│   Shadow Neutralization │  │
│  └─────────────┘    └─────────────┘    └─────────────────────────┘  │
│        │                                          │                   │
│        ▼                                          ▼                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐  │
│  │  Hillshade  │───▶│   Shadows   │───▶│      Compositing        │  │
│  │  + Imhof    │    │  (Computed) │    └─────────────────────────┘  │
│  └─────────────┘    └─────────────┘              │                   │
│                                                   ▼                   │
│                                          ┌───────────────┐           │
│                                          │  Final Tile   │           │
│                                          └───────────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Data Sources (Current)

### 1.1 Satellite Imagery
- **Source**: SWISSIMAGE 10cm (swisstopo WMTS)
- **Resolution**: 10cm ground sample distance
- **Format**: JPEG tiles, 256×256 native, combined to 512×512
- **Issue**: Contains baked shadows from capture time (~afternoon)

### 1.2 Elevation Data
- **Source**: Mapterhorn terrain tiles (swissALTI3D)
- **Resolution**: 0.5m in Switzerland
- **Encoding**: Terrarium (RGB-encoded elevation)
- **Format**: WebP, 512×512

### 1.3 Vector Data
- **Buildings**: Stadt Zürich open data (GeoJSON with heights)
- **Trees**: Stadt Zürich tree inventory (points with heights)

---

## Phase 2: Shadow Analysis (NEW)

### 2.1 Shadow Detection
Module: `shadow_analyzer.py`

**Techniques:**
1. **Luminosity threshold** - Shadows are darker (L < 0.35 in LAB)
2. **Color temperature** - Shadows have blue cast (low B in LAB)
3. **Gradient analysis** - Shadow edges have characteristic gradients
4. **Texture analysis** - Shadows have reduced local contrast

**Output:**
- Shadow probability map (soft 0-1 values)
- Estimated sun position (azimuth, altitude)
- Estimated capture time
- Shadow coverage percentage

### 2.2 Capture Time Estimation
- Analyze shadow direction to estimate sun azimuth
- Cross-reference with known capture schedule (Eastern region: 2019, 2022, 2025)
- Standard capture: sun angle ≥30°, within 2hrs of solar noon

---

## Phase 3: Shadow Neutralization (NEW)

### 3.1 Shadow Lifting
Module: `shadow_neutralizer.py`

**Algorithm:**
1. Convert to LAB color space for perceptual processing
2. Create soft shadow mask from probability map
3. Apply graduated tone curve (lift shadows more than midtones)
4. Target shadow luminosity: 0.40-0.50 (adjustable)

### 3.2 Color Temperature Correction
- Shadows have blue cast from skylight illumination
- Shift LAB 'b' channel toward neutral in shadow areas
- Preserve color relationships outside shadows

### 3.3 Detail Recovery
- Apply local contrast enhancement (unsharp mask) in shadows
- Boost: 20-40% in shadow regions
- Sigma: 15-25 pixels for natural look

### 3.4 Adaptive Parameters
Based on analysis results:

| Condition | Target Level | Temp Correction | Detail Boost |
|-----------|--------------|-----------------|--------------|
| Light shadows (<15%) | 0.40 | 0.3 | 0.2 |
| Moderate shadows (15-30%) | 0.45 | 0.5 | 0.3 |
| Heavy shadows (>30%) | 0.55 | 0.7 | 0.5 |
| High contrast (>5x) | -0.05 | -0.1 | -0.1 |

---

## Phase 4: Hillshade Generation (Enhanced)

### 4.1 Multi-Directional Hillshade
Current: Single light source
Enhanced: Blend multiple light directions

**Technique:**
- Primary light: From sun position (preset-specific)
- Secondary light: Ambient fill from opposite direction (20% weight)
- Prevents completely black shadows on terrain

### 4.2 Imhof Color Shifts
Based on Eduard Imhof's cartographic principles:

| Slope Orientation | Color Shift |
|-------------------|-------------|
| Sun-facing (lit) | Warm yellow (+b, slight +a) |
| Shadow-facing | Cool blue (-b, slight -a) |
| Transition zones | Gradient blend |

**Parameters (tunable per preset):**
- `warm_strength`: 0.2-0.5
- `cool_strength`: 0.3-0.6

---

## Phase 5: Shadow Computation (Current + Enhanced)

### 5.1 Building Shadows
- Project building footprints based on height and sun position
- Sharp edges for building shadows

### 5.2 Tree Shadows
- Soft elliptical shadows with Gaussian blur
- Crown diameter estimation from tree data

### 5.3 Ambient Occlusion
- Contact shadows at building bases
- 3m falloff radius
- Subtle darkening (40% max)

### 5.4 Shadow Integration (NEW)
**Smart blending to avoid double shadows:**

1. Detect where new shadow overlaps existing (from analysis)
2. Reduce opacity of computed shadow in overlap areas
3. Use `max()` blending instead of `multiply` in problem areas

---

## Phase 6: Compositing (Enhanced)

### 6.1 Layer Stack (Bottom to Top)
1. **Shadow-neutralized satellite** (instead of raw)
2. **Hillshade** (soft light, 50-70% opacity)
3. **Imhof color shifts** (direct LAB channel modification)
4. **Building shadows** (multiply, 60-80% opacity)
5. **Tree shadows** (multiply, 40-60% opacity)
6. **Ambient occlusion** (multiply, 30-50% opacity)

### 6.2 Color Space
All blending in LAB color space for perceptual accuracy:
- L channel: Lightness modifications (hillshade, shadows)
- a/b channels: Color shifts (Imhof tinting)

### 6.3 Preset-Specific Adjustments
| Preset | Hillshade | Shadow | Warm | Cool |
|--------|-----------|--------|------|------|
| Morning | 60% | 70% | 0.4 | 0.3 |
| Afternoon | 50% | 80% | 0.3 | 0.4 |
| Evening | 70% | 85% | 0.5 | 0.3 |

---

## Phase 7: Quality Enhancement (NEW)

### 7.1 Local Contrast (Clarity)
- Enhance mid-frequency detail
- Apply after compositing
- Strength: 10-20%

### 7.2 Color Grading
- Optional final color curve adjustments
- Preset-specific (warmer for golden hour, neutral for midday)

### 7.3 Edge Enhancement
- Subtle sharpening for building edges
- Mask to avoid noise in smooth areas

---

## Validation Scripts

### Test Individual Components
```bash
# Full test suite
python -m scripts.tile_pipeline.test_pipeline --all

# Shadow analysis only
python -m scripts.tile_pipeline.test_pipeline --shadow-analysis

# Neutralization comparison
python -m scripts.tile_pipeline.test_pipeline --shadow-neutralization

# Compositing with presets
python -m scripts.tile_pipeline.test_pipeline --compositing
```

### Explore and Experiment
```bash
# Analyze a tile
python -m scripts.tile_pipeline.explore_tile analyze --lat 47.37 --lng 8.54

# Test neutralization parameters
python -m scripts.tile_pipeline.explore_tile neutralize \
    --input satellite.png \
    --target 0.45 \
    --temperature 0.5

# Compare original vs processed
python -m scripts.tile_pipeline.explore_tile compare --preset evening_golden

# List all presets
python -m scripts.tile_pipeline.explore_tile presets
```

---

## Implementation Checklist

### Completed ✅
- [x] Shadow analyzer module (`shadow_analyzer.py`)
- [x] Shadow neutralizer module (`shadow_neutralizer.py`)
- [x] Test pipeline script (`test_pipeline.py`)
- [x] Exploration script (`explore_tile.py`)
- [x] LAB color space utilities (`color_space.py`)
- [x] Hillshade with Imhof (`hillshade.py`)
- [x] Building/tree shadow casting (`shadows.py`)
- [x] Tile compositor (`tile_compositor.py`)
- [x] Time presets (`time_presets.py`)

### To Implement 🔲
- [ ] Smart shadow blending (avoid double shadows)
- [ ] Multi-directional hillshade
- [ ] Local contrast enhancement (clarity)
- [ ] Final color grading
- [ ] LLM-assisted quality validation
- [ ] Batch processing with progress tracking
- [ ] Tile caching and incremental updates

---

## Quality Metrics

### Automated Checks
1. **Shadow balance**: Shadows should be 15-35% of image
2. **Contrast ratio**: 3-6x (not too flat, not too harsh)
3. **Color temperature**: Consistent across tile mosaic
4. **Edge definition**: Building edges visible but not harsh

### Visual Inspection (LLM-Assisted)
1. Does the tile look like a 3D render?
2. Are shadows consistent with the time preset?
3. Is there visible "double shadowing"?
4. Does the hillshade enhance or distract?

---

## Next Steps

1. **Run validation tests** to verify current components work
2. **Tune parameters** based on test output
3. **Implement missing components** (smart blending, clarity)
4. **Process sample region** for visual review
5. **Iterate on parameters** until quality is acceptable
6. **Scale to full Zurich region**

---

## Phase 8: Rendered Mode (Alternative Pipeline)

### 8.1 Overview

Rendered mode is an alternative to the satellite-based pipeline that generates
tiles purely from 3D vector data using Blender Cycles ray tracing.

**Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                   RENDERED MODE PIPELINE                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ Buildings  │  │   Trees    │  │ Elevation  │            │
│  │ (GeoJSON)  │  │ (GeoJSON)  │  │ (Terrain)  │            │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘            │
│        │               │               │                    │
│        └───────────────┼───────────────┘                    │
│                        ▼                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Blender Cycles Renderer                  │  │
│  │  • Colored materials from style                       │  │
│  │  • Principled BSDF shaders                           │  │
│  │  • GPU-accelerated ray tracing                       │  │
│  │  • Sun lamp + sky background                         │  │
│  └──────────────────────────────────────────────────────┘  │
│                        │                                    │
│                        ▼                                    │
│               ┌─────────────────┐                          │
│               │   Output Tile   │                          │
│               │  (.webp 512x512)│                          │
│               └─────────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Key Components

| Module | Purpose |
|--------|---------|
| `materials.py` | RenderStyle dataclass with 7 presets |
| `blender_renderer.py` | Python wrapper for Blender subprocess |
| `blender_scene.py` | Scene building + color material setup |
| `tile_renderer.py` | RenderedTileRenderer class |

### 8.3 Material System

Materials use Blender's Principled BSDF shader for physically-based rendering:

| Material | Color Source | Roughness |
|----------|--------------|-----------|
| Building walls | `style.building_wall` | 0.8 |
| Building roofs | `style.building_roof` | 0.9 |
| Tree foliage | `style.tree_foliage` | 0.95 |
| Tree trunks | `style.tree_trunk` | 0.9 |
| Ground/terrain | `style.terrain` | 0.95 |

### 8.4 Available Styles

7 visual styles are defined in `materials.py`:

| Style | Key Characteristic |
|-------|-------------------|
| `default` | Neutral warm beige buildings |
| `google_earth` | Muted, realistic tones |
| `simcity` | Vibrant game-like colors |
| `zurich` | Matches actual Zurich palette |
| `winter` | Snow-covered ground |
| `evening` | Golden hour lighting |
| `blueprint` | Technical blue monochrome |

### 8.5 Advantages Over Satellite Mode

1. **No double shadows** - Shadows computed in single pass
2. **Consistent lighting** - Same sun angle across all tiles
3. **Customizable colors** - Easy to create new visual styles
4. **Offline capable** - No need for satellite tile fetching
5. **Deterministic** - Same inputs always produce same output

### 8.6 CLI Usage

```bash
# Preview single tile
python3 -m scripts.tile_pipeline.cli preview \
  --lat 47.378 --lng 8.54 \
  --mode rendered --style zurich

# Render region
python3 -m scripts.tile_pipeline.cli render \
  --area hauptbahnhof \
  --mode rendered --style google_earth \
  --blender-samples 128

# List available styles
python3 -m scripts.tile_pipeline.cli styles
```

---

## References

- [SWISSIMAGE Documentation](https://www.swisstopo.admin.ch/en/orthoimage-swissimage-10)
- [Mapterhorn Terrain Tiles](https://mapterhorn.com/)
- [Shadow Detection in Aerial Imagery (Silva et al. 2017)](https://github.com/ThomasWangWeiHong/Shadow-Detection-Algorithm-for-Aerial-and-Satellite-Images)
- [Imhof Cartographic Principles](https://en.wikipedia.org/wiki/Eduard_Imhof)
- [LAB Color Space](https://en.wikipedia.org/wiki/CIELAB_color_space)
