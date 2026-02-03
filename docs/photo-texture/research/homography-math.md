# Research: Homography Math

## What is Homography?

A homography (or projective transformation) is a mapping between two planes. When you photograph a flat surface (like a building facade) from an angle, the rectangular facade appears as a quadrilateral in the image. Homography lets us reverse this distortion.

```
Real World (rectangle):     Photo (quadrilateral):

┌──────────────┐                ╱──────────╲
│              │               ╱            ╲
│   FACADE     │      →       ╱              ╲
│              │             ╱                ╲
└──────────────┘            ╱──────────────────╲
```

## The 3×3 Homography Matrix

A homography is represented as a 3×3 matrix H that transforms homogeneous coordinates:

```
┌   ┐   ┌           ┐   ┌   ┐
│ x'│   │ h11 h12 h13│   │ x │
│ y'│ = │ h21 h22 h23│ × │ y │
│ w'│   │ h31 h32 h33│   │ 1 │
└   ┘   └           ┘   └   ┘

Final coordinates: (x'/w', y'/w')
```

The matrix has 9 elements but only 8 degrees of freedom (we can scale by any factor). This means we need 4 point correspondences (8 equations) to solve for H.

## Direct Linear Transform (DLT)

The DLT algorithm solves for H given 4 or more point correspondences.

### Setup

Given:
- Source points: (x₁, y₁), (x₂, y₂), (x₃, y₃), (x₄, y₄)
- Destination points: (x'₁, y'₁), (x'₂, y'₂), (x'₃, y'₃), (x'₄, y'₄)

For each point correspondence, we get two equations:

```
-xᵢ·h₁₁ - yᵢ·h₁₂ - h₁₃ + x'ᵢ·xᵢ·h₃₁ + x'ᵢ·yᵢ·h₃₂ + x'ᵢ·h₃₃ = 0
-xᵢ·h₂₁ - yᵢ·h₂₂ - h₂₃ + y'ᵢ·xᵢ·h₃₁ + y'ᵢ·yᵢ·h₃₂ + y'ᵢ·h₃₃ = 0
```

### Matrix Form

Stack all equations into a matrix A:

```
A × h = 0

Where h = [h₁₁, h₁₂, h₁₃, h₂₁, h₂₂, h₂₃, h₃₁, h₃₂, h₃₃]ᵀ
```

### Solution via SVD

The solution is the null space of A, found via Singular Value Decomposition:

```
A = U × Σ × Vᵀ

h = last column of V (corresponding to smallest singular value)
```

## JavaScript Implementation

### Simple 4-Point Homography

```javascript
/**
 * Calculate homography matrix from 4 point correspondences
 * @param {Array} src - Source points [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
 * @param {Array} dst - Destination points [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
 * @returns {Array} 3x3 homography matrix as flat array [h11,h12,h13,h21,...]
 */
function computeHomography(src, dst) {
  // Build the 8x9 matrix A
  const A = [];

  for (let i = 0; i < 4; i++) {
    const [sx, sy] = src[i];
    const [dx, dy] = dst[i];

    A.push([
      -sx, -sy, -1,
      0, 0, 0,
      sx * dx, sy * dx, dx
    ]);

    A.push([
      0, 0, 0,
      -sx, -sy, -1,
      sx * dy, sy * dy, dy
    ]);
  }

  // Solve A*h = 0 using SVD
  const { V } = svd(A);

  // Solution is last column of V
  const h = V.map(row => row[8]);

  // Normalize so h33 = 1
  const scale = h[8];
  return h.map(v => v / scale);
}
```

### SVD Implementation (Simplified)

For a robust implementation, use a library like `ml-matrix` or `numeric.js`. Here's a simplified version for understanding:

```javascript
/**
 * Simplified SVD for 8x9 matrix
 * In production, use a library!
 */
function svd(A) {
  // Compute A^T * A
  const ATA = matMul(transpose(A), A);

  // Find eigenvalues and eigenvectors of ATA
  const { eigenvalues, eigenvectors } = eigenDecomposition(ATA);

  // V is the matrix of eigenvectors
  // Columns are ordered by decreasing eigenvalue
  // Last column corresponds to smallest eigenvalue (≈0)
  return { V: eigenvectors };
}

// Matrix utilities
function transpose(M) {
  return M[0].map((_, i) => M.map(row => row[i]));
}

function matMul(A, B) {
  return A.map(row =>
    B[0].map((_, j) =>
      row.reduce((sum, val, k) => sum + val * B[k][j], 0)
    )
  );
}
```

### Using ml-matrix Library

```javascript
import { Matrix, SingularValueDecomposition } from 'ml-matrix';

function computeHomographyWithLibrary(src, dst) {
  const A = [];

  for (let i = 0; i < 4; i++) {
    const [sx, sy] = src[i];
    const [dx, dy] = dst[i];

    A.push([-sx, -sy, -1, 0, 0, 0, sx*dx, sy*dx, dx]);
    A.push([0, 0, 0, -sx, -sy, -1, sx*dy, sy*dy, dy]);
  }

  const matrix = new Matrix(A);
  const svd = new SingularValueDecomposition(matrix);
  const V = svd.rightSingularVectors;

  // Last column of V
  const h = [];
  for (let i = 0; i < 9; i++) {
    h.push(V.get(i, 8));
  }

  // Normalize
  const scale = h[8];
  return h.map(v => v / scale);
}
```

## Applying the Homography

### Forward Transform (src → dst)

```javascript
function transformPoint(H, x, y) {
  const w = H[6] * x + H[7] * y + H[8];
  const x_ = (H[0] * x + H[1] * y + H[2]) / w;
  const y_ = (H[3] * x + H[4] * y + H[5]) / w;
  return [x_, y_];
}
```

### Inverse Transform (dst → src)

For image warping, we need the inverse: given a pixel in the output, find the corresponding pixel in the input.

```javascript
function invertHomography(H) {
  // 3x3 matrix inversion
  const [a, b, c, d, e, f, g, h, i] = H;

  const det = a*(e*i - f*h) - b*(d*i - f*g) + c*(d*h - e*g);

  return [
    (e*i - f*h) / det,
    (c*h - b*i) / det,
    (b*f - c*e) / det,
    (f*g - d*i) / det,
    (a*i - c*g) / det,
    (c*d - a*f) / det,
    (d*h - e*g) / det,
    (b*g - a*h) / det,
    (a*e - b*d) / det,
  ];
}
```

### Image Warping

```javascript
function warpImage(srcImageData, H, outputWidth, outputHeight) {
  const output = new ImageData(outputWidth, outputHeight);
  const Hinv = invertHomography(H);

  for (let y = 0; y < outputHeight; y++) {
    for (let x = 0; x < outputWidth; x++) {
      // Find corresponding source pixel
      const [srcX, srcY] = transformPoint(Hinv, x, y);

      // Bilinear interpolation
      const pixel = bilinearSample(srcImageData, srcX, srcY);

      // Write to output
      const idx = (y * outputWidth + x) * 4;
      output.data[idx] = pixel[0];     // R
      output.data[idx + 1] = pixel[1]; // G
      output.data[idx + 2] = pixel[2]; // B
      output.data[idx + 3] = pixel[3]; // A
    }
  }

  return output;
}
```

### Bilinear Interpolation

```javascript
function bilinearSample(imageData, x, y) {
  const { width, height, data } = imageData;

  // Clamp to image bounds
  x = Math.max(0, Math.min(width - 1, x));
  y = Math.max(0, Math.min(height - 1, y));

  const x0 = Math.floor(x);
  const y0 = Math.floor(y);
  const x1 = Math.min(x0 + 1, width - 1);
  const y1 = Math.min(y0 + 1, height - 1);

  const fx = x - x0;
  const fy = y - y0;

  const getPixel = (px, py) => {
    const idx = (py * width + px) * 4;
    return [data[idx], data[idx+1], data[idx+2], data[idx+3]];
  };

  const p00 = getPixel(x0, y0);
  const p10 = getPixel(x1, y0);
  const p01 = getPixel(x0, y1);
  const p11 = getPixel(x1, y1);

  // Interpolate each channel
  return p00.map((v, i) =>
    Math.round(
      (1 - fx) * (1 - fy) * p00[i] +
      fx * (1 - fy) * p10[i] +
      (1 - fx) * fy * p01[i] +
      fx * fy * p11[i]
    )
  );
}
```

## Normalization (Important!)

For numerical stability, normalize points before computing homography:

```javascript
function normalizePoints(points) {
  // Compute centroid
  const cx = points.reduce((s, p) => s + p[0], 0) / points.length;
  const cy = points.reduce((s, p) => s + p[1], 0) / points.length;

  // Compute average distance from centroid
  const avgDist = points.reduce((s, p) =>
    s + Math.hypot(p[0] - cx, p[1] - cy), 0
  ) / points.length;

  // Scale so average distance is sqrt(2)
  const scale = Math.sqrt(2) / avgDist;

  // Normalized points
  const normalized = points.map(p => [
    (p[0] - cx) * scale,
    (p[1] - cy) * scale,
  ]);

  // Normalization matrix
  const T = [
    scale, 0, -cx * scale,
    0, scale, -cy * scale,
    0, 0, 1,
  ];

  return { normalized, T };
}

// Use normalized points for better numerical stability
function computeHomographyNormalized(src, dst) {
  const { normalized: srcNorm, T: Tsrc } = normalizePoints(src);
  const { normalized: dstNorm, T: Tdst } = normalizePoints(dst);

  // Compute homography on normalized points
  const Hnorm = computeHomography(srcNorm, dstNorm);

  // Denormalize: H = Tdst^(-1) * Hnorm * Tsrc
  const TdstInv = invertHomography(Tdst);
  return matMul3x3(matMul3x3(TdstInv, Hnorm), Tsrc);
}
```

## Common Issues

### Degenerate Configurations

Homography cannot be computed if:
- 3 or more points are collinear
- All 4 points are the same
- Points are too close together

```javascript
function validatePoints(points) {
  // Check for collinearity
  const area = Math.abs(
    (points[1][0] - points[0][0]) * (points[2][1] - points[0][1]) -
    (points[2][0] - points[0][0]) * (points[1][1] - points[0][1])
  );

  if (area < 1e-6) {
    throw new Error('Points are nearly collinear');
  }

  return true;
}
```

### Flipped Images

If the output is mirrored, check:
1. Corner order (should be consistent between src and dst)
2. Coordinate system (y-up vs y-down)

## References

- Hartley & Zisserman, "Multiple View Geometry" - The definitive reference
- [OpenCV Homography Tutorial](https://docs.opencv.org/4.x/d9/dab/tutorial_homography.html)
- [Wikipedia: Homography](https://en.wikipedia.org/wiki/Homography)
- [ml-matrix SVD](https://github.com/mljs/matrix)
