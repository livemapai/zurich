/**
 * TilesViewer - Tile Gallery Component
 *
 * Displays generated tiles in a gallery grid for easy review.
 * Allows switching between styles and viewing individual tiles.
 */

import { useState, useEffect, useMemo } from 'react';
import type { TilesViewerProps, TileInfo, StylesManifest, StyleInfo } from './types';

/** Convert lat/lng to tile coordinates at a given zoom level */
function latLngToTile(lat: number, lng: number, zoom: number): { x: number; y: number } {
  const n = Math.pow(2, zoom);
  const x = Math.floor(((lng + 180) / 360) * n);
  const latRad = (lat * Math.PI) / 180;
  const y = Math.floor(((1 - Math.asinh(Math.tan(latRad)) / Math.PI) / 2) * n);
  return { x, y };
}

/** Get all tile coordinates for a style based on its bounds */
function getTilesForStyle(style: StyleInfo): TileInfo[] {
  const [west, south, east, north] = style.bounds;
  const zoom = style.zoom;

  const topLeft = latLngToTile(north, west, zoom);
  const bottomRight = latLngToTile(south, east, zoom);

  const tiles: TileInfo[] = [];
  for (let x = topLeft.x; x <= bottomRight.x; x++) {
    for (let y = topLeft.y; y <= bottomRight.y; y++) {
      tiles.push({
        x,
        y,
        z: zoom,
        path: `/tiles/${style.name}/${zoom}/${x}/${y}.webp`,
      });
    }
  }

  return tiles;
}

/** Get generator badge class */
function getGeneratorClass(generator: string): string {
  if (generator === 'blender-hybrid') return 'blender';
  return generator;
}

export function TilesViewer({ className = '' }: TilesViewerProps) {
  const [manifest, setManifest] = useState<StylesManifest | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedStyle, setSelectedStyle] = useState<string>('');
  const [failedTiles, setFailedTiles] = useState<Set<string>>(new Set());
  const [selectedTile, setSelectedTile] = useState<TileInfo | null>(null);

  // Fetch manifest on mount
  useEffect(() => {
    async function fetchManifest() {
      try {
        const response = await fetch('/tiles/ai-styles.json');
        if (!response.ok) throw new Error('Failed to load styles manifest');
        const data: StylesManifest = await response.json();
        setManifest(data);

        // Select first style by default
        const firstStyle = data.styles[0];
        if (firstStyle) {
          setSelectedStyle(firstStyle.name);
        }
      } catch (error) {
        console.error('Failed to load styles manifest:', error);
      } finally {
        setIsLoading(false);
      }
    }

    fetchManifest();
  }, []);

  // Get current style info
  const currentStyle = useMemo(() => {
    if (!manifest) return null;
    return manifest.styles.find((s) => s.name === selectedStyle) || null;
  }, [manifest, selectedStyle]);

  // Get tiles for current style
  const tiles = useMemo(() => {
    if (!currentStyle) return [];
    return getTilesForStyle(currentStyle);
  }, [currentStyle]);

  // Handle tile load error
  const handleTileError = (path: string) => {
    setFailedTiles((prev) => new Set([...prev, path]));
  };

  // Reset failed tiles when style changes
  useEffect(() => {
    setFailedTiles(new Set());
  }, [selectedStyle]);

  if (isLoading) {
    return (
      <div className={`tiles-page ${className}`}>
        <div className="tiles-loading">Loading styles...</div>
      </div>
    );
  }

  if (!manifest) {
    return (
      <div className={`tiles-page ${className}`}>
        <div className="tiles-error">Failed to load styles manifest</div>
      </div>
    );
  }

  return (
    <div className={`tiles-page ${className}`}>
      {/* Header with style selector */}
      <header className="tiles-header">
        <div className="tiles-header-left">
          <h1>Tile Gallery</h1>
          <span className="tiles-count">
            {tiles.length - failedTiles.size} / {tiles.length} tiles
          </span>
        </div>

        <div className="tiles-header-right">
          <select
            className="tiles-style-select"
            value={selectedStyle}
            onChange={(e) => setSelectedStyle(e.target.value)}
          >
            {manifest.styles.map((style) => (
              <option key={style.name} value={style.name}>
                {style.displayName} ({style.tiles} tiles)
              </option>
            ))}
          </select>
        </div>
      </header>

      {/* Style info bar */}
      {currentStyle && (
        <div className="tiles-info-bar">
          <div className="tiles-info-item">
            <span className="tiles-info-label">Generator</span>
            <span className={`generator-badge ${getGeneratorClass(currentStyle.generator)}`}>
              {currentStyle.generator === 'blender-hybrid' ? 'Blender' : currentStyle.generator}
            </span>
          </div>
          <div className="tiles-info-item">
            <span className="tiles-info-label">Zoom</span>
            <span className="tiles-info-value">{currentStyle.zoom}</span>
          </div>
          <div className="tiles-info-item">
            <span className="tiles-info-label">Colors</span>
            <div className="tiles-colors">
              {currentStyle.colors.map((color, i) => (
                <div
                  key={i}
                  className="tiles-color-swatch"
                  style={{ backgroundColor: color }}
                  title={color}
                />
              ))}
            </div>
          </div>
          <div className="tiles-info-item tiles-info-description">
            <span className="tiles-info-label">Description</span>
            <span className="tiles-info-value">{currentStyle.description}</span>
          </div>
        </div>
      )}

      {/* Tile grid */}
      <div className="tiles-grid">
        {tiles.map((tile) => {
          const isFailed = failedTiles.has(tile.path);
          return (
            <div
              key={tile.path}
              className={`tile-card ${isFailed ? 'failed' : ''}`}
              onClick={() => !isFailed && setSelectedTile(tile)}
            >
              {!isFailed ? (
                <img
                  src={tile.path}
                  alt={`Tile ${tile.z}/${tile.x}/${tile.y}`}
                  loading="lazy"
                  onError={() => handleTileError(tile.path)}
                />
              ) : (
                <div className="tile-placeholder">
                  <span>Missing</span>
                </div>
              )}
              <div className="tile-label">
                {tile.z}/{tile.x}/{tile.y}
              </div>
            </div>
          );
        })}
      </div>

      {/* Tile modal/lightbox */}
      {selectedTile && (
        <div className="tile-modal" onClick={() => setSelectedTile(null)}>
          <div className="tile-modal-content" onClick={(e) => e.stopPropagation()}>
            <img src={selectedTile.path} alt={`Tile ${selectedTile.z}/${selectedTile.x}/${selectedTile.y}`} />
            <div className="tile-modal-info">
              <span className="tile-modal-coords">
                {selectedTile.z}/{selectedTile.x}/{selectedTile.y}
              </span>
              <span className="tile-modal-path">{selectedTile.path}</span>
            </div>
            <button className="tile-modal-close" onClick={() => setSelectedTile(null)}>
              ×
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default TilesViewer;
