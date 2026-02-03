/**
 * CameraController - Manages view state transformations
 *
 * Handles:
 * - Mouse look (bearing/pitch from mouse movement)
 * - Velocity application (position updates from velocity)
 * - Altitude management (terrain following with smoothing)
 */

import type { FirstPersonViewState, Velocity, MouseDelta } from '@/types';
import { CONFIG } from '@/lib/config';
import { clamp, normalizeAngle, metersToDegreesLng, metersToDegreesLat } from '@/lib/constants';

/**
 * Apply mouse look to view state
 *
 * @param viewState - Current view state
 * @param deltaX - Mouse movement in X (pixels)
 * @param deltaY - Mouse movement in Y (pixels)
 * @returns Updated view state with new bearing and pitch
 */
export function applyMouseLook(
  viewState: FirstPersonViewState,
  deltaX: number,
  deltaY: number
): FirstPersonViewState {
  // Apply sensitivity
  const yawDelta = deltaX * CONFIG.mouse.sensitivityX;
  const pitchDelta = deltaY * CONFIG.mouse.sensitivityY * (CONFIG.mouse.invertY ? -1 : 1);

  // Update bearing (horizontal look)
  // Positive deltaX = turn right = increase bearing
  const newBearing = normalizeAngle(viewState.bearing + yawDelta);

  // Update pitch (vertical look)
  // In deck.gl FirstPersonView:
  // - pitch = 0 is looking at horizon
  // - negative pitch = looking up
  // - positive pitch = looking down
  // Positive deltaY (mouse down) = look down = increase pitch
  const newPitch = clamp(
    viewState.pitch + pitchDelta,
    CONFIG.camera.pitchMin,
    CONFIG.camera.pitchMax
  );

  return {
    ...viewState,
    bearing: newBearing,
    pitch: newPitch,
  };
}

/**
 * Apply mouse delta object to view state
 */
export function applyMouseDelta(
  viewState: FirstPersonViewState,
  delta: MouseDelta
): FirstPersonViewState {
  return applyMouseLook(viewState, delta.x, delta.y);
}

/**
 * Apply velocity to view state position
 *
 * Geographic movement updates longitude/latitude directly.
 * The position array only changes in the Z component (altitude).
 *
 * @param viewState - Current view state
 * @param velocity - Velocity in meters per second
 * @param deltaTime - Time since last frame in seconds
 * @returns Updated view state with new position
 */
export function applyVelocity(
  viewState: FirstPersonViewState,
  velocity: Velocity,
  deltaTime: number
): FirstPersonViewState {
  // Convert velocity (m/s) to degrees using deltaTime
  const deltaLng = metersToDegreesLng(velocity.x * deltaTime);
  const deltaLat = metersToDegreesLat(velocity.y * deltaTime);
  const deltaAlt = velocity.z * deltaTime;

  return {
    ...viewState,
    longitude: viewState.longitude + deltaLng,
    latitude: viewState.latitude + deltaLat,
    position: [
      viewState.position[0], // Keep meter offset X unchanged
      viewState.position[1], // Keep meter offset Y unchanged
      viewState.position[2] + deltaAlt, // Only Z (altitude) changes
    ],
  };
}

/**
 * Set view state altitude with smooth interpolation
 *
 * Only modifies position[2] (Z/altitude). longitude/latitude are unchanged.
 *
 * @param viewState - Current view state
 * @param groundElevation - Ground elevation at current position in meters
 * @param eyeHeight - Eye height above ground in meters
 * @param smooth - Smoothing factor (0 = instant, approaching 1 = slower)
 * @returns Updated view state with new altitude
 */
export function setAltitude(
  viewState: FirstPersonViewState,
  groundElevation: number,
  eyeHeight: number,
  smooth: number = 0
): FirstPersonViewState {
  const targetAltitude = groundElevation + eyeHeight;

  // If no smoothing, set directly
  if (smooth <= 0) {
    return {
      ...viewState,
      position: [0, 0, targetAltitude],
    };
  }

  // Smooth interpolation using lerp
  // smooth is like inertia: higher = slower transition
  const t = 1 - smooth;
  const currentAltitude = viewState.position[2];
  const newAltitude = currentAltitude + (targetAltitude - currentAltitude) * t;

  return {
    ...viewState,
    position: [0, 0, newAltitude],
  };
}

/**
 * Set view state position directly (for collision response)
 *
 * Updates longitude/latitude. The position array's X/Y stay at 0.
 */
export function setPosition(
  viewState: FirstPersonViewState,
  lng: number,
  lat: number,
  alt?: number
): FirstPersonViewState {
  return {
    ...viewState,
    longitude: lng,
    latitude: lat,
    position: [0, 0, alt ?? viewState.position[2]],
  };
}

/**
 * Get the forward direction vector from bearing
 * Returns [dx, dy] where dx is East and dy is North, normalized
 */
export function getForwardDirection(bearing: number): [number, number] {
  const DEG_TO_RAD = Math.PI / 180;
  // Bearing: 0 = North, 90 = East
  // We need: forward vector in (East, North) coordinates
  const rad = bearing * DEG_TO_RAD;
  return [Math.sin(rad), Math.cos(rad)];
}

/**
 * Get the right direction vector from bearing
 * Returns [dx, dy] where dx is East and dy is North, normalized
 */
export function getRightDirection(bearing: number): [number, number] {
  const DEG_TO_RAD = Math.PI / 180;
  // Right is 90 degrees clockwise from forward
  const rad = (bearing + 90) * DEG_TO_RAD;
  return [Math.sin(rad), Math.cos(rad)];
}
