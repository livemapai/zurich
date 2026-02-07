/**
 * TilingStage - Stage 2: Tile Pyramid
 *
 * Visualizes how the world is divided into tiles at different zoom levels:
 * - Web Mercator projection squares the world
 * - Each zoom level has 4× more tiles
 * - Tile count = 2^Z × 2^Z = 4^Z
 * - URL pattern: /{z}/{x}/{y}.pbf
 */

import { useState, useMemo } from 'react';
import type { StageProps } from '../types';

/** Tile count statistics by zoom level */
const ZOOM_STATS = [
  { zoom: 0, tiles: 1, coverage: 'Whole world' },
  { zoom: 2, tiles: 16, coverage: 'Continents' },
  { zoom: 6, tiles: 4096, coverage: 'Countries' },
  { zoom: 10, tiles: 1048576, coverage: 'Cities' },
  { zoom: 14, tiles: 268435456, coverage: 'Buildings' },
  { zoom: 16, tiles: 4294967296, coverage: 'Maximum detail' },
];

/** Format large numbers with abbreviations */
function formatTileCount(count: number): string {
  if (count >= 1e9) return `${(count / 1e9).toFixed(1)}B`;
  if (count >= 1e6) return `${(count / 1e6).toFixed(1)}M`;
  if (count >= 1e3) return `${(count / 1e3).toFixed(1)}K`;
  return count.toString();
}

/** Generate pyramid tile visualization */
function TilePyramid({ zoom }: { zoom: number }) {
  const tileSize = 200 / Math.pow(2, Math.min(zoom, 4));
  const tilesPerRow = Math.pow(2, Math.min(zoom, 4));
  const offsetX = (300 - tileSize * tilesPerRow) / 2;

  // Generate visible tiles (max 16 at zoom 4+ for performance)
  const tiles = useMemo(() => {
    const result = [];
    const maxTiles = Math.min(Math.pow(2, zoom), 4);
    for (let y = 0; y < maxTiles; y++) {
      for (let x = 0; x < maxTiles; x++) {
        result.push({ x, y });
      }
    }
    return result;
  }, [zoom]);

  return (
    <svg viewBox="0 0 300 250" className="tile-pyramid-svg">
      {/* Background grid */}
      <rect
        x={offsetX}
        y={10}
        width={tileSize * tilesPerRow}
        height={tileSize * tilesPerRow}
        fill="rgba(136, 192, 255, 0.05)"
        stroke="rgba(136, 192, 255, 0.2)"
        strokeWidth="1"
        rx="4"
      />

      {/* Tile grid */}
      {tiles.map((tile, i) => {
        const x = offsetX + tile.x * tileSize;
        const y = 10 + tile.y * tileSize;
        const hue = (tile.x * 30 + tile.y * 60) % 360;

        return (
          <g key={i}>
            <rect
              x={x + 1}
              y={y + 1}
              width={tileSize - 2}
              height={tileSize - 2}
              fill={`hsla(${hue}, 50%, 40%, 0.3)`}
              stroke={`hsla(${hue}, 60%, 60%, 0.6)`}
              strokeWidth="1"
              rx="2"
            >
              <animate
                attributeName="opacity"
                values="0.5;1;0.5"
                dur="2s"
                repeatCount="indefinite"
                begin={`${i * 0.1}s`}
              />
            </rect>
            {zoom <= 2 && (
              <text
                x={x + tileSize / 2}
                y={y + tileSize / 2 + 4}
                textAnchor="middle"
                fill="rgba(255, 255, 255, 0.8)"
                fontSize="10"
              >
                {tile.x},{tile.y}
              </text>
            )}
          </g>
        );
      })}

      {/* Zoom indicator */}
      <text x="150" y="235" textAnchor="middle" fill="#88c0ff" fontSize="12">
        Zoom {zoom}: {tilesPerRow}×{tilesPerRow} = {Math.pow(tilesPerRow, 2)} tiles shown
      </text>
    </svg>
  );
}

/** Zurich tile example */
function ZurichTileExample({ zoom }: { zoom: number }) {
  // Zurich coordinates: ~47.37°N, 8.54°E
  const lat = 47.37;
  const lng = 8.54;

  // Calculate tile coordinates
  const n = Math.pow(2, zoom);
  const x = Math.floor(((lng + 180) / 360) * n);
  const latRad = (lat * Math.PI) / 180;
  const y = Math.floor(((1 - Math.asinh(Math.tan(latRad)) / Math.PI) / 2) * n);

  return (
    <div className="zurich-tile-example">
      <div className="tile-coords">
        <span className="coord-label">Zurich tile at zoom {zoom}:</span>
        <code className="tile-url">
          /{zoom}/{x}/{y}.pbf
        </code>
      </div>
      <div className="tile-breakdown">
        <span>z={zoom}</span>
        <span>x={x.toLocaleString()}</span>
        <span>y={y.toLocaleString()}</span>
      </div>
    </div>
  );
}

export function TilingStage({ isActive }: StageProps) {
  const [zoom, setZoom] = useState(2);

  const currentStats = useMemo(() => {
    const totalTiles = Math.pow(4, zoom);
    const tilesPerAxis = Math.pow(2, zoom);
    const stat = ZOOM_STATS.find((s) => s.zoom === zoom) ||
      ZOOM_STATS.find((s) => s.zoom <= zoom)!;
    return { totalTiles, tilesPerAxis, coverage: stat?.coverage || 'Detail level' };
  }, [zoom]);

  if (!isActive) return null;

  return (
    <div className="tile-pyramid-container">
      {/* Zoom Control */}
      <div className="tile-pyramid-controls">
        <span className="zoom-label">Zoom Level</span>
        <input
          type="range"
          className="zoom-slider"
          min={0}
          max={8}
          value={zoom}
          onChange={(e) => setZoom(parseInt(e.target.value, 10))}
        />
        <span className="zoom-value">{zoom}</span>
      </div>

      {/* Tile Statistics */}
      <div className="tile-stats">
        <div className="tile-stat">
          <span className="stat-value">{currentStats.tilesPerAxis}</span>
          <span className="stat-label">tiles/axis</span>
        </div>
        <div className="tile-stat">
          <span className="stat-value">{formatTileCount(currentStats.totalTiles)}</span>
          <span className="stat-label">total tiles</span>
        </div>
        <div className="tile-stat">
          <span className="stat-value">4<sup>{zoom}</sup></span>
          <span className="stat-label">= 2<sup>{zoom}</sup> × 2<sup>{zoom}</sup></span>
        </div>
      </div>

      {/* Pyramid Visualization */}
      <TilePyramid zoom={zoom} />

      {/* Zurich Example */}
      <ZurichTileExample zoom={zoom} />

      {/* Zoom Level Reference */}
      <div className="zoom-reference">
        <h4>Zoom Level Reference</h4>
        <div className="zoom-table">
          {ZOOM_STATS.map((stat) => (
            <div
              key={stat.zoom}
              className={`zoom-row ${zoom === stat.zoom ? 'active' : ''}`}
              onClick={() => setZoom(stat.zoom)}
            >
              <span className="zoom-level">Z{stat.zoom}</span>
              <span className="zoom-tiles">{formatTileCount(stat.tiles)}</span>
              <span className="zoom-coverage">{stat.coverage}</span>
            </div>
          ))}
        </div>
      </div>

      <style>{`
        .tile-pyramid-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 1.5rem;
          width: 100%;
          height: 100%;
          overflow-y: auto;
        }

        .tile-stats {
          display: flex;
          gap: 2rem;
          margin-bottom: 1.5rem;
        }

        .tile-stat {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 0.75rem 1.25rem;
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 8px;
        }

        .stat-value {
          font-size: 1.5rem;
          font-weight: 600;
          color: #88c0ff;
        }

        .stat-value sup {
          font-size: 0.875rem;
        }

        .stat-label {
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.5);
          margin-top: 0.25rem;
        }

        .tile-pyramid-svg {
          width: 100%;
          max-width: 320px;
          margin-bottom: 1.5rem;
        }

        .zurich-tile-example {
          padding: 1rem 1.5rem;
          background: rgba(255, 140, 0, 0.08);
          border: 1px solid rgba(255, 140, 0, 0.2);
          border-radius: 8px;
          margin-bottom: 1.5rem;
          text-align: center;
        }

        .tile-coords {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .coord-label {
          font-size: 0.8125rem;
          color: rgba(255, 255, 255, 0.6);
        }

        .tile-url {
          font-size: 1.125rem;
          font-family: 'SF Mono', Monaco, monospace;
          color: #ff8c00;
        }

        .tile-breakdown {
          display: flex;
          justify-content: center;
          gap: 1rem;
          margin-top: 0.75rem;
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.5);
          font-family: 'SF Mono', Monaco, monospace;
        }

        .zoom-reference {
          width: 100%;
          max-width: 400px;
        }

        .zoom-reference h4 {
          margin: 0 0 0.75rem;
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: rgba(255, 255, 255, 0.5);
        }

        .zoom-table {
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
        }

        .zoom-row {
          display: grid;
          grid-template-columns: 40px 80px 1fr;
          gap: 0.75rem;
          padding: 0.5rem 0.75rem;
          background: rgba(255, 255, 255, 0.02);
          border: 1px solid transparent;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .zoom-row:hover {
          background: rgba(255, 255, 255, 0.05);
        }

        .zoom-row.active {
          background: rgba(136, 192, 255, 0.1);
          border-color: rgba(136, 192, 255, 0.3);
        }

        .zoom-level {
          font-weight: 600;
          color: #88c0ff;
        }

        .zoom-tiles {
          font-family: 'SF Mono', Monaco, monospace;
          color: rgba(255, 255, 255, 0.8);
        }

        .zoom-coverage {
          color: rgba(255, 255, 255, 0.5);
          font-size: 0.8125rem;
        }
      `}</style>
    </div>
  );
}
