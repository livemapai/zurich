/**
 * Fountains Layer Factory
 *
 * Creates deck.gl layers for rendering fountains as 3D procedural shapes.
 * Each fountain is a basin (wide cylinder) with a column (narrow cylinder).
 * Data: ~1,300 fountains from Brunnen (Stadt Zürich Open Data)
 *
 * Reads terrain elevation from feature.properties.elevation (pre-computed).
 */

import { SimpleMeshLayer, type SimpleMeshLayerProps } from '@deck.gl/mesh-layers';
import { ScatterplotLayer } from '@deck.gl/layers';
import { ZURICH_BASE_ELEVATION } from '@/types';
import type { LngLat } from '@/types';
import { generateFountainMesh } from '@/utils/fountainGeometry';

/** Properties for a fountain feature */
export interface FountainProperties {
  /** Unique fountain identifier */
  id: string;
  /** Location name */
  name: string;
  /** Fountain type (e.g., "Notwasserbrunnen") */
  type?: string;
  /** Basin material (e.g., "Granit") */
  material?: string;
  /** Artist/architect name */
  artist?: string;
  /** Construction year */
  year?: number;
  /** Photo URL */
  photo?: string;
  /** District name */
  quartier?: string;
  /** Water type */
  water_type?: string;
  /** Ground elevation in meters (from terrain) */
  elevation?: number;
}

/** GeoJSON Point geometry */
export interface PointGeometry {
  type: 'Point';
  coordinates: LngLat;
}

/** GeoJSON Feature for a fountain */
export interface FountainFeature {
  type: 'Feature';
  properties: FountainProperties;
  geometry: PointGeometry;
}

/** GeoJSON FeatureCollection for fountains */
export interface FountainCollection {
  type: 'FeatureCollection';
  features: FountainFeature[];
}

/** Configuration for fountains layer */
export interface FountainsLayerConfig {
  id?: string;
  fillColor?: [number, number, number, number];
  opacity?: number;
  visible?: boolean;
  pickable?: boolean;
}

const DEFAULT_CONFIG: Required<FountainsLayerConfig> = {
  id: 'fountains',
  fillColor: [180, 175, 165, 255], // Light gray stone
  opacity: 1.0,
  visible: true,
  pickable: true,
};

// Generate mesh once (reused for all ~1,300 fountains)
// Cast to expected mesh type - SimpleMeshLayer accepts plain objects with positions/normals/indices at runtime
const FOUNTAIN_MESH = generateFountainMesh(12) as unknown as SimpleMeshLayerProps['mesh'];

/**
 * Create a 3D fountains layer with procedural basin+column shapes
 *
 * Elevation is read from feature.properties.elevation (pre-computed by
 * scripts/terrain/add_elevations.py). Falls back to ZURICH_BASE_ELEVATION (408m).
 *
 * @param data - Array of FountainFeature objects
 * @param config - Layer configuration options
 */
export function createFountainsLayer(
  data: FountainFeature[],
  config: FountainsLayerConfig = {}
): SimpleMeshLayer<FountainFeature> {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  // Debug: log elevation statistics
  if (data.length > 0) {
    const elevations = data.map(d => d.properties.elevation ?? ZURICH_BASE_ELEVATION);
    const withElevation = data.filter(d => d.properties.elevation !== undefined).length;
    const min = Math.min(...elevations);
    const max = Math.max(...elevations);
    console.log(`[Fountains] ${data.length} total, ${withElevation} with elevation, range: ${min.toFixed(1)}m - ${max.toFixed(1)}m`);
  }

  return new SimpleMeshLayer<FountainFeature>({
    id: cfg.id,
    data,
    visible: cfg.visible,
    mesh: FOUNTAIN_MESH,

    // Position at fountain location with terrain elevation from properties
    getPosition: (d) => {
      const elevation = d.properties.elevation ?? ZURICH_BASE_ELEVATION;
      return [...d.geometry.coordinates, elevation] as [number, number, number];
    },

    // Fixed scale (fountains are ~1.5m tall)
    getScale: [1.5, 1.5, 1.5],

    getColor: cfg.fillColor,
    getOrientation: [0, 0, 0], // No rotation

    // Material settings for 3D appearance
    material: {
      ambient: 0.4,
      diffuse: 0.6,
      shininess: 20,
    },

    pickable: cfg.pickable,
  });
}

/**
 * Create a fountains layer for minimap display (2D circles, simpler)
 *
 * @param data - Array of FountainFeature objects
 * @param config - Layer configuration options
 */
export function createMinimapFountainsLayer(
  data: FountainFeature[],
  config: Partial<FountainsLayerConfig> = {}
): ScatterplotLayer<FountainFeature> {
  const cfg = {
    ...DEFAULT_CONFIG,
    id: 'minimap-fountains',
    fillColor: [100, 150, 200, 150] as [number, number, number, number], // Blue-gray
    pickable: false,
    ...config,
  };

  return new ScatterplotLayer<FountainFeature>({
    id: cfg.id,
    data,
    visible: cfg.visible,
    getPosition: (d) => d.geometry.coordinates,
    getRadius: 3, // Fixed radius
    getFillColor: cfg.fillColor,
    opacity: cfg.opacity,
    pickable: cfg.pickable,
    radiusUnits: 'meters',
    radiusMinPixels: 2,
    radiusMaxPixels: 6,
  });
}
