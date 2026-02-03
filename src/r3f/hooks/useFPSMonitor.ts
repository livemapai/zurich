/**
 * useFPSMonitor - FPS Tracking for React Three Fiber
 *
 * Tracks frame timing in the R3F render loop and updates the performance store.
 * This enables adaptive quality adjustments based on real-time performance.
 *
 * USAGE:
 * Place this hook in a component inside the Canvas:
 * ```tsx
 * function FPSMonitor() {
 *   useFPSMonitor();
 *   return null;
 * }
 *
 * <Canvas>
 *   <FPSMonitor />
 *   ...
 * </Canvas>
 * ```
 *
 * PERFORMANCE:
 * - Minimal overhead: only records delta time each frame
 * - Rolling average prevents spiky adjustments
 * - Batched state updates via the performance store
 */

import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { recordFrame, usePerformanceSelector } from '../stores/performanceStore';

/**
 * Hook that monitors FPS and updates the performance store.
 * Must be used inside a R3F Canvas component.
 *
 * @param enabled - Whether to track FPS (default: true)
 *
 * @example
 * ```tsx
 * function FPSMonitor() {
 *   useFPSMonitor();
 *   return null;
 * }
 * ```
 */
export function useFPSMonitor(enabled = true): void {
  const lastTimeRef = useRef<number>(performance.now());

  useFrame(() => {
    if (!enabled) return;

    const now = performance.now();
    const deltaMs = now - lastTimeRef.current;
    lastTimeRef.current = now;

    // Record frame time to performance store
    recordFrame(deltaMs);
  });
}

/**
 * Hook to get current FPS (convenience wrapper).
 * Updates on every frame, so use sparingly in render.
 *
 * @returns Current FPS value
 */
export function useFPS(): number {
  return usePerformanceSelector((s) => s.fps);
}

/**
 * Hook to get average FPS (smoothed).
 * Less noisy than raw FPS, better for display.
 *
 * @returns Average FPS over recent frames
 */
export function useFPSAverage(): number {
  return usePerformanceSelector((s) => s.fpsAverage);
}

/**
 * Component that monitors FPS when added to the scene.
 * This is a convenience wrapper around useFPSMonitor.
 *
 * @example
 * ```tsx
 * <Canvas>
 *   <FPSMonitor />
 *   ...other components...
 * </Canvas>
 * ```
 */
export function FPSMonitor({ enabled = true }: { enabled?: boolean }): null {
  useFPSMonitor(enabled);
  return null;
}

export default useFPSMonitor;
