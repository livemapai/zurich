# Phase 5: Rendering Layers

## Context
This phase creates deck.gl layers for rendering buildings and terrain. It also adds a minimap for navigation overview.

## Prerequisites
- Phase 4 completed (controls working)
- Building data available (`public/data/zurich-buildings.geojson`)
- `pnpm type-check` passes

## Tasks

### Task 5.1: Create BuildingsLayer Factory
**Goal:** Create a layer factory for extruded building polygons.

**Create file:** `src/layers/BuildingsLayer.ts`
```typescript
/**
 * BuildingsLayer - Factory for creating building polygon layers
 *
 * Uses SolidPolygonLayer for extruded 3D buildings.
 */

import { SolidPolygonLayer } from '@deck.gl/layers';
import type { BuildingFeature } from '@/types';

export interface BuildingsLayerConfig {
  id?: string;
  visible?: boolean;
  opacity?: number;
  extruded?: boolean;
  wireframe?: boolean;
  pickable?: boolean;
}

const DEFAULT_CONFIG: Required<BuildingsLayerConfig> = {
  id: 'buildings',
  visible: true,
  opacity: 1,
  extruded: true,
  wireframe: false,
  pickable: true,
};

// Building colors
const FILL_COLOR: [number, number, number, number] = [200, 200, 220, 255];
const LINE_COLOR: [number, number, number, number] = [100, 100, 120, 255];
const HIGHLIGHT_COLOR: [number, number, number, number] = [255, 200, 0, 128];

/**
 * Create a buildings layer for deck.gl
 *
 * @param data - Array of building features
 * @param config - Layer configuration
 * @returns Configured SolidPolygonLayer instance
 */
export function createBuildingsLayer(
  data: BuildingFeature[],
  config: BuildingsLayerConfig = {}
) {
  const mergedConfig = { ...DEFAULT_CONFIG, ...config };

  return new SolidPolygonLayer<BuildingFeature>({
    id: mergedConfig.id,
    data,

    // Geometry accessor - get polygon coordinates from feature
    getPolygon: (d) => {
      const coords = d.geometry.coordinates;
      if (d.geometry.type === 'MultiPolygon') {
        // Take first polygon for MultiPolygon
        return coords[0]?.[0] ?? [];
      }
      // Regular polygon - outer ring
      return coords[0] ?? [];
    },

    // Extrusion
    extruded: mergedConfig.extruded,
    getElevation: (d) => d.properties.height || 10,
    elevationScale: 1,

    // Appearance
    getFillColor: FILL_COLOR,
    getLineColor: LINE_COLOR,
    filled: true,
    stroked: false,
    wireframe: mergedConfig.wireframe,

    // Interaction
    pickable: mergedConfig.pickable,
    autoHighlight: true,
    highlightColor: HIGHLIGHT_COLOR,

    // Visibility
    visible: mergedConfig.visible,
    opacity: mergedConfig.opacity,

    // Material for 3D lighting
    material: {
      ambient: 0.35,
      diffuse: 0.6,
      shininess: 32,
      specularColor: [60, 64, 70],
    },

    // Performance
    _normalize: false,
  });
}

/**
 * Create a simplified buildings layer for minimap
 */
export function createMinimapBuildingsLayer(
  data: BuildingFeature[],
  config: Partial<BuildingsLayerConfig> = {}
) {
  return new SolidPolygonLayer<BuildingFeature>({
    id: config.id ?? 'minimap-buildings',
    data,

    getPolygon: (d) => {
      const coords = d.geometry.coordinates;
      if (d.geometry.type === 'MultiPolygon') {
        return coords[0]?.[0] ?? [];
      }
      return coords[0] ?? [];
    },

    // No extrusion for minimap
    extruded: false,

    // Flat colors
    getFillColor: [80, 80, 100, 200],
    filled: true,
    stroked: false,

    // No interaction
    pickable: false,

    visible: config.visible ?? true,
    opacity: config.opacity ?? 1,
  });
}
```

**Verification:**
- [ ] File exists at `src/layers/BuildingsLayer.ts`

---

### Task 5.2: Create TerrainLayer Factory
**Goal:** Create a layer factory for terrain visualization.

**Create file:** `src/layers/TerrainLayer.ts`
```typescript
/**
 * TerrainLayer - Factory for creating terrain layers
 *
 * Uses TerrainLayer from deck.gl/geo-layers for elevation visualization.
 * For MVP, creates a simple colored ground plane.
 */

import { SolidPolygonLayer } from '@deck.gl/layers';
import { ZURICH_BOUNDS } from '@/lib/constants';

export interface TerrainLayerConfig {
  id?: string;
  visible?: boolean;
  opacity?: number;
  color?: [number, number, number, number];
}

const DEFAULT_CONFIG = {
  id: 'terrain',
  visible: true,
  opacity: 1,
  color: [40, 60, 40, 255] as [number, number, number, number],
};

/**
 * Create a simple ground plane layer
 *
 * This is a placeholder until actual terrain data is integrated.
 * Creates a colored polygon covering the Zurich area.
 */
export function createTerrainLayer(config: TerrainLayerConfig = {}) {
  const mergedConfig = { ...DEFAULT_CONFIG, ...config };

  // Create a ground polygon covering the bounds
  const groundPolygon = [
    [ZURICH_BOUNDS.minLng, ZURICH_BOUNDS.minLat],
    [ZURICH_BOUNDS.maxLng, ZURICH_BOUNDS.minLat],
    [ZURICH_BOUNDS.maxLng, ZURICH_BOUNDS.maxLat],
    [ZURICH_BOUNDS.minLng, ZURICH_BOUNDS.maxLat],
    [ZURICH_BOUNDS.minLng, ZURICH_BOUNDS.minLat], // Close polygon
  ];

  return new SolidPolygonLayer({
    id: mergedConfig.id,
    data: [{ polygon: groundPolygon }],

    getPolygon: (d: { polygon: number[][] }) => d.polygon,

    // No extrusion - flat ground
    extruded: false,

    // Ground color
    getFillColor: mergedConfig.color,
    filled: true,

    // No interaction
    pickable: false,

    visible: mergedConfig.visible,
    opacity: mergedConfig.opacity,
  });
}

/**
 * Create a grid overlay for visual reference
 */
export function createGridLayer(config: { visible?: boolean } = {}) {
  // Create grid lines every 100m (approximately)
  const gridSize = 0.001; // ~100m in degrees
  const lines: { path: number[][] }[] = [];

  // Vertical lines (constant longitude)
  for (let lng = ZURICH_BOUNDS.minLng; lng <= ZURICH_BOUNDS.maxLng; lng += gridSize) {
    lines.push({
      path: [
        [lng, ZURICH_BOUNDS.minLat],
        [lng, ZURICH_BOUNDS.maxLat],
      ],
    });
  }

  // Horizontal lines (constant latitude)
  for (let lat = ZURICH_BOUNDS.minLat; lat <= ZURICH_BOUNDS.maxLat; lat += gridSize) {
    lines.push({
      path: [
        [ZURICH_BOUNDS.minLng, lat],
        [ZURICH_BOUNDS.maxLng, lat],
      ],
    });
  }

  // Import PathLayer dynamically to avoid circular deps
  const { PathLayer } = require('@deck.gl/layers');

  return new PathLayer({
    id: 'grid',
    data: lines,
    getPath: (d: { path: number[][] }) => d.path,
    getColor: [60, 80, 60, 100],
    getWidth: 1,
    widthUnits: 'pixels',
    pickable: false,
    visible: config.visible ?? false,
  });
}
```

**Verification:**
- [ ] File exists at `src/layers/TerrainLayer.ts`

---

### Task 5.3: Create Minimap Layers
**Goal:** Create layers for the minimap view.

**Create file:** `src/layers/MinimapLayers.ts`
```typescript
/**
 * MinimapLayers - Layers for the navigation minimap
 *
 * Includes building outlines, player position, and view cone.
 */

import { ScatterplotLayer, PolygonLayer } from '@deck.gl/layers';
import type { BuildingFeature } from '@/types';
import { createMinimapBuildingsLayer } from './BuildingsLayer';
import { DEG_TO_RAD } from '@/lib/constants';

export interface MinimapLayersConfig {
  buildings: BuildingFeature[] | null;
  playerPosition: [number, number];
  playerBearing: number;
  viewDistance?: number;
  viewAngle?: number;
}

/**
 * Create all layers for the minimap
 */
export function createMinimapLayers(config: MinimapLayersConfig) {
  const {
    buildings,
    playerPosition,
    playerBearing,
    viewDistance = 0.002, // ~150m in degrees
    viewAngle = 60, // degrees
  } = config;

  const layers = [];

  // 1. Buildings layer (simplified)
  if (buildings && buildings.length > 0) {
    layers.push(
      createMinimapBuildingsLayer(buildings, { id: 'minimap-buildings' })
    );
  }

  // 2. Player position (dot)
  layers.push(
    new ScatterplotLayer({
      id: 'minimap-player',
      data: [{ position: playerPosition }],
      getPosition: (d: { position: [number, number] }) => d.position,
      getFillColor: [255, 100, 100, 255],
      getRadius: 5,
      radiusUnits: 'pixels',
      pickable: false,
    })
  );

  // 3. View cone
  const viewCone = createViewCone(
    playerPosition,
    playerBearing,
    viewDistance,
    viewAngle
  );

  layers.push(
    new PolygonLayer({
      id: 'minimap-view-cone',
      data: [{ polygon: viewCone }],
      getPolygon: (d: { polygon: number[][] }) => d.polygon,
      getFillColor: [255, 200, 100, 60],
      getLineColor: [255, 200, 100, 150],
      stroked: true,
      lineWidthMinPixels: 1,
      filled: true,
      pickable: false,
    })
  );

  return layers;
}

/**
 * Create view cone polygon
 */
function createViewCone(
  position: [number, number],
  bearing: number,
  distance: number,
  angle: number
): number[][] {
  const [lng, lat] = position;

  // Calculate the two outer points of the cone
  const halfAngle = angle / 2;
  const leftAngle = (bearing - halfAngle) * DEG_TO_RAD;
  const rightAngle = (bearing + halfAngle) * DEG_TO_RAD;

  // Points at distance from player
  // Note: We use sin for lng (east-west) and cos for lat (north-south)
  // because bearing 0 = north
  const leftPoint: [number, number] = [
    lng + Math.sin(leftAngle) * distance,
    lat + Math.cos(leftAngle) * distance,
  ];

  const rightPoint: [number, number] = [
    lng + Math.sin(rightAngle) * distance,
    lat + Math.cos(rightAngle) * distance,
  ];

  // Triangle: player position, left point, right point
  return [
    [lng, lat],
    leftPoint,
    rightPoint,
    [lng, lat], // Close polygon
  ];
}
```

**Verification:**
- [ ] File exists at `src/layers/MinimapLayers.ts`

---

### Task 5.4: Create Layers Index
**Goal:** Create barrel export for layers.

**Create file:** `src/layers/index.ts`
```typescript
export {
  createBuildingsLayer,
  createMinimapBuildingsLayer,
  type BuildingsLayerConfig,
} from './BuildingsLayer';

export {
  createTerrainLayer,
  createGridLayer,
  type TerrainLayerConfig,
} from './TerrainLayer';

export {
  createMinimapLayers,
  type MinimapLayersConfig,
} from './MinimapLayers';
```

**Verification:**
- [ ] File exists at `src/layers/index.ts`

---

### Task 5.5: Create Minimap Component
**Goal:** Create a minimap overlay component.

**Create file:** `src/components/Minimap/Minimap.tsx`
```typescript
/**
 * Minimap - Navigation minimap overlay
 *
 * Shows a top-down view of the area with player position and buildings.
 */

import { useMemo } from 'react';
import DeckGL from '@deck.gl/react';
import { OrthographicView } from '@deck.gl/core';
import type { BuildingFeature } from '@/types';
import { createMinimapLayers } from '@/layers';
import { ZURICH_CENTER, METERS_PER_DEGREE } from '@/lib/constants';

interface MinimapProps {
  playerPosition: [number, number, number];
  playerBearing: number;
  buildings: BuildingFeature[] | null;
  size?: number;
  zoom?: number;
}

// Default minimap size in pixels
const DEFAULT_SIZE = 200;

// Zoom level (pixels per degree, approximately)
const DEFAULT_ZOOM = 500000; // ~7m per pixel at this zoom

export function Minimap({
  playerPosition,
  playerBearing,
  buildings,
  size = DEFAULT_SIZE,
  zoom = DEFAULT_ZOOM,
}: MinimapProps) {
  // Create orthographic view centered on player
  const view = useMemo(
    () =>
      new OrthographicView({
        id: 'minimap',
        controller: false,
      }),
    []
  );

  // View state: centered on player, north-up
  const viewState = useMemo(
    () => ({
      target: [playerPosition[0], playerPosition[1], 0],
      zoom: Math.log2(zoom),
      minZoom: 10,
      maxZoom: 20,
    }),
    [playerPosition, zoom]
  );

  // Create layers
  const layers = useMemo(
    () =>
      createMinimapLayers({
        buildings,
        playerPosition: [playerPosition[0], playerPosition[1]],
        playerBearing,
      }),
    [buildings, playerPosition, playerBearing]
  );

  return (
    <div
      style={{
        position: 'absolute',
        top: 10,
        left: 10,
        width: size,
        height: size,
        borderRadius: 8,
        overflow: 'hidden',
        border: '2px solid rgba(255, 255, 255, 0.3)',
        background: 'rgba(0, 0, 0, 0.5)',
      }}
    >
      <DeckGL
        views={view}
        viewState={viewState}
        controller={false}
        layers={layers}
        style={{ width: '100%', height: '100%' }}
      />

      {/* North indicator */}
      <div
        style={{
          position: 'absolute',
          top: 5,
          right: 5,
          fontSize: '10px',
          color: 'rgba(255, 255, 255, 0.7)',
          fontWeight: 'bold',
        }}
      >
        N
      </div>
    </div>
  );
}
```

**Verification:**
- [ ] File exists at `src/components/Minimap/Minimap.tsx`

---

### Task 5.6: Create Minimap Index
**Goal:** Create barrel export for Minimap.

**Create file:** `src/components/Minimap/index.ts`
```typescript
export { Minimap } from './Minimap';
```

**Verification:**
- [ ] File exists at `src/components/Minimap/index.ts`

---

### Task 5.7: Create Building Data Loader
**Goal:** Create a loader for building GeoJSON data.

**Create file:** `src/lib/data/buildings.ts`
```typescript
/**
 * Building data loader
 *
 * Loads and parses building GeoJSON data.
 */

import type { BuildingFeature, BuildingsCollection } from '@/types';

export interface BuildingLoadResult {
  features: BuildingFeature[];
  bounds: {
    minLng: number;
    maxLng: number;
    minLat: number;
    maxLat: number;
  };
  stats: {
    count: number;
    minHeight: number;
    maxHeight: number;
    avgHeight: number;
  };
}

/**
 * Load buildings from GeoJSON file
 *
 * @param url - URL to GeoJSON file
 * @param onProgress - Progress callback (0-100)
 */
export async function loadBuildings(
  url: string,
  onProgress?: (progress: number) => void
): Promise<BuildingLoadResult> {
  onProgress?.(0);

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to load buildings: ${response.status} ${response.statusText}`);
  }

  onProgress?.(30);

  const data: BuildingsCollection = await response.json();

  onProgress?.(60);

  // Validate structure
  if (data.type !== 'FeatureCollection' || !Array.isArray(data.features)) {
    throw new Error('Invalid GeoJSON: expected FeatureCollection');
  }

  const features = data.features;

  // Calculate bounds and stats
  let minLng = Infinity;
  let maxLng = -Infinity;
  let minLat = Infinity;
  let maxLat = -Infinity;
  let minHeight = Infinity;
  let maxHeight = -Infinity;
  let totalHeight = 0;
  let heightCount = 0;

  for (const feature of features) {
    // Get coordinates
    const coords = feature.geometry.coordinates;
    const ring = feature.geometry.type === 'MultiPolygon'
      ? coords[0]?.[0] ?? []
      : coords[0] ?? [];

    for (const [lng, lat] of ring as number[][]) {
      if (lng < minLng) minLng = lng;
      if (lng > maxLng) maxLng = lng;
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
    }

    // Get height
    const height = feature.properties?.height ?? 0;
    if (height > 0) {
      if (height < minHeight) minHeight = height;
      if (height > maxHeight) maxHeight = height;
      totalHeight += height;
      heightCount++;
    }
  }

  onProgress?.(100);

  return {
    features,
    bounds: { minLng, maxLng, minLat, maxLat },
    stats: {
      count: features.length,
      minHeight: minHeight === Infinity ? 0 : minHeight,
      maxHeight: maxHeight === -Infinity ? 0 : maxHeight,
      avgHeight: heightCount > 0 ? totalHeight / heightCount : 0,
    },
  };
}
```

**Verification:**
- [ ] File exists at `src/lib/data/buildings.ts`

---

### Task 5.8: Create Data Index
**Goal:** Create barrel export for data loaders.

**Create file:** `src/lib/data/index.ts`
```typescript
export { loadBuildings, type BuildingLoadResult } from './buildings';
```

**Verification:**
- [ ] File exists at `src/lib/data/index.ts`

---

### Task 5.9: Update ZurichViewer with Layers
**Goal:** Integrate building layers and minimap into the viewer.

**Update file:** `src/components/ZurichViewer/ZurichViewer.tsx`
```typescript
import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import DeckGL from '@deck.gl/react';
import { FirstPersonView, LightingEffect, AmbientLight, DirectionalLight } from '@deck.gl/core';
import type { FirstPersonViewState, BuildingFeature, Velocity } from '@/types';
import { CONFIG } from '@/lib/config';
import { DEFAULT_POSITION, METERS_PER_DEGREE, DEG_TO_RAD } from '@/lib/constants';
import { useKeyboardState, useMouseLook, useGameLoop, useCollisionDetection, useTerrainElevation } from '@/hooks';
import { movementController, cameraController } from '@/systems';
import { slideAlongWall } from '@/utils/math';
import { createBuildingsLayer, createTerrainLayer } from '@/layers';
import { loadBuildings } from '@/lib/data';
import { Minimap } from '@/components/Minimap';

interface ZurichViewerProps {
  onLoadProgress?: (progress: number) => void;
  onError?: (error: Error) => void;
}

const INITIAL_VIEW_STATE: FirstPersonViewState = {
  position: DEFAULT_POSITION,
  bearing: 0,
  pitch: 0,
  fov: CONFIG.render.fov,
  near: CONFIG.render.near,
  far: CONFIG.render.far,
};

const PLAYER_RADIUS_DEGREES = CONFIG.player.collisionRadius / METERS_PER_DEGREE.lng;

// Create lighting effect for 3D buildings
const lightingEffect = new LightingEffect({
  ambientLight: new AmbientLight({
    color: [255, 255, 255],
    intensity: 1.0,
  }),
  directionalLight: new DirectionalLight({
    color: [255, 255, 240],
    intensity: 1.0,
    direction: [-1, -2, -3],
  }),
});

export function ZurichViewer({ onLoadProgress, onError }: ZurichViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [viewState, setViewState] = useState<FirstPersonViewState>(INITIAL_VIEW_STATE);
  const [isReady, setIsReady] = useState(false);
  const [buildings, setBuildings] = useState<BuildingFeature[] | null>(null);
  const [showMinimap, setShowMinimap] = useState(true);

  // Input hooks
  const keyboard = useKeyboardState();
  const { isLocked, consumeDelta, requestLock, exitLock } = useMouseLook(containerRef);

  // Collision and terrain hooks
  const { checkCollision, isReady: collisionReady } = useCollisionDetection(buildings);
  const { getElevation } = useTerrainElevation(null);

  // View configuration
  const view = useMemo(
    () =>
      new FirstPersonView({
        id: 'first-person',
        controller: false,
        fovy: viewState.fov ?? CONFIG.render.fov,
        near: viewState.near ?? CONFIG.render.near,
        far: viewState.far ?? CONFIG.render.far,
      }),
    [viewState.fov, viewState.near, viewState.far]
  );

  // Create layers
  const layers = useMemo(() => {
    const result = [];

    // Ground layer
    result.push(createTerrainLayer({ id: 'terrain' }));

    // Buildings layer
    if (buildings && buildings.length > 0) {
      result.push(
        createBuildingsLayer(buildings, {
          id: 'buildings',
          extruded: true,
        })
      );
    }

    return result;
  }, [buildings]);

  // Main game loop
  const gameLoop = useCallback(
    (deltaTime: number) => {
      let newViewState = viewState;

      // Apply mouse look
      if (isLocked) {
        const mouseDelta = consumeDelta();
        newViewState = cameraController.applyMouseLook(
          newViewState,
          mouseDelta.x,
          mouseDelta.y
        );
      }

      // Calculate velocity from keyboard
      const velocity = movementController.calculateVelocity(
        keyboard,
        newViewState.bearing
      );

      if (velocity.x !== 0 || velocity.y !== 0) {
        const [lng, lat] = newViewState.position;
        const cosLat = Math.cos(lat * DEG_TO_RAD);
        const metersPerDegreeLng = METERS_PER_DEGREE.lat * cosLat;

        let dLng = (velocity.x * deltaTime) / metersPerDegreeLng;
        let dLat = (velocity.y * deltaTime) / METERS_PER_DEGREE.lat;

        // Check collision
        const proposedLng = lng + dLng;
        const proposedLat = lat + dLat;
        const collision = checkCollision(proposedLng, proposedLat, PLAYER_RADIUS_DEGREES);

        if (collision.collides && collision.normal) {
          const velocityVec = { x: velocity.x, y: velocity.y };
          const slidVelocity = slideAlongWall(velocityVec, collision.normal);

          dLng = (slidVelocity.x * deltaTime) / metersPerDegreeLng;
          dLat = (slidVelocity.y * deltaTime) / METERS_PER_DEGREE.lat;

          const slidCollision = checkCollision(lng + dLng, lat + dLat, PLAYER_RADIUS_DEGREES);
          if (slidCollision.collides) {
            dLng = 0;
            dLat = 0;
          }
        }

        newViewState = cameraController.setPosition(newViewState, lng + dLng, lat + dLat);

        // Terrain following
        const groundElevation = getElevation(
          newViewState.position[0],
          newViewState.position[1]
        );
        newViewState = cameraController.setAltitude(
          newViewState,
          groundElevation,
          CONFIG.player.eyeHeight,
          0.7
        );
      }

      if (newViewState !== viewState) {
        setViewState(newViewState);
      }
    },
    [viewState, keyboard, isLocked, consumeDelta, checkCollision, getElevation]
  );

  useGameLoop(gameLoop, isLocked);

  // Load building data
  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      try {
        onLoadProgress?.(10);

        const result = await loadBuildings(CONFIG.data.buildings, (progress) => {
          onLoadProgress?.(10 + progress * 0.8);
        });

        if (!cancelled) {
          setBuildings(result.features);
          console.log(`Loaded ${result.stats.count} buildings`);
          console.log(`Height range: ${result.stats.minHeight.toFixed(1)}-${result.stats.maxHeight.toFixed(1)}m`);
        }
      } catch (error) {
        if (!cancelled) {
          console.warn('Could not load buildings:', error);
          // Continue without buildings
        }
      }

      if (!cancelled) {
        setIsReady(true);
        onLoadProgress?.(100);
      }
    }

    loadData();

    return () => {
      cancelled = true;
    };
  }, [onLoadProgress]);

  // Handle escape and minimap toggle
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isLocked) {
        exitLock();
      }
      if (e.key === 'm' || e.key === 'M') {
        setShowMinimap((prev) => !prev);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isLocked, exitLock]);

  return (
    <div
      ref={containerRef}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        cursor: isLocked ? 'none' : isReady ? 'crosshair' : 'wait',
      }}
    >
      <DeckGL
        views={view}
        viewState={viewState}
        onViewStateChange={() => {}}
        controller={false}
        layers={layers}
        effects={[lightingEffect]}
        onClick={() => {
          if (isReady && !isLocked) {
            requestLock();
          }
        }}
        style={{ background: 'linear-gradient(to bottom, #1a1a2e 0%, #16213e 100%)' }}
      />

      {/* Minimap */}
      {isReady && showMinimap && (
        <Minimap
          playerPosition={viewState.position}
          playerBearing={viewState.bearing}
          buildings={buildings}
        />
      )}

      {/* Crosshair */}
      {isReady && isLocked && <div className="crosshair" />}

      {/* Controls hint */}
      {isReady && (
        <div className="controls-hint">
          {!isLocked ? (
            <p>Click to start</p>
          ) : (
            <>
              <p>
                <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> Move
                {' '}
                <kbd>Shift</kbd> Run
              </p>
              <p><kbd>Mouse</kbd> Look</p>
              <p><kbd>M</kbd> Toggle minimap</p>
              <p><kbd>Esc</kbd> Release cursor</p>
            </>
          )}
        </div>
      )}

      {/* Debug panel */}
      {CONFIG.debug.showDebugPanel && isReady && (
        <div className="debug-panel">
          <p>Position: {viewState.position.map((n) => n.toFixed(5)).join(', ')}</p>
          <p>Bearing: {viewState.bearing.toFixed(1)}° Pitch: {viewState.pitch.toFixed(1)}°</p>
          <p>Buildings: {buildings?.length ?? 0}</p>
          <p>Collision: {collisionReady ? 'Ready' : 'Loading'}</p>
        </div>
      )}
    </div>
  );
}
```

**Verification:**
- [ ] File updated at `src/components/ZurichViewer/ZurichViewer.tsx`

---

## Verification Checklist

After completing all tasks:

- [ ] `src/layers/BuildingsLayer.ts` exists
- [ ] `src/layers/TerrainLayer.ts` exists
- [ ] `src/layers/MinimapLayers.ts` exists
- [ ] `src/layers/index.ts` exists
- [ ] `src/components/Minimap/Minimap.tsx` exists
- [ ] `src/components/Minimap/index.ts` exists
- [ ] `src/lib/data/buildings.ts` exists
- [ ] `src/lib/data/index.ts` exists
- [ ] `src/components/ZurichViewer/ZurichViewer.tsx` updated
- [ ] `pnpm type-check` passes

## Type Check Command
```bash
cd /Users/claudioromano/Documents/livemap/zuri-3d && pnpm type-check
```

## Files Created

```
src/
├── layers/
│   ├── BuildingsLayer.ts
│   ├── TerrainLayer.ts
│   ├── MinimapLayers.ts
│   └── index.ts
├── components/
│   ├── Minimap/
│   │   ├── Minimap.tsx
│   │   └── index.ts
│   └── ZurichViewer/
│       └── ZurichViewer.tsx (updated)
└── lib/
    └── data/
        ├── buildings.ts
        └── index.ts
```

## Current State After Phase 5

The application now has:
- 3D extruded buildings with lighting
- Ground plane terrain
- Navigation minimap with player position and view cone
- Building data loading with progress
- Toggle minimap with M key

## Next Phase
After verification, read and execute: `.claude/plans/phases/06-polish.md`
