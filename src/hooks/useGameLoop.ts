/**
 * useGameLoop - RequestAnimationFrame-based game loop
 *
 * Provides a stable animation loop with delta time calculation.
 * Pauses when tab is not visible to save resources.
 */

import { useEffect, useRef, useCallback } from 'react';

interface UseGameLoopOptions {
  /** Callback called each frame with delta time */
  onFrame: (deltaTime: number) => void;
  /** Enable/disable the game loop */
  enabled?: boolean;
  /** Maximum delta time to prevent large jumps (default: 0.1s) */
  maxDeltaTime?: number;
}

/**
 * Hook to run a game loop using requestAnimationFrame
 */
export function useGameLoop(options: UseGameLoopOptions): void {
  const { onFrame, enabled = true, maxDeltaTime = 0.1 } = options;

  // Store callback in ref to avoid re-creating effect on callback change
  const onFrameRef = useRef(onFrame);
  onFrameRef.current = onFrame;

  // Track last frame time
  const lastTimeRef = useRef<number | null>(null);

  // Track animation frame ID for cleanup
  const frameIdRef = useRef<number | null>(null);

  // Track if loop is running
  const runningRef = useRef(false);

  const loop = useCallback(
    (timestamp: number) => {
      if (!runningRef.current) return;

      // Calculate delta time
      if (lastTimeRef.current === null) {
        lastTimeRef.current = timestamp;
      }

      const deltaMs = timestamp - lastTimeRef.current;
      lastTimeRef.current = timestamp;

      // Convert to seconds and clamp
      const deltaTime = Math.min(deltaMs / 1000, maxDeltaTime);

      // Call frame handler
      onFrameRef.current(deltaTime);

      // Schedule next frame
      frameIdRef.current = requestAnimationFrame(loop);
    },
    [maxDeltaTime]
  );

  useEffect(() => {
    if (!enabled) {
      runningRef.current = false;
      if (frameIdRef.current !== null) {
        cancelAnimationFrame(frameIdRef.current);
        frameIdRef.current = null;
      }
      lastTimeRef.current = null;
      return;
    }

    // Start the loop
    runningRef.current = true;
    lastTimeRef.current = null;
    frameIdRef.current = requestAnimationFrame(loop);

    // Handle visibility changes
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Pause when hidden
        runningRef.current = false;
        if (frameIdRef.current !== null) {
          cancelAnimationFrame(frameIdRef.current);
          frameIdRef.current = null;
        }
      } else if (enabled) {
        // Resume when visible
        runningRef.current = true;
        lastTimeRef.current = null; // Reset time to avoid large delta
        frameIdRef.current = requestAnimationFrame(loop);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      runningRef.current = false;
      if (frameIdRef.current !== null) {
        cancelAnimationFrame(frameIdRef.current);
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [enabled, loop]);
}

/**
 * Calculate frames per second from delta time
 */
export function deltaTimeToFps(deltaTime: number): number {
  return deltaTime > 0 ? 1 / deltaTime : 0;
}
