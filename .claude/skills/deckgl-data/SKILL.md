---
name: deckgl-data
description: Create data loaders and transformers for GeoJSON, OBJ, or binary data. Use when adding new data sources.
allowed-tools: Read, Write, Edit, Bash, Glob
---

# deck.gl Data Skill

Creates data loaders with proper coordinate transformation and validation.

## Prerequisites

- [ ] Data source URL or file path known
- [ ] Data format identified (GeoJSON, OBJ, GeoTIFF)
- [ ] Source coordinate system known (e.g., EPSG:2056 for Swiss data)
- [ ] `src/lib/data/` directory exists

## Workflow

### Step 1: Identify Data Source
- [ ] Document source URL
- [ ] Note coordinate reference system (CRS)
- [ ] Identify required transformations

### Step 2: Create Loader
- [ ] Create `src/lib/data/{dataName}.ts`
- [ ] Implement fetch/load function
- [ ] Add progress callback support
- [ ] Handle errors gracefully

### Step 3: Create Transformer (if needed)
- [ ] Coordinate transformation (LV95 -> WGS84)
- [ ] Property extraction/normalization
- [ ] Filtering/validation

### Step 4: Create React Hook
- [ ] Create `src/hooks/use{DataName}.ts`
- [ ] Manage loading state
- [ ] Cache data in state
- [ ] Handle errors

### Step 5: Test
- [ ] Write unit tests for transformations
- [ ] Test with sample data
- [ ] Verify coordinates are correct

### Step 6: Verify
- [ ] Run `pnpm type-check`
- [ ] Run `pnpm test`

## Coordinate Transformation

### Swiss LV95 (EPSG:2056) to WGS84 (EPSG:4326)

```typescript
// Approximate transformation (for Zurich area)
// For production, use proj4 library

const ZURICH_REFERENCE = {
  lv95: { e: 2683000, n: 1248000 },
  wgs84: { lng: 8.541694, lat: 47.376888 },
};

export function lv95ToWgs84(e: number, n: number): [number, number] {
  // Simplified linear approximation for Zurich area
  // Good for ~10km radius, ±1m accuracy
  const dE = e - ZURICH_REFERENCE.lv95.e;
  const dN = n - ZURICH_REFERENCE.lv95.n;

  const lng = ZURICH_REFERENCE.wgs84.lng + dE / 73000;
  const lat = ZURICH_REFERENCE.wgs84.lat + dN / 111000;

  return [lng, lat];
}
```

### Using proj4 (Accurate)

```typescript
import proj4 from 'proj4';

// Define Swiss LV95
proj4.defs('EPSG:2056', '+proj=somerc +lat_0=46.95240555555556 +lon_0=7.439583333333333 +k_0=1 +x_0=2600000 +y_0=1200000 +ellps=bessel +towgs84=674.374,15.056,405.346,0,0,0,0 +units=m +no_defs');

export function lv95ToWgs84Accurate(e: number, n: number): [number, number] {
  const [lng, lat] = proj4('EPSG:2056', 'EPSG:4326', [e, n]);
  return [lng, lat];
}
```

## Templates

- `loader.template.ts` - Base loader with progress
- `transformer.template.ts` - Coordinate transformation
- `use-data.template.ts` - React hook pattern

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| CORS errors | Server doesn't allow cross-origin | Use local file or proxy |
| Coordinates reversed | lat/lng vs lng/lat confusion | Check source format, GeoJSON is [lng, lat] |
| Memory issues | Large file | Use streaming/chunked loading |
| Type errors | Wrong GeoJSON structure | Validate with JSON schema |

## Recovery

1. Delete loader file
2. Remove hook file
3. Clear any cached data
4. Re-run from Step 1
