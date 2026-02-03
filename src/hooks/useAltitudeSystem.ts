/**
 * useAltitudeSystem - Hook for centralized altitude management
 *
 * Combines terrain elevation data with altitude system configuration
 * to provide a single interface for all altitude operations.
 *
 * Uses ref pattern to ensure callback stability for game loop.
 */

import { useRef, useCallback } from 'react';
import { createAltitudeSystem, AltitudeSystem } from '@/systems';
import { CONFIG } from '@/lib/config';
import type { LngLat } from '@/types';

interface UseAltitudeSystemOptions {
  /** Function to get terrain elevation at a position */
  getGroundElevation: (position: LngLat) => number;
  /** Eye height override (default: CONFIG.player.eyeHeight) */
  eyeHeight?: number;
  /** Max altitude override (default: CONFIG.player.maxAltitude) */
  maxAltitude?: number;
}

interface UseAltitudeSystemResult {
  /** Apply vertical velocity with clamping (for fly mode) */
  applyVerticalVelocity: (
    currentAltitude: number,
    velocityZ: number,
    deltaTime: number,
    position: LngLat
  ) => number;
  /** Smooth terrain following (for walking) */
  smoothToTerrain: (
    currentAltitude: number,
    position: LngLat,
    smoothFactor: number
  ) => number;
  /** Get minimum altitude at position */
  getMinAltitude: (position: LngLat) => number;
  /** Clamp altitude to valid range */
  clampAltitude: (altitude: number, position: LngLat) => number;
}

/**
 * Hook to create and manage an AltitudeSystem
 *
 * Uses ref pattern to ensure stable callback references for game loop.
 * This prevents unnecessary re-renders when dependencies change.
 *
 * @example
 * ```typescript
 * const { getElevationOrDefault } = useTerrainElevation({ enabled: true });
 * const { applyVerticalVelocity, smoothToTerrain } = useAltitudeSystem({
 *   getGroundElevation: getElevationOrDefault,
 * });
 *
 * // In game loop:
 * const newAlt = isFlying
 *   ? applyVerticalVelocity(currentAlt, velocity.z, deltaTime, position)
 *   : smoothToTerrain(currentAlt, position, 0.7);
 * ```
 */
export function useAltitudeSystem(
  options: UseAltitudeSystemOptions
): UseAltitudeSystemResult {
  const {
    getGroundElevation,
    eyeHeight = CONFIG.player.eyeHeight,
    maxAltitude = CONFIG.player.maxAltitude,
  } = options;

  // Store altitude system in ref to avoid recreation
  // Update the ref on every render with latest settings
  const altitudeSystemRef = useRef<AltitudeSystem | null>(null);

  // Create or update altitude system
  // We recreate when settings change, but store in ref for stable access
  if (
    !altitudeSystemRef.current ||
    altitudeSystemRef.current.getEyeHeight() !== eyeHeight ||
    altitudeSystemRef.current.getMaxAltitude() !== maxAltitude
  ) {
    altitudeSystemRef.current = createAltitudeSystem({
      eyeHeight,
      maxAltitude,
      getGroundElevation,
    });
  }

  // Update the ground elevation function on every render (it's stored by ref in AltitudeSystem)
  // This ensures we always use the latest terrain data
  const getGroundElevationRef = useRef(getGroundElevation);
  getGroundElevationRef.current = getGroundElevation;

  // Stable callback that uses refs - NEVER changes
  const applyVerticalVelocity = useCallback(
    (
      currentAltitude: number,
      velocityZ: number,
      deltaTime: number,
      position: LngLat
    ) => {
      const groundElev = getGroundElevationRef.current(position);
      const minAlt = groundElev + eyeHeight;
      const newAltitude = currentAltitude + velocityZ * deltaTime;
      return Math.max(minAlt, Math.min(maxAltitude, newAltitude));
    },
    [eyeHeight, maxAltitude]
  );

  // Stable callback that uses refs - NEVER changes
  const smoothToTerrain = useCallback(
    (currentAltitude: number, position: LngLat, smoothFactor: number) => {
      const groundElev = getGroundElevationRef.current(position);
      const targetAltitude = groundElev + eyeHeight;

      if (smoothFactor <= 0) {
        return targetAltitude;
      }

      const t = 1 - smoothFactor;
      return currentAltitude + (targetAltitude - currentAltitude) * t;
    },
    [eyeHeight]
  );

  const getMinAltitude = useCallback(
    (position: LngLat) => {
      const groundElev = getGroundElevationRef.current(position);
      return groundElev + eyeHeight;
    },
    [eyeHeight]
  );

  const clampAltitude = useCallback(
    (altitude: number, position: LngLat) => {
      const minAlt = getGroundElevationRef.current(position) + eyeHeight;
      return Math.max(minAlt, Math.min(maxAltitude, altitude));
    },
    [eyeHeight, maxAltitude]
  );

  return {
    applyVerticalVelocity,
    smoothToTerrain,
    getMinAltitude,
    clampAltitude,
  };
}
