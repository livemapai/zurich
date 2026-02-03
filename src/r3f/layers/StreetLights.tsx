/**
 * StreetLights - Instanced Street Light Rendering with Distance Filtering
 *
 * Renders street lights efficiently using Three.js InstancedMesh with distance-based culling.
 *
 * PERFORMANCE OPTIMIZATIONS:
 * - InstancedMesh renders visible lights in a single draw call
 * - Distance filtering: Only lights within render distance are processed
 * - Dynamic instance count: mesh.count is set to visible count only
 * - frustumCulled enabled: GPU further culls off-screen instances
 * - Position snapping: Prevents recalculation on minor player movements
 *
 * VISUAL STYLE:
 * - Simple cylinder pole geometry
 * - Dark gray metallic color
 * - Emissive lamp fixture (for glow effects)
 */

import { useRef, useEffect, useMemo } from 'react';
import * as THREE from 'three';
import type { LightFeature, LngLat } from '@/types';
import { geoToScene } from '@/lib/coordinateSystem';
import { CONFIG } from '@/lib/config';
import { createLampGeometry } from '../geometry/convertMesh';
import { useDistanceFilter } from '../hooks/useDistanceFilter';

/** Type for elevation callback function */
type ElevationCallback = (lng: number, lat: number) => number;

interface StreetLightsProps {
  /** Array of light features from GeoJSON */
  features: LightFeature[];
  /** Player position [lng, lat] for distance filtering */
  playerPosition?: [number, number];
  /** Pole color (default: dark gray) */
  poleColor?: string;
  /** Whether lights cast shadows (default: false - poles are thin) */
  castShadow?: boolean;
  /** Whether lights receive shadows (default: true) */
  receiveShadow?: boolean;
  /** Maximum render distance in meters (default: from config) */
  renderDistance?: number;
  /** Callback to get terrain elevation at [lng, lat] */
  getElevation?: ElevationCallback;
}

/** Extract coordinates from a light feature */
const getLightCoords = (light: LightFeature): LngLat => light.geometry.coordinates;

/**
 * StreetLights component using InstancedMesh with distance-based filtering.
 *
 * KEY OPTIMIZATIONS:
 * 1. Only visible lights (within renderDistance) are set up in instance matrix
 * 2. mesh.count is dynamically set to visible count
 * 3. frustumCulled is enabled for GPU-side culling
 * 4. Instance matrices are only updated when visible set changes
 */
export function StreetLights({
  features,
  playerPosition,
  poleColor = '#4a4a4a', // Dark gray
  castShadow = false,
  receiveShadow = true,
  renderDistance = CONFIG.performance.lightRenderDistance,
  getElevation,
}: StreetLightsProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const prevVisibleCountRef = useRef<number>(0);

  // Default player position if not provided (Zurich center)
  const effectivePlayerPos = playerPosition ?? [8.5437, 47.3739] as [number, number];

  // Filter features by distance from player
  const visibleFeatures = useDistanceFilter(
    features,
    effectivePlayerPos,
    renderDistance,
    getLightCoords
  );

  // Create shared geometry (unit lamp that gets scaled per instance)
  const geometry = useMemo(() => createLampGeometry(), []);

  // Create shared material
  const material = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: poleColor,
        metalness: 0.6,
        roughness: 0.4,
      }),
    [poleColor]
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
      console.log(`StreetLights: Updating ${visibleCount} visible instances (of ${features.length} total)`);
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

      // No rotation needed for vertical poles
      quaternion.identity();

      // Scale based on light height property
      const height = props.height || 6;
      const scaleY = height;
      const scaleXZ = 1; // Consistent pole width
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
      console.log(`StreetLights: Updated ${visibleCount} instances in ${elapsed.toFixed(1)}ms`);
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

export default StreetLights;
