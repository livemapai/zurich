/**
 * AltitudeSystem - Centralized altitude management
 *
 * Single source of truth for all altitude calculations:
 * - Minimum altitude (terrain-based)
 * - Maximum altitude (fly mode limit)
 * - Vertical velocity application
 * - Terrain following with smoothing
 *
 * COORDINATE SYSTEM:
 * deck.gl FirstPersonView uses position[2] as ABSOLUTE altitude in meters above sea level.
 * Example: Zurich ground ~408m + eye height 1.7m = 409.7m altitude
 */

import type { LngLat } from '@/types';

/**
 * Options for creating an AltitudeSystem
 */
export interface AltitudeSystemOptions {
  /** Eye height above ground in meters (typically 1.7m) */
  eyeHeight: number;
  /** Maximum altitude for fly mode in meters */
  maxAltitude: number;
  /** Function to get ground elevation at a position */
  getGroundElevation: (position: LngLat) => number;
}

/**
 * AltitudeSystem - Manages all altitude-related calculations
 *
 * Usage:
 * ```typescript
 * const altitudeSystem = new AltitudeSystem({
 *   eyeHeight: 1.7,
 *   maxAltitude: 1000,
 *   getGroundElevation: (pos) => terrainSampler.getElevationOrDefault(pos, 408),
 * });
 *
 * // Flying: apply vertical velocity with clamping
 * const newAlt = altitudeSystem.applyVerticalVelocity(currentAlt, velocityZ, deltaTime, position);
 *
 * // Walking: smooth terrain following
 * const newAlt = altitudeSystem.smoothToTerrain(currentAlt, position, 0.7);
 * ```
 */
export class AltitudeSystem {
  private readonly eyeHeight: number;
  private readonly maxAltitude: number;
  private readonly getGroundElevation: (position: LngLat) => number;

  constructor(options: AltitudeSystemOptions) {
    this.eyeHeight = options.eyeHeight;
    this.maxAltitude = options.maxAltitude;
    this.getGroundElevation = options.getGroundElevation;
  }

  /**
   * Get minimum allowed altitude at a position (ground + eyeHeight)
   *
   * This is the lowest the player can be - standing on the terrain.
   *
   * @param position - Geographic position [lng, lat]
   * @returns Minimum altitude in meters above sea level
   */
  getMinAltitude(position: LngLat): number {
    const groundElev = this.getGroundElevation(position);
    return groundElev + this.eyeHeight;
  }

  /**
   * Get maximum allowed altitude
   *
   * @returns Maximum altitude in meters above sea level
   */
  getMaxAltitude(): number {
    return this.maxAltitude;
  }

  /**
   * Clamp altitude to valid range at a position
   *
   * @param altitude - Current altitude to clamp
   * @param position - Geographic position [lng, lat]
   * @returns Clamped altitude between minAlt and maxAlt
   */
  clampAltitude(altitude: number, position: LngLat): number {
    const minAlt = this.getMinAltitude(position);
    return Math.max(minAlt, Math.min(this.maxAltitude, altitude));
  }

  /**
   * Apply vertical velocity with clamping (for fly mode)
   *
   * Calculates new altitude from vertical velocity and clamps to valid range.
   *
   * @param currentAltitude - Current altitude in meters
   * @param velocityZ - Vertical velocity in m/s (positive = up)
   * @param deltaTime - Time since last frame in seconds
   * @param position - Geographic position [lng, lat]
   * @returns New altitude clamped to valid range
   */
  applyVerticalVelocity(
    currentAltitude: number,
    velocityZ: number,
    deltaTime: number,
    position: LngLat
  ): number {
    const newAltitude = currentAltitude + velocityZ * deltaTime;
    return this.clampAltitude(newAltitude, position);
  }

  /**
   * Get terrain-following altitude at a position
   *
   * @param position - Geographic position [lng, lat]
   * @returns Altitude for standing on terrain (ground + eyeHeight)
   */
  getTerrainAltitude(position: LngLat): number {
    return this.getMinAltitude(position);
  }

  /**
   * Smoothly interpolate current altitude to terrain altitude
   *
   * Used for terrain following when walking. The smoothing prevents
   * jarring altitude changes when crossing terrain height boundaries.
   *
   * @param currentAltitude - Current altitude in meters
   * @param position - Geographic position [lng, lat]
   * @param smoothFactor - Smoothing factor (0 = instant, approaching 1 = slower)
   *                       Typical value: 0.7 for smooth walking
   * @returns Interpolated altitude
   */
  smoothToTerrain(
    currentAltitude: number,
    position: LngLat,
    smoothFactor: number
  ): number {
    const targetAltitude = this.getTerrainAltitude(position);

    // If no smoothing, snap to terrain
    if (smoothFactor <= 0) {
      return targetAltitude;
    }

    // Lerp towards target altitude
    // t = 1 - smoothFactor: higher smoothFactor = slower transition
    const t = 1 - smoothFactor;
    return currentAltitude + (targetAltitude - currentAltitude) * t;
  }

  /**
   * Check if an altitude is at or near the terrain level
   *
   * @param altitude - Altitude to check
   * @param position - Geographic position
   * @param tolerance - Distance from terrain to consider "on ground" (default 0.1m)
   * @returns true if within tolerance of terrain altitude
   */
  isOnTerrain(altitude: number, position: LngLat, tolerance: number = 0.1): number {
    const terrainAlt = this.getTerrainAltitude(position);
    return Math.abs(altitude - terrainAlt) <= tolerance ? 1 : 0;
  }

  /**
   * Get the current eye height setting
   */
  getEyeHeight(): number {
    return this.eyeHeight;
  }
}

/**
 * Create an AltitudeSystem instance
 *
 * @param options - Configuration options
 * @returns New AltitudeSystem instance
 */
export function createAltitudeSystem(options: AltitudeSystemOptions): AltitudeSystem {
  return new AltitudeSystem(options);
}
