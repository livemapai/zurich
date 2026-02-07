/**
 * InfoPanel - Explanatory Text Panel
 *
 * Displays stage title, description, key insight, code examples,
 * and links to hands-on workshop exercises.
 */

import { CodePanel } from './CodePanel';
import type { StageId } from '../types';

/** Workshop tasks mapped to each pipeline stage */
const STAGE_WORKSHOPS: Record<StageId, { tasks: Array<{ id: string; title: string; path: string }>; description: string } | null> = {
  'data-sources': {
    description: 'Learn about raster vs vector tiles',
    tasks: [
      { id: '1', title: 'Raster Tiles', path: '/rendering-workshop/tasks/01-raster-tiles.html' },
      { id: '2', title: 'Vector Tiles', path: '/rendering-workshop/tasks/02-vector-tiles.html' },
    ],
  },
  'tiling': {
    description: 'Generate tiles from OSM data',
    tasks: [
      { id: '5', title: 'Planetiler', path: '/rendering-workshop/tasks/05-planetiler/instructions.html' },
      { id: '4', title: 'PMTiles', path: '/rendering-workshop/tasks/04-pmtiles.html' },
    ],
  },
  'encoding': {
    description: 'Inspect the binary MVT format',
    tasks: [
      { id: '6', title: 'MVT Inspection', path: '/rendering-workshop/tasks/06-mvt-inspect.html' },
    ],
  },
  'schema': {
    description: 'Explore tile metadata and layer schemas',
    tasks: [
      { id: '7', title: 'TileJSON Explorer', path: '/rendering-workshop/tasks/07-tilejson.html' },
    ],
  },
  'style': {
    description: 'Create and edit styles visually',
    tasks: [
      { id: '2', title: 'Vector Styling', path: '/rendering-workshop/tasks/02-vector-tiles.html' },
      { id: '3', title: 'Maputnik Editor', path: '/rendering-workshop/tasks/03-maputnik/instructions.html' },
    ],
  },
  'render': null, // No workshop for render stage (theory focused)
};

interface InfoPanelProps {
  stageNumber: number;
  title: string;
  description: string;
  insight: string;
  stageId: StageId;
}

/** Sample code snippets for each stage */
const STAGE_CODE: Record<StageId, { code: string; language: string; title: string }> = {
  'data-sources': {
    title: 'GeoJSON Feature',
    language: 'json',
    code: `{
  "type": "Feature",
  "properties": {
    "name": "Hauptbahnhof",
    "building": "train_station",
    "height": 25
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [
      [[8.54, 47.37], [8.55, 47.37], [8.55, 47.38], [8.54, 47.38], [8.54, 47.37]]
    ]
  }
}`,
  },
  tiling: {
    title: 'Tile Coordinate Calculation',
    language: 'typescript',
    code: `// Convert lat/lng to tile coordinates
function latLngToTile(lat: number, lng: number, zoom: number) {
  const n = Math.pow(2, zoom);  // 2^zoom tiles per axis
  const x = Math.floor(((lng + 180) / 360) * n);
  const latRad = (lat * Math.PI) / 180;
  const y = Math.floor(((1 - Math.asinh(Math.tan(latRad)) / Math.PI) / 2) * n);
  return { z: zoom, x, y };  // e.g., { z: 16, x: 34322, y: 22950 }
}`,
  },
  encoding: {
    title: 'MVT Protobuf Structure',
    language: 'protobuf',
    code: `message Tile {
  repeated Layer layers = 3;
}
message Layer {
  required string name = 1;        // e.g., "building", "road"
  repeated Feature features = 2;   // array of features
  repeated string keys = 3;        // ["height", "name"]
  repeated Value values = 4;       // [25, "Station"]
  optional uint32 extent = 5 [default = 4096];
}
message Feature {
  optional uint64 id = 1;
  repeated uint32 tags = 2;        // [key_idx, val_idx, ...]
  optional GeomType type = 3;      // POLYGON=3
  repeated uint32 geometry = 4;    // encoded commands
}`,
  },
  schema: {
    title: 'TileJSON Schema',
    language: 'json',
    code: `{
  "tilejson": "3.0.0",
  "tiles": ["https://tiles.example.com/{z}/{x}/{y}.pbf"],
  "vector_layers": [
    {
      "id": "building",
      "fields": { "height": "Number", "type": "String" }
    },
    {
      "id": "road",
      "fields": { "class": "String", "name": "String" }
    },
    {
      "id": "water",
      "fields": { "class": "String" }
    }
  ],
  "minzoom": 0,
  "maxzoom": 14
}`,
  },
  style: {
    title: 'MapLibre Style Layer',
    language: 'json',
    code: `{
  "id": "building-fill",
  "type": "fill",
  "source": "openmaptiles",
  "source-layer": "building",
  "paint": {
    "fill-color": [
      "interpolate", ["linear"], ["get", "height"],
      0, "#d4c4b0",
      50, "#8b7355"
    ],
    "fill-opacity": 0.9
  },
  "filter": ["==", ["get", "type"], "residential"]
}`,
  },
  render: {
    title: 'Render Loop',
    language: 'typescript',
    code: `// Per-frame render loop (60fps target)
function render() {
  for (const layer of style.layers) {
    // 1. Get features from decoded tile
    const features = tile.getLayer(layer['source-layer']);

    // 2. Apply filter if present
    const filtered = features.filter(f =>
      evaluateFilter(layer.filter, f)
    );

    // 3. Tessellate polygons into triangles
    const triangles = tessellate(filtered, layer);

    // 4. Upload to GPU and draw
    gl.bindBuffer(gl.ARRAY_BUFFER, triangles.buffer);
    gl.useProgram(layer.shader);
    gl.drawArrays(gl.TRIANGLES, 0, triangles.count);
  }
  requestAnimationFrame(render);
}`,
  },
};

/** Workshop Link Icon */
function ExternalLinkIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ marginLeft: '4px', opacity: 0.7 }}
    >
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  );
}

export function InfoPanel({
  stageNumber,
  title,
  description,
  insight,
  stageId,
}: InfoPanelProps) {
  const codeConfig = STAGE_CODE[stageId];
  const workshop = STAGE_WORKSHOPS[stageId];

  return (
    <aside className="pipeline-info-panel">
      <div className="info-panel-content">
        {/* Stage Title */}
        <div className="stage-title">
          <h2>{title}</h2>
          <span className="stage-badge">Stage {stageNumber}</span>
        </div>

        {/* Description */}
        <p className="stage-description">{description}</p>

        {/* Insight Box */}
        <div className="stage-insight">
          <div className="insight-header">
            <span className="insight-star">★</span>
            <span>Key Insight</span>
          </div>
          <p className="insight-text">{insight}</p>
        </div>

        {/* Workshop Links */}
        {workshop && (
          <div className="stage-workshop">
            <div className="workshop-header">
              <span className="workshop-icon">🛠</span>
              <span>Hands-On Practice</span>
            </div>
            <p className="workshop-description">{workshop.description}</p>
            <div className="workshop-links">
              {workshop.tasks.map((task) => (
                <a
                  key={task.id}
                  href={task.path}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="workshop-link"
                >
                  <span className="task-number">Task {task.id}</span>
                  <span className="task-title">{task.title}</span>
                  <ExternalLinkIcon />
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Code Panel */}
        <CodePanel
          code={codeConfig.code}
          language={codeConfig.language}
          title={codeConfig.title}
        />
      </div>
    </aside>
  );
}
