/**
 * Coordinate System Utilities
 *
 * Converts between WGS84 geographic coordinates (deck.gl) and
 * local Cartesian scene coordinates (Three.js/R3F).
 *
 * COORDINATE SYSTEMS:
 * - WGS84: [longitude, latitude] in degrees - used by deck.gl and GeoJSON
 * - Scene: [x, y, z] in meters - used by Three.js
 *   - X: meters east of origin
 *   - Y: meters up (altitude)
 *   - Z: meters south of origin (negated for THREE's coordinate system)
 *
 * WHY THE NEGATION?
 * - Geographic: North is positive latitude (increasing Y)
 * - Three.js: Default camera looks down -Z axis
 * - By negating latitude → Z, North (positive lat) becomes -Z,
 *   which aligns with the camera's forward direction
 */

import { ZURICH_CENTER, METERS_PER_DEGREE } from '@/types';
import type { LngLat } from '@/types';

/**
 * Configuration for the coordinate system origin.
 * All scene coordinates are relative to this geographic point.
 */
export interface CoordinateConfig {
  /** Geographic origin [lng, lat] in degrees */
  origin: LngLat;
  /** Meters per degree longitude at this latitude */
  metersPerDegreeLng: number;
  /** Meters per degree latitude */
  metersPerDegreeLat: number;
}

/** Default config centered on Zurich */
export const DEFAULT_COORDINATE_CONFIG: CoordinateConfig = {
  origin: ZURICH_CENTER,
  metersPerDegreeLng: METERS_PER_DEGREE.lng,
  metersPerDegreeLat: METERS_PER_DEGREE.lat,
};

/**
 * Convert WGS84 coordinates to scene position.
 *
 * @param lng - Longitude in degrees
 * @param lat - Latitude in degrees
 * @param altitude - Altitude in meters (default 0)
 * @param config - Coordinate system configuration
 * @returns [x, y, z] position in scene meters
 */
export function geoToScene(
  lng: number,
  lat: number,
  altitude = 0,
  config: CoordinateConfig = DEFAULT_COORDINATE_CONFIG
): [x: number, y: number, z: number] {
  const x = (lng - config.origin[0]) * config.metersPerDegreeLng;
  const y = altitude;
  // Negate latitude offset so North (positive lat) maps to -Z (forward in Three.js)
  const z = -(lat - config.origin[1]) * config.metersPerDegreeLat;

  return [x, y, z];
}

/**
 * Convert scene position to WGS84 coordinates.
 *
 * @param x - Meters east of origin
 * @param y - Meters up (altitude)
 * @param z - Meters south of origin (negated)
 * @param config - Coordinate system configuration
 * @returns { lng, lat, altitude } in degrees and meters
 */
export function sceneToGeo(
  x: number,
  y: number,
  z: number,
  config: CoordinateConfig = DEFAULT_COORDINATE_CONFIG
): { lng: number; lat: number; altitude: number } {
  const lng = config.origin[0] + x / config.metersPerDegreeLng;
  // Negate Z back to latitude offset
  const lat = config.origin[1] - z / config.metersPerDegreeLat;
  const altitude = y;

  return { lng, lat, altitude };
}

/**
 * Convert a LngLat array to scene X, Z coordinates (ignoring altitude).
 * Useful for converting GeoJSON point coordinates.
 *
 * @param coords - [lng, lat] array
 * @param config - Coordinate system configuration
 * @returns [x, z] scene position (y=0)
 */
export function lngLatToXZ(
  coords: LngLat,
  config: CoordinateConfig = DEFAULT_COORDINATE_CONFIG
): [x: number, z: number] {
  const [x, , z] = geoToScene(coords[0], coords[1], 0, config);
  return [x, z];
}

/**
 * Convert scene X, Z to LngLat array (ignoring altitude).
 * Useful for querying terrain at a scene position.
 *
 * @param x - Scene X coordinate
 * @param z - Scene Z coordinate
 * @param config - Coordinate system configuration
 * @returns [lng, lat] array
 */
export function xzToLngLat(
  x: number,
  z: number,
  config: CoordinateConfig = DEFAULT_COORDINATE_CONFIG
): LngLat {
  const { lng, lat } = sceneToGeo(x, 0, z, config);
  return [lng, lat];
}

/**
 * Calculate the scene bounds from geographic bounds.
 *
 * @param bounds - Geographic bounds { minLng, maxLng, minLat, maxLat }
 * @param config - Coordinate system configuration
 * @returns Scene bounds { minX, maxX, minZ, maxZ }
 */
export function geoBoundsToScene(
  bounds: { minLng: number; maxLng: number; minLat: number; maxLat: number },
  config: CoordinateConfig = DEFAULT_COORDINATE_CONFIG
): { minX: number; maxX: number; minZ: number; maxZ: number } {
  const [minX, , maxZ] = geoToScene(bounds.minLng, bounds.minLat, 0, config);
  const [maxX, , minZ] = geoToScene(bounds.maxLng, bounds.maxLat, 0, config);

  return { minX, maxX, minZ, maxZ };
}

/**
 * Convert deck.gl bearing to Three.js rotation.
 *
 * deck.gl bearing: 0 = North, 90 = East (clockwise from North)
 * Three.js rotation.y: 0 = +Z, positive = counter-clockwise
 *
 * @param bearing - Bearing in degrees (deck.gl convention)
 * @returns Rotation Y in radians (Three.js convention)
 */
export function bearingToRotationY(bearing: number): number {
  // Convert from clockwise-from-north to counter-clockwise-from-Z
  // deck.gl: 0=N, 90=E → Three.js needs negative rotation for clockwise
  return -((bearing * Math.PI) / 180);
}

/**
 * Convert Three.js rotation to deck.gl bearing.
 *
 * @param rotationY - Rotation Y in radians (Three.js convention)
 * @returns Bearing in degrees (deck.gl convention)
 */
export function rotationYToBearing(rotationY: number): number {
  return -(rotationY * 180) / Math.PI;
}

/**
 * Convert deck.gl pitch to Three.js rotation.
 *
 * deck.gl pitch: 0 = horizon, positive = looking down
 * Three.js rotation.x: 0 = horizon, negative = looking down
 *
 * @param pitch - Pitch in degrees (deck.gl convention)
 * @returns Rotation X in radians (Three.js convention)
 */
export function pitchToRotationX(pitch: number): number {
  return -(pitch * Math.PI) / 180;
}

/**
 * Convert Three.js rotation to deck.gl pitch.
 *
 * @param rotationX - Rotation X in radians (Three.js convention)
 * @returns Pitch in degrees (deck.gl convention)
 */
export function rotationXToPitch(rotationX: number): number {
  return -(rotationX * 180) / Math.PI;
}
