/**
 * Map Tile Layer Factory
 *
 * Creates a deck.gl TileLayer that renders OpenStreetMap tiles as the ground plane.
 * Works with FirstPersonView unlike MapLibre which is limited to ~60° pitch.
 */

import { TileLayer } from '@deck.gl/geo-layers';
import { BitmapLayer } from '@deck.gl/layers';

/** OpenStreetMap tile URL template */
const OSM_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

/** Stadia Maps (better styling, free tier available) */
const STADIA_TILE_URL = 'https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}.png';

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
}

const DEFAULT_CONFIG: Required<MapTileLayerConfig> = {
  id: 'map-tiles',
  tileUrl: OSM_TILE_URL,
  minZoom: 0,
  maxZoom: 19,
  opacity: 1,
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
    tileSize: 256,

    renderSubLayers: (props) => {
      const { boundingBox } = props.tile;
      const [min, max] = boundingBox;

      return new BitmapLayer(props, {
        data: undefined,
        image: props.data,
        bounds: [
          min[0] as number, // west
          min[1] as number, // south
          max[0] as number, // east
          max[1] as number, // north
        ],
      });
    },
  });
}

export { OSM_TILE_URL, STADIA_TILE_URL };
