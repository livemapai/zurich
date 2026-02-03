/**
 * useTileManager - React Hook for Tile-Based Building Loading
 *
 * Provides React integration for the TileManager system.
 * Automatically loads/unloads building tiles based on player position.
 *
 * USAGE:
 * ```tsx
 * const { features, isLoading, stats } = useTileManager({
 *   playerPosition: [lng, lat],
 *   basePath: '/data/tiles/buildings',
 * });
 * ```
 *
 * Note: This is an optional enhancement to the distance-based Buildings component.
 * Use this for very large datasets where you want true progressive loading.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import type { BuildingFeature } from '@/types';
import { METERS_PER_DEGREE } from '@/types';
import { TileManager, createTileManager } from '../systems/TileManager';

/** Distance player must move before updating tiles (meters) */
const UPDATE_DISTANCE_METERS = 100;

interface UseTileManagerOptions {
  /** Player position [lng, lat] */
  playerPosition?: [number, number];
  /** Base path for tile files */
  basePath?: string;
  /** Enable tile loading (default: true) */
  enabled?: boolean;
}

interface UseTileManagerResult {
  /** Building features from loaded tiles */
  features: BuildingFeature[];
  /** Whether tiles are currently loading */
  isLoading: boolean;
  /** Whether the tile index is loaded */
  isIndexLoaded: boolean;
  /** Tile loading statistics */
  stats: {
    loadedTiles: number;
    loadingTiles: number;
    totalFeatures: number;
  };
  /** Manually trigger tile update */
  refresh: () => Promise<void>;
}

/**
 * Hook for managing tile-based building loading.
 */
export function useTileManager(options: UseTileManagerOptions = {}): UseTileManagerResult {
  const {
    playerPosition,
    basePath = '/data/tiles/buildings',
    enabled = true,
  } = options;

  // Default to Zurich center
  const effectivePos = playerPosition ?? [8.5437, 47.3739] as [number, number];

  // Track last update position
  const lastUpdatePosRef = useRef<[number, number]>([0, 0]);

  // TileManager instance (stable across renders)
  const managerRef = useRef<TileManager | null>(null);

  // State
  const [features, setFeatures] = useState<BuildingFeature[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isIndexLoaded, setIsIndexLoaded] = useState(false);
  const [stats, setStats] = useState({ loadedTiles: 0, loadingTiles: 0, totalFeatures: 0 });

  // Initialize manager
  useEffect(() => {
    if (!enabled) return;

    if (!managerRef.current) {
      managerRef.current = createTileManager(basePath);
    }

    // Load index on mount
    const loadIndex = async () => {
      if (!managerRef.current) return;

      setIsLoading(true);
      try {
        await managerRef.current.loadIndex();
        setIsIndexLoaded(true);
      } catch (error) {
        console.error('Failed to load tile index:', error);
      }
      setIsLoading(false);
    };

    loadIndex();

    // Cleanup on unmount
    return () => {
      managerRef.current?.clear();
    };
  }, [enabled, basePath]);

  // Update tiles based on player position
  useEffect(() => {
    if (!enabled || !isIndexLoaded || !managerRef.current) return;

    const [playerLng, playerLat] = effectivePos;
    const [lastLng, lastLat] = lastUpdatePosRef.current;

    // Calculate distance moved
    const dLng = (playerLng - lastLng) * METERS_PER_DEGREE.lng;
    const dLat = (playerLat - lastLat) * METERS_PER_DEGREE.lat;
    const distanceMoved = Math.sqrt(dLng * dLng + dLat * dLat);

    // Skip if we haven't moved enough
    if (distanceMoved < UPDATE_DISTANCE_METERS && features.length > 0) {
      return;
    }

    // Update last position
    lastUpdatePosRef.current = [playerLng, playerLat];

    // Load tiles
    const updateTiles = async () => {
      if (!managerRef.current) return;

      setIsLoading(true);

      try {
        const newFeatures = await managerRef.current.updateForPosition(playerLng, playerLat);
        setFeatures(newFeatures);
        setStats(managerRef.current.getStats());
      } catch (error) {
        console.error('Failed to update tiles:', error);
      }

      setIsLoading(false);
    };

    updateTiles();
  }, [effectivePos[0], effectivePos[1], enabled, isIndexLoaded, features.length]);

  // Manual refresh function
  const refresh = useCallback(async () => {
    if (!managerRef.current || !isIndexLoaded) return;

    setIsLoading(true);
    const [lng, lat] = effectivePos;

    try {
      const newFeatures = await managerRef.current.updateForPosition(lng, lat);
      setFeatures(newFeatures);
      setStats(managerRef.current.getStats());
    } catch (error) {
      console.error('Failed to refresh tiles:', error);
    }

    setIsLoading(false);
  }, [effectivePos, isIndexLoaded]);

  return {
    features,
    isLoading,
    isIndexLoaded,
    stats,
    refresh,
  };
}

export default useTileManager;
