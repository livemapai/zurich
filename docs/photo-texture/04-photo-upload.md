# Step 4: Photo Upload

## Goal

Upload a photo and apply it to the selected facade. The image stretches to fit the facade dimensions.

## Prerequisites

- Step 3 completed (facade selection works)
- Selected facade available in state

## What You'll Learn

- React file input handling
- Object URL creation and cleanup
- BitmapLayer with dynamic images
- Aspect ratio considerations

## Implementation

### 1. Create Upload Component

```typescript
// src/components/PhotoUpload/PhotoUpload.tsx

import { useCallback, useRef } from 'react';
import './PhotoUpload.css';

interface Props {
  onUpload: (file: File, objectUrl: string) => void;
  disabled?: boolean;
}

export function PhotoUpload({ onUpload, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleClick = () => {
    inputRef.current?.click();
  };

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file');
      return;
    }

    // Create object URL for preview/rendering
    const objectUrl = URL.createObjectURL(file);
    onUpload(file, objectUrl);

    // Reset input for re-uploading same file
    e.target.value = '';
  }, [onUpload]);

  return (
    <div className="photo-upload">
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        onChange={handleChange}
        style={{ display: 'none' }}
      />
      <button
        onClick={handleClick}
        disabled={disabled}
        className="upload-button"
      >
        📷 Upload Photo
      </button>
    </div>
  );
}
```

```css
/* src/components/PhotoUpload/PhotoUpload.css */

.photo-upload {
  display: inline-block;
}

.upload-button {
  background: #3b82f6;
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.upload-button:hover:not(:disabled) {
  background: #2563eb;
}

.upload-button:disabled {
  background: #6b7280;
  cursor: not-allowed;
}
```

### 2. Texture State Management

```typescript
// src/hooks/useTextureMode.ts (extended)

export interface FacadeTexture {
  facadeId: string;
  buildingId: string;
  imageUrl: string;      // Object URL or data URL
  fileName: string;
  uploadedAt: number;
  facade: FacadeQuad;    // The 4 corners
}

export interface TextureModeState {
  enabled: boolean;
  selectedBuildingId: string | null;
  selectedFacadeId: string | null;
  facadeEdges: FacadeEdge[];
  textures: FacadeTexture[];  // Add this
}

// Add texture application
const applyTexture = useCallback((
  file: File,
  objectUrl: string
) => {
  if (!selectedFacadeId || !selectedBuildingId) return;

  const edge = facadeEdges.find(e => e.id === selectedFacadeId);
  if (!edge) return;

  const facade = extractFacade(
    [edge.start, edge.end],
    0,
    420, // base altitude
    getBuildingHeight(selectedBuildingId)
  );

  const texture: FacadeTexture = {
    facadeId: selectedFacadeId,
    buildingId: selectedBuildingId,
    imageUrl: objectUrl,
    fileName: file.name,
    uploadedAt: Date.now(),
    facade,
  };

  setState(prev => ({
    ...prev,
    textures: [
      ...prev.textures.filter(t => t.facadeId !== selectedFacadeId),
      texture,
    ],
    selectedFacadeId: null, // Clear selection after applying
  }));
}, [selectedFacadeId, selectedBuildingId, facadeEdges]);
```

### 3. Create Texture Layers

```typescript
// src/layers/FacadeTexturesLayer.ts

import { BitmapLayer } from '@deck.gl/layers';
import type { FacadeTexture } from '../hooks/useTextureMode';

export function createFacadeTexturesLayers(
  textures: FacadeTexture[]
): BitmapLayer[] {
  return textures.map(texture =>
    new BitmapLayer({
      id: `texture-${texture.facadeId}`,
      image: texture.imageUrl,
      bounds: [
        texture.facade.bottomLeft,
        texture.facade.bottomRight,
        texture.facade.topRight,
        texture.facade.topLeft,
      ],
      parameters: {
        depthTest: true,
        depthWriteEnabled: false,
      },
    })
  );
}
```

### 4. Integrate in ZurichViewer

```typescript
// In ZurichViewer.tsx

import { PhotoUpload } from '@/components/PhotoUpload/PhotoUpload';
import { createFacadeTexturesLayers } from '@/layers/FacadeTexturesLayer';

const {
  enabled,
  selectedBuildingId,
  selectedFacadeId,
  textures,
  applyTexture,
} = useTextureMode();

// Create texture layers
const textureLayers = createFacadeTexturesLayers(textures);

const layers = [
  buildingsLayer,
  ...textureLayers,  // Spread texture layers
  facadeLayer,       // Selection UI on top
].filter(Boolean);

// In render
{enabled && selectedFacadeId && (
  <PhotoUpload onUpload={applyTexture} />
)}
```

### 5. Image Preview Panel

```typescript
// src/components/TexturePreview/TexturePreview.tsx

interface Props {
  texture: FacadeTexture;
  onRemove: () => void;
}

export function TexturePreview({ texture, onRemove }: Props) {
  return (
    <div className="texture-preview">
      <img
        src={texture.imageUrl}
        alt={texture.fileName}
        className="preview-image"
      />
      <div className="preview-info">
        <span className="file-name">{texture.fileName}</span>
        <button onClick={onRemove} className="remove-btn">
          ✕ Remove
        </button>
      </div>
    </div>
  );
}
```

### 6. Handle Object URL Cleanup

```typescript
// In useTextureMode.ts

// Clean up object URLs when textures are removed
const removeTexture = useCallback((facadeId: string) => {
  setState(prev => {
    const texture = prev.textures.find(t => t.facadeId === facadeId);
    if (texture && texture.imageUrl.startsWith('blob:')) {
      URL.revokeObjectURL(texture.imageUrl);
    }
    return {
      ...prev,
      textures: prev.textures.filter(t => t.facadeId !== facadeId),
    };
  });
}, []);

// Cleanup all on unmount
useEffect(() => {
  return () => {
    textures.forEach(t => {
      if (t.imageUrl.startsWith('blob:')) {
        URL.revokeObjectURL(t.imageUrl);
      }
    });
  };
}, []);
```

## Verification

1. Run `pnpm type-check` - no errors
2. Open viewer, press T, select building, select facade
3. Click "Upload Photo" and choose an image
4. Verify:
   - [ ] Image appears on the selected facade
   - [ ] Image stretches to fill facade dimensions
   - [ ] Selection clears after upload
   - [ ] Can upload to multiple facades
   - [ ] Can remove/replace a texture
   - [ ] Memory doesn't leak (check object URLs)

## Aspect Ratio Considerations

Photos rarely match facade proportions. Options:

1. **Stretch (current)** - Simple but distorts image
2. **Cover** - Crop to fill, lose edges
3. **Contain** - Letterbox, show full image with gaps
4. **Manual crop** - User selects region

For now, stretching is acceptable. Step 5 (homography) will allow perspective correction which is more important.

## Files Created/Modified

- `src/components/PhotoUpload/PhotoUpload.tsx` (new)
- `src/components/PhotoUpload/PhotoUpload.css` (new)
- `src/components/TexturePreview/TexturePreview.tsx` (new)
- `src/layers/FacadeTexturesLayer.ts` (new)
- `src/hooks/useTextureMode.ts` (extended)
- `src/components/ZurichViewer/ZurichViewer.tsx` (modified)

## Next Step

Photos are now applied but perspective is usually wrong. Proceed to [05-homography.md](./05-homography.md) to add perspective correction.

## Notes

- Object URLs are fast but temporary (cleared on page reload)
- Step 6 will convert to data URLs for persistence
- Consider max file size limits for performance
- Mobile cameras create very large files - may need resize
