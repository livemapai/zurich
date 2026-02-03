import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import DeckGL from '@deck.gl/react';
import { FirstPersonView } from '@deck.gl/core';
import type { FirstPersonViewState, BuildingCollection, TreeCollection, LightCollection, TramTrackCollection, OverheadPoleCollection, LngLat } from '@/types';
import type { FountainCollection, BenchCollection } from '@/layers';
import { ZURICH_CENTER, ZURICH_BASE_ELEVATION } from '@/types';
import { CONFIG } from '@/lib/config';
import {
  useKeyboardState,
  useMouseLook,
  useGameLoop,
  useCollisionDetection,
  useTerrainElevation,
  useAltitudeSystem,
  useSunLighting,
  deltaTimeToFps,
} from '@/hooks';
import {
  calculateVelocity,
  hasMovementInput,
  applyMouseDelta,
  setPosition,
} from '@/systems';
import {
  createBuildingsLayer,
  createMapTileLayer,
  createTreesLayer,
  createLightsLayer,
  createMapterhornTerrainLayer,
  createTramTracksLayer,
  createOverheadPolesLayer,
  createFountainsLayer,
  createBenchesLayer,
  TEXTURE_PROVIDERS,
  SWISS_ZOOM_THRESHOLD,
  type TextureProviderId,
} from '@/layers';
import { calculateEffectiveZoom } from '@/utils';
import { Minimap } from '@/components/Minimap';
import { LayerPanel, type LayerDefinition } from '@/components/LayerPanel';
import { TimeSlider } from '@/components/TimeSlider';

interface ZurichViewerProps {
  onLoadProgress?: (progress: number) => void;
  onError?: (error: Error) => void;
}

/**
 * Initial view state for deck.gl FirstPersonView
 *
 * longitude/latitude: Geographic anchor in WGS84 degrees
 * position: Meter offset from anchor [east, north, up]
 * Altitude = ground (0) + eye height (1.7m) = 1.7m (standing on ground)
 */
const INITIAL_VIEW_STATE: FirstPersonViewState = {
  longitude: ZURICH_CENTER[0], // 8.5437
  latitude: ZURICH_CENTER[1], // 47.3739
  position: [0, 0, ZURICH_BASE_ELEVATION + CONFIG.player.eyeHeight], // 0 + 1.7 = 1.7m
  bearing: 0, // Facing North
  pitch: 0, // Looking at horizon
  fov: CONFIG.render.fov,
  near: CONFIG.render.near,
  far: CONFIG.render.far,
};

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
  const [trees, setTrees] = useState<TreeCollection | undefined>();
  const [lights, setLights] = useState<LightCollection | undefined>();
  const [tramTracks, setTramTracks] = useState<TramTrackCollection | undefined>();
  const [tramPoles, setTramPoles] = useState<OverheadPoleCollection | undefined>();
  const [fountains, setFountains] = useState<FountainCollection | undefined>();
  const [benches, setBenches] = useState<BenchCollection | undefined>();
  const [fps, setFps] = useState(0);

  // Debug state
  const [showDebug, setShowDebug] = useState(CONFIG.debug.showDebugPanel);

  // Minimap state
  const [showMinimap, setShowMinimap] = useState(true);

  // Layer panel state
  const [showLayerPanel, setShowLayerPanel] = useState(true);

  // Time of day state (default: noon = 12:00 = 720 minutes)
  const [timeOfDay, setTimeOfDay] = useState(12 * 60);
  const [showTimeSlider, setShowTimeSlider] = useState(true);
  const [layerVisibility, setLayerVisibility] = useState<Record<string, boolean>>({
    terrain3d: true,
    mapTiles: false,
    buildings: true,
    trees: true,
    lights: true,
    tramTracks: true,
    tramPoles: true,
    fountains: true,
    benches: true,
  });
  const [terrainTexture, setTerrainTexture] = useState<TextureProviderId>('osm');

  // Calculate effective zoom level for hybrid texture switching
  // This converts FirstPersonView altitude + FOV to equivalent map zoom level
  const effectiveZoom = useMemo(() => {
    return calculateEffectiveZoom(
      viewState.position[2],
      ZURICH_BASE_ELEVATION,
      typeof window !== 'undefined' ? window.innerHeight : 720,
      viewState.fov ?? CONFIG.render.fov
    );
  }, [viewState.position[2], viewState.fov]);

  // Resolve texture URL with hybrid logic for swissimage
  // Falls back to Esri at low zoom because swisstopo only covers Switzerland
  const resolvedTextureUrl = useMemo(() => {
    if (terrainTexture === 'swissimage' && effectiveZoom < SWISS_ZOOM_THRESHOLD) {
      // Use Esri satellite for wide views (swisstopo returns 400 outside Swiss bounds)
      return TEXTURE_PROVIDERS.satellite.url;
    }
    return TEXTURE_PROVIDERS[terrainTexture].url;
  }, [terrainTexture, effectiveZoom]);

  // Input hooks - use getKeyboard() getter for stable reference in game loop
  const { getKeyboard } = useKeyboardState({
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

  // Altitude system - centralized altitude management
  const { applyVerticalVelocity, smoothToTerrain, getMinAltitude } = useAltitudeSystem({
    getGroundElevation: getElevationOrDefault,
  });

  // Dynamic sun lighting based on time of day
  const { lightingEffect, lighting } = useSunLighting(timeOfDay);

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
          onLoadProgress?.(60);
        }
      } catch (err) {
        if (!cancelled) {
          console.warn('Failed to load buildings:', err);
          // Continue without buildings - collision will be disabled
          onLoadProgress?.(60);
        }
      }
    };

    onLoadProgress?.(10);
    loadBuildings();

    return () => {
      cancelled = true;
    };
  }, [onLoadProgress]);

  // Load trees data
  useEffect(() => {
    let cancelled = false;

    const loadTrees = async () => {
      try {
        const response = await fetch(CONFIG.data.trees);
        if (!response.ok) {
          throw new Error(`Failed to load trees: ${response.status}`);
        }
        const data: TreeCollection = await response.json();

        if (!cancelled) {
          setTrees(data);
          onLoadProgress?.(70);
        }
      } catch (err) {
        if (!cancelled) {
          console.warn('Failed to load trees:', err);
          // Continue without trees
          onLoadProgress?.(70);
        }
      }
    };

    loadTrees();

    return () => {
      cancelled = true;
    };
  }, [onLoadProgress]);

  // Load lights data
  useEffect(() => {
    let cancelled = false;

    const loadLights = async () => {
      try {
        const response = await fetch(CONFIG.data.lights);
        if (!response.ok) {
          throw new Error(`Failed to load lights: ${response.status}`);
        }
        const data: LightCollection = await response.json();

        if (!cancelled) {
          setLights(data);
          onLoadProgress?.(75);
        }
      } catch (err) {
        if (!cancelled) {
          console.warn('Failed to load lights:', err);
          // Continue without lights
          onLoadProgress?.(75);
        }
      }
    };

    loadLights();

    return () => {
      cancelled = true;
    };
  }, [onLoadProgress]);

  // Load tram tracks data
  useEffect(() => {
    let cancelled = false;

    const loadTramTracks = async () => {
      try {
        const response = await fetch(CONFIG.data.tramTracks);
        if (!response.ok) {
          throw new Error(`Failed to load tram tracks: ${response.status}`);
        }
        const data: TramTrackCollection = await response.json();

        if (!cancelled) {
          setTramTracks(data);
          onLoadProgress?.(85);
        }
      } catch (err) {
        if (!cancelled) {
          console.warn('Failed to load tram tracks:', err);
          // Continue without tram tracks
          onLoadProgress?.(85);
        }
      }
    };

    loadTramTracks();

    return () => {
      cancelled = true;
    };
  }, [onLoadProgress]);

  // Load tram poles data
  useEffect(() => {
    let cancelled = false;

    const loadTramPoles = async () => {
      try {
        const response = await fetch(CONFIG.data.tramPoles);
        if (!response.ok) {
          throw new Error(`Failed to load tram poles: ${response.status}`);
        }
        const data: OverheadPoleCollection = await response.json();

        if (!cancelled) {
          setTramPoles(data);
          onLoadProgress?.(95);
        }
      } catch (err) {
        if (!cancelled) {
          console.warn('Failed to load tram poles:', err);
          // Continue without tram poles
          onLoadProgress?.(95);
        }
      }
    };

    loadTramPoles();

    return () => {
      cancelled = true;
    };
  }, [onLoadProgress]);

  // Load fountains data
  useEffect(() => {
    let cancelled = false;

    const loadFountains = async () => {
      try {
        const response = await fetch(CONFIG.data.fountains);
        if (!response.ok) {
          throw new Error(`Failed to load fountains: ${response.status}`);
        }
        const data: FountainCollection = await response.json();

        if (!cancelled) {
          setFountains(data);
        }
      } catch (err) {
        if (!cancelled) {
          console.warn('Failed to load fountains:', err);
          // Continue without fountains
        }
      }
    };

    loadFountains();

    return () => {
      cancelled = true;
    };
  }, []);

  // Load benches data
  useEffect(() => {
    let cancelled = false;

    const loadBenches = async () => {
      try {
        const response = await fetch(CONFIG.data.benches);
        if (!response.ok) {
          throw new Error(`Failed to load benches: ${response.status}`);
        }
        const data: BenchCollection = await response.json();

        if (!cancelled) {
          setBenches(data);
        }
      } catch (err) {
        if (!cancelled) {
          console.warn('Failed to load benches:', err);
          // Continue without benches
        }
      }
    };

    loadBenches();

    return () => {
      cancelled = true;
    };
  }, []);

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

  // Throttle FPS updates to reduce re-renders (update every 500ms instead of every frame)
  const lastFpsUpdateRef = useRef(0);

  // Game loop - runs every frame
  const handleFrame = useCallback(
    (deltaTime: number) => {
      // Throttle FPS updates to reduce re-renders (every 500ms instead of every frame)
      const now = performance.now();
      if (now - lastFpsUpdateRef.current > 500) {
        setFps(deltaTimeToFps(deltaTime));
        lastFpsUpdateRef.current = now;
      }

      let newViewState = viewStateRef.current;

      // 1. Apply mouse look if pointer is locked
      if (isLocked) {
        const mouseDelta = consumeDelta();
        if (mouseDelta.x !== 0 || mouseDelta.y !== 0) {
          newViewState = applyMouseDelta(newViewState, mouseDelta);
        }
      }

      // 2. Get current keyboard state (always fresh via getter)
      const keyboard = getKeyboard();

      // 3. Calculate velocity from keyboard input
      // Pass altitude and terrain elevation for flight speed calculation
      const currentAltitude = newViewState.position[2];
      const groundElevation = getElevationOrDefault([
        newViewState.longitude,
        newViewState.latitude,
      ]);
      const velocity = calculateVelocity(
        keyboard,
        newViewState.bearing,
        currentAltitude,
        groundElevation
      );

      // 4. Apply movement with collision detection
      if (hasMovementInput(keyboard)) {
        const currentPos: LngLat = [
          newViewState.longitude,
          newViewState.latitude,
        ];

        // Get current altitude for 3D collision detection
        // This allows players to fly over buildings when at sufficient altitude
        const currentAltitude = newViewState.position[2];

        // Move with collision detection (returns new position)
        // Pass altitude so collision system can filter out buildings we're above
        const newPos = moveWithCollision(currentPos, velocity, deltaTime, currentAltitude);

        // Update position if it changed
        if (newPos[0] !== currentPos[0] || newPos[1] !== currentPos[1]) {
          newViewState = setPosition(newViewState, newPos[0], newPos[1]);
        }

        // 5. Apply altitude changes via centralized AltitudeSystem
        const currentPosition: LngLat = [newViewState.longitude, newViewState.latitude];
        const isFlying = velocity.z !== 0;
        const minAltitude = getMinAltitude(currentPosition);
        const isNearGround = newViewState.position[2] < minAltitude + 0.5;

        const newAltitude = isFlying
          ? // Flying: apply vertical velocity with clamping
            applyVerticalVelocity(
              newViewState.position[2],
              velocity.z,
              deltaTime,
              currentPosition
            )
          : isNearGround
            ? // Walking: smooth terrain following when near ground
              smoothToTerrain(newViewState.position[2], currentPosition, 0.7)
            : // Maintain altitude when in air (hovering)
              newViewState.position[2];

        newViewState = {
          ...newViewState,
          position: [0, 0, newAltitude] as [number, number, number],
        };
      }

      // 6. Update view state if changed
      if (newViewState !== viewStateRef.current) {
        setViewState(newViewState);
      }
    },
    [isLocked, consumeDelta, getKeyboard, moveWithCollision, applyVerticalVelocity, smoothToTerrain, getMinAltitude, getElevationOrDefault]
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

  // Toggle debug panel with backtick key, minimap with M key, layers with L key, time slider with T key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Backquote') {
        setShowDebug((prev) => !prev);
      }
      if (e.code === 'KeyM') {
        setShowMinimap((prev) => !prev);
      }
      if (e.code === 'KeyL') {
        setShowLayerPanel((prev) => !prev);
      }
      if (e.code === 'KeyT') {
        setShowTimeSlider((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Handle layer toggle
  const handleLayerToggle = useCallback((layerId: string) => {
    setLayerVisibility((prev) => ({
      ...prev,
      [layerId]: !prev[layerId],
    }));
  }, []);

  // Build layer definitions for LayerPanel
  const layerDefinitions = useMemo<LayerDefinition[]>(() => [
    {
      id: 'terrain3d',
      name: '3D Terrain',
      category: 'Base Map',
      visible: layerVisibility.terrain3d ?? true,
    },
    {
      id: 'mapTiles',
      name: 'Flat Map Tiles',
      category: 'Base Map',
      visible: layerVisibility.mapTiles ?? false,
    },
    {
      id: 'buildings',
      name: 'Buildings',
      category: 'Infrastructure',
      visible: layerVisibility.buildings ?? true,
      count: buildings?.features?.length,
    },
    {
      id: 'trees',
      name: 'Trees',
      category: 'Nature',
      visible: layerVisibility.trees ?? true,
      count: trees?.features?.length,
    },
    {
      id: 'lights',
      name: 'Street Lights',
      category: 'Infrastructure',
      visible: layerVisibility.lights ?? true,
      count: lights?.features?.length,
    },
    {
      id: 'tramTracks',
      name: 'Tram Tracks',
      category: 'Transit',
      visible: layerVisibility.tramTracks ?? true,
      count: tramTracks?.features?.length,
    },
    {
      id: 'tramPoles',
      name: 'Overhead Poles',
      category: 'Transit',
      visible: layerVisibility.tramPoles ?? true,
      count: tramPoles?.features?.length,
    },
    {
      id: 'fountains',
      name: 'Fountains',
      category: 'Infrastructure',
      visible: layerVisibility.fountains ?? true,
      count: fountains?.features?.length,
    },
    {
      id: 'benches',
      name: 'Benches',
      category: 'Infrastructure',
      visible: layerVisibility.benches ?? true,
      count: benches?.features?.length,
    },
  ], [layerVisibility, buildings?.features?.length, trees?.features?.length, lights?.features?.length, tramTracks?.features?.length, tramPoles?.features?.length, fountains?.features?.length, benches?.features?.length]);

  // FirstPersonView configuration - memoized to avoid recreation on every render
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

  // Create rendering layers
  // Note: Terrain elevation is pre-computed in GeoJSON properties (by scripts/terrain/add_elevations.py)
  const layers = useMemo(() => {
    const result = [];

    // Base map layer - use 3D terrain OR flat map tiles (not both to avoid z-fighting)
    if (layerVisibility.terrain3d) {
      result.push(
        createMapterhornTerrainLayer({
          textureUrl: resolvedTextureUrl,
        })
      );
    } else if (layerVisibility.mapTiles) {
      result.push(createMapTileLayer());
    }

    // Buildings (if loaded and visible)
    if (buildings?.features?.length && layerVisibility.buildings) {
      result.push(createBuildingsLayer(buildings.features));
    }

    // Trees (if loaded and visible)
    if (trees?.features?.length && layerVisibility.trees) {
      result.push(createTreesLayer(trees.features));
    }

    // Lights (if loaded and visible)
    if (lights?.features?.length && layerVisibility.lights) {
      result.push(createLightsLayer(lights.features));
    }

    // Tram tracks (if loaded and visible)
    if (tramTracks?.features?.length && layerVisibility.tramTracks) {
      result.push(createTramTracksLayer(tramTracks.features));
    }

    // Overhead poles (if loaded and visible)
    if (tramPoles?.features?.length && layerVisibility.tramPoles) {
      result.push(createOverheadPolesLayer(tramPoles.features));
    }

    // Fountains (if loaded and visible)
    if (fountains?.features?.length && layerVisibility.fountains) {
      result.push(createFountainsLayer(fountains.features));
    }

    // Benches (if loaded and visible)
    if (benches?.features?.length && layerVisibility.benches) {
      result.push(createBenchesLayer(benches.features));
    }

    return result;
  }, [buildings, trees, lights, tramTracks, tramPoles, fountains, benches, layerVisibility, resolvedTextureUrl]);

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
        style={{ background: lighting.skyColor }}
      />

      {/* Minimap */}
      <Minimap
        playerLongitude={viewState.longitude}
        playerLatitude={viewState.latitude}
        playerBearing={viewState.bearing}
        buildings={buildings?.features}
        visible={showMinimap}
      />

      {/* Layer Panel */}
      <LayerPanel
        layers={layerDefinitions}
        onToggle={handleLayerToggle}
        visible={showLayerPanel}
        terrainTexture={terrainTexture}
        onTextureChange={setTerrainTexture}
      />

      {/* Time Slider */}
      <TimeSlider
        value={timeOfDay}
        onChange={setTimeOfDay}
        visible={showTimeSlider}
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
            <kbd>Q</kbd>
            <kbd>E</kbd> Fly up/down
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
            <kbd>L</kbd> Toggle layers
          </p>
          <p>
            <kbd>T</kbd> Toggle time slider
          </p>
          <p>
            <kbd>Esc</kbd> Release cursor
          </p>
        </div>
      )}

      {/* Debug panel */}
      {showDebug && (
        <div className="debug-panel">
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
          <div className="debug-panel-hint">Press ` to toggle debug</div>
        </div>
      )}
    </div>
  );
}
