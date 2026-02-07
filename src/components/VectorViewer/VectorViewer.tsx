/**
 * VectorViewer - MapLibre Vector Tile Viewer
 *
 * Displays Zurich vector tiles from PMTiles with layer controls,
 * feature inspection capabilities, and gradient shadow rendering.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import { Protocol } from 'pmtiles';
import 'maplibre-gl/dist/maplibre-gl.css';
import type {
  VectorViewerProps,
  LayerVisibility,
  TileVariant,
  StylePreset,
  ClickedFeature,
} from './types';
import { useShadowLayer } from './useShadowLayer';
import { TimeControl } from './TimeControl';

// Zurich center coordinates
const ZURICH_CENTER: [number, number] = [8.5417, 47.3769];
const DEFAULT_ZOOM = 15;

// Available tile variants
const TILE_VARIANTS: TileVariant[] = [
  {
    id: 'clean',
    name: 'Clean',
    description: 'Precise architectural rendering',
    pmtilesUrl: '/tiles/vector/zurich-vector.pmtiles',
  },
  {
    id: 'wobble',
    name: 'Hand-drawn',
    description: 'Organic edges with Perlin noise',
    pmtilesUrl: '/tiles/vector/zurich-wobble.pmtiles',
  },
  {
    id: 'tilt',
    name: 'Isometric',
    description: 'SimCity-style oblique projection',
    pmtilesUrl: '/tiles/vector/zurich-tilt.pmtiles',
  },
  {
    id: 'wobble-tilt',
    name: 'Iso + Hand-drawn',
    description: 'Combined isometric and hand-drawn style',
    pmtilesUrl: '/tiles/vector/zurich-wobble-tilt.pmtiles',
  },
];

// Available pencil style presets
const STYLE_PRESETS: StylePreset[] = [
  {
    id: 'sketchy',
    name: 'Sketchy',
    description: 'Loose pencil textures',
    icon: '✏️',
    styleUrl: '/tiles/vector/zurich-style-sketchy.json',
  },
  {
    id: 'technical',
    name: 'Technical',
    description: 'Clean architectural lines',
    icon: '📐',
    styleUrl: '/tiles/vector/zurich-style-technical.json',
  },
  {
    id: 'artistic',
    name: 'Artistic',
    description: 'Bold expressive strokes',
    icon: '🎨',
    styleUrl: '/tiles/vector/zurich-style-artistic.json',
  },
  {
    id: 'minimal',
    name: 'Minimal',
    description: 'Subtle clean lines',
    icon: '〰️',
    styleUrl: '/tiles/vector/zurich-style-minimal.json',
  },
  {
    id: 'zigzag',
    name: 'Zigzag',
    description: 'Playful wavy patterns',
    icon: '〰',
    styleUrl: '/tiles/vector/zurich-style-zigzag.json',
  },
];

// Layer groups for UI
const LAYER_GROUPS = [
  { id: 'water', label: 'Water', icon: '💧' },
  { id: 'buildings', label: 'Buildings', icon: '🏢' },
  { id: 'building_shadows', label: 'Shadows', icon: '🌑' },
  { id: 'roofs', label: 'Roofs', icon: '🏠' },
  { id: 'transportation', label: 'Streets', icon: '🛣️' },
  { id: 'railway', label: 'Tram', icon: '🚋' },
  { id: 'trees', label: 'Trees', icon: '🌳' },
  { id: 'poi', label: 'POI', icon: '📍' },
  { id: 'labels', label: 'Labels', icon: '🏷️' },
] as const;

// Map UI toggle IDs to actual MapLibre layer IDs in zurich-style.json
// These must match exactly or setLayoutProperty('visibility') will silently fail
const LAYER_ID_MAP: Record<string, string[]> = {
  water: ['water-fill', 'water-pattern', 'water-edge-1', 'water-edge-2'],
  buildings: [
    'building-fill',
    'building-texture',
    'building-outline-1',
    'building-outline-2',
    'building-outline-3',
  ],
  building_shadows: [
    'building-shadow-1',
    'building-shadow-2',
    'building-shadow-3',
    'building-shadow-hatching',
  ],
  roofs: ['roof-fill', 'roof-pattern', 'roof-outline-1', 'roof-outline-2'],
  transportation: [
    'street-casing',
    'street-fill',
    'street-edge-left',
    'street-edge-right',
    'street-footway',
  ],
  railway: [
    'railway-track-bed',
    'railway-rail-left',
    'railway-rail-right',
    'railway-ties',
  ],
  trees: ['tree-shadow', 'tree-fill', 'tree-outline-1', 'tree-outline-2'],
  poi: ['poi-amenity', 'poi-infrastructure'],
  labels: ['street-label', 'fountain-label'],
};

// Initialize PMTiles protocol (singleton)
let protocolInitialized = false;
function initializePMTilesProtocol() {
  if (protocolInitialized) return;
  const protocol = new Protocol();
  maplibregl.addProtocol('pmtiles', protocol.tile);
  protocolInitialized = true;
}

export function VectorViewer({ className = '' }: VectorViewerProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedVariant, setSelectedVariant] = useState<TileVariant['id']>('clean');
  const [selectedPreset, setSelectedPreset] = useState<StylePreset['id']>('sketchy');
  const [layerVisibility, setLayerVisibility] = useState<LayerVisibility>({
    water: true,
    buildings: true,
    building_shadows: true,
    roofs: true,
    transportation: true,
    railway: true,
    trees: true,
    poi: true,
    labels: true,
  });
  const [clickedFeature, setClickedFeature] = useState<ClickedFeature | null>(null);
  const [styleLoaded, setStyleLoaded] = useState(false);

  // Gradient shadow state
  const [gradientShadowsEnabled, setGradientShadowsEnabled] = useState(false);
  const [timeOfDay, setTimeOfDay] = useState(14 * 60); // Default: 2:00 PM

  // Shadow layer hook
  const {
    initializeOverlay,
    updateShadows,
    cleanup: cleanupShadows,
    shadowCount,
    sunPosition,
  } = useShadowLayer({
    enabled: gradientShadowsEnabled,
    timeOfDay,
    shadowColor: [30, 30, 40],
    maxOpacity: 0.5,
  });

  // Check if PMTiles file exists
  const checkTilesExist = useCallback(async (variant: TileVariant): Promise<boolean> => {
    try {
      const response = await fetch(variant.pmtilesUrl, { method: 'HEAD' });
      return response.ok;
    } catch {
      return false;
    }
  }, []);

  // Initialize map
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    initializePMTilesProtocol();

    // Check if tiles exist first
    const variant = TILE_VARIANTS.find((v) => v.id === selectedVariant)!;
    checkTilesExist(variant).then((exists) => {
      if (!exists) {
        setError(`Vector tiles not found. Run the pipeline first:\n\npython -m scripts.vector_tiles.pipeline all`);
        setIsLoading(false);
        return;
      }

      // Load style.json
      fetch('/tiles/vector/zurich-style.json')
        .then((response) => {
          if (!response.ok) throw new Error('Style not found');
          return response.json();
        })
        .then((style) => {
          // Update the source URL to use the selected variant
          if (style.sources?.zurich) {
            style.sources.zurich.url = `pmtiles://${variant.pmtilesUrl}`;
          }

          const map = new maplibregl.Map({
            container: mapContainerRef.current!,
            style,
            center: ZURICH_CENTER,
            zoom: DEFAULT_ZOOM,
            maxZoom: 18,
            minZoom: 10,
            hash: true,
          });

          map.addControl(new maplibregl.NavigationControl(), 'bottom-right');
          map.addControl(new maplibregl.ScaleControl({ maxWidth: 100 }), 'bottom-left');

          map.on('load', () => {
            setStyleLoaded(true);
            setIsLoading(false);

            // Initialize deck.gl shadow overlay
            initializeOverlay(map);
          });

          // Feature click handler
          map.on('click', (e) => {
            const features = map.queryRenderedFeatures(e.point);
            const feature = features[0];
            if (feature) {
              setClickedFeature({
                layer: feature.sourceLayer || feature.source?.toString() || 'unknown',
                properties: feature.properties as Record<string, unknown>,
                coordinates: [e.lngLat.lng, e.lngLat.lat],
              });
            } else {
              setClickedFeature(null);
            }
          });

          // Cursor change for interactive features
          map.on('mouseenter', 'building-fill', () => {
            map.getCanvas().style.cursor = 'pointer';
          });
          map.on('mouseleave', 'building-fill', () => {
            map.getCanvas().style.cursor = '';
          });

          mapRef.current = map;
        })
        .catch((err) => {
          setError(`Failed to load style: ${err.message}\n\nRun the pipeline first:\npython -m scripts.vector_tiles.pipeline style`);
          setIsLoading(false);
        });
    });

    return () => {
      cleanupShadows();
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Toggle layer visibility
  const toggleLayer = useCallback(
    (layerId: keyof LayerVisibility) => {
      const map = mapRef.current;
      if (!map || !styleLoaded) return;

      const newVisibility = !layerVisibility[layerId];
      setLayerVisibility((prev) => ({ ...prev, [layerId]: newVisibility }));

      const mapLayerIds = LAYER_ID_MAP[layerId] || [];
      for (const id of mapLayerIds) {
        try {
          if (map.getLayer(id)) {
            map.setLayoutProperty(id, 'visibility', newVisibility ? 'visible' : 'none');
          }
        } catch {
          // Layer might not exist in style
        }
      }
    },
    [layerVisibility, styleLoaded]
  );

  // Toggle gradient shadows (hides MapLibre shadows when enabled)
  const toggleGradientShadows = useCallback(
    (enabled: boolean) => {
      const map = mapRef.current;
      setGradientShadowsEnabled(enabled);

      if (!map || !styleLoaded) return;

      // Hide/show MapLibre shadow layers based on gradient shadow state
      const shadowLayers = LAYER_ID_MAP['building_shadows'] || [];
      for (const id of shadowLayers) {
        try {
          if (map.getLayer(id)) {
            // When gradient shadows are enabled, hide MapLibre shadows
            map.setLayoutProperty(id, 'visibility', enabled ? 'none' : 'visible');
          }
        } catch {
          // Layer might not exist
        }
      }

      // Update shadow data when enabling
      if (enabled) {
        // Small delay to ensure MapLibre has rendered before we query features
        setTimeout(() => updateShadows(), 100);
      }
    },
    [styleLoaded, updateShadows]
  );

  // Switch tile variant
  const switchVariant = useCallback(
    async (variantId: TileVariant['id']) => {
      const map = mapRef.current;
      if (!map || variantId === selectedVariant) return;

      const variant = TILE_VARIANTS.find((v) => v.id === variantId)!;
      const exists = await checkTilesExist(variant);

      if (!exists) {
        // Build the appropriate pipeline command
        let pipelineFlags = '';
        if (variantId === 'wobble') pipelineFlags = ' --wobble';
        else if (variantId === 'tilt') pipelineFlags = ' --tilt';
        else if (variantId === 'wobble-tilt') pipelineFlags = ' --wobble --tilt';

        setError(
          `${variant.name} tiles not found.\n\nGenerate with:\npython -m scripts.vector_tiles.pipeline all${pipelineFlags}`
        );
        return;
      }

      setSelectedVariant(variantId);

      // Update the source URL
      const source = map.getSource('zurich') as maplibregl.VectorTileSource;
      if (source) {
        // MapLibre doesn't support changing source URL directly,
        // so we need to reload the style
        const style = map.getStyle();
        if (style?.sources?.zurich) {
          (style.sources.zurich as { url: string }).url = `pmtiles://${variant.pmtilesUrl}`;
          map.setStyle(style);
        }
      }
    },
    [selectedVariant, checkTilesExist]
  );

  // Switch pencil style preset
  const switchPreset = useCallback(
    async (presetId: StylePreset['id']) => {
      const map = mapRef.current;
      if (!map || presetId === selectedPreset) return;

      const preset = STYLE_PRESETS.find((p) => p.id === presetId)!;
      const variant = TILE_VARIANTS.find((v) => v.id === selectedVariant)!;

      try {
        // Fetch the new style
        const response = await fetch(preset.styleUrl);
        if (!response.ok) {
          setError(
            `Style preset "${preset.name}" not found.\n\nGenerate with:\npython -m scripts.vector_tiles.pipeline style --all-presets`
          );
          return;
        }

        const style = await response.json();

        // Update the source URL to use current tile variant
        if (style.sources?.zurich) {
          style.sources.zurich.url = `pmtiles://${variant.pmtilesUrl}`;
        }

        // Save current view state
        const center = map.getCenter();
        const zoom = map.getZoom();
        const bearing = map.getBearing();
        const pitch = map.getPitch();

        // Apply the new style
        map.setStyle(style);

        // Restore view state after style loads
        map.once('style.load', () => {
          map.setCenter(center);
          map.setZoom(zoom);
          map.setBearing(bearing);
          map.setPitch(pitch);

          // Restore layer visibility
          for (const [groupId, visible] of Object.entries(layerVisibility)) {
            const mapLayerIds = LAYER_ID_MAP[groupId] || [];
            for (const id of mapLayerIds) {
              try {
                if (map.getLayer(id)) {
                  map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
                }
              } catch {
                // Layer might not exist in style
              }
            }
          }
        });

        setSelectedPreset(presetId);
      } catch (err) {
        console.error('Failed to load style preset:', err);
      }
    },
    [selectedPreset, selectedVariant, layerVisibility]
  );

  // Error state
  if (error) {
    return (
      <div className={`vector-page ${className}`}>
        <div className="vector-error">
          <h2>Vector Tiles Not Ready</h2>
          <pre>{error}</pre>
        </div>
      </div>
    );
  }

  return (
    <div className={`vector-page ${className}`}>
      {/* Control Panel */}
      <div className="vector-panel">
        <h2>Vector Tiles</h2>

        {/* Variant selector */}
        <div className="vector-section">
          <h3>Tile Variant</h3>
          <div className="variant-buttons">
            {TILE_VARIANTS.map((variant) => (
              <button
                key={variant.id}
                className={`variant-button ${selectedVariant === variant.id ? 'active' : ''}`}
                onClick={() => switchVariant(variant.id)}
                title={variant.description}
              >
                {variant.name}
              </button>
            ))}
          </div>
        </div>

        {/* Pencil preset selector */}
        <div className="vector-section">
          <h3>Pencil Style</h3>
          <div className="preset-buttons">
            {STYLE_PRESETS.map((preset) => (
              <button
                key={preset.id}
                className={`preset-button ${selectedPreset === preset.id ? 'active' : ''}`}
                onClick={() => switchPreset(preset.id)}
                title={preset.description}
              >
                <span className="preset-icon">{preset.icon}</span>
                <span className="preset-name">{preset.name}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Layer toggles */}
        <div className="vector-section">
          <h3>Layers</h3>
          <div className="layer-toggles">
            {LAYER_GROUPS.map((group) => (
              <label key={group.id} className="layer-toggle">
                <input
                  type="checkbox"
                  checked={layerVisibility[group.id as keyof LayerVisibility]}
                  onChange={() => toggleLayer(group.id as keyof LayerVisibility)}
                  disabled={!styleLoaded || (group.id === 'building_shadows' && gradientShadowsEnabled)}
                />
                <span className="layer-icon">{group.icon}</span>
                <span className="layer-label">{group.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Gradient Shadows Control */}
        <div className="vector-section">
          <h3>🌄 Dynamic Shadows</h3>
          <label className="layer-toggle gradient-toggle">
            <input
              type="checkbox"
              checked={gradientShadowsEnabled}
              onChange={(e) => toggleGradientShadows(e.target.checked)}
              disabled={!styleLoaded}
            />
            <span className="layer-icon">✨</span>
            <span className="layer-label">Gradient Shadows</span>
          </label>
          {gradientShadowsEnabled && (
            <>
              <TimeControl
                timeOfDay={timeOfDay}
                onTimeChange={setTimeOfDay}
                sunPosition={sunPosition}
                disabled={!styleLoaded}
              />
              <div className="shadow-stats">
                <small>{shadowCount} shadows rendered</small>
              </div>
            </>
          )}
        </div>

        {/* Feature inspector */}
        {clickedFeature && (
          <div className="vector-section">
            <h3>Feature Info</h3>
            <div className="feature-inspector">
              <div className="feature-layer">
                Layer: <code>{clickedFeature.layer}</code>
              </div>
              <div className="feature-props">
                {Object.entries(clickedFeature.properties)
                  .filter(([_, v]) => v !== null && v !== undefined)
                  .slice(0, 10)
                  .map(([key, value]) => (
                    <div key={key} className="feature-prop">
                      <span className="prop-key">{key}:</span>
                      <span className="prop-value">
                        {typeof value === 'number' ? value.toFixed(2) : String(value)}
                      </span>
                    </div>
                  ))}
              </div>
              <button className="clear-selection" onClick={() => setClickedFeature(null)}>
                Clear
              </button>
            </div>
          </div>
        )}

        {/* Pipeline info */}
        <div className="vector-section vector-info">
          <h3>Pipeline</h3>
          <div className="pipeline-commands">
            <code>python -m scripts.vector_tiles.pipeline all</code>
            <code>python -m scripts.vector_tiles.pipeline all --wobble</code>
            <code>python -m scripts.vector_tiles.pipeline all --tilt</code>
          </div>
        </div>
      </div>

      {/* Map container */}
      <div className="vector-map-container">
        {isLoading && (
          <div className="vector-loading">
            <div className="loading-spinner" />
            <span>Loading vector tiles...</span>
          </div>
        )}
        <div ref={mapContainerRef} className="vector-map" />
      </div>
    </div>
  );
}

export default VectorViewer;
