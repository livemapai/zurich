# Tile Stitching Test Assets

This directory contains pre-stitched tile combinations for experimenting
with different stitching approaches across AI platforms.

## Directory Structure

```
stitching_tests/
├── raw/                 # Individual input tiles (A-F)
├── styled/              # Corresponding styled tiles
├── stitched_input/      # Pre-stitched raw combinations
└── stitched_output/     # Pre-stitched styled combinations
```

## Tile Grid Layout

Looking at the tiles from above (map coordinates) - full 4×3 grid:

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

## Stitching Patterns

| Pattern | Layout | Dimensions | Purpose |
|---------|--------|------------|---------|
| `horizontal_2_AB` | A+B | 1024×512 | Test horizontal edge matching |
| `horizontal_4_ABCD` | A+B+C+D | 2048×512 | Full row stitching |
| `vertical_3_AEI` | A/E/I | 512×1536 | Full column stitching |
| `grid_2x2_BCFG` | BC/FG | 1024×1024 | Center 2×2 grid |
| `grid_3x3_center` | ABC/EFG/IJK | 1536×1536 | Large 3×3 grid |
| `grid_4x3_full` | ABCD/EFGH/IJKL | 2048×1536 | Full 12-tile grid |

## Usage for Testing

### Manual Testing with Gemini/Claude/OpenAI Web UI

1. Upload a stitched input image (e.g., `stitched_input/horizontal_2_AB.png`)
2. Use a prompt like:

```
This is two map tiles stitched side-by-side. Convert them to [style]
while ensuring the seam between tiles is completely invisible.
The output should look like a single continuous image.
```

### Testing Edge Consistency

1. Style individual tiles A and B separately
2. Compare with stitched AB output
3. Check if the seam is visible when the individual styled tiles are placed together

### Recommended Test Prompts

**For pencil/sketch styles:**
```
Transform this map tile into a detailed architectural pencil sketch.
Pay special attention to maintaining consistent line weight and shading
across any tile boundaries to ensure seamless tiling.
```

**For artistic styles:**
```
Convert this satellite map view to a [watercolor/oil painting/impressionist] style.
Ensure colors and brush strokes are consistent across the entire image
to maintain seamless tile boundaries.
```

## Expected Challenges

1. **Edge discontinuity** - Different random seeds per tile cause visible seams
2. **Scale inconsistency** - Details may be rendered at different scales
3. **Color drift** - Slight color variations between tiles
4. **Texture alignment** - Repeated patterns may not align at edges

## Comparing Approaches

| Approach | Pros | Cons |
|----------|------|------|
| Pre-stitch + style | Perfect seams | Larger image = more $, lower quality |
| Style individually | Faster, cheaper | Visible seams |
| Post-stitch blend | Can work well | Complex, may blur details |
| Stitcher model pass | Good for some styles | Extra API call |

## Notes

- All tiles are 512×512 PNG (converted from WebP source)
- Transparent areas in L-shapes indicate empty cells
- Raw tiles are from: `hybrid-isometric_golden`
- Styled tiles are from: `pencil-deep-styler`
