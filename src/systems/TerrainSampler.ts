/**
 * TerrainSampler - Elevation sampling from terrain heightmap
 *
 * Provides elevation queries using bilinear interpolation
 * from a terrain heightmap image.
 */

import type { TerrainData, TerrainQuery, LngLat } from '@/types';
import { ZURICH_BOUNDS } from '@/types';
import { lerp } from '@/lib/constants';

/**
 * Default elevation when terrain data is not available.
 * Set to 0 to match the relative coordinate system (ground = 0).
 * Without terrain data, minimum altitude = eye height (1.7m).
 */
const DEFAULT_ELEVATION = 0;

/**
 * TerrainSampler class for elevation queries
 */
export class TerrainSampler {
  private data: TerrainData | null = null;

  /**
   * Check if terrain data is loaded
   */
  isLoaded(): boolean {
    return this.data !== null;
  }

  /**
   * Load terrain data from a heightmap image
   *
   * @param imageUrl - URL to the heightmap PNG
   * @param bounds - Geographic bounds and elevation range
   */
  async load(
    imageUrl: string,
    bounds?: TerrainData['bounds']
  ): Promise<void> {
    const img = await this.loadImage(imageUrl);

    // Create canvas to read pixel data
    const canvas = document.createElement('canvas');
    canvas.width = img.width;
    canvas.height = img.height;

    const ctx = canvas.getContext('2d');
    if (!ctx) {
      throw new Error('Failed to create canvas context');
    }

    ctx.drawImage(img, 0, 0);
    const imageData = ctx.getImageData(0, 0, img.width, img.height);

    // Convert to elevation data
    // Assuming heightmap encodes elevation in the red channel
    // with 0 = minElev and 255 = maxElev
    const elevData = new Float32Array(img.width * img.height);
    const terrainBounds = bounds ?? {
      minLng: ZURICH_BOUNDS.minLng,
      maxLng: ZURICH_BOUNDS.maxLng,
      minLat: ZURICH_BOUNDS.minLat,
      maxLat: ZURICH_BOUNDS.maxLat,
      minElev: 392,  // Zurich lake level ~392m
      maxElev: 871,  // Uetliberg ~871m
    };

    const elevRange = terrainBounds.maxElev - terrainBounds.minElev;

    for (let i = 0; i < imageData.data.length; i += 4) {
      const r = imageData.data[i] ?? 0;
      const normalizedElev = r / 255;
      elevData[i / 4] = terrainBounds.minElev + normalizedElev * elevRange;
    }

    this.data = {
      width: img.width,
      height: img.height,
      data: elevData,
      bounds: terrainBounds,
    };
  }

  /**
   * Load terrain data directly (for testing or custom data)
   */
  loadDirect(data: TerrainData): void {
    this.data = data;
  }

  /**
   * Clear terrain data
   */
  clear(): void {
    this.data = null;
  }

  /**
   * Get elevation at a position using bilinear interpolation
   *
   * @param position - [lng, lat] coordinates
   * @returns TerrainQuery with elevation and bounds status
   */
  getElevation(position: LngLat): TerrainQuery {
    if (!this.data) {
      return { elevation: DEFAULT_ELEVATION, inBounds: false };
    }

    const { width, height, data, bounds } = this.data;

    // Check if position is within bounds
    const inBounds =
      position[0] >= bounds.minLng &&
      position[0] <= bounds.maxLng &&
      position[1] >= bounds.minLat &&
      position[1] <= bounds.maxLat;

    if (!inBounds) {
      return { elevation: DEFAULT_ELEVATION, inBounds: false };
    }

    // Convert position to pixel coordinates
    const u = (position[0] - bounds.minLng) / (bounds.maxLng - bounds.minLng);
    const v = (position[1] - bounds.minLat) / (bounds.maxLat - bounds.minLat);

    // Image coordinates (0,0 is top-left, so flip v)
    const px = u * (width - 1);
    const py = (1 - v) * (height - 1);

    // Bilinear interpolation
    const x0 = Math.floor(px);
    const y0 = Math.floor(py);
    const x1 = Math.min(x0 + 1, width - 1);
    const y1 = Math.min(y0 + 1, height - 1);

    const fx = px - x0;
    const fy = py - y0;

    // Sample four corners
    const e00 = data[y0 * width + x0] ?? DEFAULT_ELEVATION;
    const e10 = data[y0 * width + x1] ?? DEFAULT_ELEVATION;
    const e01 = data[y1 * width + x0] ?? DEFAULT_ELEVATION;
    const e11 = data[y1 * width + x1] ?? DEFAULT_ELEVATION;

    // Bilinear interpolation
    const e0 = lerp(e00, e10, fx);
    const e1 = lerp(e01, e11, fx);
    const elevation = lerp(e0, e1, fy);

    return { elevation, inBounds: true };
  }

  /**
   * Get elevation with default fallback
   */
  getElevationOrDefault(position: LngLat, defaultElev?: number): number {
    const result = this.getElevation(position);
    return result.inBounds ? result.elevation : (defaultElev ?? DEFAULT_ELEVATION);
  }

  /**
   * Load an image from URL
   */
  private loadImage(url: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error(`Failed to load image: ${url}`));
      img.src = url;
    });
  }
}

/**
 * Create a new TerrainSampler instance
 */
export function createTerrainSampler(): TerrainSampler {
  return new TerrainSampler();
}

/**
 * Get the default Zurich elevation
 */
export function getDefaultElevation(): number {
  return DEFAULT_ELEVATION;
}
