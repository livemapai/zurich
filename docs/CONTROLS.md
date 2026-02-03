# Controls System

## Overview

The controls system implements first-person navigation using:
- WASD keyboard movement
- Mouse look with Pointer Lock API
- Collision detection with wall sliding
- Terrain following for ground-locked movement

## Input Handling

### Keyboard State (useKeyboardState)

Tracks which movement keys are currently pressed:

```typescript
interface KeyboardState {
  forward: boolean;  // W or ArrowUp
  backward: boolean; // S or ArrowDown
  left: boolean;     // A or ArrowLeft
  right: boolean;    // D or ArrowRight
  run: boolean;      // Shift
  jump: boolean;     // Space (not implemented)
}
```

**Key Features:**
- Resets all keys on window blur (prevents stuck keys)
- Ignores input when typing in form fields
- Supports both WASD and arrow keys

### Mouse Look (useMouseLook)

Captures mouse movement for camera rotation:

```typescript
interface MouseLookState {
  isLocked: boolean;
  consumeDelta: () => { x: number; y: number };
  requestLock: () => void;
  exitLock: () => void;
}
```

**Key Features:**
- Uses Pointer Lock API for raw mouse input
- Accumulates movement between frames
- Applies sensitivity multiplier
- Resets on lock release

## Movement Calculation

### MovementController

Converts keyboard input to world-space velocity:

```
Keyboard State
      │
      ▼
┌─────────────────┐
│ Local Direction │
│ forward: +Y     │
│ right: +X       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Normalize     │
│ (diagonal fix)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Apply Bearing   │
│ Rotation        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ World Velocity  │
│ (m/s)           │
└─────────────────┘
```

**Bearing Rotation Formula:**
```typescript
// Bearing: 0 = North, 90 = East, 180 = South, 270 = West
const bearingRad = bearing * DEG_TO_RAD;
const sinB = Math.sin(bearingRad);
const cosB = Math.cos(bearingRad);

// Local to world rotation
const worldX = localX * cosB + localY * sinB;
const worldY = -localX * sinB + localY * cosB;
```

**Movement Speeds:**
| Mode | Speed |
|------|-------|
| Walk | 4 m/s |
| Run  | 8 m/s |

## Camera Control

### CameraController

Manages FirstPersonViewState updates:

**Mouse Look Application:**
```typescript
// deltaX → bearing (horizontal rotation)
bearing = normalizeAngle(bearing + deltaX);

// deltaY → pitch (vertical rotation, inverted)
pitch = clamp(pitch - deltaY, -89, 89);
```

**Position Update:**
```typescript
// Convert velocity (m/s) to degrees
const cosLat = Math.cos(lat * DEG_TO_RAD);
const metersPerDegreeLng = METERS_PER_DEGREE.lat * cosLat;

const dLng = (velocity.x * deltaTime) / metersPerDegreeLng;
const dLat = (velocity.y * deltaTime) / METERS_PER_DEGREE.lat;

newPosition = [lng + dLng, lat + dLat, alt];
```

## Collision Detection

### SpatialIndex (RBush)

Efficient spatial queries for building collision:

```
┌─────────────────────────────────────┐
│           RBush Tree                │
│  ┌─────────────────────────────┐   │
│  │    Bounding Box Index       │   │
│  │    (O(log n) queries)       │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│      Point-in-Polygon Test          │
│  (ray casting algorithm)            │
└─────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│      Wall Normal Calculation        │
│  (nearest edge perpendicular)       │
└─────────────────────────────────────┘
```

### Wall Sliding

When collision occurs, velocity is projected along the wall:

```typescript
function slideAlongWall(velocity: Vec2, wallNormal: Vec2): Vec2 {
  // Project velocity onto wall normal
  const dot = velocity.x * wallNormal.x + velocity.y * wallNormal.y;

  // If moving away from wall, no change needed
  if (dot >= 0) return velocity;

  // Remove component into wall
  return {
    x: velocity.x - dot * wallNormal.x,
    y: velocity.y - dot * wallNormal.y,
  };
}
```

## Terrain Following

### TerrainSampler

Queries elevation at player position:

```typescript
// Sample terrain at position
const groundElevation = terrainSampler.sample(lng, lat);

// Set camera altitude to ground + eye height
const targetAlt = groundElevation + eyeHeight;

// Smooth transition (optional)
const newAlt = lerp(currentAlt, targetAlt, 0.3);
```

**Default Zurich Elevation:** 408m (when no terrain data)

## Game Loop

### Frame Update Sequence

```
1. Get delta time (clamped to max 100ms)
         │
         ▼
2. Consume mouse delta
         │
         ▼
3. Apply mouse look to bearing/pitch
         │
         ▼
4. Calculate velocity from keyboard
         │
         ▼
5. Propose new position
         │
         ▼
6. Check collision at proposed position
         │
    ┌────┴────┐
    │         │
    ▼         ▼
7a. No collision:   7b. Collision:
    Keep velocity       Calculate wall slide
                        Check slide position
         │                    │
         └────────┬───────────┘
                  │
                  ▼
8. Apply position update
         │
         ▼
9. Query terrain elevation
         │
         ▼
10. Set altitude (smoothed)
         │
         ▼
11. Update React state → re-render
```

## Configuration

All control parameters are in `src/lib/config.ts`:

```typescript
CONFIG.player = {
  height: 1.8,        // Total height (meters)
  eyeHeight: 1.7,     // Camera height (meters)
  collisionRadius: 0.3, // Collision radius (meters)
  stepHeight: 0.3,    // Max step height (not implemented)
};

CONFIG.movement = {
  walk: 4.0,          // Walk speed (m/s)
  run: 8.0,           // Run speed (m/s)
  turnRate: 90,       // Keyboard turn (deg/s, not used)
};

CONFIG.mouse = {
  sensitivityX: 0.1,  // Horizontal sensitivity (deg/pixel)
  sensitivityY: 0.1,  // Vertical sensitivity (deg/pixel)
  invertY: false,     // Invert vertical axis
};

CONFIG.camera = {
  pitchMin: -89,      // Look down limit (degrees)
  pitchMax: 89,       // Look up limit (degrees)
  minAltitude: 0.5,   // Minimum altitude (meters)
};
```
