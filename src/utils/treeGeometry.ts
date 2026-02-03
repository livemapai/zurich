/**
 * Procedural Tree Mesh Generation
 *
 * Generates 3D tree geometry with:
 * - Cone crown (top portion)
 * - Cylinder trunk (bottom portion)
 *
 * Creates a unit tree (1m tall) that can be scaled per instance.
 */

/** Attribute with value and size for deck.gl/luma.gl compatibility */
interface MeshAttribute {
  value: Float32Array;
  size: number;
}

/** Index buffer for deck.gl/luma.gl compatibility */
interface MeshIndices {
  value: Uint16Array | Uint32Array;
  size?: number;
}

/** Generated tree mesh compatible with deck.gl SimpleMeshLayer */
export interface TreeMesh {
  attributes: {
    POSITION: MeshAttribute;
    NORMAL: MeshAttribute;
  };
  indices: MeshIndices;
}

/**
 * Generate a unit tree mesh (1m tall, scalable per instance)
 *
 * The tree is built along the Z axis:
 * - Z=0: Base of trunk
 * - Z=trunkHeight: Top of trunk / base of crown
 * - Z=1: Tip of crown
 *
 * @param crownSegments - Number of segments for the crown cone (default: 12)
 * @param trunkSegments - Number of segments for the trunk cylinder (default: 8)
 * @param crownRatio - Proportion of total height that is crown (default: 0.7)
 * @returns TreeMesh with positions, normals, and indices
 */
export function generateTreeMesh(
  crownSegments = 12,
  trunkSegments = 8,
  crownRatio = 0.7
): TreeMesh {
  const positions: number[] = [];
  const normals: number[] = [];
  const indices: number[] = [];

  const trunkHeight = 1 - crownRatio;
  const trunkRadius = 0.1;
  const crownRadius = 0.5;

  // --- TRUNK (cylinder) ---

  // Bottom center vertex
  const trunkBaseIdx = positions.length / 3;
  positions.push(0, 0, 0);
  normals.push(0, 0, -1);

  // Bottom ring vertices
  for (let i = 0; i < trunkSegments; i++) {
    const angle = (i / trunkSegments) * Math.PI * 2;
    const x = Math.cos(angle) * trunkRadius;
    const y = Math.sin(angle) * trunkRadius;
    positions.push(x, y, 0);
    // Outward-facing normals for cylinder sides
    normals.push(Math.cos(angle), Math.sin(angle), 0);
  }

  // Top ring vertices
  for (let i = 0; i < trunkSegments; i++) {
    const angle = (i / trunkSegments) * Math.PI * 2;
    const x = Math.cos(angle) * trunkRadius;
    const y = Math.sin(angle) * trunkRadius;
    positions.push(x, y, trunkHeight);
    normals.push(Math.cos(angle), Math.sin(angle), 0);
  }

  // Trunk bottom cap (fan from center)
  for (let i = 0; i < trunkSegments; i++) {
    const i0 = trunkBaseIdx; // center
    const i1 = trunkBaseIdx + 1 + ((i + 1) % trunkSegments);
    const i2 = trunkBaseIdx + 1 + i;
    indices.push(i0, i1, i2);
  }

  // Trunk side faces (quads as two triangles)
  for (let i = 0; i < trunkSegments; i++) {
    const i0 = trunkBaseIdx + 1 + i;
    const i1 = trunkBaseIdx + 1 + ((i + 1) % trunkSegments);
    const i2 = trunkBaseIdx + 1 + trunkSegments + i;
    const i3 = trunkBaseIdx + 1 + trunkSegments + ((i + 1) % trunkSegments);
    indices.push(i0, i1, i2);
    indices.push(i1, i3, i2);
  }

  // --- CROWN (cone) ---

  // Crown base ring vertices
  const crownBaseIdx = positions.length / 3;
  for (let i = 0; i < crownSegments; i++) {
    const angle = (i / crownSegments) * Math.PI * 2;
    const x = Math.cos(angle) * crownRadius;
    const y = Math.sin(angle) * crownRadius;
    positions.push(x, y, trunkHeight);
    // Cone normals point outward and slightly up
    // For a cone, the normal makes an angle with the axis
    const coneAngle = Math.atan2(crownRadius, crownRatio);
    const nz = Math.sin(coneAngle);
    const nxy = Math.cos(coneAngle);
    normals.push(Math.cos(angle) * nxy, Math.sin(angle) * nxy, nz);
  }

  // Crown tip vertex
  const tipIdx = positions.length / 3;
  positions.push(0, 0, 1);
  normals.push(0, 0, 1);

  // Crown cone faces (triangles from base to tip)
  for (let i = 0; i < crownSegments; i++) {
    const i0 = crownBaseIdx + i;
    const i1 = crownBaseIdx + ((i + 1) % crownSegments);
    indices.push(i0, i1, tipIdx);
  }

  // Crown bottom cap (optional, fills the base)
  const crownCapCenterIdx = positions.length / 3;
  positions.push(0, 0, trunkHeight);
  normals.push(0, 0, -1);

  for (let i = 0; i < crownSegments; i++) {
    const i0 = crownCapCenterIdx;
    const i1 = crownBaseIdx + ((i + 1) % crownSegments);
    const i2 = crownBaseIdx + i;
    indices.push(i0, i1, i2);
  }

  // Return in deck.gl/luma.gl compatible format
  return {
    attributes: {
      POSITION: { value: new Float32Array(positions), size: 3 },
      NORMAL: { value: new Float32Array(normals), size: 3 },
    },
    indices: { value: new Uint16Array(indices) },
  };
}
