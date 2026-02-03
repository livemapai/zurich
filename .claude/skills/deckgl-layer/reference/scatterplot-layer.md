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
