# FirstPersonViewState Pitfalls

Common mistakes and confusions when working with deck.gl FirstPersonView.

## Pitfall 1: Position Array is METERS, Not Degrees

**Wrong:**
```typescript
// WRONG - treating position as [lng, lat, alt]
const viewState = {
  longitude: 8.54,
  latitude: 47.37,
  position: [8.541, 47.376, 410], // These are NOT longitude/latitude!
};
```

**Correct:**
```typescript
// CORRECT - position is meter offset [east, north, altitude]
const viewState = {
  longitude: 8.54,  // Geographic anchor in degrees
  latitude: 47.37,  // Geographic anchor in degrees
  position: [0, 0, 410], // Meter offset from anchor
};
```

**Why?** The position array is a meter offset from the geographic anchor (longitude/latitude). Putting degree values in position will teleport your camera thousands of kilometers away.

## Pitfall 2: Pitch Direction is Inverted

Pitch values are opposite to intuition:

| Pitch | Direction |
|-------|-----------|
| -90 | Looking straight UP |
| 0 | Looking at horizon |
| +90 | Looking straight DOWN |

**Common mistake:**
```typescript
// WRONG - expecting positive = up
if (lookingUp) {
  pitch += 5; // Actually makes you look DOWN
}
```

**Correct:**
```typescript
// CORRECT - negative = up
if (lookingUp) {
  pitch -= 5; // Look UP (toward sky)
}
```

## Pitfall 3: Bearing Convention

Bearing is measured clockwise from North:

| Bearing | Direction |
|---------|-----------|
| 0 | North |
| 90 | East |
| 180 | South |
| 270 | West |

**Common mistake:**
```typescript
// WRONG - assuming standard math angle (0 = East, counter-clockwise)
const directionX = Math.cos(bearing * DEG_TO_RAD);
const directionY = Math.sin(bearing * DEG_TO_RAD);
```

**Correct:**
```typescript
// CORRECT - convert bearing to math angle
// bearing 0 = North = +Y, bearing 90 = East = +X
const angleRad = (90 - bearing) * DEG_TO_RAD;
const directionX = Math.cos(angleRad);
const directionY = Math.sin(angleRad);
```

## Pitfall 4: Wrong METERS_PER_DEGREE Constants

Using incorrect conversion constants leads to movement at wrong speed.

**Wrong:**
```typescript
// WRONG - these are approximations that cause drift
const metersPerDegreeLng = 73000; // Too small
const metersPerDegreeLat = 111000; // Close but inaccurate
```

**Correct:**
```typescript
// CORRECT - use project constants
import { METERS_PER_DEGREE } from '@/types';

const dLng = velocityX * dt / METERS_PER_DEGREE.lng; // 75500
const dLat = velocityY * dt / METERS_PER_DEGREE.lat; // 111320
```

## Pitfall 5: Altitude vs Ground Elevation

Altitude is absolute (above sea level), not relative to terrain.

**Wrong:**
```typescript
// WRONG - treating altitude as height above ground
const altitude = 1.7; // Eye height... but where is ground?
```

**Correct:**
```typescript
// CORRECT - altitude = ground elevation + eye height
const groundElevation = 408; // Zurich base
const eyeHeight = 1.7;
const altitude = groundElevation + eyeHeight; // 409.7m above sea level
```

## Pitfall 6: Forgetting to Convert Units

Movement velocity is in m/s, but position update needs degrees.

**Wrong:**
```typescript
// WRONG - adding meters to degrees
newLongitude = viewState.longitude + velocityX * deltaTime;
// velocityX is in m/s, longitude is in degrees!
```

**Correct:**
```typescript
// CORRECT - convert to degrees first
const dLng = (velocityX * deltaTime) / METERS_PER_DEGREE.lng;
newLongitude = viewState.longitude + dLng;
```

## Pitfall 7: Pitch Clamping

Pitch must be clamped to prevent camera flipping.

**Wrong:**
```typescript
// WRONG - no clamping
newPitch = viewState.pitch + mouseDeltaY * sensitivity;
// Can exceed -90 or +90, causing camera flip
```

**Correct:**
```typescript
// CORRECT - clamp to safe range
const newPitch = Math.max(-89, Math.min(89,
  viewState.pitch + mouseDeltaY * sensitivity
));
```

## Pitfall 8: Stale Closures in Game Loop

Using state directly in requestAnimationFrame causes stale values.

**Wrong:**
```typescript
// WRONG - viewState will be stale
useEffect(() => {
  const loop = () => {
    // viewState is captured at effect creation time
    doSomething(viewState);
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}, []); // Empty deps = stale closure
```

**Correct:**
```typescript
// CORRECT - use ref for current value
const viewStateRef = useRef(viewState);
viewStateRef.current = viewState;

useEffect(() => {
  const loop = () => {
    // Always gets current value
    doSomething(viewStateRef.current);
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}, []);
```

## Pitfall 9: Delta Time in Wrong Units

Delta time must be in seconds for velocity calculations.

**Wrong:**
```typescript
// WRONG - delta time in milliseconds
const deltaTime = currentTime - lastTime; // e.g., 16.67ms
const distance = speed * deltaTime; // Way too large!
```

**Correct:**
```typescript
// CORRECT - convert to seconds
const deltaTime = (currentTime - lastTime) / 1000; // e.g., 0.01667s
const distance = speed * deltaTime; // Correct distance
```

## Pitfall 10: Updating Position Without Spreading

React state updates need new object references.

**Wrong:**
```typescript
// WRONG - mutating existing object
viewState.longitude += dLng;
setViewState(viewState); // React may not detect change
```

**Correct:**
```typescript
// CORRECT - create new object
setViewState({
  ...viewState,
  longitude: viewState.longitude + dLng,
});
```

## Quick Reference Card

| Property | Type | Unit | Notes |
|----------|------|------|-------|
| longitude | number | degrees | WGS84, geographic anchor |
| latitude | number | degrees | WGS84, geographic anchor |
| position[0] | number | meters | East offset from anchor |
| position[1] | number | meters | North offset from anchor |
| position[2] | number | meters | Altitude above sea level |
| bearing | number | degrees | 0=N, 90=E, clockwise |
| pitch | number | degrees | Negative=up, positive=down |
