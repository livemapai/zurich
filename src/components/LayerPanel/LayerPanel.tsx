/**
 * LayerPanel Component
 *
 * UI panel for toggling visibility of map layers.
 * Organizes layers by category (Nature, Transport, POI, etc.)
 */

import { useCallback } from 'react';
import { TEXTURE_PROVIDERS, type TextureProviderId } from '@/layers/MapterhornTerrainLayer';

/** Single layer definition */
export interface LayerDefinition {
  /** Unique layer identifier */
  id: string;
  /** Display name */
  name: string;
  /** Category for grouping */
  category: string;
  /** Current visibility state */
  visible: boolean;
  /** Layer opacity (0-1) */
  opacity?: number;
  /** Whether this layer supports opacity control */
  supportsOpacity?: boolean;
  /** Feature count (optional) */
  count?: number;
}

export interface LayerPanelProps {
  /** Array of layer definitions */
  layers: LayerDefinition[];
  /** Callback when layer visibility is toggled */
  onToggle: (layerId: string) => void;
  /** Callback when layer opacity is changed */
  onOpacityChange?: (layerId: string, opacity: number) => void;
  /** Whether the panel is visible */
  visible?: boolean;
  /** Current terrain texture provider ID */
  terrainTexture?: TextureProviderId;
  /** Callback when terrain texture is changed */
  onTextureChange?: (providerId: TextureProviderId) => void;
}

/** Group layers by category */
function groupByCategory(
  layers: LayerDefinition[]
): Record<string, LayerDefinition[]> {
  return layers.reduce(
    (acc, layer) => {
      const category = layer.category;
      if (!acc[category]) {
        acc[category] = [];
      }
      acc[category].push(layer);
      return acc;
    },
    {} as Record<string, LayerDefinition[]>
  );
}

/**
 * LayerPanel - UI for toggling layer visibility
 */
export function LayerPanel({
  layers,
  onToggle,
  onOpacityChange,
  visible = true,
  terrainTexture = 'osm',
  onTextureChange,
}: LayerPanelProps) {
  const grouped = groupByCategory(layers);

  const handleToggle = useCallback(
    (layerId: string) => {
      onToggle(layerId);
    },
    [onToggle]
  );

  const handleOpacityChange = useCallback(
    (layerId: string, e: React.ChangeEvent<HTMLInputElement>) => {
      onOpacityChange?.(layerId, parseFloat(e.target.value));
    },
    [onOpacityChange]
  );

  const handleTextureChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      onTextureChange?.(e.target.value as TextureProviderId);
    },
    [onTextureChange]
  );

  // Check if 3D terrain is enabled to show texture selector
  const terrain3dLayer = layers.find((l) => l.id === 'terrain3d');
  const showTextureSelector = terrain3dLayer?.visible ?? false;

  if (!visible) {
    return null;
  }

  return (
    <div
      className="layer-panel"
      onPointerDown={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="layer-panel-header">Layers</div>
      {Object.entries(grouped).map(([category, items]) => (
        <div key={category} className="layer-category">
          <h4>{category}</h4>
          {items.map((layer) => (
            <div key={layer.id} className="layer-item-container">
              <label className="layer-item">
                <input
                  type="checkbox"
                  checked={layer.visible}
                  onChange={() => handleToggle(layer.id)}
                />
                <span className="layer-name">{layer.name}</span>
                {layer.count !== undefined && (
                  <span className="layer-count">({layer.count.toLocaleString()})</span>
                )}
              </label>
              {layer.supportsOpacity && layer.visible && (
                <div className="layer-opacity">
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={layer.opacity ?? 1}
                    onChange={(e) => handleOpacityChange(layer.id, e)}
                    className="opacity-slider"
                  />
                  <span className="opacity-value">{Math.round((layer.opacity ?? 1) * 100)}%</span>
                </div>
              )}
            </div>
          ))}
          {/* Texture selector - shown under Base Map when 3D terrain is enabled */}
          {category === 'Base Map' && showTextureSelector && (
            <div className="texture-selector">
              <label className="texture-label">
                <span>Ground Texture</span>
                <select value={terrainTexture} onChange={handleTextureChange}>
                  {Object.entries(TEXTURE_PROVIDERS).map(([id, provider]) => (
                    <option key={id} value={id}>
                      {provider.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
