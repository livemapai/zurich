# MapLibre Pipeline Workshop

A hands-on workshop teaching the **complete journey** from raw vector data to rendered tiles in a browser.

## Learning Goal

> "I can take any vector data and turn it into map tiles that display in a browser."

## The Pipeline

```
Raw GeoJSON → Tile Generation → MVT Encoding → HTTP/CDN → MapLibre → Pixels!
```

## Quick Start

```bash
# Navigate to workshop directory
cd rendering-workshop

# Serve locally (pick one)
npx http-server . -p 3000 --cors
# or
python -m http.server 3000

# Open in browser
open http://localhost:3000
```

## Workshop Tasks

| Task | Title | What You'll Learn |
|------|-------|-------------------|
| **1** | [Raster Tiles](tasks/01-raster-tiles.html) | How web maps load pre-rendered images |
| **2** | [Vector Tiles](tasks/02-vector-tiles.html) | Client-side rendering from geometry data |
| **3** | [Maputnik](tasks/03-maputnik/instructions.html) | Visual style editing |
| **4** | [PMTiles](tasks/04-pmtiles.html) | Serverless tile hosting |
| **5** | [Planetiler](tasks/05-planetiler/instructions.html) | Generate tiles from OSM |
| **6** | [MVT Inspection](tasks/06-mvt-inspect.html) | Protobuf binary structure |
| **7** | [TileJSON](tasks/07-tilejson.html) | Tile metadata and schema |
| **★** | [Capstone](capstone/index.html) | Full end-to-end pipeline |

## Prerequisites

- Modern browser with DevTools (Chrome, Firefox, Safari)
- Node.js 18+ (for `npx http-server`)
- Java 21+ (only for Task 5: Planetiler)

## File Structure

```
rendering-workshop/
├── index.html                    # Workshop home page
├── README.md                     # This file
├── tasks/
│   ├── 01-raster-tiles.html      # Task 1: Basic raster map
│   ├── 02-vector-tiles.html      # Task 2: Add vector source
│   ├── 03-maputnik/
│   │   └── instructions.html     # Task 3: Maputnik guide
│   ├── 04-pmtiles.html           # Task 4: PMTiles loading
│   ├── 05-planetiler/
│   │   └── instructions.html     # Task 5: Tile generation
│   ├── 06-mvt-inspect.html       # Task 6: MVT inspection
│   └── 07-tilejson.html          # Task 7: TileJSON exploration
└── capstone/
    └── index.html                # End-to-end exercise
```

## Pipeline Stage Mapping

| Pipeline Stage | Workshop Tasks |
|---------------|----------------|
| Data Sources | Tasks 1, 2 |
| Tile Generation | Task 5 |
| MVT Encoding | Task 6 |
| Schema/Layers | Task 7 |
| Style Spec | Tasks 2, 3 |
| WebGL Render | (See Pipeline Viewer) |

## Key Concepts

### Z/X/Y Tile Coordinates

```javascript
// Convert lat/lng to tile coordinates
function latLngToTile(lat, lng, zoom) {
  const n = Math.pow(2, zoom);
  const x = Math.floor(((lng + 180) / 360) * n);
  const latRad = (lat * Math.PI) / 180;
  const y = Math.floor(((1 - Math.asinh(Math.tan(latRad)) / Math.PI) / 2) * n);
  return { z: zoom, x, y };
}
```

### Vector Tile Structure

```
Tile {
  layers: [
    Layer {
      name: "building"
      keys: ["height", "type"]
      values: [25, "residential"]
      features: [Feature { id, tags, geometry }]
    }
  ]
}
```

### TileJSON Metadata

```json
{
  "tilejson": "3.0.0",
  "tiles": ["https://.../{z}/{x}/{y}.pbf"],
  "vector_layers": [
    { "id": "building", "fields": { "height": "Number" } }
  ]
}
```

## Resources

- [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/)
- [MapLibre Style Specification](https://maplibre.org/maplibre-style-spec/)
- [PMTiles](https://protomaps.com/docs/pmtiles)
- [Planetiler](https://github.com/onthegomap/planetiler)
- [Maputnik](https://maputnik.github.io/)
- [TileJSON Spec](https://github.com/mapbox/tilejson-spec)

## Related

- **[Pipeline Explorer](/pipeline)**: Interactive visualization of how MapLibre works internally
- **[Zurich 3D Walkthrough](/)**: The main project using these techniques

---

## Capstone: End-to-End in 10 Minutes

After completing all tasks, test your knowledge:

```bash
# 1. Create a GeoJSON file
echo '{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature",
    "properties": { "name": "My Building" },
    "geometry": {
      "type": "Polygon",
      "coordinates": [[[8.54, 47.37], [8.545, 47.37], [8.545, 47.375], [8.54, 47.375], [8.54, 47.37]]]
    }
  }]
}' > my-data.geojson

# 2. Generate tiles (using tippecanoe)
tippecanoe -o my-tiles.mbtiles -z16 -Z10 my-data.geojson

# 3. Convert to PMTiles
pmtiles convert my-tiles.mbtiles my-tiles.pmtiles

# 4. Serve and display!
npx http-server . -p 3000 --cors
```

Then open `capstone/index.html` and load your `my-tiles.pmtiles` file.

**Success!** You've completed the full pipeline: GeoJSON → Tiles → Browser.
