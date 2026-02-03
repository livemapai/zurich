# Step 6: Persistence

## Goal

Save texture mappings to localStorage so they persist between browser sessions. Add export/import functionality for sharing.

## Prerequisites

- Step 5 completed (homography works)
- Textures being applied to facades

## What You'll Learn

- localStorage for state persistence
- Data URL vs Object URL tradeoffs
- JSON export/import patterns
- Storage quota management

## Implementation

### 1. Define Storage Schema

```typescript
// src/lib/textureStorage.ts

export interface StoredTexture {
  id: string;               // Unique ID
  facadeId: string;         // Which facade
  buildingId: string;       // Which building
  imageDataUrl: string;     // Base64 data URL
  fileName: string;         // Original filename
  createdAt: number;        // Timestamp
  updatedAt: number;
  facade: {
    bottomLeft: [number, number, number];
    bottomRight: [number, number, number];
    topRight: [number, number, number];
    topLeft: [number, number, number];
  };
}

export interface TextureStore {
  version: number;
  textures: StoredTexture[];
}

const STORAGE_KEY = 'zurich3d_textures';
const CURRENT_VERSION = 1;
```

### 2. Storage Functions

```typescript
// src/lib/textureStorage.ts (continued)

export function loadTextures(): StoredTexture[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];

    const store: TextureStore = JSON.parse(raw);

    // Handle version migrations if needed
    if (store.version !== CURRENT_VERSION) {
      return migrateTextures(store);
    }

    return store.textures;
  } catch (error) {
    console.error('Failed to load textures:', error);
    return [];
  }
}

export function saveTextures(textures: StoredTexture[]): boolean {
  try {
    const store: TextureStore = {
      version: CURRENT_VERSION,
      textures,
    };

    const json = JSON.stringify(store);

    // Check storage quota (rough estimate)
    const sizeInMB = json.length / (1024 * 1024);
    if (sizeInMB > 4) {
      console.warn('Texture storage approaching limit:', sizeInMB.toFixed(2), 'MB');
    }

    localStorage.setItem(STORAGE_KEY, json);
    return true;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'QuotaExceededError') {
      console.error('Storage quota exceeded. Consider removing old textures.');
    }
    return false;
  }
}

export function addTexture(texture: StoredTexture): boolean {
  const textures = loadTextures();

  // Remove existing texture for same facade
  const filtered = textures.filter(t => t.facadeId !== texture.facadeId);
  filtered.push(texture);

  return saveTextures(filtered);
}

export function removeTexture(facadeId: string): boolean {
  const textures = loadTextures();
  const filtered = textures.filter(t => t.facadeId !== facadeId);
  return saveTextures(filtered);
}

export function clearAllTextures(): boolean {
  return saveTextures([]);
}

function migrateTextures(oldStore: TextureStore): StoredTexture[] {
  // Handle migrations between versions
  console.log('Migrating textures from version', oldStore.version);
  return oldStore.textures;
}
```

### 3. Convert Object URL to Data URL

```typescript
// src/utils/imageUtils.ts

export function objectUrlToDataUrl(
  objectUrl: string,
  maxSize = 1024  // Resize to max dimension
): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      // Calculate resize dimensions
      let { width, height } = img;
      if (width > maxSize || height > maxSize) {
        const scale = maxSize / Math.max(width, height);
        width = Math.round(width * scale);
        height = Math.round(height * scale);
      }

      // Draw to canvas
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reject(new Error('Could not get canvas context'));
        return;
      }

      ctx.drawImage(img, 0, 0, width, height);

      // Convert to data URL (JPEG for smaller size)
      const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
      resolve(dataUrl);
    };
    img.onerror = () => reject(new Error('Failed to load image'));
    img.src = objectUrl;
  });
}

export function estimateStorageSize(textures: StoredTexture[]): number {
  return textures.reduce((total, t) => {
    // Data URL is ~33% larger than binary
    return total + t.imageDataUrl.length;
  }, 0);
}
```

### 4. Integrate with useTextureMode

```typescript
// src/hooks/useTextureMode.ts (extended)

import {
  loadTextures,
  addTexture,
  removeTexture,
  type StoredTexture
} from '@/lib/textureStorage';
import { objectUrlToDataUrl } from '@/utils/imageUtils';

// Load textures on mount
useEffect(() => {
  const stored = loadTextures();

  // Convert stored textures to runtime format
  const runtime: FacadeTexture[] = stored.map(s => ({
    facadeId: s.facadeId,
    buildingId: s.buildingId,
    imageUrl: s.imageDataUrl,  // Data URLs work directly
    fileName: s.fileName,
    uploadedAt: s.createdAt,
    facade: s.facade,
  }));

  setState(prev => ({ ...prev, textures: runtime }));
}, []);

// Save texture when applied
const applyTextureWithPersistence = useCallback(async (
  file: File,
  correctedImageUrl: string,  // Could be object URL or data URL
  facade: FacadeQuad
) => {
  // Ensure we have a data URL for storage
  let dataUrl = correctedImageUrl;
  if (correctedImageUrl.startsWith('blob:')) {
    dataUrl = await objectUrlToDataUrl(correctedImageUrl);
    URL.revokeObjectURL(correctedImageUrl);
  }

  const stored: StoredTexture = {
    id: `texture_${Date.now()}`,
    facadeId: selectedFacadeId!,
    buildingId: selectedBuildingId!,
    imageDataUrl: dataUrl,
    fileName: file.name,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    facade,
  };

  // Save to localStorage
  const success = addTexture(stored);
  if (!success) {
    console.error('Failed to save texture - storage may be full');
  }

  // Update runtime state
  setState(prev => ({
    ...prev,
    textures: [
      ...prev.textures.filter(t => t.facadeId !== stored.facadeId),
      {
        facadeId: stored.facadeId,
        buildingId: stored.buildingId,
        imageUrl: dataUrl,
        fileName: stored.fileName,
        uploadedAt: stored.createdAt,
        facade: stored.facade,
      },
    ],
    selectedFacadeId: null,
  }));
}, [selectedFacadeId, selectedBuildingId]);
```

### 5. Export/Import UI

```typescript
// src/components/TextureManager/TextureManager.tsx

import { loadTextures, saveTextures, clearAllTextures } from '@/lib/textureStorage';

interface Props {
  textureCount: number;
  onImport: () => void;
}

export function TextureManager({ textureCount, onImport }: Props) {
  const handleExport = useCallback(() => {
    const textures = loadTextures();
    const blob = new Blob([JSON.stringify(textures, null, 2)], {
      type: 'application/json',
    });

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `zurich-textures-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, []);

  const handleImport = useCallback(() => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;

      try {
        const text = await file.text();
        const imported = JSON.parse(text) as StoredTexture[];

        // Validate structure
        if (!Array.isArray(imported)) {
          throw new Error('Invalid format');
        }

        // Merge with existing
        const existing = loadTextures();
        const merged = [
          ...existing,
          ...imported.filter(i => !existing.some(e => e.facadeId === i.facadeId)),
        ];

        saveTextures(merged);
        onImport();  // Trigger reload
      } catch (error) {
        console.error('Import failed:', error);
        alert('Failed to import textures. Invalid file format.');
      }
    };
    input.click();
  }, [onImport]);

  const handleClear = useCallback(() => {
    if (confirm('Delete all saved textures? This cannot be undone.')) {
      clearAllTextures();
      onImport();  // Trigger reload
    }
  }, [onImport]);

  return (
    <div className="texture-manager">
      <div className="manager-stats">
        {textureCount} texture{textureCount !== 1 ? 's' : ''} saved
      </div>
      <div className="manager-actions">
        <button onClick={handleExport} disabled={textureCount === 0}>
          📤 Export
        </button>
        <button onClick={handleImport}>
          📥 Import
        </button>
        <button onClick={handleClear} disabled={textureCount === 0} className="danger">
          🗑️ Clear All
        </button>
      </div>
    </div>
  );
}
```

### 6. Storage Status Indicator

```typescript
// src/components/StorageStatus/StorageStatus.tsx

import { useEffect, useState } from 'react';
import { loadTextures, estimateStorageSize } from '@/lib/textureStorage';

export function StorageStatus() {
  const [usage, setUsage] = useState({ count: 0, sizeMB: 0 });

  useEffect(() => {
    const textures = loadTextures();
    const size = estimateStorageSize(textures);
    setUsage({
      count: textures.length,
      sizeMB: size / (1024 * 1024),
    });
  }, []);

  const maxMB = 5; // Approximate localStorage limit
  const percent = (usage.sizeMB / maxMB) * 100;

  return (
    <div className="storage-status">
      <div className="storage-bar">
        <div
          className="storage-fill"
          style={{ width: `${Math.min(100, percent)}%` }}
        />
      </div>
      <div className="storage-text">
        {usage.sizeMB.toFixed(2)} MB / ~{maxMB} MB
      </div>
    </div>
  );
}
```

## Verification

1. Run `pnpm type-check` - no errors
2. Open viewer, apply a texture to a facade
3. Refresh the page
4. Verify:
   - [ ] Texture still visible after refresh
   - [ ] Multiple textures persist
   - [ ] Export creates valid JSON file
   - [ ] Import loads textures from JSON
   - [ ] Clear all removes everything
   - [ ] Storage indicator shows usage

## Storage Limits

| Browser | localStorage Limit |
|---------|-------------------|
| Chrome | ~5 MB |
| Firefox | ~5 MB |
| Safari | ~5 MB |
| Edge | ~5 MB |

At ~100KB per compressed texture, you can store ~50 textures.

## Files Created/Modified

- `src/lib/textureStorage.ts` (new)
- `src/utils/imageUtils.ts` (new)
- `src/components/TextureManager/TextureManager.tsx` (new)
- `src/components/StorageStatus/StorageStatus.tsx` (new)
- `src/hooks/useTextureMode.ts` (extended)
- `src/components/ZurichViewer/ZurichViewer.tsx` (modified)

## Future Enhancements

- Cloud storage backend (Firebase, Supabase)
- Shared texture libraries
- Compression (WebP instead of JPEG)
- IndexedDB for larger storage
- Lazy loading for many textures

## Complete!

You've now implemented the full photo-to-building texture pipeline:

1. ✅ Hardcoded texture (proof of concept)
2. ✅ Building selection (interactivity)
3. ✅ Facade selection (precision)
4. ✅ Photo upload (user content)
5. ✅ Homography (perspective correction)
6. ✅ Persistence (durability)

## Notes

- Data URLs are larger than binary but simpler to store
- Consider IndexedDB for production (larger quota)
- Export format could include metadata (date, location)
- Could add thumbnail generation for texture list
