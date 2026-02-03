# Phase 3: Core Application

## Context
This phase creates the React application shell with deck.gl FirstPersonView. It establishes the foundational component structure without movement controls (those come in Phase 4).

## Prerequisites
- Phase 0 completed (dependencies installed)
- Phase 2 completed (sample data available)
- `pnpm install` completed

## Tasks

### Task 3.1: Create Vitest Configuration
**Goal:** Configure Vitest for unit testing with React and WebGL mocking.

**Create file:** `vitest.config.ts`
```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
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

### Task 3.2: Create Test Setup
**Goal:** Set up test environment with WebGL mocks and testing utilities.

**Create file:** `src/test/setup.ts`
```typescript
import { vi } from 'vitest';
import '@testing-library/jest-dom/vitest';

// Mock WebGL context
HTMLCanvasElement.prototype.getContext = vi.fn((type) => {
  if (type === 'webgl' || type === 'webgl2') {
    return {
      canvas: { width: 800, height: 600 },
      getExtension: vi.fn(),
      createShader: vi.fn(),
      createProgram: vi.fn(),
      getAttribLocation: vi.fn(),
      getUniformLocation: vi.fn(),
      enable: vi.fn(),
      disable: vi.fn(),
      viewport: vi.fn(),
      clearColor: vi.fn(),
      clear: vi.fn(),
    } as unknown as WebGLRenderingContext;
  }
  return null;
}) as typeof HTMLCanvasElement.prototype.getContext;

// Mock requestAnimationFrame
global.requestAnimationFrame = vi.fn((cb) => setTimeout(cb, 16) as unknown as number);
global.cancelAnimationFrame = vi.fn((id) => clearTimeout(id));

// Mock ResizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});
```

**Verification:**
- [ ] File exists at `src/test/setup.ts`

---

### Task 3.3: Create React Entry Point
**Goal:** Create the main React entry point that renders the app.

**Create file:** `src/main.tsx`
```typescript
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles/globals.css';

const container = document.getElementById('root');

if (!container) {
  throw new Error('Root element not found');
}

const root = createRoot(container);

root.render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

**Verification:**
- [ ] File exists at `src/main.tsx`

---

### Task 3.4: Create Global Styles
**Goal:** Set up base CSS for full-screen viewport.

**Create file:** `src/styles/globals.css`
```css
/* Reset and base styles */
*,
*::before,
*::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html,
body {
  width: 100%;
  height: 100%;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen,
    Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
  background-color: #1a1a2e;
  color: #ffffff;
}

#root {
  width: 100%;
  height: 100%;
}

/* Utility classes */
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* Prevent text selection during interaction */
.no-select {
  user-select: none;
  -webkit-user-select: none;
}

/* Full viewport container */
.viewport {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

/* Loading overlay */
.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background-color: #1a1a2e;
  z-index: 100;
}

.loading-text {
  font-size: 1.5rem;
  margin-bottom: 1rem;
}

.loading-progress {
  width: 200px;
  height: 4px;
  background-color: #333;
  border-radius: 2px;
  overflow: hidden;
}

.loading-progress-bar {
  height: 100%;
  background-color: #4a9eff;
  transition: width 0.3s ease;
}

/* HUD overlay */
.hud {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 10;
}

.hud > * {
  pointer-events: auto;
}

/* Crosshair */
.crosshair {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 20px;
  height: 20px;
  pointer-events: none;
}

.crosshair::before,
.crosshair::after {
  content: '';
  position: absolute;
  background-color: rgba(255, 255, 255, 0.7);
}

.crosshair::before {
  top: 50%;
  left: 0;
  right: 0;
  height: 2px;
  transform: translateY(-50%);
}

.crosshair::after {
  left: 50%;
  top: 0;
  bottom: 0;
  width: 2px;
  transform: translateX(-50%);
}

/* Controls hint */
.controls-hint {
  position: absolute;
  bottom: 20px;
  left: 20px;
  padding: 12px 16px;
  background-color: rgba(0, 0, 0, 0.7);
  border-radius: 8px;
  font-size: 0.875rem;
  line-height: 1.5;
}

.controls-hint kbd {
  display: inline-block;
  padding: 2px 6px;
  margin: 0 2px;
  background-color: #333;
  border: 1px solid #555;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.75rem;
}

/* Debug info */
.debug-panel {
  position: absolute;
  top: 10px;
  right: 10px;
  padding: 10px;
  background-color: rgba(0, 0, 0, 0.7);
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.75rem;
}

.debug-panel p {
  margin: 2px 0;
}
```

**Verification:**
- [ ] File exists at `src/styles/globals.css`

---

### Task 3.5: Create Configuration
**Goal:** Centralize game and rendering settings.

**Create file:** `src/lib/config.ts`
```typescript
/**
 * Application configuration
 *
 * Centralized settings for the 3D viewer
 */

export const CONFIG = {
  /** Rendering settings */
  render: {
    /** Vertical field of view in degrees */
    fov: 75,
    /** Near clipping plane in meters */
    near: 0.1,
    /** Far clipping plane in meters */
    far: 10000,
    /** Target frame rate */
    targetFps: 60,
  },

  /** Player settings */
  player: {
    /** Total height in meters */
    height: 1.8,
    /** Camera/eye height from ground */
    eyeHeight: 1.7,
    /** Collision radius in meters */
    collisionRadius: 0.3,
    /** Maximum step-up height in meters */
    stepHeight: 0.3,
  },

  /** Movement speeds in meters per second */
  movement: {
    walk: 4.0,
    run: 8.0,
    /** Keyboard turn rate in degrees per second */
    turnRate: 90,
  },

  /** Mouse sensitivity (degrees per pixel) */
  mouse: {
    sensitivityX: 0.1,
    sensitivityY: 0.1,
    /** Invert Y axis */
    invertY: false,
  },

  /** Camera constraints */
  camera: {
    /** Minimum pitch angle (looking down) */
    pitchMin: -89,
    /** Maximum pitch angle (looking up) */
    pitchMax: 89,
    /** Minimum altitude above ground */
    minAltitude: 0.5,
  },

  /** Data paths */
  data: {
    buildings: '/data/zurich-buildings.geojson',
    terrain: '/data/terrain.png',
    tileIndex: '/data/tiles/buildings/tile-index.json',
  },

  /** Debug settings */
  debug: {
    /** Show debug panel */
    showDebugPanel: import.meta.env.DEV,
    /** Log performance metrics */
    logPerformance: false,
  },
} as const;

/** Type for the config object */
export type Config = typeof CONFIG;
```

**Verification:**
- [ ] File exists at `src/lib/config.ts`

---

### Task 3.6: Create Constants
**Goal:** Re-export Zurich constants from types and add coordinate utilities.

**Create file:** `src/lib/constants.ts`
```typescript
/**
 * Zurich-specific constants and coordinate utilities
 *
 * Re-exports core constants from @/types (single source of truth)
 * and adds utility functions for coordinate conversions.
 */

// Re-export core constants from types (single source of truth)
export { ZURICH_CENTER, ZURICH_BOUNDS, METERS_PER_DEGREE } from '@/types';

// Import for local use
import { ZURICH_CENTER, METERS_PER_DEGREE } from '@/types';

/** Default starting position (Zurich main station area) */
export const DEFAULT_POSITION: [number, number, number] = [
  ZURICH_CENTER.lng,
  ZURICH_CENTER.lat,
  410, // Zurich elevation ~408m + eye height
];

/** Conversion factor: degrees to radians */
export const DEG_TO_RAD = Math.PI / 180;

/** Conversion factor: radians to degrees */
export const RAD_TO_DEG = 180 / Math.PI;

/**
 * Convert meters to degrees longitude at Zurich latitude
 */
export function metersToDegreesLng(meters: number): number {
  return meters / METERS_PER_DEGREE.lng;
}

/**
 * Convert meters to degrees latitude
 */
export function metersToDegreesLat(meters: number): number {
  return meters / METERS_PER_DEGREE.lat;
}

/**
 * Convert degrees longitude to meters at Zurich latitude
 */
export function degreesLngToMeters(degrees: number): number {
  return degrees * METERS_PER_DEGREE.lng;
}

/**
 * Convert degrees latitude to meters
 */
export function degreesLatToMeters(degrees: number): number {
  return degrees * METERS_PER_DEGREE.lat;
}

/**
 * Clamp a value between min and max
 */
export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

/**
 * Linear interpolation between two values
 */
export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/**
 * Normalize an angle to [0, 360) range
 */
export function normalizeAngle(degrees: number): number {
  return ((degrees % 360) + 360) % 360;
}
```

**Verification:**
- [ ] File exists at `src/lib/constants.ts`

---

### Task 3.7: Create App Component
**Goal:** Create the main App component that hosts the viewer.

**Create file:** `src/App.tsx`
```typescript
import { useState } from 'react';
import { ZurichViewer } from './components/ZurichViewer';
import { CONFIG } from './lib/config';

function App() {
  const [isLoading, setIsLoading] = useState(true);
  const [loadProgress, setLoadProgress] = useState(0);
  const [error, setError] = useState<Error | null>(null);

  const handleLoadProgress = (progress: number) => {
    setLoadProgress(progress);
    if (progress >= 100) {
      setIsLoading(false);
    }
  };

  const handleError = (err: Error) => {
    console.error('Viewer error:', err);
    setError(err);
    setIsLoading(false);
  };

  if (error) {
    return (
      <div className="viewport" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', padding: '2rem' }}>
          <h1 style={{ marginBottom: '1rem', color: '#ff6b6b' }}>Error</h1>
          <p style={{ marginBottom: '1rem' }}>{error.message}</p>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '0.5rem 1rem',
              background: '#4a9eff',
              border: 'none',
              borderRadius: '4px',
              color: 'white',
              cursor: 'pointer',
            }}
          >
            Reload
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="viewport no-select">
      {/* Loading overlay */}
      {isLoading && (
        <div className="loading-overlay">
          <p className="loading-text">Loading Zurich 3D...</p>
          <div className="loading-progress">
            <div
              className="loading-progress-bar"
              style={{ width: `${loadProgress}%` }}
            />
          </div>
          <p style={{ marginTop: '0.5rem', fontSize: '0.875rem', opacity: 0.7 }}>
            {loadProgress.toFixed(0)}%
          </p>
        </div>
      )}

      {/* Main viewer */}
      <ZurichViewer
        onLoadProgress={handleLoadProgress}
        onError={handleError}
      />

      {/* Debug panel (dev only) */}
      {CONFIG.debug.showDebugPanel && !isLoading && (
        <div className="debug-panel">
          <p>Debug Mode</p>
        </div>
      )}
    </div>
  );
}

export default App;
```

**Verification:**
- [ ] File exists at `src/App.tsx`

---

### Task 3.8: Create ZurichViewer Component
**Goal:** Create the main deck.gl viewer component with FirstPersonView.

**Create file:** `src/components/ZurichViewer/ZurichViewer.tsx`
```typescript
import { useState, useRef, useEffect, useCallback } from 'react';
import DeckGL from '@deck.gl/react';
import { FirstPersonView } from '@deck.gl/core';
import type { FirstPersonViewState } from '@/types';
import { CONFIG } from '@/lib/config';
import { DEFAULT_POSITION } from '@/lib/constants';

interface ZurichViewerProps {
  onLoadProgress?: (progress: number) => void;
  onError?: (error: Error) => void;
}

/**
 * Initial view state - centered on Zurich
 */
const INITIAL_VIEW_STATE: FirstPersonViewState = {
  position: DEFAULT_POSITION,
  bearing: 0,    // Facing North
  pitch: 0,      // Level
  fov: CONFIG.render.fov,
  near: CONFIG.render.near,
  far: CONFIG.render.far,
};

/**
 * ZurichViewer - Main 3D viewer component
 *
 * Uses deck.gl FirstPersonView for walkthrough navigation.
 * This component sets up the view but does not handle controls
 * (those are added in Phase 4).
 */
export function ZurichViewer({ onLoadProgress, onError }: ZurichViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [viewState, setViewState] = useState<FirstPersonViewState>(INITIAL_VIEW_STATE);
  const [isReady, setIsReady] = useState(false);

  // FirstPersonView configuration
  const view = new FirstPersonView({
    id: 'first-person',
    // Disable built-in controller - we'll add custom controls in Phase 4
    controller: false,
    // Vertical field of view
    fovy: viewState.fov ?? CONFIG.render.fov,
    // Clipping planes
    near: viewState.near ?? CONFIG.render.near,
    far: viewState.far ?? CONFIG.render.far,
  });

  // Handle view state changes (for future controller integration)
  const handleViewStateChange = useCallback(
    ({ viewState: newViewState }: { viewState: FirstPersonViewState }) => {
      setViewState(newViewState);
    },
    []
  );

  // Simulate initial load (will be replaced with actual data loading)
  useEffect(() => {
    let progress = 0;
    const interval = setInterval(() => {
      progress += 10;
      onLoadProgress?.(Math.min(progress, 100));

      if (progress >= 100) {
        clearInterval(interval);
        setIsReady(true);
      }
    }, 100);

    return () => clearInterval(interval);
  }, [onLoadProgress]);

  // Handle WebGL context loss
  const handleWebGLContextLost = useCallback(() => {
    onError?.(new Error('WebGL context lost. Please refresh the page.'));
  }, [onError]);

  // No layers yet - will be added in Phase 5
  const layers: never[] = [];

  return (
    <div
      ref={containerRef}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        cursor: isReady ? 'crosshair' : 'wait',
      }}
    >
      <DeckGL
        views={view}
        viewState={viewState}
        onViewStateChange={handleViewStateChange}
        controller={false}
        layers={layers}
        onWebGLInitialized={() => {
          console.log('WebGL initialized');
        }}
        onError={(error) => {
          console.error('DeckGL error:', error);
          onError?.(error instanceof Error ? error : new Error(String(error)));
        }}
        // Background color (will be hidden by terrain)
        style={{ background: '#16213e' }}
      />

      {/* Crosshair - shown when ready */}
      {isReady && <div className="crosshair" />}

      {/* Controls hint - will be expanded in Phase 4 */}
      {isReady && (
        <div className="controls-hint">
          <p>Controls coming in Phase 4</p>
          <p>
            <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> Move
          </p>
          <p>
            <kbd>Mouse</kbd> Look around (click to lock)
          </p>
        </div>
      )}
    </div>
  );
}
```

**Verification:**
- [ ] File exists at `src/components/ZurichViewer/ZurichViewer.tsx`

---

### Task 3.9: Create ZurichViewer Index Export
**Goal:** Create barrel export for the component.

**Create file:** `src/components/ZurichViewer/index.ts`
```typescript
export { ZurichViewer } from './ZurichViewer';
```

**Verification:**
- [ ] File exists at `src/components/ZurichViewer/index.ts`

---

### Task 3.10: Create Lib Index
**Goal:** Create barrel export for lib utilities.

**Create file:** `src/lib/index.ts`
```typescript
export { CONFIG } from './config';
export * from './constants';
```

**Verification:**
- [ ] File exists at `src/lib/index.ts`

---

### Task 3.11: Update Types with Vite Env
**Goal:** Add Vite environment type declarations.

**Create file:** `src/vite-env.d.ts`
```typescript
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly DEV: boolean;
  readonly PROD: boolean;
  readonly MODE: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

**Verification:**
- [ ] File exists at `src/vite-env.d.ts`

---

### Task 3.12: Create Constants Unit Tests
**Goal:** Test coordinate conversion functions and utility functions.

**Create file:** `src/lib/constants.test.ts`
```typescript
import { describe, it, expect } from 'vitest';
import {
  ZURICH_CENTER,
  ZURICH_BOUNDS,
  METERS_PER_DEGREE,
  DEFAULT_POSITION,
  DEG_TO_RAD,
  RAD_TO_DEG,
  metersToDegreesLng,
  metersToDegreesLat,
  degreesLngToMeters,
  degreesLatToMeters,
  clamp,
  lerp,
  normalizeAngle,
} from './constants';

describe('constants', () => {
  describe('ZURICH_CENTER', () => {
    it('should be valid WGS84 coordinates', () => {
      expect(ZURICH_CENTER.lng).toBeGreaterThan(8);
      expect(ZURICH_CENTER.lng).toBeLessThan(9);
      expect(ZURICH_CENTER.lat).toBeGreaterThan(47);
      expect(ZURICH_CENTER.lat).toBeLessThan(48);
    });
  });

  describe('ZURICH_BOUNDS', () => {
    it('should contain ZURICH_CENTER', () => {
      expect(ZURICH_CENTER.lng).toBeGreaterThan(ZURICH_BOUNDS.minLng);
      expect(ZURICH_CENTER.lng).toBeLessThan(ZURICH_BOUNDS.maxLng);
      expect(ZURICH_CENTER.lat).toBeGreaterThan(ZURICH_BOUNDS.minLat);
      expect(ZURICH_CENTER.lat).toBeLessThan(ZURICH_BOUNDS.maxLat);
    });
  });

  describe('METERS_PER_DEGREE', () => {
    it('should have realistic values for ~47°N latitude', () => {
      // At 47°N, 1 degree longitude ≈ 75,500m
      expect(METERS_PER_DEGREE.lng).toBeGreaterThan(70000);
      expect(METERS_PER_DEGREE.lng).toBeLessThan(80000);
      // 1 degree latitude ≈ 111,320m
      expect(METERS_PER_DEGREE.lat).toBeGreaterThan(110000);
      expect(METERS_PER_DEGREE.lat).toBeLessThan(112000);
    });
  });

  describe('DEFAULT_POSITION', () => {
    it('should be a valid 3D position', () => {
      expect(DEFAULT_POSITION).toHaveLength(3);
      expect(DEFAULT_POSITION[0]).toBe(ZURICH_CENTER.lng);
      expect(DEFAULT_POSITION[1]).toBe(ZURICH_CENTER.lat);
      expect(DEFAULT_POSITION[2]).toBeGreaterThan(400); // Zurich altitude
    });
  });
});

describe('coordinate conversion', () => {
  describe('metersToDegreesLng', () => {
    it('should convert meters to degrees', () => {
      const meters = METERS_PER_DEGREE.lng;
      expect(metersToDegreesLng(meters)).toBeCloseTo(1, 5);
    });

    it('should handle zero', () => {
      expect(metersToDegreesLng(0)).toBe(0);
    });
  });

  describe('metersToDegreesLat', () => {
    it('should convert meters to degrees', () => {
      const meters = METERS_PER_DEGREE.lat;
      expect(metersToDegreesLat(meters)).toBeCloseTo(1, 5);
    });
  });

  describe('degreesLngToMeters', () => {
    it('should be inverse of metersToDegreesLng', () => {
      const meters = 1000;
      const degrees = metersToDegreesLng(meters);
      expect(degreesLngToMeters(degrees)).toBeCloseTo(meters, 5);
    });
  });

  describe('degreesLatToMeters', () => {
    it('should be inverse of metersToDegreesLat', () => {
      const meters = 1000;
      const degrees = metersToDegreesLat(meters);
      expect(degreesLatToMeters(degrees)).toBeCloseTo(meters, 5);
    });
  });
});

describe('utility functions', () => {
  describe('clamp', () => {
    it('should clamp values within range', () => {
      expect(clamp(5, 0, 10)).toBe(5);
      expect(clamp(-5, 0, 10)).toBe(0);
      expect(clamp(15, 0, 10)).toBe(10);
    });

    it('should handle edge cases', () => {
      expect(clamp(0, 0, 10)).toBe(0);
      expect(clamp(10, 0, 10)).toBe(10);
    });
  });

  describe('lerp', () => {
    it('should interpolate between values', () => {
      expect(lerp(0, 10, 0)).toBe(0);
      expect(lerp(0, 10, 1)).toBe(10);
      expect(lerp(0, 10, 0.5)).toBe(5);
    });

    it('should handle negative values', () => {
      expect(lerp(-10, 10, 0.5)).toBe(0);
    });
  });

  describe('normalizeAngle', () => {
    it('should normalize angles to [0, 360)', () => {
      expect(normalizeAngle(0)).toBe(0);
      expect(normalizeAngle(90)).toBe(90);
      expect(normalizeAngle(360)).toBe(0);
      expect(normalizeAngle(450)).toBe(90);
      expect(normalizeAngle(-90)).toBe(270);
      expect(normalizeAngle(-360)).toBe(0);
    });
  });

  describe('DEG_TO_RAD and RAD_TO_DEG', () => {
    it('should be inverses', () => {
      expect(DEG_TO_RAD * RAD_TO_DEG).toBeCloseTo(1, 10);
    });

    it('should convert correctly', () => {
      expect(180 * DEG_TO_RAD).toBeCloseTo(Math.PI, 10);
      expect(Math.PI * RAD_TO_DEG).toBeCloseTo(180, 10);
    });
  });
});
```

**Verification:**
- [ ] File exists at `src/lib/constants.test.ts`

---

### Task 3.13: Create Config Unit Tests
**Goal:** Test configuration structure and validate settings.

**Create file:** `src/lib/config.test.ts`
```typescript
import { describe, it, expect } from 'vitest';
import { CONFIG } from './config';

describe('CONFIG', () => {
  describe('render settings', () => {
    it('should have valid FOV', () => {
      expect(CONFIG.render.fov).toBeGreaterThan(30);
      expect(CONFIG.render.fov).toBeLessThan(120);
    });

    it('should have valid clipping planes', () => {
      expect(CONFIG.render.near).toBeGreaterThan(0);
      expect(CONFIG.render.near).toBeLessThan(1);
      expect(CONFIG.render.far).toBeGreaterThan(1000);
    });

    it('should have reasonable frame rate target', () => {
      expect(CONFIG.render.targetFps).toBeGreaterThanOrEqual(30);
      expect(CONFIG.render.targetFps).toBeLessThanOrEqual(144);
    });
  });

  describe('player settings', () => {
    it('should have realistic human dimensions', () => {
      expect(CONFIG.player.height).toBeGreaterThan(1.5);
      expect(CONFIG.player.height).toBeLessThan(2.2);
      expect(CONFIG.player.eyeHeight).toBeLessThan(CONFIG.player.height);
      expect(CONFIG.player.eyeHeight).toBeGreaterThan(1.4);
    });

    it('should have reasonable collision radius', () => {
      expect(CONFIG.player.collisionRadius).toBeGreaterThan(0.1);
      expect(CONFIG.player.collisionRadius).toBeLessThan(0.5);
    });

    it('should have reasonable step height', () => {
      expect(CONFIG.player.stepHeight).toBeGreaterThan(0.1);
      expect(CONFIG.player.stepHeight).toBeLessThan(0.5);
    });
  });

  describe('movement settings', () => {
    it('should have realistic walking speed', () => {
      // Average human walking speed: 1.4 m/s, fast walk: 2-3 m/s
      expect(CONFIG.movement.walk).toBeGreaterThan(1);
      expect(CONFIG.movement.walk).toBeLessThan(10);
    });

    it('should have run speed faster than walk', () => {
      expect(CONFIG.movement.run).toBeGreaterThan(CONFIG.movement.walk);
    });
  });

  describe('mouse settings', () => {
    it('should have reasonable sensitivity', () => {
      expect(CONFIG.mouse.sensitivityX).toBeGreaterThan(0);
      expect(CONFIG.mouse.sensitivityX).toBeLessThan(1);
      expect(CONFIG.mouse.sensitivityY).toBeGreaterThan(0);
      expect(CONFIG.mouse.sensitivityY).toBeLessThan(1);
    });

    it('should have invertY as boolean', () => {
      expect(typeof CONFIG.mouse.invertY).toBe('boolean');
    });
  });

  describe('camera settings', () => {
    it('should have valid pitch limits', () => {
      expect(CONFIG.camera.pitchMin).toBeLessThan(0);
      expect(CONFIG.camera.pitchMax).toBeGreaterThan(0);
      expect(CONFIG.camera.pitchMin).toBeGreaterThanOrEqual(-90);
      expect(CONFIG.camera.pitchMax).toBeLessThanOrEqual(90);
    });

    it('should have positive minimum altitude', () => {
      expect(CONFIG.camera.minAltitude).toBeGreaterThan(0);
    });
  });

  describe('data paths', () => {
    it('should have required data paths', () => {
      expect(CONFIG.data.buildings).toBeDefined();
      expect(CONFIG.data.terrain).toBeDefined();
      expect(typeof CONFIG.data.buildings).toBe('string');
      expect(typeof CONFIG.data.terrain).toBe('string');
    });
  });
});
```

**Verification:**
- [ ] File exists at `src/lib/config.test.ts`

---

### Task 3.14: Create ZurichViewer Unit Tests
**Goal:** Test component renders and handles callbacks.

**Create file:** `src/components/ZurichViewer/ZurichViewer.test.tsx`
```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { ZurichViewer } from './ZurichViewer';

// Mock deck.gl modules
vi.mock('@deck.gl/react', () => ({
  default: ({ children, onWebGLInitialized }: { children?: React.ReactNode; onWebGLInitialized?: () => void }) => {
    // Simulate WebGL initialization
    if (onWebGLInitialized) {
      setTimeout(onWebGLInitialized, 0);
    }
    return <div data-testid="deckgl-mock">{children}</div>;
  },
}));

vi.mock('@deck.gl/core', () => ({
  FirstPersonView: vi.fn().mockImplementation(() => ({
    id: 'first-person',
  })),
}));

describe('ZurichViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render without crashing', () => {
    const { container } = render(<ZurichViewer />);
    expect(container).toBeDefined();
  });

  it('should call onLoadProgress with increasing values', async () => {
    const onLoadProgress = vi.fn();
    render(<ZurichViewer onLoadProgress={onLoadProgress} />);

    await waitFor(() => {
      expect(onLoadProgress).toHaveBeenCalled();
    }, { timeout: 2000 });

    // Should receive progress updates
    const calls = onLoadProgress.mock.calls;
    expect(calls.length).toBeGreaterThan(0);

    // Progress values should increase
    const progressValues = calls.map(call => call[0] as number);
    for (let i = 1; i < progressValues.length; i++) {
      expect(progressValues[i]).toBeGreaterThanOrEqual(progressValues[i - 1]!);
    }
  });

  it('should call onLoadProgress with 100 when loading completes', async () => {
    const onLoadProgress = vi.fn();
    render(<ZurichViewer onLoadProgress={onLoadProgress} />);

    await waitFor(() => {
      const calls = onLoadProgress.mock.calls;
      const lastCall = calls[calls.length - 1];
      expect(lastCall?.[0]).toBe(100);
    }, { timeout: 2000 });
  });

  it('should show crosshair when ready', async () => {
    const onLoadProgress = vi.fn();
    const { container } = render(<ZurichViewer onLoadProgress={onLoadProgress} />);

    await waitFor(() => {
      const crosshair = container.querySelector('.crosshair');
      expect(crosshair).toBeInTheDocument();
    }, { timeout: 2000 });
  });

  it('should show controls hint when ready', async () => {
    const onLoadProgress = vi.fn();
    const { container } = render(<ZurichViewer onLoadProgress={onLoadProgress} />);

    await waitFor(() => {
      const hint = container.querySelector('.controls-hint');
      expect(hint).toBeInTheDocument();
    }, { timeout: 2000 });
  });

  it('should render DeckGL component', () => {
    const { getByTestId } = render(<ZurichViewer />);
    expect(getByTestId('deckgl-mock')).toBeInTheDocument();
  });
});
```

**Verification:**
- [ ] File exists at `src/components/ZurichViewer/ZurichViewer.test.tsx`

---

## Verification Checklist

After completing all tasks:

### Files
- [ ] `vitest.config.ts` exists
- [ ] `src/test/setup.ts` exists
- [ ] `src/main.tsx` exists
- [ ] `src/App.tsx` exists
- [ ] `src/styles/globals.css` exists
- [ ] `src/lib/config.ts` exists
- [ ] `src/lib/constants.ts` exists (re-exports from types)
- [ ] `src/lib/constants.test.ts` exists
- [ ] `src/lib/config.test.ts` exists
- [ ] `src/lib/index.ts` exists
- [ ] `src/components/ZurichViewer/ZurichViewer.tsx` exists
- [ ] `src/components/ZurichViewer/ZurichViewer.test.tsx` exists
- [ ] `src/components/ZurichViewer/index.ts` exists
- [ ] `src/vite-env.d.ts` exists

### Commands
```bash
cd /Users/claudioromano/Documents/livemap/zuri-3d && pnpm type-check  # Should pass
cd /Users/claudioromano/Documents/livemap/zuri-3d && pnpm test        # Should pass
```

## Files Created

```
vitest.config.ts                          # NEW
src/
├── main.tsx
├── App.tsx
├── vite-env.d.ts
├── test/
│   └── setup.ts                          # NEW
├── styles/
│   └── globals.css
├── lib/
│   ├── config.ts
│   ├── config.test.ts                    # NEW
│   ├── constants.ts                      # MODIFIED (re-exports)
│   ├── constants.test.ts                 # NEW
│   └── index.ts
└── components/
    └── ZurichViewer/
        ├── ZurichViewer.tsx
        ├── ZurichViewer.test.tsx         # NEW
        └── index.ts
```

## Current State After Phase 3

The application now has:
- Vitest configuration with WebGL mocking
- Test setup for React and deck.gl components
- React entry point and App component
- deck.gl FirstPersonView setup
- Basic UI structure (loading, crosshair, hints)
- Configuration and constants (re-exported from types)
- Unit tests for constants, config, and ZurichViewer
- Type-safe foundations with full test coverage

**Not yet implemented:**
- WASD movement controls (Phase 4)
- Mouse look (Phase 4)
- Collision detection (Phase 4)
- Building layers (Phase 5)
- Terrain (Phase 5)

## Next Phase
After verification, read and execute: `.claude/plans/phases/04-controls.md`
