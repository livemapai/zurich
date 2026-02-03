/**
 * TileManager - Spatial Tile Loading System for Buildings
 *
 * Manages dynamic loading/unloading of building tiles based on player position.
 * Tiles are ~200m × 200m spatial chunks with pre-processed building data.
 *
 * LOADING STRATEGY:
 * - Load tiles within 2-tile radius of player (~500m)
 * - Unload tiles beyond 4-tile radius (~1000m)
 * - Progressive loading using requestIdleCallback
 *
 * COORDINATE SYSTEM:
 * - Tiles indexed by [x, y] where x = floor(lng / tileSize), y = floor(lat / tileSize)
 * - Zurich center ~[8.54, 47.37] → tile [854, 4737] at tileSize=0.01
 */

import type { BuildingFeature, BuildingCollection } from '@/types';
import { CONFIG } from '@/lib/config';

/** Tile index structure from tile-index.json */
export interface TileIndex {
  tileSize: number;
  tiles: Record<string, TileInfo>;
}

/** Information about a single tile */
export interface TileInfo {
  file: string;
  featureCount: number;
  bounds: [number, number, number, number]; // [minLng, minLat, maxLng, maxLat]
}

/** Loaded tile with features */
export interface LoadedTile {
  key: string;
  info: TileInfo;
  features: BuildingFeature[];
  loadedAt: number;
}

/** Tile load/unload radius in tiles */
const LOAD_RADIUS_TILES = 2;
const UNLOAD_RADIUS_TILES = 4;

/**
 * TileManager class for managing tile loading.
 */
export class TileManager {
  private index: TileIndex | null = null;
  private loadedTiles: Map<string, LoadedTile> = new Map();
  private loadingTiles: Set<string> = new Set();
  private basePath: string;

  constructor(basePath: string = '/data/tiles/buildings') {
    this.basePath = basePath;
  }

  /**
   * Load the tile index.
   */
  async loadIndex(): Promise<void> {
    if (this.index) return;

    try {
      const response = await fetch(`${this.basePath}/tile-index.json`);
      if (!response.ok) {
        throw new Error(`Failed to load tile index: ${response.status}`);
      }
      this.index = await response.json();
      console.log(`TileManager: Loaded index with ${Object.keys(this.index!.tiles).length} tiles`);
    } catch (error) {
      console.error('TileManager: Failed to load index:', error);
      throw error;
    }
  }

  /**
   * Get tile key for a coordinate.
   */
  getTileKey(lng: number, lat: number): string {
    const tileSize = this.index?.tileSize ?? 0.01;
    const x = Math.floor(lng / tileSize);
    const y = Math.floor(lat / tileSize);
    return `${x},${y}`;
  }

  /**
   * Get all tile keys within a radius of a position.
   */
  getTilesInRadius(lng: number, lat: number, radiusTiles: number): string[] {
    if (!this.index) return [];

    const tileSize = this.index.tileSize;
    const centerX = Math.floor(lng / tileSize);
    const centerY = Math.floor(lat / tileSize);

    const keys: string[] = [];
    for (let dx = -radiusTiles; dx <= radiusTiles; dx++) {
      for (let dy = -radiusTiles; dy <= radiusTiles; dy++) {
        const key = `${centerX + dx},${centerY + dy}`;
        if (this.index.tiles[key]) {
          keys.push(key);
        }
      }
    }
    return keys;
  }

  /**
   * Load a single tile.
   */
  async loadTile(key: string): Promise<LoadedTile | null> {
    if (!this.index) return null;

    const info = this.index.tiles[key];
    if (!info) return null;

    // Already loaded or loading
    if (this.loadedTiles.has(key) || this.loadingTiles.has(key)) {
      return this.loadedTiles.get(key) ?? null;
    }

    this.loadingTiles.add(key);

    try {
      const response = await fetch(`${this.basePath}/${info.file}`);
      if (!response.ok) {
        throw new Error(`Failed to load tile ${key}: ${response.status}`);
      }

      const data: BuildingCollection = await response.json();

      const loadedTile: LoadedTile = {
        key,
        info,
        features: data.features,
        loadedAt: Date.now(),
      };

      this.loadedTiles.set(key, loadedTile);
      this.loadingTiles.delete(key);

      if (CONFIG.debug.logPerformance) {
        console.log(`TileManager: Loaded tile ${key} (${data.features.length} buildings)`);
      }

      return loadedTile;
    } catch (error) {
      console.error(`TileManager: Failed to load tile ${key}:`, error);
      this.loadingTiles.delete(key);
      return null;
    }
  }

  /**
   * Unload a tile.
   */
  unloadTile(key: string): void {
    if (this.loadedTiles.has(key)) {
      this.loadedTiles.delete(key);
      if (CONFIG.debug.logPerformance) {
        console.log(`TileManager: Unloaded tile ${key}`);
      }
    }
  }

  /**
   * Update loaded tiles based on player position.
   * Loads nearby tiles and unloads distant ones.
   */
  async updateForPosition(lng: number, lat: number): Promise<BuildingFeature[]> {
    if (!this.index) {
      await this.loadIndex();
    }

    // Get tiles to load and unload
    const tilesToLoad = this.getTilesInRadius(lng, lat, LOAD_RADIUS_TILES);
    const tilesToKeep = new Set(this.getTilesInRadius(lng, lat, UNLOAD_RADIUS_TILES));

    // Unload distant tiles
    for (const key of this.loadedTiles.keys()) {
      if (!tilesToKeep.has(key)) {
        this.unloadTile(key);
      }
    }

    // Load nearby tiles (in parallel)
    const loadPromises = tilesToLoad.map((key) => this.loadTile(key));
    await Promise.all(loadPromises);

    // Return all features from loaded tiles
    return this.getAllFeatures();
  }

  /**
   * Get all features from currently loaded tiles.
   */
  getAllFeatures(): BuildingFeature[] {
    const features: BuildingFeature[] = [];
    for (const tile of this.loadedTiles.values()) {
      features.push(...tile.features);
    }
    return features;
  }

  /**
   * Get statistics about loaded tiles.
   */
  getStats(): { loadedTiles: number; loadingTiles: number; totalFeatures: number } {
    return {
      loadedTiles: this.loadedTiles.size,
      loadingTiles: this.loadingTiles.size,
      totalFeatures: this.getAllFeatures().length,
    };
  }

  /**
   * Check if the index is loaded.
   */
  isIndexLoaded(): boolean {
    return this.index !== null;
  }

  /**
   * Clear all loaded tiles.
   */
  clear(): void {
    this.loadedTiles.clear();
    this.loadingTiles.clear();
  }
}

/**
 * Create a new TileManager instance.
 */
export function createTileManager(basePath?: string): TileManager {
  return new TileManager(basePath);
}
