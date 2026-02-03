/**
 * Lights Layer Factory
 *
 * Creates deck.gl layers for rendering street lights as 3D procedural shapes.
 * Each light is a thin pole with a lamp fixture at the top.
 * Data: ~40,000 lights from Öffentliche Beleuchtung (Stadt Zürich Open Data)
 *
 * Reads terrain elevation from feature.properties.elevation (pre-computed).
 */

import { SimpleMeshLayer, type SimpleMeshLayerProps } from '@deck.gl/mesh-layers';
import { ScatterplotLayer } from '@deck.gl/layers';
import { ZURICH_BASE_ELEVATION } from '@/types';
import type { LightFeature, LightProperties, PointGeometry } from '@/types';
import { generateLightMesh } from '@/utils/lightGeometry';

// Re-export types for convenience
export type { LightFeature, LightProperties, PointGeometry };

/** Configuration for lights layer */
export interface LightsLayerConfig {
  id?: string;
  fillColor?: [number, number, number, number];
  opacity?: number;
  visible?: boolean;
  pickable?: boolean;
}

const DEFAULT_CONFIG: Required<LightsLayerConfig> = {
  id: 'lights',
  fillColor: [80, 80, 80, 255], // Dark gray for poles
  opacity: 1.0,
  visible: true,
  pickable: true,
};

// Generate mesh once (reused for all ~40k lights)
// Cast to expected mesh type - SimpleMeshLayer accepts plain objects with positions/normals/indices at runtime
const LIGHT_MESH = generateLightMesh(8, 8, 0.15) as unknown as SimpleMeshLayerProps['mesh'];

/**
 * Create a 3D lights layer with procedural pole+lamp shapes
 *
 * Elevation is read from feature.properties.elevation (pre-computed by
 * scripts/terrain/add_elevations.py). Falls back to ZURICH_BASE_ELEVATION (408m).
 *
 * @param data - Array of LightFeature objects
 * @param config - Layer configuration options
 */
export function createLightsLayer(
  data: LightFeature[],
  config: LightsLayerConfig = {}
): SimpleMeshLayer<LightFeature> {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  // Debug: log elevation statistics
  if (data.length > 0) {
    const elevations = data.map(d => d.properties.elevation ?? ZURICH_BASE_ELEVATION);
    const withElevation = data.filter(d => d.properties.elevation !== undefined).length;
    const min = Math.min(...elevations);
    const max = Math.max(...elevations);
    console.log(`[Lights] ${data.length} total, ${withElevation} with elevation, range: ${min.toFixed(1)}m - ${max.toFixed(1)}m`);
  }

  return new SimpleMeshLayer<LightFeature>({
    id: cfg.id,
    data,
    visible: cfg.visible,
    mesh: LIGHT_MESH,

    // Position at light location with terrain elevation from properties
    getPosition: (d) => {
      const elevation = d.properties.elevation ?? ZURICH_BASE_ELEVATION;
      return [...d.geometry.coordinates, elevation] as [number, number, number];
    },

    // Scale mesh to match light dimensions
    // Unit mesh is 1m tall, pole radius 0.03m, lamp radius 0.15m
    // Scale uniformly by height (typical street light: 6-10m)
    getScale: (d) => {
      const height = d.properties.height || 6;
      return [height * 0.5, height * 0.5, height]; // Slight horizontal scaling
    },

    getColor: cfg.fillColor,
    getOrientation: [0, 0, 0], // No rotation

    // Material settings for metallic appearance
    material: {
      ambient: 0.5,
      diffuse: 0.5,
      shininess: 32, // Metallic appearance
    },

    pickable: cfg.pickable,
  });
}

/**
 * Create a lights layer for minimap display (2D circles, simpler)
 *
 * @param data - Array of LightFeature objects
 * @param config - Layer configuration options
 */
export function createMinimapLightsLayer(
  data: LightFeature[],
  config: Partial<LightsLayerConfig> = {}
): ScatterplotLayer<LightFeature> {
  const cfg = {
    ...DEFAULT_CONFIG,
    id: 'minimap-lights',
    fillColor: [255, 200, 50, 150] as [number, number, number, number], // Yellow dots
    pickable: false,
    ...config,
  };

  return new ScatterplotLayer<LightFeature>({
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
