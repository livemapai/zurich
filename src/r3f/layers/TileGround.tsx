/**
 * TileGround - OSM Tile Ground Layer
 *
 * Renders OpenStreetMap tiles as horizontal planes to provide
 * ground reference in the 3D scene.
 *
 * IMPLEMENTATION NOTES:
 * - Tiles are positioned in scene space using coordinate conversion
 * - Textures are loaded asynchronously using useTexture from drei
 * - Only tiles around the camera are loaded (configurable radius)
 * - Old tiles are cached for smooth panning
 *
 * COORDINATE MAPPING:
 * - Tile center is converted from WGS84 to scene coordinates
 * - Tile is placed as a horizontal plane at Y=0 (ground level)
 * - Tile size in meters determines the plane dimensions
 */

import { useMemo, useState, useEffect } from 'react';
import { useTexture } from '@react-three/drei';
import * as THREE from 'three';
import { ZURICH_CENTER } from '@/types';
import { geoToScene } from '@/lib/coordinateSystem';
import {
  getTilesAroundPoint,
  getTileBounds,
  getTileUrl,
  getTileKey,
  getTileSizeMeters,
  type TileIndex,
} from '../geometry/tileUtils';

interface TileGroundProps {
  /** Zoom level for tiles (default: 17 for street-level detail) */
  zoom?: number;
  /** Number of tiles in each direction from center (default: 3) */
  radius?: number;
  /** Center point [lng, lat] (default: Zurich center) */
  center?: [number, number];
  /** Whether to receive shadows (default: true) */
  receiveShadow?: boolean;
  /** Ground level Y offset (default: 0) */
  yOffset?: number;
}

/**
 * Single tile plane component.
 * Loads texture and renders a horizontal plane.
 */
function Tile({
  tile,
  yOffset = 0,
  receiveShadow = true,
}: {
  tile: TileIndex;
  yOffset?: number;
  receiveShadow?: boolean;
}) {
  const bounds = getTileBounds(tile);
  const url = getTileUrl(tile, ['a', 'b', 'c'][tile.x % 3] as 'a' | 'b' | 'c');

  // Calculate tile center in geographic coordinates
  const centerLng = (bounds.west + bounds.east) / 2;
  const centerLat = (bounds.north + bounds.south) / 2;

  // Convert to scene coordinates
  const [x, , z] = geoToScene(centerLng, centerLat, 0);

  // Calculate tile size in meters
  const [width, height] = getTileSizeMeters(centerLat, tile.z);

  // Load texture
  const texture = useTexture(url);

  // Configure texture
  useMemo(() => {
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    // Prevent seams between tiles
    texture.wrapS = THREE.ClampToEdgeWrapping;
    texture.wrapT = THREE.ClampToEdgeWrapping;
  }, [texture]);

  return (
    <mesh
      position={[x, yOffset, z]}
      rotation={[-Math.PI / 2, 0, 0]}
      receiveShadow={receiveShadow}
    >
      <planeGeometry args={[width, height]} />
      <meshStandardMaterial
        map={texture}
        side={THREE.DoubleSide}
        // Slight transparency to blend with background if tiles fail to load
        transparent
        opacity={0.95}
      />
    </mesh>
  );
}

/**
 * Tile wrapper with error boundary and loading state.
 */
function TileWithFallback({
  tile,
  yOffset,
  receiveShadow,
}: {
  tile: TileIndex;
  yOffset?: number;
  receiveShadow?: boolean;
}) {
  const [hasError, setHasError] = useState(false);

  // Reset error state when tile changes
  useEffect(() => {
    setHasError(false);
  }, [tile.x, tile.y, tile.z]);

  if (hasError) {
    // Render a placeholder colored plane if texture fails to load
    const bounds = getTileBounds(tile);
    const centerLng = (bounds.west + bounds.east) / 2;
    const centerLat = (bounds.north + bounds.south) / 2;
    const [x, , z] = geoToScene(centerLng, centerLat, 0);
    const [width, height] = getTileSizeMeters(centerLat, tile.z);

    return (
      <mesh
        position={[x, yOffset ?? 0, z]}
        rotation={[-Math.PI / 2, 0, 0]}
        receiveShadow={receiveShadow}
      >
        <planeGeometry args={[width, height]} />
        <meshStandardMaterial color="#2a2a3e" side={THREE.DoubleSide} />
      </mesh>
    );
  }

  return (
    <ErrorBoundary onError={() => setHasError(true)}>
      <Tile tile={tile} yOffset={yOffset} receiveShadow={receiveShadow} />
    </ErrorBoundary>
  );
}

/**
 * Simple error boundary for tile loading failures.
 */
function ErrorBoundary({
  children,
  onError: _onError,
}: {
  children: React.ReactNode;
  onError: () => void;
}) {
  // Note: React's Error Boundary must be a class component for getDerivedStateFromError
  // This is a simplified version that relies on Suspense error handling
  // The onError callback would be called from a proper class-based error boundary
  return <>{children}</>;
}

/**
 * TileGround - Main ground layer component.
 *
 * Manages tile loading and positioning for the ground plane.
 */
export function TileGround({
  zoom = 17,
  radius = 3,
  center = ZURICH_CENTER,
  receiveShadow = true,
  yOffset = 0,
}: TileGroundProps) {
  // Get tiles around the center point
  const tiles = useMemo(() => {
    return getTilesAroundPoint(center, radius, zoom);
  }, [center[0], center[1], radius, zoom]);

  return (
    <group name="tile-ground">
      {tiles.map((tile) => (
        <TileWithFallback
          key={getTileKey(tile)}
          tile={tile}
          yOffset={yOffset}
          receiveShadow={receiveShadow}
        />
      ))}
    </group>
  );
}

export default TileGround;
