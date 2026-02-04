/**
 * Buildings Layer Factory
 *
 * Creates deck.gl layers for rendering 3D extruded buildings.
 * Reads terrain elevation from feature.properties.elevation (pre-computed).
 */

import { SolidPolygonLayer } from '@deck.gl/layers';
import { ZURICH_BASE_ELEVATION } from '@/types';
import type { BuildingFeature, LngLat, Position3D } from '@/types';

export interface BuildingsLayerConfig {
  id?: string;
  fillColor?: [number, number, number, number];
  highlightColor?: [number, number, number, number];
  opacity?: number;
  pickable?: boolean;
  autoHighlight?: boolean;
  baseElevation?: number;
  /** Use per-feature terrain elevation (true) or flat base elevation (false). Default: true */
  useTerrainElevation?: boolean;
}

const DEFAULT_CONFIG: Required<BuildingsLayerConfig> = {
  id: 'buildings',
  fillColor: [200, 200, 220, 255],
  highlightColor: [255, 200, 100, 255],
  opacity: 1,
  pickable: true,
  autoHighlight: true,
  baseElevation: ZURICH_BASE_ELEVATION,
  useTerrainElevation: true,
};

/**
 * Extract the outer ring from a building geometry with terrain elevation
 * Reads elevation from feature.properties.elevation (pre-computed by Python script)
 *
 * @param feature - Building feature with geometry and elevation property
 * @param baseElevation - Fallback elevation if feature has no elevation
 * @param useTerrainElevation - If true, use per-feature terrain elevation; if false, use flat base elevation
 */
function getPolygonCoordinates(
  feature: BuildingFeature,
  baseElevation: number,
  useTerrainElevation: boolean
): Position3D[] {
  const { geometry } = feature;
  let coords: LngLat[];

  if (geometry.type === 'MultiPolygon') {
    // Use the first polygon's outer ring
    coords = (geometry.coordinates[0]?.[0] ?? []) as LngLat[];
  } else {
    // Polygon - use outer ring
    coords = (geometry.coordinates[0] ?? []) as LngLat[];
  }

  // Use terrain elevation only if enabled, otherwise use flat base elevation
  const elevation = useTerrainElevation
    ? (feature.properties.elevation ?? baseElevation)
    : baseElevation;

  // Add terrain elevation to each coordinate
  return coords.map(([lng, lat]) => [lng, lat, elevation]);
}

/**
 * Create a 3D extruded buildings layer
 *
 * Elevation is read from feature.properties.elevation (pre-computed by
 * scripts/terrain/add_elevations.py). Falls back to baseElevation (408m).
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

  // Debug: log elevation statistics
  if (data.length > 0) {
    const elevations = data.map(d => d.properties.elevation ?? baseElev);
    const withElevation = data.filter(d => d.properties.elevation !== undefined).length;
    const min = Math.min(...elevations);
    const max = Math.max(...elevations);
    console.log(`[Buildings] ${data.length} total, ${withElevation} with elevation, range: ${min.toFixed(1)}m - ${max.toFixed(1)}m`);
  }

  return new SolidPolygonLayer<BuildingFeature>({
    id: mergedConfig.id,
    data,
    getPolygon: (d) => getPolygonCoordinates(d, baseElev, mergedConfig.useTerrainElevation),
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
    // Force getPolygon re-evaluation when terrain elevation mode changes
    updateTriggers: {
      getPolygon: [mergedConfig.useTerrainElevation],
    },
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
    getPolygon: (d) => getPolygonCoordinates(d, 0, false), // Minimap uses z=0 (2D view, flat)
    extruded: false, // Flat for minimap
    getFillColor: mergedConfig.fillColor,
    opacity: mergedConfig.opacity,
    pickable: mergedConfig.pickable,
  });
}
