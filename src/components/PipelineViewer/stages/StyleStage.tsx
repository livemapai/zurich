/**
 * StyleStage - Stage 5: MapLibre Style Specification
 *
 * Interactive style editor with live MapLibre map preview:
 * - Edit JSON style and see changes in real-time
 * - Drag-and-drop layer reordering
 * - Paint property controls
 * - Expression builder for data-driven styling
 */

import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import CodeMirror from '@uiw/react-codemirror';
import { json } from '@codemirror/lang-json';
import { EditorView } from '@codemirror/view';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { StageProps } from '../types';

/** Sample style layers for demonstration */
interface StyleLayerDef {
  id: string;
  type: string;
  color: string;
  visible: boolean;
}

const INITIAL_LAYERS: StyleLayerDef[] = [
  { id: 'water', type: 'fill', color: '#5b9bd5', visible: true },
  { id: 'landuse', type: 'fill', color: '#3d5a3d', visible: true },
  { id: 'building', type: 'fill', color: '#8b7355', visible: true },
  { id: 'road', type: 'line', color: '#e0e0e0', visible: true },
  { id: 'labels', type: 'symbol', color: '#ffffff', visible: true },
];

/** Sample style JSON */
const SAMPLE_STYLE = `{
  "id": "building-fill",
  "type": "fill",
  "source": "openmaptiles",
  "source-layer": "building",
  "paint": {
    "fill-color": [
      "interpolate",
      ["linear"],
      ["get", "height"],
      0, "#d4c4b0",
      50, "#8b7355"
    ],
    "fill-opacity": 0.9
  },
  "filter": ["==", ["geometry-type"], "Polygon"]
}`;

/** Custom CodeMirror theme */
const codeTheme = EditorView.theme(
  {
    '&': {
      backgroundColor: 'transparent',
      fontSize: '12px',
    },
    '.cm-content': {
      fontFamily: "'SF Mono', Monaco, Consolas, monospace",
      padding: '8px 0',
    },
    '.cm-gutters': {
      backgroundColor: 'rgba(0, 0, 0, 0.2)',
      borderRight: '1px solid rgba(255, 255, 255, 0.05)',
      color: 'rgba(255, 255, 255, 0.3)',
    },
    '.cm-activeLine': {
      backgroundColor: 'rgba(136, 192, 255, 0.05)',
    },
  },
  { dark: true }
);

/** Sortable Layer Item */
function SortableLayerItem({
  layer,
  onToggle,
  onColorChange,
}: {
  layer: StyleLayerDef;
  onToggle: (id: string) => void;
  onColorChange: (id: string, color: string) => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: layer.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`layer-item ${layer.visible ? '' : 'hidden'}`}
    >
      <span className="drag-handle" {...attributes} {...listeners}>
        ⋮⋮
      </span>
      <input
        type="color"
        value={layer.color}
        onChange={(e) => onColorChange(layer.id, e.target.value)}
        className="color-picker"
      />
      <span className="layer-name">{layer.id}</span>
      <span className="layer-type">{layer.type}</span>
      <button
        className={`visibility-toggle ${layer.visible ? 'visible' : ''}`}
        onClick={() => onToggle(layer.id)}
        title={layer.visible ? 'Hide layer' : 'Show layer'}
      >
        {layer.visible ? '👁' : '👁‍🗨'}
      </button>
    </div>
  );
}

/** Layers List with Drag & Drop */
function LayersList({
  layers,
  onReorder,
  onToggle,
  onColorChange,
}: {
  layers: StyleLayerDef[];
  onReorder: (layers: StyleLayerDef[]) => void;
  onToggle: (id: string) => void;
  onColorChange: (id: string, color: string) => void;
}) {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (active.id !== over?.id) {
      const oldIndex = layers.findIndex((l) => l.id === active.id);
      const newIndex = layers.findIndex((l) => l.id === over?.id);
      onReorder(arrayMove(layers, oldIndex, newIndex));
    }
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={layers.map((l) => l.id)}
        strategy={verticalListSortingStrategy}
      >
        <div className="layers-list">
          {layers.map((layer) => (
            <SortableLayerItem
              key={layer.id}
              layer={layer}
              onToggle={onToggle}
              onColorChange={onColorChange}
            />
          ))}
        </div>
      </SortableContext>
    </DndContext>
  );
}

/** Expression Presets */
const EXPRESSION_PRESETS = [
  {
    name: 'Height-based color',
    code: '["interpolate", ["linear"], ["get", "height"], 0, "#d4c4b0", 50, "#8b7355"]',
  },
  {
    name: 'Road class match',
    code: '["match", ["get", "class"], "highway", "#ff6600", "primary", "#ffcc00", "#ffffff"]',
  },
  {
    name: 'Zoom-based width',
    code: '["interpolate", ["linear"], ["zoom"], 10, 1, 16, 4]',
  },
];

export function StyleStage({ isActive }: StageProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [layers, setLayers] = useState(INITIAL_LAYERS);
  const [styleCode, setStyleCode] = useState(SAMPLE_STYLE);
  const [parseError, setParseError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'layers' | 'code' | 'expressions'>('layers');

  // Initialize map
  useEffect(() => {
    if (!isActive || !mapContainer.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [8.54, 47.37], // Zurich
      zoom: 14,
      pitch: 45,
    });

    map.addControl(new maplibregl.NavigationControl(), 'top-right');

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [isActive]);

  /**
   * Helper: Find actual MapLibre layer IDs by category
   * The CARTO Dark Matter style uses different layer naming than our simplified categories.
   * This function searches for layers that match our category keywords.
   */
  const findMapLayerIds = useCallback((category: string): string[] => {
    const map = mapRef.current;
    if (!map) return [];

    const style = map.getStyle();
    if (!style?.layers) return [];

    // Map our simplified categories to CARTO Dark Matter layer patterns
    const patterns: Record<string, string[]> = {
      'water': ['water'],
      'landuse': ['landuse', 'park', 'landcover'],
      'building': ['building'],
      'road': ['road', 'tunnel', 'bridge', 'highway', 'path', 'street'],
      'labels': ['label', 'place', 'poi', 'name'],
    };

    const searchTerms = patterns[category] || [category];
    const matchingIds: string[] = [];

    for (const layer of style.layers) {
      for (const term of searchTerms) {
        if (layer.id.toLowerCase().includes(term.toLowerCase())) {
          matchingIds.push(layer.id);
          break;
        }
      }
    }
    return matchingIds;
  }, []);

  // Handle layer reorder - FIXED: now calls map.moveLayer()
  const handleReorder = useCallback((newLayers: StyleLayerDef[]) => {
    setLayers(newLayers);

    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    // Reorder layers in MapLibre to match new order
    // Layers are rendered bottom-to-top, so we need to move category layers
    // relative to each other. We use the first layer of each category as anchor.
    for (let i = newLayers.length - 1; i > 0; i--) {
      const currentLayer = newLayers[i];
      const prevLayer = newLayers[i - 1];
      if (!currentLayer || !prevLayer) continue;

      const currentLayerIds = findMapLayerIds(currentLayer.id);
      const prevLayerIds = findMapLayerIds(prevLayer.id);

      const firstCurrentId = currentLayerIds[0];
      const firstPrevId = prevLayerIds[0];

      if (firstCurrentId && firstPrevId) {
        // Move the first layer of current category before the first layer of previous
        try {
          map.moveLayer(firstCurrentId, firstPrevId);
        } catch {
          // Layer might not exist in this style
        }
      }
    }
  }, [findMapLayerIds]);

  // Handle visibility toggle - FIXED: now calls map.setLayoutProperty()
  const handleToggle = useCallback((id: string) => {
    setLayers((prev) => {
      const newLayers = prev.map((l) =>
        l.id === id ? { ...l, visible: !l.visible } : l
      );

      const map = mapRef.current;
      if (map && map.isStyleLoaded()) {
        const layer = newLayers.find((l) => l.id === id);
        const layerIds = findMapLayerIds(id);

        if (layer) {
          const visibility = layer.visible ? 'visible' : 'none';
          for (const layerId of layerIds) {
            try {
              map.setLayoutProperty(layerId, 'visibility', visibility);
            } catch {
              // Layer might not exist
            }
          }
        }
      }

      return newLayers;
    });
  }, [findMapLayerIds]);

  // Handle color change - FIXED: now calls map.setPaintProperty()
  const handleColorChange = useCallback((id: string, color: string) => {
    setLayers((prev) =>
      prev.map((l) => (l.id === id ? { ...l, color } : l))
    );

    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const layerIds = findMapLayerIds(id);
    for (const layerId of layerIds) {
      try {
        const layer = map.getLayer(layerId);
        if (layer) {
          // Apply color based on layer type
          const layerType = layer.type;
          if (layerType === 'fill') {
            map.setPaintProperty(layerId, 'fill-color', color);
          } else if (layerType === 'line') {
            map.setPaintProperty(layerId, 'line-color', color);
          } else if (layerType === 'circle') {
            map.setPaintProperty(layerId, 'circle-color', color);
          } else if (layerType === 'symbol') {
            map.setPaintProperty(layerId, 'text-color', color);
          } else if (layerType === 'fill-extrusion') {
            map.setPaintProperty(layerId, 'fill-extrusion-color', color);
          }
        }
      } catch {
        // Property might not be supported
      }
    }
  }, [findMapLayerIds]);

  // Handle code change
  const handleCodeChange = useCallback((value: string) => {
    setStyleCode(value);
    try {
      JSON.parse(value);
      setParseError(null);
    } catch (e) {
      setParseError((e as Error).message);
    }
  }, []);

  // Apply expression preset
  const applyPreset = useCallback((preset: typeof EXPRESSION_PRESETS[0]) => {
    setStyleCode(preset.code);
    setParseError(null);
  }, []);

  // Extensions for CodeMirror
  const extensions = useMemo(() => [json(), codeTheme, EditorView.lineWrapping], []);

  if (!isActive) return null;

  return (
    <div className="style-stage">
      <div className="style-content">
        {/* Left Panel: Controls */}
        <div className="style-controls">
          {/* Tabs */}
          <div className="style-tabs">
            <button
              className={`style-tab ${activeTab === 'layers' ? 'active' : ''}`}
              onClick={() => setActiveTab('layers')}
            >
              Layers
            </button>
            <button
              className={`style-tab ${activeTab === 'code' ? 'active' : ''}`}
              onClick={() => setActiveTab('code')}
            >
              Style JSON
            </button>
            <button
              className={`style-tab ${activeTab === 'expressions' ? 'active' : ''}`}
              onClick={() => setActiveTab('expressions')}
            >
              Expressions
            </button>
          </div>

          {/* Tab Content */}
          <div className="style-tab-content">
            {activeTab === 'layers' && (
              <div className="layers-panel">
                <p className="panel-hint">
                  Drag to reorder layers. Top layers render on top.
                </p>
                <LayersList
                  layers={layers}
                  onReorder={handleReorder}
                  onToggle={handleToggle}
                  onColorChange={handleColorChange}
                />
              </div>
            )}

            {activeTab === 'code' && (
              <div className="code-editor-panel">
                <p className="panel-hint">Edit layer style JSON:</p>
                <div className="code-editor-wrapper">
                  <CodeMirror
                    value={styleCode}
                    height="200px"
                    extensions={extensions}
                    onChange={handleCodeChange}
                    basicSetup={{
                      lineNumbers: true,
                      foldGutter: false,
                      bracketMatching: true,
                    }}
                  />
                </div>
                {parseError && (
                  <div className="parse-error">
                    <span>⚠</span> {parseError}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'expressions' && (
              <div className="expressions-panel">
                <p className="panel-hint">
                  Click a preset to see the expression:
                </p>
                <div className="expression-presets">
                  {EXPRESSION_PRESETS.map((preset) => (
                    <button
                      key={preset.name}
                      className="preset-btn"
                      onClick={() => applyPreset(preset)}
                    >
                      {preset.name}
                    </button>
                  ))}
                </div>
                <div className="expression-preview">
                  <code>{styleCode}</code>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Panel: Map */}
        <div className="style-map-container">
          <div ref={mapContainer} className="style-map" />
          <div className="map-overlay">
            <span className="map-hint">
              Live MapLibre GL preview • Zurich, Switzerland
            </span>
          </div>
        </div>
      </div>

      <style>{`
        .style-stage {
          display: flex;
          width: 100%;
          height: 100%;
        }

        .style-content {
          display: flex;
          width: 100%;
          height: 100%;
        }

        /* Controls Panel */
        .style-controls {
          width: 320px;
          min-width: 320px;
          display: flex;
          flex-direction: column;
          border-right: 1px solid rgba(255, 255, 255, 0.08);
          background: rgba(20, 20, 35, 0.5);
        }

        .style-tabs {
          display: flex;
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }

        .style-tab {
          flex: 1;
          padding: 0.75rem;
          background: transparent;
          border: none;
          color: rgba(255, 255, 255, 0.6);
          font-size: 0.8125rem;
          cursor: pointer;
          transition: all 0.2s;
        }

        .style-tab:hover {
          background: rgba(255, 255, 255, 0.03);
          color: rgba(255, 255, 255, 0.8);
        }

        .style-tab.active {
          background: rgba(136, 192, 255, 0.1);
          color: #88c0ff;
          border-bottom: 2px solid #88c0ff;
        }

        .style-tab-content {
          flex: 1;
          overflow-y: auto;
          padding: 1rem;
        }

        .panel-hint {
          margin: 0 0 0.75rem;
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.5);
        }

        /* Layers List */
        .layers-list {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .layer-item {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.625rem 0.75rem;
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 8px;
          transition: all 0.2s;
        }

        .layer-item:hover {
          background: rgba(255, 255, 255, 0.05);
        }

        .layer-item.hidden {
          opacity: 0.5;
        }

        .drag-handle {
          color: rgba(255, 255, 255, 0.3);
          cursor: grab;
          font-size: 0.875rem;
          letter-spacing: -2px;
        }

        .drag-handle:active {
          cursor: grabbing;
        }

        .color-picker {
          width: 24px;
          height: 24px;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          background: transparent;
        }

        .color-picker::-webkit-color-swatch-wrapper {
          padding: 0;
        }

        .color-picker::-webkit-color-swatch {
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 4px;
        }

        .layer-name {
          flex: 1;
          font-weight: 500;
          color: #fff;
          font-size: 0.875rem;
        }

        .layer-type {
          font-size: 0.6875rem;
          padding: 0.125rem 0.375rem;
          background: rgba(136, 192, 255, 0.1);
          color: #88c0ff;
          border-radius: 4px;
        }

        .visibility-toggle {
          background: transparent;
          border: none;
          cursor: pointer;
          font-size: 0.875rem;
          opacity: 0.5;
          transition: opacity 0.2s;
        }

        .visibility-toggle.visible {
          opacity: 1;
        }

        /* Code Editor */
        .code-editor-wrapper {
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 8px;
          overflow: hidden;
        }

        .parse-error {
          margin-top: 0.5rem;
          padding: 0.5rem 0.75rem;
          background: rgba(239, 68, 68, 0.1);
          border: 1px solid rgba(239, 68, 68, 0.2);
          border-radius: 6px;
          font-size: 0.75rem;
          color: #fca5a5;
        }

        /* Expressions Panel */
        .expression-presets {
          display: flex;
          flex-direction: column;
          gap: 0.375rem;
          margin-bottom: 1rem;
        }

        .preset-btn {
          padding: 0.5rem 0.75rem;
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 6px;
          color: rgba(255, 255, 255, 0.8);
          font-size: 0.8125rem;
          text-align: left;
          cursor: pointer;
          transition: all 0.2s;
        }

        .preset-btn:hover {
          background: rgba(136, 192, 255, 0.1);
          border-color: rgba(136, 192, 255, 0.3);
        }

        .expression-preview {
          padding: 0.75rem;
          background: rgba(0, 0, 0, 0.3);
          border-radius: 6px;
          overflow-x: auto;
        }

        .expression-preview code {
          font-size: 0.75rem;
          color: #c3e88d;
          white-space: pre-wrap;
          word-break: break-all;
        }

        /* Map Container */
        .style-map-container {
          flex: 1;
          position: relative;
        }

        .style-map {
          width: 100%;
          height: 100%;
        }

        .map-overlay {
          position: absolute;
          bottom: 0.75rem;
          left: 0.75rem;
          padding: 0.375rem 0.75rem;
          background: rgba(26, 26, 46, 0.9);
          border-radius: 4px;
          backdrop-filter: blur(8px);
        }

        .map-hint {
          font-size: 0.6875rem;
          color: rgba(255, 255, 255, 0.5);
        }

        @media (max-width: 768px) {
          .style-content {
            flex-direction: column;
          }

          .style-controls {
            width: 100%;
            min-width: 100%;
            max-height: 50%;
          }

          .style-map-container {
            min-height: 300px;
          }
        }
      `}</style>
    </div>
  );
}
