# Research: deck.gl BitmapLayer

## Overview

BitmapLayer renders a bitmap (image) at specified coordinates. It's designed for georeferenced images like satellite tiles but works perfectly for facade textures.

## Basic Usage

```typescript
import { BitmapLayer } from '@deck.gl/layers';

const layer = new BitmapLayer({
  id: 'bitmap-layer',
  image: '/path/to/image.jpg',  // URL or ImageData
  bounds: [
    [-122.45, 37.78],  // Southwest corner [lng, lat]
    [-122.43, 37.78],  // Southeast corner
    [-122.43, 37.80],  // Northeast corner
    [-122.45, 37.80],  // Northwest corner
  ],
});
```

## Bounds Parameter

The `bounds` parameter defines where the image is placed. It accepts:

### 2D Bounds (Flat on ground)

```typescript
// [west, south, east, north] - Axis-aligned rectangle
bounds: [-122.45, 37.78, -122.43, 37.80]

// Or 4 corners for arbitrary quadrilateral
bounds: [
  [lng1, lat1],  // Bottom-left
  [lng2, lat2],  // Bottom-right
  [lng3, lat3],  // Top-right
  [lng4, lat4],  // Top-left
]
```

### 3D Bounds (With altitude)

For vertical facades, include altitude as the third coordinate:

```typescript
bounds: [
  [8.5390, 47.3775, 420],   // Bottom-left [lng, lat, altitude]
  [8.5395, 47.3775, 420],   // Bottom-right
  [8.5395, 47.3775, 435],   // Top-right (15m higher)
  [8.5390, 47.3775, 435],   // Top-left
]
```

**Important:** Altitude is in meters above sea level, matching deck.gl's coordinate system.

## Corner Order

BitmapLayer expects corners in this order:

```
           3 ─────────── 2
           │             │
           │   IMAGE     │
           │             │
           0 ─────────── 1

0: Bottom-left  (SW)
1: Bottom-right (SE)
2: Top-right    (NE)
3: Top-left     (NW)
```

If your image appears flipped or rotated, check the corner order.

## Z-Fighting Prevention

When placing BitmapLayer on building surfaces, z-fighting (flickering) can occur because both geometries occupy the same space.

### Solution 1: Depth Write Disabled

```typescript
new BitmapLayer({
  // ...
  parameters: {
    depthTest: true,      // Still test depth
    depthWriteEnabled: false,  // Don't write to depth buffer
  },
});
```

### Solution 2: Polygon Offset

```typescript
new BitmapLayer({
  // ...
  parameters: {
    depthTest: true,
    polygonOffset: true,
    polygonOffsetFactor: -1,
    polygonOffsetUnits: -1,
  },
});
```

### Solution 3: Offset Geometry

Push the texture slightly away from the building surface:

```typescript
function offsetFacade(facade: FacadeQuad, offset: number): FacadeQuad {
  // Calculate facade normal direction
  const normal = calculateOutwardNormal(facade);

  // Offset all points by normal * offset
  return {
    bottomLeft: [
      facade.bottomLeft[0] + normal[0] * offset,
      facade.bottomLeft[1] + normal[1] * offset,
      facade.bottomLeft[2],
    ],
    // ... repeat for other corners
  };
}

// Use 0.1m offset (10cm)
const offsetFacade = offsetFacade(originalFacade, 0.1);
```

## Image Sources

BitmapLayer accepts multiple image source types:

```typescript
// URL string
image: '/textures/facade.jpg'

// Data URL
image: 'data:image/jpeg;base64,/9j/4AAQ...'

// HTMLImageElement
const img = new Image();
img.src = '/textures/facade.jpg';
image: img

// ImageData (from canvas)
const ctx = canvas.getContext('2d');
const imageData = ctx.getImageData(0, 0, width, height);
image: imageData

// ImageBitmap (best performance)
const bitmap = await createImageBitmap(file);
image: bitmap
```

## Performance Considerations

### Many Textures

Each BitmapLayer is a separate draw call. With many textures:

1. **Texture Atlas**: Combine multiple images into one large image
2. **LOD**: Only show nearby textures at full resolution
3. **Culling**: Don't render off-screen textures

```typescript
// Simple frustum culling
const visibleTextures = textures.filter(t =>
  isInViewport(t.bounds, viewState)
);

const layers = visibleTextures.map(t =>
  new BitmapLayer({ id: t.id, ... })
);
```

### Image Size

Large images impact memory and rendering:

```typescript
// Resize images before use
async function resizeImage(
  img: HTMLImageElement,
  maxSize: number
): Promise<ImageBitmap> {
  let { width, height } = img;

  if (width > maxSize || height > maxSize) {
    const scale = maxSize / Math.max(width, height);
    width = Math.round(width * scale);
    height = Math.round(height * scale);
  }

  return createImageBitmap(img, {
    resizeWidth: width,
    resizeHeight: height,
    resizeQuality: 'high',
  });
}
```

Recommended max texture size: 1024x1024 or 2048x2048.

## Transparency

BitmapLayer supports transparent images (PNG with alpha):

```typescript
new BitmapLayer({
  // ...
  // Transparency is automatic with PNG images
  // For proper blending order, set:
  parameters: {
    blend: true,
    blendFunc: [
      GL.SRC_ALPHA,
      GL.ONE_MINUS_SRC_ALPHA,
    ],
  },
});
```

## Coordinate System Notes

### deck.gl Default

- Longitude: -180 to 180 (West to East)
- Latitude: -90 to 90 (South to North)
- Altitude: meters above sea level

### Zurich Specifics

- Zurich center: ~8.54°E, 47.37°N
- Base altitude: ~400-450m above sea level
- 1 degree longitude ≈ 75,500m at this latitude
- 1 degree latitude ≈ 111,320m

### Converting Meters to Degrees

```typescript
const METERS_PER_DEGREE_LAT = 111320;
const METERS_PER_DEGREE_LNG = 75500; // At Zurich latitude

function metersToDegreesLat(meters: number): number {
  return meters / METERS_PER_DEGREE_LAT;
}

function metersToDegreesLng(meters: number): number {
  return meters / METERS_PER_DEGREE_LNG;
}
```

## Debugging Tips

### Visualize Bounds

```typescript
import { PolygonLayer } from '@deck.gl/layers';

const debugLayer = new PolygonLayer({
  id: 'texture-bounds-debug',
  data: [{ polygon: bounds }],
  getPolygon: d => d.polygon,
  getFillColor: [255, 0, 0, 100],
  getLineColor: [255, 0, 0, 255],
  lineWidthMinPixels: 2,
});
```

### Check Image Loading

```typescript
new BitmapLayer({
  // ...
  onDataLoad: (image) => {
    console.log('Image loaded:', image.width, 'x', image.height);
  },
  onImageLoadError: (error) => {
    console.error('Failed to load image:', error);
  },
});
```

## References

- [deck.gl BitmapLayer docs](https://deck.gl/docs/api-reference/layers/bitmap-layer)
- [deck.gl Coordinate Systems](https://deck.gl/docs/developer-guide/coordinate-systems)
- [WebGL Depth Buffer](https://learnopengl.com/Advanced-OpenGL/Depth-testing)
