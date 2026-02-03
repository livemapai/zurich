/**
 * Toilets Layer Factory
 *
 * Creates deck.gl layers for rendering public toilets (Züri WC) as 3D kiosk shapes.
 * Data: ~200 public toilets from Züri WC (Stadt Zürich Open Data)
 */

import { SimpleMeshLayer, type SimpleMeshLayerProps } from '@deck.gl/mesh-layers';
import { ScatterplotLayer } from '@deck.gl/layers';
import { ZURICH_BASE_ELEVATION } from '@/types';
import type { LngLat } from '@/types';
import { generateToiletMesh } from '@/utils/toiletGeometry';

export interface ToiletProperties {
  id: string;
  name: string;
  address: string;
  category: string;
  hours: string;
  fee: string;
  accessible: boolean;
  elevation?: number;
}

export interface PointGeometry {
  type: 'Point';
  coordinates: LngLat;
}

export interface ToiletFeature {
  type: 'Feature';
  properties: ToiletProperties;
  geometry: PointGeometry;
}

export interface ToiletCollection {
  type: 'FeatureCollection';
  features: ToiletFeature[];
}

export interface ToiletsLayerConfig {
  id?: string;
  fillColor?: [number, number, number, number];
  opacity?: number;
  visible?: boolean;
  pickable?: boolean;
}

const DEFAULT_CONFIG: Required<ToiletsLayerConfig> = {
  id: 'toilets',
  fillColor: [100, 149, 237, 255], // Cornflower blue
  opacity: 1.0,
  visible: true,
  pickable: true,
};

const TOILET_MESH = generateToiletMesh() as unknown as SimpleMeshLayerProps['mesh'];

export function createToiletsLayer(
  data: ToiletFeature[],
  config: ToiletsLayerConfig = {}
): SimpleMeshLayer<ToiletFeature> {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  if (data.length > 0) {
    const elevations = data.map(d => d.properties.elevation ?? ZURICH_BASE_ELEVATION);
    const withElevation = data.filter(d => d.properties.elevation !== undefined).length;
    const min = Math.min(...elevations);
    const max = Math.max(...elevations);
    console.log(`[Toilets] ${data.length} total, ${withElevation} with elevation, range: ${min.toFixed(1)}m - ${max.toFixed(1)}m`);
  }

  return new SimpleMeshLayer<ToiletFeature>({
    id: cfg.id,
    data,
    visible: cfg.visible,
    mesh: TOILET_MESH,

    getPosition: (d) => {
      const elevation = d.properties.elevation ?? ZURICH_BASE_ELEVATION;
      return [...d.geometry.coordinates, elevation] as [number, number, number];
    },

    getScale: [3.0, 2.5, 3.0], // ~3m wide × 2.5m deep × 3m tall

    getColor: cfg.fillColor,
    getOrientation: [0, 0, 0],

    material: {
      ambient: 0.4,
      diffuse: 0.6,
      shininess: 20,
    },

    pickable: cfg.pickable,
  });
}

export function createMinimapToiletsLayer(
  data: ToiletFeature[],
  config: Partial<ToiletsLayerConfig> = {}
): ScatterplotLayer<ToiletFeature> {
  const cfg = {
    ...DEFAULT_CONFIG,
    id: 'minimap-toilets',
    fillColor: [100, 149, 237, 180] as [number, number, number, number],
    pickable: false,
    ...config,
  };

  return new ScatterplotLayer<ToiletFeature>({
    id: cfg.id,
    data,
    visible: cfg.visible,
    getPosition: (d) => d.geometry.coordinates,
    getRadius: 4,
    getFillColor: cfg.fillColor,
    opacity: cfg.opacity,
    pickable: cfg.pickable,
    radiusUnits: 'meters',
    radiusMinPixels: 2,
    radiusMaxPixels: 6,
  });
}
