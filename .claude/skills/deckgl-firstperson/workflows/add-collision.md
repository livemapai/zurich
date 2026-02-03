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
