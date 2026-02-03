/**
 * Procedural Light Pole Mesh Generation
 *
 * Generates 3D lamp post geometry with:
 * - Thin cylinder pole (main structure)
 * - Small cone lamp fixture at top (pointing down)
 *
 * Creates a unit lamp (1m tall) that can be scaled per instance.
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

/** Generated light mesh compatible with deck.gl SimpleMeshLayer */
export interface LightMesh {
  attributes: {
    POSITION: MeshAttribute;
    NORMAL: MeshAttribute;
  };
  indices: MeshIndices;
}

/**
 * Generate a unit light pole mesh (1m tall, scalable per instance)
 *
 * The lamp is built along the Z axis:
 * - Z=0: Base of pole
 * - Z=(1-lampRatio): Top of pole / bottom of lamp fixture
 * - Z=1: Top of lamp fixture
 *
 * @param poleSegments - Number of segments for the pole cylinder (default: 8)
 * @param lampSegments - Number of segments for the lamp cone (default: 8)
 * @param lampRatio - Proportion of total height that is lamp (default: 0.15)
 * @returns LightMesh with positions, normals, and indices
 */
export function generateLightMesh(
  poleSegments = 8,
  lampSegments = 8,
  lampRatio = 0.15
): LightMesh {
  const positions: number[] = [];
  const normals: number[] = [];
  const indices: number[] = [];

  const poleHeight = 1 - lampRatio;
  const poleRadius = 0.03; // Thin pole
  const lampRadius = 0.15; // Lamp fixture radius

  // --- POLE (thin cylinder) ---
  const poleBaseIdx = positions.length / 3;

  // Bottom center vertex
  positions.push(0, 0, 0);
  normals.push(0, 0, -1);

  // Bottom ring vertices
  for (let i = 0; i < poleSegments; i++) {
    const angle = (i / poleSegments) * Math.PI * 2;
    const x = Math.cos(angle) * poleRadius;
    const y = Math.sin(angle) * poleRadius;
    positions.push(x, y, 0);
    // Outward-facing normals for cylinder sides
    normals.push(Math.cos(angle), Math.sin(angle), 0);
  }

  // Top ring vertices
  for (let i = 0; i < poleSegments; i++) {
    const angle = (i / poleSegments) * Math.PI * 2;
    const x = Math.cos(angle) * poleRadius;
    const y = Math.sin(angle) * poleRadius;
    positions.push(x, y, poleHeight);
    normals.push(Math.cos(angle), Math.sin(angle), 0);
  }

  // Pole bottom cap (fan from center)
  for (let i = 0; i < poleSegments; i++) {
    const i0 = poleBaseIdx; // center
    const i1 = poleBaseIdx + 1 + ((i + 1) % poleSegments);
    const i2 = poleBaseIdx + 1 + i;
    indices.push(i0, i1, i2);
  }

  // Pole side faces (quads as two triangles)
  for (let i = 0; i < poleSegments; i++) {
    const i0 = poleBaseIdx + 1 + i;
    const i1 = poleBaseIdx + 1 + ((i + 1) % poleSegments);
    const i2 = poleBaseIdx + 1 + poleSegments + i;
    const i3 = poleBaseIdx + 1 + poleSegments + ((i + 1) % poleSegments);
    indices.push(i0, i1, i2);
    indices.push(i1, i3, i2);
  }

  // --- LAMP FIXTURE (inverted cone / dome) ---
  const lampBaseIdx = positions.length / 3;

  // Lamp top ring (wider, at z=1)
  for (let i = 0; i < lampSegments; i++) {
    const angle = (i / lampSegments) * Math.PI * 2;
    const x = Math.cos(angle) * lampRadius;
    const y = Math.sin(angle) * lampRadius;
    positions.push(x, y, 1);
    // Normals point outward and slightly down for the cone shape
    const coneAngle = Math.atan2(lampRadius, lampRatio);
    const nz = -Math.sin(coneAngle);
    const nxy = Math.cos(coneAngle);
    normals.push(Math.cos(angle) * nxy, Math.sin(angle) * nxy, nz);
  }

  // Lamp bottom point (connects to pole top)
  const lampTipIdx = positions.length / 3;
  positions.push(0, 0, poleHeight);
  normals.push(0, 0, -1);

  // Lamp cone faces (from ring down to tip)
  for (let i = 0; i < lampSegments; i++) {
    indices.push(
      lampBaseIdx + i,
      lampTipIdx,
      lampBaseIdx + ((i + 1) % lampSegments)
    );
  }

  // Lamp top cap (flat top)
  const lampCapIdx = positions.length / 3;
  positions.push(0, 0, 1);
  normals.push(0, 0, 1);

  for (let i = 0; i < lampSegments; i++) {
    indices.push(
      lampCapIdx,
      lampBaseIdx + i,
      lampBaseIdx + ((i + 1) % lampSegments)
    );
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
