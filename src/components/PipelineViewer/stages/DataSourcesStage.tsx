/**
 * DataSourcesStage - Stage 1: Raw Geodata Sources
 *
 * Visualizes the different sources of geodata:
 * - OpenStreetMap (OSM) - Crowdsourced, .osm.pbf files
 * - GeoJSON - Human-readable JSON, good for small datasets
 * - Shapefiles - Legacy ESRI format, still widely used
 * - PostGIS - PostgreSQL with spatial extensions
 */

import { useState, useMemo, type ReactNode } from 'react';
import type { StageProps, DataSourceType } from '../types';

interface DataSourceInfo {
  id: DataSourceType;
  name: string;
  format: string;
  description: string;
  icon: ReactNode;
  color: string;
  pros: string[];
  cons: string[];
}

const DATA_SOURCES: DataSourceInfo[] = [
  {
    id: 'osm',
    name: 'OpenStreetMap',
    format: '.osm.pbf',
    description: 'Crowdsourced global geodata with rich tagging schema',
    color: '#7eb533',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 2a10 10 0 0 0 0 20" strokeDasharray="2 2" />
        <path d="M2 12h20" />
        <path d="M12 2v20" />
      </svg>
    ),
    pros: ['Global coverage', 'Free & open', 'Rich tags'],
    cons: ['Large files', 'Needs processing'],
  },
  {
    id: 'geojson',
    name: 'GeoJSON',
    format: '.geojson',
    description: 'Human-readable JSON format, ideal for small datasets',
    color: '#f7df1e',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M4 6h16M4 12h16M4 18h10" />
        <circle cx="8" cy="6" r="2" fill="currentColor" />
        <rect x="6" y="10" width="8" height="4" rx="1" />
        <path d="M18 14l4 4-4 4" />
      </svg>
    ),
    pros: ['Human readable', 'Easy debugging', 'Web-native'],
    cons: ['Large file size', 'No streaming'],
  },
  {
    id: 'shapefile',
    name: 'Shapefile',
    format: '.shp/.dbf',
    description: 'Legacy ESRI format, still common in GIS workflows',
    color: '#3b82f6',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <path d="M3 9h18M9 3v18" />
        <polygon points="12,12 18,12 18,18 12,18" fill="currentColor" opacity="0.3" />
      </svg>
    ),
    pros: ['GIS standard', 'Wide support', 'Indexed'],
    cons: ['Multiple files', 'No UTF-8 native'],
  },
  {
    id: 'postgis',
    name: 'PostGIS',
    format: 'PostgreSQL',
    description: 'Spatial database enabling dynamic queries and filtering',
    color: '#336791',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <ellipse cx="12" cy="6" rx="8" ry="3" />
        <path d="M4 6v6c0 1.66 3.58 3 8 3s8-1.34 8-3V6" />
        <path d="M4 12v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6" />
        <circle cx="17" cy="14" r="3" fill="currentColor" opacity="0.3" />
      </svg>
    ),
    pros: ['SQL queries', 'Real-time', 'Spatial ops'],
    cons: ['Server required', 'Setup overhead'],
  },
];

/** Animated particle effect between sources */
function DataParticle({ sourceX, sourceY, delay }: { sourceX: number; sourceY: number; delay: number }) {
  return (
    <circle
      r="3"
      fill="#88c0ff"
      opacity="0.6"
      style={{
        animation: `dataFlow 2s ease-in-out ${delay}s infinite`,
      }}
    >
      <animateMotion
        dur="2s"
        repeatCount="indefinite"
        begin={`${delay}s`}
        path={`M ${sourceX} ${sourceY} Q 350 250 400 300`}
      />
      <animate
        attributeName="opacity"
        values="0;0.8;0.8;0"
        dur="2s"
        repeatCount="indefinite"
        begin={`${delay}s`}
      />
    </circle>
  );
}

export function DataSourcesStage({ isActive }: StageProps) {
  const [selectedSource, setSelectedSource] = useState<DataSourceType>('osm');

  const selectedInfo = useMemo(
    () => DATA_SOURCES.find((s) => s.id === selectedSource)!,
    [selectedSource]
  );

  if (!isActive) return null;

  return (
    <div className="data-sources-stage">
      {/* Source Cards Grid */}
      <div className="data-sources-grid">
        {DATA_SOURCES.map((source) => (
          <button
            key={source.id}
            className={`data-source-card ${selectedSource === source.id ? 'active' : ''}`}
            onClick={() => setSelectedSource(source.id)}
          >
            <div
              className="data-source-icon"
              style={{ color: source.color }}
            >
              {source.icon}
            </div>
            <div className="data-source-name">{source.name}</div>
            <div className="data-source-format">{source.format}</div>
          </button>
        ))}
      </div>

      {/* Selected Source Details */}
      <div className="data-source-details">
        <div className="source-detail-header" style={{ borderColor: selectedInfo.color }}>
          <h3>{selectedInfo.name}</h3>
          <span className="source-format-badge">{selectedInfo.format}</span>
        </div>
        <p className="source-description">{selectedInfo.description}</p>

        <div className="source-pros-cons">
          <div className="source-pros">
            <h4>Advantages</h4>
            <ul>
              {selectedInfo.pros.map((pro, i) => (
                <li key={i}>
                  <span className="pro-icon">✓</span>
                  {pro}
                </li>
              ))}
            </ul>
          </div>
          <div className="source-cons">
            <h4>Trade-offs</h4>
            <ul>
              {selectedInfo.cons.map((con, i) => (
                <li key={i}>
                  <span className="con-icon">○</span>
                  {con}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Flow Diagram */}
      <svg className="data-flow-diagram" viewBox="0 0 500 120">
        <defs>
          <marker
            id="arrow"
            markerWidth="10"
            markerHeight="7"
            refX="9"
            refY="3.5"
            orient="auto"
          >
            <polygon points="0 0, 10 3.5, 0 7" fill="#88c0ff" />
          </marker>
        </defs>

        {/* Source nodes */}
        <g transform="translate(50, 40)">
          <rect
            x="-40"
            y="-20"
            width="80"
            height="40"
            rx="8"
            fill={selectedInfo.color}
            opacity="0.2"
            stroke={selectedInfo.color}
          />
          <text x="0" y="5" textAnchor="middle" fill="#fff" fontSize="12">
            {selectedInfo.name.split(' ')[0]}
          </text>
        </g>

        {/* Processing node */}
        <g transform="translate(250, 40)">
          <rect
            x="-50"
            y="-20"
            width="100"
            height="40"
            rx="8"
            fill="rgba(136, 192, 255, 0.1)"
            stroke="#88c0ff"
          />
          <text x="0" y="5" textAnchor="middle" fill="#88c0ff" fontSize="12">
            Processing
          </text>
        </g>

        {/* Output node */}
        <g transform="translate(450, 40)">
          <rect
            x="-45"
            y="-20"
            width="90"
            height="40"
            rx="8"
            fill="rgba(255, 140, 0, 0.1)"
            stroke="#ff8c00"
          />
          <text x="0" y="5" textAnchor="middle" fill="#ff8c00" fontSize="12">
            Vector Tiles
          </text>
        </g>

        {/* Connecting arrows */}
        <line
          x1="90"
          y1="40"
          x2="195"
          y2="40"
          stroke="#88c0ff"
          strokeWidth="2"
          markerEnd="url(#arrow)"
        />
        <line
          x1="305"
          y1="40"
          x2="400"
          y2="40"
          stroke="#88c0ff"
          strokeWidth="2"
          markerEnd="url(#arrow)"
        />

        {/* Animated particles */}
        <DataParticle sourceX={90} sourceY={40} delay={0} />
        <DataParticle sourceX={90} sourceY={40} delay={0.5} />
        <DataParticle sourceX={305} sourceY={40} delay={1} />
      </svg>

      <style>{`
        .data-sources-stage {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 1.5rem;
          width: 100%;
          height: 100%;
          overflow-y: auto;
        }

        .data-source-details {
          max-width: 500px;
          margin-top: 1.5rem;
          padding: 1.25rem;
          background: rgba(255, 255, 255, 0.02);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 12px;
        }

        .source-detail-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding-bottom: 0.75rem;
          border-bottom: 2px solid;
          margin-bottom: 0.75rem;
        }

        .source-detail-header h3 {
          margin: 0;
          font-size: 1.125rem;
          color: #fff;
        }

        .source-format-badge {
          font-size: 0.75rem;
          padding: 0.25rem 0.5rem;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 4px;
          font-family: 'SF Mono', Monaco, monospace;
          color: rgba(255, 255, 255, 0.7);
        }

        .source-description {
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.7);
          line-height: 1.5;
          margin-bottom: 1rem;
        }

        .source-pros-cons {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 1rem;
        }

        .source-pros h4,
        .source-cons h4 {
          margin: 0 0 0.5rem;
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: rgba(255, 255, 255, 0.5);
        }

        .source-pros ul,
        .source-cons ul {
          margin: 0;
          padding: 0;
          list-style: none;
        }

        .source-pros li,
        .source-cons li {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.8125rem;
          color: rgba(255, 255, 255, 0.8);
          margin-bottom: 0.25rem;
        }

        .pro-icon {
          color: #4ade80;
        }

        .con-icon {
          color: rgba(255, 255, 255, 0.4);
        }

        .data-flow-diagram {
          width: 100%;
          max-width: 500px;
          margin-top: 1.5rem;
        }

        @keyframes dataFlow {
          0% { transform: scale(0.5); }
          50% { transform: scale(1); }
          100% { transform: scale(0.5); }
        }
      `}</style>
    </div>
  );
}
