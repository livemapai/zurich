# Phase 6: Polish & Optimization

## Context
This final phase adds UI polish, loading states, performance optimizations, and documentation. It completes the project for a production-ready state.

## Prerequisites
- Phase 5 completed (rendering working)
- Buildings and minimap visible
- `pnpm type-check` passes

## Tasks

### Task 6.1: Create Loading Screen Component
**Goal:** Create a polished loading screen with progress.

**Create file:** `src/components/Loading/LoadingScreen.tsx`
```typescript
/**
 * LoadingScreen - Full-screen loading overlay
 *
 * Shows progress bar and status messages during data loading.
 */

interface LoadingScreenProps {
  progress: number;
  message?: string;
}

export function LoadingScreen({ progress, message }: LoadingScreenProps) {
  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(to bottom, #1a1a2e 0%, #16213e 100%)',
        zIndex: 1000,
      }}
    >
      {/* Title */}
      <h1
        style={{
          fontSize: '2.5rem',
          fontWeight: 300,
          letterSpacing: '0.1em',
          marginBottom: '2rem',
          color: '#ffffff',
        }}
      >
        ZURICH 3D
      </h1>

      {/* Progress bar container */}
      <div
        style={{
          width: '300px',
          height: '4px',
          background: 'rgba(255, 255, 255, 0.1)',
          borderRadius: '2px',
          overflow: 'hidden',
        }}
      >
        {/* Progress bar fill */}
        <div
          style={{
            width: `${progress}%`,
            height: '100%',
            background: 'linear-gradient(90deg, #4a9eff 0%, #00d4ff 100%)',
            borderRadius: '2px',
            transition: 'width 0.3s ease',
          }}
        />
      </div>

      {/* Progress text */}
      <p
        style={{
          marginTop: '1rem',
          fontSize: '0.875rem',
          color: 'rgba(255, 255, 255, 0.6)',
        }}
      >
        {message ?? `Loading... ${progress.toFixed(0)}%`}
      </p>

      {/* Tip */}
      <p
        style={{
          position: 'absolute',
          bottom: '2rem',
          fontSize: '0.75rem',
          color: 'rgba(255, 255, 255, 0.4)',
        }}
      >
        Tip: Use WASD to move, mouse to look around
      </p>
    </div>
  );
}
```

**Verification:**
- [ ] File exists at `src/components/Loading/LoadingScreen.tsx`

---

### Task 6.2: Create Loading Index
**Goal:** Create barrel export for Loading.

**Create file:** `src/components/Loading/index.ts`
```typescript
export { LoadingScreen } from './LoadingScreen';
```

**Verification:**
- [ ] File exists at `src/components/Loading/index.ts`

---

### Task 6.3: Create Controls Overlay Component
**Goal:** Create a polished controls hint overlay.

**Create file:** `src/components/Controls/ControlsOverlay.tsx`
```typescript
/**
 * ControlsOverlay - Shows keyboard and mouse controls
 */

interface ControlsOverlayProps {
  isLocked: boolean;
  showMinimap: boolean;
}

export function ControlsOverlay({ isLocked, showMinimap }: ControlsOverlayProps) {
  if (!isLocked) {
    return (
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          textAlign: 'center',
          color: 'white',
          pointerEvents: 'none',
        }}
      >
        <p style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>
          Click to start exploring
        </p>
        <p style={{ fontSize: '0.875rem', opacity: 0.7 }}>
          Use WASD to move, mouse to look around
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        position: 'absolute',
        bottom: '20px',
        left: '20px',
        padding: '12px 16px',
        background: 'rgba(0, 0, 0, 0.6)',
        borderRadius: '8px',
        fontSize: '0.8rem',
        color: 'rgba(255, 255, 255, 0.9)',
        lineHeight: 1.6,
        backdropFilter: 'blur(4px)',
      }}
    >
      <div style={{ display: 'flex', gap: '24px' }}>
        <div>
          <ControlRow keys={['W', 'A', 'S', 'D']} label="Move" />
          <ControlRow keys={['Shift']} label="Run" />
        </div>
        <div>
          <ControlRow keys={['Mouse']} label="Look" />
          <ControlRow keys={['M']} label={showMinimap ? 'Hide map' : 'Show map'} />
          <ControlRow keys={['Esc']} label="Release" />
        </div>
      </div>
    </div>
  );
}

function ControlRow({ keys, label }: { keys: string[]; label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
      <div style={{ display: 'flex', gap: '2px' }}>
        {keys.map((key) => (
          <kbd
            key={key}
            style={{
              display: 'inline-block',
              padding: '2px 6px',
              background: 'rgba(255, 255, 255, 0.15)',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              borderRadius: '4px',
              fontSize: '0.7rem',
              fontFamily: 'monospace',
              minWidth: '20px',
              textAlign: 'center',
            }}
          >
            {key}
          </kbd>
        ))}
      </div>
      <span style={{ opacity: 0.8 }}>{label}</span>
    </div>
  );
}
```

**Verification:**
- [ ] File exists at `src/components/Controls/ControlsOverlay.tsx`

---

### Task 6.4: Create Crosshair Component
**Goal:** Create a styled crosshair component.

**Create file:** `src/components/Controls/Crosshair.tsx`
```typescript
/**
 * Crosshair - Center screen reticle
 */

interface CrosshairProps {
  size?: number;
  color?: string;
  thickness?: number;
  gap?: number;
}

export function Crosshair({
  size = 20,
  color = 'rgba(255, 255, 255, 0.7)',
  thickness = 2,
  gap = 4,
}: CrosshairProps) {
  const halfSize = size / 2;
  const lineLength = halfSize - gap;

  return (
    <div
      style={{
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        width: size,
        height: size,
        pointerEvents: 'none',
      }}
    >
      {/* Top */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: '50%',
          transform: 'translateX(-50%)',
          width: thickness,
          height: lineLength,
          background: color,
        }}
      />
      {/* Bottom */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: '50%',
          transform: 'translateX(-50%)',
          width: thickness,
          height: lineLength,
          background: color,
        }}
      />
      {/* Left */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: '50%',
          transform: 'translateY(-50%)',
          width: lineLength,
          height: thickness,
          background: color,
        }}
      />
      {/* Right */}
      <div
        style={{
          position: 'absolute',
          right: 0,
          top: '50%',
          transform: 'translateY(-50%)',
          width: lineLength,
          height: thickness,
          background: color,
        }}
      />
      {/* Center dot */}
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: thickness,
          height: thickness,
          background: color,
          borderRadius: '50%',
        }}
      />
    </div>
  );
}
```

**Verification:**
- [ ] File exists at `src/components/Controls/Crosshair.tsx`

---

### Task 6.5: Create Controls Index
**Goal:** Create barrel export for Controls.

**Create file:** `src/components/Controls/index.ts`
```typescript
export { ControlsOverlay } from './ControlsOverlay';
export { Crosshair } from './Crosshair';
```

**Verification:**
- [ ] File exists at `src/components/Controls/index.ts`

---

### Task 6.6: Create Components Index
**Goal:** Create barrel export for all components.

**Create file:** `src/components/index.ts`
```typescript
export { ZurichViewer } from './ZurichViewer';
export { Minimap } from './Minimap';
export { LoadingScreen } from './Loading';
export { ControlsOverlay, Crosshair } from './Controls';
```

**Verification:**
- [ ] File exists at `src/components/index.ts`

---

### Task 6.7: Update App with Polish
**Goal:** Integrate polished components into App.

**Update file:** `src/App.tsx`
```typescript
import { useState, useCallback } from 'react';
import { ZurichViewer, LoadingScreen } from './components';

function App() {
  const [isLoading, setIsLoading] = useState(true);
  const [loadProgress, setLoadProgress] = useState(0);
  const [loadMessage, setLoadMessage] = useState('Initializing...');
  const [error, setError] = useState<Error | null>(null);

  const handleLoadProgress = useCallback((progress: number) => {
    setLoadProgress(progress);

    // Update message based on progress
    if (progress < 20) {
      setLoadMessage('Connecting...');
    } else if (progress < 50) {
      setLoadMessage('Loading buildings...');
    } else if (progress < 80) {
      setLoadMessage('Processing geometry...');
    } else if (progress < 100) {
      setLoadMessage('Preparing scene...');
    } else {
      setLoadMessage('Ready!');
      // Short delay before hiding loading screen
      setTimeout(() => setIsLoading(false), 500);
    }
  }, []);

  const handleError = useCallback((err: Error) => {
    console.error('Application error:', err);
    setError(err);
    setIsLoading(false);
  }, []);

  if (error) {
    return (
      <div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#1a1a2e',
          color: 'white',
        }}
      >
        <h1 style={{ fontSize: '1.5rem', marginBottom: '1rem', color: '#ff6b6b' }}>
          Error
        </h1>
        <p style={{ marginBottom: '1.5rem', opacity: 0.8, maxWidth: '400px', textAlign: 'center' }}>
          {error.message}
        </p>
        <button
          onClick={() => window.location.reload()}
          style={{
            padding: '10px 24px',
            background: '#4a9eff',
            border: 'none',
            borderRadius: '6px',
            color: 'white',
            fontSize: '1rem',
            cursor: 'pointer',
            transition: 'background 0.2s',
          }}
          onMouseOver={(e) => (e.currentTarget.style.background = '#3a8eef')}
          onMouseOut={(e) => (e.currentTarget.style.background = '#4a9eff')}
        >
          Reload
        </button>
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height: '100%', overflow: 'hidden' }}>
      {/* Loading overlay */}
      {isLoading && (
        <LoadingScreen progress={loadProgress} message={loadMessage} />
      )}

      {/* Main viewer (renders in background during load) */}
      <ZurichViewer onLoadProgress={handleLoadProgress} onError={handleError} />
    </div>
  );
}

export default App;
```

**Verification:**
- [ ] File updated at `src/App.tsx`

---

### Task 6.8: Final ZurichViewer Update with Polished Components
**Goal:** Use polished Crosshair and ControlsOverlay components.

**Update file:** `src/components/ZurichViewer/ZurichViewer.tsx`

Replace the crosshair and controls-hint divs with:
```typescript
import { Crosshair, ControlsOverlay } from '@/components/Controls';

// ... in the return JSX, replace:

{/* Crosshair */}
{isReady && isLocked && <Crosshair />}

{/* Controls overlay */}
{isReady && <ControlsOverlay isLocked={isLocked} showMinimap={showMinimap} />}
```

**Verification:**
- [ ] File updated at `src/components/ZurichViewer/ZurichViewer.tsx`

---

### Task 6.9: Create Test File for SpatialIndex
**Goal:** Add unit tests for collision detection.

**Create file:** `src/systems/SpatialIndex.test.ts`
```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { SpatialIndex } from './SpatialIndex';
import type { BuildingFeature } from '@/types';

describe('SpatialIndex', () => {
  let index: SpatialIndex;

  beforeEach(() => {
    index = new SpatialIndex();
  });

  it('should start empty', () => {
    expect(index.loaded).toBe(false);
  });

  it('should load buildings', () => {
    const buildings: BuildingFeature[] = [
      createSquareBuilding(8.54, 47.38, 0.001, 10),
    ];

    index.load(buildings);
    expect(index.loaded).toBe(true);
  });

  it('should detect collision inside building', () => {
    const buildings: BuildingFeature[] = [
      createSquareBuilding(8.54, 47.38, 0.001, 10),
    ];

    index.load(buildings);

    // Point inside building
    const result = index.checkCollision(8.54, 47.38);
    expect(result.collides).toBe(true);
    expect(result.building).toBeDefined();
  });

  it('should not detect collision outside building', () => {
    const buildings: BuildingFeature[] = [
      createSquareBuilding(8.54, 47.38, 0.001, 10),
    ];

    index.load(buildings);

    // Point outside building
    const result = index.checkCollision(8.55, 47.39);
    expect(result.collides).toBe(false);
  });

  it('should return wall normal on collision', () => {
    const buildings: BuildingFeature[] = [
      createSquareBuilding(8.54, 47.38, 0.001, 10),
    ];

    index.load(buildings);

    const result = index.checkCollision(8.54, 47.38);
    expect(result.collides).toBe(true);
    expect(result.normal).toBeDefined();
    expect(result.normal?.x).not.toBeNaN();
    expect(result.normal?.y).not.toBeNaN();
  });

  it('should clear index', () => {
    const buildings: BuildingFeature[] = [
      createSquareBuilding(8.54, 47.38, 0.001, 10),
    ];

    index.load(buildings);
    expect(index.loaded).toBe(true);

    index.clear();
    expect(index.loaded).toBe(false);
  });
});

// Helper to create a square building
function createSquareBuilding(
  lng: number,
  lat: number,
  size: number,
  height: number
): BuildingFeature {
  const half = size / 2;
  return {
    type: 'Feature',
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          [lng - half, lat - half],
          [lng + half, lat - half],
          [lng + half, lat + half],
          [lng - half, lat + half],
          [lng - half, lat - half],
        ],
      ],
    },
    properties: {
      id: 'test-building',
      height,
      baseElevation: 400,
    },
  };
}
```

**Verification:**
- [ ] File exists at `src/systems/SpatialIndex.test.ts`

---

### Task 6.10: Create Vitest Configuration
**Goal:** Configure Vitest for testing.

**Create file:** `vitest.config.ts`
```typescript
import { defineConfig } from 'vitest/config';
import { resolve } from 'path';

export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
    },
  },
});
```

**Verification:**
- [ ] File exists at `vitest.config.ts`

---

## Verification Checklist

After completing all tasks:

- [ ] `src/components/Loading/LoadingScreen.tsx` exists
- [ ] `src/components/Loading/index.ts` exists
- [ ] `src/components/Controls/ControlsOverlay.tsx` exists
- [ ] `src/components/Controls/Crosshair.tsx` exists
- [ ] `src/components/Controls/index.ts` exists
- [ ] `src/components/index.ts` exists
- [ ] `src/App.tsx` updated
- [ ] `src/components/ZurichViewer/ZurichViewer.tsx` updated
- [ ] `src/systems/SpatialIndex.test.ts` exists
- [ ] `vitest.config.ts` exists
- [ ] `pnpm type-check` passes
- [ ] `pnpm test` passes

## Type Check and Test Commands
```bash
cd /Users/claudioromano/Documents/livemap/zuri-3d
pnpm type-check
pnpm test
```

## Files Created

```
src/
├── components/
│   ├── Loading/
│   │   ├── LoadingScreen.tsx
│   │   └── index.ts
│   ├── Controls/
│   │   ├── ControlsOverlay.tsx
│   │   ├── Crosshair.tsx
│   │   └── index.ts
│   └── index.ts
├── systems/
│   └── SpatialIndex.test.ts
├── App.tsx (updated)
└── components/ZurichViewer/ZurichViewer.tsx (updated)
vitest.config.ts
```

## Project Complete!

After Phase 6, the project includes:

### Features
- 3D walkable Zurich with 50k+ buildings
- First-person WASD + mouse controls
- Collision detection with wall sliding
- Terrain-locked altitude
- Navigation minimap
- Polished loading screen
- Controls overlay

### Technical
- TypeScript strict mode
- React 19 + deck.gl v9
- RBush spatial indexing
- requestAnimationFrame game loop
- Pointer Lock API for mouse capture
- Unit tests for critical systems

### Code Quality
- Type-safe throughout
- Barrel exports for clean imports
- Documented with JSDoc
- Tested with Vitest

## Final Project Structure

```
/Users/claudioromano/Documents/livemap/zuri-3d/
├── .claude/
│   ├── plans/phases/          # Executable phase instructions
│   └── skills/                # Claude Code skills
├── docs/                      # Reference documentation
├── scripts/                   # Data pipeline (Python)
├── src/
│   ├── components/           # React components
│   │   ├── ZurichViewer/
│   │   ├── Minimap/
│   │   ├── Loading/
│   │   └── Controls/
│   ├── hooks/                # React hooks
│   ├── systems/              # Game systems
│   ├── layers/               # deck.gl layers
│   ├── lib/                  # Config and data
│   ├── types/                # TypeScript types
│   ├── utils/                # Utilities
│   └── styles/               # CSS
├── public/data/              # GeoJSON data
├── CLAUDE.md
├── package.json
├── tsconfig.json
├── vite.config.ts
└── vitest.config.ts
```
