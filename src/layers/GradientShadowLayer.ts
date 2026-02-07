/**
 * Gradient Shadow Layer Factory
 *
 * Creates deck.gl layers for rendering shadows with penumbra gradient effect.
 * The shadows are darker near buildings (umbra) and fade toward the edges (penumbra).
 *
 * Uses a multi-layer approach:
 * 1. Core shadow layer (most opaque)
 * 2. Mid shadow layer (medium opacity)
 * 3. Outer shadow layer (faint, soft edge)
 *
 * This creates a smooth gradient effect without custom shaders.
 */

import { SolidPolygonLayer } from '@deck.gl/layers';
import type { Layer } from '@deck.gl/core';
import type { ShadowFeature, ShadowPolygon } from '@/lib/data/shadowLoader';

// Re-export shadow types
export type { ShadowFeature, ShadowPolygon };

/**
 * Configuration for gradient shadow layer
 */
export interface GradientShadowLayerProps {
  /** Layer ID prefix */
  id?: string;
  /** Shadow polygon data */
  data: ShadowFeature[];
  /** Base shadow color RGB (0-255) */
  shadowColor?: [number, number, number];
  /** Maximum opacity at the darkest point (0-1) */
  maxOpacity?: number;
  /** Sun altitude in degrees (affects shadow intensity) */
  sunAltitude?: number;
  /** Number of gradient layers (more = smoother but slower) */
  gradientLayers?: number;
}

const DEFAULT_PROPS = {
  id: 'gradient-shadows',
  shadowColor: [30, 30, 40] as [number, number, number],
  maxOpacity: 0.4,
  sunAltitude: 45,
  gradientLayers: 3,
};

/**
 * Calculate shadow opacity based on sun altitude
 * Higher sun = shorter, less intense shadows
 * Lower sun = longer, more pronounced shadows
 */
function calculateShadowIntensity(sunAltitude: number, baseOpacity: number): number {
  // At low sun angles (< 20°), shadows are most intense
  // At high sun angles (> 60°), shadows are faint
  const altitudeFactor = 1 - Math.min(1, Math.max(0, (sunAltitude - 10) / 60));
  return baseOpacity * (0.5 + 0.5 * altitudeFactor);
}

/**
 * Scale a polygon toward its centroid to create inner/outer rings
 */
function scalePolygon(
  coordinates: ShadowPolygon,
  centroid: [number, number],
  scale: number
): ShadowPolygon {
  return coordinates.map((ring) =>
    ring.map(([lng, lat]) => {
      const dx = lng - centroid[0];
      const dy = lat - centroid[1];
      return [centroid[0] + dx * scale, centroid[1] + dy * scale] as [number, number];
    })
  );
}

/**
 * Create gradient shadow layers
 *
 * Generates multiple stacked polygon layers with decreasing opacity to
 * simulate the penumbra (soft shadow edge) effect.
 *
 * @param config - Layer configuration
 * @returns Array of deck.gl layers
 */
export function createGradientShadowLayers(
  config: GradientShadowLayerProps
): Layer[] {
  const {
    id = DEFAULT_PROPS.id,
    data,
    shadowColor = DEFAULT_PROPS.shadowColor,
    maxOpacity = DEFAULT_PROPS.maxOpacity,
    sunAltitude = DEFAULT_PROPS.sunAltitude,
    gradientLayers = DEFAULT_PROPS.gradientLayers,
  } = config;

  if (!data || data.length === 0) {
    return [];
  }

  // Calculate adjusted opacity based on sun position
  const adjustedOpacity = calculateShadowIntensity(sunAltitude, maxOpacity);

  // Create gradient layers from outer (most transparent) to inner (most opaque)
  const layers: SolidPolygonLayer<ShadowFeature>[] = [];

  for (let i = 0; i < gradientLayers; i++) {
    // Calculate scale and opacity for this layer
    // Outer layers are larger (scale > 1) and more transparent
    // Inner layers are smaller (scale < 1) and more opaque
    const layerProgress = i / (gradientLayers - 1 || 1); // 0 = outer, 1 = inner
    const scale = 1 - layerProgress * 0.3; // 1.0 → 0.7 (outer to inner)
    const opacity = adjustedOpacity * (0.3 + layerProgress * 0.7); // 30% → 100% of max

    layers.push(
      new SolidPolygonLayer<ShadowFeature>({
        id: `${id}-gradient-${i}`,
        data,
        getPolygon: (d) => {
          // For inner layers, scale the polygon toward centroid
          if (scale < 1 && d.properties.centroid) {
            return scalePolygon(d.geometry.coordinates, d.properties.centroid, scale);
          }
          return d.geometry.coordinates;
        },
        getFillColor: [...shadowColor, Math.round(opacity * 255)] as [number, number, number, number],
        extruded: false,
        pickable: false,
        // Render order: outer layers first (behind), inner layers last (on top)
        getPolygonOffset: () => [0, -1000 + i * 10],
      })
    );
  }

  return layers;
}

/**
 * Simple gradient shadow layer using opacity-based falloff
 *
 * A simpler alternative that uses a single layer with per-polygon
 * opacity based on distance from building edge.
 */
export interface SimpleGradientShadowConfig {
  id?: string;
  /** Base shadow color RGB (0-255) */
  shadowColor?: [number, number, number];
  /** Maximum opacity (0-1) */
  maxOpacity?: number;
  /** Sun altitude in degrees */
  sunAltitude?: number;
}

/**
 * Create a simple gradient shadow layer
 *
 * Uses getFillColor accessor to compute per-polygon colors based on
 * the polygon's `opacity` property (from shadowLoader).
 */
export function createGradientShadowLayer(
  data: ShadowFeature[],
  config: SimpleGradientShadowConfig = {}
): SolidPolygonLayer<ShadowFeature> {
  const {
    id = 'gradient-shadows',
    shadowColor = [30, 30, 40],
    maxOpacity = 0.5,
    sunAltitude = 45,
  } = config;

  // Adjust base opacity based on sun altitude
  const adjustedOpacity = calculateShadowIntensity(sunAltitude, maxOpacity);

  return new SolidPolygonLayer<ShadowFeature>({
    id,
    data,
    getPolygon: (d) => d.geometry.coordinates,
    getFillColor: (d) => {
      // Use the pre-computed opacity from shadow data
      // This allows distance-from-building-based gradients
      const polygonOpacity = d.properties.opacity ?? 1;
      const finalOpacity = adjustedOpacity * polygonOpacity;
      return [...shadowColor, Math.round(finalOpacity * 255)] as [number, number, number, number];
    },
    extruded: false,
    pickable: false,
    // Render below other layers
    getPolygonOffset: () => [0, -1000],
  });
}

/**
 * Create a multi-ring gradient shadow effect
 *
 * Generates multiple shadow polygons at different scales to create
 * a smooth penumbra gradient effect.
 *
 * @param shadowData - Original shadow polygon data
 * @param rings - Number of gradient rings (default: 4)
 * @returns Array of shadow features with decreasing opacity
 */
export function expandShadowsWithGradient(
  shadowData: ShadowFeature[],
  rings: number = 4
): ShadowFeature[] {
  const expandedShadows: ShadowFeature[] = [];

  for (const shadow of shadowData) {
    const centroid = shadow.properties.centroid;
    if (!centroid) continue;

    for (let i = 0; i < rings; i++) {
      // Progress from outer (0) to inner (1)
      const progress = i / (rings - 1 || 1);
      // Scale: outer rings are original size, inner rings are smaller
      const scale = 1 - progress * 0.4;
      // Opacity: outer rings are faint, inner rings are dark
      const opacity = 0.2 + progress * 0.8;

      expandedShadows.push({
        type: 'Feature',
        properties: {
          ...shadow.properties,
          opacity,
          ringIndex: i,
        },
        geometry: {
          type: 'Polygon',
          coordinates: scalePolygon(shadow.geometry.coordinates, centroid, scale),
        },
      });
    }
  }

  return expandedShadows;
}

/**
 * GradientShadowLayer class (alias for backwards compatibility)
 *
 * This is a wrapper that creates gradient shadow layers.
 * Usage: new GradientShadowLayer(props) -> call getLayers() to get the actual layers
 */
export class GradientShadowLayer {
  static layerName = 'GradientShadowLayer';
  private props: GradientShadowLayerProps;

  constructor(props: GradientShadowLayerProps) {
    this.props = props;
  }

  /**
   * Get the deck.gl layers for this shadow layer
   */
  getLayers(): Layer[] {
    return createGradientShadowLayers(this.props);
  }
}
