/**
 * Buildings Layer Factory
 *
 * Creates deck.gl layers for rendering 3D extruded buildings.
 */

import { SolidPolygonLayer } from '@deck.gl/layers';
import type { BuildingFeature, LngLat, Position3D } from '@/types';

/** Zurich base elevation in meters - set to 0 for coordinate system test */
const ZURICH_BASE_ELEVATION = 0;

export interface BuildingsLayerConfig {
  id?: string;
  fillColor?: [number, number, number, number];
  highlightColor?: [number, number, number, number];
  opacity?: number;
  pickable?: boolean;
  autoHighlight?: boolean;
  baseElevation?: number;
}

const DEFAULT_CONFIG: Required<BuildingsLayerConfig> = {
  id: 'buildings',
  fillColor: [200, 200, 220, 255],
  highlightColor: [255, 200, 100, 255],
  opacity: 1,
  pickable: true,
  autoHighlight: true,
  baseElevation: ZURICH_BASE_ELEVATION,
};

/**
 * Extract the outer ring from a building geometry with base elevation
 */
function getPolygonCoordinates(feature: BuildingFeature, baseElevation: number): Position3D[] {
  const { geometry } = feature;
  let coords: LngLat[];

  if (geometry.type === 'MultiPolygon') {
    // Use the first polygon's outer ring
    coords = (geometry.coordinates[0]?.[0] ?? []) as LngLat[];
  } else {
    // Polygon - use outer ring
    coords = (geometry.coordinates[0] ?? []) as LngLat[];
  }

  // Add base elevation to each coordinate
  return coords.map(([lng, lat]) => [lng, lat, baseElevation]);
}

/**
 * Create a 3D extruded buildings layer
 *
 * @param data - Array of BuildingFeature objects
 * @param config - Layer configuration options
 */
export function createBuildingsLayer(
  data: BuildingFeature[],
  config: BuildingsLayerConfig = {}
): SolidPolygonLayer<BuildingFeature> {
  const mergedConfig = { ...DEFAULT_CONFIG, ...config };
  const baseElev = mergedConfig.baseElevation;

  return new SolidPolygonLayer<BuildingFeature>({
    id: mergedConfig.id,
    data,
    getPolygon: (d) => getPolygonCoordinates(d, baseElev),
    extruded: true,
    getElevation: (d) => d.properties.height || 10,
    getFillColor: mergedConfig.fillColor,
    highlightColor: mergedConfig.highlightColor,
    opacity: mergedConfig.opacity,
    pickable: mergedConfig.pickable,
    autoHighlight: mergedConfig.autoHighlight,
    material: {
      ambient: 0.35,
      diffuse: 0.6,
      shininess: 32,
      specularColor: [60, 64, 70],
    },
    elevationScale: 1,
  });
}

/**
 * Create a flat buildings layer for minimap display
 *
 * @param data - Array of BuildingFeature objects
 * @param config - Layer configuration options
 */
export function createMinimapBuildingsLayer(
  data: BuildingFeature[],
  config: Partial<BuildingsLayerConfig> = {}
): SolidPolygonLayer<BuildingFeature> {
  const mergedConfig = {
    ...DEFAULT_CONFIG,
    id: 'minimap-buildings',
    fillColor: [80, 80, 100, 200] as [number, number, number, number],
    pickable: false,
    autoHighlight: false,
    ...config,
  };

  return new SolidPolygonLayer<BuildingFeature>({
    id: mergedConfig.id,
    data,
    getPolygon: (d) => getPolygonCoordinates(d, 0), // Minimap uses z=0 (2D view)
    extruded: false, // Flat for minimap
    getFillColor: mergedConfig.fillColor,
    opacity: mergedConfig.opacity,
    pickable: mergedConfig.pickable,
  });
}
