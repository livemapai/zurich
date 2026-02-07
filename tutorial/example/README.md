# Map Rendering Workshop

## Files

| File | Description |
|------|-------------|
| `index.html` | Tasks 1-3: Raster + Vector tiles with labels |
| `style.json` | MapLibre style for Maputnik editing |
| `pmtiles.html` | Task 4: PMTiles example |

## Running

```bash
npx http-server . -p 3002 --cors
```

Then open:
- http://localhost:3002 - Main example (raster + vector)
- http://localhost:3002/pmtiles.html - PMTiles example

## Task Summary

### Task 1: Raster Tiles
- OpenStreetMap tiles as raster source
- `hash: 'map'` for URL state
- `showTileBoundaries = true` for debugging

### Task 2: Vector Tiles
- MapLibre demo tiles (countries layer)
- Blue country borders (line layer)

### Task 3: Maputnik
- Export style with `map.getStyle()`
- Edit in https://maplibre.org/maputnik/
- View → Inspect to explore vector data
- Added symbol layer with `["get", "NAME"]` expression

### Task 4: PMTiles
- Single-file tile archive format
- Protocol handler: `pmtiles://` URLs
- Can extract regions with `pmtiles extract`

### Task 5: Planetiler
See https://github.com/onthegomap/planetiler-examples
- Java-based tile generation
- Process OSM data into vector tiles
- Custom schemas possible
