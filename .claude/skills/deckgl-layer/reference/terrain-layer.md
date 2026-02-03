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
