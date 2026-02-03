/**
 * LODInstancedMesh - Multi-Level-of-Detail Instanced Rendering
 *
 * Manages multiple InstancedMesh objects with different geometry detail levels.
 * Distributes instances across LOD levels based on distance from camera.
 *
 * ARCHITECTURE:
 * - Three InstancedMesh objects (high, medium, low detail)
 * - Each frame, instances are sorted into buckets by distance
 * - Instance matrices are updated per LOD mesh
 * - mesh.count is set dynamically for each LOD
 *
 * PERFORMANCE:
 * - Significantly reduces GPU vertex processing
 * - High detail only for nearby objects (< 100m)
 * - Medium detail for mid-range (100-300m)
 * - Low detail for distant objects (> 300m)
 */

import { useRef, useEffect, useMemo } from 'react';
import * as THREE from 'three';
import type { LngLat } from '@/types';
import { METERS_PER_DEGREE } from '@/types';
import { geoToScene } from '@/lib/coordinateSystem';
import { CONFIG } from '@/lib/config';
import { LOD_DISTANCES, type LODGeometries } from '../geometry/convertMesh';

/** Feature with position and scale properties */
export interface LODFeature {
  /** Geographic coordinates [lng, lat] */
  coordinates: LngLat;
  /** Scale factors [x, y, z] */
  scale: [number, number, number];
}

interface LODInstancedMeshProps {
  /** LOD geometries (high, medium, low) */
  geometries: LODGeometries;
  /** Material to use for all LOD levels */
  material: THREE.Material;
  /** Features to render with their positions and scales */
  features: LODFeature[];
  /** Player position [lng, lat] for distance calculation */
  playerPosition: [number, number];
  /** Maximum render distance in meters */
  maxDistance: number;
  /** Whether to cast shadows */
  castShadow?: boolean;
  /** Whether to receive shadows */
  receiveShadow?: boolean;
}

/** Calculate distance between two points in meters */
function distanceMeters(lng1: number, lat1: number, lng2: number, lat2: number): number {
  const dLng = (lng2 - lng1) * METERS_PER_DEGREE.lng;
  const dLat = (lat2 - lat1) * METERS_PER_DEGREE.lat;
  return Math.sqrt(dLng * dLng + dLat * dLat);
}

/** Structure for tracking instances per LOD level */
interface LODInstances {
  high: { feature: LODFeature; distance: number }[];
  medium: { feature: LODFeature; distance: number }[];
  low: { feature: LODFeature; distance: number }[];
}

/**
 * LODInstancedMesh - Renders features with level-of-detail based on distance.
 *
 * This component maintains three InstancedMesh objects and dynamically
 * distributes instances across them based on player distance.
 */
export function LODInstancedMesh({
  geometries,
  material,
  features,
  playerPosition,
  maxDistance,
  castShadow = false,
  receiveShadow = false,
}: LODInstancedMeshProps) {
  // Refs for the three LOD meshes
  const highMeshRef = useRef<THREE.InstancedMesh>(null);
  const mediumMeshRef = useRef<THREE.InstancedMesh>(null);
  const lowMeshRef = useRef<THREE.InstancedMesh>(null);

  // Track previous counts to avoid unnecessary updates
  const prevCountsRef = useRef({ high: 0, medium: 0, low: 0 });

  // Reusable matrices and vectors
  const matrix = useMemo(() => new THREE.Matrix4(), []);
  const position = useMemo(() => new THREE.Vector3(), []);
  const quaternion = useMemo(() => new THREE.Quaternion(), []);
  const scale = useMemo(() => new THREE.Vector3(), []);

  // Sort features into LOD buckets and update instance matrices
  useEffect(() => {
    const highMesh = highMeshRef.current;
    const mediumMesh = mediumMeshRef.current;
    const lowMesh = lowMeshRef.current;

    if (!highMesh || !mediumMesh || !lowMesh) return;

    const [playerLng, playerLat] = playerPosition;

    // Sort features into LOD buckets
    const instances: LODInstances = {
      high: [],
      medium: [],
      low: [],
    };

    for (const feature of features) {
      const dist = distanceMeters(
        playerLng,
        playerLat,
        feature.coordinates[0],
        feature.coordinates[1]
      );

      // Skip if beyond max render distance
      if (dist > maxDistance) continue;

      // Assign to appropriate LOD bucket
      if (dist < LOD_DISTANCES.high) {
        instances.high.push({ feature, distance: dist });
      } else if (dist < LOD_DISTANCES.medium) {
        instances.medium.push({ feature, distance: dist });
      } else {
        instances.low.push({ feature, distance: dist });
      }
    }

    const counts = {
      high: instances.high.length,
      medium: instances.medium.length,
      low: instances.low.length,
    };

    // Skip if counts haven't changed significantly
    const prevCounts = prevCountsRef.current;
    const totalChanged = Math.abs(
      counts.high + counts.medium + counts.low -
      prevCounts.high - prevCounts.medium - prevCounts.low
    );
    if (totalChanged < 10 && counts.high > 0) {
      // Minor change, skip update for performance
      return;
    }

    prevCountsRef.current = counts;

    if (CONFIG.debug.logPerformance) {
      console.log(`LODInstancedMesh: high=${counts.high}, medium=${counts.medium}, low=${counts.low}`);
    }

    // Helper to update a mesh with its instances
    const updateMesh = (
      mesh: THREE.InstancedMesh,
      instanceList: { feature: LODFeature; distance: number }[]
    ) => {
      instanceList.forEach(({ feature }, i) => {
        const [x, , z] = geoToScene(
          feature.coordinates[0],
          feature.coordinates[1],
          0
        );
        position.set(x, 0, z);
        quaternion.identity();
        scale.set(...feature.scale);
        matrix.compose(position, quaternion, scale);
        mesh.setMatrixAt(i, matrix);
      });
      mesh.count = instanceList.length;
      mesh.instanceMatrix.needsUpdate = true;
    };

    // Update all three LOD meshes
    updateMesh(highMesh, instances.high);
    updateMesh(mediumMesh, instances.medium);
    updateMesh(lowMesh, instances.low);
  }, [features, playerPosition, maxDistance, matrix, position, quaternion, scale]);

  // Calculate max instance count (allocate for all features)
  const maxInstances = features.length;

  if (maxInstances === 0) return null;

  return (
    <group name="lod-instanced-mesh">
      {/* High detail mesh */}
      <instancedMesh
        ref={highMeshRef}
        args={[geometries.high, material, maxInstances]}
        castShadow={castShadow}
        receiveShadow={receiveShadow}
        frustumCulled={true}
      />

      {/* Medium detail mesh */}
      <instancedMesh
        ref={mediumMeshRef}
        args={[geometries.medium, material, maxInstances]}
        castShadow={castShadow}
        receiveShadow={receiveShadow}
        frustumCulled={true}
      />

      {/* Low detail mesh */}
      <instancedMesh
        ref={lowMeshRef}
        args={[geometries.low, material, maxInstances]}
        castShadow={false} // Low detail doesn't need shadows
        receiveShadow={receiveShadow}
        frustumCulled={true}
      />
    </group>
  );
}

export default LODInstancedMesh;
