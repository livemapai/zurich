/**
 * Mapterhorn 3D Terrain Layer Factory
 *
 * Creates a deck.gl TerrainLayer using Mapterhorn elevation tiles
 * and OpenStreetMap texture overlay.
 *
 * Mapterhorn tiles use Terrarium encoding:
 * elevation = R*256 + G + B/256 - 32768
 *
 * Attribution: Terrain: Mapterhorn | swisstopo
 */

import { TerrainLayer } from '@deck.gl/geo-layers';

// Mapterhorn elevation tiles (WebP, 512x512, Terrarium encoding)
const MAPTERHORN_URL = 'https://tiles.mapterhorn.com/{z}/{x}/{y}.webp';

// OpenStreetMap texture for ground color
const OSM_TEXTURE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

/**
 * Available texture providers for terrain layer
 * Each provider offers different visual styles for the ground surface
 *
 * Note: Esri uses {z}/{y}/{x} order (TMS-like), others use {z}/{x}/{y} (XYZ/Slippy)
 *
 * swissimage: High-resolution satellite imagery from swisstopo (only covers Switzerland)
 * - Uses hybrid mode: falls back to Esri at low zoom levels (< SWISS_ZOOM_THRESHOLD)
 * - This is because swisstopo only covers Swiss territory, returns HTTP 400 for wide views
 */
export const TEXTURE_PROVIDERS = {
  osm: {
    name: 'OpenStreetMap',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  },
  satellite: {
    name: 'Satellite (Esri)',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  },
  swissimage: {
    name: 'Swiss Satellite',
    url: 'https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissimage/default/current/3857/{z}/{x}/{y}.jpeg',
  },
  cartoDark: {
    name: 'Dark (Carto)',
    url: 'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
  },
} as const;

/**
 * Zoom threshold for hybrid Swiss satellite switching
 *
 * Below this zoom level, swissimage falls back to Esri satellite
 * because swisstopo only serves tiles within Switzerland bounds.
 *
 * Reference zoom levels:
 * - 12: ~500m eye height - city district view
 * - 14: ~100m eye height - block view
 * - 16: ~25m eye height - building detail
 */
export const SWISS_ZOOM_THRESHOLD = 12;

/** Type-safe texture provider IDs */
export type TextureProviderId = keyof typeof TEXTURE_PROVIDERS;

/**
 * Terrarium decoder coefficients
 * Formula: elevation = R * rScaler + G * gScaler + B * bScaler + offset
 * Terrarium: elevation = R*256 + G + B/256 - 32768
 */
const TERRARIUM_DECODER = {
  rScaler: 256,
  gScaler: 1,
  bScaler: 1 / 256,
  offset: -32768,
};

export interface MapterhornTerrainLayerConfig {
  /** Layer ID (default: 'mapterhorn-terrain') */
  id?: string;
  /** Elevation tile URL template (default: Mapterhorn) */
  elevationUrl?: string;
  /** Texture tile URL template (default: OSM) */
  textureUrl?: string;
  /** Minimum zoom level (default: 4) */
  minZoom?: number;
  /** Maximum zoom level for elevation tiles (default: 14) */
  maxZoom?: number;
  /** Mesh max error in meters - controls mesh simplification (default: 4) */
  meshMaxError?: number;
  /** Layer opacity (default: 1) */
  opacity?: number;
  /** Elevation scale multiplier (default: 1) */
  elevationScale?: number;
}

const DEFAULT_CONFIG: Required<MapterhornTerrainLayerConfig> = {
  id: 'mapterhorn-terrain',
  elevationUrl: MAPTERHORN_URL,
  textureUrl: OSM_TEXTURE_URL,
  minZoom: 4,
  maxZoom: 14,
  meshMaxError: 4,
  opacity: 1,
  elevationScale: 1,
};

/**
 * Generate a short hash from a string (for layer ID uniqueness)
 * Uses djb2 algorithm - fast and produces good distribution
 */
function hashString(str: string): string {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 33) ^ str.charCodeAt(i);
  }
  return (hash >>> 0).toString(36);
}

/**
 * Create a 3D terrain layer using Mapterhorn elevation tiles
 *
 * IMPORTANT: The layer ID includes a hash of the texture URL. This forces
 * deck.gl to create a new layer instance when the texture changes, avoiding
 * texture hot-swap issues that cause "Cannot read properties of null" errors.
 *
 * @param config - Layer configuration options
 * @returns TerrainLayer instance
 *
 * @example
 * ```ts
 * // Basic usage
 * const terrain = createMapterhornTerrainLayer();
 *
 * // Custom mesh quality
 * const highQuality = createMapterhornTerrainLayer({ meshMaxError: 2 });
 * ```
 */
export function createMapterhornTerrainLayer(
  config: MapterhornTerrainLayerConfig = {}
): TerrainLayer {
  const mergedConfig = { ...DEFAULT_CONFIG, ...config };

  // Include texture hash in layer ID to force recreation when texture changes
  // This prevents deck.gl texture hot-swap issues
  const textureHash = hashString(mergedConfig.textureUrl);
  const layerId = `${mergedConfig.id}-${textureHash}`;

  return new TerrainLayer({
    id: layerId,
    elevationDecoder: TERRARIUM_DECODER,
    elevationData: mergedConfig.elevationUrl,
    texture: mergedConfig.textureUrl,
    minZoom: mergedConfig.minZoom,
    maxZoom: mergedConfig.maxZoom,
    meshMaxError: mergedConfig.meshMaxError,
    opacity: mergedConfig.opacity,
    elevationScale: mergedConfig.elevationScale,
    pickable: false,
  });
}
