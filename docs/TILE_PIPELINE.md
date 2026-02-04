# Photorealistic Tile Pipeline

Generate beautiful map tiles with ray-traced shadows for Zürich.

## Quick Start

### Preview a Single Tile

```bash
python3 -m scripts.tile_pipeline.cli preview --lat 47.376 --lng 8.54 --zoom 16
```

### Render Around a Coordinate

```bash
# Render 200m radius around a point (default)
python3 -m scripts.tile_pipeline.cli render --lat 47.378 --lng 8.54

# Render 500m radius around a point
python3 -m scripts.tile_pipeline.cli render --lat 47.378 --lng 8.54 --radius 500
```

### Render a Predefined Area

```bash
# List available areas
python3 -m scripts.tile_pipeline.cli areas

# Render Hauptbahnhof area
python3 -m scripts.tile_pipeline.cli render --area hauptbahnhof --preset afternoon

# Render small demo area (4 tiles at z16)
python3 -m scripts.tile_pipeline.cli render --area demo_small
```

### Render Custom Bounds

```bash
python3 -m scripts.tile_pipeline.cli render \
  --bounds "8.53,47.37,8.55,47.39" \
  --min-zoom 15 --max-zoom 17 \
  --preset afternoon
```

## Defining Custom Bounds

Bounds format: `west,south,east,north` (longitude min, latitude min, longitude max, latitude max)

### How to Find Bounds

1. **OpenStreetMap**: Right-click → "Show address" to get coordinates
2. **Google Maps**: Right-click to copy lat/lng
3. **geojson.io**: Draw a rectangle and copy bbox

### Common Zürich Areas

| Area | Bounds | Tiles (z16) |
|------|--------|-------------|
| Hauptbahnhof | 8.535,47.375,8.545,47.382 | ~6 |
| Bellevue/Sechseläutenplatz | 8.543,47.365,8.548,47.372 | ~4 |
| ETH/University | 8.545,47.375,8.555,47.382 | ~6 |
| Limmatquai | 8.540,47.368,8.548,47.378 | ~8 |
| Niederdorf (Old Town) | 8.538,47.368,8.548,47.375 | ~6 |
| Zürich West | 8.500,47.385,8.525,47.400 | ~35 |
| Oerlikon | 8.540,47.400,8.570,47.420 | ~40 |
| City Center (demo) | 8.530,47.365,8.555,47.385 | ~35 |
| Full Zürich | 8.440,47.320,8.630,47.440 | ~700 |

See `python -m scripts.tile_pipeline.cli areas` for the complete list with descriptions.

## Time Presets

Available presets control sun position and shadow appearance:

| Preset | Description | Use Case |
|--------|-------------|----------|
| `morning` | Low eastern sun, long shadows | Dramatic morning light |
| `afternoon` | Standard SW sun (default) | Balanced daytime view |
| `evening` | Low western sun, warm tones | Golden hour effect |
| `golden_hour` | Very low sun, dramatic shadows | Artistic renders |

```bash
# List all presets with sun angles
python -m scripts.tile_pipeline.cli presets
```

## Rendering Methods

### Basic (Fast, ~2s/tile)

Uses 2D shadow projection. Good for quick previews.

```bash
python -m scripts.tile_pipeline.cli render \
  --area demo_small \
  --preset afternoon
```

### Blender (Recommended, ~5-10s/tile)

GPU-accelerated ray tracing with soft shadows. Requires Blender installed.

```bash
python -m scripts.tile_pipeline.cli render \
  --area hauptbahnhof \
  --use-blender \
  --preset golden_hour
```

---

## Rendered Mode (Pure 3D)

Rendered mode bypasses satellite imagery entirely and generates tiles from 3D vector
data using Blender Cycles. This solves the "double shadow" problem where computed
shadows overlay existing shadows in satellite photos.

### When to Use Rendered Mode

| Scenario | Recommended Mode |
|----------|------------------|
| Photorealistic map tiles | `satellite` |
| Consistent visual style | `rendered` |
| Offline/no internet | `rendered` |
| Custom color schemes | `rendered` |
| Avoiding double shadows | `rendered` |

### Quick Start

```bash
# Preview with default style
python3 -m scripts.tile_pipeline.cli preview \
  --lat 47.378 --lng 8.54 --mode rendered

# Render area with specific style
python3 -m scripts.tile_pipeline.cli render \
  --area demo_small --mode rendered --style simcity
```

### Available Styles

| Style | Description |
|-------|-------------|
| `default` | Clean, neutral colors |
| `google_earth` | Realistic, muted tones like Google Earth 3D |
| `simcity` | Vibrant, game-like colors |
| `zurich` | Colors matching actual Zurich building palette |
| `winter` | Snow-covered ground, cool tones |
| `evening` | Warm golden hour lighting |
| `blueprint` | Technical blue monochrome |

```bash
# List all styles with details
python3 -m scripts.tile_pipeline.cli styles
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--mode rendered` | Enable pure 3D rendering |
| `--style <name>` | Visual style (default: `default`) |
| `--blender-samples` | Render quality (default: 64) |

### Requirements

- **Blender 3.0+** must be installed
- GPU recommended (Metal on Mac, CUDA/OptiX on NVIDIA)
- ~5-10 seconds per tile at 64 samples with GPU

---

## AO Tiles (Ambient Occlusion)

Pre-computed ambient occlusion tiles that add contact shadows at building bases.
These overlay satellite imagery to make buildings feel "grounded" without runtime ray tracing.

### Quick Start

```bash
# Generate AO tiles for an area
python3 -m scripts.tile_pipeline.ao_tile_generator \
  --bounds "8.535,47.375,8.545,47.382" \
  --zoom 16 \
  --output-dir public/tiles/ao \
  --buildings public/data/zurich-buildings.geojson
```

### What AO Tiles Are

| Property | Value |
|----------|-------|
| Format | Grayscale WebP (512x512) |
| White pixels | No occlusion (pass through) |
| Dark pixels | Contact shadow at building base |
| Blend mode | Multiply at ~35% opacity |

### CLI Options

| Option | Description |
|--------|-------------|
| `--bounds` | Geographic bounds (west,south,east,north) |
| `--zoom` | Tile zoom level (default: 16) |
| `--output-dir` | Output directory (creates z/x/y structure) |
| `--buildings` | Path to buildings GeoJSON |
| `--trees` | Path to trees GeoJSON (optional) |

### Output Structure

```
public/tiles/ao/
├── 16/
│   ├── 34321/
│   │   ├── 22948.webp
│   │   ├── 22949.webp
│   │   └── 22950.webp
│   └── 34322/
│       └── ...
```

### Integration with deck.gl

```typescript
import { createAOTileLayer } from '@/layers/AOTileLayer';

const aoLayer = createAOTileLayer({
  tileUrl: '/tiles/ao/{z}/{x}/{y}.webp',
  opacity: 0.35,  // Subtle grounding effect
});
```

### When to Use AO vs Shadows

| Use Case | Recommendation |
|----------|----------------|
| Static grounding effect | AO tiles |
| Time-of-day shadows | `--use-blender` photorealistic |
| Both combined | AO tiles + time shadows |

---

## Output

Tiles are saved to: `public/tiles/photorealistic/{z}/{x}/{y}.webp`

Directory structure follows standard TMS/XYZ scheme:

```
public/tiles/photorealistic/
├── 15/
│   └── 17160/
│       └── 11474.webp
├── 16/
│   ├── 34321/
│   │   ├── 22949.webp
│   │   ├── 22950.webp
│   │   └── 22951.webp
│   └── 34322/
│       └── ...
└── 17/
    └── ...
```

## CLI Reference

### Commands

| Command | Description |
|---------|-------------|
| `preview` | Render a single tile at a location |
| `render` | Render tiles for a region |
| `presets` | List available time presets |
| `areas` | List predefined Zürich areas |
| `info` | Show data source information |

### Preview Options

```bash
python -m scripts.tile_pipeline.cli preview \
  --lat 47.376        # Latitude (required)
  --lng 8.54          # Longitude (required)
  --zoom 16           # Zoom level (default: 16)
  --preset afternoon  # Time preset
  --output tile.png   # Output file
```

### Render Options

```bash
python3 -m scripts.tile_pipeline.cli render \
  --area hauptbahnhof     # Predefined area name
  --lat 47.378            # Center latitude (use with --lng)
  --lng 8.54              # Center longitude (use with --lat)
  --radius 200            # Radius in meters (default: 200)
  --bounds "w,s,e,n"      # Custom bounds as west,south,east,north
  --min-zoom 15           # Min zoom level
  --max-zoom 17           # Max zoom level
  --preset afternoon      # Time preset
  --workers 4             # Parallel workers
  --use-blender           # Use Blender ray tracing
  --blender-samples 16    # Ray tracing quality (default: 16)
  --dry-run               # Count tiles only
  -y, --yes               # Skip confirmation
```

**Priority**: `--area` > `--lat/--lng` > `--bounds` > default config

## Examples

### Quick Test (4 tiles)

```bash
python -m scripts.tile_pipeline.cli render --area demo_small --preset afternoon
```

### City Center Demo (~35 tiles)

```bash
python -m scripts.tile_pipeline.cli render \
  --area city_center \
  --min-zoom 16 --max-zoom 16 \
  --preset golden_hour \
  -y
```

### Full Neighborhood with Blender

```bash
python -m scripts.tile_pipeline.cli render \
  --area zurich_west \
  --min-zoom 15 --max-zoom 17 \
  --use-blender \
  --workers 2
```

### Custom Bounds

```bash
# Render specific coordinates
python -m scripts.tile_pipeline.cli render \
  --bounds "8.538,47.370,8.548,47.380" \
  --min-zoom 16 --max-zoom 16
```

## Troubleshooting

### "No satellite data"

The pipeline fetches SWISSIMAGE tiles from swisstopo. Check your internet connection.

### "No buildings found"

Run the data pipeline first:

```bash
python scripts/run-pipeline.py
```

### "Blender not found"

Install Blender and ensure it's in your PATH:

```bash
# macOS
brew install --cask blender

# Linux
sudo snap install blender --classic
```

### Slow rendering

- Reduce zoom range (e.g., only z16)
- Use `--workers 1` to reduce memory usage
- Start with smaller areas like `demo_small`

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Satellite  │     │   Elevation  │     │  Buildings  │
│  (SWISSIMAGE)│     │  (swissALTI) │     │  (GeoJSON)  │
└──────┬──────┘     └──────┬───────┘     └──────┬──────┘
       │                   │                    │
       ▼                   ▼                    ▼
┌──────────────────────────────────────────────────────┐
│                  Tile Compositor                      │
│  - Fetches data for tile bounds                      │
│  - Builds 3D scene from buildings                    │
│  - Computes shadows (basic or Blender)               │
│  - Composites final image                            │
└──────────────────────────────────────────────────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │  Output Tile    │
                 │  (.webp 512x512)│
                 └─────────────────┘
```

## Data Sources

| Data | Source | License |
|------|--------|---------|
| Satellite | SWISSIMAGE 10cm | swisstopo Open |
| Elevation | swissALTI3D | swisstopo Open |
| Buildings | Stadt Zürich | CC0 |
| Trees | Stadt Zürich | CC0 |
