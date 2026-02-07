# Vector Tile Pipeline Workshop - Agent Instructions

This document provides instructions for AI agents assisting users with the workshop.

> **Note:** This workshop is an exploratory reference guide, not a structured course.
> There is no progress tracking or completion status. Users can explore tasks in any order.

## Prerequisites

- Node.js 18+ (for `npx http-server`)
- Modern browser with DevTools (Chrome recommended)
- Java 21+ (only for Task 5: Planetiler)
- ~2GB disk space for OSM data processing

## Quick Start

```bash
# Navigate to workshop directory
cd rendering-workshop

# Serve the workshop locally
npx http-server . -p 3000 --cors

# Open in browser
open http://localhost:3000
```

## Workshop Task Overview

| Task | File | Duration | Prerequisites |
|------|------|----------|---------------|
| 1. Raster Tiles | `tasks/01-raster-tiles.html` | 10 min | None |
| 2. Vector Tiles | `tasks/02-vector-tiles.html` | 15 min | Task 1 |
| 3. Maputnik | `tasks/03-maputnik/instructions.html` | 20 min | Task 2 |
| 4. PMTiles | `tasks/04-pmtiles.html` | 15 min | Task 2 |
| 5. Planetiler | `tasks/05-planetiler/instructions.html` | 30 min | Java 21 |
| 6. MVT Inspection | `tasks/06-mvt-inspect.html` | 15 min | Task 2 |
| 7. TileJSON | `tasks/07-tilejson.html` | 10 min | None |
| Capstone | `capstone/index.html` | 20 min | Recommended: all above |

## Recommended Exploration Paths

### Path A: Client-Side Focus (1.5 hours)
```
Task 1 → Task 2 → Task 6 → Task 7 → Task 3 → Capstone
```
Focus on understanding how browsers render vector tiles.

### Path B: Full Stack (2.5 hours)
```
Task 1 → Task 2 → Task 5 → Task 4 → Task 6 → Task 7 → Task 3 → Capstone
```
Complete end-to-end pipeline including tile generation.

### Path C: Quick Overview (45 min)
```
Task 1 → Task 2 → Task 7 → Capstone
```
Minimal path to understand the core concepts.

## Task-by-Task Guide

### Task 1: Raster Tiles
**Objective:** Understand pre-rendered image tiles and Z/X/Y coordinates.

**Key Actions:**
1. Open `http://localhost:3000/tasks/01-raster-tiles.html`
2. Toggle "Show Tile Boundaries" checkbox
3. Open DevTools Network tab (F12)
4. Pan/zoom the map and observe tile requests
5. Note URL pattern: `/{z}/{x}/{y}.png`

**What to Learn:**
- The Z/X/Y coordinate system for tile addressing
- How PNG tile requests appear in the Network tab
- URL hash navigation for sharing map positions

### Task 2: Vector Tiles
**Objective:** Learn client-side rendering from geometry data.

**Key Actions:**
1. Open `http://localhost:3000/tasks/02-vector-tiles.html`
2. Use color pickers to change fill/stroke colors
3. Click on map features to query properties
4. Open Network tab - notice `.pbf` files

**What to Learn:**
- The `source-layer` concept in vector tiles
- Why style changes don't require new network requests
- How to query feature properties via click events

### Task 3: Maputnik
**Objective:** Visual style editing workflow.

**Key Actions:**
1. Open Task 2's map
2. Run in console: `copy(JSON.stringify(map.getStyle(), null, 2))`
3. Open https://maputnik.github.io/editor
4. Upload pasted style JSON
5. Make modifications using visual editor
6. Export modified style

**What to Learn:**
- Roundtrip workflow: code → Maputnik → code
- Expression syntax like `["get", "NAME"]`
- Using Inspect mode to discover layer fields

### Task 4: PMTiles
**Objective:** Serverless tile hosting via HTTP range requests.

**Key Actions:**
1. Open `http://localhost:3000/tasks/04-pmtiles.html`
2. Open DevTools Network tab
3. Click on any `.pmtiles` request
4. Examine `Range` request header
5. Examine `Content-Range` response header

**What to Learn:**
- Cloud-optimized tile format structure
- How HTTP range requests work
- Benefits over traditional tile servers

### Task 5: Planetiler
**Objective:** Generate vector tiles from OSM data.

**Prerequisites Check:**
```bash
java --version  # Must be 21+
```

**Key Actions:**
1. Download Planetiler JAR
2. Download Switzerland OSM extract (~400MB)
3. Run: `java -Xmx2g -jar planetiler.jar --download --area=switzerland --output=switzerland.mbtiles`
4. Convert to PMTiles: `pmtiles convert switzerland.mbtiles switzerland.pmtiles`
5. Serve and view tiles

**What to Learn:**
- How to generate valid MBTiles output
- OpenMapTiles schema structure
- MBTiles → PMTiles conversion

### Task 6: MVT Inspection
**Objective:** Understand binary structure of vector tiles.

**Key Actions:**
1. Open `http://localhost:3000/tasks/06-mvt-inspect.html`
2. Click on map to select a tile coordinate
3. Click "Fetch & Inspect"
4. Explore decoded layers, keys, values
5. Understand tag/value deduplication

**What to Learn:**
- How to decode a tile and see its layers
- Key/value deduplication for efficiency
- Geometry encoding basics

### Task 7: TileJSON
**Objective:** Tile metadata and schema discovery.

**Key Actions:**
1. Open `http://localhost:3000/tasks/07-tilejson.html`
2. Select different TileJSON sources
3. Explore vector_layers array
4. Click layers to see field types
5. Generate style template for a layer

**What to Learn:**
- How to read TileJSON metadata
- The vector_layers structure
- Generating valid style layers from TileJSON

### Capstone
**Objective:** Complete end-to-end demonstration.

**Option A - PMTiles (if Task 5 completed):**
1. Open `http://localhost:3000/capstone/index.html`
2. Drag and drop generated `.pmtiles` file
3. Observe automatic layer styling

**Option B - GeoJSON (quick path):**
1. Open capstone page
2. Edit or paste custom GeoJSON
3. Click "Load GeoJSON on Map"
4. Verify data displays correctly

**What to Learn:**
- Loading custom data into MapLibre
- The complete data → render pipeline
- How different data formats are handled

## Troubleshooting

### Common Issues

**1. CORS errors when loading TileJSON**
```
Solution: Make sure http-server is running with --cors flag
```

**2. Tile fetch fails with 404**
```
Solution: Not all tile coordinates have data. Try a different Z/X/Y.
Demo tiles have limited coverage.
```

**3. Planetiler out of memory**
```
Solution: Increase heap size: java -Xmx4g -jar planetiler.jar ...
Or use a smaller OSM extract (e.g., Zurich canton only)
```

**4. PMTiles file not loading**
```
Solution: Ensure file was properly converted from MBTiles.
Check browser console for detailed error messages.
```

**5. Style changes not appearing**
```
Solution: MapLibre caches aggressively. Try hard refresh (Cmd+Shift+R)
or open in incognito window.
```

## Key Concepts Glossary

| Term | Definition |
|------|-----------|
| **MVT** | Mapbox Vector Tile - specification for vector tile structure |
| **PBF** | Protocol Buffer Format - binary encoding used by MVT |
| **PMTiles** | Cloud-optimized single-file format for vector/raster tiles |
| **TileJSON** | Metadata specification describing tilesets |
| **source-layer** | Named layer within a vector tile (e.g., "building", "road") |
| **Z/X/Y** | Tile coordinate system: zoom level, column, row |
| **extent** | Coordinate space within tile (typically 4096x4096) |
| **zigzag** | Encoding technique for efficient small signed integers |

## Learning Outcomes

After exploring the workshop, users should be able to:

- Explain the difference between raster and vector tiles
- Identify tile requests in browser DevTools
- Style vector data using MapLibre expressions
- Use Maputnik for visual style editing
- Describe how PMTiles enables serverless hosting
- Understand basic MVT structure (layers, features, properties)
- Read TileJSON to discover available data
- Generate vector tiles from OSM data (optional)
- Load custom GeoJSON/PMTiles into MapLibre

## Resources

- [MapLibre GL JS Docs](https://maplibre.org/maplibre-gl-js/docs/)
- [MapLibre Style Specification](https://maplibre.org/maplibre-style-spec/)
- [PMTiles Documentation](https://protomaps.com/docs/pmtiles)
- [Planetiler GitHub](https://github.com/onthegomap/planetiler)
- [Maputnik Editor](https://maputnik.github.io/)
- [TileJSON Specification](https://github.com/mapbox/tilejson-spec)
- [OpenMapTiles Schema](https://openmaptiles.org/schema/)

## Extending the Workshop

To add new exercises:

1. Create new HTML file in `tasks/` directory
2. Follow the existing template structure:
   - Sidebar with instructions
   - Map or interactive panel
   - Console logging for education
   - Navigation links to prev/next tasks
3. Update `index.html` task grid
4. Update this agent document with new task guide
