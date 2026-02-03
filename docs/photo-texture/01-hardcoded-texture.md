# Step 1: Hardcoded Texture

## Goal

Render a test image on one building facade using deck.gl BitmapLayer. This proves the concept works before adding any interactivity.

## Prerequisites

- Working Zurich 3D viewer with buildings
- A test image (e.g., 512x512 brick texture)

## What You'll Learn

- How BitmapLayer positions images in 3D space
- Coordinate math for building facades
- Z-fighting prevention techniques

## Implementation

### 1. Add Test Image

Place a test texture in the public folder:

```
public/
└── textures/
    └── test-facade.jpg  # Any image, ~512x512
```

### 2. Pick a Target Building

Choose a building near the spawn point. You need its polygon coordinates from the GeoJSON.

```typescript
// Example: A building near Zurich HB
const TARGET_BUILDING_ID = 'building_123'; // Pick from your data

// Extract one facade (4 corners) from the building polygon
// Buildings are typically rectangles, so pick 2 adjacent vertices
// and extrude them to the building height
```

### 3. Calculate Facade Quad

```typescript
// src/utils/facadeGeometry.ts

interface FacadeQuad {
  // 4 corners in [lng, lat, altitude] format
  // Counter-clockwise from bottom-left
  bottomLeft: [number, number, number];
  bottomRight: [number, number, number];
  topRight: [number, number, number];
  topLeft: [number, number, number];
}

export function extractFacade(
  polygon: number[][], // Building footprint [[lng, lat], ...]
  edgeIndex: number,   // Which edge (0 = first two vertices)
  baseAltitude: number,
  buildingHeight: number
): FacadeQuad {
  const p1 = polygon[edgeIndex];
  const p2 = polygon[(edgeIndex + 1) % polygon.length];

  return {
    bottomLeft: [p1[0], p1[1], baseAltitude],
    bottomRight: [p2[0], p2[1], baseAltitude],
    topRight: [p2[0], p2[1], baseAltitude + buildingHeight],
    topLeft: [p1[0], p1[1], baseAltitude + buildingHeight],
  };
}
```

### 4. Create BitmapLayer

```typescript
// src/layers/FacadeTextureLayer.ts

import { BitmapLayer } from '@deck.gl/layers';
import type { FacadeQuad } from '../utils/facadeGeometry';

export function createFacadeTextureLayer(
  id: string,
  imageUrl: string,
  facade: FacadeQuad
) {
  return new BitmapLayer({
    id,
    image: imageUrl,
    bounds: [
      facade.bottomLeft,
      facade.bottomRight,
      facade.topRight,
      facade.topLeft,
    ],
    // Prevent z-fighting with building geometry
    parameters: {
      depthTest: true,
      depthWriteEnabled: false,
    },
  });
}
```

### 5. Add to ZurichViewer

```typescript
// In ZurichViewer.tsx

import { createFacadeTextureLayer } from '@/layers/FacadeTextureLayer';
import { extractFacade } from '@/utils/facadeGeometry';

// Inside the component:
const testFacade = extractFacade(
  targetBuildingPolygon,
  0, // First edge
  420, // Base altitude (Zurich is ~400m)
  15  // Building height in meters
);

const textureLayer = createFacadeTextureLayer(
  'test-texture',
  '/textures/test-facade.jpg',
  testFacade
);

// Add to layers array
const layers = [
  buildingsLayer,
  textureLayer, // Add after buildings
  // ... other layers
];
```

## Verification

1. Run `pnpm type-check` - no errors
2. Open viewer in browser (manually, don't start dev server)
3. Navigate to the target building
4. Verify:
   - [ ] Image appears on the building face
   - [ ] Image is correctly oriented (not flipped/rotated)
   - [ ] No z-fighting flicker
   - [ ] Image scales with building height

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Image not visible | Check bounds coordinates are in WGS84 |
| Image underground | Verify altitude matches terrain |
| Z-fighting | Offset facade slightly outward (0.1m) |
| Wrong orientation | Reverse the bounds array order |
| Blurry texture | Use higher resolution source image |

## Files Created/Modified

- `public/textures/test-facade.jpg` (new)
- `src/utils/facadeGeometry.ts` (new)
- `src/layers/FacadeTextureLayer.ts` (new)
- `src/components/ZurichViewer/ZurichViewer.tsx` (modified)

## Next Step

Once this works, proceed to [02-building-selection.md](./02-building-selection.md) to make building selection interactive.

## Notes

- BitmapLayer bounds expects corners in specific order
- Altitude is in meters above sea level
- Building heights come from GeoJSON properties
- Test with a simple grid image first to verify orientation
