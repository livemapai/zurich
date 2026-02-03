/**
 * Minimap Layers Factory
 *
 * Creates deck.gl layers for the minimap overlay including:
 * - Player position marker
 * - View cone showing field of view direction
 * - Buildings footprints
 */

import { ScatterplotLayer, PolygonLayer } from '@deck.gl/layers';
import { DEG_TO_RAD } from '@/lib/constants';
import type { BuildingFeature, LngLat } from '@/types';
import { createMinimapBuildingsLayer } from './BuildingsLayer';

export interface MinimapConfig {
  playerPosition: LngLat;
  playerBearing: number;
  viewConeDistance?: number; // Distance in degrees
  viewConeAngle?: number; // Half-angle in degrees
  playerColor?: [number, number, number, number];
  viewConeColor?: [number, number, number, number];
}

const DEFAULT_VIEW_CONE_DISTANCE = 0.002; // ~150m at Zurich
const DEFAULT_VIEW_CONE_ANGLE = 30; // 60° total FOV
const DEFAULT_PLAYER_COLOR: [number, number, number, number] = [255, 100, 100, 255];
const DEFAULT_VIEW_CONE_COLOR: [number, number, number, number] = [255, 255, 100, 100];

interface PlayerMarker {
  position: LngLat;
}

interface ViewConeData {
  polygon: LngLat[];
}

/**
 * Create a view cone polygon (triangle showing look direction)
 */
function createViewConePolygon(
  position: LngLat,
  bearing: number,
  distance: number,
  halfAngle: number
): LngLat[] {
  const [lng, lat] = position;
  const bearingRad = bearing * DEG_TO_RAD;
  const leftAngle = bearingRad - halfAngle * DEG_TO_RAD;
  const rightAngle = bearingRad + halfAngle * DEG_TO_RAD;

  // Calculate cone vertices
  // Note: bearing 0 = North (+Y), 90 = East (+X)
  const leftLng = lng + Math.sin(leftAngle) * distance;
  const leftLat = lat + Math.cos(leftAngle) * distance;
  const rightLng = lng + Math.sin(rightAngle) * distance;
  const rightLat = lat + Math.cos(rightAngle) * distance;

  return [
    [lng, lat], // Player position (cone apex)
    [leftLng, leftLat], // Left edge of cone
    [rightLng, rightLat], // Right edge of cone
    [lng, lat], // Close polygon
  ];
}

/**
 * Create player position marker layer
 */
export function createPlayerMarkerLayer(
  position: LngLat,
  color: [number, number, number, number] = DEFAULT_PLAYER_COLOR
): ScatterplotLayer<PlayerMarker> {
  const playerData: PlayerMarker[] = [{ position }];

  return new ScatterplotLayer<PlayerMarker>({
    id: 'minimap-player',
    data: playerData,
    getPosition: (d) => d.position,
    getFillColor: color,
    getRadius: 8,
    radiusUnits: 'pixels',
    radiusMinPixels: 6,
    radiusMaxPixels: 12,
    pickable: false,
  });
}

/**
 * Create view cone layer showing player's field of view
 */
export function createViewConeLayer(
  position: LngLat,
  bearing: number,
  distance: number = DEFAULT_VIEW_CONE_DISTANCE,
  halfAngle: number = DEFAULT_VIEW_CONE_ANGLE,
  color: [number, number, number, number] = DEFAULT_VIEW_CONE_COLOR
): PolygonLayer<ViewConeData> {
  const conePolygon = createViewConePolygon(position, bearing, distance, halfAngle);

  const coneData: ViewConeData[] = [{ polygon: conePolygon }];

  return new PolygonLayer<ViewConeData>({
    id: 'minimap-view-cone',
    data: coneData,
    getPolygon: (d) => d.polygon,
    getFillColor: color,
    getLineColor: [255, 255, 100, 200],
    getLineWidth: 1,
    lineWidthUnits: 'pixels',
    pickable: false,
  });
}

/**
 * Create all minimap layers
 *
 * @param config - Minimap configuration
 * @param buildings - Optional building features for minimap display
 */
export function createMinimapLayers(
  config: MinimapConfig,
  buildings?: BuildingFeature[]
) {
  const {
    playerPosition,
    playerBearing,
    viewConeDistance = DEFAULT_VIEW_CONE_DISTANCE,
    viewConeAngle = DEFAULT_VIEW_CONE_ANGLE,
    playerColor = DEFAULT_PLAYER_COLOR,
    viewConeColor = DEFAULT_VIEW_CONE_COLOR,
  } = config;

  const layers = [];

  // Add buildings layer if data available
  if (buildings && buildings.length > 0) {
    layers.push(createMinimapBuildingsLayer(buildings));
  }

  // Add view cone (below player marker)
  layers.push(
    createViewConeLayer(
      playerPosition,
      playerBearing,
      viewConeDistance,
      viewConeAngle,
      viewConeColor
    )
  );

  // Add player marker (on top)
  layers.push(createPlayerMarkerLayer(playerPosition, playerColor));

  return layers;
}
