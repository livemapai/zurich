/**
 * Shadow Layer Hook for VectorViewer
 *
 * Manages the deck.gl gradient shadow layer overlay on MapLibre,
 * including data extraction from vector tiles and time-based updates.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import type maplibregl from 'maplibre-gl';
import { MapboxOverlay } from '@deck.gl/mapbox';
import { createGradientShadowLayers } from '@/layers/GradientShadowLayer';
import { extractShadowsFromMapLibre, type ShadowFeature } from '@/lib/data/shadowLoader';
import { useSunPosition } from '@/hooks/useSunPosition';

export interface UseShadowLayerOptions {
  /** Whether gradient shadows are enabled */
  enabled: boolean;
  /** Time of day in minutes from midnight */
  timeOfDay: number;
  /** Shadow color RGB (0-255) */
  shadowColor?: [number, number, number];
  /** Maximum shadow opacity (0-1) */
  maxOpacity?: number;
  /** Number of gradient layers */
  gradientLayers?: number;
}

export interface UseShadowLayerResult {
  /** The MapboxOverlay instance (add to map with map.addControl) */
  overlay: MapboxOverlay | null;
  /** Initialize the overlay on a map */
  initializeOverlay: (map: maplibregl.Map) => void;
  /** Update shadow data from current map view */
  updateShadows: () => void;
  /** Cleanup function */
  cleanup: () => void;
  /** Current shadow feature count */
  shadowCount: number;
  /** Sun position data */
  sunPosition: ReturnType<typeof useSunPosition>;
}

/**
 * Hook that creates and manages a deck.gl shadow overlay on MapLibre
 *
 * @example
 * ```tsx
 * const { overlay, initializeOverlay, updateShadows } = useShadowLayer({
 *   enabled: true,
 *   timeOfDay: 14 * 60, // 2:00 PM
 * });
 *
 * useEffect(() => {
 *   if (map && overlay) {
 *     map.addControl(overlay);
 *     updateShadows();
 *   }
 * }, [map, overlay]);
 * ```
 */
export function useShadowLayer(options: UseShadowLayerOptions): UseShadowLayerResult {
  const {
    enabled,
    timeOfDay,
    shadowColor = [30, 30, 40],
    maxOpacity = 0.5,
    gradientLayers = 3,
  } = options;

  const [overlay, setOverlay] = useState<MapboxOverlay | null>(null);
  const [shadows, setShadows] = useState<ShadowFeature[]>([]);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);

  // Get sun position from time of day
  const sunPosition = useSunPosition(timeOfDay);

  /**
   * Initialize the MapboxOverlay on a map instance
   */
  const initializeOverlay = useCallback((map: maplibregl.Map) => {
    console.log('[useShadowLayer] Initializing overlay');
    mapRef.current = map;

    // Create the deck.gl overlay
    const newOverlay = new MapboxOverlay({
      interleaved: false, // Render on top of MapLibre layers
      layers: [],
    });

    overlayRef.current = newOverlay;
    setOverlay(newOverlay);

    // Add the overlay control to the map
    map.addControl(newOverlay as unknown as maplibregl.IControl);
    console.log('[useShadowLayer] Overlay initialized and added to map');
  }, []);

  /**
   * Extract shadow data from MapLibre vector tiles
   *
   * Uses querySourceFeatures() instead of queryRenderedFeatures() because
   * the MapLibre shadow layers are hidden when gradient shadows are enabled.
   * querySourceFeatures() returns all features from the vector tile source
   * regardless of layer visibility.
   */
  const updateShadows = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;

    try {
      // Query shadow features directly from the vector tile source
      // This works even when MapLibre shadow layers are hidden
      const features = map.querySourceFeatures('zurich', {
        sourceLayer: 'building_shadows',
      });

      console.log(`[useShadowLayer] Extracted ${features.length} shadow features from source`);

      if (features.length === 0) {
        console.warn('[useShadowLayer] No shadow features found in source. Check that:');
        console.warn('  - Source "zurich" exists');
        console.warn('  - Source layer "building_shadows" has data');
        console.warn('  - Map zoom level is >= 14 (shadows may not be in tiles at low zoom)');
        return;
      }

      // Convert to our shadow format
      const shadowFeatures = extractShadowsFromMapLibre(features);

      // Deduplicate by building ID
      const uniqueShadows = new Map<string, ShadowFeature>();
      for (const shadow of shadowFeatures) {
        const id = shadow.properties.buildingId || Math.random().toString();
        if (!uniqueShadows.has(id)) {
          uniqueShadows.set(id, shadow);
        }
      }

      const dedupedShadows = Array.from(uniqueShadows.values());
      console.log(`[useShadowLayer] After deduplication: ${dedupedShadows.length} unique shadows`);

      setShadows(dedupedShadows);
    } catch (error) {
      console.warn('[useShadowLayer] Failed to extract shadows:', error);
    }
  }, []);

  /**
   * Cleanup the overlay
   */
  const cleanup = useCallback(() => {
    const map = mapRef.current;
    const currentOverlay = overlayRef.current;

    if (map && currentOverlay) {
      try {
        map.removeControl(currentOverlay as unknown as maplibregl.IControl);
      } catch {
        // Ignore if already removed
      }
    }

    overlayRef.current = null;
    mapRef.current = null;
    setOverlay(null);
    setShadows([]);
  }, []);

  /**
   * Update deck.gl layers when shadow data or settings change
   */
  useEffect(() => {
    const currentOverlay = overlayRef.current;
    if (!currentOverlay) {
      console.log('[useShadowLayer] No overlay yet, skipping layer update');
      return;
    }

    if (!enabled || shadows.length === 0) {
      // Clear layers when disabled or no data
      console.log(`[useShadowLayer] Clearing layers (enabled=${enabled}, shadows=${shadows.length})`);
      currentOverlay.setProps({ layers: [] });
      return;
    }

    // Create the gradient shadow layers
    const shadowLayers = createGradientShadowLayers({
      id: 'gradient-shadows',
      data: shadows,
      shadowColor,
      maxOpacity,
      sunAltitude: sunPosition.altitude,
      gradientLayers,
    });

    console.log(`[useShadowLayer] Setting ${shadowLayers.length} deck.gl layers with ${shadows.length} shadows`);

    currentOverlay.setProps({
      layers: shadowLayers,
    });
  }, [enabled, shadows, shadowColor, maxOpacity, sunPosition.altitude, gradientLayers]);

  /**
   * Update shadows when map moves
   */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !enabled) return;

    const handleMoveEnd = () => {
      updateShadows();
    };

    map.on('moveend', handleMoveEnd);
    map.on('zoomend', handleMoveEnd);

    return () => {
      map.off('moveend', handleMoveEnd);
      map.off('zoomend', handleMoveEnd);
    };
  }, [enabled, updateShadows]);

  return {
    overlay,
    initializeOverlay,
    updateShadows,
    cleanup,
    shadowCount: shadows.length,
    sunPosition,
  };
}
