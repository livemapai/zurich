# Step 3: Facade Selection

## Goal

After selecting a building, click on a specific edge to select that facade for texturing.

## Prerequisites

- Step 2 completed (building selection works)
- Understanding of building polygon structure

## What You'll Learn

- Extracting facade edges from building polygons
- LineLayer/PathLayer for edge visualization
- Edge picking and interaction

## Concepts

### Facade Geometry

A building footprint is a polygon. Each edge becomes a facade when extruded:

```
Building Polygon (top view):     Facade (3D side view):

    1───────2                         ┌─────────┐ top
    │       │                         │         │
    │       │      Edge 1-2  →        │ FACADE  │
    │       │                         │         │
    0───────3                         └─────────┘ bottom

    Edge 0-1 = Left facade
    Edge 1-2 = Back facade
    Edge 2-3 = Right facade
    Edge 3-0 = Front facade
```

## Implementation

### 1. Extract Facade Edges

```typescript
// src/utils/facadeGeometry.ts

export interface FacadeEdge {
  id: string;
  buildingId: string;
  edgeIndex: number;
  start: [number, number];  // [lng, lat]
  end: [number, number];
  length: number;  // meters
  bearing: number; // degrees, 0=North
}

export function extractFacadeEdges(
  buildingId: string,
  polygon: number[][]  // [[lng, lat], ...]
): FacadeEdge[] {
  const edges: FacadeEdge[] = [];

  for (let i = 0; i < polygon.length; i++) {
    const start = polygon[i];
    const end = polygon[(i + 1) % polygon.length];

    edges.push({
      id: `${buildingId}_edge_${i}`,
      buildingId,
      edgeIndex: i,
      start: [start[0], start[1]],
      end: [end[0], end[1]],
      length: calculateDistance(start, end),
      bearing: calculateBearing(start, end),
    });
  }

  return edges;
}

function calculateDistance(
  p1: number[],
  p2: number[]
): number {
  // Haversine formula or simple approximation
  const dLng = (p2[0] - p1[0]) * 75500; // meters at Zurich latitude
  const dLat = (p2[1] - p1[1]) * 111320;
  return Math.sqrt(dLng * dLng + dLat * dLat);
}

function calculateBearing(
  p1: number[],
  p2: number[]
): number {
  const dLng = p2[0] - p1[0];
  const dLat = p2[1] - p1[1];
  const angle = Math.atan2(dLng, dLat) * (180 / Math.PI);
  return (angle + 360) % 360;
}
```

### 2. Create Facade Edges Layer

```typescript
// src/layers/FacadeEdgesLayer.ts

import { PathLayer } from '@deck.gl/layers';
import type { FacadeEdge } from '../utils/facadeGeometry';

export function createFacadeEdgesLayer(
  edges: FacadeEdge[],
  options: {
    selectedEdgeId?: string | null;
    hoveredEdgeId?: string | null;
    buildingHeight: number;
    baseAltitude: number;
    onClick?: (edge: FacadeEdge) => void;
  }
) {
  // Create 3D paths for each edge (vertical lines at building corners)
  const pathData = edges.flatMap(edge => [
    // Bottom edge
    {
      ...edge,
      path: [
        [...edge.start, options.baseAltitude],
        [...edge.end, options.baseAltitude],
      ],
      type: 'bottom',
    },
    // Top edge
    {
      ...edge,
      path: [
        [...edge.start, options.baseAltitude + options.buildingHeight],
        [...edge.end, options.baseAltitude + options.buildingHeight],
      ],
      type: 'top',
    },
    // Left vertical
    {
      ...edge,
      path: [
        [...edge.start, options.baseAltitude],
        [...edge.start, options.baseAltitude + options.buildingHeight],
      ],
      type: 'vertical',
    },
  ]);

  return new PathLayer({
    id: 'facade-edges',
    data: pathData,
    getPath: d => d.path,
    getWidth: d => {
      if (d.id === options.selectedEdgeId) return 4;
      if (d.id === options.hoveredEdgeId) return 3;
      return 2;
    },
    getColor: d => {
      if (d.id === options.selectedEdgeId) return [0, 255, 0, 255]; // Green
      if (d.id === options.hoveredEdgeId) return [255, 255, 0, 255]; // Yellow
      return [255, 100, 0, 200]; // Orange
    },
    pickable: true,
    onHover: info => {
      // Handle hover state
    },
    onClick: info => {
      if (info.object && options.onClick) {
        options.onClick(info.object);
      }
    },
    widthUnits: 'pixels',
    updateTriggers: {
      getWidth: [options.selectedEdgeId, options.hoveredEdgeId],
      getColor: [options.selectedEdgeId, options.hoveredEdgeId],
    },
  });
}
```

### 3. Alternative: Clickable Facade Polygons

For better UX, render the facade as a filled polygon:

```typescript
// src/layers/FacadePolygonsLayer.ts

import { PolygonLayer } from '@deck.gl/layers';
import type { FacadeEdge, FacadeQuad } from '../utils/facadeGeometry';

export function createFacadePolygonsLayer(
  edges: FacadeEdge[],
  options: {
    selectedEdgeId?: string | null;
    hoveredEdgeId?: string | null;
    buildingHeight: number;
    baseAltitude: number;
    onClick?: (edge: FacadeEdge) => void;
  }
) {
  const polygonData = edges.map(edge => ({
    ...edge,
    polygon: [
      [...edge.start, options.baseAltitude],
      [...edge.end, options.baseAltitude],
      [...edge.end, options.baseAltitude + options.buildingHeight],
      [...edge.start, options.baseAltitude + options.buildingHeight],
    ],
  }));

  return new PolygonLayer({
    id: 'facade-polygons',
    data: polygonData,
    getPolygon: d => d.polygon,
    getFillColor: d => {
      if (d.id === options.selectedEdgeId) return [0, 255, 0, 100];
      if (d.id === options.hoveredEdgeId) return [255, 255, 0, 80];
      return [255, 100, 0, 60];
    },
    getLineColor: [255, 255, 255, 200],
    getLineWidth: 2,
    lineWidthUnits: 'pixels',
    pickable: true,
    onClick: info => {
      if (info.object && options.onClick) {
        options.onClick(info.object);
      }
    },
    updateTriggers: {
      getFillColor: [options.selectedEdgeId, options.hoveredEdgeId],
    },
  });
}
```

### 4. Update Texture Mode State

```typescript
// src/hooks/useTextureMode.ts

export interface TextureModeState {
  enabled: boolean;
  selectedBuildingId: string | null;
  selectedFacadeId: string | null;  // Add this
  facadeEdges: FacadeEdge[];        // Add this
}

// Add facade selection
const selectFacade = useCallback((facadeId: string | null) => {
  setState(prev => ({
    ...prev,
    selectedFacadeId: facadeId,
  }));
}, []);

// When building is selected, extract its edges
useEffect(() => {
  if (selectedBuildingId) {
    const building = findBuildingById(selectedBuildingId);
    if (building) {
      const edges = extractFacadeEdges(
        selectedBuildingId,
        building.geometry.coordinates[0]
      );
      setState(prev => ({ ...prev, facadeEdges: edges }));
    }
  } else {
    setState(prev => ({ ...prev, facadeEdges: [], selectedFacadeId: null }));
  }
}, [selectedBuildingId]);
```

### 5. Integrate in ZurichViewer

```typescript
// In ZurichViewer.tsx

const {
  enabled,
  selectedBuildingId,
  selectedFacadeId,
  facadeEdges,
  selectFacade,
} = useTextureMode();

// Show facade edges when building is selected
const facadeLayer = selectedBuildingId ? createFacadePolygonsLayer(
  facadeEdges,
  {
    selectedEdgeId: selectedFacadeId,
    buildingHeight: selectedBuildingHeight,
    baseAltitude: 420,
    onClick: (edge) => selectFacade(edge.id),
  }
) : null;

const layers = [
  buildingsLayer,
  facadeLayer,  // Add after buildings
  // ... textures, etc.
].filter(Boolean);
```

### 6. Update Mode Indicator

```typescript
// In TextureModeIndicator.tsx

{selectedBuildingId && !selectedFacadeId && (
  <div className="selection-hint">
    Click a facade edge to select it
  </div>
)}

{selectedFacadeId && (
  <div className="selection-info">
    Facade selected - ready for texture
    <button onClick={() => /* open upload */}>
      Upload Photo
    </button>
  </div>
)}
```

## Verification

1. Run `pnpm type-check` - no errors
2. Open viewer, press T, click a building
3. Verify:
   - [ ] Facade edges/polygons appear on selected building
   - [ ] Edges are orange by default
   - [ ] Hovering shows yellow highlight
   - [ ] Clicking selects (green)
   - [ ] Only one facade selected at a time
   - [ ] Clicking different building resets facade selection

## Files Created/Modified

- `src/utils/facadeGeometry.ts` (extended)
- `src/layers/FacadeEdgesLayer.ts` (new) OR
- `src/layers/FacadePolygonsLayer.ts` (new)
- `src/hooks/useTextureMode.ts` (extended)
- `src/components/TextureModeIndicator.tsx` (extended)
- `src/components/ZurichViewer/ZurichViewer.tsx` (modified)

## Next Step

With facade selection working, proceed to [04-photo-upload.md](./04-photo-upload.md) to upload and apply photos.

## Notes

- PolygonLayer is easier to click than PathLayer
- Consider face orientation (normal direction) for camera-facing detection
- Building heights may vary - get from GeoJSON properties
- Some buildings have complex polygons with holes
