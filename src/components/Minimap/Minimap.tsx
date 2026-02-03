/**
 * Minimap Component
 *
 * Displays an overhead view of the player's position and surroundings.
 * Shows buildings, player marker, and view cone direction.
 */

import { useMemo } from 'react';
import DeckGL from '@deck.gl/react';
import { OrthographicView } from '@deck.gl/core';
import { createMinimapLayers } from '@/layers';
import type { BuildingFeature, LngLat } from '@/types';

export interface MinimapProps {
  /** Player longitude (WGS84 degrees) */
  playerLongitude: number;
  /** Player latitude (WGS84 degrees) */
  playerLatitude: number;
  /** Player bearing (0 = North, 90 = East) */
  playerBearing: number;
  /** Building features for display */
  buildings?: BuildingFeature[];
  /** Whether minimap is visible */
  visible?: boolean;
  /** Size of minimap in pixels */
  size?: number;
}

const MINIMAP_ZOOM = 17; // Zoom level for minimap

export function Minimap({
  playerLongitude,
  playerLatitude,
  playerBearing,
  buildings,
  visible = true,
  size = 200,
}: MinimapProps) {
  // Player position as LngLat for minimap layers
  const playerPosition: LngLat = useMemo(
    () => [playerLongitude, playerLatitude],
    [playerLongitude, playerLatitude]
  );

  // Create minimap layers
  const layers = useMemo(() => {
    return createMinimapLayers(
      {
        playerPosition,
        playerBearing,
        viewConeDistance: 0.0015, // ~110m at Zurich
        viewConeAngle: 30,
      },
      buildings
    );
  }, [playerPosition, playerBearing, buildings]);

  // OrthographicView settings centered on player
  const viewState = useMemo(
    () => ({
      target: [playerLongitude, playerLatitude, 0] as [number, number, number],
      zoom: MINIMAP_ZOOM,
    }),
    [playerLongitude, playerLatitude]
  );

  if (!visible) {
    return null;
  }

  return (
    <div
      style={{
        position: 'absolute',
        top: 10,
        right: 10,
        width: size,
        height: size,
        borderRadius: 8,
        overflow: 'hidden',
        border: '2px solid rgba(255, 255, 255, 0.3)',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.3)',
        pointerEvents: 'none',
      }}
    >
      <DeckGL
        views={
          new OrthographicView({
            id: 'minimap',
            flipY: false,
          })
        }
        viewState={viewState}
        controller={false}
        layers={layers}
        style={{
          background: 'rgba(30, 40, 50, 0.9)',
        }}
      />

      {/* North indicator */}
      <div
        style={{
          position: 'absolute',
          top: 8,
          left: '50%',
          transform: `translateX(-50%) rotate(${-playerBearing}deg)`,
          color: '#fff',
          fontSize: 12,
          fontWeight: 'bold',
          textShadow: '0 1px 2px rgba(0,0,0,0.8)',
          transition: 'transform 0.1s ease-out',
        }}
      >
        N
      </div>

      {/* Compass ring tick marks */}
      <div
        style={{
          position: 'absolute',
          top: 4,
          left: 4,
          right: 4,
          bottom: 4,
          borderRadius: '50%',
          border: '1px solid rgba(255, 255, 255, 0.2)',
          pointerEvents: 'none',
        }}
      />
    </div>
  );
}
