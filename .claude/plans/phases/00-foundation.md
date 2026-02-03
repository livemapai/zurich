# Phase 0: Foundation

## Context
This phase initializes the project with all dependencies, TypeScript configuration, and core documentation. After completing this phase, you'll have a type-safe project structure ready for deck.gl development.

## Prerequisites
- Node.js 18+ installed
- pnpm available
- Empty project directory at `/Users/claudioromano/Documents/livemap/zuri-3d/`

## Tasks

### Task 0.1: Create package.json
**Goal:** Define all project dependencies including deck.gl v9, React 19, and development tools.

**Create file:** `package.json`
```json
{
  "name": "zuri-3d",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "type-check": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@deck.gl/core": "^9.0.0",
    "@deck.gl/extensions": "^9.0.0",
    "@deck.gl/geo-layers": "^9.0.0",
    "@deck.gl/layers": "^9.0.0",
    "@deck.gl/react": "^9.0.0",
    "@loaders.gl/3d-tiles": "^4.0.0",
    "@loaders.gl/core": "^4.0.0",
    "@loaders.gl/terrain": "^4.0.0",
    "@math.gl/core": "^4.0.0",
    "deck.gl": "^9.0.0",
    "rbush": "^3.0.1",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@deck.gl/test-utils": "^9.0.0",
    "@testing-library/jest-dom": "^6.0.0",
    "@testing-library/react": "^14.0.0",
    "@types/rbush": "^3.0.3",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "jsdom": "^24.0.0",
    "typescript": "^5.7.0",
    "vite": "^6.0.0",
    "vitest": "^2.0.0"
  }
}
```

**Verification:**
- [ ] File exists at `package.json`

---

### Task 0.2: Create TypeScript Configuration
**Goal:** Configure TypeScript for strict type checking with React and deck.gl support.

**Create file:** `tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "forceConsistentCasingInFileNames": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src", "scripts/**/*.ts"],
  "exclude": ["node_modules"]
}
```

**Verification:**
- [ ] File exists at `tsconfig.json`

---

### Task 0.3: Create Vite Configuration
**Goal:** Configure Vite bundler with React plugin and path aliases.

**Create file:** `vite.config.ts`
```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    open: true,
  },
  build: {
    target: 'ES2022',
    sourcemap: true,
  },
  optimizeDeps: {
    include: ['deck.gl', '@deck.gl/core', '@deck.gl/layers', '@deck.gl/react'],
  },
});
```

**Verification:**
- [ ] File exists at `vite.config.ts`

---

### Task 0.4: Create HTML Entry Point
**Goal:** Create the HTML file that hosts the React application.

**Create file:** `index.html`
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="3D walkthrough of Zurich using deck.gl" />
    <title>Zurich 3D Walkthrough</title>
    <style>
      * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }
      html, body, #root {
        width: 100%;
        height: 100%;
        overflow: hidden;
        background: #1a1a2e;
      }
    </style>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

**Verification:**
- [ ] File exists at `index.html`

---

### Task 0.5: Create Core TypeScript Types
**Goal:** Define all TypeScript interfaces for the application including ViewState, GameState, and GeoJSON types.

**Create file:** `src/types/index.ts`
```typescript
/**
 * Core type definitions for Zurich 3D Walkthrough
 */

// ============================================================================
// Coordinate Types
// ============================================================================

/** WGS84 longitude/latitude coordinates */
export interface LngLat {
  lng: number;
  lat: number;
}

/** Position in meters relative to a reference point */
export interface MetersPosition {
  x: number; // East-West (positive = East)
  y: number; // North-South (positive = North)
  z: number; // Altitude (positive = Up)
}

/** Swiss LV95 coordinates (EPSG:2056) */
export interface LV95Coordinates {
  e: number; // Easting
  n: number; // Northing
}

// ============================================================================
// Zurich Constants
// ============================================================================

/** Zurich city center in WGS84 */
export const ZURICH_CENTER: LngLat = {
  lng: 8.541694,
  lat: 47.376888,
};

/** Zurich bounding box in WGS84 */
export const ZURICH_BOUNDS = {
  minLng: 8.448,
  maxLng: 8.626,
  minLat: 47.320,
  maxLat: 47.435,
} as const;

/** Approximate meters per degree at Zurich's latitude */
export const METERS_PER_DEGREE = {
  lng: 73000, // At ~47° latitude
  lat: 111000,
} as const;

// ============================================================================
// First Person View State
// ============================================================================

/**
 * FirstPersonView state for deck.gl
 * Position is in [longitude, latitude, altitude] format
 */
export interface FirstPersonViewState {
  /** Camera position [lng, lat, altitude in meters] */
  position: [number, number, number];
  /** Horizontal rotation in degrees (0 = North, 90 = East) */
  bearing: number;
  /** Vertical rotation in degrees (-90 = down, 90 = up) */
  pitch: number;
  /** Field of view in degrees (vertical) */
  fov?: number;
  /** Near clipping plane in meters */
  near?: number;
  /** Far clipping plane in meters */
  far?: number;
}

/** Default view state centered on Zurich */
export const DEFAULT_VIEW_STATE: FirstPersonViewState = {
  position: [ZURICH_CENTER.lng, ZURICH_CENTER.lat, 2], // 2m = eye height
  bearing: 0,
  pitch: 0,
  fov: 75,
  near: 0.1,
  far: 10000,
};

// ============================================================================
// Player & Movement
// ============================================================================

/** Player physical dimensions in meters */
export const PLAYER_DIMENSIONS = {
  height: 1.8,      // Total height
  eyeHeight: 1.7,   // Camera position from ground
  radius: 0.3,      // Collision radius
  stepHeight: 0.3,  // Max step-up height
} as const;

/** Movement speeds in meters per second */
export const MOVEMENT_SPEEDS = {
  walk: 4.0,
  run: 8.0,
  turnRate: 90, // Degrees per second (keyboard)
} as const;

/** Mouse sensitivity */
export const MOUSE_SENSITIVITY = {
  x: 0.1, // Degrees per pixel
  y: 0.1,
} as const;

/** Keyboard state for WASD controls */
export interface KeyboardState {
  forward: boolean;  // W
  backward: boolean; // S
  left: boolean;     // A
  right: boolean;    // D
  run: boolean;      // Shift
  jump: boolean;     // Space
}

/** Velocity vector in meters per second */
export interface Velocity {
  x: number;
  y: number;
  z: number;
}

// ============================================================================
// Game State
// ============================================================================

/** Overall game/application state */
export interface GameState {
  viewState: FirstPersonViewState;
  velocity: Velocity;
  isGrounded: boolean;
  isPointerLocked: boolean;
  groundElevation: number;
  currentTime: number;
  deltaTime: number;
}

/** Initial game state */
export const INITIAL_GAME_STATE: GameState = {
  viewState: DEFAULT_VIEW_STATE,
  velocity: { x: 0, y: 0, z: 0 },
  isGrounded: true,
  isPointerLocked: false,
  groundElevation: 0,
  currentTime: 0,
  deltaTime: 0,
};

// ============================================================================
// GeoJSON Types for Buildings
// ============================================================================

/** Building properties from Stadt Zürich data */
export interface BuildingProperties {
  id: string;
  height: number;        // Building height in meters
  baseElevation: number; // Ground level in meters
  roofType?: string;
  yearBuilt?: number;
}

/** GeoJSON Feature for a building */
export interface BuildingFeature {
  type: 'Feature';
  geometry: {
    type: 'Polygon' | 'MultiPolygon';
    coordinates: number[][][] | number[][][][];
  };
  properties: BuildingProperties;
}

/** GeoJSON FeatureCollection for buildings */
export interface BuildingsCollection {
  type: 'FeatureCollection';
  features: BuildingFeature[];
}

// ============================================================================
// Collision Detection
// ============================================================================

/** Axis-aligned bounding box for spatial indexing */
export interface CollisionBBox {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
  /** Reference to the building feature */
  feature: BuildingFeature;
}

/** Result of a collision check */
export interface CollisionResult {
  collides: boolean;
  /** Penetration depth if collision occurred */
  depth?: number;
  /** Normal vector pointing away from collision */
  normal?: { x: number; y: number };
  /** The building that was hit */
  building?: BuildingFeature;
}

// ============================================================================
// Terrain
// ============================================================================

/** Terrain elevation data */
export interface TerrainData {
  /** Width in pixels */
  width: number;
  /** Height in pixels */
  height: number;
  /** Bounding box in WGS84 */
  bounds: {
    minLng: number;
    maxLng: number;
    minLat: number;
    maxLat: number;
  };
  /** Elevation values in meters (row-major) */
  elevations: Float32Array;
}

/** Query result for terrain elevation */
export interface TerrainQuery {
  elevation: number;
  /** Surface normal at the query point */
  normal?: { x: number; y: number; z: number };
}

// ============================================================================
// Layer Configuration
// ============================================================================

/** Common layer properties */
export interface LayerConfig {
  id: string;
  visible: boolean;
  opacity: number;
  pickable?: boolean;
}

/** Buildings layer configuration */
export interface BuildingsLayerConfig extends LayerConfig {
  extruded: boolean;
  wireframe: boolean;
  filled: boolean;
  /** LOD distance thresholds in meters */
  lodDistances?: {
    high: number;
    medium: number;
    low: number;
  };
}

/** Terrain layer configuration */
export interface TerrainLayerConfig extends LayerConfig {
  meshMaxError: number;
  elevationScale: number;
}

// ============================================================================
// Data Loading
// ============================================================================

/** Loading state for async data */
export interface LoadingState<T> {
  data: T | null;
  isLoading: boolean;
  error: Error | null;
  progress: number; // 0-100
}

/** Data source configuration */
export interface DataSource {
  url: string;
  format: 'geojson' | 'obj' | 'geotiff' | 'terrain-rgb';
  crs?: 'EPSG:4326' | 'EPSG:2056';
}

// ============================================================================
// Utility Types
// ============================================================================

/** Clamp a number between min and max */
export type ClampedNumber<Min extends number, Max extends number> = number & {
  __brand: 'ClampedNumber';
  __min: Min;
  __max: Max;
};

/** Degrees (for clarity in function signatures) */
export type Degrees = number;

/** Meters (for clarity in function signatures) */
export type Meters = number;

/** Milliseconds (for clarity in function signatures) */
export type Milliseconds = number;
```

**Verification:**
- [ ] File exists at `src/types/index.ts`
- [ ] Run `pnpm type-check` (after installing dependencies)

---

### Task 0.6: Create CLAUDE.md Project Instructions
**Goal:** Create the main project instructions file that Claude Code will use for all sessions.

**Create file:** `CLAUDE.md`
```markdown
# Zurich 3D Walkthrough - Project Instructions

## Overview
A 3D walkable visualization of Zurich using deck.gl with open data sources. Features 50,000+ buildings, terrain elevation, and first-person navigation controls.

## Tech Stack
- **Rendering:** deck.gl v9 with FirstPersonView
- **Framework:** React 19 + TypeScript 5.7
- **Build:** Vite 6
- **Spatial Index:** RBush
- **Data:** GeoJSON (converted from OBJ/GeoTIFF)

## Project Structure
```
src/
├── components/          # React components
│   ├── ZurichViewer/   # Main viewer component
│   ├── Minimap/        # Navigation minimap
│   ├── Controls/       # UI overlays
│   └── Loading/        # Loading states
├── hooks/              # React hooks
│   ├── useKeyboardState.ts
│   ├── useMouseLook.ts
│   ├── useGameLoop.ts
│   ├── useCollisionDetection.ts
│   └── useTerrainElevation.ts
├── systems/            # Game systems (non-React)
│   ├── MovementController.ts
│   ├── CameraController.ts
│   ├── SpatialIndex.ts
│   └── TerrainSampler.ts
├── layers/             # deck.gl layer factories
│   ├── BuildingsLayer.ts
│   ├── TerrainLayer.ts
│   └── MinimapLayers.ts
├── lib/                # Configuration and data loading
│   ├── config.ts
│   ├── constants.ts
│   └── data/
├── types/              # TypeScript definitions
├── utils/              # Pure utility functions
└── styles/             # CSS files
```

## Key Concepts

### Coordinate Systems
- **WGS84 (EPSG:4326):** Longitude/latitude for deck.gl
- **Swiss LV95 (EPSG:2056):** Source data format
- **Local Meters:** For movement calculations

### FirstPersonView
deck.gl's FirstPersonView uses:
- `position`: [lng, lat, altitude] in WGS84
- `bearing`: Horizontal angle (0=North, 90=East)
- `pitch`: Vertical angle (-90=down, 90=up)

### Movement System
1. Keyboard state → Velocity vector
2. Velocity + bearing → World-space movement
3. Collision check → Adjusted position
4. Terrain query → Ground-locked altitude
5. Update ViewState

## Commands
```bash
pnpm install          # Install dependencies
pnpm type-check       # TypeScript validation
pnpm test             # Run tests
pnpm dev              # Start dev server (DO NOT USE)
pnpm build            # Production build
```

## Important Notes
- **NEVER start the dev server** - verify with type-check and tests only
- **NEVER run build** - not needed for development
- All coordinates must be in WGS84 for deck.gl
- Movement calculations use meters, then convert to degrees
- Buildings are extruded polygons, not 3D meshes

## Data Sources
| Data | URL | Format |
|------|-----|--------|
| Buildings | data.stadt-zuerich.ch | OBJ → GeoJSON |
| Terrain | swisstopo swissALTI3D | GeoTIFF → RGB |

## Phase Execution
Execute phases in order:
1. `.claude/plans/phases/00-foundation.md` ✓
2. `.claude/plans/phases/01-skills.md`
3. `.claude/plans/phases/02-data-pipeline.md`
4. `.claude/plans/phases/03-core-app.md`
5. `.claude/plans/phases/04-controls.md`
6. `.claude/plans/phases/05-layers.md`
7. `.claude/plans/phases/06-polish.md`

## Skills Available (After Phase 1)
- `/deckgl-layer` - Create deck.gl layers
- `/deckgl-data` - Create data loaders
- `/deckgl-firstperson` - First-person navigation
- `/deckgl-verify` - Verify implementation
```

**Verification:**
- [ ] File exists at `CLAUDE.md`

---

### Task 0.7: Install Dependencies
**Goal:** Install all npm dependencies.

**Run command:**
```bash
cd /Users/claudioromano/Documents/livemap/zuri-3d && pnpm install
```

**Verification:**
- [ ] `node_modules/` directory exists
- [ ] `pnpm-lock.yaml` exists
- [ ] No errors during installation

---

### Task 0.8: Verify TypeScript Setup
**Goal:** Confirm TypeScript is properly configured.

**Run command:**
```bash
cd /Users/claudioromano/Documents/livemap/zuri-3d && pnpm type-check
```

**Expected result:** Should pass with no errors (or only warnings about empty src files)

---

## Verification Checklist

After completing all tasks:

- [ ] `package.json` exists with correct dependencies
- [ ] `tsconfig.json` exists with strict mode
- [ ] `vite.config.ts` exists with React plugin
- [ ] `index.html` exists with root div
- [ ] `src/types/index.ts` exists with all type definitions
- [ ] `CLAUDE.md` exists with project instructions
- [ ] `pnpm install` completed successfully
- [ ] `pnpm type-check` passes

## Files Created

```
/Users/claudioromano/Documents/livemap/zuri-3d/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html
├── CLAUDE.md
└── src/
    └── types/
        └── index.ts
```

## Next Phase
After verification, read and execute: `.claude/plans/phases/01-skills.md`
