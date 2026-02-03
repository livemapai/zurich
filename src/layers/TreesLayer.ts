/**
 * Trees Layer Factory
 *
 * Creates deck.gl layers for rendering trees as 3D procedural shapes.
 * Each tree is a cone (crown) on top of a cylinder (trunk).
 * Data: ~80,000 trees from Baumkataster (Stadt Zürich Open Data)
 *
 * Reads terrain elevation from feature.properties.elevation (pre-computed).
 */

import { SimpleMeshLayer, type SimpleMeshLayerProps } from '@deck.gl/mesh-layers';
import { ScatterplotLayer } from '@deck.gl/layers';
import { ZURICH_BASE_ELEVATION } from '@/types';
import type { LngLat } from '@/types';
import { generateTreeMesh } from '@/utils/treeGeometry';

/** Properties for a tree feature */
export interface TreeProperties {
  /** Unique tree identifier */
  id: string;
  /** Latin species name */
  species?: string;
  /** German species name */
  species_de?: string;
  /** Tree height in meters */
  height: number;
  /** Crown diameter in meters */
  crown_diameter: number;
  /** Trunk diameter in meters */
  trunk_diameter: number;
  /** Year planted (optional) */
  year_planted?: number;
  /** Ground elevation in meters (from terrain) */
  elevation?: number;
}

/** GeoJSON Point geometry */
export interface PointGeometry {
  type: 'Point';
  coordinates: LngLat;
}

/** GeoJSON Feature for a tree */
export interface TreeFeature {
  type: 'Feature';
  properties: TreeProperties;
  geometry: PointGeometry;
}

/** GeoJSON FeatureCollection for trees */
export interface TreeCollection {
  type: 'FeatureCollection';
  features: TreeFeature[];
}

/** Configuration for trees layer */
export interface TreesLayerConfig {
  id?: string;
  fillColor?: [number, number, number, number];
  opacity?: number;
  visible?: boolean;
  pickable?: boolean;
}

const DEFAULT_CONFIG: Required<TreesLayerConfig> = {
  id: 'trees',
  fillColor: [34, 139, 34, 200], // Forest green
  opacity: 1.0,
  visible: true,
  pickable: true,
};

// Generate mesh once (reused for all ~80k trees)
// Cast to expected mesh type - SimpleMeshLayer accepts plain objects with positions/normals/indices at runtime
const TREE_MESH = generateTreeMesh(12, 8, 0.7) as unknown as SimpleMeshLayerProps['mesh'];

/**
 * Create a 3D trees layer with procedural cone+cylinder shapes
 *
 * Elevation is read from feature.properties.elevation (pre-computed by
 * scripts/terrain/add_elevations.py). Falls back to ZURICH_BASE_ELEVATION (408m).
 *
 * @param data - Array of TreeFeature objects
 * @param config - Layer configuration options
 */
export function createTreesLayer(
  data: TreeFeature[],
  config: TreesLayerConfig = {}
): SimpleMeshLayer<TreeFeature> {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  // Debug: log elevation statistics
  if (data.length > 0) {
    const elevations = data.map(d => d.properties.elevation ?? ZURICH_BASE_ELEVATION);
    const withElevation = data.filter(d => d.properties.elevation !== undefined).length;
    const min = Math.min(...elevations);
    const max = Math.max(...elevations);
    console.log(`[Trees] ${data.length} total, ${withElevation} with elevation, range: ${min.toFixed(1)}m - ${max.toFixed(1)}m`);
  }

  return new SimpleMeshLayer<TreeFeature>({
    id: cfg.id,
    data,
    visible: cfg.visible,
    mesh: TREE_MESH,

    // Position at tree location with terrain elevation from properties
    getPosition: (d) => {
      const elevation = d.properties.elevation ?? ZURICH_BASE_ELEVATION;
      return [...d.geometry.coordinates, elevation] as [number, number, number];
    },

    // Scale mesh to match tree dimensions
    // The unit mesh is 1m tall, crown radius 0.5, so we scale:
    // X/Y by crown_diameter (since unit mesh has diameter of 1)
    // Z by height
    getScale: (d) => {
      const height = d.properties.height || 10;
      const crownDiam = d.properties.crown_diameter || 5;
      return [crownDiam, crownDiam, height];
    },

    getColor: cfg.fillColor,
    getOrientation: [0, 0, 0], // No rotation

    // Material settings for 3D appearance
    material: {
      ambient: 0.4,
      diffuse: 0.6,
      shininess: 16,
    },

    pickable: cfg.pickable,
  });
}

/**
 * Create a trees layer for minimap display (2D circles, simpler)
 *
 * @param data - Array of TreeFeature objects
 * @param config - Layer configuration options
 */
export function createMinimapTreesLayer(
  data: TreeFeature[],
  config: Partial<TreesLayerConfig> = {}
): ScatterplotLayer<TreeFeature> {
  const cfg = {
    ...DEFAULT_CONFIG,
    id: 'minimap-trees',
    fillColor: [34, 139, 34, 120] as [number, number, number, number],
    pickable: false,
    ...config,
  };

  return new ScatterplotLayer<TreeFeature>({
    id: cfg.id,
    data,
    visible: cfg.visible,
    getPosition: (d) => d.geometry.coordinates,
    getRadius: (d) => (d.properties.crown_diameter || 5) / 2,
    getFillColor: cfg.fillColor,
    opacity: cfg.opacity,
    pickable: cfg.pickable,
    radiusUnits: 'meters',
    radiusMinPixels: 1,
    radiusMaxPixels: 10,
  });
}
