/**
 * Trees - Instanced Tree Rendering with Distance Filtering
 *
 * Renders trees efficiently using Three.js InstancedMesh with distance-based culling.
 *
 * PERFORMANCE OPTIMIZATIONS:
 * - InstancedMesh renders visible trees in a single draw call
 * - Distance filtering: Only trees within render distance are processed
 * - Dynamic instance count: mesh.count is set to visible count only
 * - frustumCulled enabled: GPU further culls off-screen instances
 * - Position snapping: Prevents recalculation on minor player movements
 *
 * VISUAL STYLE:
 * - Simple cone geometry (matches deck.gl SimpleMeshLayer)
 * - Green color with slight variation possible
 * - Casts shadows for realism
 */

import { useRef, useEffect, useMemo } from 'react';
import * as THREE from 'three';
import type { TreeFeature, LngLat } from '@/types';
import { geoToScene } from '@/lib/coordinateSystem';
import { CONFIG } from '@/lib/config';
import { createTreeGeometry } from '../geometry/convertMesh';
import { useDistanceFilter } from '../hooks/useDistanceFilter';

/** Type for elevation callback function */
type ElevationCallback = (lng: number, lat: number) => number;

interface TreesProps {
  /** Array of tree features from GeoJSON */
  features: TreeFeature[];
  /** Player position [lng, lat] for distance filtering */
  playerPosition?: [number, number];
  /** Base color for trees (default: forest green) */
  color?: string;
  /** Whether trees cast shadows (default: true) */
  castShadow?: boolean;
  /** Whether trees receive shadows (default: false) */
  receiveShadow?: boolean;
  /** Maximum render distance in meters (default: from config) */
  renderDistance?: number;
  /** Callback to get terrain elevation at [lng, lat] */
  getElevation?: ElevationCallback;
}

/** Extract coordinates from a tree feature */
const getTreeCoords = (tree: TreeFeature): LngLat => tree.geometry.coordinates;

/**
 * Trees component using InstancedMesh with distance-based filtering.
 *
 * KEY OPTIMIZATIONS:
 * 1. Only visible trees (within renderDistance) are set up in instance matrix
 * 2. mesh.count is dynamically set to visible count
 * 3. frustumCulled is enabled for GPU-side culling
 * 4. Instance matrices are only updated when visible set changes
 */
export function Trees({
  features,
  playerPosition,
  color = '#228B22', // Forest green
  castShadow = true,
  receiveShadow = false,
  renderDistance = CONFIG.performance.treeRenderDistance,
  getElevation,
}: TreesProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const prevVisibleCountRef = useRef<number>(0);

  // Default player position if not provided (Zurich center)
  const effectivePlayerPos = playerPosition ?? [8.5437, 47.3739] as [number, number];

  // Filter features by distance from player
  const visibleFeatures = useDistanceFilter(
    features,
    effectivePlayerPos,
    renderDistance,
    getTreeCoords
  );

  // Create shared geometry (unit tree that gets scaled per instance)
  const geometry = useMemo(() => createTreeGeometry(), []);

  // Create shared material
  const material = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color,
        flatShading: true,
      }),
    [color]
  );

  // Update instance matrices when visible features change
  useEffect(() => {
    if (!meshRef.current) return;

    const mesh = meshRef.current;
    const visibleCount = visibleFeatures.length;

    // Skip update if count is the same (features didn't change meaningfully)
    if (visibleCount === prevVisibleCountRef.current && visibleCount > 0) {
      return;
    }

    prevVisibleCountRef.current = visibleCount;

    const matrix = new THREE.Matrix4();
    const position = new THREE.Vector3();
    const quaternion = new THREE.Quaternion();
    const scale = new THREE.Vector3();

    if (CONFIG.debug.logPerformance) {
      console.log(`Trees: Updating ${visibleCount} visible instances (of ${features.length} total)`);
    }

    const start = performance.now();

    visibleFeatures.forEach((feature, i) => {
      const coords = feature.geometry.coordinates;
      const props = feature.properties;

      // Convert geographic coordinates to scene position
      const [x, , z] = geoToScene(coords[0], coords[1], 0);

      // Get terrain elevation at this position
      const elevation = getElevation ? getElevation(coords[0], coords[1]) : 0;
      position.set(x, elevation, z);

      // No rotation needed for trees
      quaternion.identity();

      // Scale based on tree properties
      const height = props.height || 10;
      const crownDiameter = props.crown_diameter || 5;
      const scaleXZ = crownDiameter / 5; // Normalize to base diameter
      const scaleY = height / 10; // Normalize to base height
      scale.set(scaleXZ, scaleY, scaleXZ);

      // Compose the transformation matrix
      matrix.compose(position, quaternion, scale);
      mesh.setMatrixAt(i, matrix);
    });

    // Set visible count (crucial for performance!)
    mesh.count = visibleCount;

    // Mark instance matrix as needing update
    mesh.instanceMatrix.needsUpdate = true;

    if (CONFIG.debug.logPerformance) {
      const elapsed = performance.now() - start;
      console.log(`Trees: Updated ${visibleCount} instances in ${elapsed.toFixed(1)}ms`);
    }
  }, [visibleFeatures, features.length, getElevation]);

  // Don't render if no features
  if (!features.length) return null;

  return (
    <instancedMesh
      ref={meshRef}
      // Allocate for max possible instances, but mesh.count controls actual rendering
      args={[geometry, material, features.length]}
      castShadow={castShadow}
      receiveShadow={receiveShadow}
      // Enable frustum culling - GPU will further cull off-screen instances
      frustumCulled={true}
    />
  );
}

export default Trees;
