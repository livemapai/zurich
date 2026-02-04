/**
 * StylesViewer - AI Styles Map Viewer
 *
 * Main component combining MapLibre map with style selection panel.
 * Displays AI-generated tiles with coverage visualization.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { StylePanel } from './StylePanel';
import type { StylesManifest, StylesViewerProps } from './types';

// Zurich center coordinates
const ZURICH_CENTER: [number, number] = [8.5417, 47.3769];
const DEFAULT_ZOOM = 16; // Match AI tile zoom level

// All possible style names for cleanup (both ai-* and sd-* prefixes)
const ALL_STYLES = [
  'ai-winter', 'ai-cyberpunk', 'ai-watercolor', 'ai-autumn', 'ai-blueprint', 'ai-retro',
  'sd-winter', 'sd-cyberpunk', 'sd-watercolor', 'sd-autumn', 'sd-blueprint', 'sd-retro',
  'satellite',
  // Legacy names for cleanup
  'winter', 'cyberpunk', 'watercolor', 'autumn', 'blueprint', 'retro',
];

/** Convert bounds array to GeoJSON polygon */
function boundsToGeoJSON(bounds: [number, number, number, number]) {
  const [west, south, east, north] = bounds;
  return {
    type: 'Feature' as const,
    properties: {},
    geometry: {
      type: 'Polygon' as const,
      coordinates: [
        [
          [west, south],
          [east, south],
          [east, north],
          [west, north],
          [west, south],
        ],
      ],
    },
  };
}

/** Get tile source configuration for a style */
function getTileSource(styleName: string, manifest: StylesManifest) {
  if (styleName === 'satellite') {
    return {
      type: 'raster' as const,
      tiles: [manifest.satellite.url],
      tileSize: manifest.satellite.tileSize,
      attribution: '&copy; swisstopo',
    };
  }

  const style = manifest.styles.find((s) => s.name === styleName);
  if (!style) return null;

  // Style name already includes prefix (ai-winter, sd-winter, etc.)
  // Use it directly in the tile URL path
  return {
    type: 'raster' as const,
    tiles: [`/tiles/${styleName}/{z}/{x}/{y}.webp`],
    tileSize: 512,
    minzoom: style.zoom,
    maxzoom: 19,
    bounds: style.bounds,
  };
}

/** Remove all tile layers and sources from the map */
function clearAllTileLayers(map: maplibregl.Map) {
  for (const styleName of ALL_STYLES) {
    const layerId = `layer-${styleName}`;
    const sourceId = `tiles-${styleName}`;
    const coverageLayerId = `coverage-outline-${styleName}`;
    const coverageSourceId = `coverage-${styleName}`;

    try {
      if (map.getLayer(layerId)) map.removeLayer(layerId);
      if (map.getLayer(coverageLayerId)) map.removeLayer(coverageLayerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
      if (map.getSource(coverageSourceId)) map.removeSource(coverageSourceId);
    } catch (e) {
      // Ignore errors during cleanup
    }
  }
}

export function StylesViewer({ className = '' }: StylesViewerProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const currentStyleRef = useRef<string | null>(null);

  const [manifest, setManifest] = useState<StylesManifest | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedStyle, setSelectedStyle] = useState<string>('ai-winter');

  // Fetch manifest on mount
  useEffect(() => {
    async function fetchManifest() {
      try {
        const response = await fetch('/tiles/ai-styles.json');
        if (!response.ok) throw new Error('Failed to load styles manifest');
        const data = await response.json();
        setManifest(data);
      } catch (error) {
        console.error('Failed to load styles manifest:', error);
      } finally {
        setIsLoading(false);
      }
    }

    fetchManifest();
  }, []);

  // Initialize map
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        sources: {},
        layers: [
          {
            id: 'background',
            type: 'background',
            paint: { 'background-color': '#0a0a0a' },
          },
        ],
      },
      center: ZURICH_CENTER,
      zoom: DEFAULT_ZOOM,
      maxZoom: 19,
      minZoom: 10,
    });

    map.addControl(new maplibregl.NavigationControl(), 'bottom-right');

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Function to apply a style to the map
  const applyStyle = useCallback((styleName: string, manifest: StylesManifest) => {
    const map = mapRef.current;
    if (!map || !map.loaded()) return;

    // Skip if already showing this style
    if (currentStyleRef.current === styleName) {
      console.log(`Style ${styleName} already active`);
      return;
    }

    console.log(`Switching from ${currentStyleRef.current} to ${styleName}`);

    // Clear all existing tile layers first
    clearAllTileLayers(map);

    // Get source config for the new style
    const sourceConfig = getTileSource(styleName, manifest);
    if (!sourceConfig) {
      console.warn(`No source config for style: ${styleName}`);
      return;
    }

    const sourceId = `tiles-${styleName}`;
    const layerId = `layer-${styleName}`;

    // Add new source and layer
    console.log(`Adding source: ${sourceId}`, sourceConfig);
    map.addSource(sourceId, sourceConfig);
    map.addLayer({
      id: layerId,
      type: 'raster',
      source: sourceId,
      paint: {
        'raster-opacity': 1,
      },
    });

    // Add coverage outline for AI styles (not satellite)
    if (styleName !== 'satellite') {
      const style = manifest.styles.find((s) => s.name === styleName);
      if (style) {
        const coverageSourceId = `coverage-${styleName}`;
        const coverageLayerId = `coverage-outline-${styleName}`;

        map.addSource(coverageSourceId, {
          type: 'geojson',
          data: boundsToGeoJSON(style.bounds),
        });

        map.addLayer({
          id: coverageLayerId,
          type: 'line',
          source: coverageSourceId,
          paint: {
            'line-color': '#ff6600',
            'line-width': 2,
            'line-dasharray': [4, 4],
          },
        });
      }
    }

    // Update current style ref
    currentStyleRef.current = styleName;

    // Force repaint
    map.triggerRepaint();
  }, []);

  // Apply initial style when map loads
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !manifest) return;

    const onLoad = () => {
      console.log('Map loaded, applying initial style:', selectedStyle);
      applyStyle(selectedStyle, manifest);
    };

    if (map.loaded()) {
      onLoad();
    } else {
      map.on('load', onLoad);
      return () => {
        map.off('load', onLoad);
      };
    }
  // Only run on initial mount when manifest is ready
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manifest]);

  // Handle style selection - directly apply style, don't rely on useEffect
  const handleStyleSelect = useCallback(
    (styleName: string) => {
      console.log('handleStyleSelect called:', styleName);
      setSelectedStyle(styleName);

      const map = mapRef.current;
      if (!map || !manifest) {
        console.log('Map or manifest not ready');
        return;
      }

      // Apply the style directly
      applyStyle(styleName, manifest);

      // Fly to coverage center, always at zoom 16
      if (styleName === 'satellite') {
        map.flyTo({
          center: ZURICH_CENTER,
          zoom: DEFAULT_ZOOM,
          duration: 1000,
        });
      } else {
        const style = manifest.styles.find((s) => s.name === styleName);
        if (style) {
          const [west, south, east, north] = style.bounds;
          const centerLng = (west + east) / 2;
          const centerLat = (south + north) / 2;
          map.flyTo({
            center: [centerLng, centerLat],
            zoom: 16, // Always zoom 16 - we only have tiles at this level
            duration: 1000,
          });
        }
      }
    },
    [manifest, applyStyle]
  );

  return (
    <div className={`styles-page ${className}`}>
      <StylePanel
        manifest={manifest}
        selectedStyle={selectedStyle}
        onStyleSelect={handleStyleSelect}
        isLoading={isLoading}
      />

      <div className="styles-map-container">
        <div ref={mapContainerRef} style={{ width: '100%', height: '100%' }} />

        {/* Coverage legend for AI styles */}
        {selectedStyle !== 'satellite' && manifest && (
          <div className="coverage-legend">
            <div className="coverage-legend-title">Coverage</div>
            <div className="coverage-legend-items">
              <div className="coverage-legend-item">
                <div className="coverage-legend-line dashed" />
                <span>Generated tiles area</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default StylesViewer;
