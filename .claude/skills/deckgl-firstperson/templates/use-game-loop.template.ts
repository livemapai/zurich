/**
 * useGameLoop Hook
 *
 * Manages requestAnimationFrame loop with proper timing
 */

import { useEffect, useRef, useCallback } from 'react';

export interface GameLoopCallback {
  (deltaTime: number, totalTime: number): void;
}

export function useGameLoop(
  callback: GameLoopCallback,
  isActive: boolean = true
): void {
  const callbackRef = useRef<GameLoopCallback>(callback);
  const frameRef = useRef<number>();
  const lastTimeRef = useRef<number>();
  const startTimeRef = useRef<number>();

  // Keep callback ref updated without triggering effect
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!isActive) {
      // Reset timing when paused
      lastTimeRef.current = undefined;
      return;
    }

    const loop = (timestamp: number) => {
      // Initialize start time on first frame
      if (startTimeRef.current === undefined) {
        startTimeRef.current = timestamp;
      }

      // Calculate delta time
      if (lastTimeRef.current !== undefined) {
        const deltaMs = timestamp - lastTimeRef.current;

        // Convert to seconds and clamp to avoid huge jumps
        // (e.g., when tab was in background)
        const deltaTime = Math.min(deltaMs / 1000, 0.1);

        const totalTime = (timestamp - startTimeRef.current) / 1000;

        callbackRef.current(deltaTime, totalTime);
      }

      lastTimeRef.current = timestamp;
      frameRef.current = requestAnimationFrame(loop);
    };

    frameRef.current = requestAnimationFrame(loop);

    return () => {
      if (frameRef.current !== undefined) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = undefined;
      }
    };
  }, [isActive]);
}

/**
 * Fixed timestep game loop for physics
 */
export function useFixedGameLoop(
  callback: GameLoopCallback,
  fixedStep: number = 1 / 60,
  isActive: boolean = true
): void {
  const accumulatorRef = useRef(0);

  const wrappedCallback = useCallback(
    (deltaTime: number, totalTime: number) => {
      accumulatorRef.current += deltaTime;

      while (accumulatorRef.current >= fixedStep) {
        callback(fixedStep, totalTime);
        accumulatorRef.current -= fixedStep;
      }
    },
    [callback, fixedStep]
  );

  useGameLoop(wrappedCallback, isActive);
}
