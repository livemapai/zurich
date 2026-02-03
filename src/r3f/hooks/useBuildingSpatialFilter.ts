/**
 * useBuildingSpatialFilter - SpatialIndex-Based Building Filtering
 *
 * Uses RBush spatial index for O(log n) queries instead of O(n) linear scan.
 * This is critical for performance with 65K+ buildings.
 *
 * PERFORMANCE CHARACTERISTICS:
 * - Index construction: O(n log n) once
 * - Per-query: O(log n + k) where k is number of results
 * - Position snapping: Prevents constant re-queries
 *
 * COMPARISON WITH useDistanceFilter:
 * - useDistanceFilter: O(n) per update - too slow for 65K buildings
 * - useBuildingSpatialFilter: O(log n + k) per update - fast!
 */

import { useMemo, useRef, useState, useEffect } from 'react';
import type { BuildingFeature } from '@/types';
import { METERS_PER_DEGREE } from '@/types';
import { createSpatialIndex } from '@/systems/SpatialIndex';

/** Distance player must move before rebuilding visible set (meters) */
const UPDATE_DISTANCE_METERS = 100;

/** Default render distance for buildings (meters) */
const DEFAULT_RENDER_DISTANCE = 750;

interface UseBuildingSpatialFilterOptions {
  /** Maximum distance to render buildings in meters */
  renderDistance?: number;
  /** Distance player must move to trigger update (meters) */
  updateThreshold?: number;
}

/**
 * Filter buildings by distance from player using spatial index.
 *
 * @param features - All building features
 * @param playerPosition - Player [lng, lat] position
 * @param options - Configuration options
 * @returns Array of nearby building features
 *
 * @example
 * ```tsx
 * const visibleBuildings = useBuildingSpatialFilter(
 *   buildings.features,
 *   [playerPos.lng, playerPos.lat],
 *   { renderDistance: 750 }
 * );
 * ```
 */
export function useBuildingSpatialFilter(
  features: BuildingFeature[],
  playerPosition: [number, number] | undefined,
  options: UseBuildingSpatialFilterOptions = {}
): BuildingFeature[] {
  const {
    renderDistance = DEFAULT_RENDER_DISTANCE,
    updateThreshold = UPDATE_DISTANCE_METERS,
  } = options;

  // Default to Zurich center if no position provided
  const effectivePos = playerPosition ?? [8.5437, 47.3739] as [number, number];

  // Track last update position
  const lastUpdatePosRef = useRef<[number, number]>([0, 0]);

  // Visible features state
  const [visibleFeatures, setVisibleFeatures] = useState<BuildingFeature[]>([]);

  // Build spatial index once when features change
  const spatialIndex = useMemo(() => {
    if (!features || features.length === 0) return null;

    const start = performance.now();
    const index = createSpatialIndex();
    index.load({ type: 'FeatureCollection', features });
    const elapsed = performance.now() - start;

    console.log(`Built building spatial index (${features.length} features) in ${elapsed.toFixed(1)}ms`);

    return index;
  }, [features]);

  // Update visible features when player moves significantly
  useEffect(() => {
    if (!spatialIndex || !features || features.length === 0) {
      setVisibleFeatures([]);
      return;
    }

    const [playerLng, playerLat] = effectivePos;
    const [lastLng, lastLat] = lastUpdatePosRef.current;

    // Calculate distance moved since last update
    const dLng = (playerLng - lastLng) * METERS_PER_DEGREE.lng;
    const dLat = (playerLat - lastLat) * METERS_PER_DEGREE.lat;
    const distanceMoved = Math.sqrt(dLng * dLng + dLat * dLat);

    // Skip if we haven't moved enough (and we have results)
    if (distanceMoved < updateThreshold && visibleFeatures.length > 0) {
      return;
    }

    // Update last position
    lastUpdatePosRef.current = [playerLng, playerLat];

    // Query for nearby buildings using SpatialIndex O(log n) lookup
    const start = performance.now();
    const nearby = spatialIndex.getNearby([playerLng, playerLat], renderDistance);
    const elapsed = performance.now() - start;

    console.log(
      `Building spatial query: ${nearby.length} of ${features.length} (${elapsed.toFixed(1)}ms) @ ${renderDistance}m`
    );

    setVisibleFeatures(nearby);
  }, [
    effectivePos[0],
    effectivePos[1],
    spatialIndex,
    renderDistance,
    updateThreshold,
    features,
    visibleFeatures.length,
  ]);

  return visibleFeatures;
}

export default useBuildingSpatialFilter;
