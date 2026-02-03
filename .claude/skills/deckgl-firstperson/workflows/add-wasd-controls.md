# Add WASD Controls Workflow

Minimal implementation for WASD movement without collision.

## Steps

### 1. Create useKeyboardState
Copy from `templates/use-keyboard-state.template.ts` to:
`src/hooks/useKeyboardState.ts`

### 2. Create useMouseLook
Copy from `templates/use-mouse-look.template.ts` to:
`src/hooks/useMouseLook.ts`

### 3. Create useGameLoop
Copy from `templates/use-game-loop.template.ts` to:
`src/hooks/useGameLoop.ts`

### 4. Create MovementController
Copy from `templates/movement-controller.template.ts` to:
`src/systems/MovementController.ts`

### 5. Create CameraController
Copy from `templates/camera-controller.template.ts` to:
`src/systems/CameraController.ts`

### 6. Create hooks index
Create `src/hooks/index.ts`:
```typescript
export { useKeyboardState } from './useKeyboardState';
export { useMouseLook } from './useMouseLook';
export { useGameLoop, useFixedGameLoop } from './useGameLoop';
```

### 7. Create systems index
Create `src/systems/index.ts`:
```typescript
export { MovementController, movementController } from './MovementController';
export { CameraController, cameraController } from './CameraController';
```

### 8. Integrate in Component
```tsx
import { useRef, useState, useCallback } from 'react';
import DeckGL from '@deck.gl/react';
import { FirstPersonView } from '@deck.gl/core';
import { useKeyboardState } from '@/hooks/useKeyboardState';
import { useMouseLook } from '@/hooks/useMouseLook';
import { useGameLoop } from '@/hooks/useGameLoop';
import { movementController } from '@/systems/MovementController';
import { cameraController } from '@/systems/CameraController';
import { DEFAULT_VIEW_STATE, PLAYER_DIMENSIONS } from '@/types';

function ZurichViewer() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [viewState, setViewState] = useState(DEFAULT_VIEW_STATE);

  const keyboard = useKeyboardState();
  const { isLocked, consumeDelta, requestLock } = useMouseLook(containerRef);

  const gameLoop = useCallback(
    (deltaTime: number) => {
      // Apply mouse look
      const mouseDelta = consumeDelta();
      let newState = cameraController.applyMouseLook(
        viewState,
        mouseDelta.x,
        mouseDelta.y
      );

      // Calculate velocity from keyboard
      const velocity = movementController.calculateVelocity(
        keyboard,
        newState.bearing,
        deltaTime
      );

      // Apply velocity to position
      const { viewState: updatedState } = cameraController.applyVelocity(
        newState,
        velocity,
        deltaTime
      );

      setViewState(updatedState);
    },
    [viewState, keyboard, consumeDelta]
  );

  useGameLoop(gameLoop, isLocked);

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%' }}>
      <DeckGL
        views={new FirstPersonView({ fovy: 75 })}
        viewState={viewState}
        controller={false}
        onClick={requestLock}
        layers={[]}
      />
    </div>
  );
}
```

### 9. Verify
```bash
pnpm type-check
```
