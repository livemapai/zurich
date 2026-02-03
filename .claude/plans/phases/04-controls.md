# Phase 4: First-Person Controls

## Context
This phase implements the complete first-person navigation system including WASD movement, mouse look with pointer lock, collision detection with buildings, and terrain following. This is the most complex phase.

## Prerequisites
- Phase 3 completed
- Core app renders without errors
- `pnpm type-check` passes

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Game Loop                               │
│  (useGameLoop - 60fps requestAnimationFrame)                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Input Gathering                          │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │ useKeyboardState│    │  useMouseLook   │                 │
│  │   (WASD keys)   │    │ (pointer lock)  │                 │
│  └────────┬────────┘    └────────┬────────┘                 │
└───────────│──────────────────────│──────────────────────────┘
            │                      │
            ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   Movement Calculation                       │
│  ┌─────────────────────────────────────────────────┐        │
│  │              MovementController                  │        │
│  │   keyboard + bearing → velocity (m/s)           │        │
│  └─────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Collision Detection                        │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │  SpatialIndex   │    │ useCollision    │                 │
│  │    (RBush)      │◄───│   Detection     │                 │
│  └─────────────────┘    └────────┬────────┘                 │
│                                  │                           │
│                         Wall sliding                         │
└──────────────────────────────────│──────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────┐
│                   Terrain Following                          │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │ TerrainSampler  │    │ useTerrainElev  │                 │
│  │  (elevation)    │◄───│    ation        │                 │
│  └─────────────────┘    └────────┬────────┘                 │
└──────────────────────────────────│──────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────┐
│                   Camera Update                              │
│  ┌─────────────────────────────────────────────────┐        │
│  │              CameraController                    │        │
│  │   velocity + collision → new ViewState          │        │
│  └─────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Tasks

### Task 4.1: Create useKeyboardState Hook
**Goal:** Track WASD and modifier key state.

**Create file:** `src/hooks/useKeyboardState.ts`
```typescript
/**
 * useKeyboardState - Track keyboard state for movement controls
 *
 * Tracks WASD keys plus modifiers for game-like controls.
 * Resets all keys when window loses focus to prevent stuck keys.
 */

import { useState, useEffect, useCallback } from 'react';
import type { KeyboardState } from '@/types';

const INITIAL_STATE: KeyboardState = {
  forward: false,
  backward: false,
  left: false,
  right: false,
  run: false,
  jump: false,
};

/**
 * Map key codes to state properties
 * Supports both WASD and arrow keys
 */
const KEY_MAP: Record<string, keyof KeyboardState> = {
  // WASD
  KeyW: 'forward',
  KeyS: 'backward',
  KeyA: 'left',
  KeyD: 'right',
  // Arrow keys (alternative)
  ArrowUp: 'forward',
  ArrowDown: 'backward',
  ArrowLeft: 'left',
  ArrowRight: 'right',
  // Modifiers
  ShiftLeft: 'run',
  ShiftRight: 'run',
  Space: 'jump',
};

/**
 * Hook to track keyboard state for movement
 *
 * @returns Current keyboard state
 *
 * @example
 * ```tsx
 * function Movement() {
 *   const keyboard = useKeyboardState();
 *
 *   useEffect(() => {
 *     if (keyboard.forward) {
 *       // Move forward
 *     }
 *   }, [keyboard]);
 * }
 * ```
 */
export function useKeyboardState(): KeyboardState {
  const [state, setState] = useState<KeyboardState>(INITIAL_STATE);

  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    // Ignore if user is typing in an input
    if (
      event.target instanceof HTMLInputElement ||
      event.target instanceof HTMLTextAreaElement
    ) {
      return;
    }

    const key = KEY_MAP[event.code];
    if (key) {
      event.preventDefault();
      setState((prev) => {
        // Only update if state actually changed
        if (prev[key]) return prev;
        return { ...prev, [key]: true };
      });
    }
  }, []);

  const handleKeyUp = useCallback((event: KeyboardEvent) => {
    const key = KEY_MAP[event.code];
    if (key) {
      setState((prev) => {
        // Only update if state actually changed
        if (!prev[key]) return prev;
        return { ...prev, [key]: false };
      });
    }
  }, []);

  const handleBlur = useCallback(() => {
    // Reset all keys when window loses focus
    // This prevents stuck keys when user alt-tabs
    setState(INITIAL_STATE);
  }, []);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', handleBlur);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('blur', handleBlur);
    };
  }, [handleKeyDown, handleKeyUp, handleBlur]);

  return state;
}
```

**Verification:**
- [ ] File exists at `src/hooks/useKeyboardState.ts`

---

### Task 4.2: Create useMouseLook Hook
**Goal:** Implement pointer lock and mouse movement tracking.

**Create file:** `src/hooks/useMouseLook.ts`
```typescript
/**
 * useMouseLook - Manage pointer lock and mouse movement for camera control
 *
 * Uses the Pointer Lock API to capture mouse movement for FPS-style look.
 * Movement deltas are accumulated and can be consumed each frame.
 */

import { useState, useEffect, useCallback, useRef, type RefObject } from 'react';
import { CONFIG } from '@/lib/config';

export interface MouseLookState {
  /** Whether pointer is currently locked */
  isLocked: boolean;
  /** Get and reset accumulated movement delta */
  consumeDelta: () => { x: number; y: number };
  /** Request pointer lock (must be called from user gesture) */
  requestLock: () => void;
  /** Exit pointer lock */
  exitLock: () => void;
}

/**
 * Hook for pointer-lock based mouse look
 *
 * @param targetRef - Ref to the element that will capture the pointer
 * @param sensitivity - Mouse sensitivity multiplier
 * @returns Mouse look state and controls
 *
 * @example
 * ```tsx
 * function Viewer() {
 *   const containerRef = useRef<HTMLDivElement>(null);
 *   const { isLocked, consumeDelta, requestLock } = useMouseLook(containerRef);
 *
 *   useGameLoop(() => {
 *     const delta = consumeDelta();
 *     // Apply delta to camera rotation
 *   });
 *
 *   return <div ref={containerRef} onClick={requestLock} />;
 * }
 * ```
 */
export function useMouseLook(
  targetRef: RefObject<HTMLElement | null>,
  sensitivity = { x: CONFIG.mouse.sensitivityX, y: CONFIG.mouse.sensitivityY }
): MouseLookState {
  const [isLocked, setIsLocked] = useState(false);
  const deltaRef = useRef({ x: 0, y: 0 });

  // Handle pointer lock state changes
  useEffect(() => {
    const handleLockChange = () => {
      const target = targetRef.current;
      const isNowLocked = document.pointerLockElement === target;
      setIsLocked(isNowLocked);

      // Reset delta when lock state changes
      if (!isNowLocked) {
        deltaRef.current = { x: 0, y: 0 };
      }
    };

    const handleLockError = (event: Event) => {
      console.warn('Pointer lock request failed:', event);
      setIsLocked(false);
    };

    document.addEventListener('pointerlockchange', handleLockChange);
    document.addEventListener('pointerlockerror', handleLockError);

    return () => {
      document.removeEventListener('pointerlockchange', handleLockChange);
      document.removeEventListener('pointerlockerror', handleLockError);
    };
  }, [targetRef]);

  // Handle mouse movement while locked
  useEffect(() => {
    const handleMouseMove = (event: MouseEvent) => {
      const target = targetRef.current;
      if (document.pointerLockElement !== target) return;

      // Accumulate movement scaled by sensitivity
      deltaRef.current.x += event.movementX * sensitivity.x;

      // Y movement with optional inversion
      const yMove = CONFIG.mouse.invertY ? -event.movementY : event.movementY;
      deltaRef.current.y += yMove * sensitivity.y;
    };

    document.addEventListener('mousemove', handleMouseMove);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
    };
  }, [targetRef, sensitivity.x, sensitivity.y]);

  // Consume accumulated delta (resets to zero)
  const consumeDelta = useCallback(() => {
    const delta = { ...deltaRef.current };
    deltaRef.current = { x: 0, y: 0 };
    return delta;
  }, []);

  // Request pointer lock (must be called from user gesture like click)
  const requestLock = useCallback(() => {
    const target = targetRef.current;
    if (target && document.pointerLockElement !== target) {
      // Use the standard API
      target.requestPointerLock();
    }
  }, [targetRef]);

  // Exit pointer lock
  const exitLock = useCallback(() => {
    if (document.pointerLockElement) {
      document.exitPointerLock();
    }
  }, []);

  return { isLocked, consumeDelta, requestLock, exitLock };
}
```

**Verification:**
- [ ] File exists at `src/hooks/useMouseLook.ts`

---

### Task 4.3: Create useGameLoop Hook
**Goal:** Implement requestAnimationFrame-based game loop.

**Create file:** `src/hooks/useGameLoop.ts`
```typescript
/**
 * useGameLoop - requestAnimationFrame-based game loop
 *
 * Provides consistent timing for game-like updates.
 * Delta time is clamped to avoid large jumps when tab is inactive.
 */

import { useEffect, useRef, useCallback } from 'react';

export type GameLoopCallback = (deltaTime: number, totalTime: number) => void;

/**
 * Hook for running a game loop with requestAnimationFrame
 *
 * @param callback - Function called each frame with delta time (seconds)
 * @param isActive - Whether the loop should run (default: true)
 *
 * @example
 * ```tsx
 * function Game() {
 *   const [position, setPosition] = useState(0);
 *
 *   useGameLoop((deltaTime) => {
 *     // Move 100 units per second
 *     setPosition(prev => prev + 100 * deltaTime);
 *   });
 *
 *   return <div style={{ left: position }}>Player</div>;
 * }
 * ```
 */
export function useGameLoop(
  callback: GameLoopCallback,
  isActive: boolean = true
): void {
  const callbackRef = useRef<GameLoopCallback>(callback);
  const frameRef = useRef<number | undefined>();
  const lastTimeRef = useRef<number | undefined>();
  const startTimeRef = useRef<number | undefined>();

  // Keep callback ref updated without triggering effect
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!isActive) {
      // Reset timing when paused
      lastTimeRef.current = undefined;
      return;
    }

    const loop = (timestamp: number) => {
      // Initialize start time on first frame
      if (startTimeRef.current === undefined) {
        startTimeRef.current = timestamp;
      }

      // Calculate delta time
      if (lastTimeRef.current !== undefined) {
        const deltaMs = timestamp - lastTimeRef.current;

        // Convert to seconds and clamp to avoid huge jumps
        // (e.g., when tab was in background)
        const deltaTime = Math.min(deltaMs / 1000, 0.1); // Max 100ms

        const totalTime = (timestamp - startTimeRef.current) / 1000;

        callbackRef.current(deltaTime, totalTime);
      }

      lastTimeRef.current = timestamp;
      frameRef.current = requestAnimationFrame(loop);
    };

    frameRef.current = requestAnimationFrame(loop);

    return () => {
      if (frameRef.current !== undefined) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = undefined;
      }
    };
  }, [isActive]);
}

/**
 * Hook for fixed timestep game loop (for physics)
 *
 * Runs physics at fixed rate while rendering at variable rate.
 *
 * @param callback - Function called at fixed intervals
 * @param fixedStep - Time step in seconds (default: 1/60)
 * @param isActive - Whether the loop should run
 */
export function useFixedGameLoop(
  callback: GameLoopCallback,
  fixedStep: number = 1 / 60,
  isActive: boolean = true
): void {
  const accumulatorRef = useRef(0);
  const physicsTimeRef = useRef(0);

  const wrappedCallback = useCallback(
    (deltaTime: number, _totalTime: number) => {
      accumulatorRef.current += deltaTime;

      // Run physics updates at fixed rate
      while (accumulatorRef.current >= fixedStep) {
        callback(fixedStep, physicsTimeRef.current);
        physicsTimeRef.current += fixedStep;
        accumulatorRef.current -= fixedStep;
      }
    },
    [callback, fixedStep]
  );

  useGameLoop(wrappedCallback, isActive);
}
```

**Verification:**
- [ ] File exists at `src/hooks/useGameLoop.ts`

---

### Task 4.4: Create MovementController System
**Goal:** Convert keyboard input to velocity vectors.

**Create file:** `src/systems/MovementController.ts`
```typescript
/**
 * MovementController - Convert keyboard state to velocity vectors
 *
 * Handles the conversion from keyboard input (WASD) to world-space
 * velocity vectors based on camera bearing.
 */

import type { KeyboardState, Velocity } from '@/types';
import { CONFIG } from '@/lib/config';
import { DEG_TO_RAD } from '@/lib/constants';

export interface MovementControllerConfig {
  walkSpeed?: number;
  runSpeed?: number;
}

export class MovementController {
  private walkSpeed: number;
  private runSpeed: number;

  constructor(config: MovementControllerConfig = {}) {
    this.walkSpeed = config.walkSpeed ?? CONFIG.movement.walk;
    this.runSpeed = config.runSpeed ?? CONFIG.movement.run;
  }

  /**
   * Calculate velocity from keyboard state and camera bearing
   *
   * @param keyboard - Current keyboard state
   * @param bearing - Camera bearing in degrees (0 = North)
   * @returns Velocity in meters per second (world space)
   */
  calculateVelocity(keyboard: KeyboardState, bearing: number): Velocity {
    // Determine movement direction in local space
    // Local space: +Y = forward, +X = right
    let localX = 0;
    let localY = 0;

    if (keyboard.forward) localY += 1;
    if (keyboard.backward) localY -= 1;
    if (keyboard.right) localX += 1;
    if (keyboard.left) localX -= 1;

    // Handle no input
    if (localX === 0 && localY === 0) {
      return { x: 0, y: 0, z: 0 };
    }

    // Normalize diagonal movement to prevent faster diagonal speed
    const length = Math.sqrt(localX * localX + localY * localY);
    localX /= length;
    localY /= length;

    // Determine speed (walk or run)
    const speed = keyboard.run ? this.runSpeed : this.walkSpeed;

    // Convert bearing to radians
    // Bearing: 0 = North (+Y world), 90 = East (+X world)
    const bearingRad = bearing * DEG_TO_RAD;
    const sinB = Math.sin(bearingRad);
    const cosB = Math.cos(bearingRad);

    // Rotate local direction by bearing to get world direction
    // World space: +Y = North, +X = East
    //
    // Forward (+localY) should point in bearing direction:
    //   worldX = sin(bearing), worldY = cos(bearing)
    // Right (+localX) should point 90° clockwise from bearing:
    //   worldX = cos(bearing), worldY = -sin(bearing)
    //
    // Combined rotation:
    const worldX = localX * cosB + localY * sinB;
    const worldY = -localX * sinB + localY * cosB;

    return {
      x: worldX * speed,
      y: worldY * speed,
      z: 0, // Vertical velocity handled separately
    };
  }

  /**
   * Check if any movement input is active
   */
  isMoving(keyboard: KeyboardState): boolean {
    return (
      keyboard.forward ||
      keyboard.backward ||
      keyboard.left ||
      keyboard.right
    );
  }
}

// Singleton instance for convenience
export const movementController = new MovementController();
```

**Verification:**
- [ ] File exists at `src/systems/MovementController.ts`

---

### Task 4.5: Create CameraController System
**Goal:** Manage camera state updates.

**Create file:** `src/systems/CameraController.ts`
```typescript
/**
 * CameraController - Manage FirstPersonViewState updates
 *
 * Handles camera rotation (mouse look) and position updates (movement).
 * Enforces constraints like pitch limits and minimum altitude.
 */

import type { FirstPersonViewState, Velocity } from '@/types';
import { CONFIG } from '@/lib/config';
import { DEG_TO_RAD, normalizeAngle, clamp, METERS_PER_DEGREE } from '@/lib/constants';

export interface CameraControllerConfig {
  pitchMin?: number;
  pitchMax?: number;
  minAltitude?: number;
}

export interface CameraUpdateResult {
  viewState: FirstPersonViewState;
  wasConstrained: boolean;
}

export class CameraController {
  private pitchMin: number;
  private pitchMax: number;
  private minAltitude: number;

  constructor(config: CameraControllerConfig = {}) {
    this.pitchMin = config.pitchMin ?? CONFIG.camera.pitchMin;
    this.pitchMax = config.pitchMax ?? CONFIG.camera.pitchMax;
    this.minAltitude = config.minAltitude ?? CONFIG.camera.minAltitude;
  }

  /**
   * Apply mouse look deltas to bearing and pitch
   *
   * @param viewState - Current view state
   * @param deltaX - Horizontal movement (degrees)
   * @param deltaY - Vertical movement (degrees)
   * @returns Updated view state
   */
  applyMouseLook(
    viewState: FirstPersonViewState,
    deltaX: number,
    deltaY: number
  ): FirstPersonViewState {
    // deltaX rotates bearing (horizontal)
    let newBearing = viewState.bearing + deltaX;

    // deltaY rotates pitch (vertical)
    // Note: Positive deltaY from mouse = looking down (decreasing pitch)
    let newPitch = viewState.pitch - deltaY;

    // Normalize bearing to [0, 360)
    newBearing = normalizeAngle(newBearing);

    // Clamp pitch to avoid gimbal lock and unnatural views
    newPitch = clamp(newPitch, this.pitchMin, this.pitchMax);

    return {
      ...viewState,
      bearing: newBearing,
      pitch: newPitch,
    };
  }

  /**
   * Apply velocity to position
   *
   * @param viewState - Current view state
   * @param velocity - Velocity in meters per second
   * @param deltaTime - Time step in seconds
   * @returns Updated view state and constraint info
   */
  applyVelocity(
    viewState: FirstPersonViewState,
    velocity: Velocity,
    deltaTime: number
  ): CameraUpdateResult {
    const [lng, lat, alt] = viewState.position;

    // Convert velocity (m/s) to degrees per second
    // Account for latitude in longitude conversion
    const cosLat = Math.cos(lat * DEG_TO_RAD);
    const metersPerDegreeLng = METERS_PER_DEGREE.lat * cosLat;

    // Calculate position delta
    const dLng = (velocity.x * deltaTime) / metersPerDegreeLng;
    const dLat = (velocity.y * deltaTime) / METERS_PER_DEGREE.lat;
    const dAlt = velocity.z * deltaTime;

    let newLng = lng + dLng;
    let newLat = lat + dLat;
    let newAlt = alt + dAlt;

    // Clamp altitude
    let wasConstrained = false;
    if (newAlt < this.minAltitude) {
      newAlt = this.minAltitude;
      wasConstrained = true;
    }

    return {
      viewState: {
        ...viewState,
        position: [newLng, newLat, newAlt],
      },
      wasConstrained,
    };
  }

  /**
   * Set position directly (e.g., after collision resolution)
   */
  setPosition(
    viewState: FirstPersonViewState,
    lng: number,
    lat: number,
    alt?: number
  ): FirstPersonViewState {
    return {
      ...viewState,
      position: [lng, lat, alt ?? viewState.position[2]],
    };
  }

  /**
   * Set altitude based on terrain elevation and eye height
   *
   * @param viewState - Current view state
   * @param groundElevation - Ground elevation in meters
   * @param eyeHeight - Player eye height in meters
   * @param smooth - Apply smoothing (0-1, 0 = instant, 1 = no change)
   */
  setAltitude(
    viewState: FirstPersonViewState,
    groundElevation: number,
    eyeHeight: number,
    smooth: number = 0
  ): FirstPersonViewState {
    const targetAlt = groundElevation + eyeHeight;
    const currentAlt = viewState.position[2];

    // Apply smoothing if requested
    const newAlt = smooth > 0
      ? currentAlt + (targetAlt - currentAlt) * (1 - smooth)
      : targetAlt;

    return {
      ...viewState,
      position: [
        viewState.position[0],
        viewState.position[1],
        Math.max(newAlt, this.minAltitude),
      ],
    };
  }

  /**
   * Get position as separate lng/lat/alt values
   */
  getPosition(viewState: FirstPersonViewState) {
    return {
      lng: viewState.position[0],
      lat: viewState.position[1],
      alt: viewState.position[2],
    };
  }
}

// Singleton instance
export const cameraController = new CameraController();
```

**Verification:**
- [ ] File exists at `src/systems/CameraController.ts`

---

### Task 4.6: Create SpatialIndex System
**Goal:** Implement RBush-based spatial indexing for collision detection.

**Create file:** `src/systems/SpatialIndex.ts`
```typescript
/**
 * SpatialIndex - RBush-based spatial index for collision detection
 *
 * Efficiently indexes building footprints for fast collision queries.
 * Uses bounding box queries followed by precise point-in-polygon tests.
 */

import RBush from 'rbush';
import type { BuildingFeature, CollisionBBox, CollisionResult } from '@/types';

export class SpatialIndex {
  private tree: RBush<CollisionBBox>;
  private isLoaded: boolean = false;

  constructor() {
    this.tree = new RBush<CollisionBBox>();
  }

  /**
   * Load building features into the spatial index
   *
   * @param features - Array of building features
   */
  load(features: BuildingFeature[]): void {
    const startTime = performance.now();

    const bboxes = features
      .map((feature) => this.extractBBox(feature))
      .filter((bbox): bbox is CollisionBBox => bbox !== null);

    // Bulk load for better performance
    this.tree.load(bboxes);
    this.isLoaded = true;

    const elapsed = performance.now() - startTime;
    console.log(`SpatialIndex: Loaded ${bboxes.length} buildings in ${elapsed.toFixed(1)}ms`);
  }

  /**
   * Clear all data from the index
   */
  clear(): void {
    this.tree.clear();
    this.isLoaded = false;
  }

  /**
   * Check if index has been loaded with data
   */
  get loaded(): boolean {
    return this.isLoaded;
  }

  /**
   * Query buildings near a point
   *
   * @param lng - Longitude
   * @param lat - Latitude
   * @param radiusDegrees - Search radius in degrees
   */
  queryNearby(
    lng: number,
    lat: number,
    radiusDegrees: number
  ): CollisionBBox[] {
    return this.tree.search({
      minX: lng - radiusDegrees,
      minY: lat - radiusDegrees,
      maxX: lng + radiusDegrees,
      maxY: lat + radiusDegrees,
    });
  }

  /**
   * Check collision at a point
   *
   * @param lng - Longitude
   * @param lat - Latitude
   * @param radiusDegrees - Player radius in degrees (~0.000004 = 0.3m)
   */
  checkCollision(
    lng: number,
    lat: number,
    radiusDegrees: number = 0.000004
  ): CollisionResult {
    if (!this.isLoaded) {
      return { collides: false };
    }

    const nearby = this.queryNearby(lng, lat, radiusDegrees);

    for (const bbox of nearby) {
      const polygon = this.getOuterRing(bbox.feature);

      if (this.pointInPolygon(lng, lat, polygon)) {
        const normal = this.findNearestEdgeNormal(lng, lat, polygon);

        return {
          collides: true,
          building: bbox.feature,
          normal,
        };
      }
    }

    return { collides: false };
  }

  /**
   * Extract bounding box from a building feature
   */
  private extractBBox(feature: BuildingFeature): CollisionBBox | null {
    try {
      const coords = this.getOuterRing(feature);
      if (coords.length < 3) return null;

      let minX = Infinity;
      let minY = Infinity;
      let maxX = -Infinity;
      let maxY = -Infinity;

      for (const coord of coords) {
        const [x, y] = coord;
        if (x < minX) minX = x;
        if (y < minY) minY = y;
        if (x > maxX) maxX = x;
        if (y > maxY) maxY = y;
      }

      return { minX, minY, maxX, maxY, feature };
    } catch {
      return null;
    }
  }

  /**
   * Get outer ring coordinates from a feature
   */
  private getOuterRing(feature: BuildingFeature): number[][] {
    const coords = feature.geometry.coordinates;

    if (feature.geometry.type === 'MultiPolygon') {
      // Take first polygon's outer ring
      return (coords as number[][][][])[0]?.[0] ?? [];
    }

    // Polygon: first array is outer ring
    return (coords as number[][][])[0] ?? [];
  }

  /**
   * Ray-casting point-in-polygon test
   *
   * Classic algorithm: cast a ray from point to infinity,
   * count intersections with polygon edges.
   * Odd count = inside, even count = outside.
   */
  private pointInPolygon(x: number, y: number, polygon: number[][]): boolean {
    let inside = false;
    const n = polygon.length;

    for (let i = 0, j = n - 1; i < n; j = i++) {
      const xi = polygon[i]?.[0] ?? 0;
      const yi = polygon[i]?.[1] ?? 0;
      const xj = polygon[j]?.[0] ?? 0;
      const yj = polygon[j]?.[1] ?? 0;

      // Check if ray from point crosses this edge
      if (
        yi > y !== yj > y &&
        x < ((xj - xi) * (y - yi)) / (yj - yi) + xi
      ) {
        inside = !inside;
      }
    }

    return inside;
  }

  /**
   * Find normal of nearest edge for wall sliding
   *
   * Returns unit vector pointing away from the nearest wall.
   */
  private findNearestEdgeNormal(
    x: number,
    y: number,
    polygon: number[][]
  ): { x: number; y: number } {
    let minDist = Infinity;
    let nearestNormal = { x: 0, y: 1 };
    const n = polygon.length;

    for (let i = 0, j = n - 1; i < n; j = i++) {
      const x1 = polygon[j]?.[0] ?? 0;
      const y1 = polygon[j]?.[1] ?? 0;
      const x2 = polygon[i]?.[0] ?? 0;
      const y2 = polygon[i]?.[1] ?? 0;

      // Distance from point to line segment
      const dist = this.pointToSegmentDistance(x, y, x1, y1, x2, y2);

      if (dist < minDist) {
        minDist = dist;

        // Calculate edge direction
        const dx = x2 - x1;
        const dy = y2 - y1;
        const len = Math.sqrt(dx * dx + dy * dy);

        if (len > 0) {
          // Perpendicular to edge (two possible directions)
          const nx = -dy / len;
          const ny = dx / len;

          // Choose direction pointing toward the test point (outward from polygon)
          const toPointX = x - x1;
          const toPointY = y - y1;
          const dot = nx * toPointX + ny * toPointY;

          if (dot < 0) {
            nearestNormal = { x: -nx, y: -ny };
          } else {
            nearestNormal = { x: nx, y: ny };
          }
        }
      }
    }

    return nearestNormal;
  }

  /**
   * Calculate distance from a point to a line segment
   */
  private pointToSegmentDistance(
    px: number,
    py: number,
    x1: number,
    y1: number,
    x2: number,
    y2: number
  ): number {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const lengthSq = dx * dx + dy * dy;

    if (lengthSq === 0) {
      // Segment is a point
      return Math.sqrt((px - x1) ** 2 + (py - y1) ** 2);
    }

    // Project point onto line, clamped to segment
    let t = ((px - x1) * dx + (py - y1) * dy) / lengthSq;
    t = Math.max(0, Math.min(1, t));

    const nearestX = x1 + t * dx;
    const nearestY = y1 + t * dy;

    return Math.sqrt((px - nearestX) ** 2 + (py - nearestY) ** 2);
  }
}

// Singleton instance
export const spatialIndex = new SpatialIndex();
```

**Verification:**
- [ ] File exists at `src/systems/SpatialIndex.ts`

---

### Task 4.7: Create TerrainSampler System
**Goal:** Sample elevation at positions for terrain following.

**Create file:** `src/systems/TerrainSampler.ts`
```typescript
/**
 * TerrainSampler - Sample elevation from terrain data
 *
 * For MVP, uses a constant elevation. Can be extended to sample
 * from actual terrain heightmap data.
 */

import type { TerrainData, TerrainQuery } from '@/types';
import { ZURICH_BOUNDS } from '@/lib/constants';

// Default elevation for Zurich (meters above sea level)
const ZURICH_DEFAULT_ELEVATION = 408;

export class TerrainSampler {
  private data: TerrainData | null = null;

  /**
   * Load terrain data
   */
  load(terrain: TerrainData): void {
    this.data = terrain;
    console.log('TerrainSampler: Loaded terrain data');
  }

  /**
   * Clear terrain data
   */
  clear(): void {
    this.data = null;
  }

  /**
   * Check if terrain data is loaded
   */
  get loaded(): boolean {
    return this.data !== null;
  }

  /**
   * Sample elevation at a WGS84 coordinate
   *
   * @param lng - Longitude
   * @param lat - Latitude
   * @returns Elevation in meters
   */
  sample(lng: number, lat: number): number {
    // If no terrain data, return default Zurich elevation
    if (!this.data) {
      return ZURICH_DEFAULT_ELEVATION;
    }

    const { bounds, width, height, elevations } = this.data;

    // Check bounds
    if (
      lng < bounds.minLng ||
      lng > bounds.maxLng ||
      lat < bounds.minLat ||
      lat > bounds.maxLat
    ) {
      return ZURICH_DEFAULT_ELEVATION;
    }

    // Convert lng/lat to pixel coordinates
    const x = ((lng - bounds.minLng) / (bounds.maxLng - bounds.minLng)) * (width - 1);
    const y = ((bounds.maxLat - lat) / (bounds.maxLat - bounds.minLat)) * (height - 1);

    // Bilinear interpolation
    const x0 = Math.floor(x);
    const y0 = Math.floor(y);
    const x1 = Math.min(x0 + 1, width - 1);
    const y1 = Math.min(y0 + 1, height - 1);

    const fx = x - x0;
    const fy = y - y0;

    const e00 = elevations[y0 * width + x0] ?? ZURICH_DEFAULT_ELEVATION;
    const e10 = elevations[y0 * width + x1] ?? ZURICH_DEFAULT_ELEVATION;
    const e01 = elevations[y1 * width + x0] ?? ZURICH_DEFAULT_ELEVATION;
    const e11 = elevations[y1 * width + x1] ?? ZURICH_DEFAULT_ELEVATION;

    // Bilinear interpolation formula
    const elevation =
      e00 * (1 - fx) * (1 - fy) +
      e10 * fx * (1 - fy) +
      e01 * (1 - fx) * fy +
      e11 * fx * fy;

    return elevation;
  }

  /**
   * Query elevation with surface normal
   */
  query(lng: number, lat: number): TerrainQuery {
    const elevation = this.sample(lng, lat);

    // For now, assume flat terrain (normal pointing up)
    // Could calculate normal from neighboring samples
    return {
      elevation,
      normal: { x: 0, y: 0, z: 1 },
    };
  }
}

// Singleton instance
export const terrainSampler = new TerrainSampler();
```

**Verification:**
- [ ] File exists at `src/systems/TerrainSampler.ts`

---

### Task 4.8: Create useCollisionDetection Hook
**Goal:** React hook for collision detection with buildings.

**Create file:** `src/hooks/useCollisionDetection.ts`
```typescript
/**
 * useCollisionDetection - Hook for building collision detection
 *
 * Manages the spatial index and provides collision checking functions.
 */

import { useEffect, useCallback, useRef } from 'react';
import { spatialIndex } from '@/systems/SpatialIndex';
import type { BuildingFeature, CollisionResult } from '@/types';

export interface CollisionDetectionResult {
  /** Check collision at a position */
  checkCollision: (lng: number, lat: number, radius?: number) => CollisionResult;
  /** Whether the spatial index is ready */
  isReady: boolean;
  /** Number of buildings indexed */
  buildingCount: number;
}

/**
 * Hook for collision detection with buildings
 *
 * @param buildings - Array of building features to index
 * @returns Collision detection functions and state
 */
export function useCollisionDetection(
  buildings: BuildingFeature[] | null
): CollisionDetectionResult {
  const buildingCountRef = useRef(0);

  // Load buildings into spatial index when data changes
  useEffect(() => {
    if (buildings && buildings.length > 0) {
      spatialIndex.load(buildings);
      buildingCountRef.current = buildings.length;
    }

    return () => {
      spatialIndex.clear();
      buildingCountRef.current = 0;
    };
  }, [buildings]);

  // Check collision at position
  const checkCollision = useCallback(
    (lng: number, lat: number, radius?: number): CollisionResult => {
      if (!spatialIndex.loaded) {
        return { collides: false };
      }
      return spatialIndex.checkCollision(lng, lat, radius);
    },
    []
  );

  return {
    checkCollision,
    isReady: spatialIndex.loaded,
    buildingCount: buildingCountRef.current,
  };
}
```

**Verification:**
- [ ] File exists at `src/hooks/useCollisionDetection.ts`

---

### Task 4.9: Create useTerrainElevation Hook
**Goal:** React hook for terrain elevation queries.

**Create file:** `src/hooks/useTerrainElevation.ts`
```typescript
/**
 * useTerrainElevation - Hook for terrain elevation queries
 *
 * Manages terrain data and provides elevation sampling functions.
 */

import { useEffect, useCallback } from 'react';
import { terrainSampler } from '@/systems/TerrainSampler';
import type { TerrainData } from '@/types';

export interface TerrainElevationResult {
  /** Get elevation at a position */
  getElevation: (lng: number, lat: number) => number;
  /** Whether terrain data is loaded */
  isReady: boolean;
}

/**
 * Hook for terrain elevation queries
 *
 * @param terrain - Terrain data to use
 * @returns Elevation query function and state
 */
export function useTerrainElevation(
  terrain: TerrainData | null
): TerrainElevationResult {
  // Load terrain data when it changes
  useEffect(() => {
    if (terrain) {
      terrainSampler.load(terrain);
    }

    return () => {
      terrainSampler.clear();
    };
  }, [terrain]);

  // Get elevation at position
  const getElevation = useCallback(
    (lng: number, lat: number): number => {
      return terrainSampler.sample(lng, lat);
    },
    []
  );

  return {
    getElevation,
    isReady: terrainSampler.loaded,
  };
}
```

**Verification:**
- [ ] File exists at `src/hooks/useTerrainElevation.ts`

---

### Task 4.10: Create Math Utilities
**Goal:** Vector math utilities for movement calculations.

**Create file:** `src/utils/math.ts`
```typescript
/**
 * Math utilities for movement and collision calculations
 */

export interface Vec2 {
  x: number;
  y: number;
}

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

/**
 * Create a 2D vector
 */
export function vec2(x: number, y: number): Vec2 {
  return { x, y };
}

/**
 * Create a 3D vector
 */
export function vec3(x: number, y: number, z: number): Vec3 {
  return { x, y, z };
}

/**
 * Add two 2D vectors
 */
export function add2(a: Vec2, b: Vec2): Vec2 {
  return { x: a.x + b.x, y: a.y + b.y };
}

/**
 * Add two 3D vectors
 */
export function add3(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z };
}

/**
 * Subtract 2D vectors (a - b)
 */
export function sub2(a: Vec2, b: Vec2): Vec2 {
  return { x: a.x - b.x, y: a.y - b.y };
}

/**
 * Scale a 2D vector
 */
export function scale2(v: Vec2, s: number): Vec2 {
  return { x: v.x * s, y: v.y * s };
}

/**
 * Scale a 3D vector
 */
export function scale3(v: Vec3, s: number): Vec3 {
  return { x: v.x * s, y: v.y * s, z: v.z * s };
}

/**
 * Dot product of two 2D vectors
 */
export function dot2(a: Vec2, b: Vec2): number {
  return a.x * b.x + a.y * b.y;
}

/**
 * Length of a 2D vector
 */
export function length2(v: Vec2): number {
  return Math.sqrt(v.x * v.x + v.y * v.y);
}

/**
 * Normalize a 2D vector
 */
export function normalize2(v: Vec2): Vec2 {
  const len = length2(v);
  if (len === 0) return { x: 0, y: 0 };
  return { x: v.x / len, y: v.y / len };
}

/**
 * Project vector a onto vector b
 */
export function project2(a: Vec2, b: Vec2): Vec2 {
  const bLen = length2(b);
  if (bLen === 0) return { x: 0, y: 0 };
  const scalar = dot2(a, b) / (bLen * bLen);
  return scale2(b, scalar);
}

/**
 * Reflect vector v off a surface with normal n
 */
export function reflect2(v: Vec2, n: Vec2): Vec2 {
  const d = 2 * dot2(v, n);
  return { x: v.x - d * n.x, y: v.y - d * n.y };
}

/**
 * Slide vector along a wall (remove component into wall)
 */
export function slideAlongWall(
  velocity: Vec2,
  wallNormal: Vec2
): Vec2 {
  // Project velocity onto wall normal
  const dot = dot2(velocity, wallNormal);

  // If moving away from wall, no sliding needed
  if (dot >= 0) {
    return velocity;
  }

  // Remove component into wall
  return {
    x: velocity.x - dot * wallNormal.x,
    y: velocity.y - dot * wallNormal.y,
  };
}

/**
 * Linear interpolation
 */
export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/**
 * Clamp value between min and max
 */
export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
```

**Verification:**
- [ ] File exists at `src/utils/math.ts`

---

### Task 4.11: Create Index Exports
**Goal:** Create barrel exports for hooks, systems, and utils.

**Create file:** `src/hooks/index.ts`
```typescript
export { useKeyboardState } from './useKeyboardState';
export { useMouseLook, type MouseLookState } from './useMouseLook';
export { useGameLoop, useFixedGameLoop, type GameLoopCallback } from './useGameLoop';
export { useCollisionDetection, type CollisionDetectionResult } from './useCollisionDetection';
export { useTerrainElevation, type TerrainElevationResult } from './useTerrainElevation';
```

**Create file:** `src/systems/index.ts`
```typescript
export { MovementController, movementController } from './MovementController';
export { CameraController, cameraController } from './CameraController';
export { SpatialIndex, spatialIndex } from './SpatialIndex';
export { TerrainSampler, terrainSampler } from './TerrainSampler';
```

**Create file:** `src/utils/index.ts`
```typescript
export * from './math';
```

**Verification:**
- [ ] `src/hooks/index.ts` exists
- [ ] `src/systems/index.ts` exists
- [ ] `src/utils/index.ts` exists

---

### Task 4.12: Update ZurichViewer with Controls
**Goal:** Integrate all control systems into the viewer.

**Update file:** `src/components/ZurichViewer/ZurichViewer.tsx`
```typescript
import { useState, useRef, useEffect, useCallback } from 'react';
import DeckGL from '@deck.gl/react';
import { FirstPersonView } from '@deck.gl/core';
import type { FirstPersonViewState, BuildingFeature, Velocity } from '@/types';
import { CONFIG } from '@/lib/config';
import { DEFAULT_POSITION, METERS_PER_DEGREE, DEG_TO_RAD } from '@/lib/constants';
import { useKeyboardState, useMouseLook, useGameLoop, useCollisionDetection, useTerrainElevation } from '@/hooks';
import { movementController, cameraController } from '@/systems';
import { slideAlongWall } from '@/utils/math';

interface ZurichViewerProps {
  onLoadProgress?: (progress: number) => void;
  onError?: (error: Error) => void;
}

const INITIAL_VIEW_STATE: FirstPersonViewState = {
  position: DEFAULT_POSITION,
  bearing: 0,
  pitch: 0,
  fov: CONFIG.render.fov,
  near: CONFIG.render.near,
  far: CONFIG.render.far,
};

// Player collision radius in degrees (~0.3m at Zurich latitude)
const PLAYER_RADIUS_DEGREES = CONFIG.player.collisionRadius / METERS_PER_DEGREE.lng;

export function ZurichViewer({ onLoadProgress, onError }: ZurichViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [viewState, setViewState] = useState<FirstPersonViewState>(INITIAL_VIEW_STATE);
  const [isReady, setIsReady] = useState(false);
  const [buildings, setBuildings] = useState<BuildingFeature[] | null>(null);

  // Input hooks
  const keyboard = useKeyboardState();
  const { isLocked, consumeDelta, requestLock, exitLock } = useMouseLook(containerRef);

  // Collision and terrain hooks
  const { checkCollision, isReady: collisionReady } = useCollisionDetection(buildings);
  const { getElevation } = useTerrainElevation(null); // No terrain data yet

  // View configuration
  const view = new FirstPersonView({
    id: 'first-person',
    controller: false,
    fovy: viewState.fov ?? CONFIG.render.fov,
    near: viewState.near ?? CONFIG.render.near,
    far: viewState.far ?? CONFIG.render.far,
  });

  // Main game loop
  const gameLoop = useCallback(
    (deltaTime: number) => {
      let newViewState = viewState;

      // 1. Apply mouse look (if pointer locked)
      if (isLocked) {
        const mouseDelta = consumeDelta();
        newViewState = cameraController.applyMouseLook(
          newViewState,
          mouseDelta.x,
          mouseDelta.y
        );
      }

      // 2. Calculate velocity from keyboard
      const velocity = movementController.calculateVelocity(
        keyboard,
        newViewState.bearing
      );

      // Only process movement if there's velocity
      if (velocity.x !== 0 || velocity.y !== 0) {
        // 3. Convert velocity to position delta
        const [lng, lat] = newViewState.position;
        const cosLat = Math.cos(lat * DEG_TO_RAD);
        const metersPerDegreeLng = METERS_PER_DEGREE.lat * cosLat;

        let dLng = (velocity.x * deltaTime) / metersPerDegreeLng;
        let dLat = (velocity.y * deltaTime) / METERS_PER_DEGREE.lat;

        // 4. Check collision at proposed position
        const proposedLng = lng + dLng;
        const proposedLat = lat + dLat;

        const collision = checkCollision(proposedLng, proposedLat, PLAYER_RADIUS_DEGREES);

        if (collision.collides && collision.normal) {
          // Wall sliding: remove velocity component into wall
          const velocityVec = { x: velocity.x, y: velocity.y };
          const slidVelocity = slideAlongWall(velocityVec, collision.normal);

          // Recalculate deltas with sliding velocity
          dLng = (slidVelocity.x * deltaTime) / metersPerDegreeLng;
          dLat = (slidVelocity.y * deltaTime) / METERS_PER_DEGREE.lat;

          // Check collision again at slid position
          const slidLng = lng + dLng;
          const slidLat = lat + dLat;
          const slidCollision = checkCollision(slidLng, slidLat, PLAYER_RADIUS_DEGREES);

          if (slidCollision.collides) {
            // Still colliding, don't move
            dLng = 0;
            dLat = 0;
          }
        }

        // 5. Apply movement
        newViewState = cameraController.setPosition(
          newViewState,
          lng + dLng,
          lat + dLat
        );

        // 6. Apply terrain following
        const groundElevation = getElevation(
          newViewState.position[0],
          newViewState.position[1]
        );
        newViewState = cameraController.setAltitude(
          newViewState,
          groundElevation,
          CONFIG.player.eyeHeight,
          0.7 // Smoothing factor
        );
      }

      // Update state if changed
      if (newViewState !== viewState) {
        setViewState(newViewState);
      }
    },
    [viewState, keyboard, isLocked, consumeDelta, checkCollision, getElevation]
  );

  // Run game loop only when pointer is locked
  useGameLoop(gameLoop, isLocked);

  // Load building data
  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      try {
        onLoadProgress?.(10);

        const response = await fetch(CONFIG.data.buildings);
        if (!response.ok) {
          throw new Error(`Failed to load buildings: ${response.statusText}`);
        }

        onLoadProgress?.(50);

        const data = await response.json();
        if (!cancelled) {
          setBuildings(data.features);
          onLoadProgress?.(90);
        }
      } catch (error) {
        if (!cancelled) {
          console.warn('Could not load buildings, continuing without collision:', error);
          // Continue without buildings for development
        }
      }

      if (!cancelled) {
        setIsReady(true);
        onLoadProgress?.(100);
      }
    }

    loadData();

    return () => {
      cancelled = true;
    };
  }, [onLoadProgress]);

  // Handle escape to exit pointer lock
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isLocked) {
        exitLock();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isLocked, exitLock]);

  // No layers yet - will be added in Phase 5
  const layers: never[] = [];

  return (
    <div
      ref={containerRef}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        cursor: isLocked ? 'none' : (isReady ? 'crosshair' : 'wait'),
      }}
    >
      <DeckGL
        views={view}
        viewState={viewState}
        onViewStateChange={() => {}} // Controlled externally
        controller={false}
        layers={layers}
        onClick={() => {
          if (isReady && !isLocked) {
            requestLock();
          }
        }}
        style={{ background: '#16213e' }}
      />

      {/* Crosshair - shown when locked */}
      {isReady && isLocked && <div className="crosshair" />}

      {/* Controls hint */}
      {isReady && (
        <div className="controls-hint">
          {!isLocked ? (
            <p>Click to start</p>
          ) : (
            <>
              <p>
                <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> Move
                {' '}
                <kbd>Shift</kbd> Run
              </p>
              <p><kbd>Mouse</kbd> Look around</p>
              <p><kbd>Esc</kbd> Release cursor</p>
            </>
          )}
        </div>
      )}

      {/* Debug panel */}
      {CONFIG.debug.showDebugPanel && isReady && (
        <div className="debug-panel">
          <p>Pointer: {isLocked ? 'Locked' : 'Free'}</p>
          <p>Position: {viewState.position.map(n => n.toFixed(6)).join(', ')}</p>
          <p>Bearing: {viewState.bearing.toFixed(1)}°</p>
          <p>Pitch: {viewState.pitch.toFixed(1)}°</p>
          <p>Collision: {collisionReady ? 'Ready' : 'Loading'}</p>
          <p>Buildings: {buildings?.length ?? 0}</p>
        </div>
      )}
    </div>
  );
}
```

**Verification:**
- [ ] File updated at `src/components/ZurichViewer/ZurichViewer.tsx`

---

## Verification Checklist

After completing all tasks:

- [ ] `src/hooks/useKeyboardState.ts` exists
- [ ] `src/hooks/useMouseLook.ts` exists
- [ ] `src/hooks/useGameLoop.ts` exists
- [ ] `src/hooks/useCollisionDetection.ts` exists
- [ ] `src/hooks/useTerrainElevation.ts` exists
- [ ] `src/hooks/index.ts` exists
- [ ] `src/systems/MovementController.ts` exists
- [ ] `src/systems/CameraController.ts` exists
- [ ] `src/systems/SpatialIndex.ts` exists
- [ ] `src/systems/TerrainSampler.ts` exists
- [ ] `src/systems/index.ts` exists
- [ ] `src/utils/math.ts` exists
- [ ] `src/utils/index.ts` exists
- [ ] `src/components/ZurichViewer/ZurichViewer.tsx` updated
- [ ] `pnpm type-check` passes

## Type Check Command
```bash
cd /Users/claudioromano/Documents/livemap/zuri-3d && pnpm type-check
```

## Files Created

```
src/
├── hooks/
│   ├── useKeyboardState.ts
│   ├── useMouseLook.ts
│   ├── useGameLoop.ts
│   ├── useCollisionDetection.ts
│   ├── useTerrainElevation.ts
│   └── index.ts
├── systems/
│   ├── MovementController.ts
│   ├── CameraController.ts
│   ├── SpatialIndex.ts
│   ├── TerrainSampler.ts
│   └── index.ts
├── utils/
│   ├── math.ts
│   └── index.ts
└── components/
    └── ZurichViewer/
        └── ZurichViewer.tsx (updated)
```

## Current State After Phase 4

The application now has:
- WASD movement with bearing-relative direction
- Mouse look with pointer lock
- RBush-based collision detection
- Wall sliding collision response
- Terrain elevation (default Zurich height)
- Smooth camera updates
- Debug panel showing state

**Not yet implemented:**
- Building rendering (Phase 5)
- Terrain rendering (Phase 5)
- Minimap (Phase 5)
- UI polish (Phase 6)

## Next Phase
After verification, read and execute: `.claude/plans/phases/05-layers.md`
