/**
 * BuildingColliders - Dynamic Physics Colliders for Buildings
 *
 * Creates Rapier physics colliders only for nearby buildings to reduce CPU overhead.
 * Colliders are recreated when player moves significantly from last update position.
 *
 * PERFORMANCE OPTIMIZATIONS:
 * - Only creates colliders for buildings within CONFIG.performance.colliderRadius
 * - Limits total colliders to CONFIG.performance.maxActiveColliders
 * - Uses SpatialIndex.getNearby() for efficient spatial query
 * - Position snapping prevents constant collider recreation
 *
 * COLLIDER TYPES:
 * - TrimeshCollider: Precise collision using actual building mesh (expensive)
 * - CuboidCollider: Simple AABB box approximation (cheap, less accurate)
 *
 * RAPIER COORDINATE SYSTEM:
 * - Same as Three.js: Y is up
 * - Buildings are positioned at their scene coordinates
 */

import { useMemo, useRef, useEffect, useState } from 'react';
import { RigidBody, CuboidCollider } from '@react-three/rapier';
import type { BuildingFeature } from '@/types';
import { METERS_PER_DEGREE } from '@/types';
import { CONFIG } from '@/lib/config';
import { createBuildingBounds, type ElevationCallback } from '../geometry/buildingGeometry';
import { createSpatialIndex } from '@/systems/SpatialIndex';

interface BuildingCollidersProps {
  /** Array of building features from GeoJSON */
  features: BuildingFeature[];
  /** Player position [lng, lat] for proximity-based colliders */
  playerPosition?: [number, number];
  /** Use simple box colliders instead of mesh colliders (default: true for performance) */
  useBoxColliders?: boolean;
  /** Maximum distance to create colliders in meters (default: from config) */
  colliderRadius?: number;
  /** Maximum number of active colliders (default: from config) */
  maxColliders?: number;
  /** Callback to get terrain elevation at [lng, lat] */
  getElevation?: ElevationCallback;
}

/** Distance in meters before updating colliders */
const UPDATE_DISTANCE_METERS = 50;

/**
 * Single building box collider.
 */
function BuildingBoxCollider({
  feature,
  index,
  getElevation,
}: {
  feature: BuildingFeature;
  index: number;
  getElevation?: ElevationCallback;
}) {
  const bounds = useMemo(() => createBuildingBounds(feature, getElevation), [feature, getElevation]);

  if (!bounds) return null;

  const { dimensions, center } = bounds;
  const [width, height, depth] = dimensions;
  const [x, y, z] = center;

  // Cuboid uses half-extents
  const halfWidth = width / 2;
  const halfHeight = height / 2;
  const halfDepth = depth / 2;

  return (
    <RigidBody
      key={`building-collider-${index}`}
      type="fixed"
      position={[x, y, z]}
      colliders={false}
    >
      <CuboidCollider args={[halfWidth, halfHeight, halfDepth]} />
    </RigidBody>
  );
}

/**
 * BuildingColliders - Creates physics colliders for nearby buildings.
 *
 * Uses dynamic collider creation based on player position:
 * 1. Builds a SpatialIndex from all building features
 * 2. Queries for nearest buildings within colliderRadius
 * 3. Creates colliders only for those buildings
 * 4. Updates when player moves > UPDATE_DISTANCE_METERS
 */
export function BuildingColliders({
  features,
  playerPosition,
  useBoxColliders = true,
  colliderRadius = CONFIG.performance.colliderRadius,
  maxColliders = CONFIG.performance.maxActiveColliders,
  getElevation,
}: BuildingCollidersProps) {
  // Default player position (Zurich center)
  const effectivePlayerPos = playerPosition ?? [8.5437, 47.3739] as [number, number];

  // Track last update position
  const lastUpdatePosRef = useRef<[number, number]>([0, 0]);

  // State for visible colliders
  const [visibleFeatures, setVisibleFeatures] = useState<BuildingFeature[]>([]);

  // Build spatial index once when features change
  const spatialIndex = useMemo(() => {
    const index = createSpatialIndex();
    index.load({ type: 'FeatureCollection', features });
    return index;
  }, [features]);

  // For now, we only support box colliders
  if (!useBoxColliders) {
    console.warn('BuildingColliders: Only box colliders are currently supported');
  }

  // Update visible colliders when player moves significantly
  useEffect(() => {
    const [playerLng, playerLat] = effectivePlayerPos;
    const [lastLng, lastLat] = lastUpdatePosRef.current;

    // Calculate distance moved since last update
    const dLng = (playerLng - lastLng) * METERS_PER_DEGREE.lng;
    const dLat = (playerLat - lastLat) * METERS_PER_DEGREE.lat;
    const distanceMoved = Math.sqrt(dLng * dLng + dLat * dLat);

    // Skip if we haven't moved enough (and we have colliders)
    if (distanceMoved < UPDATE_DISTANCE_METERS && visibleFeatures.length > 0) {
      return;
    }

    // Update last position
    lastUpdatePosRef.current = [playerLng, playerLat];

    // Query for nearby buildings
    const nearby = spatialIndex.getNearby(
      [playerLng, playerLat],
      colliderRadius,
      maxColliders
    );

    // Filter to only valid features (those that can create bounds)
    const validNearby = nearby.filter((f) => {
      const bounds = createBuildingBounds(f, getElevation);
      return bounds !== null;
    });

    if (CONFIG.debug.logPerformance) {
      console.log(
        `BuildingColliders: Creating ${validNearby.length} colliders (of ${features.length} total)`
      );
    }

    setVisibleFeatures(validNearby);
  }, [
    effectivePlayerPos[0],
    effectivePlayerPos[1],
    spatialIndex,
    colliderRadius,
    maxColliders,
    features.length,
    visibleFeatures.length,
    getElevation,
  ]);

  if (visibleFeatures.length === 0) {
    return null;
  }

  return (
    <group name="building-colliders">
      {visibleFeatures.map((feature, index) => (
        <BuildingBoxCollider
          key={`${feature.properties.id}-${index}`}
          feature={feature}
          index={index}
          getElevation={getElevation}
        />
      ))}
    </group>
  );
}

export default BuildingColliders;
