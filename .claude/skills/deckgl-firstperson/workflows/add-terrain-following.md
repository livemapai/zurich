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
