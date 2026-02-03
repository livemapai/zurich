/**
 * GameUI - Game User Interface Overlay
 *
 * Provides UI elements for the game mode:
 * - Crosshair
 * - Controls hints
 * - Debug information
 */

import { CONFIG } from '@/lib/config';

interface GameUIProps {
  /** Whether the game is active (pointer locked) */
  isStarted: boolean;
  /** Whether loading is complete */
  isLoading: boolean;
  /** Callback to start the game */
  onStart: () => void;
  /** Player position for debug display */
  playerPos?: { lng: number; lat: number; alt: number };
  /** Debug stats */
  stats?: {
    buildings?: number;
    trees?: number;
    lights?: number;
  };
}

/**
 * Crosshair overlay shown when playing
 */
function Crosshair() {
  return <div className="crosshair" />;
}

/**
 * Controls hint shown before game starts
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

/**
 * Debug panel with game stats
 */
function DebugPanel({
  isStarted,
  playerPos,
  stats,
}: {
  isStarted: boolean;
  playerPos?: { lng: number; lat: number; alt: number };
  stats?: { buildings?: number; trees?: number; lights?: number };
}) {
  return (
    <div className="debug-panel">
      <div>R3F Game Mode</div>
      <div>Started: {isStarted ? 'Yes' : 'No'}</div>
      {playerPos && (
        <>
          <div>
            Pos: [{playerPos.lng.toFixed(5)}, {playerPos.lat.toFixed(5)}]
          </div>
          <div>Alt: {playerPos.alt.toFixed(1)}m</div>
        </>
      )}
      {stats && (
        <>
          <div>Buildings: {stats.buildings ?? 0}</div>
          <div>Trees: {stats.trees ?? 0}</div>
          <div>Lights: {stats.lights ?? 0}</div>
        </>
      )}
      <div className="debug-panel-hint">Press ` to toggle debug</div>
    </div>
  );
}

/**
 * GameUI - Main UI overlay component
 */
export function GameUI({ isStarted, isLoading, onStart, playerPos, stats }: GameUIProps) {
  return (
    <>
      {/* Crosshair when playing */}
      {isStarted && <Crosshair />}

      {/* Controls hint when not started */}
      {!isLoading && !isStarted && <ControlsHint onStart={onStart} />}

      {/* Debug panel */}
      {CONFIG.debug.showDebugPanel && !isLoading && (
        <DebugPanel isStarted={isStarted} playerPos={playerPos} stats={stats} />
      )}
    </>
  );
}

export default GameUI;
