/**
 * SpatialChunkManager - Grid-Based Spatial Partitioning
 *
 * Divides the world into fixed-size grid cells for O(1) spatial queries.
 * Pre-computes feature membership at load time to avoid runtime calculations.
 *
 * PERFORMANCE CHARACTERISTICS:
 * - Load time: O(n) - each feature assigned to one cell
 * - Query time: O(k) - where k is number of cells in radius (typically 9-25)
 * - Memory: O(n) - feature references stored per cell
 *
 * ALGORITHM:
 * 1. At load: Hash each feature's position to cell coordinates
 * 2. At query: Calculate which cells overlap the query radius
 * 3. Return: Concatenate features from all overlapping cells
 *
 * COORDINATE SYSTEM:
 * Uses WGS84 degrees for position, converts to meters for distance.
 * Cell indices are integers: cellX = floor(lng / cellSizeDegrees)
 */

import { METERS_PER_DEGREE } from '@/types';
import type { LngLat } from '@/types';

/** Default cell size in meters (100m × 100m cells) */
const DEFAULT_CELL_SIZE_METERS = 100;

/** Configuration for the chunk manager */
export interface SpatialChunkConfig {
  /** Cell size in meters (default: 100) */
  cellSizeMeters?: number;
}

/** Cell key for Map storage */
type CellKey = string;

/** Result of a spatial query */
export interface SpatialQueryResult<T> {
  /** Features within the query radius */
  features: T[];
  /** Number of cells queried */
  cellsQueried: number;
  /** Cache hit (position unchanged from last query) */
  cacheHit: boolean;
}

/**
 * Create a cell key from cell coordinates
 */
function makeCellKey(cellX: number, cellY: number): CellKey {
  return `${cellX},${cellY}`;
}

/**
 * SpatialChunkManager - Grid-based spatial index for features
 *
 * @template T - Feature type (must be extractable to LngLat)
 */
export class SpatialChunkManager<T> {
  /** Cell size in degrees (longitude) */
  private cellSizeLng: number;
  /** Cell size in degrees (latitude) */
  private cellSizeLat: number;
  /** Cell size in meters */
  private cellSizeMeters: number;
  /** Map of cell key to features in that cell */
  private cells: Map<CellKey, T[]> = new Map();
  /** Function to extract coordinates from a feature */
  private getCoords: (feature: T) => LngLat;
  /** Total feature count */
  private featureCount = 0;
  /** Cached query result */
  private cachedResult: T[] = [];
  /** Cached query position */
  private cachedPosition: [number, number] = [0, 0];
  /** Cached query radius */
  private cachedRadius = 0;

  /**
   * Create a new SpatialChunkManager
   *
   * @param getCoords - Function to extract [lng, lat] from a feature
   * @param config - Configuration options
   */
  constructor(
    getCoords: (feature: T) => LngLat,
    config: SpatialChunkConfig = {}
  ) {
    this.getCoords = getCoords;
    this.cellSizeMeters = config.cellSizeMeters ?? DEFAULT_CELL_SIZE_METERS;

    // Convert cell size to degrees
    this.cellSizeLng = this.cellSizeMeters / METERS_PER_DEGREE.lng;
    this.cellSizeLat = this.cellSizeMeters / METERS_PER_DEGREE.lat;
  }

  /**
   * Get the cell coordinates for a position
   */
  private getCellCoords(lng: number, lat: number): [cellX: number, cellY: number] {
    return [
      Math.floor(lng / this.cellSizeLng),
      Math.floor(lat / this.cellSizeLat),
    ];
  }

  /**
   * Load features into the spatial index
   *
   * @param features - Array of features to index
   */
  load(features: T[]): void {
    // Clear existing data
    this.cells.clear();
    this.featureCount = 0;
    this.cachedResult = [];

    // Index each feature
    for (const feature of features) {
      const coords = this.getCoords(feature);
      const [cellX, cellY] = this.getCellCoords(coords[0], coords[1]);
      const key = makeCellKey(cellX, cellY);

      let cell = this.cells.get(key);
      if (!cell) {
        cell = [];
        this.cells.set(key, cell);
      }
      cell.push(feature);
      this.featureCount++;
    }
  }

  /**
   * Query features within a radius of a position
   *
   * @param lng - Longitude of query center
   * @param lat - Latitude of query center
   * @param radiusMeters - Query radius in meters
   * @returns Query result with features and metadata
   */
  queryRadius(lng: number, lat: number, radiusMeters: number): SpatialQueryResult<T> {
    // Check cache
    const posChanged =
      Math.abs(lng - this.cachedPosition[0]) > this.cellSizeLng * 0.5 ||
      Math.abs(lat - this.cachedPosition[1]) > this.cellSizeLat * 0.5;
    const radiusChanged = Math.abs(radiusMeters - this.cachedRadius) > this.cellSizeMeters;

    if (!posChanged && !radiusChanged && this.cachedResult.length > 0) {
      return {
        features: this.cachedResult,
        cellsQueried: 0,
        cacheHit: true,
      };
    }

    // Calculate cell range to query
    const radiusLng = radiusMeters / METERS_PER_DEGREE.lng;
    const radiusLat = radiusMeters / METERS_PER_DEGREE.lat;

    const minCellX = Math.floor((lng - radiusLng) / this.cellSizeLng);
    const maxCellX = Math.floor((lng + radiusLng) / this.cellSizeLng);
    const minCellY = Math.floor((lat - radiusLat) / this.cellSizeLat);
    const maxCellY = Math.floor((lat + radiusLat) / this.cellSizeLat);

    // Collect features from all cells in range
    const result: T[] = [];
    let cellsQueried = 0;

    // Pre-calculate for distance check
    const radiusSq = radiusMeters * radiusMeters;

    for (let cx = minCellX; cx <= maxCellX; cx++) {
      for (let cy = minCellY; cy <= maxCellY; cy++) {
        const key = makeCellKey(cx, cy);
        const cell = this.cells.get(key);
        if (cell) {
          cellsQueried++;
          // Filter features within actual radius (cells are rectangular approximation)
          for (const feature of cell) {
            const coords = this.getCoords(feature);
            const dLng = (coords[0] - lng) * METERS_PER_DEGREE.lng;
            const dLat = (coords[1] - lat) * METERS_PER_DEGREE.lat;
            const distSq = dLng * dLng + dLat * dLat;
            if (distSq <= radiusSq) {
              result.push(feature);
            }
          }
        }
      }
    }

    // Update cache
    this.cachedPosition = [lng, lat];
    this.cachedRadius = radiusMeters;
    this.cachedResult = result;

    return {
      features: result,
      cellsQueried,
      cacheHit: false,
    };
  }

  /**
   * Get features from a single cell (for debugging)
   */
  getCell(lng: number, lat: number): T[] {
    const [cellX, cellY] = this.getCellCoords(lng, lat);
    return this.cells.get(makeCellKey(cellX, cellY)) ?? [];
  }

  /**
   * Get statistics about the spatial index
   */
  getStats(): {
    featureCount: number;
    cellCount: number;
    cellSizeMeters: number;
    avgFeaturesPerCell: number;
  } {
    return {
      featureCount: this.featureCount,
      cellCount: this.cells.size,
      cellSizeMeters: this.cellSizeMeters,
      avgFeaturesPerCell:
        this.cells.size > 0 ? this.featureCount / this.cells.size : 0,
    };
  }

  /**
   * Clear the spatial index
   */
  clear(): void {
    this.cells.clear();
    this.featureCount = 0;
    this.cachedResult = [];
    this.cachedPosition = [0, 0];
    this.cachedRadius = 0;
  }
}

/**
 * Create a new SpatialChunkManager
 */
export function createSpatialChunkManager<T>(
  getCoords: (feature: T) => LngLat,
  config?: SpatialChunkConfig
): SpatialChunkManager<T> {
  return new SpatialChunkManager(getCoords, config);
}
