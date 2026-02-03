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
 * @param keyboard - Current keyboard state (WASD + run)
 * @param bearing - Current camera bearing in degrees (0 = North)
 * @returns Velocity in meters per second (world space)
 */
export function calculateVelocity(
  keyboard: KeyboardState,
  bearing: number
): Velocity {
  // Determine input direction (local space)
  let localX = 0; // Left/Right
  let localY = 0; // Forward/Backward

  if (keyboard.forward) localY += 1;
  if (keyboard.backward) localY -= 1;
  if (keyboard.left) localX -= 1;
  if (keyboard.right) localX += 1;

  // Early exit if no movement
  if (localX === 0 && localY === 0) {
    return { x: 0, y: 0, z: 0 };
  }

  // Normalize diagonal movement
  const inputLength = Math.sqrt(localX * localX + localY * localY);
  localX /= inputLength;
  localY /= inputLength;

  // Determine speed based on run state
  const speed = keyboard.run ? CONFIG.movement.run : CONFIG.movement.walk;

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
    z: 0, // No vertical movement from WASD
  };
}

/**
 * Check if there is any movement input
 */
export function hasMovementInput(keyboard: KeyboardState): boolean {
  return (
    keyboard.forward ||
    keyboard.backward ||
    keyboard.left ||
    keyboard.right
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
    run: false,
    jump: false,
  };
}
