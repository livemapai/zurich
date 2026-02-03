/**
 * Buildings - 3D Building Mesh Layer with Distance-Based Rendering
 *
 * Renders extruded building geometries from GeoJSON data.
 * Buildings are filtered by distance and merged into batches for performance.
 *
 * PERFORMANCE OPTIMIZATIONS:
 * - SpatialIndex for O(log n) distance queries (vs O(n) linear scan)
 * - Only creates geometry for buildings within 750m radius (~2500 buildings)
 * - Geometries are merged to reduce draw calls (hundreds → few)
 * - Vertex limit per batch ensures 16-bit indices work
 * - Per-building geometry cache survives React Strict Mode remounts
 * - Shadow casting disabled (major GPU savings)
 *
 * VISUAL STYLE:
 * - Warm beige/tan color matching real buildings
 * - Receives shadows for depth perception (but doesn't cast)
 * - Flat shading for crisp architectural edges
 */

import { useRef, useEffect, useState } from 'react';
import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import type { BuildingFeature } from '@/types';
import { createBuildingGeometry, type ElevationCallback } from '../geometry/buildingGeometry';
import { useBuildingSpatialFilter } from '../hooks/useBuildingSpatialFilter';
import { CONFIG } from '@/lib/config';

/**
 * Module-level cache for individual building geometries.
 * Keyed by building ID for precise cache hits.
 */
const buildingGeometryCache = new Map<string | number, THREE.BufferGeometry>();

/** Default render distance for buildings (meters) */
const BUILDING_RENDER_DISTANCE = 750;

/** Maximum vertices per merged batch (16-bit indices limit) */
const MAX_VERTICES_PER_BATCH = 65000;

interface BuildingsProps {
  /** Array of building features from GeoJSON */
  features: BuildingFeature[];
  /** Building color (default: warm beige) */
  color?: string;
  /** Whether buildings receive shadows (default: true) */
  receiveShadow?: boolean;
  /** Opacity (default: 1.0) */
  opacity?: number;
  /** Use flat shading for crisp edges (default: true) */
  flatShading?: boolean;
  /** Callback to get terrain elevation at [lng, lat] */
  getElevation?: ElevationCallback;
  /** Player position [lng, lat] for distance-based rendering */
  playerPosition?: [number, number];
  /** Maximum distance to render buildings in meters (default: 750) */
  renderDistance?: number;
}

/**
 * Single building batch mesh component.
 */
function BuildingBatch({
  geometry,
  color,
  receiveShadow,
  opacity,
  flatShading,
}: {
  geometry: THREE.BufferGeometry;
  color: string;
  receiveShadow: boolean;
  opacity: number;
  flatShading: boolean;
}) {
  return (
    <mesh geometry={geometry} castShadow={false} receiveShadow={receiveShadow}>
      <meshStandardMaterial
        color={color}
        flatShading={flatShading}
        transparent={opacity < 1}
        opacity={opacity}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

/**
 * Get or create geometry for a building feature.
 * Uses module-level cache keyed by building ID.
 */
function getOrCreateBuildingGeometry(
  feature: BuildingFeature,
  getElevation?: ElevationCallback
): THREE.BufferGeometry | null {
  const buildingId = feature.properties.id;

  // Check cache first
  const cached = buildingGeometryCache.get(buildingId);
  if (cached) {
    return cached;
  }

  // Create new geometry
  const geom = createBuildingGeometry(feature, {}, getElevation);
  if (geom) {
    buildingGeometryCache.set(buildingId, geom);
  }

  return geom;
}

/**
 * Create merged batches from an array of building features.
 * Uses per-building geometry cache for efficiency.
 */
function createMergedBatches(
  features: BuildingFeature[],
  getElevation?: ElevationCallback
): THREE.BufferGeometry[] {
  const batches: THREE.BufferGeometry[] = [];
  let currentBatch: THREE.BufferGeometry[] = [];
  let currentVertexCount = 0;

  for (const feature of features) {
    const geom = getOrCreateBuildingGeometry(feature, getElevation);
    if (!geom) continue;

    const vertexCount = geom.getAttribute('position').count;

    // If adding this geometry would exceed the limit, merge current batch
    if (currentVertexCount + vertexCount > MAX_VERTICES_PER_BATCH && currentBatch.length > 0) {
      const merged = mergeGeometries(currentBatch, false);
      if (merged) {
        batches.push(merged);
      }
      currentBatch = [];
      currentVertexCount = 0;
    }

    currentBatch.push(geom);
    currentVertexCount += vertexCount;
  }

  // Merge remaining geometries
  if (currentBatch.length > 0) {
    const merged = mergeGeometries(currentBatch, false);
    if (merged) {
      batches.push(merged);
    }
  }

  return batches;
}

/**
 * Buildings layer component with distance-based rendering.
 *
 * KEY OPTIMIZATION: Uses SpatialIndex to query only nearby buildings (O(log n))
 * instead of processing all 65K buildings. This reduces geometry creation from
 * 65K buildings to ~2500 (at 750m radius), a 96% reduction.
 */
export function Buildings({
  features,
  color = '#d4c4a8', // Warm beige
  receiveShadow = true,
  opacity = 1.0,
  flatShading = true,
  getElevation,
  playerPosition,
  renderDistance = BUILDING_RENDER_DISTANCE,
}: BuildingsProps) {
  // Ref to track elevation callback without triggering rebuilds
  const getElevationRef = useRef(getElevation);
  getElevationRef.current = getElevation;

  // Filter buildings by distance using SpatialIndex (O(log n) query)
  const visibleFeatures = useBuildingSpatialFilter(features, playerPosition, {
    renderDistance,
    updateThreshold: 100, // Update when player moves 100m
  });

  // Track the last set of visible features to avoid unnecessary rebuilds
  const lastVisibleCountRef = useRef(0);
  const [geometryBatches, setGeometryBatches] = useState<THREE.BufferGeometry[]>([]);

  // Create merged geometries from visible features
  // Uses requestIdleCallback for non-blocking geometry creation
  useEffect(() => {
    if (!visibleFeatures || visibleFeatures.length === 0) {
      setGeometryBatches([]);
      lastVisibleCountRef.current = 0;
      return;
    }

    // Skip if count hasn't changed significantly (within 10%)
    const countDiff = Math.abs(visibleFeatures.length - lastVisibleCountRef.current);
    const significantChange = countDiff > lastVisibleCountRef.current * 0.1 || countDiff > 50;

    if (!significantChange && geometryBatches.length > 0) {
      return;
    }

    lastVisibleCountRef.current = visibleFeatures.length;

    // Use requestIdleCallback for non-blocking geometry creation
    const startGeometryCreation = () => {
      const start = performance.now();

      const batches = createMergedBatches(visibleFeatures, getElevationRef.current);

      const elapsed = performance.now() - start;

      if (CONFIG.debug.logPerformance) {
        console.log(
          `Buildings: Created ${batches.length} batches from ${visibleFeatures.length} buildings in ${elapsed.toFixed(1)}ms`
        );
      }

      setGeometryBatches(batches);
    };

    // Try to use requestIdleCallback for non-blocking creation
    if ('requestIdleCallback' in window) {
      (window as Window & typeof globalThis & { requestIdleCallback: (cb: () => void) => number }).requestIdleCallback(
        startGeometryCreation,
        { timeout: 500 }
      );
    } else {
      // Fallback to setTimeout
      setTimeout(startGeometryCreation, 0);
    }
  }, [visibleFeatures, geometryBatches.length]);

  // Log visible building count for debugging
  useEffect(() => {
    if (visibleFeatures.length > 0 && features.length > 0) {
      const percentage = ((visibleFeatures.length / features.length) * 100).toFixed(1);
      console.log(
        `Rendering ${visibleFeatures.length} buildings of ${features.length} total (${percentage}%)`
      );
    }
  }, [visibleFeatures.length, features.length]);

  if (geometryBatches.length === 0) {
    return null;
  }

  return (
    <group name="buildings">
      {geometryBatches.map((geometry, index) => (
        <BuildingBatch
          key={`building-batch-${index}`}
          geometry={geometry}
          color={color}
          receiveShadow={receiveShadow}
          opacity={opacity}
          flatShading={flatShading}
        />
      ))}
    </group>
  );
}

export default Buildings;
