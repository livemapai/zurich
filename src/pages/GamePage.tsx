/**
 * GamePage - React Three Fiber Game Experience
 *
 * A game-ready 3D walkthrough using react-three-fiber with:
 * - Physics-based collision via @react-three/rapier
 * - Post-processing effects (SSAO, Bloom)
 * - Instanced rendering for trees and lights
 *
 * Route: /game
 */

import { Suspense, useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { Physics } from '@react-three/rapier';
import { CONFIG } from '@/lib/config';
import { Scene, TileGround, Buildings, BuildingColliders, Trees, StreetLights, Player, AdaptiveEffects } from '@/r3f';
import { useTerrainElevation } from '@/hooks/useTerrainElevation';
import type { BuildingCollection, TreeCollection, LightCollection } from '@/types';

/**
 * Loading screen shown while 3D assets load
 */
function LoadingScreen({ progress, status }: { progress: number; status: string }) {
  return (
    <div className="loading-overlay">
      <p className="loading-text">Loading Game...</p>
      <div className="loading-progress">
        <div className="loading-progress-bar" style={{ width: `${progress}%` }} />
      </div>
      <p style={{ marginTop: '0.5rem', fontSize: '0.875rem', opacity: 0.7 }}>
        {status}
      </p>
    </div>
  );
}

/** Type for elevation callback */
type ElevationCallback = (lng: number, lat: number) => number;

/** Props for GameScene */
interface GameSceneProps {
  buildings: BuildingCollection | null;
  trees: TreeCollection | null;
  lights: LightCollection | null;
  isStarted: boolean;
  /** Player position [lng, lat] for distance-based rendering */
  playerPosition: [number, number];
  onPositionChange?: (pos: { lng: number; lat: number; alt: number }) => void;
  /** Callback to get terrain elevation at [lng, lat] */
  getElevation?: ElevationCallback;
}

/**
 * Game scene content - contains all 3D objects
 */
function GameScene({ buildings, trees, lights, isStarted, playerPosition, onPositionChange, getElevation }: GameSceneProps) {
  return (
    <Scene>
      {/* OSM tile ground layer */}
      <TileGround zoom={17} radius={4} receiveShadow />

      {/* Buildings (visual mesh) - distance filtered with terrain elevation */}
      {buildings && buildings.features.length > 0 && (
        <Buildings features={buildings.features} playerPosition={playerPosition} getElevation={getElevation} />
      )}

      {/* Trees (instanced mesh) - distance filtered with terrain elevation */}
      {trees && trees.features.length > 0 && (
        <Trees features={trees.features} playerPosition={playerPosition} getElevation={getElevation} />
      )}

      {/* Street Lights (instanced mesh) - distance filtered with terrain elevation */}
      {lights && lights.features.length > 0 && (
        <StreetLights features={lights.features} playerPosition={playerPosition} getElevation={getElevation} />
      )}

      {/* Physics world with player and building colliders */}
      {/* Using updateLoop="independent" decouples physics from render loop for smoother movement */}
      <Physics gravity={[0, -9.81, 0]} debug={false} updateLoop="independent">
        {/* Player with first-person camera and physics */}
        <Player enabled={isStarted} onPositionChange={onPositionChange} />

        {/* Building colliders for collision detection - terrain elevation for accurate collision */}
        {buildings && buildings.features.length > 0 && (
          <BuildingColliders features={buildings.features} playerPosition={playerPosition} getElevation={getElevation} />
        )}
      </Physics>

      {/* Post-processing effects with adaptive quality */}
      <AdaptiveEffects bloomIntensity={0.3} />
    </Scene>
  );
}

/**
 * Controls hint overlay
 */
function ControlsHint({ onStart }: { onStart: () => void }) {
  return (
    <div className="controls-hint">
      <p style={{ marginBottom: '1rem', fontSize: '1.25rem' }}>R3F Game Mode</p>
      <button
        onClick={onStart}
        style={{
          padding: '0.75rem 1.5rem',
          background: '#4a9eff',
          border: 'none',
          borderRadius: '4px',
          color: 'white',
          cursor: 'pointer',
          fontSize: '1rem',
          marginBottom: '1rem',
        }}
      >
        Click to Start
      </button>
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
        <kbd>Esc</kbd> Release cursor
      </p>
      <p style={{ marginTop: '1rem', opacity: 0.7, fontSize: '0.875rem' }}>
        <a href="/viewer" style={{ color: '#4a9eff' }}>
          ← Back to deck.gl viewer
        </a>
      </p>
    </div>
  );
}

export function GamePage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadProgress, setLoadProgress] = useState(0);
  const [loadStatus, setLoadStatus] = useState('Initializing...');
  const [isStarted, setIsStarted] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Data state
  const [buildings, setBuildings] = useState<BuildingCollection | null>(null);
  const [trees, setTrees] = useState<TreeCollection | null>(null);
  const [lights, setLights] = useState<LightCollection | null>(null);

  // Player position state for debug panel and distance filtering
  // Initialize to Zurich center
  const [playerPos, setPlayerPos] = useState({ lng: 8.5437, lat: 47.3739, alt: 0 });

  // Memoized player position tuple for distance filtering (to prevent unnecessary recalcs)
  const playerPosTuple: [number, number] = useMemo(
    () => [playerPos.lng, playerPos.lat],
    [playerPos.lng, playerPos.lat]
  );

  // Terrain elevation hook for placing objects on terrain
  const { getElevationOrDefault, isLoaded: terrainLoaded } = useTerrainElevation();

  // Memoized elevation callback to prevent unnecessary re-renders
  const getElevation = useCallback(
    (lng: number, lat: number) => getElevationOrDefault([lng, lat]),
    [getElevationOrDefault]
  );

  // Load all data
  useEffect(() => {
    let cancelled = false;

    const loadData = async () => {
      try {
        // Load buildings
        setLoadStatus('Loading buildings...');
        setLoadProgress(10);

        const buildingsResponse = await fetch(CONFIG.data.buildings);
        if (!buildingsResponse.ok) {
          throw new Error(`Failed to load buildings: ${buildingsResponse.status}`);
        }
        const buildingsData: BuildingCollection = await buildingsResponse.json();

        if (!cancelled) {
          setBuildings(buildingsData);
          setLoadStatus(`Loaded ${buildingsData.features.length} buildings`);
          setLoadProgress(40);
        }

        // Load trees
        setLoadStatus('Loading trees...');
        const treesResponse = await fetch(CONFIG.data.trees);
        if (treesResponse.ok) {
          const treesData: TreeCollection = await treesResponse.json();
          if (!cancelled) {
            setTrees(treesData);
            setLoadStatus(`Loaded ${treesData.features.length} trees`);
          }
        }
        setLoadProgress(60);

        // Load lights
        setLoadStatus('Loading street lights...');
        const lightsResponse = await fetch(CONFIG.data.lights);
        if (lightsResponse.ok) {
          const lightsData: LightCollection = await lightsResponse.json();
          if (!cancelled) {
            setLights(lightsData);
            setLoadStatus(`Loaded ${lightsData.features.length} lights`);
          }
        }
        setLoadProgress(80);

        // Complete loading
        if (!cancelled) {
          setTimeout(() => {
            if (!cancelled) {
              setLoadProgress(100);
              setLoadStatus('Ready!');
              setIsLoading(false);
            }
          }, 500);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to load data:', err);
          setError(err instanceof Error ? err : new Error('Failed to load data'));
          setIsLoading(false);
        }
      }
    };

    loadData();

    return () => {
      cancelled = true;
    };
  }, []);

  const handleStart = useCallback(() => {
    setIsStarted(true);
    // Delay pointer lock request to ensure Canvas is fully mounted and ready
    // This prevents silent failures when requestPointerLock is called too early
    setTimeout(() => {
      // IMPORTANT: Request lock on the CANVAS element, not the container div.
      // usePlayerCamera checks `document.pointerLockElement === gl.domElement` (canvas),
      // so we must lock the canvas for mouse look to work.
      const canvas = containerRef.current?.querySelector('canvas');
      canvas?.requestPointerLock();
    }, 100);
  }, []);

  // Handle pointer lock change
  useEffect(() => {
    const handlePointerLockChange = () => {
      if (!document.pointerLockElement && isStarted) {
        setIsStarted(false);
      }
    };

    document.addEventListener('pointerlockchange', handlePointerLockChange);
    return () => document.removeEventListener('pointerlockchange', handlePointerLockChange);
  }, [isStarted]);

  if (error) {
    return (
      <div
        className="viewport"
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      >
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
    <div
      ref={containerRef}
      className="viewport no-select"
      style={{ cursor: isStarted ? 'none' : 'default' }}
    >
      {/* Loading screen */}
      {isLoading && <LoadingScreen progress={loadProgress} status={loadStatus} />}

      {/* Three.js Canvas */}
      <Canvas
        shadows
        camera={{
          fov: CONFIG.render.fov,
          near: CONFIG.render.near,
          far: CONFIG.render.far,
          position: [0, CONFIG.player.eyeHeight, 0],
        }}
        gl={{
          antialias: true,
          // Logarithmic depth buffer for large geographic scenes
          logarithmicDepthBuffer: true,
        }}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          background: '#16213e',
        }}
        onCreated={() => {
          console.log('R3F Canvas initialized');
        }}
      >
        <Suspense fallback={null}>
          <GameScene
            buildings={buildings}
            trees={trees}
            lights={lights}
            isStarted={isStarted}
            playerPosition={playerPosTuple}
            onPositionChange={setPlayerPos}
            getElevation={terrainLoaded ? getElevation : undefined}
          />
        </Suspense>
      </Canvas>

      {/* Crosshair when playing */}
      {isStarted && <div className="crosshair" />}

      {/* Controls hint when not started */}
      {!isLoading && !isStarted && <ControlsHint onStart={handleStart} />}

      {/* Debug panel */}
      {CONFIG.debug.showDebugPanel && !isLoading && (
        <div className="debug-panel">
          <div>R3F Game Mode</div>
          <div>Started: {isStarted ? 'Yes' : 'No'}</div>
          <div>Pos: [{playerPos.lng.toFixed(5)}, {playerPos.lat.toFixed(5)}]</div>
          <div>Alt: {playerPos.alt.toFixed(1)}m</div>
          <div>Buildings: {buildings?.features.length ?? 0}</div>
          <div>Trees: {trees?.features.length ?? 0}</div>
          <div>Lights: {lights?.features.length ?? 0}</div>
          <div className="debug-panel-hint">Press ` to toggle debug</div>
        </div>
      )}
    </div>
  );
}

export default GamePage;
