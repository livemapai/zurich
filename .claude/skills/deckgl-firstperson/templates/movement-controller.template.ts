/**
 * MovementController
 *
 * Converts keyboard state to velocity vectors based on camera bearing
 */

import type { KeyboardState, Velocity } from '@/types';
import { MOVEMENT_SPEEDS } from '@/types';

const DEG_TO_RAD = Math.PI / 180;

export interface MovementControllerConfig {
  walkSpeed?: number;
  runSpeed?: number;
}

export class MovementController {
  private walkSpeed: number;
  private runSpeed: number;

  constructor(config: MovementControllerConfig = {}) {
    this.walkSpeed = config.walkSpeed ?? MOVEMENT_SPEEDS.walk;
    this.runSpeed = config.runSpeed ?? MOVEMENT_SPEEDS.run;
  }

  /**
   * Calculate velocity from keyboard state and camera bearing
   * Returns velocity in meters per second
   */
  calculateVelocity(
    keyboard: KeyboardState,
    bearing: number,
    deltaTime: number
  ): Velocity {
    // Determine movement direction in local space
    let localX = 0; // Right/Left
    let localY = 0; // Forward/Backward

    if (keyboard.forward) localY += 1;
    if (keyboard.backward) localY -= 1;
    if (keyboard.right) localX += 1;
    if (keyboard.left) localX -= 1;

    // Normalize diagonal movement
    const length = Math.sqrt(localX * localX + localY * localY);
    if (length > 0) {
      localX /= length;
      localY /= length;
    }

    // Determine speed
    const speed = keyboard.run ? this.runSpeed : this.walkSpeed;

    // Convert bearing to radians (0 = North = +Y in world space)
    const bearingRad = bearing * DEG_TO_RAD;
    const sinB = Math.sin(bearingRad);
    const cosB = Math.cos(bearingRad);

    // Rotate local direction by bearing to get world direction
    // Forward (+localY) should point in bearing direction
    // Right (+localX) should point 90° clockwise from bearing
    const worldX = localX * cosB + localY * sinB;
    const worldY = -localX * sinB + localY * cosB;

    return {
      x: worldX * speed,
      y: worldY * speed,
      z: 0, // Vertical velocity handled separately
    };
  }

  /**
   * Convert velocity in meters to position delta in degrees
   * For use with WGS84 coordinates
   */
  velocityToDegrees(
    velocity: Velocity,
    deltaTime: number,
    latitude: number
  ): { dLng: number; dLat: number; dAlt: number } {
    // Meters per degree varies with latitude
    const metersPerDegreeLat = 111000;
    const metersPerDegreeLng = 111000 * Math.cos(latitude * DEG_TO_RAD);

    return {
      dLng: (velocity.x * deltaTime) / metersPerDegreeLng,
      dLat: (velocity.y * deltaTime) / metersPerDegreeLat,
      dAlt: velocity.z * deltaTime,
    };
  }
}

// Singleton instance for convenience
export const movementController = new MovementController();
