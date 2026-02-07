/**
 * SchemaStage - Stage 4: Layer Schema
 *
 * Visualizes how data is organized into named layers within tiles:
 * - Each tile contains multiple named layers (building, road, water)
 * - TileJSON metadata describes available layers and their fields
 * - Same source-layer can be styled as multiple visual layers
 */

import { useState, type ReactNode } from 'react';
import type { StageProps, LayerSchema } from '../types';

/** Common OpenMapTiles layers */
const LAYERS: LayerSchema[] = [
  {
    id: 'building',
    geometryType: 'Polygon',
    fields: {
      height: 'Number',
      type: 'String',
      name: 'String',
    },
    description: 'Building footprints with height and classification',
  },
  {
    id: 'road',
    geometryType: 'LineString',
    fields: {
      class: 'String',
      name: 'String',
      oneway: 'Boolean',
    },
    description: 'Road network with classification and routing info',
  },
  {
    id: 'water',
    geometryType: 'Polygon',
    fields: {
      class: 'String',
    },
    description: 'Water bodies: lakes, rivers, oceans',
  },
  {
    id: 'landuse',
    geometryType: 'Polygon',
    fields: {
      class: 'String',
    },
    description: 'Land use zones: residential, industrial, park',
  },
  {
    id: 'poi',
    geometryType: 'Point',
    fields: {
      name: 'String',
      class: 'String',
      subclass: 'String',
    },
    description: 'Points of interest: restaurants, shops, attractions',
  },
];

/** Layer color mapping */
const LAYER_COLORS: Record<string, string> = {
  building: '#8b7355',
  road: '#e0e0e0',
  water: '#5b9bd5',
  landuse: '#4ade80',
  poi: '#f59e0b',
};

/** Geometry type icons */
const GEOMETRY_ICONS: Record<string, ReactNode> = {
  Point: (
    <svg viewBox="0 0 16 16" width="14" height="14">
      <circle cx="8" cy="8" r="4" fill="currentColor" />
    </svg>
  ),
  LineString: (
    <svg viewBox="0 0 16 16" width="14" height="14">
      <path d="M2 14L8 4L14 12" stroke="currentColor" strokeWidth="2" fill="none" />
    </svg>
  ),
  Polygon: (
    <svg viewBox="0 0 16 16" width="14" height="14">
      <polygon points="8,2 14,6 12,14 4,14 2,6" fill="currentColor" opacity="0.7" />
    </svg>
  ),
};

/** Sample feature data for inspection */
const SAMPLE_FEATURES: Record<string, Record<string, unknown>[]> = {
  building: [
    { id: 12345, height: 25, type: 'residential', name: null },
    { id: 12346, height: 45, type: 'commercial', name: 'Prime Tower' },
    { id: 12347, height: 18, type: 'industrial', name: null },
  ],
  road: [
    { id: 5001, class: 'highway', name: 'A1', oneway: true },
    { id: 5002, class: 'primary', name: 'Bahnhofstrasse', oneway: false },
    { id: 5003, class: 'residential', name: 'Musterweg', oneway: false },
  ],
  water: [
    { id: 8001, class: 'lake' },
    { id: 8002, class: 'river' },
  ],
  landuse: [
    { id: 9001, class: 'residential' },
    { id: 9002, class: 'park' },
    { id: 9003, class: 'industrial' },
  ],
  poi: [
    { id: 7001, name: 'Sprüngli', class: 'shop', subclass: 'confectionery' },
    { id: 7002, name: 'Kunsthaus', class: 'attraction', subclass: 'museum' },
  ],
};

/** Layer Stack Visualization */
function LayerStack({
  layers,
  selectedLayer,
  onSelectLayer,
}: {
  layers: LayerSchema[];
  selectedLayer: string;
  onSelectLayer: (id: string) => void;
}) {
  return (
    <div className="layer-stack-3d">
      {layers.map((layer, index) => (
        <div
          key={layer.id}
          className={`layer-card-3d ${selectedLayer === layer.id ? 'active' : ''}`}
          style={{
            transform: `translateZ(${(layers.length - index) * 20}px) translateY(${index * 8}px)`,
            zIndex: layers.length - index,
          }}
          onClick={() => onSelectLayer(layer.id)}
        >
          <div
            className="layer-color-bar"
            style={{ backgroundColor: LAYER_COLORS[layer.id] }}
          />
          <div className="layer-info">
            <div className="layer-name-row">
              <span className="layer-name">{layer.id}</span>
              <span className="layer-geometry">
                {GEOMETRY_ICONS[layer.geometryType]}
                {layer.geometryType}
              </span>
            </div>
            <div className="layer-fields">
              {Object.entries(layer.fields).map(([key, type]) => (
                <span key={key} className="field-tag">
                  {key}: <span className="field-type">{type}</span>
                </span>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/** Feature Inspector */
function FeatureInspector({ layerId }: { layerId: string }) {
  const features = SAMPLE_FEATURES[layerId] || [];
  const layer = LAYERS.find((l) => l.id === layerId);

  if (!layer) return null;

  return (
    <div className="feature-inspector">
      <h4>Sample Features ({features.length})</h4>
      <div className="feature-table">
        <div className="feature-header">
          <span className="feature-cell">id</span>
          {Object.keys(layer.fields).map((key) => (
            <span key={key} className="feature-cell">
              {key}
            </span>
          ))}
        </div>
        {features.map((feature, i) => (
          <div key={i} className="feature-row">
            <span className="feature-cell">{String(feature.id)}</span>
            {Object.keys(layer.fields).map((key) => (
              <span key={key} className="feature-cell">
                {feature[key] === null
                  ? 'null'
                  : feature[key] === true
                  ? '✓'
                  : feature[key] === false
                  ? '✗'
                  : String(feature[key])}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Source-Layer to Style-Layer Mapping */
function StyleLayerMapping({ sourceLayer }: { sourceLayer: string }) {
  const mappings: Record<string, string[]> = {
    building: ['building-fill', 'building-outline', 'building-3d'],
    road: ['highway', 'primary-road', 'street', 'path', 'road-labels'],
    water: ['water-fill', 'water-pattern'],
    landuse: ['park', 'residential-area', 'industrial-zone'],
    poi: ['poi-icons', 'poi-labels'],
  };

  const styleLayers = mappings[sourceLayer] || [];

  return (
    <div className="style-mapping">
      <h4>Style Layers using "{sourceLayer}"</h4>
      <div className="mapping-diagram">
        <div className="source-node">
          <span>source-layer:</span>
          <strong>{sourceLayer}</strong>
        </div>
        <div className="mapping-arrow">→</div>
        <div className="style-nodes">
          {styleLayers.map((layer) => (
            <div key={layer} className="style-node">
              {layer}
            </div>
          ))}
        </div>
      </div>
      <p className="mapping-hint">
        One source layer can be styled multiple ways with different filters and
        paint properties.
      </p>
    </div>
  );
}

/** Educational Introduction Component */
function SchemaIntro() {
  const [showDetails, setShowDetails] = useState<'layer' | 'schema' | 'mapping' | null>(null);

  return (
    <div className="schema-intro">
      {/* What is a Layer? */}
      <div className="concept-card">
        <div
          className="concept-header"
          onClick={() => setShowDetails(showDetails === 'layer' ? null : 'layer')}
        >
          <h4>📁 What is a Layer?</h4>
          <span className="expand-icon">{showDetails === 'layer' ? '−' : '+'}</span>
        </div>
        {showDetails === 'layer' && (
          <div className="concept-content">
            <p>
              A <strong>LAYER</strong> is a named collection of map features that share the same type.
              Think of it like folders on your computer:
            </p>
            <div className="folder-diagram">
              <div className="folder-item folder">📁 My Map Tile</div>
              <div className="folder-item sub">├── 📁 <span className="layer-name">building</span> (all buildings in this area)</div>
              <div className="folder-item sub">├── 📁 <span className="layer-name">road</span> (all roads in this area)</div>
              <div className="folder-item sub">├── 📁 <span className="layer-name">water</span> (rivers, lakes, pools)</div>
              <div className="folder-item sub">└── 📁 <span className="layer-name">poi</span> (points of interest)</div>
            </div>
            <p className="concept-insight">
              💡 Each "folder" (layer) contains features of the same category, making it easy to style them differently.
            </p>
          </div>
        )}
      </div>

      {/* What is a Schema? */}
      <div className="concept-card">
        <div
          className="concept-header"
          onClick={() => setShowDetails(showDetails === 'schema' ? null : 'schema')}
        >
          <h4>📋 What is a Schema?</h4>
          <span className="expand-icon">{showDetails === 'schema' ? '−' : '+'}</span>
        </div>
        {showDetails === 'schema' && (
          <div className="concept-content">
            <p>
              A <strong>SCHEMA</strong> is like a "contract" that describes what data is in each layer. It answers:
            </p>
            <ul className="schema-questions">
              <li><strong>What layers exist?</strong> ("building", "road", "water")</li>
              <li><strong>What geometry type?</strong> (Point/Line/Polygon)</li>
              <li><strong>What attributes can features have?</strong></li>
            </ul>
            <div className="schema-example">
              <div className="schema-box">
                <div className="schema-title">Layer: "building"</div>
                <div className="schema-field">Geometry: <span className="type">Polygon</span></div>
                <div className="schema-field">Attributes:</div>
                <div className="schema-attr">  • height: <span className="type">Number</span> (how tall, in meters)</div>
                <div className="schema-attr">  • type: <span className="type">String</span> ("residential", "commercial")</div>
                <div className="schema-attr">  • name: <span className="type">String</span> (optional building name)</div>
              </div>
            </div>
            <p className="concept-insight">
              💡 Without a schema, you'd have to guess what data exists! The schema tells the map renderer what to expect.
            </p>
          </div>
        )}
      </div>

      {/* Source-Layer vs Style-Layer */}
      <div className="concept-card">
        <div
          className="concept-header"
          onClick={() => setShowDetails(showDetails === 'mapping' ? null : 'mapping')}
        >
          <h4>🎨 Source-Layer vs Style-Layer</h4>
          <span className="expand-icon">{showDetails === 'mapping' ? '−' : '+'}</span>
        </div>
        {showDetails === 'mapping' && (
          <div className="concept-content">
            <p>This is a <strong>CRITICAL</strong> concept:</p>
            <div className="vs-diagram">
              <div className="vs-box source">
                <span className="vs-label">SOURCE-LAYER</span>
                <span className="vs-desc">the data (what's IN the tile)</span>
              </div>
              <span className="vs-ne">≠</span>
              <div className="vs-box style">
                <span className="vs-label">STYLE-LAYER</span>
                <span className="vs-desc">the visual (how it's DRAWN)</span>
              </div>
            </div>
            <p className="vs-key">
              ONE source-layer can create MANY style-layers:
            </p>
            <div className="multi-style-demo">
              <div className="source-single">Source: "road"</div>
              <div className="style-arrow">↓</div>
              <div className="style-multiple">
                <span className="style-variant highway">highway (orange, thick)</span>
                <span className="style-variant primary">primary (yellow, medium)</span>
                <span className="style-variant street">street (white, thin)</span>
                <span className="style-variant path">path (dashed, gray)</span>
                <span className="style-variant label">road-label (text on roads)</span>
              </div>
            </div>
            <p className="concept-insight">
              💡 Same data source, 5 different visual representations! This separation is what makes vector tiles so powerful.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export function SchemaStage({ isActive }: StageProps) {
  const [selectedLayer, setSelectedLayer] = useState('building');

  const currentLayer = LAYERS.find((l) => l.id === selectedLayer);

  if (!isActive) return null;

  return (
    <div className="schema-stage">
      {/* Educational Introduction */}
      <SchemaIntro />

      <div className="schema-content">
        {/* Layer Stack */}
        <div className="schema-stack-section">
          <h3>Tile Layers</h3>
          <LayerStack
            layers={LAYERS}
            selectedLayer={selectedLayer}
            onSelectLayer={setSelectedLayer}
          />
        </div>

        {/* Selected Layer Details */}
        <div className="schema-details-section">
          {currentLayer && (
            <>
              <div className="layer-detail-header">
                <div
                  className="layer-color-swatch"
                  style={{ backgroundColor: LAYER_COLORS[selectedLayer] }}
                />
                <div>
                  <h3>{currentLayer.id}</h3>
                  <p>{currentLayer.description}</p>
                </div>
              </div>

              <FeatureInspector layerId={selectedLayer} />

              <StyleLayerMapping sourceLayer={selectedLayer} />
            </>
          )}
        </div>
      </div>

      <style>{`
        .schema-stage {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 1.5rem;
          width: 100%;
          height: 100%;
          overflow-y: auto;
        }

        .schema-content {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 2rem;
          width: 100%;
          max-width: 900px;
        }

        .schema-stack-section h3,
        .schema-details-section h3 {
          margin: 0 0 1rem;
          font-size: 0.875rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: rgba(255, 255, 255, 0.5);
        }

        /* 3D Layer Stack */
        .layer-stack-3d {
          perspective: 800px;
          transform-style: preserve-3d;
          padding: 1rem;
        }

        .layer-card-3d {
          display: flex;
          gap: 0.75rem;
          padding: 0.75rem;
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.3s ease;
          margin-bottom: 0.5rem;
        }

        .layer-card-3d:hover {
          background: rgba(255, 255, 255, 0.06);
          transform: translateX(4px);
        }

        .layer-card-3d.active {
          background: rgba(136, 192, 255, 0.1);
          border-color: rgba(136, 192, 255, 0.3);
        }

        .layer-color-bar {
          width: 4px;
          border-radius: 2px;
          flex-shrink: 0;
        }

        .layer-info {
          flex: 1;
        }

        .layer-name-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 0.375rem;
        }

        .layer-name {
          font-weight: 600;
          color: #fff;
        }

        .layer-geometry {
          display: flex;
          align-items: center;
          gap: 0.375rem;
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.5);
        }

        .layer-fields {
          display: flex;
          flex-wrap: wrap;
          gap: 0.375rem;
        }

        .field-tag {
          font-size: 0.6875rem;
          padding: 0.125rem 0.375rem;
          background: rgba(255, 255, 255, 0.05);
          border-radius: 4px;
          color: rgba(255, 255, 255, 0.6);
        }

        .field-type {
          color: #c792ea;
        }

        /* Layer Details */
        .layer-detail-header {
          display: flex;
          gap: 1rem;
          margin-bottom: 1.5rem;
          padding: 1rem;
          background: rgba(255, 255, 255, 0.02);
          border-radius: 8px;
        }

        .layer-color-swatch {
          width: 48px;
          height: 48px;
          border-radius: 8px;
          flex-shrink: 0;
        }

        .layer-detail-header h3 {
          margin: 0;
          font-size: 1.25rem;
          color: #fff;
          text-transform: none;
          letter-spacing: normal;
        }

        .layer-detail-header p {
          margin: 0.25rem 0 0;
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.6);
        }

        /* Feature Inspector */
        .feature-inspector {
          margin-bottom: 1.5rem;
        }

        .feature-inspector h4 {
          margin: 0 0 0.75rem;
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: rgba(255, 255, 255, 0.5);
        }

        .feature-table {
          font-family: 'SF Mono', Monaco, monospace;
          font-size: 0.75rem;
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 8px;
          overflow: hidden;
        }

        .feature-header {
          display: flex;
          background: rgba(255, 255, 255, 0.05);
        }

        .feature-header .feature-cell {
          color: #88c0ff;
          font-weight: 600;
        }

        .feature-row {
          display: flex;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .feature-row:hover {
          background: rgba(255, 255, 255, 0.02);
        }

        .feature-cell {
          flex: 1;
          padding: 0.5rem 0.75rem;
          color: rgba(255, 255, 255, 0.8);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        /* Style Mapping */
        .style-mapping h4 {
          margin: 0 0 0.75rem;
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: rgba(255, 255, 255, 0.5);
        }

        .mapping-diagram {
          display: flex;
          align-items: center;
          gap: 1rem;
          padding: 1rem;
          background: rgba(255, 255, 255, 0.02);
          border-radius: 8px;
          margin-bottom: 0.75rem;
        }

        .source-node {
          padding: 0.5rem 0.75rem;
          background: rgba(136, 192, 255, 0.1);
          border: 1px solid rgba(136, 192, 255, 0.3);
          border-radius: 6px;
          font-size: 0.8125rem;
        }

        .source-node span {
          color: rgba(255, 255, 255, 0.5);
        }

        .source-node strong {
          color: #88c0ff;
          margin-left: 0.25rem;
        }

        .mapping-arrow {
          color: rgba(255, 255, 255, 0.3);
          font-size: 1.25rem;
        }

        .style-nodes {
          display: flex;
          flex-direction: column;
          gap: 0.375rem;
        }

        .style-node {
          padding: 0.375rem 0.625rem;
          background: rgba(255, 140, 0, 0.1);
          border: 1px solid rgba(255, 140, 0, 0.2);
          border-radius: 4px;
          font-size: 0.75rem;
          color: #ff8c00;
        }

        .mapping-hint {
          font-size: 0.8125rem;
          color: rgba(255, 255, 255, 0.5);
          margin: 0;
        }

        /* Schema Introduction */
        .schema-intro {
          width: 100%;
          max-width: 900px;
          margin-bottom: 2rem;
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .concept-card {
          background: rgba(255, 255, 255, 0.02);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 10px;
          overflow: hidden;
        }

        .concept-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.875rem 1rem;
          cursor: pointer;
          transition: background 0.2s;
        }

        .concept-header:hover {
          background: rgba(255, 255, 255, 0.03);
        }

        .concept-header h4 {
          margin: 0;
          font-size: 0.9375rem;
          font-weight: 600;
          color: #fff;
        }

        .expand-icon {
          color: rgba(255, 255, 255, 0.4);
          font-size: 1.25rem;
          font-weight: 300;
        }

        .concept-content {
          padding: 0 1rem 1rem;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .concept-content p {
          margin: 1rem 0 0.75rem;
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.8);
          line-height: 1.6;
        }

        .concept-insight {
          padding: 0.75rem;
          background: rgba(136, 192, 255, 0.08);
          border-radius: 6px;
          font-size: 0.8125rem !important;
          color: #88c0ff !important;
          margin-top: 1rem !important;
        }

        /* Folder Diagram */
        .folder-diagram {
          background: rgba(0, 0, 0, 0.2);
          border-radius: 8px;
          padding: 1rem;
          font-family: 'SF Mono', Monaco, Consolas, monospace;
          font-size: 0.8125rem;
        }

        .folder-item {
          padding: 0.25rem 0;
          color: rgba(255, 255, 255, 0.7);
        }

        .folder-item.folder {
          color: #f59e0b;
          font-weight: 600;
        }

        .folder-item.sub {
          padding-left: 1.5rem;
        }

        .folder-item .layer-name {
          color: #88c0ff;
          font-weight: 600;
        }

        /* Schema Questions */
        .schema-questions {
          margin: 0.5rem 0 1rem;
          padding-left: 1.25rem;
        }

        .schema-questions li {
          margin: 0.5rem 0;
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.7);
        }

        /* Schema Example Box */
        .schema-example {
          margin: 1rem 0;
        }

        .schema-box {
          background: rgba(0, 0, 0, 0.3);
          border: 1px solid rgba(136, 192, 255, 0.2);
          border-radius: 8px;
          padding: 1rem;
          font-family: 'SF Mono', Monaco, Consolas, monospace;
          font-size: 0.75rem;
        }

        .schema-title {
          color: #88c0ff;
          font-weight: 600;
          margin-bottom: 0.5rem;
        }

        .schema-field {
          color: rgba(255, 255, 255, 0.8);
          margin: 0.25rem 0;
        }

        .schema-attr {
          color: rgba(255, 255, 255, 0.6);
          margin: 0.125rem 0;
          padding-left: 0.5rem;
        }

        .schema-box .type {
          color: #c792ea;
        }

        /* VS Diagram */
        .vs-diagram {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 1rem;
          margin: 1rem 0;
        }

        .vs-box {
          padding: 0.75rem 1rem;
          border-radius: 8px;
          text-align: center;
        }

        .vs-box.source {
          background: rgba(136, 192, 255, 0.15);
          border: 1px solid rgba(136, 192, 255, 0.3);
        }

        .vs-box.style {
          background: rgba(255, 140, 0, 0.15);
          border: 1px solid rgba(255, 140, 0, 0.3);
        }

        .vs-label {
          display: block;
          font-weight: 700;
          font-size: 0.75rem;
          letter-spacing: 0.05em;
        }

        .vs-box.source .vs-label {
          color: #88c0ff;
        }

        .vs-box.style .vs-label {
          color: #ff8c00;
        }

        .vs-desc {
          display: block;
          font-size: 0.6875rem;
          color: rgba(255, 255, 255, 0.5);
          margin-top: 0.25rem;
        }

        .vs-ne {
          font-size: 1.5rem;
          color: rgba(255, 255, 255, 0.3);
        }

        .vs-key {
          text-align: center;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.9) !important;
        }

        /* Multi-style Demo */
        .multi-style-demo {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.5rem;
          padding: 1rem;
          background: rgba(0, 0, 0, 0.2);
          border-radius: 8px;
        }

        .source-single {
          padding: 0.5rem 1rem;
          background: rgba(136, 192, 255, 0.15);
          border: 1px solid rgba(136, 192, 255, 0.3);
          border-radius: 6px;
          color: #88c0ff;
          font-weight: 600;
          font-size: 0.875rem;
        }

        .style-arrow {
          color: rgba(255, 255, 255, 0.4);
          font-size: 1.25rem;
        }

        .style-multiple {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
          justify-content: center;
        }

        .style-variant {
          padding: 0.375rem 0.625rem;
          border-radius: 4px;
          font-size: 0.6875rem;
          font-weight: 500;
        }

        .style-variant.highway {
          background: rgba(255, 102, 0, 0.2);
          color: #ff6600;
        }

        .style-variant.primary {
          background: rgba(255, 204, 0, 0.2);
          color: #ffcc00;
        }

        .style-variant.street {
          background: rgba(255, 255, 255, 0.1);
          color: #fff;
        }

        .style-variant.path {
          background: rgba(128, 128, 128, 0.2);
          color: #999;
        }

        .style-variant.label {
          background: rgba(100, 200, 255, 0.2);
          color: #64c8ff;
        }

        @media (max-width: 768px) {
          .schema-content {
            grid-template-columns: 1fr;
          }

          .vs-diagram {
            flex-direction: column;
            gap: 0.5rem;
          }

          .vs-ne {
            transform: rotate(90deg);
          }
        }
      `}</style>
    </div>
  );
}
