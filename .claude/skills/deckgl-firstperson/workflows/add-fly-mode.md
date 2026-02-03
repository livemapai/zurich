# Add Fly Mode (Q/E Vertical Movement)

This workflow adds vertical movement (fly mode) to an existing first-person navigation system.

## Prerequisites

- [ ] Existing WASD movement working
- [ ] `KeyboardState` type defined
- [ ] `useKeyboardState` hook implemented
- [ ] `MovementController` or `calculateVelocity` function
- [ ] Game loop applying velocity to position

## Overview

Fly mode allows vertical movement with Q (up) and E (down) keys. Uses the same speed as horizontal movement (walk/run).

## Steps

### Step 1: Update KeyboardState Type

Add `up` and `down` fields to the keyboard state interface.

**File:** `src/types/index.ts`

```typescript
export interface KeyboardState {
  forward: boolean;
  backward: boolean;
  left: boolean;
  right: boolean;
  up: boolean;    // Q key - fly up (NEW)
  down: boolean;  // E key - fly down (NEW)
  run: boolean;
  jump: boolean;
}
```

### Step 2: Add Q/E Key Mappings

Update the keyboard hook to map Q and E keys.

**File:** `src/hooks/useKeyboardState.ts`

```typescript
const KEY_MAP: Record<string, keyof KeyboardState> = {
  KeyW: 'forward',
  KeyS: 'backward',
  KeyA: 'left',
  KeyD: 'right',
  KeyQ: 'up',       // NEW - Fly up
  KeyE: 'down',     // NEW - Fly down
  // ... existing keys
};
```

### Step 3: Update Empty Keyboard State

If you have a `createEmptyKeyboardState` function, add the new fields.

**File:** `src/systems/MovementController.ts`

```typescript
export function createEmptyKeyboardState(): KeyboardState {
  return {
    forward: false,
    backward: false,
    left: false,
    right: false,
    up: false,    // NEW
    down: false,  // NEW
    run: false,
    jump: false,
  };
}
```

### Step 4: Add Vertical Velocity Calculation

Update the velocity calculation to include vertical movement.

**File:** `src/systems/MovementController.ts`

```typescript
export function calculateVelocity(
  keyboard: KeyboardState,
  bearing: number
): Velocity {
  // ... existing horizontal velocity calculation ...

  // Add vertical movement (fly mode)
  let localZ = 0;
  if (keyboard.up) localZ += 1;
  if (keyboard.down) localZ -= 1;

  return {
    x: worldX * speed,
    y: worldY * speed,
    z: localZ * speed, // Same speed as horizontal
  };
}
```

### Step 5: Update hasMovementInput

Include vertical keys in the movement check.

```typescript
export function hasMovementInput(keyboard: KeyboardState): boolean {
  return (
    keyboard.forward ||
    keyboard.backward ||
    keyboard.left ||
    keyboard.right ||
    keyboard.up ||      // NEW
    keyboard.down       // NEW
  );
}
```

### Step 6: Add Config Values

Add altitude limits to configuration.

**File:** `src/lib/config.ts`

```typescript
player: {
  // ... existing config ...
  minAltitude: 410,  // Just above Zurich ground (~408m)
  maxAltitude: 1000, // Maximum flight height
},
```

### Step 7: Apply Vertical Movement in Game Loop

Update the main component's game loop to handle vertical velocity.

**File:** `src/components/ZurichViewer/ZurichViewer.tsx`

```typescript
// In game loop, after calculating velocity:
const isFlying = velocity.z !== 0;

if (isFlying) {
  // Apply vertical velocity (fly mode)
  const newAltitude = viewState.position[2] + velocity.z * deltaTime;

  // Clamp to valid range
  const clampedAlt = Math.max(
    CONFIG.player.minAltitude,
    Math.min(CONFIG.player.maxAltitude, newAltitude)
  );

  newViewState = {
    ...newViewState,
    position: [0, 0, clampedAlt] as [number, number, number],
  };
} else {
  // Apply terrain following (only when not flying)
  const groundElev = getElevation(position);
  newViewState = setAltitude(newViewState, groundElev, eyeHeight, 0.7);
}
```

### Step 8: Update Controls Hint

Add Q/E keys to the UI controls display.

```tsx
<p>
  <kbd>Q</kbd>
  <kbd>E</kbd> Fly up/down
</p>
```

## Verification

1. Run `pnpm type-check` - no errors
2. Test Q key moves camera up
3. Test E key moves camera down
4. Test altitude clamping at min/max limits
5. Test terrain following resumes when not flying

## Behavior Notes

### Fly vs Walk Mode

- **Walking:** Terrain following active, camera stays at ground + eye height
- **Flying (Q/E pressed):** Terrain following disabled, direct altitude control

### Speed

Vertical speed matches horizontal speed:
- Walk: 4 m/s up/down
- Run (Shift + Q/E): 8 m/s up/down

### Altitude Limits

- Minimum: 410m (just above Zurich ground level ~408m)
- Maximum: 1000m (configurable)

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Q/E not working | Keys not mapped | Add KeyQ/KeyE to KEY_MAP |
| Type error on up/down | Missing fields | Add to KeyboardState interface |
| No vertical movement | velocity.z not applied | Check game loop handles z velocity |
| Falls through ground | Min altitude too low | Increase minAltitude config |
| Jerky vertical motion | Missing deltaTime | Multiply velocity.z by deltaTime |

## Rollback

To remove fly mode:
1. Remove `up`/`down` from KeyboardState
2. Remove KeyQ/KeyE from KEY_MAP
3. Remove velocity.z calculation
4. Remove vertical movement from game loop
5. Run `pnpm type-check` to find remaining references
