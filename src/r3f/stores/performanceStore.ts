/**
 * performanceStore - Lightweight State Management for Performance Settings
 *
 * Uses useSyncExternalStore pattern for a Zustand-like API without dependencies.
 * Manages adaptive quality settings based on real-time FPS monitoring.
 *
 * QUALITY TIERS:
 * - 0 (Low): Reduced SSAO, no bloom, shorter render distances
 * - 1 (Medium): Moderate SSAO, bloom enabled, normal render distances
 * - 2 (High): Full SSAO samples, full effects, maximum render distances
 *
 * ADAPTIVE BEHAVIOR:
 * - FPS < 30 for sustained period → reduce quality
 * - FPS > 55 for sustained period → increase quality
 * - Hysteresis prevents rapid quality oscillation
 */

import { useSyncExternalStore } from 'react';
import { CONFIG } from '@/lib/config';

/** Quality tier levels */
export type QualityTier = 0 | 1 | 2;

/** Performance state shape */
export interface PerformanceState {
  /** Current frames per second */
  fps: number;
  /** Rolling FPS average over recent frames */
  fpsAverage: number;
  /** Current quality tier (0=low, 1=medium, 2=high) */
  qualityTier: QualityTier;
  /** SSAO samples based on quality tier */
  ssaoSamples: number;
  /** Whether bloom is enabled based on quality tier */
  bloomEnabled: boolean;
  /** Render distance multiplier based on quality tier */
  renderDistanceMultiplier: number;
  /** Frame times buffer for averaging */
  frameTimes: number[];
  /** Number of consecutive frames below/above threshold */
  consecutiveFrames: number;
  /** Direction of last quality change (-1, 0, 1) */
  qualityDirection: -1 | 0 | 1;
}

/** Get settings for a quality tier */
function getQualitySettings(tier: QualityTier): {
  ssaoSamples: number;
  bloomEnabled: boolean;
  renderDistanceMultiplier: number;
} {
  return {
    ssaoSamples: CONFIG.performance.ssaoSamples[tier],
    bloomEnabled: CONFIG.performance.bloomEnabled[tier],
    renderDistanceMultiplier: CONFIG.performance.renderDistanceMultiplier[tier],
  };
}

/** Initial state */
const initialSettings = getQualitySettings(2); // Start at high quality
const initialState: PerformanceState = {
  fps: 60,
  fpsAverage: 60,
  qualityTier: 2,
  ssaoSamples: initialSettings.ssaoSamples,
  bloomEnabled: initialSettings.bloomEnabled,
  renderDistanceMultiplier: initialSettings.renderDistanceMultiplier,
  frameTimes: [],
  consecutiveFrames: 0,
  qualityDirection: 0,
};

// Store implementation
let state = { ...initialState };
const listeners = new Set<() => void>();

/** Subscribe to state changes */
function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Get current state snapshot */
function getSnapshot(): PerformanceState {
  return state;
}

/** Notify all listeners of state change */
function emit(): void {
  listeners.forEach((listener) => listener());
}

/** Update state and notify listeners */
function setState(partial: Partial<PerformanceState>): void {
  state = { ...state, ...partial };
  emit();
}

/**
 * Record a frame time and update FPS metrics.
 * Call this in useFrame or requestAnimationFrame.
 *
 * @param deltaMs - Frame delta time in milliseconds
 */
export function recordFrame(deltaMs: number): void {
  const fps = 1000 / Math.max(deltaMs, 1);

  // Update rolling frame times buffer
  const frameTimes = [...state.frameTimes, deltaMs];
  if (frameTimes.length > CONFIG.performance.fpsAverageFrames) {
    frameTimes.shift();
  }

  // Calculate average FPS
  const avgDelta = frameTimes.reduce((a, b) => a + b, 0) / frameTimes.length;
  const fpsAverage = 1000 / avgDelta;

  // Check if we should adjust quality
  let { qualityTier, consecutiveFrames, qualityDirection } = state;

  if (fpsAverage < CONFIG.performance.fpsThresholdLow) {
    // FPS too low
    if (qualityDirection !== -1) {
      consecutiveFrames = 1;
      qualityDirection = -1;
    } else {
      consecutiveFrames++;
    }

    // After sustained low FPS, reduce quality
    if (consecutiveFrames > CONFIG.performance.fpsAverageFrames && qualityTier > 0) {
      qualityTier = (qualityTier - 1) as QualityTier;
      consecutiveFrames = 0;
      qualityDirection = 0;
    }
  } else if (fpsAverage > CONFIG.performance.fpsThresholdHigh) {
    // FPS good, potentially increase quality
    if (qualityDirection !== 1) {
      consecutiveFrames = 1;
      qualityDirection = 1;
    } else {
      consecutiveFrames++;
    }

    // After sustained high FPS, increase quality
    if (consecutiveFrames > CONFIG.performance.fpsAverageFrames * 2 && qualityTier < 2) {
      qualityTier = (qualityTier + 1) as QualityTier;
      consecutiveFrames = 0;
      qualityDirection = 0;
    }
  } else {
    // FPS in acceptable range
    consecutiveFrames = 0;
    qualityDirection = 0;
  }

  // Get quality settings for current tier
  const settings = getQualitySettings(qualityTier);

  setState({
    fps,
    fpsAverage,
    frameTimes,
    qualityTier,
    consecutiveFrames,
    qualityDirection,
    ...settings,
  });
}

/**
 * Manually set quality tier (overrides adaptive behavior)
 *
 * @param tier - Quality tier (0, 1, or 2)
 */
export function setQualityTier(tier: QualityTier): void {
  const settings = getQualitySettings(tier);
  setState({
    qualityTier: tier,
    consecutiveFrames: 0,
    qualityDirection: 0,
    ...settings,
  });
}

/**
 * Reset to initial state
 */
export function resetPerformanceStore(): void {
  state = { ...initialState };
  emit();
}

/**
 * Hook to access performance state.
 * Components will re-render when relevant state changes.
 *
 * @returns Current performance state
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { qualityTier, ssaoSamples, bloomEnabled } = usePerformanceStore();
 *   // ...
 * }
 * ```
 */
export function usePerformanceStore(): PerformanceState {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

/**
 * Hook to access only specific performance values (prevents unnecessary re-renders).
 *
 * @param selector - Function to select desired values from state
 * @returns Selected values
 *
 * @example
 * ```tsx
 * const ssaoSamples = usePerformanceSelector(s => s.ssaoSamples);
 * ```
 */
export function usePerformanceSelector<T>(selector: (state: PerformanceState) => T): T {
  return useSyncExternalStore(
    subscribe,
    () => selector(getSnapshot()),
    () => selector(getSnapshot())
  );
}

export default usePerformanceStore;
