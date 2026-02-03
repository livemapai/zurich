/**
 * Zurich-specific constants and coordinate utilities
 *
 * Re-exports core constants from @/types (single source of truth)
 * and adds utility functions for coordinate conversions.
 */

// Re-export core constants from types (single source of truth)
export { ZURICH_CENTER, ZURICH_BOUNDS, METERS_PER_DEGREE, ZURICH_BASE_ELEVATION } from '@/types';

// Import for local use
import { ZURICH_CENTER, METERS_PER_DEGREE } from '@/types';

/** Default starting position (Zurich main station area) */
export const DEFAULT_POSITION: [number, number, number] = [
  ZURICH_CENTER[0], // longitude
  ZURICH_CENTER[1], // latitude
  100, // 100m altitude looking down
];

/** Conversion factor: degrees to radians */
export const DEG_TO_RAD = Math.PI / 180;

/** Conversion factor: radians to degrees */
export const RAD_TO_DEG = 180 / Math.PI;

/**
 * Convert meters to degrees longitude at Zurich latitude
 */
export function metersToDegreesLng(meters: number): number {
  return meters / METERS_PER_DEGREE.lng;
}

/**
 * Convert meters to degrees latitude
 */
export function metersToDegreesLat(meters: number): number {
  return meters / METERS_PER_DEGREE.lat;
}

/**
 * Convert degrees longitude to meters at Zurich latitude
 */
export function degreesLngToMeters(degrees: number): number {
  return degrees * METERS_PER_DEGREE.lng;
}

/**
 * Convert degrees latitude to meters
 */
export function degreesLatToMeters(degrees: number): number {
  return degrees * METERS_PER_DEGREE.lat;
}

/**
 * Clamp a value between min and max
 */
export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

/**
 * Linear interpolation between two values
 */
export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/**
 * Normalize an angle to [0, 360) range
 */
export function normalizeAngle(degrees: number): number {
  return ((degrees % 360) + 360) % 360;
}
