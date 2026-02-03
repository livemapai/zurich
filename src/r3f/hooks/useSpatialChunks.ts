/**
 * useSpatialChunks - React Hook for Spatial Chunking
 *
 * Provides a React-friendly interface to SpatialChunkManager.
 * Handles manager creation, feature loading, and memoized queries.
 *
 * USAGE:
 * ```tsx
 * const visibleTrees = useSpatialChunks(
 *   allTrees,
 *   [playerLng, playerLat],
 *   500, // meters
 *   (tree) => tree.geometry.coordinates
 * );
 * ```
 *
 * PERFORMANCE:
 * - Manager is recreated only when features array changes
 * - Query results are cached until position changes significantly
 * - Uses position snapping to prevent excessive recalculation
 */

import { useMemo, useRef } from 'react';
import type { LngLat } from '@/types';
import {
  SpatialChunkManager,
  createSpatialChunkManager,
  type SpatialChunkConfig,
} from '../systems/SpatialChunkManager';

/** Snap distance in meters - only recalculate when player moves this far */
const SNAP_DISTANCE_METERS = 10;

/**
 * Query features within a radius using spatial chunking.
 *
 * This hook provides O(k) spatial queries where k is the number of cells
 * in the query radius (typically 9-25), instead of O(n) distance checks.
 *
 * @param features - Array of features to index
 * @param playerPosition - Current player position [lng, lat]
 * @param radiusMeters - Query radius in meters
 * @param getCoords - Function to extract [lng, lat] from a feature
 * @param config - Optional configuration for cell size
 * @returns Array of features within radius
 *
 * @example
 * ```tsx
 * const visibleTrees = useSpatialChunks(
 *   trees,
 *   [8.5437, 47.3739],
 *   500,
 *   (t) => t.geometry.coordinates
 * );
 * ```
 */
export function useSpatialChunks<T>(
  features: T[],
  playerPosition: [lng: number, lat: number],
  radiusMeters: number,
  getCoords: (feature: T) => LngLat,
  config?: SpatialChunkConfig
): T[] {
  // Create and load the spatial manager when features change
  const managerRef = useRef<SpatialChunkManager<T> | null>(null);
  const featuresRef = useRef<T[]>([]);

  // Track snapped position for cache invalidation
  const lastQueryRef = useRef<{
    lng: number;
    lat: number;
    radius: number;
    result: T[];
  } | null>(null);

  // Recreate manager only when features change (reference equality)
  const manager = useMemo(() => {
    // Check if features actually changed
    if (features === featuresRef.current && managerRef.current) {
      return managerRef.current;
    }

    // Create new manager and load features
    const newManager = createSpatialChunkManager(getCoords, config);
    newManager.load(features);

    // Update refs
    managerRef.current = newManager;
    featuresRef.current = features;

    // Invalidate query cache when manager changes
    lastQueryRef.current = null;

    return newManager;
  }, [features, getCoords, config]);

  // Query for visible features
  return useMemo(() => {
    const [lng, lat] = playerPosition;

    // Check if we can use cached result
    const lastQuery = lastQueryRef.current;
    if (lastQuery) {
      const dLng = Math.abs(lng - lastQuery.lng) * 75500; // approx meters at 47°N
      const dLat = Math.abs(lat - lastQuery.lat) * 111320;
      const moved = Math.sqrt(dLng * dLng + dLat * dLat);

      if (moved < SNAP_DISTANCE_METERS && radiusMeters === lastQuery.radius) {
        return lastQuery.result;
      }
    }

    // Perform query
    const result = manager.queryRadius(lng, lat, radiusMeters);

    // Cache result
    lastQueryRef.current = {
      lng,
      lat,
      radius: radiusMeters,
      result: result.features,
    };

    return result.features;
  }, [manager, playerPosition[0], playerPosition[1], radiusMeters]);
}

/**
 * Get statistics about the spatial index (for debugging)
 */
export function useSpatialChunkStats<T>(
  features: T[],
  getCoords: (feature: T) => LngLat,
  config?: SpatialChunkConfig
): {
  featureCount: number;
  cellCount: number;
  cellSizeMeters: number;
  avgFeaturesPerCell: number;
} {
  return useMemo(() => {
    const manager = createSpatialChunkManager(getCoords, config);
    manager.load(features);
    return manager.getStats();
  }, [features, getCoords, config]);
}

export default useSpatialChunks;
