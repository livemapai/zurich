# Step 5: Homography (Perspective Correction)

## Goal

Allow users to correct perspective distortion by marking 4 corners on their photo that correspond to the facade corners.

## Prerequisites

- Step 4 completed (photo upload works)
- Basic understanding of perspective transformation

## What You'll Learn

- Homography matrix calculation
- Canvas 2D perspective transformation
- Draggable point UI
- Image warping

## Concepts

### What is Homography?

When you photograph a rectangular facade at an angle, it appears as a quadrilateral. Homography transforms this quad back to a rectangle.

```
Photo (distorted):          After homography:

   ╱────────╲                ┌──────────┐
  ╱          ╲               │          │
 ╱            ╲      →       │          │
╱──────────────╲             │          │
                             └──────────┘
```

### The Math

See [research/homography-math.md](./research/homography-math.md) for detailed explanation.

## Implementation

### 1. Create Corner Editor Component

```typescript
// src/components/HomographyEditor/HomographyEditor.tsx

import { useState, useRef, useCallback, useEffect } from 'react';
import './HomographyEditor.css';

interface Point {
  x: number;
  y: number;
}

interface Props {
  imageUrl: string;
  onConfirm: (correctedImageUrl: string) => void;
  onCancel: () => void;
}

export function HomographyEditor({ imageUrl, onConfirm, onCancel }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [corners, setCorners] = useState<Point[]>([
    { x: 0.1, y: 0.1 },   // Top-left (normalized 0-1)
    { x: 0.9, y: 0.1 },   // Top-right
    { x: 0.9, y: 0.9 },   // Bottom-right
    { x: 0.1, y: 0.9 },   // Bottom-left
  ]);
  const [dragging, setDragging] = useState<number | null>(null);

  // Load image
  useEffect(() => {
    const img = new Image();
    img.onload = () => setImage(img);
    img.src = imageUrl;
  }, [imageUrl]);

  // Draw canvas
  useEffect(() => {
    if (!canvasRef.current || !image) return;

    const ctx = canvasRef.current.getContext('2d');
    if (!ctx) return;

    const { width, height } = canvasRef.current;

    // Draw image
    ctx.drawImage(image, 0, 0, width, height);

    // Draw corner points
    corners.forEach((corner, i) => {
      const x = corner.x * width;
      const y = corner.y * height;

      // Point
      ctx.beginPath();
      ctx.arc(x, y, 10, 0, Math.PI * 2);
      ctx.fillStyle = i === dragging ? '#ff0' : '#0f0';
      ctx.fill();
      ctx.strokeStyle = '#000';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Label
      ctx.fillStyle = '#000';
      ctx.font = '14px sans-serif';
      ctx.fillText(['TL', 'TR', 'BR', 'BL'][i], x - 8, y + 4);
    });

    // Draw quad outline
    ctx.beginPath();
    ctx.moveTo(corners[0].x * width, corners[0].y * height);
    for (let i = 1; i <= 4; i++) {
      const c = corners[i % 4];
      ctx.lineTo(c.x * width, c.y * height);
    }
    ctx.strokeStyle = '#0f0';
    ctx.lineWidth = 2;
    ctx.stroke();
  }, [image, corners, dragging]);

  // Handle mouse/touch
  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;

    // Find closest corner
    let closest = -1;
    let minDist = 0.05; // 5% of canvas size threshold
    corners.forEach((corner, i) => {
      const dist = Math.hypot(corner.x - x, corner.y - y);
      if (dist < minDist) {
        minDist = dist;
        closest = i;
      }
    });

    if (closest >= 0) {
      setDragging(closest);
      canvas.setPointerCapture(e.pointerId);
    }
  }, [corners]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (dragging === null) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));

    setCorners(prev => prev.map((c, i) =>
      i === dragging ? { x, y } : c
    ));
  }, [dragging]);

  const handlePointerUp = useCallback(() => {
    setDragging(null);
  }, []);

  // Apply homography and export
  const handleConfirm = useCallback(() => {
    if (!image) return;

    const corrected = applyHomography(image, corners);
    onConfirm(corrected);
  }, [image, corners, onConfirm]);

  return (
    <div className="homography-editor">
      <div className="editor-header">
        <h3>Adjust Perspective</h3>
        <p>Drag the green corners to match the facade edges in your photo</p>
      </div>

      <canvas
        ref={canvasRef}
        width={800}
        height={600}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        className="editor-canvas"
      />

      <div className="editor-actions">
        <button onClick={onCancel} className="btn-cancel">
          Cancel
        </button>
        <button onClick={handleConfirm} className="btn-confirm">
          Apply Correction
        </button>
      </div>
    </div>
  );
}
```

### 2. Homography Calculation

```typescript
// src/utils/homography.ts

interface Point {
  x: number;
  y: number;
}

/**
 * Calculate 3x3 homography matrix using Direct Linear Transform (DLT)
 * Maps srcPoints to dstPoints
 */
export function calculateHomography(
  srcPoints: Point[],  // 4 corners in source image
  dstPoints: Point[]   // 4 corners in destination (rectangle)
): number[] {
  // Build the 8x9 matrix for DLT
  const A: number[][] = [];

  for (let i = 0; i < 4; i++) {
    const { x: sx, y: sy } = srcPoints[i];
    const { x: dx, y: dy } = dstPoints[i];

    A.push([
      -sx, -sy, -1, 0, 0, 0, sx * dx, sy * dx, dx
    ]);
    A.push([
      0, 0, 0, -sx, -sy, -1, sx * dy, sy * dy, dy
    ]);
  }

  // Solve using SVD (simplified - use a library in production)
  // Returns the null space of A, which is the homography
  const h = solveHomographyDLT(A);

  return h;
}

/**
 * Apply homography to transform image
 */
export function applyHomography(
  sourceImage: HTMLImageElement,
  corners: Point[]  // User-marked corners (normalized 0-1)
): string {
  // Output size (could be configurable)
  const outWidth = 1024;
  const outHeight = 1024;

  // Create output canvas
  const canvas = document.createElement('canvas');
  canvas.width = outWidth;
  canvas.height = outHeight;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Could not get canvas context');

  // Source points (user-marked corners in pixel coordinates)
  const srcPoints = corners.map(c => ({
    x: c.x * sourceImage.width,
    y: c.y * sourceImage.height,
  }));

  // Destination points (rectangle corners)
  const dstPoints = [
    { x: 0, y: 0 },
    { x: outWidth, y: 0 },
    { x: outWidth, y: outHeight },
    { x: 0, y: outHeight },
  ];

  // Calculate inverse homography (dst -> src)
  const H = calculateHomography(dstPoints, srcPoints);

  // Get source image data
  const srcCanvas = document.createElement('canvas');
  srcCanvas.width = sourceImage.width;
  srcCanvas.height = sourceImage.height;
  const srcCtx = srcCanvas.getContext('2d');
  if (!srcCtx) throw new Error('Could not get source canvas context');
  srcCtx.drawImage(sourceImage, 0, 0);
  const srcData = srcCtx.getImageData(0, 0, srcCanvas.width, srcCanvas.height);

  // Create output image data
  const outData = ctx.createImageData(outWidth, outHeight);

  // For each output pixel, find corresponding source pixel
  for (let y = 0; y < outHeight; y++) {
    for (let x = 0; x < outWidth; x++) {
      // Apply homography: src = H * dst
      const w = H[6] * x + H[7] * y + H[8];
      const srcX = (H[0] * x + H[1] * y + H[2]) / w;
      const srcY = (H[3] * x + H[4] * y + H[5]) / w;

      // Bilinear interpolation
      const pixel = bilinearSample(srcData, srcX, srcY);

      const outIdx = (y * outWidth + x) * 4;
      outData.data[outIdx] = pixel[0];
      outData.data[outIdx + 1] = pixel[1];
      outData.data[outIdx + 2] = pixel[2];
      outData.data[outIdx + 3] = pixel[3];
    }
  }

  ctx.putImageData(outData, 0, 0);
  return canvas.toDataURL('image/jpeg', 0.9);
}

function bilinearSample(
  imageData: ImageData,
  x: number,
  y: number
): [number, number, number, number] {
  const { width, height, data } = imageData;

  // Clamp to bounds
  x = Math.max(0, Math.min(width - 1, x));
  y = Math.max(0, Math.min(height - 1, y));

  const x0 = Math.floor(x);
  const y0 = Math.floor(y);
  const x1 = Math.min(x0 + 1, width - 1);
  const y1 = Math.min(y0 + 1, height - 1);

  const fx = x - x0;
  const fy = y - y0;

  const getPixel = (px: number, py: number): [number, number, number, number] => {
    const idx = (py * width + px) * 4;
    return [data[idx], data[idx + 1], data[idx + 2], data[idx + 3]];
  };

  const p00 = getPixel(x0, y0);
  const p10 = getPixel(x1, y0);
  const p01 = getPixel(x0, y1);
  const p11 = getPixel(x1, y1);

  return [0, 1, 2, 3].map(i =>
    (1 - fx) * (1 - fy) * p00[i] +
    fx * (1 - fy) * p10[i] +
    (1 - fx) * fy * p01[i] +
    fx * fy * p11[i]
  ) as [number, number, number, number];
}
```

### 3. Integrate into Upload Flow

```typescript
// In useTextureMode.ts

export interface TextureModeState {
  // ... existing
  pendingImage: { file: File; objectUrl: string } | null;
  showHomographyEditor: boolean;
}

// New flow:
// 1. User uploads image -> set pendingImage, show editor
// 2. User adjusts corners -> apply homography
// 3. Corrected image applied to facade

const uploadImage = useCallback((file: File, objectUrl: string) => {
  setState(prev => ({
    ...prev,
    pendingImage: { file, objectUrl },
    showHomographyEditor: true,
  }));
}, []);

const confirmHomography = useCallback((correctedUrl: string) => {
  // Clean up original object URL
  if (state.pendingImage) {
    URL.revokeObjectURL(state.pendingImage.objectUrl);
  }

  // Apply corrected texture
  applyTextureWithUrl(correctedUrl);

  setState(prev => ({
    ...prev,
    pendingImage: null,
    showHomographyEditor: false,
  }));
}, [state.pendingImage]);
```

### 4. Add to ZurichViewer

```typescript
// In ZurichViewer.tsx

{showHomographyEditor && pendingImage && (
  <div className="editor-overlay">
    <HomographyEditor
      imageUrl={pendingImage.objectUrl}
      onConfirm={confirmHomography}
      onCancel={() => cancelHomography()}
    />
  </div>
)}
```

```css
.editor-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}
```

## Verification

1. Run `pnpm type-check` - no errors
2. Open viewer, select facade, upload photo
3. Verify:
   - [ ] Homography editor opens as overlay
   - [ ] 4 green corner points visible
   - [ ] Points are draggable
   - [ ] Quad outline updates as points move
   - [ ] "Apply Correction" transforms image
   - [ ] Corrected image appears on facade
   - [ ] Perspective looks corrected

## Performance Notes

- Homography calculation is fast (~1ms)
- Image warping can be slow for large images
- Consider resizing input to max 2048px
- WebGL-based warping would be faster (future enhancement)

## Files Created/Modified

- `src/components/HomographyEditor/HomographyEditor.tsx` (new)
- `src/components/HomographyEditor/HomographyEditor.css` (new)
- `src/utils/homography.ts` (new)
- `src/hooks/useTextureMode.ts` (extended)
- `src/components/ZurichViewer/ZurichViewer.tsx` (modified)

## Next Step

Textures now look correct but are lost on page reload. Proceed to [06-persistence.md](./06-persistence.md) to save textures.

## Notes

- The DLT algorithm needs a proper SVD implementation
- Consider using a library like `numeric.js` or `ml-matrix`
- Touch support important for mobile users
- Could add grid overlay to help alignment
