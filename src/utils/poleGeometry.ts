/**
 * Procedural Overhead Pole Mesh Generation
 *
 * Generates 3D geometry for tram/trolleybus overhead line support poles.
 * Creates a simple cylinder representing the metal pole.
 *
 * Creates a unit pole (1m tall) that gets scaled per instance using
 * the actual pole height from VBZ data (hoehemastok - hoehemastuk).
 */

/** Attribute with value and size for deck.gl/luma.gl compatibility */
interface MeshAttribute {
  value: Float32Array;
  size: number;
}

/** Index buffer for deck.gl/luma.gl compatibility */
interface MeshIndices {
  value: Uint16Array | Uint32Array;
}

/** Generated pole mesh compatible with deck.gl SimpleMeshLayer */
export interface PoleMesh {
  attributes: {
    POSITION: MeshAttribute;
    NORMAL: MeshAttribute;
  };
  indices: MeshIndices;
}

/**
 * Generate a unit overhead pole mesh (1m tall, scalable per instance)
 *
 * The pole is built along the Z axis:
 * - Z=0: Base of pole (ground level / hoehemastuk)
 * - Z=1: Top of pole (hoehemastok)
 *
 * Typical overhead poles are 8-12m tall with ~0.15m radius.
 * The mesh is a simple cylinder with flat caps.
 *
 * @param segments - Number of segments for the cylinder (default: 8)
 * @param radius - Pole radius in meters (default: 0.15)
 * @returns PoleMesh with positions, normals, and indices
 */
export function generatePoleMesh(segments = 8, radius = 0.15): PoleMesh {
  const positions: number[] = [];
  const normals: number[] = [];
  const indices: number[] = [];

  // --- BOTTOM CAP ---
  // Center vertex at bottom
  const bottomCenterIdx = 0;
  positions.push(0, 0, 0);
  normals.push(0, 0, -1);

  // Bottom ring vertices
  for (let i = 0; i < segments; i++) {
    const angle = (i / segments) * Math.PI * 2;
    positions.push(Math.cos(angle) * radius, Math.sin(angle) * radius, 0);
    normals.push(0, 0, -1); // All bottom cap normals point down
  }

  // Bottom cap faces (triangle fan)
  for (let i = 0; i < segments; i++) {
    indices.push(
      bottomCenterIdx,
      1 + ((i + 1) % segments),
      1 + i
    );
  }

  // --- SIDE CYLINDER ---
  const sideBottomStart = positions.length / 3;

  // Bottom ring (with outward normals for sides)
  for (let i = 0; i < segments; i++) {
    const angle = (i / segments) * Math.PI * 2;
    const nx = Math.cos(angle);
    const ny = Math.sin(angle);
    positions.push(nx * radius, ny * radius, 0);
    normals.push(nx, ny, 0);
  }

  // Top ring (with outward normals for sides)
  const sideTopStart = positions.length / 3;
  for (let i = 0; i < segments; i++) {
    const angle = (i / segments) * Math.PI * 2;
    const nx = Math.cos(angle);
    const ny = Math.sin(angle);
    positions.push(nx * radius, ny * radius, 1);
    normals.push(nx, ny, 0);
  }

  // Side faces (quads as two triangles each)
  for (let i = 0; i < segments; i++) {
    const b1 = sideBottomStart + i;
    const b2 = sideBottomStart + ((i + 1) % segments);
    const t1 = sideTopStart + i;
    const t2 = sideTopStart + ((i + 1) % segments);
    // Two triangles per quad
    indices.push(b1, b2, t1);
    indices.push(b2, t2, t1);
  }

  // --- TOP CAP ---
  const topCenterIdx = positions.length / 3;
  positions.push(0, 0, 1);
  normals.push(0, 0, 1);

  // Top ring vertices for cap
  const topCapStart = positions.length / 3;
  for (let i = 0; i < segments; i++) {
    const angle = (i / segments) * Math.PI * 2;
    positions.push(Math.cos(angle) * radius, Math.sin(angle) * radius, 1);
    normals.push(0, 0, 1); // All top cap normals point up
  }

  // Top cap faces (triangle fan)
  for (let i = 0; i < segments; i++) {
    indices.push(
      topCenterIdx,
      topCapStart + i,
      topCapStart + ((i + 1) % segments)
    );
  }

  return {
    attributes: {
      POSITION: { value: new Float32Array(positions), size: 3 },
      NORMAL: { value: new Float32Array(normals), size: 3 },
    },
    indices: { value: new Uint16Array(indices) },
  };
}
