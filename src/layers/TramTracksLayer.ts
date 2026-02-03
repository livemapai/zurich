/**
 * Tram Tracks Layer Factory
 *
 * Creates deck.gl PathLayer for rendering VBZ tram track centerlines.
 * Tracks are colored by direction:
 * - Blue: Auswärtsgleis (outbound from city center)
 * - Orange: Einwärtsgleis (inbound to city center)
 *
 * Data: ~6,200 track segments from VBZ_Infrastruktur_OGD
 */

import { PathLayer } from '@deck.gl/layers';
import { ZURICH_BASE_ELEVATION } from '@/types';
import type { TramTrackFeature, TramTrackPath } from '@/types';

// Re-export types for convenience
export type { TramTrackFeature, TramTrackPath };

/** Configuration for tram tracks layer */
export interface TramTracksLayerConfig {
  id?: string;
  outboundColor?: [number, number, number, number];
  inboundColor?: [number, number, number, number];
  width?: number;
  opacity?: number;
  visible?: boolean;
  pickable?: boolean;
}

/** Default configuration values */
const DEFAULT_CONFIG: Required<TramTracksLayerConfig> = {
  id: 'tram-tracks',
  outboundColor: [0, 100, 200, 200],   // Blue for outbound (Auswärtsgleis)
  inboundColor: [200, 100, 0, 200],    // Orange for inbound (Einwärtsgleis)
  width: 1.5,                          // Track width in meters
  opacity: 1.0,
  visible: true,
  pickable: true,
};

/**
 * Process tram track features into flat path array
 *
 * MultiLineString geometries are flattened into individual paths,
 * each with 3D coordinates at ground elevation.
 *
 * @param features - Array of TramTrackFeature from GeoJSON
 * @returns Array of processed paths ready for PathLayer
 */
export function processTramTracks(features: TramTrackFeature[]): TramTrackPath[] {
  return features.flatMap((feature) =>
    feature.geometry.coordinates.map((line) => ({
      path: line.map(([lng, lat]) => [lng, lat, ZURICH_BASE_ELEVATION] as [number, number, number]),
      direction: feature.properties.streckengleistyptext || 'unknown',
      name: feature.properties.streckengleisbezeichnung || '',
    }))
  );
}

/**
 * Create a 3D tram tracks layer
 *
 * Renders track centerlines as colored paths on the ground.
 * Direction-based coloring helps visualize the tram network structure.
 *
 * @param data - Array of TramTrackFeature objects
 * @param config - Layer configuration options
 */
export function createTramTracksLayer(
  data: TramTrackFeature[],
  config: TramTracksLayerConfig = {}
): PathLayer<TramTrackPath> {
  const cfg = { ...DEFAULT_CONFIG, ...config };
  const paths = processTramTracks(data);

  return new PathLayer<TramTrackPath>({
    id: cfg.id,
    data: paths,
    visible: cfg.visible,

    // 3D path coordinates
    getPath: (d) => d.path,

    // Color by direction
    getColor: (d) =>
      d.direction === 'Auswärtsgleis' ? cfg.outboundColor : cfg.inboundColor,

    // Track dimensions
    getWidth: cfg.width,
    widthUnits: 'meters',
    widthMinPixels: 2,  // Ensure visibility at all zoom levels

    // Smooth path rendering
    jointRounded: true,
    capRounded: true,

    pickable: cfg.pickable,
  });
}

/** Processed tram track path for 2D minimap rendering */
interface TramTrackPath2D {
  /** 2D path coordinates [lng, lat] */
  path: [number, number][];
  /** Track direction for coloring */
  direction: string;
  /** Street/location name */
  name: string;
}

/**
 * Process tram track features into flat 2D path array (for minimap)
 */
function processTramTracks2D(features: TramTrackFeature[]): TramTrackPath2D[] {
  return features.flatMap((feature) =>
    feature.geometry.coordinates.map((line) => ({
      path: line.map(([lng, lat]) => [lng, lat] as [number, number]),
      direction: feature.properties.streckengleistyptext || 'unknown',
      name: feature.properties.streckengleisbezeichnung || '',
    }))
  );
}

/**
 * Create a minimap tram tracks layer (2D, simpler)
 *
 * @param data - Array of TramTrackFeature objects
 * @param config - Layer configuration options
 */
export function createMinimapTramTracksLayer(
  data: TramTrackFeature[],
  config: Partial<TramTracksLayerConfig> = {}
): PathLayer<TramTrackPath2D> {
  const cfg = {
    ...DEFAULT_CONFIG,
    id: 'minimap-tram-tracks',
    width: 3,
    pickable: false,
    ...config,
  };

  const paths = processTramTracks2D(data);

  return new PathLayer<TramTrackPath2D>({
    id: cfg.id,
    data: paths,
    visible: cfg.visible,
    getPath: (d) => d.path,
    getColor: (d) =>
      d.direction === 'Auswärtsgleis' ? cfg.outboundColor : cfg.inboundColor,
    getWidth: cfg.width,
    widthUnits: 'meters',
    widthMinPixels: 1,
    jointRounded: true,
    capRounded: true,
    pickable: cfg.pickable,
  });
}
