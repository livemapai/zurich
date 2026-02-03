/**
 * Tile Coordinate Utilities
 *
 * Handles conversion between geographic coordinates and tile indices
 * for loading OSM (OpenStreetMap) raster tiles.
 *
 * TILE COORDINATE SYSTEM (Web Mercator / EPSG:3857):
 * - Tiles are 256x256 pixel images
 * - Zoom level 0: entire world in one tile
 * - Zoom level N: 2^N × 2^N tiles
 * - Tile origin (0,0) is top-left (northwest corner)
 * - X increases eastward, Y increases southward
 *
 * OSM TILE URL FORMAT:
 * https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png
 * where {s} is a subdomain (a, b, or c) for load balancing
 */

import type { LngLat } from '@/types';

/** Tile index coordinates */
export interface TileIndex {
  x: number;
  y: number;
  z: number;
}

/** Tile bounds in geographic coordinates */
export interface TileBounds {
  west: number;
  east: number;
  north: number;
  south: number;
}

/** Tile with its geographic bounds and scene position */
export interface TileInfo {
  key: string;
  index: TileIndex;
  bounds: TileBounds;
  /** Center position in scene coordinates */
  center: [x: number, y: number, z: number];
  /** Size in scene coordinates [width, height] */
  size: [width: number, height: number];
  url: string;
}

/**
 * Convert longitude to tile X coordinate at a given zoom level.
 *
 * @param lng - Longitude in degrees (-180 to 180)
 * @param zoom - Zoom level (0-19)
 * @returns Tile X coordinate (fractional)
 */
export function lngToTileX(lng: number, zoom: number): number {
  return ((lng + 180) / 360) * Math.pow(2, zoom);
}

/**
 * Convert latitude to tile Y coordinate at a given zoom level.
 * Uses Spherical Mercator projection (EPSG:3857).
 *
 * @param lat - Latitude in degrees (-85.05 to 85.05)
 * @param zoom - Zoom level (0-19)
 * @returns Tile Y coordinate (fractional)
 */
export function latToTileY(lat: number, zoom: number): number {
  const latRad = (lat * Math.PI) / 180;
  const n = Math.pow(2, zoom);
  return ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * n;
}

/**
 * Convert tile X coordinate to longitude.
 *
 * @param x - Tile X coordinate
 * @param zoom - Zoom level
 * @returns Longitude in degrees
 */
export function tileXToLng(x: number, zoom: number): number {
  return (x / Math.pow(2, zoom)) * 360 - 180;
}

/**
 * Convert tile Y coordinate to latitude.
 *
 * @param y - Tile Y coordinate
 * @param zoom - Zoom level
 * @returns Latitude in degrees
 */
export function tileYToLat(y: number, zoom: number): number {
  const n = Math.PI - (2 * Math.PI * y) / Math.pow(2, zoom);
  return (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
}

/**
 * Get the tile index containing a geographic point.
 *
 * @param lng - Longitude in degrees
 * @param lat - Latitude in degrees
 * @param zoom - Zoom level
 * @returns Tile index {x, y, z}
 */
export function getTileIndex(lng: number, lat: number, zoom: number): TileIndex {
  return {
    x: Math.floor(lngToTileX(lng, zoom)),
    y: Math.floor(latToTileY(lat, zoom)),
    z: zoom,
  };
}

/**
 * Get the geographic bounds of a tile.
 *
 * @param tile - Tile index
 * @returns Geographic bounds {west, east, north, south}
 */
export function getTileBounds(tile: TileIndex): TileBounds {
  return {
    west: tileXToLng(tile.x, tile.z),
    east: tileXToLng(tile.x + 1, tile.z),
    north: tileYToLat(tile.y, tile.z),
    south: tileYToLat(tile.y + 1, tile.z),
  };
}

/**
 * Generate OSM tile URL.
 *
 * @param tile - Tile index
 * @param subdomain - Subdomain for load balancing (a, b, or c)
 * @returns Full tile URL
 */
export function getTileUrl(tile: TileIndex, subdomain: 'a' | 'b' | 'c' = 'a'): string {
  return `https://${subdomain}.tile.openstreetmap.org/${tile.z}/${tile.x}/${tile.y}.png`;
}

/**
 * Generate a unique key for a tile (for caching and React keys).
 *
 * @param tile - Tile index
 * @returns Unique string key
 */
export function getTileKey(tile: TileIndex): string {
  return `${tile.z}/${tile.x}/${tile.y}`;
}

/**
 * Get all tiles visible within a geographic bounding box.
 *
 * @param bounds - Geographic bounds
 * @param zoom - Zoom level
 * @returns Array of tile indices
 */
export function getTilesInBounds(
  bounds: { minLng: number; maxLng: number; minLat: number; maxLat: number },
  zoom: number
): TileIndex[] {
  const minX = Math.floor(lngToTileX(bounds.minLng, zoom));
  const maxX = Math.floor(lngToTileX(bounds.maxLng, zoom));
  const minY = Math.floor(latToTileY(bounds.maxLat, zoom)); // maxLat = north = smaller Y
  const maxY = Math.floor(latToTileY(bounds.minLat, zoom)); // minLat = south = larger Y

  const tiles: TileIndex[] = [];

  for (let x = minX; x <= maxX; x++) {
    for (let y = minY; y <= maxY; y++) {
      tiles.push({ x, y, z: zoom });
    }
  }

  return tiles;
}

/**
 * Get tiles in a radius around a center point.
 *
 * @param center - Center point [lng, lat]
 * @param radiusTiles - Number of tiles in each direction (total = (2*radius+1)^2)
 * @param zoom - Zoom level
 * @returns Array of tile indices
 */
export function getTilesAroundPoint(
  center: LngLat,
  radiusTiles: number,
  zoom: number
): TileIndex[] {
  const centerTile = getTileIndex(center[0], center[1], zoom);
  const tiles: TileIndex[] = [];

  for (let dx = -radiusTiles; dx <= radiusTiles; dx++) {
    for (let dy = -radiusTiles; dy <= radiusTiles; dy++) {
      tiles.push({
        x: centerTile.x + dx,
        y: centerTile.y + dy,
        z: zoom,
      });
    }
  }

  return tiles;
}

/**
 * Calculate the approximate size of a tile in meters at a given latitude.
 *
 * @param lat - Latitude in degrees
 * @param zoom - Zoom level
 * @returns Tile size in meters [width, height]
 */
export function getTileSizeMeters(lat: number, zoom: number): [number, number] {
  // Earth's circumference at equator ≈ 40,075 km
  const earthCircumference = 40075016.686;
  const tilesAtZoom = Math.pow(2, zoom);

  // Width varies with latitude (cosine correction)
  const metersPerTileX = (earthCircumference * Math.cos((lat * Math.PI) / 180)) / tilesAtZoom;
  // Height is constant (in Mercator projection, tiles are square in screen space)
  const metersPerTileY = earthCircumference / tilesAtZoom;

  return [metersPerTileX, metersPerTileY];
}
