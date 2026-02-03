---
name: deckgl-firstperson
description: Implement first-person navigation with WASD controls, mouse look, collision detection, and terrain following. Use when building walkthrough experiences.
allowed-tools: Read, Write, Edit, Glob, Grep
---

# deck.gl First-Person Navigation Skill

Implements complete first-person walkthrough controls for deck.gl applications.

## Features

- **WASD Movement:** Keyboard-based walking/running
- **Q/E Fly Mode:** Vertical movement (up/down) with altitude clamping
- **Mouse Look:** Pointer lock for camera control
- **Collision Detection:** RBush spatial indexing for buildings
- **Terrain Following:** Ground-locked altitude with smooth transitions

## Prerequisites

- [ ] deck.gl v9 installed
- [ ] React 19 setup complete
- [ ] `src/types/index.ts` with FirstPersonViewState type
- [ ] rbush installed (`pnpm list rbush`)

## Core Concepts

### FirstPersonView Coordinate System (Dual-Anchor)

deck.gl's FirstPersonView uses a **dual-anchor system** for high precision:

```typescript
interface FirstPersonViewState {
  longitude: number;  // Geographic anchor (WGS84 degrees)
  latitude: number;   // Geographic anchor (WGS84 degrees)
  position: [number, number, number]; // Offset [east, north, up] in METERS
  bearing: number;    // 0=North, 90=East, 180=South, 270=West (clockwise)
  pitch: number;      // -90=up, 0=horizon, +90=down
}
```

**Why dual-anchor?** This prevents floating-point precision issues at high zoom.

- `longitude`/`latitude`: Fixed geographic reference point
- `position[0]`: East offset in meters (NOT longitude!)
- `position[1]`: North offset in meters (NOT latitude!)
- `position[2]`: Altitude in meters above sea level

### Movement Pattern

Our implementation moves via `longitude`/`latitude` directly:

```typescript
// From src/lib/constants.ts - use project constants
import { METERS_PER_DEGREE } from '@/lib/constants';

// Velocity in m/s → position delta in degrees
const dLng = (velocity.x * deltaTime) / METERS_PER_DEGREE.lng; // 75500 at 47°N
const dLat = (velocity.y * deltaTime) / METERS_PER_DEGREE.lat; // 111320

// Update geographic anchor directly
newViewState = {
  ...viewState,
  longitude: viewState.longitude + dLng,
  latitude: viewState.latitude + dLat,
};

// position[0] and position[1] stay at 0
// position[2] is altitude in meters
```

### Fly Mode (Q/E Keys)

Vertical movement uses `position[2]` for altitude:

```typescript
// Q = up, E = down (same speed as horizontal movement)
if (keyboard.up) velocity.z += speed;
if (keyboard.down) velocity.z -= speed;

// Apply vertical movement directly to position[2]
const newAltitude = viewState.position[2] + velocity.z * deltaTime;
newViewState = {
  ...viewState,
  position: [0, 0, Math.max(minAltitude, Math.min(maxAltitude, newAltitude))],
};
```

## Workflow

### Full Implementation (All Features)

1. [ ] Create `useKeyboardState` hook
2. [ ] Create `useMouseLook` hook
3. [ ] Create `useGameLoop` hook
4. [ ] Create `MovementController` system
5. [ ] Create `CameraController` system
6. [ ] Create `SpatialIndex` for collision
7. [ ] Create `useCollisionDetection` hook
8. [ ] Create `useTerrainElevation` hook
9. [ ] Integrate in main component
10. [ ] Verify with type-check

### Partial Implementation (Sub-workflows)

See `workflows/` directory:
- `add-wasd-controls.md` - Just movement, no collision
- `add-collision.md` - Add collision to existing movement
- `add-terrain-following.md` - Add terrain to existing system
- `add-fly-mode.md` - Add Q/E vertical movement

## Reference Files

- `reference/first-person-view.md` - deck.gl FPV specifics
- `reference/game-loop.md` - RAF timing patterns
- `reference/collision-system.md` - RBush + wall sliding
- `reference/pointer-lock.md` - Browser Pointer Lock API

## Templates

All templates are complete implementations ready to copy:
- `use-keyboard-state.template.ts`
- `use-mouse-look.template.ts`
- `use-game-loop.template.ts`
- `movement-controller.template.ts`
- `spatial-index.template.ts`
- `camera-controller.template.ts`

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Camera moves wrong direction | Bearing convention wrong | Check: 0=North, increases clockwise |
| Movement too fast/slow | Delta time not in seconds | Ensure deltaTime is seconds, not ms |
| Pointer lock fails | Not in click handler | Must request from user gesture |
| Collision not detecting | RBush not populated | Call `load()` before checking |
| Jittery movement | Float precision | Use doubles, reduce calculation frequency |
| Falls through terrain | Terrain not loaded | Add loading check before movement |
| Position shows degrees | Confusing position with lng/lat | `position` is meter offsets, NOT degrees! |
| Wrong METERS_PER_DEGREE | Wrong constant value | Use 75500 for lng, 111320 for lat at 47°N |
| Fly mode not working | Missing up/down in KeyboardState | Add `up` and `down` boolean fields |
| Can't fly below ground | Missing altitude clamping | Use `Math.max(minAltitude, altitude)` |

## Recovery

If partial implementation breaks:
1. Remove all new hooks from `src/hooks/`
2. Remove all new systems from `src/systems/`
3. Revert changes to main component
4. Run `pnpm type-check`
5. Re-run skill from start

## External References

- [deck.gl FirstPersonView](https://deck.gl/docs/api-reference/core/first-person-view)
- [Pointer Lock API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Pointer_Lock_API)
- [RBush](https://github.com/mourner/rbush)
- [requestAnimationFrame](https://developer.mozilla.org/en-US/docs/Web/API/window/requestAnimationFrame)
