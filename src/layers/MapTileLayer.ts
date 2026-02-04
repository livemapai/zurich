/**
 * Map Tile Layer Factory
 *
 * Creates a deck.gl TileLayer that renders OpenStreetMap tiles as the ground plane.
 * Works with FirstPersonView unlike MapLibre which is limited to ~60° pitch.
 */

import { TileLayer } from '@deck.gl/geo-layers';
import { BitmapLayer } from '@deck.gl/layers';
import { ZURICH_BASE_ELEVATION } from '@/types';

/** OpenStreetMap tile URL template */
const OSM_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

/** Stadia Maps (better styling, free tier available) */
const STADIA_TILE_URL = 'https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}.png';

/** CartoDB Voyager - Modern, clean style with good detail (free tier) */
const CARTO_VOYAGER_URL = 'https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png';

/** CartoDB Positron - Minimalist light gray style (free tier) */
const CARTO_POSITRON_URL = 'https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png';

/** CartoDB Dark Matter - Dark theme with cyan highlights (free tier) */
const CARTO_DARK_URL = 'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png';

/**
 * Map tile provider configuration
 */
export interface MapTileProvider {
  /** Display name */
  name: string;
  /** Tile URL template */
  url: string;
}

/**
 * Available map tile providers
 * Similar to TEXTURE_PROVIDERS for terrain, but for flat 2D map tiles
 */
export const MAP_TILE_PROVIDERS = {
  voyager: {
    name: 'CartoDB Voyager',
    url: CARTO_VOYAGER_URL,
  },
  positron: {
    name: 'CartoDB Light',
    url: CARTO_POSITRON_URL,
  },
  dark: {
    name: 'CartoDB Dark',
    url: CARTO_DARK_URL,
  },
  osm: {
    name: 'OpenStreetMap',
    url: OSM_TILE_URL,
  },
  stadia: {
    name: 'Stadia Smooth',
    url: STADIA_TILE_URL,
  },
} as const satisfies Record<string, MapTileProvider>;

/** Map tile provider ID type */
export type MapTileProviderId = keyof typeof MAP_TILE_PROVIDERS;

export interface MapTileLayerConfig {
  id?: string;
  /** Tile URL template with {z}/{x}/{y} placeholders */
  tileUrl?: string;
  /** Minimum zoom level */
  minZoom?: number;
  /** Maximum zoom level */
  maxZoom?: number;
  /** Layer opacity */
  opacity?: number;
  /** Base elevation for tile rendering (default: ZURICH_BASE_ELEVATION = 408m) */
  baseElevation?: number;
  /** Maximum number of tiles to cache (default: 100) */
  maxCacheSize?: number;
  /** Maximum cache size in bytes (default: 100MB) */
  maxCacheByteSize?: number;
  /** Debounce time in ms for tile requests during rapid viewport changes (default: 50) */
  debounceTime?: number;
}

const DEFAULT_CONFIG: Required<MapTileLayerConfig> = {
  id: 'map-tiles',
  tileUrl: CARTO_VOYAGER_URL,
  minZoom: 0,
  maxZoom: 19,
  opacity: 1,
  baseElevation: ZURICH_BASE_ELEVATION,
  maxCacheSize: 100,
  maxCacheByteSize: 100 * 1024 * 1024, // 100MB
  debounceTime: 50,
};

/**
 * Create a tile layer that renders map tiles as the ground
 *
 * Uses deck.gl TileLayer + BitmapLayer to render raster tiles.
 * Compatible with FirstPersonView (unlike MapLibre).
 */
export function createMapTileLayer(config: MapTileLayerConfig = {}): TileLayer {
  const mergedConfig = { ...DEFAULT_CONFIG, ...config };

  return new TileLayer({
    id: mergedConfig.id,
    data: mergedConfig.tileUrl,
    minZoom: mergedConfig.minZoom,
    maxZoom: mergedConfig.maxZoom,
    opacity: mergedConfig.opacity,
    // Use 512 to match @2x tiles from CartoDB (default provider)
    // Using 256 with @2x tiles causes deck.gl to request 4x more tiles than needed
    tileSize: 512,
    // Performance: limit tile cache to prevent unbounded memory growth
    maxCacheSize: mergedConfig.maxCacheSize,
    maxCacheByteSize: mergedConfig.maxCacheByteSize,
    // Performance: batch tile requests during rapid panning/zooming
    debounceTime: mergedConfig.debounceTime,
    // Show lower-resolution tiles while higher-resolution load
    refinementStrategy: 'best-available',

    renderSubLayers: (props) => {
      const { boundingBox } = props.tile;
      const [min, max] = boundingBox;
      const elevation = mergedConfig.baseElevation;

      // Use 4-corner bounds format to specify elevation
      // This ensures tiles render at ground level (408m) instead of sea level (0m)
      return new BitmapLayer(props, {
        data: undefined,
        image: props.data,
        bounds: [
          [min[0] as number, min[1] as number, elevation], // SW corner
          [min[0] as number, max[1] as number, elevation], // NW corner
          [max[0] as number, max[1] as number, elevation], // NE corner
          [max[0] as number, min[1] as number, elevation], // SE corner
        ],
      });
    },
  });
}

export {
  OSM_TILE_URL,
  STADIA_TILE_URL,
  CARTO_VOYAGER_URL,
  CARTO_POSITRON_URL,
  CARTO_DARK_URL,
};
