# Tile Stitching Experimentation Framework

A comprehensive framework for testing and comparing different tile stitching approaches for AI-powered map styling.

## 🏆 Recommended Approach: Pre-Stitch Full Grid (#6)

**TL;DR:** Style all tiles as ONE image. It's the fastest, cheapest, AND best quality.

| Approach | Seam Score | Time | API Calls |
|----------|------------|------|-----------|
| **6. Full Grid** | **8.25** | **9.4s** | **1** |
| 4. 3×3 | 14.09 | 17.9s | 2 |
| 3. 2×2 | 23.52 | 57.7s | 6 |
| 1. Individual | 30.58 | 108.0s | 12 |

**Key Finding:** More context = better consistency. When the AI sees all tiles at once, it applies ONE unified style decision with no seams.

## Overview

This framework tests **13 different approaches** to generating consistent, seamless styled tiles. Each approach is designed to address the "seam problem" - visible discontinuities at tile edges when styling tiles independently.

## Quick Start

```bash
# List available approaches
python -m scripts.tile_pipeline.experiments.experiment_runner --list

# Run specific approaches
python -m scripts.tile_pipeline.experiments.experiment_runner \
    --source scripts/tile_pipeline/assets/stitching_tests/raw \
    --prompt "architectural pencil sketch" \
    --approaches 1,3,7

# Run all approaches (expensive!)
python -m scripts.tile_pipeline.experiments.experiment_runner \
    --source scripts/tile_pipeline/assets/stitching_tests/raw \
    --prompt "architectural pencil sketch" \
    --all
```

## The 12 Approaches

### Category A: Baseline (No Context)

| ID | Name | Description | Expected Result |
|----|------|-------------|-----------------|
| 1 | `individual` | Style each tile independently | Visible seams, color drift |
| 2 | `individual_low_temp` | Individual + temperature=0.1 | Slightly better consistency |

### Category B: Pre-Stitch Then Style

| ID | Name | Description | Expected Result |
|----|------|-------------|-----------------|
| 3 | `pre_stitch_2x2` | Stitch 2×2 → style → split | Good local consistency |
| 4 | `pre_stitch_3x3` | Stitch 3×3 → style → split | Better but larger API call |
| 5 | `pre_stitch_full_row` | Stitch rows → style → split | Horizontal continuity |
| 6 | `pre_stitch_full_grid` | Stitch all 12 → style → split | Best seams but may exceed limits |

### Category C: Context-Aware Generation

| ID | Name | Description | Expected Result |
|----|------|-------------|-----------------|
| 7 | `l_shape_context` | Use L-shaped neighbor context | Good with progressive expansion |
| 8 | `two_pass_reference` | Two-pass with style reference | Better with full context |
| 9 | `sliding_window_2x2` | Overlapping 2×2 windows | Very smooth but expensive |

### Category D: Post-Processing

| ID | Name | Description | Expected Result |
|----|------|-------------|-----------------|
| 10 | `individual_edge_blend` | Individual → blend edges | Quick fix, may blur |
| 11 | `individual_stitcher_pass` | Individual → AI fixes seams | Two-phase approach |

### Category E: Hybrid

| ID | Name | Description | Expected Result |
|----|------|-------------|-----------------|
| 12 | `pre_stitch_seed_expand` | Pre-stitch seed → expand | Balance of quality and cost |
| 13 | `overlap_feathered_blend` | Pre-stitch with overlap → blend | ⚠️ Not recommended (ghosting)

## Output Structure

```
experiments/
├── approach_01_individual/
│   ├── output/                    # Individual tiles
│   │   ├── tile_A.png
│   │   ├── tile_B.png
│   │   └── ...
│   ├── stitched_result.png        # Full grid stitched
│   ├── seam_heatmap.png           # Seam quality visualization
│   └── analysis.json              # Metrics
│
├── approach_02_individual_low_temp/
├── ... (approaches 03-12)
│
├── comparison/
│   ├── side_by_side.png           # Visual comparison
│   ├── rankings.md                # Performance rankings
│   └── results.json               # All metrics
│
├── EXPERIMENT_LOG.md              # Detailed experiment log
└── README.md                      # This file
```

## Metrics

### Seam Score

The primary metric is **seam score** - lower is better. It measures:
- Mean pixel difference at tile edges
- Gradient continuity across seams
- Color consistency

### Cost Metrics

- **API Calls**: Number of Gemini API calls
- **Time**: Total execution time

## Recommended Prompt

For testing, use the architectural pencil sketch prompt:

```
Transform this aerial map view into a detailed architectural pencil sketch
drawing, as if hand-drawn by a master architect. Use varying line weights -
bold confident strokes for building edges and rooflines, lighter hatching
for shadows and depth. Add subtle cross-hatching to create the illusion of
3D depth and volume while maintaining the exact geometry. The style should
evoke architectural presentation drawings from the golden age of draftsmanship.
```

## Source Tiles

The test grid is a 4×3 arrangement of tiles:

```
    x=34321  x=34322  x=34323  x=34324
    ───────  ───────  ───────  ───────
y=22949 │  A   │   B   │   C   │   D   │
    ───────  ───────  ───────  ───────
y=22950 │  E   │   F   │   G   │   H   │
    ───────  ───────  ───────  ───────
y=22951 │  I   │   J   │   K   │   L   │
    ───────  ───────  ───────  ───────
```

## Environment

Requires `GOOGLE_API_KEY` environment variable set for Gemini API access.

```bash
export GOOGLE_API_KEY=your_api_key_here
```

## Files

| File | Purpose |
|------|---------|
| `experiment_runner.py` | Main orchestration script |
| `utils.py` | Image manipulation utilities |
| `analysis.py` | Seam analysis and comparison tools |
| `approaches/` | Approach implementations |
| `approaches/base.py` | Base class for approaches |
| `approaches/individual.py` | Approaches 1-2 |
| `approaches/pre_stitch.py` | Approaches 3-6 |
| `approaches/context_aware.py` | Approaches 7-9 |
| `approaches/post_process.py` | Approaches 10-11 |
| `approaches/hybrid.py` | Approaches 12-13 |

## Adding New Approaches

1. Create a new class inheriting from `BaseApproach`
2. Implement the `run()` method
3. Set class attributes: `description`, `category`
4. Register in `approaches/__init__.py`

```python
from .base import BaseApproach

class MyApproach(BaseApproach):
    description = "My custom approach"
    category = "Custom"

    def run(self, source_grid: TileGrid) -> TileGrid:
        result = TileGrid()
        # Your logic here
        return result

# In __init__.py:
APPROACHES.register(13, "my_approach", MyApproach)
```
