# Data Sources

## Buildings

### Stadt Zürich 3D-Blockmodell LoD1

**Source:** [data.stadt-zuerich.ch](https://data.stadt-zuerich.ch/dataset/geo_3d_blockmodell_lod1)

**Details:**
| Property | Value |
|----------|-------|
| Format | OBJ (Wavefront) |
| CRS | EPSG:2056 (Swiss LV95) |
| Count | ~50,000 buildings |
| LoD | Level of Detail 1 (block model) |
| License | CC0 (Public Domain) |

**API Endpoint:**
```
https://data.stadt-zuerich.ch/api/3/action/package_show?id=geo_3d_blockmodell_lod1
```

**Properties Available:**
- Building footprint (polygon)
- Building height (meters)
- Base elevation (meters above sea level)

### Processing Pipeline

```
OBJ Files (LV95)
      │
      ▼
[obj-to-geojson.py]
      │
      ▼
GeoJSON (LV95)
      │
      ▼
[transform-coords.py]
      │
      ▼
GeoJSON (WGS84)
      │
      ▼
[tile-buildings.py]
      │
      ▼
Final GeoJSON / Tiles
```

---

## Terrain

### swissALTI3D

**Source:** [swisstopo](https://www.swisstopo.admin.ch/en/height-model-swissalti3d)

**Details:**
| Property | Value |
|----------|-------|
| Format | GeoTIFF |
| CRS | EPSG:2056 (Swiss LV95) |
| Resolution | 0.5m |
| Vertical Accuracy | ±0.3-3m |
| License | Open Government Data |

**Coverage:**
- Full Switzerland
- For Zurich: Tiles in the 2680-2690 (E) x 1245-1255 (N) range

### Terrain RGB Encoding

For web use, terrain can be encoded as RGB images:

```
elevation = -10000 + ((R * 256 * 256 + G * 256 + B) * 0.1)
```

This allows loading elevation as standard PNG images.

---

## Coordinate Reference Systems

### Swiss LV95 (EPSG:2056)

**Parameters:**
```
+proj=somerc
+lat_0=46.95240555555556
+lon_0=7.439583333333333
+k_0=1
+x_0=2600000
+y_0=1200000
+ellps=bessel
+towgs84=674.374,15.056,405.346,0,0,0,0
+units=m
+no_defs
```

**Zurich Center:**
- E: 2,683,000
- N: 1,248,000

### WGS84 (EPSG:4326)

**Zurich Center:**
- Longitude: 8.541694°
- Latitude: 47.376888°

### Conversion

Using pyproj:
```python
from pyproj import Transformer

transformer = Transformer.from_crs(
    "EPSG:2056",
    "EPSG:4326",
    always_xy=True
)

lng, lat = transformer.transform(e, n)
```

Approximate linear conversion (for Zurich area):
```javascript
const metersPerDegreeLng = 75500; // at 47°N
const metersPerDegreeLat = 111320;

const lng = ZURICH_CENTER.lng + (e - 2683000) / metersPerDegreeLng;
const lat = ZURICH_CENTER.lat + (n - 1248000) / metersPerDegreeLat;
```

---

## Zurich Bounding Box

### WGS84
```javascript
const ZURICH_BOUNDS = {
  minLng: 8.448,
  maxLng: 8.626,
  minLat: 47.320,
  maxLat: 47.435,
};
```

### LV95
```javascript
const ZURICH_BOUNDS_LV95 = {
  minE: 2676000,
  maxE: 2690000,
  minN: 1241000,
  maxN: 1255000,
};
```

---

## Sample Data

For development without downloading full datasets:

```bash
# Create sample buildings (500 random rectangles)
python scripts/convert/obj-to-geojson.py --sample --sample-count 500 -o data/processed/buildings-lv95.geojson

# Transform to WGS84
python scripts/convert/transform-coords.py data/processed/buildings-lv95.geojson

# Create final file
python scripts/convert/tile-buildings.py data/processed/buildings-wgs84.geojson --single -o public/data/zurich-buildings.geojson
```

Or run the full pipeline:
```bash
python scripts/run-pipeline.py
```

---

## Data Validation

Check data integrity:
```bash
python scripts/validate/check-data.py public/data/zurich-buildings.geojson
```

Expected output:
```
Found 500 features in public/data/zurich-buildings.geojson
Validating all 500 features...
✓ public/data/zurich-buildings.geojson - Valid
```

---

## Transit Data

### GTFS from opentransportdata.swiss

**Source:** [opentransportdata.swiss](https://opentransportdata.swiss/)

**Details:**
| Property | Value |
|----------|-------|
| Format | GTFS |
| Coverage | ZVV (Zurich transport) |
| Routes | 365 (trams, buses, rail, funicular) |
| License | Open |

**Processed File:** `public/data/zurich-tram-trips.json`

Contains 29,346 trips with paths and timestamps for real-time visualization.

---

## Amenities

### Benches, Fountains, Toilets

**Source:** [data.stadt-zuerich.ch](https://data.stadt-zuerich.ch/)

| Dataset | File | Count |
|---------|------|-------|
| Benches | `zurich-benches.geojson` | ~7,267 |
| Fountains | `zurich-fountains.geojson` | ~1,288 |
| Toilets | `zurich-toilets.geojson` | ~25 |
| Trees | `zurich-trees.geojson` | ~80,484 |

---

## Route-Building Spatial Index

### Preprocessed Index

**File:** `public/data/route-building-index.json`

**Size:** ~4 MB

A spatial index mapping transit routes to nearby features within 50m buffer:

| Feature | Indexed Count |
|---------|---------------|
| Buildings | 29,162 (of 65,677) |
| Benches | 2,793 (of 7,267) |
| Fountains | 522 (of 1,288) |
| Toilets | 16 (of 25) |

### Rebuilding the Index

```bash
# Rebuild after data changes
python -m scripts.preprocess.build_route_building_index -v

# Dry run to preview
python -m scripts.preprocess.build_route_building_index --dry-run -v
```

### Query Examples

```bash
# Which tram passes the most benches?
python -m scripts.tile_pipeline.cli route-buildings -l --type tram --sort-by benches

# How many buildings does Tram 11 pass?
python -m scripts.tile_pipeline.cli route-buildings -r 11

# Compare routes
python -m scripts.tile_pipeline.cli compare-routes 4 11 15
```
