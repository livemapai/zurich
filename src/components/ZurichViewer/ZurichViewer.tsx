import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import DeckGL from '@deck.gl/react';
import { FirstPersonView, LightingEffect, AmbientLight, DirectionalLight } from '@deck.gl/core';
import type { FirstPersonViewState, BuildingCollection, LngLat } from '@/types';
import { ZURICH_CENTER } from '@/types';
import { CONFIG } from '@/lib/config';
import {
  useKeyboardState,
  useMouseLook,
  useGameLoop,
  useCollisionDetection,
  useTerrainElevation,
  deltaTimeToFps,
} from '@/hooks';
import {
  calculateVelocity,
  hasMovementInput,
  applyMouseDelta,
  setAltitude,
  setPosition,
} from '@/systems';
import { createBuildingsLayer, createTerrainLayer } from '@/layers';
import { Minimap } from '@/components/Minimap';

interface ZurichViewerProps {
  onLoadProgress?: (progress: number) => void;
  onError?: (error: Error) => void;
}

/**
 * Initial view state for deck.gl FirstPersonView
 *
 * longitude/latitude: Geographic anchor in WGS84 degrees
 * position: Meter offset from anchor [east, north, up]
 */
const INITIAL_VIEW_STATE: FirstPersonViewState = {
  longitude: ZURICH_CENTER[0], // 8.5437
  latitude: ZURICH_CENTER[1], // 47.3739
  position: [0, 0, 1.7], // 0m east, 0m north, 1.7m up (eye height)
  bearing: 0, // Facing North
  pitch: 0, // Looking at horizon
  fov: CONFIG.render.fov,
  near: CONFIG.render.near,
  far: CONFIG.render.far,
};

/**
 * Lighting effect for 3D buildings
 * Creates ambient and directional light for realistic shading
 */
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

/**
 * ZurichViewer - Main 3D viewer component
 *
 * Uses deck.gl FirstPersonView for walkthrough navigation.
 * Integrates WASD movement, mouse look, collision detection, and terrain following.
 */
export function ZurichViewer({ onLoadProgress, onError }: ZurichViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [viewState, setViewState] = useState<FirstPersonViewState>(INITIAL_VIEW_STATE);
  const [isReady, setIsReady] = useState(false);
  const [buildings, setBuildings] = useState<BuildingCollection | undefined>();
  const [fps, setFps] = useState(0);

  // Debug state
  const [showDebug, setShowDebug] = useState(CONFIG.debug.showDebugPanel);

  // Minimap state
  const [showMinimap, setShowMinimap] = useState(true);

  // Input hooks
  const { keyboard } = useKeyboardState({
    enabled: isReady,
  });

  const { isLocked, requestLock, consumeDelta } = useMouseLook({
    targetRef: containerRef,
    enabled: isReady,
  });

  // Collision detection
  const { isLoaded: collisionLoaded, buildingCount, moveWithCollision } =
    useCollisionDetection({
      buildings,
      collisionRadius: CONFIG.player.collisionRadius,
    });

  // Terrain elevation
  const { isLoaded: terrainLoaded, getElevationOrDefault } = useTerrainElevation({
    enabled: isReady,
  });

  // Load building data
  useEffect(() => {
    let cancelled = false;

    const loadBuildings = async () => {
      try {
        const response = await fetch(CONFIG.data.buildings);
        if (!response.ok) {
          throw new Error(`Failed to load buildings: ${response.status}`);
        }
        const data: BuildingCollection = await response.json();

        if (!cancelled) {
          setBuildings(data);
          onLoadProgress?.(80);
        }
      } catch (err) {
        if (!cancelled) {
          console.warn('Failed to load buildings:', err);
          // Continue without buildings - collision will be disabled
          onLoadProgress?.(80);
        }
      }
    };

    onLoadProgress?.(10);
    loadBuildings();

    return () => {
      cancelled = true;
    };
  }, [onLoadProgress]);

  // Mark ready when buildings attempt is complete
  useEffect(() => {
    // Give a small delay after buildings load attempt
    const timer = setTimeout(() => {
      setIsReady(true);
      onLoadProgress?.(100);
    }, 500);

    return () => clearTimeout(timer);
  }, [onLoadProgress]);

  // View state ref for game loop (avoid stale closures)
  const viewStateRef = useRef(viewState);
  viewStateRef.current = viewState;

  // Game loop - runs every frame
  const handleFrame = useCallback(
    (deltaTime: number) => {
      // Update FPS display
      setFps(deltaTimeToFps(deltaTime));

      let newViewState = viewStateRef.current;

      // 1. Apply mouse look if pointer is locked
      if (isLocked) {
        const mouseDelta = consumeDelta();
        if (mouseDelta.x !== 0 || mouseDelta.y !== 0) {
          newViewState = applyMouseDelta(newViewState, mouseDelta);
        }
      }

      // 2. Calculate velocity from keyboard input
      const velocity = calculateVelocity(keyboard, newViewState.bearing);

      // 3. Apply movement with collision detection
      if (hasMovementInput(keyboard)) {
        const currentPos: LngLat = [
          newViewState.longitude,
          newViewState.latitude,
        ];

        // Move with collision detection (returns new position)
        const newPos = moveWithCollision(currentPos, velocity, deltaTime);

        // Update position if it changed
        if (newPos[0] !== currentPos[0] || newPos[1] !== currentPos[1]) {
          newViewState = setPosition(newViewState, newPos[0], newPos[1]);
        }

        // 4. Apply terrain following
        const groundElev = getElevationOrDefault([
          newViewState.longitude,
          newViewState.latitude,
        ]);
        newViewState = setAltitude(
          newViewState,
          groundElev,
          CONFIG.player.eyeHeight,
          0.7 // Smooth factor
        );
      }

      // 5. Update view state if changed
      if (newViewState !== viewStateRef.current) {
        setViewState(newViewState);
      }
    },
    [isLocked, consumeDelta, keyboard, moveWithCollision, getElevationOrDefault]
  );

  // Start game loop
  useGameLoop({
    onFrame: handleFrame,
    enabled: isReady,
  });

  // Handle click to request pointer lock
  const handleClick = useCallback(() => {
    if (isReady && !isLocked) {
      requestLock();
    }
  }, [isReady, isLocked, requestLock]);

  // Toggle debug panel with backtick key and minimap with M key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Backquote') {
        setShowDebug((prev) => !prev);
      }
      if (e.code === 'KeyM') {
        setShowMinimap((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // FirstPersonView configuration
  const view = new FirstPersonView({
    id: 'first-person',
    controller: false,
    fovy: viewState.fov ?? CONFIG.render.fov,
    near: viewState.near ?? CONFIG.render.near,
    far: viewState.far ?? CONFIG.render.far,
  });

  // Create rendering layers
  const layers = useMemo(() => {
    const result = [];

    // Ground plane
    result.push(createTerrainLayer());

    // Buildings (if loaded)
    if (buildings?.features?.length) {
      result.push(createBuildingsLayer(buildings.features));
    }

    return result;
  }, [buildings]);

  return (
    <div
      ref={containerRef}
      onClick={handleClick}
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
        controller={false}
        layers={layers}
        effects={[lightingEffect]}
        onWebGLInitialized={() => {
          console.log('WebGL initialized');
        }}
        onError={(error) => {
          console.error('DeckGL error:', error);
          onError?.(error instanceof Error ? error : new Error(String(error)));
        }}
        style={{ background: '#16213e' }}
      />

      {/* Minimap */}
      <Minimap
        playerLongitude={viewState.longitude}
        playerLatitude={viewState.latitude}
        playerBearing={viewState.bearing}
        buildings={buildings?.features}
        visible={showMinimap}
      />

      {/* Crosshair - shown when locked */}
      {isLocked && <div className="crosshair" />}

      {/* Controls hint - shown when not locked */}
      {isReady && !isLocked && (
        <div className="controls-hint">
          <p>Click to start</p>
          <p>
            <kbd>W</kbd>
            <kbd>A</kbd>
            <kbd>S</kbd>
            <kbd>D</kbd> Move
          </p>
          <p>
            <kbd>Shift</kbd> Run
          </p>
          <p>
            <kbd>Mouse</kbd> Look around
          </p>
          <p>
            <kbd>M</kbd> Toggle minimap
          </p>
          <p>
            <kbd>Esc</kbd> Release cursor
          </p>
        </div>
      )}

      {/* Debug panel */}
      {showDebug && (
        <div
          style={{
            position: 'absolute',
            top: 10,
            left: 10,
            padding: '10px',
            background: 'rgba(0, 0, 0, 0.7)',
            color: '#fff',
            fontFamily: 'monospace',
            fontSize: '12px',
            borderRadius: '4px',
            pointerEvents: 'none',
          }}
        >
          <div>FPS: {fps.toFixed(0)}</div>
          <div>
            Pos: [{viewState.longitude.toFixed(5)}, {viewState.latitude.toFixed(5)}]
          </div>
          <div>Alt: {viewState.position[2].toFixed(1)}m</div>
          <div>Bearing: {viewState.bearing.toFixed(1)}°</div>
          <div>Pitch: {viewState.pitch.toFixed(1)}°</div>
          <div>Locked: {isLocked ? 'Yes' : 'No'}</div>
          <div>Buildings: {buildingCount}</div>
          <div>Collision: {collisionLoaded ? 'Ready' : 'Loading'}</div>
          <div>Terrain: {terrainLoaded ? 'Ready' : 'Default'}</div>
          <div style={{ marginTop: '5px', fontSize: '10px', color: '#888' }}>
            Press ` to toggle debug
          </div>
        </div>
      )}
    </div>
  );
}
