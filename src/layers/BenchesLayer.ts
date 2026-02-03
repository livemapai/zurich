/**
 * Benches Layer Factory
 *
 * Creates deck.gl layers for rendering benches as 3D procedural shapes.
 * Each bench is a seat slab with a backrest.
 * Data: ~4,000-6,000 benches from Sitzbankkataster (Stadt Zürich Open Data)
 *
 * Reads terrain elevation from feature.properties.elevation (pre-computed).
 */

import { SimpleMeshLayer, type SimpleMeshLayerProps } from '@deck.gl/mesh-layers';
import { ScatterplotLayer } from '@deck.gl/layers';
import { ZURICH_BASE_ELEVATION } from '@/types';
import type { LngLat } from '@/types';
import { generateBenchMesh } from '@/utils/benchGeometry';

/** Properties for a bench feature */
export interface BenchProperties {
  id: string;
  address: string;
  model?: string;
  elevation?: number;
}

/** Point geometry type */
export interface PointGeometry {
  type: 'Point';
  coordinates: LngLat;
}

/** GeoJSON feature for a bench */
export interface BenchFeature {
  type: 'Feature';
  properties: BenchProperties;
  geometry: PointGeometry;
}

/** GeoJSON FeatureCollection for benches */
export interface BenchCollection {
  type: 'FeatureCollection';
  features: BenchFeature[];
}

/** Configuration for benches layer */
export interface BenchesLayerConfig {
  id?: string;
  fillColor?: [number, number, number, number];
  opacity?: number;
  visible?: boolean;
  pickable?: boolean;
}

const DEFAULT_CONFIG: Required<BenchesLayerConfig> = {
  id: 'benches',
  fillColor: [139, 90, 43, 255], // Wood brown
  opacity: 1.0,
  visible: true,
  pickable: true,
};

// Generate mesh once (reused for all benches)
// Cast to expected mesh type - SimpleMeshLayer accepts plain objects with positions/normals/indices at runtime
const BENCH_MESH = generateBenchMesh() as unknown as SimpleMeshLayerProps['mesh'];

/**
 * Create a 3D benches layer with procedural seat+backrest shapes
 *
 * Elevation is read from feature.properties.elevation (pre-computed by
 * scripts/terrain/add_elevations.py). Falls back to ZURICH_BASE_ELEVATION (408m).
 *
 * @param data - Array of BenchFeature objects
 * @param config - Layer configuration options
 */
export function createBenchesLayer(
  data: BenchFeature[],
  config: BenchesLayerConfig = {}
): SimpleMeshLayer<BenchFeature> {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  // Debug: log elevation statistics
  if (data.length > 0) {
    const elevations = data.map(d => d.properties.elevation ?? ZURICH_BASE_ELEVATION);
    const withElevation = data.filter(d => d.properties.elevation !== undefined).length;
    const min = Math.min(...elevations);
    const max = Math.max(...elevations);
    console.log(`[Benches] ${data.length} total, ${withElevation} with elevation, range: ${min.toFixed(1)}m - ${max.toFixed(1)}m`);
  }

  return new SimpleMeshLayer<BenchFeature>({
    id: cfg.id,
    data,
    visible: cfg.visible,
    mesh: BENCH_MESH,

    // Position at bench location with terrain elevation from properties
    getPosition: (d) => {
      const elevation = d.properties.elevation ?? ZURICH_BASE_ELEVATION;
      return [...d.geometry.coordinates, elevation] as [number, number, number];
    },

    // Scale: ~1.5m wide bench (unit mesh is 1m)
    getScale: [1.5, 1.5, 1.0],

    getColor: cfg.fillColor,
    getOrientation: [0, 0, 0], // No rotation

    // Material settings for wood-like appearance
    material: {
      ambient: 0.5,
      diffuse: 0.5,
      shininess: 10, // Low shininess for wood
    },

    pickable: cfg.pickable,
  });
}

/**
 * Create a benches layer for minimap display (2D circles, simpler)
 *
 * @param data - Array of BenchFeature objects
 * @param config - Layer configuration options
 */
export function createMinimapBenchesLayer(
  data: BenchFeature[],
  config: Partial<BenchesLayerConfig> = {}
): ScatterplotLayer<BenchFeature> {
  const cfg = {
    ...DEFAULT_CONFIG,
    id: 'minimap-benches',
    fillColor: [139, 90, 43, 120] as [number, number, number, number], // Semi-transparent brown
    pickable: false,
    ...config,
  };

  return new ScatterplotLayer<BenchFeature>({
    id: cfg.id,
    data,
    visible: cfg.visible,
    getPosition: (d) => d.geometry.coordinates,
    getRadius: 2, // Small fixed radius
    getFillColor: cfg.fillColor,
    opacity: cfg.opacity,
    pickable: cfg.pickable,
    radiusUnits: 'meters',
    radiusMinPixels: 1,
    radiusMaxPixels: 4,
  });
}
