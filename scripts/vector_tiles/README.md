# Vector Tile Pipeline for Zurich

Creates PMTiles vector tiles from GeoJSON data using Tippecanoe.

## Prerequisites

```bash
# Install system tools
brew install tippecanoe pmtiles

# Install Python dependency (for wobble effect)
pip3 install noise
```

## Usage

### Full Pipeline

```bash
# Clean geometric tiles
python3 -m scripts.vector_tiles.pipeline all

# Hand-drawn style with Perlin noise distortion
python3 -m scripts.vector_tiles.pipeline all --wobble
```

### Individual Steps

```bash
# Check prerequisites
python3 -m scripts.vector_tiles.pipeline check

# Preprocess data (sample trees, create shadows, transform streets)
python3 -m scripts.vector_tiles.pipeline prepare

# Generate MBTiles with Tippecanoe
python3 -m scripts.vector_tiles.pipeline generate

# Convert MBTiles → PMTiles
python3 -m scripts.vector_tiles.pipeline convert

# Generate MapLibre style.json
python3 -m scripts.vector_tiles.pipeline style
```

## Output Files

| File | Size | Description |
|------|------|-------------|
| `zurich-vector.pmtiles` | ~40 MB | Vector tiles (clean) |
| `zurich-wobble.pmtiles` | ~40 MB | Vector tiles (hand-drawn) |
| `zurich-style.json` | ~12 KB | MapLibre style |

## Layers

| Layer | Zoom | Features | Description |
|-------|------|----------|-------------|
| water | 0-18 | 4 | Lakes, rivers |
| buildings | 12-18 | 65,677 | Building footprints |
| building_shadows | 14-18 | 65,677 | Offset shadow geometry |
| roofs | 16-18 | 13,461 | LOD2 roof faces |
| transportation | 12-18 | 9,954 | Streets, paths |
| railway | 13-18 | 6,227 | Tram tracks |
| trees | 14-18 | 80,484 | Street trees (sampled at z14-15) |
| poi | 15-18 | 55,000+ | Benches, fountains, lights, etc. |

## Tree Sampling Strategy

Trees are sampled at lower zoom levels to reduce tile size:

| Zoom | Sample Rate | Trees |
|------|-------------|-------|
| z14 | 1 in 10 | ~8,000 |
| z15 | 1 in 5 | ~16,000 |
| z16+ | All | ~80,000 |

## Wobble Effect

When `--wobble` is enabled, Perlin noise distortion is applied to polygon coordinates, creating organic/hand-drawn edges with ~1 meter variation.

```bash
python3 -m scripts.vector_tiles.pipeline all --wobble
```

## Viewing Tiles

Access the vector viewer at `/vector` route in the app.

Or use Maputnik for style editing:
1. Open https://maputnik.github.io/
2. Load `zurich-style.json`
3. Update PMTiles URL to local server

## Style Customization

The style colors buildings by German `art` type:

| Art Value | Color | Hex |
|-----------|-------|-----|
| Gebaeude_Wohnen | Warm beige | #e8dcc8 |
| Gebaeude_Industrie | Gray | #d4d4d4 |
| Gebaeude_Gewerbe | Blue-gray | #c8d8e8 |
| Gebaeude_oeffentlich | Green-gray | #d8e8c8 |

Roofs are colored by material:

| Material | Color | Hex |
|----------|-------|-----|
| roof_terracotta | Terra cotta | #b8745a |
| roof_slate | Dark slate | #5a5855 |
| roof_flat | Gray | #8a8a8d |
