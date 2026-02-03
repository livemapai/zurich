/**
 * Procedural Fountain Mesh Generation
 *
 * Generates 3D fountain geometry with:
 * - Circular basin (wide, short cylinder at bottom)
 * - Central column (narrow, tall cylinder)
 *
 * Creates a unit fountain (1m tall) that can be scaled per instance.
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

/** Generated fountain mesh compatible with deck.gl SimpleMeshLayer */
export interface FountainMesh {
  attributes: {
    POSITION: MeshAttribute;
    NORMAL: MeshAttribute;
  };
  indices: MeshIndices;
}

/**
 * Generate a unit fountain mesh (1m tall, scalable per instance)
 *
 * The fountain is built along the Z axis:
 * - Z=0: Base of basin
 * - Z=0.3: Top of basin / base of column
 * - Z=1: Top of column
 *
 * @param segments - Number of segments for the cylinders (default: 12)
 * @returns FountainMesh with positions, normals, and indices
 */
export function generateFountainMesh(segments = 12): FountainMesh {
  const positions: number[] = [];
  const normals: number[] = [];
  const indices: number[] = [];

  // Basin: radius 0.5, height 0.3 (bottom 30% of unit height)
  // Column: radius 0.1, height 0.7 (top 70%)
  const basinRadius = 0.5;
  const basinHeight = 0.3;
  const columnRadius = 0.1;
  const columnHeight = 0.7;

  /**
   * Add a cylinder to the mesh
   *
   * @param radius - Cylinder radius
   * @param zStart - Z position of bottom
   * @param zEnd - Z position of top
   * @returns Index offset after adding the cylinder
   */
  function addCylinder(radius: number, zStart: number, zEnd: number): number {
    const startIdx = positions.length / 3;

    // Bottom ring vertices
    for (let i = 0; i < segments; i++) {
      const angle = (i / segments) * Math.PI * 2;
      const x = Math.cos(angle) * radius;
      const y = Math.sin(angle) * radius;
      positions.push(x, y, zStart);
      // Outward-facing normals for cylinder sides
      normals.push(Math.cos(angle), Math.sin(angle), 0);
    }

    // Top ring vertices
    for (let i = 0; i < segments; i++) {
      const angle = (i / segments) * Math.PI * 2;
      const x = Math.cos(angle) * radius;
      const y = Math.sin(angle) * radius;
      positions.push(x, y, zEnd);
      normals.push(Math.cos(angle), Math.sin(angle), 0);
    }

    // Side faces (quads as two triangles)
    for (let i = 0; i < segments; i++) {
      const b1 = startIdx + i;
      const b2 = startIdx + ((i + 1) % segments);
      const t1 = startIdx + segments + i;
      const t2 = startIdx + segments + ((i + 1) % segments);
      indices.push(b1, b2, t1);
      indices.push(b2, t2, t1);
    }

    return startIdx + segments * 2;
  }

  // Add basin cylinder (wide, short)
  addCylinder(basinRadius, 0, basinHeight);

  // Add column cylinder (narrow, tall)
  addCylinder(columnRadius, basinHeight, basinHeight + columnHeight);

  // Return in deck.gl/luma.gl compatible format
  return {
    attributes: {
      POSITION: { value: new Float32Array(positions), size: 3 },
      NORMAL: { value: new Float32Array(normals), size: 3 },
    },
    indices: { value: new Uint16Array(indices) },
  };
}
