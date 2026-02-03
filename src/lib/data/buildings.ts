/**
 * Buildings Data Loader
 *
 * Loads and processes building GeoJSON data with progress reporting.
 */

import type { BuildingFeature, BuildingCollection, ZurichBounds } from '@/types';

export interface BuildingStats {
  count: number;
  minHeight: number;
  maxHeight: number;
  avgHeight: number;
}

export interface LoadBuildingsResult {
  features: BuildingFeature[];
  bounds: ZurichBounds;
  stats: BuildingStats;
}

/**
 * Calculate bounding box from building features
 */
function calculateBounds(features: BuildingFeature[]): ZurichBounds {
  let minLng = Infinity;
  let maxLng = -Infinity;
  let minLat = Infinity;
  let maxLat = -Infinity;

  for (const feature of features) {
    const { geometry } = feature;
    const rings =
      geometry.type === 'MultiPolygon'
        ? geometry.coordinates.flat()
        : geometry.coordinates;

    for (const ring of rings) {
      for (const [lng, lat] of ring) {
        if (lng < minLng) minLng = lng;
        if (lng > maxLng) maxLng = lng;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
      }
    }
  }

  return { minLng, maxLng, minLat, maxLat };
}

/**
 * Calculate statistics from building features
 */
function calculateStats(features: BuildingFeature[]): BuildingStats {
  if (features.length === 0) {
    return { count: 0, minHeight: 0, maxHeight: 0, avgHeight: 0 };
  }

  let minHeight = Infinity;
  let maxHeight = -Infinity;
  let totalHeight = 0;

  for (const feature of features) {
    const height = feature.properties.height || 10;
    if (height < minHeight) minHeight = height;
    if (height > maxHeight) maxHeight = height;
    totalHeight += height;
  }

  return {
    count: features.length,
    minHeight,
    maxHeight,
    avgHeight: totalHeight / features.length,
  };
}

/**
 * Load building data from URL
 *
 * @param url - URL to the GeoJSON file
 * @param onProgress - Optional callback for progress updates (0-100)
 */
export async function loadBuildings(
  url: string,
  onProgress?: (progress: number) => void
): Promise<LoadBuildingsResult> {
  onProgress?.(0);

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to load buildings: ${response.status} ${response.statusText}`);
  }

  onProgress?.(30);

  const data: BuildingCollection = await response.json();

  if (!data.features || !Array.isArray(data.features)) {
    throw new Error('Invalid GeoJSON: missing features array');
  }

  onProgress?.(60);

  const features = data.features;
  const bounds = calculateBounds(features);
  const stats = calculateStats(features);

  onProgress?.(100);

  return { features, bounds, stats };
}

/**
 * Load building data with timeout
 *
 * @param url - URL to the GeoJSON file
 * @param timeout - Timeout in milliseconds (default: 30000)
 * @param onProgress - Optional callback for progress updates
 */
export async function loadBuildingsWithTimeout(
  url: string,
  timeout: number = 30000,
  onProgress?: (progress: number) => void
): Promise<LoadBuildingsResult> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    onProgress?.(0);

    const response = await fetch(url, { signal: controller.signal });

    if (!response.ok) {
      throw new Error(`Failed to load buildings: ${response.status}`);
    }

    onProgress?.(30);

    const data: BuildingCollection = await response.json();

    if (!data.features || !Array.isArray(data.features)) {
      throw new Error('Invalid GeoJSON: missing features array');
    }

    onProgress?.(60);

    const features = data.features;
    const bounds = calculateBounds(features);
    const stats = calculateStats(features);

    onProgress?.(100);

    return { features, bounds, stats };
  } finally {
    clearTimeout(timeoutId);
  }
}
