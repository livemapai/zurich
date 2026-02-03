/**
 * {LayerName}Layer - {description}
 *
 * @module layers/{LayerName}Layer
 */

import { {DeckGLLayerClass} } from '{deckgl-import-path}';
import type { {DataType} } from '@/types';

export interface {LayerName}LayerConfig {
  visible?: boolean;
  opacity?: number;
  pickable?: boolean;
  // Add layer-specific config options
}

const DEFAULT_CONFIG: Required<{LayerName}LayerConfig> = {
  visible: true,
  opacity: 1,
  pickable: true,
};

/**
 * Creates a {LayerName} layer for deck.gl
 *
 * @param data - Array of {DataType} features
 * @param config - Layer configuration options
 * @returns Configured {DeckGLLayerClass} instance
 */
export function create{LayerName}Layer(
  data: {DataType}[],
  config: {LayerName}LayerConfig = {}
): {DeckGLLayerClass}<{DataType}> {
  const mergedConfig = { ...DEFAULT_CONFIG, ...config };

  return new {DeckGLLayerClass}<{DataType}>({
    id: '{layer-id}',
    data,

    // Geometry accessor
    // getPolygon: (d) => d.geometry.coordinates,
    // getPosition: (d) => d.position,

    // Appearance
    // getFillColor: [200, 200, 220, 255],

    // Config
    visible: mergedConfig.visible,
    opacity: mergedConfig.opacity,
    pickable: mergedConfig.pickable,
  });
}
