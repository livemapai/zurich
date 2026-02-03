/**
 * Procedural Toilet Building Mesh Generation
 *
 * Creates a unit toilet building (1m scale) shaped like a small kiosk:
 * - Main body: rectangular box
 * - Flat roof with slight overhang
 */

interface MeshAttribute {
  value: Float32Array;
  size: number;
}

interface MeshIndices {
  value: Uint16Array | Uint32Array;
  size?: number;
}

export interface ToiletMesh {
  attributes: {
    POSITION: MeshAttribute;
    NORMAL: MeshAttribute;
  };
  indices: MeshIndices;
}

export function generateToiletMesh(): ToiletMesh {
  const positions: number[] = [];
  const normals: number[] = [];
  const indices: number[] = [];

  function addBox(
    x0: number, y0: number, z0: number,
    x1: number, y1: number, z1: number
  ): void {
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

  // Main building body: centered on origin
  addBox(-0.5, -0.4, 0, 0.5, 0.4, 0.85);

  // Roof with slight overhang
  addBox(-0.55, -0.45, 0.85, 0.55, 0.45, 0.93);

  return {
    attributes: {
      POSITION: { value: new Float32Array(positions), size: 3 },
      NORMAL: { value: new Float32Array(normals), size: 3 },
    },
    indices: { value: new Uint16Array(indices) },
  };
}
