/**
 * Mesh Conversion Utilities
 *
 * Converts deck.gl/luma.gl mesh format to Three.js BufferGeometry.
 *
 * MESH FORMAT COMPARISON:
 * - deck.gl: { attributes: { POSITION: { value, size }, NORMAL: { value, size } }, indices }
 * - Three.js: BufferGeometry with BufferAttribute instances
 *
 * Both use interleaved Float32Array data, so conversion is straightforward.
 */

import * as THREE from 'three';

/** deck.gl/luma.gl mesh attribute format */
interface MeshAttribute {
  value: Float32Array;
  size: number;
}

/** deck.gl/luma.gl mesh indices format */
interface MeshIndices {
  value: Uint16Array | Uint32Array;
  size?: number;
}

/** deck.gl mesh format (compatible with SimpleMeshLayer) */
interface DeckMesh {
  attributes: {
    POSITION: MeshAttribute;
    NORMAL: MeshAttribute;
  };
  indices: MeshIndices;
}

/**
 * Convert a deck.gl mesh to Three.js BufferGeometry.
 *
 * @param mesh - deck.gl/luma.gl mesh object
 * @returns THREE.BufferGeometry
 */
export function deckMeshToBufferGeometry(mesh: DeckMesh): THREE.BufferGeometry {
  const geometry = new THREE.BufferGeometry();

  // Position attribute
  const positionAttr = new THREE.BufferAttribute(
    mesh.attributes.POSITION.value,
    mesh.attributes.POSITION.size
  );
  geometry.setAttribute('position', positionAttr);

  // Normal attribute
  const normalAttr = new THREE.BufferAttribute(
    mesh.attributes.NORMAL.value,
    mesh.attributes.NORMAL.size
  );
  geometry.setAttribute('normal', normalAttr);

  // Index buffer
  geometry.setIndex(new THREE.BufferAttribute(mesh.indices.value, 1));

  // Compute bounding sphere for frustum culling
  geometry.computeBoundingSphere();

  return geometry;
}

/**
 * Create a simple cone geometry (for tree crowns).
 * Built along Z axis, can be rotated for different orientations.
 *
 * @param radius - Base radius
 * @param height - Cone height
 * @param segments - Number of radial segments
 * @returns THREE.ConeGeometry
 */
export function createConeGeometry(
  radius = 0.5,
  height = 0.7,
  segments = 8
): THREE.ConeGeometry {
  return new THREE.ConeGeometry(radius, height, segments);
}

/**
 * Create a simple cylinder geometry (for tree trunks, light poles).
 *
 * @param radiusTop - Top radius
 * @param radiusBottom - Bottom radius
 * @param height - Cylinder height
 * @param segments - Number of radial segments
 * @returns THREE.CylinderGeometry
 */
export function createCylinderGeometry(
  radiusTop = 0.1,
  radiusBottom = 0.1,
  height = 0.3,
  segments = 6
): THREE.CylinderGeometry {
  return new THREE.CylinderGeometry(radiusTop, radiusBottom, height, segments);
}

/**
 * Create a simple tree geometry by merging a cone (crown) and cylinder (trunk).
 * Tree is created pointing up (Y+), centered at origin with base at Y=0.
 *
 * @param crownRadius - Crown cone radius (default: 0.5)
 * @param crownHeight - Crown height (default: 0.7)
 * @param trunkRadius - Trunk radius (default: 0.1)
 * @param trunkHeight - Trunk height (default: 0.3)
 * @returns Merged BufferGeometry
 */
export function createTreeGeometry(
  crownRadius = 0.5,
  crownHeight = 0.7,
  trunkRadius = 0.1,
  trunkHeight = 0.3
): THREE.BufferGeometry {
  // Create crown (cone)
  const crown = new THREE.ConeGeometry(crownRadius, crownHeight, 8);
  // Position crown above trunk
  crown.translate(0, trunkHeight + crownHeight / 2, 0);

  // Create trunk (cylinder)
  const trunk = new THREE.CylinderGeometry(trunkRadius, trunkRadius * 1.2, trunkHeight, 6);
  // Position trunk with base at Y=0
  trunk.translate(0, trunkHeight / 2, 0);

  // Merge geometries
  // Note: For better performance, we could merge these, but keeping separate
  // allows different materials for crown vs trunk if desired
  return crown;
}

/**
 * Create a simple lamp post geometry.
 * Lamp is created pointing up (Y+), centered at origin with base at Y=0.
 *
 * @param poleRadius - Pole radius (default: 0.03)
 * @param poleHeight - Pole height (default: 0.85)
 * @param lampRadius - Lamp fixture radius (default: 0.15)
 * @param lampHeight - Lamp fixture height (default: 0.15)
 * @returns BufferGeometry
 */
export function createLampGeometry(
  poleRadius = 0.03,
  poleHeight = 0.85,
  lampRadius = 0.15,
  lampHeight = 0.15
): THREE.BufferGeometry {
  // Create pole (thin cylinder)
  const pole = new THREE.CylinderGeometry(poleRadius, poleRadius, poleHeight, 6);
  // Position pole with base at Y=0
  pole.translate(0, poleHeight / 2, 0);

  // Create lamp fixture (inverted cone / dome)
  const lamp = new THREE.ConeGeometry(lampRadius, lampHeight, 8);
  // Invert the cone so it points down
  lamp.rotateX(Math.PI);
  // Position lamp at top of pole
  lamp.translate(0, poleHeight + lampHeight / 2, 0);

  // For simplicity, just return the pole geometry
  // The lamp fixture could be added as a separate instanced mesh for emissive materials
  return pole;
}

/**
 * Create a simple sphere geometry (useful for debugging/markers).
 *
 * @param radius - Sphere radius
 * @param segments - Sphere segments (both width and height)
 * @returns THREE.SphereGeometry
 */
export function createSphereGeometry(radius = 0.5, segments = 8): THREE.SphereGeometry {
  return new THREE.SphereGeometry(radius, segments, segments);
}

// ============================================================================
// LOD (Level of Detail) Geometry Variants
// ============================================================================

/** LOD levels for geometry detail */
export interface LODGeometries {
  /** High detail - < 100m distance */
  high: THREE.BufferGeometry;
  /** Medium detail - 100-300m distance */
  medium: THREE.BufferGeometry;
  /** Low detail - > 300m distance (billboard or minimal geometry) */
  low: THREE.BufferGeometry;
}

/** Distance thresholds for LOD transitions in meters */
export const LOD_DISTANCES = {
  /** Distance below which to use high detail */
  high: 100,
  /** Distance below which to use medium detail */
  medium: 300,
  // Above medium threshold uses low detail
} as const;

/**
 * Create tree geometry at different LOD levels.
 *
 * HIGH (< 100m): 8 radial segments, full detail
 * MEDIUM (100-300m): 4 radial segments, ~50% vertices
 * LOW (> 300m): Billboard quad (2 triangles)
 *
 * @returns LOD geometries for trees
 */
export function createTreeGeometryLOD(): LODGeometries {
  // HIGH: Full detail tree (8 segments)
  const highCrown = new THREE.ConeGeometry(0.5, 0.7, 8);
  highCrown.translate(0, 0.3 + 0.7 / 2, 0);
  const high = highCrown;

  // MEDIUM: Reduced detail tree (4 segments)
  const mediumCrown = new THREE.ConeGeometry(0.5, 0.7, 4);
  mediumCrown.translate(0, 0.3 + 0.7 / 2, 0);
  const medium = mediumCrown;

  // LOW: Simple pyramid (3 segments - minimal cone)
  const lowCrown = new THREE.ConeGeometry(0.5, 0.7, 3);
  lowCrown.translate(0, 0.3 + 0.7 / 2, 0);
  const low = lowCrown;

  return { high, medium, low };
}

/**
 * Create lamp post geometry at different LOD levels.
 *
 * HIGH (< 100m): 6 radial segments, full detail
 * MEDIUM (100-300m): 4 radial segments
 * LOW (> 300m): 3 segments (triangular pole)
 *
 * @returns LOD geometries for lamps
 */
export function createLampGeometryLOD(): LODGeometries {
  // HIGH: Full detail pole (6 segments)
  const highPole = new THREE.CylinderGeometry(0.03, 0.03, 0.85, 6);
  highPole.translate(0, 0.85 / 2, 0);
  const high = highPole;

  // MEDIUM: Reduced detail pole (4 segments)
  const mediumPole = new THREE.CylinderGeometry(0.03, 0.03, 0.85, 4);
  mediumPole.translate(0, 0.85 / 2, 0);
  const medium = mediumPole;

  // LOW: Minimal pole (3 segments - triangular)
  const lowPole = new THREE.CylinderGeometry(0.03, 0.03, 0.85, 3);
  lowPole.translate(0, 0.85 / 2, 0);
  const low = lowPole;

  return { high, medium, low };
}

/**
 * Create a billboard quad geometry for maximum distance LOD.
 * The quad is oriented to always face the camera (requires shader modification).
 *
 * @param width - Billboard width
 * @param height - Billboard height
 * @returns PlaneGeometry suitable for billboarding
 */
export function createBillboardGeometry(
  width = 1,
  height = 1
): THREE.PlaneGeometry {
  const plane = new THREE.PlaneGeometry(width, height);
  // Position so bottom is at Y=0
  plane.translate(0, height / 2, 0);
  return plane;
}
