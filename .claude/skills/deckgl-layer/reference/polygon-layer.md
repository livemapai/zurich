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
