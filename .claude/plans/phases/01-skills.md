# Phase 1: Claude Code Skills

## Context
This phase creates specialized Claude Code skills for deck.gl development. These skills provide reusable workflows, templates, and reference documentation that accelerate development in subsequent phases.

## Prerequisites
- Phase 0 completed
- `package.json` and `tsconfig.json` exist
- `pnpm install` completed successfully

## Tasks

### Task 1.1: Create deckgl-layer Skill
**Goal:** Create a skill for scaffolding deck.gl layers with proper TypeScript types.

**Create directory structure:**
```
.claude/skills/deckgl-layer/
├── SKILL.md
├── reference/
│   ├── polygon-layer.md
│   ├── terrain-layer.md
│   └── scatterplot-layer.md
└── templates/
    ├── layer-factory.template.ts
    ├── layer-component.template.tsx
    └── layer-types.template.ts
```

**Create file:** `.claude/skills/deckgl-layer/SKILL.md`
```markdown
---
name: deckgl-layer
description: Scaffold a new deck.gl layer with factory function and React component. Use when adding buildings, terrain, points, or paths.
allowed-tools: Read, Write, Edit, Glob, Grep
---

# deck.gl Layer Skill

Creates deck.gl layers following the project's established patterns with proper TypeScript types and factory functions.

## Prerequisites

Before using this skill, verify:
- [ ] `src/types/index.ts` exists with core types
- [ ] deck.gl dependencies installed (`pnpm list deck.gl`)
- [ ] Layer directory exists: `src/layers/`

## Workflow

### Step 1: Gather Requirements
Ask the user or determine:
- [ ] Layer name (e.g., "Buildings", "Terrain", "Points")
- [ ] Layer type (PolygonLayer, TerrainLayer, ScatterplotLayer, etc.)
- [ ] Data format (GeoJSON, binary, etc.)
- [ ] Required properties from data

### Step 2: Read Reference Documentation
- [ ] Read `reference/polygon-layer.md` (or relevant type)
- [ ] Note required props and their types
- [ ] Check deck.gl v9 API for any changes

### Step 3: Create Type Definitions
- [ ] Create `src/layers/{LayerName}Layer.types.ts`
- [ ] Define data shape interface
- [ ] Define layer config interface
- [ ] Export all types

### Step 4: Create Layer Factory
- [ ] Create `src/layers/{LayerName}Layer.ts`
- [ ] Import deck.gl layer class
- [ ] Create factory function with typed config
- [ ] Add JSDoc documentation
- [ ] Export factory function

### Step 5: Create React Component (Optional)
- [ ] Create `src/components/layers/{LayerName}Layer.tsx`
- [ ] Use factory function internally
- [ ] Add props for visibility, data source
- [ ] Handle loading states

### Step 6: Export from Index
- [ ] Add export to `src/layers/index.ts`
- [ ] Add component export to `src/components/layers/index.ts`

### Step 7: Verify
- [ ] Run `pnpm type-check`
- [ ] Confirm no type errors
- [ ] Check imports resolve correctly

## Reference Files

See `reference/` directory for:
- `polygon-layer.md` - For buildings, areas, regions
- `terrain-layer.md` - For elevation/terrain
- `scatterplot-layer.md` - For point data

## Templates

Use templates from `templates/` directory:
- `layer-factory.template.ts` - Base factory pattern
- `layer-component.template.tsx` - React wrapper
- `layer-types.template.ts` - Type definitions

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Cannot find module deck.gl" | Missing dependency | Run `pnpm install` |
| Type mismatch on data | Wrong data shape | Check GeoJSON structure matches interface |
| Layer not rendering | Data is empty/null | Add null checks, log data in console |
| WebGL errors | Invalid props | Check prop values (opacity 0-1, colors 0-255) |
| "accessor" errors in v9 | API changed | Use direct property access, not function accessors |

## Recovery

If this skill fails partway through:
1. Delete any partially created files in `src/layers/`
2. Remove exports added to index files
3. Run `pnpm type-check` to identify broken imports
4. Re-run skill from Step 1

## External References

- [deck.gl Layer Docs](https://deck.gl/docs/api-reference/layers)
- [SolidPolygonLayer](https://deck.gl/docs/api-reference/layers/solid-polygon-layer)
- [TerrainLayer](https://deck.gl/docs/api-reference/geo-layers/terrain-layer)
```

**Create file:** `.claude/skills/deckgl-layer/reference/polygon-layer.md`
```markdown
# PolygonLayer / SolidPolygonLayer Reference

## When to Use
- Building footprints with extrusion
- Area boundaries
- Regions/zones

## deck.gl v9 API

### Import
```typescript
import { SolidPolygonLayer } from '@deck.gl/layers';
```

### Required Props
```typescript
interface SolidPolygonLayerProps<DataT> {
  id: string;
  data: DataT[];

  // Geometry accessor
  getPolygon: (d: DataT) => Position[][] | Position[][][];

  // Appearance
  getFillColor?: (d: DataT) => Color;
  getLineColor?: (d: DataT) => Color;

  // Extrusion
  extruded?: boolean;
  getElevation?: (d: DataT) => number;
  elevationScale?: number;

  // Material
  material?: Material | boolean;
}
```

### For Buildings (Best Practice)
```typescript
import { SolidPolygonLayer } from '@deck.gl/layers';
import type { BuildingFeature } from '@/types';

export function createBuildingsLayer(
  data: BuildingFeature[],
  config: { visible?: boolean; opacity?: number } = {}
) {
  return new SolidPolygonLayer<BuildingFeature>({
    id: 'buildings',
    data,

    // Geometry
    getPolygon: (d) => d.geometry.coordinates[0] as Position[][],

    // Extrusion
    extruded: true,
    getElevation: (d) => d.properties.height,
    elevationScale: 1,

    // Appearance
    getFillColor: [200, 200, 220, 255],
    getLineColor: [100, 100, 120, 255],

    // Performance
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 200, 0, 128],

    // Visibility
    visible: config.visible ?? true,
    opacity: config.opacity ?? 1,

    // Material for 3D lighting
    material: {
      ambient: 0.35,
      diffuse: 0.6,
      shininess: 32,
      specularColor: [60, 64, 70],
    },
  });
}
```

### Type Definition Pattern
```typescript
// src/layers/BuildingsLayer.types.ts
export interface BuildingsLayerConfig {
  visible?: boolean;
  opacity?: number;
  extruded?: boolean;
  wireframe?: boolean;
}
```

## Common Issues

1. **Coordinates wrong order**: GeoJSON is [lng, lat], deck.gl expects this
2. **Holes in polygons**: Use Position[][] for outer ring, Position[][][] for with holes
3. **Elevation baseline**: Set `elevationScale` if heights are in different units
```

**Create file:** `.claude/skills/deckgl-layer/reference/terrain-layer.md`
```markdown
# TerrainLayer Reference

## When to Use
- Terrain/elevation visualization
- Height maps
- DEM data

## deck.gl v9 API

### Import
```typescript
import { TerrainLayer } from '@deck.gl/geo-layers';
```

### Required Props
```typescript
interface TerrainLayerProps {
  id: string;

  // Tile source
  elevationData: string | TileLoadProps;
  texture?: string;

  // Bounds (WGS84)
  bounds?: [number, number, number, number]; // [west, south, east, north]

  // Mesh quality
  meshMaxError?: number; // Default 4, lower = more detail

  // Elevation
  elevationDecoder?: {
    rScaler: number;
    gScaler: number;
    bScaler: number;
    offset: number;
  };
  elevationScale?: number;
}
```

### For Terrain RGB (Mapbox style)
```typescript
import { TerrainLayer } from '@deck.gl/geo-layers';

export function createTerrainLayer(config: {
  elevationUrl: string;
  textureUrl?: string;
  bounds: [number, number, number, number];
  visible?: boolean;
}) {
  return new TerrainLayer({
    id: 'terrain',

    // Data sources
    elevationData: config.elevationUrl,
    texture: config.textureUrl,

    // Bounds
    bounds: config.bounds,

    // Mesh quality (lower = more triangles)
    meshMaxError: 2,

    // RGB elevation decoder (Mapbox terrain-rgb format)
    // elevation = -10000 + ((R * 256 * 256 + G * 256 + B) * 0.1)
    elevationDecoder: {
      rScaler: 6553.6,
      gScaler: 25.6,
      bScaler: 0.1,
      offset: -10000,
    },

    // Scale
    elevationScale: 1,

    // Appearance
    visible: config.visible ?? true,

    // Material
    material: {
      ambient: 0.4,
      diffuse: 0.6,
      shininess: 20,
    },
  });
}
```

### For swissALTI3D (Custom Format)
```typescript
// Swiss elevation tiles use different encoding
// Consult swisstopo documentation for exact decoder values
export const SWISS_ELEVATION_DECODER = {
  rScaler: 256 * 256 * 0.01,
  gScaler: 256 * 0.01,
  bScaler: 0.01,
  offset: 0,
};
```

## Common Issues

1. **Seams between tiles**: Set `meshMaxError` consistently
2. **Elevation scale wrong**: Check source data units (meters vs feet)
3. **Texture misalignment**: Ensure bounds match exactly
```

**Create file:** `.claude/skills/deckgl-layer/reference/scatterplot-layer.md`
```markdown
# ScatterplotLayer Reference

## When to Use
- Point data (POIs, markers)
- Location pins
- Data points

## deck.gl v9 API

### Import
```typescript
import { ScatterplotLayer } from '@deck.gl/layers';
```

### Example
```typescript
import { ScatterplotLayer } from '@deck.gl/layers';

interface PointData {
  position: [number, number]; // [lng, lat]
  radius: number;
  color: [number, number, number, number];
}

export function createPointsLayer(data: PointData[]) {
  return new ScatterplotLayer<PointData>({
    id: 'points',
    data,

    getPosition: (d) => d.position,
    getRadius: (d) => d.radius,
    getFillColor: (d) => d.color,

    pickable: true,
    radiusScale: 1,
    radiusMinPixels: 2,
    radiusMaxPixels: 100,
  });
}
```
```

**Create file:** `.claude/skills/deckgl-layer/templates/layer-factory.template.ts`
```typescript
/**
 * {LayerName}Layer - {description}
 *
 * @module layers/{LayerName}Layer
 */

import { {DeckGLLayerClass} } from '{deckgl-import-path}';
import type { {DataType} } from '@/types';

export interface {LayerName}LayerConfig {
  visible?: boolean;
  opacity?: number;
  pickable?: boolean;
  // Add layer-specific config options
}

const DEFAULT_CONFIG: Required<{LayerName}LayerConfig> = {
  visible: true,
  opacity: 1,
  pickable: true,
};

/**
 * Creates a {LayerName} layer for deck.gl
 *
 * @param data - Array of {DataType} features
 * @param config - Layer configuration options
 * @returns Configured {DeckGLLayerClass} instance
 */
export function create{LayerName}Layer(
  data: {DataType}[],
  config: {LayerName}LayerConfig = {}
): {DeckGLLayerClass}<{DataType}> {
  const mergedConfig = { ...DEFAULT_CONFIG, ...config };

  return new {DeckGLLayerClass}<{DataType}>({
    id: '{layer-id}',
    data,

    // Geometry accessor
    // getPolygon: (d) => d.geometry.coordinates,
    // getPosition: (d) => d.position,

    // Appearance
    // getFillColor: [200, 200, 220, 255],

    // Config
    visible: mergedConfig.visible,
    opacity: mergedConfig.opacity,
    pickable: mergedConfig.pickable,
  });
}
```

**Create file:** `.claude/skills/deckgl-layer/templates/layer-component.template.tsx`
```typescript
/**
 * {LayerName}Layer React Component
 */

import { useMemo } from 'react';
import { create{LayerName}Layer, type {LayerName}LayerConfig } from '@/layers/{LayerName}Layer';
import type { {DataType} } from '@/types';

interface {LayerName}LayerProps extends {LayerName}LayerConfig {
  data: {DataType}[] | null;
}

export function {LayerName}Layer({ data, ...config }: {LayerName}LayerProps) {
  const layer = useMemo(() => {
    if (!data || data.length === 0) return null;
    return create{LayerName}Layer(data, config);
  }, [data, config.visible, config.opacity, config.pickable]);

  return layer;
}
```

**Create file:** `.claude/skills/deckgl-layer/templates/layer-types.template.ts`
```typescript
/**
 * Type definitions for {LayerName}Layer
 */

export interface {LayerName}Properties {
  id: string;
  // Add feature-specific properties
}

export interface {LayerName}Feature {
  type: 'Feature';
  geometry: {
    type: '{GeometryType}'; // 'Polygon' | 'Point' | 'LineString'
    coordinates: {CoordinateType}; // number[][] | number[] | number[][][]
  };
  properties: {LayerName}Properties;
}

export interface {LayerName}LayerConfig {
  visible?: boolean;
  opacity?: number;
  pickable?: boolean;
}
```

---

### Task 1.2: Create deckgl-data Skill
**Goal:** Create a skill for data loading and transformation.

**Create directory structure:**
```
.claude/skills/deckgl-data/
├── SKILL.md
├── reference/
│   └── geojson-loader.md
└── templates/
    ├── loader.template.ts
    ├── transformer.template.ts
    └── use-data.template.ts
```

**Create file:** `.claude/skills/deckgl-data/SKILL.md`
```markdown
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
- [ ] Coordinate transformation (LV95 → WGS84)
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
```

**Create file:** `.claude/skills/deckgl-data/reference/geojson-loader.md`
```markdown
# GeoJSON Loader Reference

## Standard Loading

```typescript
export async function loadGeoJSON<T extends GeoJSON.FeatureCollection>(
  url: string,
  options?: {
    onProgress?: (progress: number) => void;
  }
): Promise<T> {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to load GeoJSON: ${response.statusText}`);
  }

  const data = await response.json();

  // Validate structure
  if (data.type !== 'FeatureCollection') {
    throw new Error('Expected GeoJSON FeatureCollection');
  }

  return data as T;
}
```

## With Progress Tracking

```typescript
export async function loadGeoJSONWithProgress<T>(
  url: string,
  onProgress?: (progress: number) => void
): Promise<T> {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const contentLength = response.headers.get('Content-Length');
  const total = contentLength ? parseInt(contentLength, 10) : 0;

  if (!response.body) {
    return response.json();
  }

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let received = 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    chunks.push(value);
    received += value.length;

    if (total && onProgress) {
      onProgress((received / total) * 100);
    }
  }

  const text = new TextDecoder().decode(
    new Uint8Array(chunks.flatMap((c) => [...c]))
  );

  return JSON.parse(text) as T;
}
```

## React Hook Pattern

```typescript
import { useState, useEffect } from 'react';
import type { LoadingState } from '@/types';

export function useGeoJSONData<T>(url: string | null): LoadingState<T> {
  const [state, setState] = useState<LoadingState<T>>({
    data: null,
    isLoading: false,
    error: null,
    progress: 0,
  });

  useEffect(() => {
    if (!url) return;

    const controller = new AbortController();

    setState((s) => ({ ...s, isLoading: true, error: null, progress: 0 }));

    loadGeoJSONWithProgress<T>(url, (progress) => {
      setState((s) => ({ ...s, progress }));
    })
      .then((data) => {
        if (!controller.signal.aborted) {
          setState({ data, isLoading: false, error: null, progress: 100 });
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setState((s) => ({ ...s, isLoading: false, error, progress: 0 }));
        }
      });

    return () => controller.abort();
  }, [url]);

  return state;
}
```
```

**Create file:** `.claude/skills/deckgl-data/templates/loader.template.ts`
```typescript
/**
 * {DataName} Data Loader
 *
 * Loads {description} from {source}
 */

import type { {DataType} } from '@/types';

export interface {DataName}LoadOptions {
  onProgress?: (progress: number) => void;
  signal?: AbortSignal;
}

/**
 * Load {DataName} data from URL
 */
export async function load{DataName}(
  url: string,
  options: {DataName}LoadOptions = {}
): Promise<{DataType}> {
  const { onProgress, signal } = options;

  const response = await fetch(url, { signal });

  if (!response.ok) {
    throw new Error(`Failed to load {DataName}: ${response.statusText}`);
  }

  // TODO: Add progress tracking if Content-Length available
  if (onProgress) {
    onProgress(50);
  }

  const data = await response.json();

  // TODO: Add validation

  if (onProgress) {
    onProgress(100);
  }

  return data as {DataType};
}
```

**Create file:** `.claude/skills/deckgl-data/templates/transformer.template.ts`
```typescript
/**
 * {DataName} Coordinate Transformer
 *
 * Transforms coordinates from {sourceCRS} to {targetCRS}
 */

import type { {InputType}, {OutputType} } from '@/types';

/**
 * Transform a single coordinate
 */
export function transform{DataName}Coordinate(
  input: [number, number]
): [number, number] {
  // TODO: Implement transformation
  // Example: LV95 to WGS84
  const [e, n] = input;

  // Reference point for Zurich
  const ref = {
    lv95: { e: 2683000, n: 1248000 },
    wgs84: { lng: 8.541694, lat: 47.376888 },
  };

  const lng = ref.wgs84.lng + (e - ref.lv95.e) / 73000;
  const lat = ref.wgs84.lat + (n - ref.lv95.n) / 111000;

  return [lng, lat];
}

/**
 * Transform all coordinates in a feature collection
 */
export function transform{DataName}Features(
  input: {InputType}
): {OutputType} {
  // TODO: Implement feature transformation
  return input as unknown as {OutputType};
}
```

**Create file:** `.claude/skills/deckgl-data/templates/use-data.template.ts`
```typescript
/**
 * use{DataName} Hook
 *
 * Loads and caches {DataName} data with loading state management
 */

import { useState, useEffect } from 'react';
import { load{DataName} } from '@/lib/data/{dataName}';
import type { {DataType}, LoadingState } from '@/types';

export function use{DataName}(url: string | null): LoadingState<{DataType}> {
  const [state, setState] = useState<LoadingState<{DataType}>>({
    data: null,
    isLoading: false,
    error: null,
    progress: 0,
  });

  useEffect(() => {
    if (!url) {
      setState({ data: null, isLoading: false, error: null, progress: 0 });
      return;
    }

    const controller = new AbortController();

    setState((prev) => ({ ...prev, isLoading: true, error: null, progress: 0 }));

    load{DataName}(url, {
      onProgress: (progress) => {
        setState((prev) => ({ ...prev, progress }));
      },
      signal: controller.signal,
    })
      .then((data) => {
        if (!controller.signal.aborted) {
          setState({ data, isLoading: false, error: null, progress: 100 });
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted && error.name !== 'AbortError') {
          setState((prev) => ({
            ...prev,
            isLoading: false,
            error: error instanceof Error ? error : new Error(String(error)),
            progress: 0,
          }));
        }
      });

    return () => controller.abort();
  }, [url]);

  return state;
}
```

---

### Task 1.3: Create deckgl-firstperson Skill
**Goal:** Create the most comprehensive skill for first-person navigation with WASD controls, collision detection, and terrain following.

**Create directory structure:**
```
.claude/skills/deckgl-firstperson/
├── SKILL.md
├── reference/
│   ├── first-person-view.md
│   ├── game-loop.md
│   ├── collision-system.md
│   └── pointer-lock.md
├── templates/
│   ├── use-keyboard-state.template.ts
│   ├── use-mouse-look.template.ts
│   ├── use-game-loop.template.ts
│   ├── movement-controller.template.ts
│   ├── spatial-index.template.ts
│   └── camera-controller.template.ts
└── workflows/
    ├── add-wasd-controls.md
    ├── add-collision.md
    └── add-terrain-following.md
```

**Create file:** `.claude/skills/deckgl-firstperson/SKILL.md`
```markdown
---
name: deckgl-firstperson
description: Implement first-person navigation with WASD controls, mouse look, collision detection, and terrain following. Use when building walkthrough experiences.
allowed-tools: Read, Write, Edit, Glob, Grep
---

# deck.gl First-Person Navigation Skill

Implements complete first-person walkthrough controls for deck.gl applications.

## Features

- **WASD Movement:** Keyboard-based walking/running
- **Mouse Look:** Pointer lock for camera control
- **Collision Detection:** RBush spatial indexing for buildings
- **Terrain Following:** Ground-locked altitude with smooth transitions

## Prerequisites

- [ ] deck.gl v9 installed
- [ ] React 19 setup complete
- [ ] `src/types/index.ts` with FirstPersonViewState type
- [ ] rbush installed (`pnpm list rbush`)

## Core Concepts

### FirstPersonView Coordinate System

deck.gl's FirstPersonView uses:
```typescript
interface FirstPersonViewState {
  position: [lng, lat, altitude]; // WGS84 + meters
  bearing: number;  // 0=North, 90=East, 180=South, 270=West
  pitch: number;    // -90=down, 0=level, 90=up
}
```

### Movement Calculation

Movement is calculated in meters, then converted to degrees:
```typescript
// Bearing-relative movement
const dx = Math.sin(bearing * DEG_TO_RAD) * velocity.forward;
const dy = Math.cos(bearing * DEG_TO_RAD) * velocity.forward;

// Convert meters to degrees (at Zurich latitude)
const dLng = dx / 73000;  // meters per degree longitude
const dLat = dy / 111000; // meters per degree latitude
```

## Workflow

### Full Implementation (All Features)

1. [ ] Create `useKeyboardState` hook
2. [ ] Create `useMouseLook` hook
3. [ ] Create `useGameLoop` hook
4. [ ] Create `MovementController` system
5. [ ] Create `CameraController` system
6. [ ] Create `SpatialIndex` for collision
7. [ ] Create `useCollisionDetection` hook
8. [ ] Create `useTerrainElevation` hook
9. [ ] Integrate in main component
10. [ ] Verify with type-check

### Partial Implementation (Sub-workflows)

See `workflows/` directory:
- `add-wasd-controls.md` - Just movement, no collision
- `add-collision.md` - Add collision to existing movement
- `add-terrain-following.md` - Add terrain to existing system

## Reference Files

- `reference/first-person-view.md` - deck.gl FPV specifics
- `reference/game-loop.md` - RAF timing patterns
- `reference/collision-system.md` - RBush + wall sliding
- `reference/pointer-lock.md` - Browser Pointer Lock API

## Templates

All templates are complete implementations ready to copy:
- `use-keyboard-state.template.ts`
- `use-mouse-look.template.ts`
- `use-game-loop.template.ts`
- `movement-controller.template.ts`
- `spatial-index.template.ts`
- `camera-controller.template.ts`

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Camera moves wrong direction | Bearing convention wrong | Check: 0=North, increases clockwise |
| Movement too fast/slow | Delta time not in seconds | Ensure deltaTime is seconds, not ms |
| Pointer lock fails | Not in click handler | Must request from user gesture |
| Collision not detecting | RBush not populated | Call `load()` before checking |
| Jittery movement | Float precision | Use doubles, reduce calculation frequency |
| Falls through terrain | Terrain not loaded | Add loading check before movement |

## Recovery

If partial implementation breaks:
1. Remove all new hooks from `src/hooks/`
2. Remove all new systems from `src/systems/`
3. Revert changes to main component
4. Run `pnpm type-check`
5. Re-run skill from start

## External References

- [deck.gl FirstPersonView](https://deck.gl/docs/api-reference/core/first-person-view)
- [Pointer Lock API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Pointer_Lock_API)
- [RBush](https://github.com/mourner/rbush)
- [requestAnimationFrame](https://developer.mozilla.org/en-US/docs/Web/API/window/requestAnimationFrame)
```

**Create file:** `.claude/skills/deckgl-firstperson/reference/first-person-view.md`
```markdown
# deck.gl FirstPersonView Reference

## Import

```typescript
import { Deck } from '@deck.gl/core';
import { FirstPersonView } from '@deck.gl/core';
```

## View Configuration

```typescript
const view = new FirstPersonView({
  id: 'first-person',

  // Controller (disable for custom controls)
  controller: false,

  // Field of view (vertical, in degrees)
  fovy: 75,

  // Clipping planes (in meters)
  near: 0.1,
  far: 10000,
});
```

## ViewState

```typescript
interface FirstPersonViewState {
  // Camera position in [longitude, latitude, altitude]
  // Altitude is in METERS above sea level
  position: [number, number, number];

  // Horizontal rotation (0 = North, 90 = East)
  bearing: number;

  // Vertical rotation (-90 = down, 90 = up)
  pitch: number;
}
```

## With DeckGL React Component

```tsx
import DeckGL from '@deck.gl/react';
import { FirstPersonView } from '@deck.gl/core';

function Viewer() {
  const [viewState, setViewState] = useState({
    position: [8.541694, 47.376888, 2],
    bearing: 0,
    pitch: 0,
  });

  return (
    <DeckGL
      views={new FirstPersonView({ fovy: 75, near: 0.1, far: 10000 })}
      viewState={viewState}
      onViewStateChange={({ viewState }) => setViewState(viewState)}
      controller={false} // Disable default controller for custom controls
      layers={[/* ... */]}
    />
  );
}
```

## Important Notes

1. **Position is WGS84**: longitude, latitude in degrees, altitude in meters
2. **Bearing is clockwise from North**: 0°=N, 90°=E, 180°=S, 270°=W
3. **Pitch limits**: Usually clamp to [-89, 89] to avoid gimbal lock
4. **Controller: false**: Required for custom WASD controls
5. **near/far in meters**: Set appropriately for your scene scale
```

**Create file:** `.claude/skills/deckgl-firstperson/reference/game-loop.md`
```markdown
# Game Loop Reference

## requestAnimationFrame Pattern

```typescript
function useGameLoop(
  callback: (deltaTime: number) => void,
  isActive: boolean = true
) {
  const callbackRef = useRef(callback);
  const frameRef = useRef<number>();
  const lastTimeRef = useRef<number>();

  // Keep callback ref updated
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!isActive) return;

    const loop = (time: number) => {
      if (lastTimeRef.current !== undefined) {
        // Delta time in SECONDS
        const deltaTime = (time - lastTimeRef.current) / 1000;

        // Clamp to avoid huge jumps (e.g., tab was inactive)
        const clampedDelta = Math.min(deltaTime, 0.1);

        callbackRef.current(clampedDelta);
      }

      lastTimeRef.current = time;
      frameRef.current = requestAnimationFrame(loop);
    };

    frameRef.current = requestAnimationFrame(loop);

    return () => {
      if (frameRef.current !== undefined) {
        cancelAnimationFrame(frameRef.current);
      }
    };
  }, [isActive]);
}
```

## Fixed Timestep (Physics)

For deterministic physics, use fixed timestep with interpolation:

```typescript
const FIXED_STEP = 1 / 60; // 60 updates per second
let accumulator = 0;

function fixedUpdate(deltaTime: number) {
  accumulator += deltaTime;

  while (accumulator >= FIXED_STEP) {
    // Physics update at fixed rate
    physicsStep(FIXED_STEP);
    accumulator -= FIXED_STEP;
  }

  // Interpolation factor for rendering
  const alpha = accumulator / FIXED_STEP;
  render(alpha);
}
```

## Frame Timing Best Practices

1. **Always use deltaTime**: Never assume 60fps
2. **Clamp deltaTime**: Avoid huge jumps when tab resumes
3. **Use ref for callback**: Avoid recreating RAF each render
4. **Clean up on unmount**: Cancel pending frame
5. **Check isActive flag**: Allow pausing the loop
```

**Create file:** `.claude/skills/deckgl-firstperson/reference/collision-system.md`
```markdown
# Collision System Reference

## RBush Spatial Index

```typescript
import RBush from 'rbush';

interface BuildingBBox {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
  feature: BuildingFeature;
}

// Create index
const tree = new RBush<BuildingBBox>();

// Bulk load (efficient for many items)
tree.load(buildingBBoxes);

// Query nearby buildings
const nearby = tree.search({
  minX: playerX - radius,
  minY: playerY - radius,
  maxX: playerX + radius,
  maxY: playerY + radius,
});
```

## Building BBox Extraction

```typescript
function extractBBox(feature: BuildingFeature): BuildingBBox {
  const coords = feature.geometry.coordinates[0]; // Outer ring

  let minX = Infinity, minY = Infinity;
  let maxX = -Infinity, maxY = -Infinity;

  for (const [x, y] of coords) {
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  }

  return { minX, minY, maxX, maxY, feature };
}
```

## Point-in-Polygon Test

```typescript
function pointInPolygon(
  x: number,
  y: number,
  polygon: number[][]
): boolean {
  let inside = false;

  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i][0], yi = polygon[i][1];
    const xj = polygon[j][0], yj = polygon[j][1];

    if (((yi > y) !== (yj > y)) &&
        (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) {
      inside = !inside;
    }
  }

  return inside;
}
```

## Wall Sliding

When collision occurs, slide along the wall:

```typescript
function slideAlongWall(
  position: [number, number],
  velocity: [number, number],
  wallNormal: [number, number]
): [number, number] {
  // Project velocity onto wall tangent
  const dot = velocity[0] * wallNormal[0] + velocity[1] * wallNormal[1];

  return [
    velocity[0] - dot * wallNormal[0],
    velocity[1] - dot * wallNormal[1],
  ];
}
```

## Complete Collision Check

```typescript
function checkCollision(
  spatialIndex: RBush<BuildingBBox>,
  position: [number, number],
  radius: number
): CollisionResult {
  const nearby = spatialIndex.search({
    minX: position[0] - radius,
    minY: position[1] - radius,
    maxX: position[0] + radius,
    maxY: position[1] + radius,
  });

  for (const bbox of nearby) {
    const polygon = bbox.feature.geometry.coordinates[0];

    if (pointInPolygon(position[0], position[1], polygon)) {
      // Find nearest edge for wall normal
      const normal = findNearestEdgeNormal(position, polygon);

      return {
        collides: true,
        building: bbox.feature,
        normal,
      };
    }
  }

  return { collides: false };
}
```
```

**Create file:** `.claude/skills/deckgl-firstperson/reference/pointer-lock.md`
```markdown
# Pointer Lock API Reference

## Basic Usage

```typescript
// Request pointer lock (must be from user gesture)
element.requestPointerLock();

// Check if locked
document.pointerLockElement === element;

// Exit pointer lock
document.exitPointerLock();
```

## Mouse Movement While Locked

```typescript
function handleMouseMove(event: MouseEvent) {
  if (document.pointerLockElement !== targetElement) return;

  // movementX/Y give delta since last event (in pixels)
  const deltaX = event.movementX;
  const deltaY = event.movementY;

  // Apply sensitivity
  const bearingDelta = deltaX * SENSITIVITY;
  const pitchDelta = -deltaY * SENSITIVITY; // Inverted for natural feel
}
```

## Complete Hook Implementation

```typescript
function useMouseLook(
  targetRef: RefObject<HTMLElement>,
  sensitivity: { x: number; y: number } = { x: 0.1, y: 0.1 }
) {
  const [isLocked, setIsLocked] = useState(false);
  const deltaRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const target = targetRef.current;
    if (!target) return;

    const handleLockChange = () => {
      setIsLocked(document.pointerLockElement === target);
    };

    const handleMouseMove = (e: MouseEvent) => {
      if (document.pointerLockElement !== target) return;

      deltaRef.current.x += e.movementX * sensitivity.x;
      deltaRef.current.y += e.movementY * sensitivity.y;
    };

    const handleClick = () => {
      if (document.pointerLockElement !== target) {
        target.requestPointerLock();
      }
    };

    document.addEventListener('pointerlockchange', handleLockChange);
    document.addEventListener('mousemove', handleMouseMove);
    target.addEventListener('click', handleClick);

    return () => {
      document.removeEventListener('pointerlockchange', handleLockChange);
      document.removeEventListener('mousemove', handleMouseMove);
      target.removeEventListener('click', handleClick);
    };
  }, [targetRef, sensitivity.x, sensitivity.y]);

  const consumeDelta = useCallback(() => {
    const delta = { ...deltaRef.current };
    deltaRef.current = { x: 0, y: 0 };
    return delta;
  }, []);

  return { isLocked, consumeDelta };
}
```

## Browser Compatibility

- Chrome: Full support
- Firefox: Full support
- Safari: Full support (since 10.1)
- Edge: Full support

## Common Issues

1. **Must be in click handler**: Browser security requirement
2. **User can exit with Escape**: Always handle `pointerlockchange`
3. **movementX/Y can be fractional**: Don't round prematurely
4. **Safari may need webkit prefix**: Check `webkitRequestPointerLock`
```

**Create file:** `.claude/skills/deckgl-firstperson/templates/use-keyboard-state.template.ts`
```typescript
/**
 * useKeyboardState Hook
 *
 * Tracks WASD + modifier key state for movement controls
 */

import { useState, useEffect, useCallback } from 'react';
import type { KeyboardState } from '@/types';

const INITIAL_STATE: KeyboardState = {
  forward: false,
  backward: false,
  left: false,
  right: false,
  run: false,
  jump: false,
};

const KEY_MAP: Record<string, keyof KeyboardState> = {
  KeyW: 'forward',
  KeyS: 'backward',
  KeyA: 'left',
  KeyD: 'right',
  ShiftLeft: 'run',
  ShiftRight: 'run',
  Space: 'jump',
  // Arrow keys as alternatives
  ArrowUp: 'forward',
  ArrowDown: 'backward',
  ArrowLeft: 'left',
  ArrowRight: 'right',
};

export function useKeyboardState(): KeyboardState {
  const [state, setState] = useState<KeyboardState>(INITIAL_STATE);

  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    const key = KEY_MAP[event.code];
    if (key) {
      event.preventDefault();
      setState((prev) => ({ ...prev, [key]: true }));
    }
  }, []);

  const handleKeyUp = useCallback((event: KeyboardEvent) => {
    const key = KEY_MAP[event.code];
    if (key) {
      setState((prev) => ({ ...prev, [key]: false }));
    }
  }, []);

  const handleBlur = useCallback(() => {
    // Reset all keys when window loses focus
    setState(INITIAL_STATE);
  }, []);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', handleBlur);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('blur', handleBlur);
    };
  }, [handleKeyDown, handleKeyUp, handleBlur]);

  return state;
}
```

**Create file:** `.claude/skills/deckgl-firstperson/templates/use-mouse-look.template.ts`
```typescript
/**
 * useMouseLook Hook
 *
 * Manages pointer lock and accumulates mouse movement for camera control
 */

import { useState, useEffect, useCallback, useRef, type RefObject } from 'react';
import { MOUSE_SENSITIVITY } from '@/types';

export interface MouseLookState {
  isLocked: boolean;
  consumeDelta: () => { x: number; y: number };
  requestLock: () => void;
  exitLock: () => void;
}

export function useMouseLook(
  targetRef: RefObject<HTMLElement | null>,
  sensitivity = MOUSE_SENSITIVITY
): MouseLookState {
  const [isLocked, setIsLocked] = useState(false);
  const deltaRef = useRef({ x: 0, y: 0 });

  // Handle pointer lock state changes
  useEffect(() => {
    const handleLockChange = () => {
      const isNowLocked = document.pointerLockElement === targetRef.current;
      setIsLocked(isNowLocked);

      // Reset delta when lock state changes
      if (!isNowLocked) {
        deltaRef.current = { x: 0, y: 0 };
      }
    };

    const handleLockError = () => {
      console.warn('Pointer lock request failed');
      setIsLocked(false);
    };

    document.addEventListener('pointerlockchange', handleLockChange);
    document.addEventListener('pointerlockerror', handleLockError);

    return () => {
      document.removeEventListener('pointerlockchange', handleLockChange);
      document.removeEventListener('pointerlockerror', handleLockError);
    };
  }, [targetRef]);

  // Handle mouse movement while locked
  useEffect(() => {
    const handleMouseMove = (event: MouseEvent) => {
      if (document.pointerLockElement !== targetRef.current) return;

      // Accumulate movement scaled by sensitivity
      deltaRef.current.x += event.movementX * sensitivity.x;
      deltaRef.current.y += event.movementY * sensitivity.y;
    };

    document.addEventListener('mousemove', handleMouseMove);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
    };
  }, [targetRef, sensitivity.x, sensitivity.y]);

  // Consume accumulated delta (resets to zero)
  const consumeDelta = useCallback(() => {
    const delta = { ...deltaRef.current };
    deltaRef.current = { x: 0, y: 0 };
    return delta;
  }, []);

  // Request pointer lock
  const requestLock = useCallback(() => {
    const target = targetRef.current;
    if (target && document.pointerLockElement !== target) {
      target.requestPointerLock();
    }
  }, [targetRef]);

  // Exit pointer lock
  const exitLock = useCallback(() => {
    if (document.pointerLockElement) {
      document.exitPointerLock();
    }
  }, []);

  return { isLocked, consumeDelta, requestLock, exitLock };
}
```

**Create file:** `.claude/skills/deckgl-firstperson/templates/use-game-loop.template.ts`
```typescript
/**
 * useGameLoop Hook
 *
 * Manages requestAnimationFrame loop with proper timing
 */

import { useEffect, useRef, useCallback } from 'react';

export interface GameLoopCallback {
  (deltaTime: number, totalTime: number): void;
}

export function useGameLoop(
  callback: GameLoopCallback,
  isActive: boolean = true
): void {
  const callbackRef = useRef<GameLoopCallback>(callback);
  const frameRef = useRef<number>();
  const lastTimeRef = useRef<number>();
  const startTimeRef = useRef<number>();

  // Keep callback ref updated without triggering effect
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!isActive) {
      // Reset timing when paused
      lastTimeRef.current = undefined;
      return;
    }

    const loop = (timestamp: number) => {
      // Initialize start time on first frame
      if (startTimeRef.current === undefined) {
        startTimeRef.current = timestamp;
      }

      // Calculate delta time
      if (lastTimeRef.current !== undefined) {
        const deltaMs = timestamp - lastTimeRef.current;

        // Convert to seconds and clamp to avoid huge jumps
        // (e.g., when tab was in background)
        const deltaTime = Math.min(deltaMs / 1000, 0.1);

        const totalTime = (timestamp - startTimeRef.current) / 1000;

        callbackRef.current(deltaTime, totalTime);
      }

      lastTimeRef.current = timestamp;
      frameRef.current = requestAnimationFrame(loop);
    };

    frameRef.current = requestAnimationFrame(loop);

    return () => {
      if (frameRef.current !== undefined) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = undefined;
      }
    };
  }, [isActive]);
}

/**
 * Fixed timestep game loop for physics
 */
export function useFixedGameLoop(
  callback: GameLoopCallback,
  fixedStep: number = 1 / 60,
  isActive: boolean = true
): void {
  const accumulatorRef = useRef(0);

  const wrappedCallback = useCallback(
    (deltaTime: number, totalTime: number) => {
      accumulatorRef.current += deltaTime;

      while (accumulatorRef.current >= fixedStep) {
        callback(fixedStep, totalTime);
        accumulatorRef.current -= fixedStep;
      }
    },
    [callback, fixedStep]
  );

  useGameLoop(wrappedCallback, isActive);
}
```

**Create file:** `.claude/skills/deckgl-firstperson/templates/movement-controller.template.ts`
```typescript
/**
 * MovementController
 *
 * Converts keyboard state to velocity vectors based on camera bearing
 */

import type { KeyboardState, Velocity } from '@/types';
import { MOVEMENT_SPEEDS } from '@/types';

const DEG_TO_RAD = Math.PI / 180;

export interface MovementControllerConfig {
  walkSpeed?: number;
  runSpeed?: number;
}

export class MovementController {
  private walkSpeed: number;
  private runSpeed: number;

  constructor(config: MovementControllerConfig = {}) {
    this.walkSpeed = config.walkSpeed ?? MOVEMENT_SPEEDS.walk;
    this.runSpeed = config.runSpeed ?? MOVEMENT_SPEEDS.run;
  }

  /**
   * Calculate velocity from keyboard state and camera bearing
   * Returns velocity in meters per second
   */
  calculateVelocity(
    keyboard: KeyboardState,
    bearing: number,
    deltaTime: number
  ): Velocity {
    // Determine movement direction in local space
    let localX = 0; // Right/Left
    let localY = 0; // Forward/Backward

    if (keyboard.forward) localY += 1;
    if (keyboard.backward) localY -= 1;
    if (keyboard.right) localX += 1;
    if (keyboard.left) localX -= 1;

    // Normalize diagonal movement
    const length = Math.sqrt(localX * localX + localY * localY);
    if (length > 0) {
      localX /= length;
      localY /= length;
    }

    // Determine speed
    const speed = keyboard.run ? this.runSpeed : this.walkSpeed;

    // Convert bearing to radians (0 = North = +Y in world space)
    const bearingRad = bearing * DEG_TO_RAD;
    const sinB = Math.sin(bearingRad);
    const cosB = Math.cos(bearingRad);

    // Rotate local direction by bearing to get world direction
    // Forward (+localY) should point in bearing direction
    // Right (+localX) should point 90° clockwise from bearing
    const worldX = localX * cosB + localY * sinB;
    const worldY = -localX * sinB + localY * cosB;

    return {
      x: worldX * speed,
      y: worldY * speed,
      z: 0, // Vertical velocity handled separately
    };
  }

  /**
   * Convert velocity in meters to position delta in degrees
   * For use with WGS84 coordinates
   */
  velocityToDegrees(
    velocity: Velocity,
    deltaTime: number,
    latitude: number
  ): { dLng: number; dLat: number; dAlt: number } {
    // Meters per degree varies with latitude
    const metersPerDegreeLat = 111000;
    const metersPerDegreeLng = 111000 * Math.cos(latitude * DEG_TO_RAD);

    return {
      dLng: (velocity.x * deltaTime) / metersPerDegreeLng,
      dLat: (velocity.y * deltaTime) / metersPerDegreeLat,
      dAlt: velocity.z * deltaTime,
    };
  }
}

// Singleton instance for convenience
export const movementController = new MovementController();
```

**Create file:** `.claude/skills/deckgl-firstperson/templates/spatial-index.template.ts`
```typescript
/**
 * SpatialIndex
 *
 * RBush-based spatial index for collision detection
 */

import RBush from 'rbush';
import type { BuildingFeature, CollisionBBox, CollisionResult } from '@/types';

export class SpatialIndex {
  private tree: RBush<CollisionBBox>;
  private isLoaded: boolean = false;

  constructor() {
    this.tree = new RBush<CollisionBBox>();
  }

  /**
   * Load building features into the spatial index
   */
  load(features: BuildingFeature[]): void {
    const bboxes = features.map((feature) => this.extractBBox(feature));
    this.tree.load(bboxes);
    this.isLoaded = true;
  }

  /**
   * Clear all data from the index
   */
  clear(): void {
    this.tree.clear();
    this.isLoaded = false;
  }

  /**
   * Check if index has been loaded with data
   */
  get loaded(): boolean {
    return this.isLoaded;
  }

  /**
   * Query buildings near a point
   */
  queryNearby(
    lng: number,
    lat: number,
    radiusDegrees: number
  ): CollisionBBox[] {
    return this.tree.search({
      minX: lng - radiusDegrees,
      minY: lat - radiusDegrees,
      maxX: lng + radiusDegrees,
      maxY: lat + radiusDegrees,
    });
  }

  /**
   * Check collision at a point
   */
  checkCollision(
    lng: number,
    lat: number,
    radiusDegrees: number = 0.00001 // ~1m at Zurich latitude
  ): CollisionResult {
    const nearby = this.queryNearby(lng, lat, radiusDegrees);

    for (const bbox of nearby) {
      const polygon = this.getOuterRing(bbox.feature);

      if (this.pointInPolygon(lng, lat, polygon)) {
        const normal = this.findNearestEdgeNormal(lng, lat, polygon);

        return {
          collides: true,
          building: bbox.feature,
          normal,
        };
      }
    }

    return { collides: false };
  }

  /**
   * Extract bounding box from a building feature
   */
  private extractBBox(feature: BuildingFeature): CollisionBBox {
    const coords = this.getOuterRing(feature);

    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;

    for (const coord of coords) {
      const [x, y] = coord;
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }

    return { minX, minY, maxX, maxY, feature };
  }

  /**
   * Get outer ring coordinates from a feature
   */
  private getOuterRing(feature: BuildingFeature): number[][] {
    const coords = feature.geometry.coordinates;

    if (feature.geometry.type === 'MultiPolygon') {
      // Take first polygon's outer ring
      return (coords as number[][][][])[0][0];
    }

    // Polygon: first array is outer ring
    return (coords as number[][][])[0];
  }

  /**
   * Ray-casting point-in-polygon test
   */
  private pointInPolygon(x: number, y: number, polygon: number[][]): boolean {
    let inside = false;

    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const xi = polygon[i][0];
      const yi = polygon[i][1];
      const xj = polygon[j][0];
      const yj = polygon[j][1];

      if (
        yi > y !== yj > y &&
        x < ((xj - xi) * (y - yi)) / (yj - yi) + xi
      ) {
        inside = !inside;
      }
    }

    return inside;
  }

  /**
   * Find normal of nearest edge for wall sliding
   */
  private findNearestEdgeNormal(
    x: number,
    y: number,
    polygon: number[][]
  ): { x: number; y: number } {
    let minDist = Infinity;
    let nearestNormal = { x: 0, y: 1 };

    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const x1 = polygon[j][0];
      const y1 = polygon[j][1];
      const x2 = polygon[i][0];
      const y2 = polygon[i][1];

      // Distance from point to line segment
      const dist = this.pointToSegmentDistance(x, y, x1, y1, x2, y2);

      if (dist < minDist) {
        minDist = dist;

        // Calculate outward normal
        const dx = x2 - x1;
        const dy = y2 - y1;
        const len = Math.sqrt(dx * dx + dy * dy);

        // Perpendicular (pointing outward from polygon)
        nearestNormal = {
          x: -dy / len,
          y: dx / len,
        };

        // Ensure normal points outward (toward the test point)
        const toPoint = { x: x - x1, y: y - y1 };
        const dot = nearestNormal.x * toPoint.x + nearestNormal.y * toPoint.y;
        if (dot < 0) {
          nearestNormal.x = -nearestNormal.x;
          nearestNormal.y = -nearestNormal.y;
        }
      }
    }

    return nearestNormal;
  }

  /**
   * Distance from point to line segment
   */
  private pointToSegmentDistance(
    px: number,
    py: number,
    x1: number,
    y1: number,
    x2: number,
    y2: number
  ): number {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const lengthSq = dx * dx + dy * dy;

    if (lengthSq === 0) {
      return Math.sqrt((px - x1) ** 2 + (py - y1) ** 2);
    }

    let t = ((px - x1) * dx + (py - y1) * dy) / lengthSq;
    t = Math.max(0, Math.min(1, t));

    const nearestX = x1 + t * dx;
    const nearestY = y1 + t * dy;

    return Math.sqrt((px - nearestX) ** 2 + (py - nearestY) ** 2);
  }
}

// Singleton instance
export const spatialIndex = new SpatialIndex();
```

**Create file:** `.claude/skills/deckgl-firstperson/templates/camera-controller.template.ts`
```typescript
/**
 * CameraController
 *
 * Manages FirstPersonViewState updates including position, bearing, and pitch
 */

import type { FirstPersonViewState, Velocity } from '@/types';

const DEG_TO_RAD = Math.PI / 180;

export interface CameraUpdateResult {
  viewState: FirstPersonViewState;
  wasConstrained: boolean;
}

export interface CameraControllerConfig {
  pitchMin?: number;
  pitchMax?: number;
  minAltitude?: number;
}

export class CameraController {
  private pitchMin: number;
  private pitchMax: number;
  private minAltitude: number;

  constructor(config: CameraControllerConfig = {}) {
    this.pitchMin = config.pitchMin ?? -89;
    this.pitchMax = config.pitchMax ?? 89;
    this.minAltitude = config.minAltitude ?? 0.5;
  }

  /**
   * Apply mouse look deltas to bearing and pitch
   */
  applyMouseLook(
    viewState: FirstPersonViewState,
    deltaX: number,
    deltaY: number
  ): FirstPersonViewState {
    // deltaX rotates bearing (horizontal)
    // deltaY rotates pitch (vertical, inverted for natural feel)
    let newBearing = viewState.bearing + deltaX;
    let newPitch = viewState.pitch - deltaY; // Inverted

    // Normalize bearing to [0, 360)
    newBearing = ((newBearing % 360) + 360) % 360;

    // Clamp pitch to avoid gimbal lock
    newPitch = Math.max(this.pitchMin, Math.min(this.pitchMax, newPitch));

    return {
      ...viewState,
      bearing: newBearing,
      pitch: newPitch,
    };
  }

  /**
   * Apply velocity to position
   */
  applyVelocity(
    viewState: FirstPersonViewState,
    velocity: Velocity,
    deltaTime: number
  ): CameraUpdateResult {
    const [lng, lat, alt] = viewState.position;

    // Convert velocity (m/s) to degrees
    const metersPerDegreeLat = 111000;
    const metersPerDegreeLng = 111000 * Math.cos(lat * DEG_TO_RAD);

    const newLng = lng + (velocity.x * deltaTime) / metersPerDegreeLng;
    const newLat = lat + (velocity.y * deltaTime) / metersPerDegreeLat;
    let newAlt = alt + velocity.z * deltaTime;

    // Clamp altitude
    let wasConstrained = false;
    if (newAlt < this.minAltitude) {
      newAlt = this.minAltitude;
      wasConstrained = true;
    }

    return {
      viewState: {
        ...viewState,
        position: [newLng, newLat, newAlt],
      },
      wasConstrained,
    };
  }

  /**
   * Set position directly (e.g., after collision resolution)
   */
  setPosition(
    viewState: FirstPersonViewState,
    lng: number,
    lat: number,
    alt?: number
  ): FirstPersonViewState {
    return {
      ...viewState,
      position: [lng, lat, alt ?? viewState.position[2]],
    };
  }

  /**
   * Set altitude (e.g., after terrain query)
   */
  setAltitude(
    viewState: FirstPersonViewState,
    groundElevation: number,
    eyeHeight: number
  ): FirstPersonViewState {
    const targetAlt = groundElevation + eyeHeight;

    return {
      ...viewState,
      position: [
        viewState.position[0],
        viewState.position[1],
        Math.max(targetAlt, this.minAltitude),
      ],
    };
  }
}

// Singleton instance
export const cameraController = new CameraController();
```

**Create file:** `.claude/skills/deckgl-firstperson/workflows/add-wasd-controls.md`
```markdown
# Add WASD Controls Workflow

Minimal implementation for WASD movement without collision.

## Steps

### 1. Create useKeyboardState
Copy from `templates/use-keyboard-state.template.ts` to:
`src/hooks/useKeyboardState.ts`

### 2. Create useMouseLook
Copy from `templates/use-mouse-look.template.ts` to:
`src/hooks/useMouseLook.ts`

### 3. Create useGameLoop
Copy from `templates/use-game-loop.template.ts` to:
`src/hooks/useGameLoop.ts`

### 4. Create MovementController
Copy from `templates/movement-controller.template.ts` to:
`src/systems/MovementController.ts`

### 5. Create CameraController
Copy from `templates/camera-controller.template.ts` to:
`src/systems/CameraController.ts`

### 6. Create hooks index
Create `src/hooks/index.ts`:
```typescript
export { useKeyboardState } from './useKeyboardState';
export { useMouseLook } from './useMouseLook';
export { useGameLoop, useFixedGameLoop } from './useGameLoop';
```

### 7. Create systems index
Create `src/systems/index.ts`:
```typescript
export { MovementController, movementController } from './MovementController';
export { CameraController, cameraController } from './CameraController';
```

### 8. Integrate in Component
```tsx
import { useRef, useState, useCallback } from 'react';
import DeckGL from '@deck.gl/react';
import { FirstPersonView } from '@deck.gl/core';
import { useKeyboardState } from '@/hooks/useKeyboardState';
import { useMouseLook } from '@/hooks/useMouseLook';
import { useGameLoop } from '@/hooks/useGameLoop';
import { movementController } from '@/systems/MovementController';
import { cameraController } from '@/systems/CameraController';
import { DEFAULT_VIEW_STATE, PLAYER_DIMENSIONS } from '@/types';

function ZurichViewer() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [viewState, setViewState] = useState(DEFAULT_VIEW_STATE);

  const keyboard = useKeyboardState();
  const { isLocked, consumeDelta, requestLock } = useMouseLook(containerRef);

  const gameLoop = useCallback(
    (deltaTime: number) => {
      // Apply mouse look
      const mouseDelta = consumeDelta();
      let newState = cameraController.applyMouseLook(
        viewState,
        mouseDelta.x,
        mouseDelta.y
      );

      // Calculate velocity from keyboard
      const velocity = movementController.calculateVelocity(
        keyboard,
        newState.bearing,
        deltaTime
      );

      // Apply velocity to position
      const { viewState: updatedState } = cameraController.applyVelocity(
        newState,
        velocity,
        deltaTime
      );

      setViewState(updatedState);
    },
    [viewState, keyboard, consumeDelta]
  );

  useGameLoop(gameLoop, isLocked);

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%' }}>
      <DeckGL
        views={new FirstPersonView({ fovy: 75 })}
        viewState={viewState}
        controller={false}
        onClick={requestLock}
        layers={[]}
      />
    </div>
  );
}
```

### 9. Verify
```bash
pnpm type-check
```
```

**Create file:** `.claude/skills/deckgl-firstperson/workflows/add-collision.md`
```markdown
# Add Collision Detection Workflow

Add building collision to existing WASD controls.

## Prerequisites
- WASD controls working (see add-wasd-controls.md)
- Building data loaded

## Steps

### 1. Create SpatialIndex
Copy from `templates/spatial-index.template.ts` to:
`src/systems/SpatialIndex.ts`

### 2. Export from systems
Update `src/systems/index.ts`:
```typescript
export { SpatialIndex, spatialIndex } from './SpatialIndex';
```

### 3. Create useCollisionDetection
Create `src/hooks/useCollisionDetection.ts`:
```typescript
import { useEffect, useCallback } from 'react';
import { spatialIndex } from '@/systems/SpatialIndex';
import type { BuildingFeature, CollisionResult } from '@/types';

export function useCollisionDetection(buildings: BuildingFeature[] | null) {
  // Load buildings into spatial index
  useEffect(() => {
    if (buildings && buildings.length > 0) {
      spatialIndex.load(buildings);
    }
    return () => spatialIndex.clear();
  }, [buildings]);

  // Check collision at position
  const checkCollision = useCallback(
    (lng: number, lat: number, radius?: number): CollisionResult => {
      if (!spatialIndex.loaded) {
        return { collides: false };
      }
      return spatialIndex.checkCollision(lng, lat, radius);
    },
    []
  );

  return { checkCollision, isReady: spatialIndex.loaded };
}
```

### 4. Update game loop
Add collision checking to movement:
```typescript
// After calculating velocity, before applying:
const proposedLng = viewState.position[0] + dLng;
const proposedLat = viewState.position[1] + dLat;

const collision = checkCollision(proposedLng, proposedLat);

if (collision.collides && collision.normal) {
  // Wall sliding: remove velocity component into wall
  const dot = velocity.x * collision.normal.x + velocity.y * collision.normal.y;
  velocity.x -= dot * collision.normal.x;
  velocity.y -= dot * collision.normal.y;
}
```
```

**Create file:** `.claude/skills/deckgl-firstperson/workflows/add-terrain-following.md`
```markdown
# Add Terrain Following Workflow

Add terrain elevation to existing movement system.

## Prerequisites
- WASD controls working
- Terrain data loaded

## Steps

### 1. Create TerrainSampler
Create `src/systems/TerrainSampler.ts`:
```typescript
import type { TerrainData } from '@/types';

export class TerrainSampler {
  private data: TerrainData | null = null;

  load(terrain: TerrainData): void {
    this.data = terrain;
  }

  clear(): void {
    this.data = null;
  }

  get loaded(): boolean {
    return this.data !== null;
  }

  /**
   * Sample elevation at a WGS84 coordinate
   */
  sample(lng: number, lat: number): number {
    if (!this.data) return 0;

    const { bounds, width, height, elevations } = this.data;

    // Convert lng/lat to pixel coordinates
    const x = ((lng - bounds.minLng) / (bounds.maxLng - bounds.minLng)) * (width - 1);
    const y = ((bounds.maxLat - lat) / (bounds.maxLat - bounds.minLat)) * (height - 1);

    // Bilinear interpolation
    const x0 = Math.floor(x);
    const y0 = Math.floor(y);
    const x1 = Math.min(x0 + 1, width - 1);
    const y1 = Math.min(y0 + 1, height - 1);

    const fx = x - x0;
    const fy = y - y0;

    const e00 = elevations[y0 * width + x0];
    const e10 = elevations[y0 * width + x1];
    const e01 = elevations[y1 * width + x0];
    const e11 = elevations[y1 * width + x1];

    return (
      e00 * (1 - fx) * (1 - fy) +
      e10 * fx * (1 - fy) +
      e01 * (1 - fx) * fy +
      e11 * fx * fy
    );
  }
}

export const terrainSampler = new TerrainSampler();
```

### 2. Create useTerrainElevation
Create `src/hooks/useTerrainElevation.ts`:
```typescript
import { useEffect, useCallback } from 'react';
import { terrainSampler } from '@/systems/TerrainSampler';
import type { TerrainData } from '@/types';

export function useTerrainElevation(terrain: TerrainData | null) {
  useEffect(() => {
    if (terrain) {
      terrainSampler.load(terrain);
    }
    return () => terrainSampler.clear();
  }, [terrain]);

  const getElevation = useCallback((lng: number, lat: number): number => {
    if (!terrainSampler.loaded) return 0;
    return terrainSampler.sample(lng, lat);
  }, []);

  return { getElevation, isReady: terrainSampler.loaded };
}
```

### 3. Update game loop
Lock camera to terrain:
```typescript
// After applying velocity:
const groundElevation = getElevation(newLng, newLat);
const newAlt = groundElevation + PLAYER_DIMENSIONS.eyeHeight;

// Smooth transition (optional)
const currentAlt = viewState.position[2];
const smoothedAlt = currentAlt + (newAlt - currentAlt) * 0.3;
```
```

---

### Task 1.4: Create deckgl-verify Skill
**Goal:** Create a verification skill that runs without dev server.

**Create directory structure:**
```
.claude/skills/deckgl-verify/
├── SKILL.md
└── scripts/
    ├── verify-types.ts
    └── verify-data.ts
```

**Create file:** `.claude/skills/deckgl-verify/SKILL.md`
```markdown
---
name: deckgl-verify
description: Verify deck.gl implementation without starting dev server. Use after making changes to confirm correctness.
allowed-tools: Read, Bash, Glob, Grep
---

# deck.gl Verification Skill

Validates implementation through type checking, unit tests, and static analysis.

## Quick Checks

### Type Check
```bash
pnpm type-check
```

### Run Tests
```bash
pnpm test
```

### Check Imports
```bash
# Verify no circular dependencies
npx madge --circular src/
```

## Full Verification Workflow

### Step 1: Type Safety
- [ ] Run `pnpm type-check`
- [ ] No errors expected
- [ ] Warnings are acceptable

### Step 2: Tests
- [ ] Run `pnpm test`
- [ ] All tests pass
- [ ] Coverage acceptable

### Step 3: Import Validation
- [ ] Check all deck.gl imports resolve
- [ ] Check @/ alias resolves
- [ ] No circular dependencies

### Step 4: Data Validation (if applicable)
- [ ] GeoJSON files parse correctly
- [ ] Coordinates are in correct format
- [ ] Building heights are positive

### Step 5: Layer Configuration
- [ ] Layer IDs are unique
- [ ] Required props provided
- [ ] Color values in valid range (0-255)

## Common Verification Commands

```bash
# Full type check
pnpm type-check

# Type check with watch
pnpm tsc --noEmit --watch

# Run specific test file
pnpm test src/systems/SpatialIndex.test.ts

# Validate GeoJSON
node scripts/validate-geojson.js public/data/buildings.geojson

# Check bundle size (dry run)
pnpm build --dry-run
```

## Verification Scripts

### verify-types.ts
Runs TypeScript compiler and reports errors.

### verify-data.ts
Validates GeoJSON files for correct structure.

## Troubleshooting

| Issue | Verification | Solution |
|-------|--------------|----------|
| Import errors | `pnpm type-check` | Check path aliases in tsconfig |
| Test failures | `pnpm test` | Read error messages, fix code |
| Data validation | Run verify-data.ts | Check GeoJSON structure |
| Runtime errors | Build + manual test | Use browser dev tools |

## When to Run

Run verification after:
- Creating new files
- Modifying types
- Changing imports
- Updating data files
- Before committing
```

**Create file:** `.claude/skills/deckgl-verify/scripts/verify-types.ts`
```typescript
#!/usr/bin/env npx ts-node

/**
 * Type verification script
 * Run with: npx ts-node scripts/verify-types.ts
 */

import { execSync } from 'child_process';

interface VerificationResult {
  step: string;
  passed: boolean;
  output?: string;
  error?: string;
}

function runCommand(command: string): { success: boolean; output: string } {
  try {
    const output = execSync(command, { encoding: 'utf-8', stdio: 'pipe' });
    return { success: true, output };
  } catch (error: any) {
    return { success: false, output: error.stdout || error.message };
  }
}

function verify(): VerificationResult[] {
  const results: VerificationResult[] = [];

  // Step 1: TypeScript compilation
  console.log('Checking TypeScript...');
  const tscResult = runCommand('pnpm tsc --noEmit');
  results.push({
    step: 'TypeScript Compilation',
    passed: tscResult.success,
    output: tscResult.output,
  });

  // Step 2: Check for any type errors in specific files
  console.log('Checking critical files...');
  const criticalFiles = [
    'src/types/index.ts',
    'src/hooks/useKeyboardState.ts',
    'src/systems/SpatialIndex.ts',
  ];

  for (const file of criticalFiles) {
    try {
      const content = require('fs').readFileSync(file, 'utf-8');
      results.push({
        step: `File exists: ${file}`,
        passed: true,
      });
    } catch {
      results.push({
        step: `File exists: ${file}`,
        passed: false,
        error: 'File not found',
      });
    }
  }

  return results;
}

// Run verification
const results = verify();

// Report
console.log('\n=== Verification Results ===\n');
let allPassed = true;

for (const result of results) {
  const status = result.passed ? '✓' : '✗';
  console.log(`${status} ${result.step}`);

  if (!result.passed) {
    allPassed = false;
    if (result.error) console.log(`  Error: ${result.error}`);
    if (result.output) console.log(`  Output: ${result.output.slice(0, 500)}`);
  }
}

console.log(`\n${allPassed ? 'All checks passed!' : 'Some checks failed.'}`);
process.exit(allPassed ? 0 : 1);
```

**Create file:** `.claude/skills/deckgl-verify/scripts/verify-data.ts`
```typescript
#!/usr/bin/env npx ts-node

/**
 * Data verification script for GeoJSON files
 * Run with: npx ts-node scripts/verify-data.ts
 */

import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

interface ValidationError {
  file: string;
  issue: string;
  details?: string;
}

function validateGeoJSON(filePath: string): ValidationError[] {
  const errors: ValidationError[] = [];

  if (!existsSync(filePath)) {
    errors.push({ file: filePath, issue: 'File not found' });
    return errors;
  }

  try {
    const content = readFileSync(filePath, 'utf-8');
    const data = JSON.parse(content);

    // Check FeatureCollection
    if (data.type !== 'FeatureCollection') {
      errors.push({
        file: filePath,
        issue: 'Not a FeatureCollection',
        details: `Found type: ${data.type}`,
      });
    }

    // Check features array
    if (!Array.isArray(data.features)) {
      errors.push({
        file: filePath,
        issue: 'Missing features array',
      });
      return errors;
    }

    console.log(`Found ${data.features.length} features in ${filePath}`);

    // Sample validation (first 10 features)
    const sample = data.features.slice(0, 10);

    for (let i = 0; i < sample.length; i++) {
      const feature = sample[i];

      // Check geometry
      if (!feature.geometry) {
        errors.push({
          file: filePath,
          issue: `Feature ${i} missing geometry`,
        });
        continue;
      }

      // Check coordinates
      if (!feature.geometry.coordinates) {
        errors.push({
          file: filePath,
          issue: `Feature ${i} missing coordinates`,
        });
        continue;
      }

      // Check coordinate format (should be [lng, lat])
      const coords = feature.geometry.coordinates;
      if (feature.geometry.type === 'Polygon' && coords[0]?.[0]) {
        const firstCoord = coords[0][0];
        const [lng, lat] = firstCoord;

        // Zurich bounds check
        if (lng < 8 || lng > 9 || lat < 47 || lat > 48) {
          errors.push({
            file: filePath,
            issue: `Feature ${i} coordinates outside Zurich bounds`,
            details: `[${lng}, ${lat}]`,
          });
        }
      }

      // Check properties
      if (feature.properties) {
        const height = feature.properties.height;
        if (height !== undefined && (height < 0 || height > 500)) {
          errors.push({
            file: filePath,
            issue: `Feature ${i} invalid height`,
            details: `height: ${height}`,
          });
        }
      }
    }
  } catch (e: any) {
    errors.push({
      file: filePath,
      issue: 'Parse error',
      details: e.message,
    });
  }

  return errors;
}

// Main
const dataDir = join(process.cwd(), 'public', 'data');
const files = ['zurich-buildings.geojson'];

console.log('=== Data Verification ===\n');

let totalErrors = 0;

for (const file of files) {
  const filePath = join(dataDir, file);
  const errors = validateGeoJSON(filePath);

  if (errors.length === 0) {
    console.log(`✓ ${file} - Valid`);
  } else {
    console.log(`✗ ${file} - ${errors.length} issues:`);
    for (const error of errors) {
      console.log(`  - ${error.issue}${error.details ? `: ${error.details}` : ''}`);
    }
    totalErrors += errors.length;
  }
}

console.log(`\n${totalErrors === 0 ? 'All data valid!' : `${totalErrors} issues found.`}`);
process.exit(totalErrors === 0 ? 0 : 1);
```

---

## Verification Checklist

After completing all tasks:

- [ ] `.claude/skills/deckgl-layer/SKILL.md` exists
- [ ] `.claude/skills/deckgl-layer/reference/` contains 3 files
- [ ] `.claude/skills/deckgl-layer/templates/` contains 3 files
- [ ] `.claude/skills/deckgl-data/SKILL.md` exists
- [ ] `.claude/skills/deckgl-data/reference/` contains 1 file
- [ ] `.claude/skills/deckgl-data/templates/` contains 3 files
- [ ] `.claude/skills/deckgl-firstperson/SKILL.md` exists
- [ ] `.claude/skills/deckgl-firstperson/reference/` contains 4 files
- [ ] `.claude/skills/deckgl-firstperson/templates/` contains 6 files
- [ ] `.claude/skills/deckgl-firstperson/workflows/` contains 3 files
- [ ] `.claude/skills/deckgl-verify/SKILL.md` exists
- [ ] `.claude/skills/deckgl-verify/scripts/` contains 2 files

## Files Created

```
.claude/skills/
├── deckgl-layer/
│   ├── SKILL.md
│   ├── reference/
│   │   ├── polygon-layer.md
│   │   ├── terrain-layer.md
│   │   └── scatterplot-layer.md
│   └── templates/
│       ├── layer-factory.template.ts
│       ├── layer-component.template.tsx
│       └── layer-types.template.ts
├── deckgl-data/
│   ├── SKILL.md
│   ├── reference/
│   │   └── geojson-loader.md
│   └── templates/
│       ├── loader.template.ts
│       ├── transformer.template.ts
│       └── use-data.template.ts
├── deckgl-firstperson/
│   ├── SKILL.md
│   ├── reference/
│   │   ├── first-person-view.md
│   │   ├── game-loop.md
│   │   ├── collision-system.md
│   │   └── pointer-lock.md
│   ├── templates/
│   │   ├── use-keyboard-state.template.ts
│   │   ├── use-mouse-look.template.ts
│   │   ├── use-game-loop.template.ts
│   │   ├── movement-controller.template.ts
│   │   ├── spatial-index.template.ts
│   │   └── camera-controller.template.ts
│   └── workflows/
│       ├── add-wasd-controls.md
│       ├── add-collision.md
│       └── add-terrain-following.md
└── deckgl-verify/
    ├── SKILL.md
    └── scripts/
        ├── verify-types.ts
        └── verify-data.ts
```

## Next Phase
After verification, read and execute: `.claude/plans/phases/02-data-pipeline.md`
