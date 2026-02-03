/**
 * CameraController
 *
 * Manages FirstPersonViewState updates including position, bearing, and pitch
 *
 * Note on pitch: In deck.gl FirstPersonView, pitch follows the convention:
 * - Negative pitch (-90) = looking up
 * - Zero pitch (0) = looking level/horizontal
 * - Positive pitch (+90) = looking down
 */

import type { FirstPersonViewState, Velocity } from '@/types';

const DEG_TO_RAD = Math.PI / 180;

export interface CameraUpdateResult {
  viewState: FirstPersonViewState;
  wasConstrained: boolean;
}

export interface CameraControllerConfig {
  pitchMin?: number;
  pitchMax?: number;
  minAltitude?: number;
}

export class CameraController {
  private pitchMin: number;
  private pitchMax: number;
  private minAltitude: number;

  constructor(config: CameraControllerConfig = {}) {
    this.pitchMin = config.pitchMin ?? -89;
    this.pitchMax = config.pitchMax ?? 89;
    this.minAltitude = config.minAltitude ?? 0.5;
  }

  /**
   * Apply mouse look deltas to bearing and pitch
   *
   * deltaX: horizontal mouse movement (positive = move right = increase bearing)
   * deltaY: vertical mouse movement (positive = move down = increase pitch = look down)
   */
  applyMouseLook(
    viewState: FirstPersonViewState,
    deltaX: number,
    deltaY: number
  ): FirstPersonViewState {
    // deltaX rotates bearing (horizontal)
    // deltaY rotates pitch (vertical)
    // Positive deltaY = mouse moved down = look down = increase pitch
    let newBearing = viewState.bearing + deltaX;
    let newPitch = viewState.pitch + deltaY;

    // Normalize bearing to [0, 360)
    newBearing = ((newBearing % 360) + 360) % 360;

    // Clamp pitch to avoid gimbal lock
    // pitchMin is typically -89 (looking up), pitchMax is typically 89 (looking down)
    newPitch = Math.max(this.pitchMin, Math.min(this.pitchMax, newPitch));

    return {
      ...viewState,
      bearing: newBearing,
      pitch: newPitch,
    };
  }

  /**
   * Apply velocity to position
   */
  applyVelocity(
    viewState: FirstPersonViewState,
    velocity: Velocity,
    deltaTime: number
  ): CameraUpdateResult {
    const [lng, lat, alt] = viewState.position;

    // Convert velocity (m/s) to degrees
    const metersPerDegreeLat = 111000;
    const metersPerDegreeLng = 111000 * Math.cos(lat * DEG_TO_RAD);

    const newLng = lng + (velocity.x * deltaTime) / metersPerDegreeLng;
    const newLat = lat + (velocity.y * deltaTime) / metersPerDegreeLat;
    let newAlt = alt + velocity.z * deltaTime;

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
   * Set altitude (e.g., after terrain query)
   */
  setAltitude(
    viewState: FirstPersonViewState,
    groundElevation: number,
    eyeHeight: number
  ): FirstPersonViewState {
    const targetAlt = groundElevation + eyeHeight;

    return {
      ...viewState,
      position: [
        viewState.position[0],
        viewState.position[1],
        Math.max(targetAlt, this.minAltitude),
      ],
    };
  }
}

// Singleton instance
export const cameraController = new CameraController();
