# Rendering Layers

## Overview

The application uses deck.gl layers for 3D visualization:

| Layer | Type | Purpose |
|-------|------|---------|
| TerrainLayer | SolidPolygonLayer | Ground plane |
| BuildingsLayer | SolidPolygonLayer | 3D extruded buildings |
| MinimapLayers | Various | Navigation minimap |

## Buildings Layer

### Configuration

```typescript
interface BuildingsLayerConfig {
  id?: string;
  visible?: boolean;
  opacity?: number;
  extruded?: boolean;
  wireframe?: boolean;
  pickable?: boolean;
}
```

### Implementation

Uses `SolidPolygonLayer` for extruded 3D buildings:

```typescript
new SolidPolygonLayer<BuildingFeature>({
  id: 'buildings',
  data: buildings,

  // Geometry
  getPolygon: (d) => d.geometry.coordinates[0],
  extruded: true,
  getElevation: (d) => d.properties.height,

  // Appearance
  getFillColor: [200, 200, 220, 255],
  material: {
    ambient: 0.35,
    diffuse: 0.6,
    shininess: 32,
  },

  // Interaction
  pickable: true,
  autoHighlight: true,
});
```

### Colors

| Element | Color (RGBA) |
|---------|-------------|
| Fill | [200, 200, 220, 255] |
| Highlight | [255, 200, 0, 128] |
| Minimap Fill | [80, 80, 100, 200] |

## Terrain Layer

### Configuration

```typescript
interface TerrainLayerConfig {
  id?: string;
  visible?: boolean;
  opacity?: number;
  color?: [number, number, number, number];
}
```

### Implementation (MVP)

Simple ground plane covering the Zurich area:

```typescript
new SolidPolygonLayer({
  id: 'terrain',
  data: [{
    polygon: [
      [ZURICH_BOUNDS.minLng, ZURICH_BOUNDS.minLat],
      [ZURICH_BOUNDS.maxLng, ZURICH_BOUNDS.minLat],
      [ZURICH_BOUNDS.maxLng, ZURICH_BOUNDS.maxLat],
      [ZURICH_BOUNDS.minLng, ZURICH_BOUNDS.maxLat],
      [ZURICH_BOUNDS.minLng, ZURICH_BOUNDS.minLat],
    ],
  }],
  getPolygon: (d) => d.polygon,
  extruded: false,
  getFillColor: [40, 60, 40, 255],
});
```

### Future: Real Terrain

For actual terrain elevation:

```typescript
import { TerrainLayer } from '@deck.gl/geo-layers';

new TerrainLayer({
  id: 'terrain',
  elevationData: 'terrain-rgb.png',
  texture: 'satellite.jpg',
  bounds: [minLng, minLat, maxLng, maxLat],
  meshMaxError: 2,
  elevationDecoder: {
    rScaler: 6553.6,
    gScaler: 25.6,
    bScaler: 0.1,
    offset: -10000,
  },
});
```

## Minimap Layers

### Configuration

```typescript
interface MinimapLayersConfig {
  buildings: BuildingFeature[] | null;
  playerPosition: [number, number];
  playerBearing: number;
  viewDistance?: number;
  viewAngle?: number;
}
```

### Components

1. **Building Outlines:**
   - Simplified non-extruded polygons
   - Darker fill color
   - No interaction

2. **Player Position:**
   - ScatterplotLayer with single point
   - Red dot at player location

3. **View Cone:**
   - PolygonLayer triangle
   - Semi-transparent orange
   - Shows current viewing direction

### View Cone Calculation

```typescript
function createViewCone(
  position: [number, number],
  bearing: number,
  distance: number,
  angle: number
): number[][] {
  const halfAngle = angle / 2;
  const leftAngle = (bearing - halfAngle) * DEG_TO_RAD;
  const rightAngle = (bearing + halfAngle) * DEG_TO_RAD;

  return [
    position,
    [position[0] + Math.sin(leftAngle) * distance,
     position[1] + Math.cos(leftAngle) * distance],
    [position[0] + Math.sin(rightAngle) * distance,
     position[1] + Math.cos(rightAngle) * distance],
    position, // close
  ];
}
```

## Lighting

### Lighting Effect

```typescript
const lightingEffect = new LightingEffect({
  ambientLight: new AmbientLight({
    color: [255, 255, 255],
    intensity: 1.0,
  }),
  directionalLight: new DirectionalLight({
    color: [255, 255, 240],
    intensity: 1.0,
    direction: [-1, -2, -3],
  }),
});
```

### Material Properties

| Property | Value | Effect |
|----------|-------|--------|
| ambient | 0.35 | Base illumination |
| diffuse | 0.6 | Light scattering |
| shininess | 32 | Specular highlight size |
| specularColor | [60, 64, 70] | Highlight tint |

## Performance

### Layer Memoization

```typescript
const layers = useMemo(() => {
  const result = [];

  if (buildings && buildings.length > 0) {
    result.push(createBuildingsLayer(buildings));
  }

  result.push(createTerrainLayer());

  return result;
}, [buildings]); // Only recreate when buildings change
```

### LOD Considerations

For very large datasets, consider:
- Distance-based detail levels
- Tile-based loading
- Frustum culling (built into deck.gl)
- Instance batching

## Rendering Order

Layers render in array order (first = bottom):

1. Terrain (background)
2. Buildings (3D)
3. (Future: Points of interest)
4. (Future: Paths/routes)

Minimap renders in separate OrthographicView with its own layers.
