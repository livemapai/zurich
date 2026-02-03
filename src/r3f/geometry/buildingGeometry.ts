/**
 * Building Geometry Utilities
 *
 * Converts GeoJSON building polygons to Three.js geometry for rendering
 * and physics collisions.
 *
 * GEOMETRY CONVERSION:
 * 1. GeoJSON Polygon → Three.js Shape (2D outline)
 * 2. Shape → ExtrudeGeometry (3D building with height)
 * 3. Optional: Merge multiple geometries for draw call optimization
 *
 * COORDINATE HANDLING:
 * - GeoJSON uses [lng, lat] order
 * - We convert to scene coordinates [x, z] using geoToScene
 * - Three.js Shape uses [x, y] for 2D, then extrudes along Z
 * - We rotate the final geometry so extrusion goes UP (Y axis)
 */

import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import type { BuildingFeature, PolygonRing } from '@/types';
import { geoToScene } from '@/lib/coordinateSystem';

/** Options for building geometry generation */
export interface BuildingGeometryOptions {
  /** Bevel settings for the extrusion (default: no bevel) */
  bevel?: boolean;
  /** Number of segments for beveled edges */
  bevelSegments?: number;
  /** Size of bevel */
  bevelSize?: number;
}

/** Type for elevation callback function */
export type ElevationCallback = (lng: number, lat: number) => number;

/**
 * Calculate the centroid of a building polygon.
 * Uses the first polygon's outer ring for MultiPolygon types.
 *
 * @param feature - Building feature
 * @returns [lng, lat] centroid coordinates
 */
export function getBuildingCentroid(feature: BuildingFeature): [number, number] {
  const { geometry } = feature;

  // Get the first polygon's outer ring
  const outerRing =
    geometry.type === 'MultiPolygon'
      ? geometry.coordinates[0]?.[0]
      : geometry.coordinates[0];

  if (!outerRing || outerRing.length === 0) {
    // Fallback to a default if no coordinates
    return [0, 0];
  }

  // Calculate centroid as average of all vertices
  let sumLng = 0;
  let sumLat = 0;
  let count = 0;

  for (const coord of outerRing) {
    const lng = coord[0];
    const lat = coord[1];
    if (lng !== undefined && lat !== undefined) {
      sumLng += lng;
      sumLat += lat;
      count++;
    }
  }

  if (count === 0) {
    return [0, 0];
  }

  return [sumLng / count, sumLat / count];
}

/**
 * Convert a GeoJSON polygon ring to a Three.js Shape.
 *
 * @param ring - Array of [lng, lat] coordinates
 * @returns Three.js Shape
 */
export function polygonRingToShape(ring: PolygonRing): THREE.Shape {
  const shape = new THREE.Shape();

  ring.forEach((coord, i) => {
    // Convert WGS84 to scene coordinates
    const [x, , z] = geoToScene(coord[0], coord[1], 0);

    // THREE.Shape uses X/Y, but we need X/Z for horizontal plane
    // We'll use X/-Z so that the shape extrudes correctly
    if (i === 0) {
      shape.moveTo(x, -z);
    } else {
      shape.lineTo(x, -z);
    }
  });

  // Close the shape
  shape.closePath();

  return shape;
}

/**
 * Convert a GeoJSON polygon ring to a Three.js Path (for holes).
 *
 * @param ring - Array of [lng, lat] coordinates
 * @returns Three.js Path
 */
export function polygonRingToPath(ring: PolygonRing): THREE.Path {
  const path = new THREE.Path();

  ring.forEach((coord, i) => {
    const [x, , z] = geoToScene(coord[0], coord[1], 0);

    if (i === 0) {
      path.moveTo(x, -z);
    } else {
      path.lineTo(x, -z);
    }
  });

  path.closePath();

  return path;
}

/**
 * Create extruded geometry for a single building.
 *
 * @param feature - GeoJSON building feature
 * @param options - Geometry generation options
 * @param getElevation - Optional callback to get terrain elevation at [lng, lat]
 * @returns THREE.ExtrudeGeometry or null if invalid
 */
export function createBuildingGeometry(
  feature: BuildingFeature,
  options: BuildingGeometryOptions = {},
  getElevation?: ElevationCallback
): THREE.ExtrudeGeometry | null {
  const { geometry, properties } = feature;
  const height = properties.height || 10; // Default 10m height

  // Handle both Polygon and MultiPolygon
  const polygons =
    geometry.type === 'MultiPolygon'
      ? geometry.coordinates
      : [geometry.coordinates];

  const shapes: THREE.Shape[] = [];

  for (const polygon of polygons) {
    const outerRing = polygon[0];
    if (!polygon.length || !outerRing || outerRing.length === 0) continue;

    // First ring is the outer boundary
    const shape = polygonRingToShape(outerRing);

    // Additional rings are holes
    for (let i = 1; i < polygon.length; i++) {
      const holeRing = polygon[i];
      if (holeRing && holeRing.length >= 3) {
        const hole = polygonRingToPath(holeRing);
        shape.holes.push(hole);
      }
    }

    shapes.push(shape);
  }

  if (shapes.length === 0) return null;

  // Extrusion settings
  const extrudeSettings: THREE.ExtrudeGeometryOptions = {
    depth: height,
    bevelEnabled: options.bevel ?? false,
    bevelSegments: options.bevelSegments ?? 1,
    bevelSize: options.bevelSize ?? 0.1,
    bevelThickness: options.bevelSize ?? 0.1,
  };

  // Create extruded geometry
  const extrudeGeom = new THREE.ExtrudeGeometry(shapes, extrudeSettings);

  // Rotate to make extrusion go UP (Y axis) instead of OUT (Z axis)
  // ExtrudeGeometry extrudes along +Z, we need +Y
  extrudeGeom.rotateX(-Math.PI / 2);

  // Apply terrain elevation offset if callback provided
  if (getElevation) {
    const [centroidLng, centroidLat] = getBuildingCentroid(feature);
    const elevation = getElevation(centroidLng, centroidLat);
    if (elevation !== 0) {
      extrudeGeom.translate(0, elevation, 0);
    }
  }

  return extrudeGeom;
}

/**
 * Create merged geometry for multiple buildings.
 * This significantly reduces draw calls for rendering performance.
 *
 * @param features - Array of building features
 * @param options - Geometry generation options
 * @param maxVertices - Maximum vertices per merged geometry (default: 65535 for Uint16 indices)
 * @param getElevation - Optional callback to get terrain elevation at [lng, lat]
 * @returns Array of merged BufferGeometry objects
 */
export function createMergedBuildingGeometry(
  features: BuildingFeature[],
  options: BuildingGeometryOptions = {},
  maxVertices = 65000,
  getElevation?: ElevationCallback
): THREE.BufferGeometry[] {
  const geometries: THREE.BufferGeometry[] = [];
  let currentBatch: THREE.BufferGeometry[] = [];
  let currentVertexCount = 0;

  for (const feature of features) {
    const geom = createBuildingGeometry(feature, options, getElevation);
    if (!geom) continue;

    const vertexCount = geom.getAttribute('position').count;

    // If adding this geometry would exceed the limit, merge current batch
    if (currentVertexCount + vertexCount > maxVertices && currentBatch.length > 0) {
      const merged = mergeGeometries(currentBatch, false);
      if (merged) {
        geometries.push(merged);
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
      geometries.push(merged);
    }
  }

  return geometries;
}

/**
 * Create a simple box collider geometry for a building.
 * Used for physics simulation when detailed geometry is too expensive.
 *
 * @param feature - Building feature
 * @param getElevation - Optional callback to get terrain elevation at [lng, lat]
 * @returns Box dimensions [width, height, depth] and center position
 */
export function createBuildingBounds(
  feature: BuildingFeature,
  getElevation?: ElevationCallback
): {
  dimensions: [number, number, number];
  center: [number, number, number];
} | null {
  const { geometry, properties } = feature;
  const height = properties.height || 10;

  // Get all coordinates
  const allCoords: number[][] = [];
  const polygons =
    geometry.type === 'MultiPolygon'
      ? geometry.coordinates
      : [geometry.coordinates];

  for (const polygon of polygons) {
    for (const ring of polygon) {
      allCoords.push(...ring);
    }
  }

  if (allCoords.length === 0) return null;

  // Find bounding box in scene coordinates
  let minX = Infinity,
    maxX = -Infinity;
  let minZ = Infinity,
    maxZ = -Infinity;

  for (const coord of allCoords) {
    const lng = coord[0];
    const lat = coord[1];
    if (lng === undefined || lat === undefined) continue;
    const [x, , z] = geoToScene(lng, lat, 0);
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minZ = Math.min(minZ, z);
    maxZ = Math.max(maxZ, z);
  }

  const width = maxX - minX;
  const depth = maxZ - minZ;

  // Calculate terrain elevation at centroid
  let baseElevation = 0;
  if (getElevation) {
    const [centroidLng, centroidLat] = getBuildingCentroid(feature);
    baseElevation = getElevation(centroidLng, centroidLat);
  }

  return {
    dimensions: [width, height, depth],
    center: [(minX + maxX) / 2, baseElevation + height / 2, (minZ + maxZ) / 2],
  };
}

/**
 * Extract vertices from a building feature for trimesh collider.
 *
 * @param feature - Building feature
 * @returns Float32Array of vertices [x1,y1,z1, x2,y2,z2, ...] or null
 */
export function extractBuildingVertices(feature: BuildingFeature): Float32Array | null {
  const { geometry, properties } = feature;
  const height = properties.height || 10;

  // Get all coordinates from the outer ring(s)
  const outerCoords: number[][] = [];
  const polygons =
    geometry.type === 'MultiPolygon'
      ? geometry.coordinates
      : [geometry.coordinates];

  for (const polygon of polygons) {
    if (polygon[0]) {
      outerCoords.push(...polygon[0]);
    }
  }

  if (outerCoords.length < 3) return null;

  // Create vertices for bottom and top faces
  const vertices: number[] = [];

  for (const coord of outerCoords) {
    const lng = coord[0];
    const lat = coord[1];
    if (lng === undefined || lat === undefined) continue;
    const [x, , z] = geoToScene(lng, lat, 0);
    // Bottom vertex
    vertices.push(x, 0, z);
    // Top vertex
    vertices.push(x, height, z);
  }

  return new Float32Array(vertices);
}
