---
name: deckgl-firstperson
description: Implement first-person navigation with WASD controls, mouse look, collision detection, and terrain following. Use when building walkthrough experiences.
allowed-tools: Read, Write, Edit, Glob, Grep
---

# deck.gl First-Person Navigation Skill

Implements complete first-person walkthrough controls for deck.gl applications.

## Features

- **WASD Movement:** Keyboard-based walking/running
- **Mouse Look:** Pointer lock for camera control
- **Collision Detection:** RBush spatial indexing for buildings
- **Terrain Following:** Ground-locked altitude with smooth transitions

## Prerequisites

- [ ] deck.gl v9 installed
- [ ] React 19 setup complete
- [ ] `src/types/index.ts` with FirstPersonViewState type
- [ ] rbush installed (`pnpm list rbush`)

## Core Concepts

### FirstPersonView Coordinate System

deck.gl's FirstPersonView uses:
```typescript
interface FirstPersonViewState {
  position: [lng, lat, altitude]; // WGS84 + meters
  bearing: number;  // 0=North, 90=East, 180=South, 270=West
  pitch: number;    // -90=up, 0=level, 90=down
}
```

### Movement Calculation

Movement is calculated in meters, then converted to degrees:
```typescript
// Bearing-relative movement
const dx = Math.sin(bearing * DEG_TO_RAD) * velocity.forward;
const dy = Math.cos(bearing * DEG_TO_RAD) * velocity.forward;

// Convert meters to degrees (at Zurich latitude)
const dLng = dx / 73000;  // meters per degree longitude
const dLat = dy / 111000; // meters per degree latitude
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
