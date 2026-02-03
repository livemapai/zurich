/**
 * Overhead Poles Layer Factory
 *
 * Creates deck.gl SimpleMeshLayer for rendering tram/trolleybus overhead line poles.
 * Each pole is rendered as a 3D cylinder using absolute elevation from VBZ data.
 *
 * Key insight: VBZ data provides absolute elevations (meters above sea level):
 * - hoehemastuk: Bottom of pole (ground level, ~399-410m in Zurich)
 * - hoehemastok: Top of pole (bottom + pole height, typically +8-12m)
 *
 * Data: ~4,600 poles from VBZ_Infrastruktur_OGD
 */

import { SimpleMeshLayer, type SimpleMeshLayerProps } from '@deck.gl/mesh-layers';
import type { OverheadPoleFeature, ProcessedPole } from '@/types';
import { generatePoleMesh } from '@/utils/poleGeometry';

// Re-export types for convenience
export type { OverheadPoleFeature, ProcessedPole };

/** Configuration for overhead poles layer */
export interface OverheadPolesLayerConfig {
  id?: string;
  color?: [number, number, number, number];
  opacity?: number;
  visible?: boolean;
  pickable?: boolean;
}

/** Default configuration values */
const DEFAULT_CONFIG: Required<OverheadPolesLayerConfig> = {
  id: 'overhead-poles',
  color: [60, 60, 60, 255],  // Dark gray (metallic poles)
  opacity: 1.0,
  visible: true,
  pickable: true,
};

// Generate mesh once (reused for all ~4,600 poles)
// Cast to expected mesh type - SimpleMeshLayer accepts plain objects at runtime
const POLE_MESH = generatePoleMesh(8, 0.15) as unknown as SimpleMeshLayerProps['mesh'];

/** Default pole height when data is missing */
const DEFAULT_POLE_HEIGHT = 10;

/**
 * Process overhead pole features into flat array
 *
 * MultiPoint geometries are flattened, and elevation data is extracted.
 * Handles missing elevation data gracefully with defaults.
 *
 * @param features - Array of OverheadPoleFeature from GeoJSON
 * @returns Array of processed poles ready for SimpleMeshLayer
 */
export function processOverheadPoles(features: OverheadPoleFeature[]): ProcessedPole[] {
  return features.flatMap((feature) =>
    feature.geometry.coordinates.map((coord) => ({
      position: coord as [number, number],
      topHeight: feature.properties.hoehemastok || 418,  // Default ~10m above base
      bottomHeight: feature.properties.hoehemastuk || 408,  // Default Zurich ground level
    }))
  );
}

/**
 * Create a 3D overhead poles layer
 *
 * Renders poles as vertical cylinders using absolute elevation from VBZ data.
 * The mesh is scaled per-instance based on actual pole height.
 *
 * @param data - Array of OverheadPoleFeature objects
 * @param config - Layer configuration options
 */
export function createOverheadPolesLayer(
  data: OverheadPoleFeature[],
  config: OverheadPolesLayerConfig = {}
): SimpleMeshLayer<ProcessedPole> {
  const cfg = { ...DEFAULT_CONFIG, ...config };
  const poles = processOverheadPoles(data);

  return new SimpleMeshLayer<ProcessedPole>({
    id: cfg.id,
    data: poles,
    visible: cfg.visible,
    mesh: POLE_MESH,

    // Position at pole location with bottom elevation (absolute meters ASL)
    getPosition: (d) => [...d.position, d.bottomHeight] as [number, number, number],

    // Scale mesh: unit mesh is 1m tall, scale Z to actual pole height
    // X and Y remain at 1 (radius already set in mesh generation)
    getScale: (d) => {
      const height = d.topHeight - d.bottomHeight;
      // Sanity check: pole height should be positive and reasonable
      const safeHeight = height > 0 && height < 50 ? height : DEFAULT_POLE_HEIGHT;
      return [1, 1, safeHeight];
    },

    getColor: cfg.color,
    getOrientation: [0, 0, 0],  // Poles are vertical

    // Material settings for metallic appearance
    material: {
      ambient: 0.4,
      diffuse: 0.6,
      shininess: 32,
    },

    pickable: cfg.pickable,
  });
}
