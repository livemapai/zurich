/**
 * MovementController - Converts keyboard input to velocity
 *
 * Takes keyboard state and current bearing, outputs velocity in m/s.
 * Does NOT apply deltaTime - that's handled by CameraController.
 */

import type { KeyboardState, Velocity } from '@/types';
import { CONFIG } from '@/lib/config';
import { DEG_TO_RAD } from '@/lib/constants';

/**
 * Calculate velocity vector from keyboard input and current bearing
 *
 * Supports progressive altitude-based speed: movement speed scales linearly
 * with height above terrain. Every 100m adds 1x base speed (ground=1x, 100m=2x,
 * 200m=3x, etc.) capped at 10x for a smooth "low=walking, high=flying" feel.
 *
 * @param keyboard - Current keyboard state (WASD + run)
 * @param bearing - Current camera bearing in degrees (0 = North)
 * @param altitude - Optional: current eye altitude in meters (for speed scaling)
 * @param groundElevation - Optional: terrain elevation at current position (for speed scaling)
 * @returns Velocity in meters per second (world space)
 */
export function calculateVelocity(
  keyboard: KeyboardState,
  bearing: number,
  altitude?: number,
  groundElevation?: number
): Velocity {
  // Determine input direction (local space)
  let localX = 0; // Left/Right
  let localY = 0; // Forward/Backward
  let localZ = 0; // Up/Down (fly mode)

  if (keyboard.forward) localY += 1;
  if (keyboard.backward) localY -= 1;
  if (keyboard.left) localX -= 1;
  if (keyboard.right) localX += 1;
  if (keyboard.up) localZ += 1;   // Q key - fly up
  if (keyboard.down) localZ -= 1; // E key - fly down

  // Early exit if no movement (now includes vertical)
  if (localX === 0 && localY === 0 && localZ === 0) {
    return { x: 0, y: 0, z: 0 };
  }

  // Calculate progressive speed multiplier based on height above terrain
  // Higher altitude = faster movement (linear scaling capped at maxSpeedMultiplier)
  let speedMultiplier = 1.0;
  if (altitude !== undefined && groundElevation !== undefined) {
    const heightAboveGround = Math.max(0, altitude - groundElevation);
    speedMultiplier = Math.min(
      1 + heightAboveGround / CONFIG.movement.altitudeScaleFactor,
      CONFIG.movement.maxSpeedMultiplier
    );
  }

  // Apply multiplier to base speed (walk or run)
  const baseSpeed = keyboard.run ? CONFIG.movement.run : CONFIG.movement.walk;
  const speed = baseSpeed * speedMultiplier;

  // Handle vertical-only movement (Q/E without WASD)
  if (localX === 0 && localY === 0) {
    return {
      x: 0,
      y: 0,
      z: localZ * speed,
    };
  }

  // Normalize diagonal movement (horizontal only)
  const inputLength = Math.sqrt(localX * localX + localY * localY);
  localX /= inputLength;
  localY /= inputLength;

  // Convert bearing to radians (deck.gl bearing: 0 = North, 90 = East)
  // We need to convert to standard math angle where 0 = East, 90 = North
  const angleRad = (90 - bearing) * DEG_TO_RAD;

  // Rotate local velocity to world space
  // Forward (localY) -> direction of bearing
  // Right (localX) -> 90 degrees clockwise from bearing
  const cos = Math.cos(angleRad);
  const sin = Math.sin(angleRad);

  // World X = East, World Y = North
  // Forward in local space points along bearing
  // Right in local space points 90 degrees clockwise from bearing
  const worldX = localX * sin + localY * cos;
  const worldY = -localX * cos + localY * sin;

  return {
    x: worldX * speed,
    y: worldY * speed,
    z: localZ * speed, // Q/E fly mode uses same speed
  };
}

/**
 * Check if there is any movement input (including vertical)
 */
export function hasMovementInput(keyboard: KeyboardState): boolean {
  return (
    keyboard.forward ||
    keyboard.backward ||
    keyboard.left ||
    keyboard.right ||
    keyboard.up ||
    keyboard.down
  );
}

/**
 * Create an empty keyboard state
 */
export function createEmptyKeyboardState(): KeyboardState {
  return {
    forward: false,
    backward: false,
    left: false,
    right: false,
    up: false,    // Q key - fly up
    down: false,  // E key - fly down
    run: false,
    jump: false,
  };
}
