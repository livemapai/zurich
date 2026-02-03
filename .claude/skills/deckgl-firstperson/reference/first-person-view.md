# deck.gl FirstPersonView Reference

## Import

```typescript
import { Deck } from '@deck.gl/core';
import { FirstPersonView } from '@deck.gl/core';
```

## View Configuration

```typescript
const view = new FirstPersonView({
  id: 'first-person',

  // Controller (disable for custom controls)
  controller: false,

  // Field of view (vertical, in degrees)
  fovy: 75,

  // Clipping planes (in meters)
  near: 0.1,
  far: 10000,
});
```

## ViewState (Dual-Anchor System)

deck.gl FirstPersonView uses a **dual-anchor coordinate system** for high floating-point precision:

```typescript
interface FirstPersonViewState {
  // Geographic anchor point (WGS84)
  longitude: number;  // Degrees
  latitude: number;   // Degrees

  // Meter offset from the geographic anchor
  // [east, north, altitude] in METERS
  position: [number, number, number];

  // Horizontal rotation (0 = North, clockwise)
  bearing: number;

  // Vertical rotation
  // -90 = looking straight UP
  //   0 = looking at horizon
  // +90 = looking straight DOWN
  pitch: number;
}
```

### Why Dual-Anchor?

At high zoom levels (street-level view), using longitude/latitude directly for small movements causes floating-point precision issues. The dual-anchor system solves this:

- **Geographic anchor** (`longitude`, `latitude`): Fixed reference point
- **Position offset** (`position`): High-precision meter offsets

### Movement Strategies

There are two valid approaches:

**Strategy A: Move via longitude/latitude (our implementation)**
```typescript
// Calculate movement in meters, convert to degrees
const dLng = velocityX * deltaTime / METERS_PER_DEGREE.lng;
const dLat = velocityY * deltaTime / METERS_PER_DEGREE.lat;

newViewState = {
  ...viewState,
  longitude: viewState.longitude + dLng,
  latitude: viewState.latitude + dLat,
  position: [0, 0, altitude], // Keep horizontal offset at 0
};
```

**Strategy B: Move via position offset (alternative)**
```typescript
// Calculate movement in meters, accumulate in position
newViewState = {
  ...viewState,
  position: [
    viewState.position[0] + velocityX * deltaTime,
    viewState.position[1] + velocityY * deltaTime,
    altitude,
  ],
};
// Periodically re-anchor to prevent drift
```

### Position Array Breakdown

```typescript
position: [east, north, altitude]
```

| Index | Name | Unit | Description |
|-------|------|------|-------------|
| `[0]` | east | meters | East offset from anchor (positive = east) |
| `[1]` | north | meters | North offset from anchor (positive = north) |
| `[2]` | altitude | meters | Height above sea level (NOT relative!) |

**Common mistake:** Treating `position[0]` as longitude or `position[1]` as latitude. They are **meter offsets**, not degrees!

## Vertical Movement (Fly Mode)

Altitude is controlled via `position[2]`:

```typescript
// Fly up/down with Q/E keys
const newAltitude = viewState.position[2] + velocityZ * deltaTime;

// Clamp to valid range
const clampedAlt = Math.max(minAltitude, Math.min(maxAltitude, newAltitude));

newViewState = {
  ...viewState,
  position: [0, 0, clampedAlt],
};
```

When flying is active, you may want to disable terrain following to allow free vertical movement.

## With DeckGL React Component

```tsx
import DeckGL from '@deck.gl/react';
import { FirstPersonView } from '@deck.gl/core';
import { ZURICH_CENTER, ZURICH_BASE_ELEVATION } from '@/types';
import { CONFIG } from '@/lib/config';

function Viewer() {
  const [viewState, setViewState] = useState({
    // Geographic anchor
    longitude: ZURICH_CENTER[0], // 8.5437
    latitude: ZURICH_CENTER[1],  // 47.3739
    // Meter offset [east, north, altitude]
    position: [0, 0, ZURICH_BASE_ELEVATION + CONFIG.player.eyeHeight], // 409.7m
    bearing: 0,
    pitch: 0,
  });

  return (
    <DeckGL
      views={new FirstPersonView({ fovy: 75, near: 0.1, far: 10000 })}
      viewState={viewState}
      onViewStateChange={({ viewState }) => setViewState(viewState)}
      controller={false} // Disable default controller for custom controls
      layers={[/* ... */]}
    />
  );
}
```

## Important Notes

1. **Position is METERS, not degrees**: `position[0]` and `position[1]` are meter offsets
2. **Longitude/Latitude are the anchor**: Use these for geographic position
3. **Altitude is absolute**: `position[2]` is meters above sea level
4. **Bearing is clockwise from North**: 0=N, 90=E, 180=S, 270=W
5. **Pitch inverted from intuition**: Negative = looking up, positive = looking down
6. **Controller: false required**: For custom WASD controls, disable the built-in controller

## Zurich-Specific Values

```typescript
// From src/lib/constants.ts
const ZURICH_CENTER: LngLat = [8.5437, 47.3739];
const ZURICH_BASE_ELEVATION = 408; // meters above sea level

// Conversion factors at 47°N latitude
const METERS_PER_DEGREE = {
  lng: 75500,  // 1° longitude ≈ 75,500m
  lat: 111320, // 1° latitude ≈ 111,320m
};
```

## External References

- [deck.gl FirstPersonView API](https://deck.gl/docs/api-reference/core/first-person-view)
- [deck.gl FirstPersonController](https://deck.gl/docs/api-reference/core/first-person-controller)
