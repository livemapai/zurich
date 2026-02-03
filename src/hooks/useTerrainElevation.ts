/**
 * useTerrainElevation - Terrain elevation sampling hook
 *
 * Manages terrain data loading and provides elevation queries.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { LngLat, TerrainQuery } from '@/types';
import { TerrainSampler, createTerrainSampler, getDefaultElevation } from '@/systems';
import { CONFIG } from '@/lib/config';

interface UseTerrainElevationOptions {
  /** URL to terrain heightmap image (optional, will use config default) */
  terrainUrl?: string;
  /** Enable terrain loading */
  enabled?: boolean;
}

interface UseTerrainElevationResult {
  /** Whether terrain data is loaded */
  isLoaded: boolean;
  /** Loading state */
  isLoading: boolean;
  /** Error if loading failed */
  error: Error | null;
  /** Get elevation at a position */
  getElevation: (position: LngLat) => TerrainQuery;
  /** Get elevation with default fallback */
  getElevationOrDefault: (position: LngLat) => number;
}

/**
 * Hook to manage terrain elevation data
 */
export function useTerrainElevation(
  options: UseTerrainElevationOptions = {}
): UseTerrainElevationResult {
  const { terrainUrl = CONFIG.data.terrain, enabled = true } = options;

  const [isLoaded, setIsLoaded] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Terrain sampler stored in ref
  const samplerRef = useRef<TerrainSampler>(createTerrainSampler());

  // Load terrain data
  useEffect(() => {
    if (!enabled) {
      samplerRef.current.clear();
      setIsLoaded(false);
      setIsLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;

    const loadTerrain = async () => {
      setIsLoading(true);
      setError(null);

      try {
        await samplerRef.current.load(terrainUrl);

        if (!cancelled) {
          setIsLoaded(true);
          setIsLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          const errorObj = err instanceof Error ? err : new Error(String(err));
          console.warn('Failed to load terrain:', errorObj.message);
          setError(errorObj);
          setIsLoading(false);
          // Don't set isLoaded=false, keep using default elevation
        }
      }
    };

    loadTerrain();

    return () => {
      cancelled = true;
    };
  }, [terrainUrl, enabled]);

  /**
   * Get elevation at a position
   */
  const getElevation = useCallback((position: LngLat): TerrainQuery => {
    return samplerRef.current.getElevation(position);
  }, []);

  /**
   * Get elevation with default fallback
   */
  const getElevationOrDefault = useCallback((position: LngLat): number => {
    return samplerRef.current.getElevationOrDefault(position, getDefaultElevation());
  }, []);

  return {
    isLoaded,
    isLoading,
    error,
    getElevation,
    getElevationOrDefault,
  };
}
