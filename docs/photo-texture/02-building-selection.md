# Step 2: Building Selection

## Goal

Click on a building to select it for texturing. Add a "texture mode" toggle so normal navigation isn't affected.

## Prerequisites

- Step 1 completed (hardcoded texture works)
- Buildings rendering with deck.gl

## What You'll Learn

- deck.gl picking system
- React state management for selection
- Layer interaction modes

## Implementation

### 1. Add Texture Mode State

```typescript
// src/hooks/useTextureMode.ts

import { useState, useCallback } from 'react';

export interface TextureModeState {
  enabled: boolean;
  selectedBuildingId: string | null;
}

export function useTextureMode() {
  const [state, setState] = useState<TextureModeState>({
    enabled: false,
    selectedBuildingId: null,
  });

  const toggleTextureMode = useCallback(() => {
    setState(prev => ({
      ...prev,
      enabled: !prev.enabled,
      selectedBuildingId: null, // Clear selection on toggle
    }));
  }, []);

  const selectBuilding = useCallback((buildingId: string | null) => {
    setState(prev => ({
      ...prev,
      selectedBuildingId: buildingId,
    }));
  }, []);

  return {
    ...state,
    toggleTextureMode,
    selectBuilding,
  };
}
```

### 2. Add Keyboard Toggle (T key)

```typescript
// In useKeyboardState.ts or new hook

useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 't' || e.key === 'T') {
      toggleTextureMode();
    }
  };

  window.addEventListener('keydown', handleKeyDown);
  return () => window.removeEventListener('keydown', handleKeyDown);
}, [toggleTextureMode]);
```

### 3. Enable Picking on Buildings Layer

```typescript
// src/layers/BuildingsLayer.ts

export function createBuildingsLayer(
  data: BuildingFeature[],
  options: {
    pickable?: boolean;
    onHover?: (info: PickingInfo) => void;
    onClick?: (info: PickingInfo) => void;
    highlightedId?: string | null;
  }
) {
  return new GeoJsonLayer({
    id: 'buildings',
    data,
    // Existing props...

    // Picking
    pickable: options.pickable ?? false,
    onHover: options.onHover,
    onClick: options.onClick,

    // Highlight selected building
    getFillColor: (d) => {
      if (d.properties.id === options.highlightedId) {
        return [255, 200, 0, 200]; // Yellow highlight
      }
      return [200, 200, 200, 200]; // Default gray
    },

    updateTriggers: {
      getFillColor: [options.highlightedId],
    },
  });
}
```

### 4. Handle Building Click

```typescript
// In ZurichViewer.tsx

const { enabled, selectedBuildingId, selectBuilding } = useTextureMode();

const handleBuildingClick = useCallback((info: PickingInfo) => {
  if (!enabled) return;

  const feature = info.object as BuildingFeature | undefined;
  if (feature?.properties?.id) {
    selectBuilding(feature.properties.id);
    console.log('Selected building:', feature.properties.id);
  }
}, [enabled, selectBuilding]);

// Pass to layer
const buildingsLayer = createBuildingsLayer(buildings, {
  pickable: enabled,
  onClick: handleBuildingClick,
  highlightedId: selectedBuildingId,
});
```

### 5. Add Mode Indicator UI

```typescript
// src/components/TextureModeIndicator.tsx

interface Props {
  enabled: boolean;
  selectedBuildingId: string | null;
}

export function TextureModeIndicator({ enabled, selectedBuildingId }: Props) {
  if (!enabled) return null;

  return (
    <div className="texture-mode-indicator">
      <div className="mode-badge">TEXTURE MODE</div>
      {selectedBuildingId ? (
        <div className="selection-info">
          Selected: {selectedBuildingId}
        </div>
      ) : (
        <div className="selection-hint">
          Click a building to select it
        </div>
      )}
      <div className="mode-hint">Press T to exit</div>
    </div>
  );
}
```

```css
/* src/styles/texture-mode.css */

.texture-mode-indicator {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.8);
  color: white;
  padding: 12px 24px;
  border-radius: 8px;
  text-align: center;
  z-index: 1000;
}

.mode-badge {
  background: #f59e0b;
  color: black;
  font-weight: bold;
  padding: 4px 12px;
  border-radius: 4px;
  margin-bottom: 8px;
  display: inline-block;
}

.selection-info {
  font-family: monospace;
  font-size: 14px;
}

.selection-hint {
  color: #9ca3af;
  font-size: 14px;
}

.mode-hint {
  color: #6b7280;
  font-size: 12px;
  margin-top: 8px;
}
```

### 6. Disable Navigation in Texture Mode

```typescript
// In ZurichViewer.tsx or movement hooks

// When texture mode is enabled:
// - Disable pointer lock (mouse look)
// - Disable WASD movement
// - Enable normal mouse cursor for clicking

const handleCanvasClick = useCallback(() => {
  if (!textureModeEnabled) {
    // Normal: request pointer lock for mouse look
    requestPointerLock();
  }
  // In texture mode: don't lock pointer, allow clicking
}, [textureModeEnabled]);
```

## Verification

1. Run `pnpm type-check` - no errors
2. Open viewer in browser
3. Press T to enter texture mode
4. Verify:
   - [ ] Mode indicator appears at top
   - [ ] Mouse cursor is visible (not locked)
   - [ ] Hover over building shows cursor change
   - [ ] Click building highlights it yellow
   - [ ] Building ID shown in indicator
   - [ ] Press T again exits mode
   - [ ] Navigation works normally outside texture mode

## Files Created/Modified

- `src/hooks/useTextureMode.ts` (new)
- `src/components/TextureModeIndicator.tsx` (new)
- `src/styles/texture-mode.css` (new)
- `src/layers/BuildingsLayer.ts` (modified)
- `src/components/ZurichViewer/ZurichViewer.tsx` (modified)

## Next Step

With building selection working, proceed to [03-facade-selection.md](./03-facade-selection.md) to select specific building faces.

## Notes

- deck.gl picking uses GPU color picking for performance
- `pickable: true` has minimal performance impact
- Consider adding hover highlight (lighter yellow) for UX
- Building ID must be unique in your GeoJSON data
