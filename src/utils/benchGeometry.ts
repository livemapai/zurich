/**
 * Procedural Bench Mesh Generation
 *
 * Creates a unit bench (1m scale) with:
 * - Seat: wide, shallow box slab
 * - Backrest: narrow, tall box behind seat
 *
 * The bench is built along the Z axis:
 * - Z=0: Ground level
 * - Z=0.35-0.45: Seat height
 * - Z=0.45-0.9: Backrest
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

/** Generated bench mesh compatible with deck.gl SimpleMeshLayer */
export interface BenchMesh {
  attributes: {
    POSITION: MeshAttribute;
    NORMAL: MeshAttribute;
  };
  indices: MeshIndices;
}

/**
 * Generate a unit bench mesh (1m scale, can be scaled per instance)
 *
 * Creates a simple bench with:
 * - A seat slab: 1.0m wide, 0.4m deep, at ~0.4m height
 * - A backrest: 1.0m wide, 0.1m thick, 0.45m tall
 *
 * @returns BenchMesh with positions, normals, and indices
 */
export function generateBenchMesh(): BenchMesh {
  const positions: number[] = [];
  const normals: number[] = [];
  const indices: number[] = [];

  /**
   * Adds a box (rectangular prism) to the mesh.
   * Each face gets its own vertices so normals are correct per-face.
   */
  function addBox(
    x0: number, y0: number, z0: number,
    x1: number, y1: number, z1: number
  ): void {
    // 6 faces, each with 4 vertices and 2 triangles

    // Face: Front (Y-)
    const frontStart = positions.length / 3;
    positions.push(x0, y0, z0, x1, y0, z0, x1, y0, z1, x0, y0, z1);
    for (let i = 0; i < 4; i++) normals.push(0, -1, 0);
    indices.push(frontStart, frontStart + 1, frontStart + 2);
    indices.push(frontStart, frontStart + 2, frontStart + 3);

    // Face: Back (Y+)
    const backStart = positions.length / 3;
    positions.push(x1, y1, z0, x0, y1, z0, x0, y1, z1, x1, y1, z1);
    for (let i = 0; i < 4; i++) normals.push(0, 1, 0);
    indices.push(backStart, backStart + 1, backStart + 2);
    indices.push(backStart, backStart + 2, backStart + 3);

    // Face: Left (X-)
    const leftStart = positions.length / 3;
    positions.push(x0, y1, z0, x0, y0, z0, x0, y0, z1, x0, y1, z1);
    for (let i = 0; i < 4; i++) normals.push(-1, 0, 0);
    indices.push(leftStart, leftStart + 1, leftStart + 2);
    indices.push(leftStart, leftStart + 2, leftStart + 3);

    // Face: Right (X+)
    const rightStart = positions.length / 3;
    positions.push(x1, y0, z0, x1, y1, z0, x1, y1, z1, x1, y0, z1);
    for (let i = 0; i < 4; i++) normals.push(1, 0, 0);
    indices.push(rightStart, rightStart + 1, rightStart + 2);
    indices.push(rightStart, rightStart + 2, rightStart + 3);

    // Face: Top (Z+)
    const topStart = positions.length / 3;
    positions.push(x0, y0, z1, x1, y0, z1, x1, y1, z1, x0, y1, z1);
    for (let i = 0; i < 4; i++) normals.push(0, 0, 1);
    indices.push(topStart, topStart + 1, topStart + 2);
    indices.push(topStart, topStart + 2, topStart + 3);

    // Face: Bottom (Z-)
    const bottomStart = positions.length / 3;
    positions.push(x0, y1, z0, x1, y1, z0, x1, y0, z0, x0, y0, z0);
    for (let i = 0; i < 4; i++) normals.push(0, 0, -1);
    indices.push(bottomStart, bottomStart + 1, bottomStart + 2);
    indices.push(bottomStart, bottomStart + 2, bottomStart + 3);
  }

  // Bench seat slab: centered on X, front edge at Y=0
  // Dimensions: 1.0m wide (X: -0.5 to 0.5), 0.4m deep (Y: 0 to 0.4), 0.1m thick (Z: 0.35 to 0.45)
  addBox(-0.5, 0, 0.35, 0.5, 0.4, 0.45);

  // Backrest: at back of seat, taller
  // Dimensions: 1.0m wide, 0.1m thick (Y: 0.3 to 0.4), 0.45m tall (Z: 0.45 to 0.9)
  addBox(-0.5, 0.3, 0.45, 0.5, 0.4, 0.9);

  // Return in deck.gl/luma.gl compatible format
  return {
    attributes: {
      POSITION: { value: new Float32Array(positions), size: 3 },
      NORMAL: { value: new Float32Array(normals), size: 3 },
    },
    indices: { value: new Uint16Array(indices) },
  };
}
