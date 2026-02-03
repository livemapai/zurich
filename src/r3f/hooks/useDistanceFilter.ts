/**
 * useDistanceFilter - Distance-Based Feature Filtering
 *
 * Filters features by distance from camera position for performance optimization.
 * Uses position snapping to prevent constant recalculation on every frame.
 *
 * KEY OPTIMIZATIONS:
 * 1. Position snapping: Only recalculate when player moves > snapDistance
 * 2. Pre-computed meters-per-degree: Avoids expensive trig in hot path
 * 3. Euclidean approximation: Valid at local scales (< 10km)
 * 4. Memoized results: Returns same array reference when unchanged
 *
 * USAGE:
 * ```tsx
 * const visibleTrees = useDistanceFilter(
 *   allTrees,
 *   [playerLng, playerLat],
 *   500, // meters
 *   (tree) => tree.geometry.coordinates
 * );
 * ```
 */

import { useMemo, useRef } from 'react';
import { METERS_PER_DEGREE } from '@/types';
import type { LngLat } from '@/types';

/** Snap position to grid to prevent constant recalculation */
const SNAP_DISTANCE_METERS = 10;

/** Convert snap distance to degrees */
const SNAP_LNG = SNAP_DISTANCE_METERS / METERS_PER_DEGREE.lng;
const SNAP_LAT = SNAP_DISTANCE_METERS / METERS_PER_DEGREE.lat;

/**
 * Snap a position to a grid to reduce update frequency.
 * Returns stable position that only changes when crossing grid boundaries.
 */
function snapPosition(lng: number, lat: number): [number, number] {
  return [
    Math.round(lng / SNAP_LNG) * SNAP_LNG,
    Math.round(lat / SNAP_LAT) * SNAP_LAT,
  ];
}

/**
 * Calculate distance between two points in meters.
 * Uses Euclidean approximation (valid for local scales at constant latitude).
 */
function distanceMeters(
  lng1: number,
  lat1: number,
  lng2: number,
  lat2: number
): number {
  const dLng = (lng2 - lng1) * METERS_PER_DEGREE.lng;
  const dLat = (lat2 - lat1) * METERS_PER_DEGREE.lat;
  return Math.sqrt(dLng * dLng + dLat * dLat);
}

/**
 * Filter features by distance from camera position.
 *
 * @param features - Array of features to filter
 * @param playerPosition - Current player position [lng, lat]
 * @param maxDistanceMeters - Maximum distance in meters to include features
 * @param getCoords - Function to extract [lng, lat] from a feature
 * @returns Filtered array of features within distance
 *
 * @example
 * ```tsx
 * const visible = useDistanceFilter(
 *   trees,
 *   [8.5437, 47.3739],
 *   500,
 *   (t) => t.geometry.coordinates
 * );
 * ```
 */
export function useDistanceFilter<T>(
  features: T[],
  playerPosition: [lng: number, lat: number],
  maxDistanceMeters: number,
  getCoords: (feature: T) => LngLat
): T[] {
  // Track snapped position to avoid recalculating on minor movements
  const snappedPosRef = useRef<[number, number]>([0, 0]);
  const cachedResultRef = useRef<T[]>([]);

  return useMemo(() => {
    const [playerLng, playerLat] = playerPosition;
    const [snappedLng, snappedLat] = snapPosition(playerLng, playerLat);

    // Check if position has changed enough to warrant recalculation
    const [prevLng, prevLat] = snappedPosRef.current;
    if (
      snappedLng === prevLng &&
      snappedLat === prevLat &&
      cachedResultRef.current.length > 0
    ) {
      // Position hasn't changed significantly, return cached result
      return cachedResultRef.current;
    }

    // Update snapped position
    snappedPosRef.current = [snappedLng, snappedLat];

    // Filter features by distance
    const filtered = features.filter((feature) => {
      const coords = getCoords(feature);
      const dist = distanceMeters(playerLng, playerLat, coords[0], coords[1]);
      return dist <= maxDistanceMeters;
    });

    // Cache result
    cachedResultRef.current = filtered;

    return filtered;
  }, [features, playerPosition[0], playerPosition[1], maxDistanceMeters, getCoords]);
}

/**
 * Same as useDistanceFilter but returns indices instead of features.
 * Useful for instanced mesh rendering where you need to know which instances to show.
 *
 * @param features - Array of features
 * @param playerPosition - Current player position [lng, lat]
 * @param maxDistanceMeters - Maximum distance in meters
 * @param getCoords - Function to extract [lng, lat] from a feature
 * @returns Array of indices of visible features
 */
export function useDistanceFilterIndices<T>(
  features: T[],
  playerPosition: [lng: number, lat: number],
  maxDistanceMeters: number,
  getCoords: (feature: T) => LngLat
): number[] {
  const snappedPosRef = useRef<[number, number]>([0, 0]);
  const cachedResultRef = useRef<number[]>([]);

  return useMemo(() => {
    const [playerLng, playerLat] = playerPosition;
    const [snappedLng, snappedLat] = snapPosition(playerLng, playerLat);

    // Check if position has changed enough to warrant recalculation
    const [prevLng, prevLat] = snappedPosRef.current;
    if (
      snappedLng === prevLng &&
      snappedLat === prevLat &&
      cachedResultRef.current.length > 0
    ) {
      return cachedResultRef.current;
    }

    // Update snapped position
    snappedPosRef.current = [snappedLng, snappedLat];

    // Collect indices of features within distance
    const indices: number[] = [];
    for (let i = 0; i < features.length; i++) {
      const feature = features[i];
      if (!feature) continue;
      const coords = getCoords(feature);
      const dist = distanceMeters(playerLng, playerLat, coords[0], coords[1]);
      if (dist <= maxDistanceMeters) {
        indices.push(i);
      }
    }

    // Cache result
    cachedResultRef.current = indices;

    return indices;
  }, [features, playerPosition[0], playerPosition[1], maxDistanceMeters, getCoords]);
}

export default useDistanceFilter;
