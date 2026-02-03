/**
 * Terrain Layer Factory
 *
 * Creates deck.gl layers for rendering ground plane and optional grid overlay.
 */

import { SolidPolygonLayer, PathLayer } from '@deck.gl/layers';
import { ZURICH_BOUNDS } from '@/lib/constants';
import { ZURICH_BASE_ELEVATION } from '@/types';
import type { LngLat, Position3D } from '@/types';

export interface TerrainLayerConfig {
  id?: string;
  fillColor?: [number, number, number, number];
  opacity?: number;
  elevation?: number;
}

export interface GridLayerConfig {
  id?: string;
  lineColor?: [number, number, number, number];
  lineWidth?: number;
  gridSize?: number; // Grid cell size in degrees
  opacity?: number;
}

const DEFAULT_TERRAIN_CONFIG: Required<TerrainLayerConfig> = {
  id: 'terrain',
  fillColor: [80, 140, 80, 255], // Brighter green for visibility
  opacity: 1,
  elevation: ZURICH_BASE_ELEVATION - 0.5, // Slightly below buildings to avoid z-fighting
};

const DEFAULT_GRID_CONFIG: Required<GridLayerConfig> = {
  id: 'grid',
  lineColor: [60, 100, 65, 200],
  lineWidth: 1,
  gridSize: 0.005, // ~375m at Zurich latitude
  opacity: 0.5,
};

/**
 * Generate ground polygon vertices covering Zurich bounds with elevation
 */
function getGroundPolygon(elevation: number): Position3D[] {
  const { minLng, maxLng, minLat, maxLat } = ZURICH_BOUNDS;

  // Counter-clockwise polygon with elevation (for proper face culling)
  return [
    [minLng, minLat, elevation],
    [minLng, maxLat, elevation],
    [maxLng, maxLat, elevation],
    [maxLng, minLat, elevation],
    [minLng, minLat, elevation], // Close the polygon
  ];
}

/**
 * Generate grid lines within Zurich bounds
 */
function generateGridLines(gridSize: number): LngLat[][] {
  const { minLng, maxLng, minLat, maxLat } = ZURICH_BOUNDS;
  const lines: LngLat[][] = [];

  // Vertical lines (longitude)
  for (let lng = Math.ceil(minLng / gridSize) * gridSize; lng <= maxLng; lng += gridSize) {
    lines.push([
      [lng, minLat],
      [lng, maxLat],
    ]);
  }

  // Horizontal lines (latitude)
  for (let lat = Math.ceil(minLat / gridSize) * gridSize; lat <= maxLat; lat += gridSize) {
    lines.push([
      [minLng, lat],
      [maxLng, lat],
    ]);
  }

  return lines;
}

interface GroundData {
  polygon: Position3D[];
}

/**
 * Create a ground plane layer covering Zurich area
 *
 * @param config - Layer configuration options
 */
export function createTerrainLayer(
  config: TerrainLayerConfig = {}
): SolidPolygonLayer<GroundData> {
  const mergedConfig = { ...DEFAULT_TERRAIN_CONFIG, ...config };

  const groundData: GroundData[] = [{ polygon: getGroundPolygon(mergedConfig.elevation) }];

  return new SolidPolygonLayer<GroundData>({
    id: mergedConfig.id,
    data: groundData,
    getPolygon: (d) => d.polygon,
    extruded: true, // Use extruded for proper 3D rendering
    getElevation: () => 0.1, // Minimal height
    getFillColor: mergedConfig.fillColor,
    opacity: mergedConfig.opacity,
    pickable: false,
  });
}

interface GridLine {
  path: LngLat[];
}

/**
 * Create a grid overlay layer
 *
 * @param config - Layer configuration options
 */
export function createGridLayer(config: GridLayerConfig = {}): PathLayer<GridLine> {
  const mergedConfig = { ...DEFAULT_GRID_CONFIG, ...config };

  const gridLines = generateGridLines(mergedConfig.gridSize);
  const gridData: GridLine[] = gridLines.map((path) => ({ path }));

  return new PathLayer<GridLine>({
    id: mergedConfig.id,
    data: gridData,
    getPath: (d) => d.path,
    getColor: mergedConfig.lineColor,
    getWidth: mergedConfig.lineWidth,
    widthUnits: 'pixels',
    opacity: mergedConfig.opacity,
    pickable: false,
  });
}
