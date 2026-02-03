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
