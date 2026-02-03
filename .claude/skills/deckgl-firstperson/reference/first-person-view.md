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

## ViewState

```typescript
interface FirstPersonViewState {
  // Camera position in [longitude, latitude, altitude]
  // Altitude is in METERS above sea level
  position: [number, number, number];

  // Horizontal rotation (0 = North, 90 = East)
  bearing: number;

  // Vertical rotation (-90 = up, 90 = down)
  pitch: number;
}
```

## With DeckGL React Component

```tsx
import DeckGL from '@deck.gl/react';
import { FirstPersonView } from '@deck.gl/core';

function Viewer() {
  const [viewState, setViewState] = useState({
    position: [8.541694, 47.376888, 2],
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

1. **Position is WGS84**: longitude, latitude in degrees, altitude in meters
2. **Bearing is clockwise from North**: 0°=N, 90°=E, 180°=S, 270°=W
3. **Pitch limits**: Usually clamp to [-89, 89] where negative = looking up
4. **Controller: false**: Required for custom WASD controls
5. **near/far in meters**: Set appropriately for your scene scale
