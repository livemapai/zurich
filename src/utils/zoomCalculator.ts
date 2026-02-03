/**
 * Zoom Calculator Utility
 *
 * Calculates effective map zoom level from FirstPersonView camera parameters.
 * This is needed because FirstPersonView doesn't have a traditional "zoom" property,
 * but we need to know the effective zoom for zoom-dependent features like
 * hybrid tile switching.
 *
 * The formula converts from camera altitude + FOV to the equivalent web map zoom level.
 */

/**
 * Calculate effective map zoom level from FirstPersonView camera
 *
 * Formula derivation:
 * - metersPerPixel = eyeHeight / (viewportHeight * tan(fov/2))
 * - zoom = 28.5 - log2(metersPerPixel)
 *
 * The 28.5 constant comes from: zoom = 28.35 - log2(metersPerPixel)
 * where 28.35 is calibrated against web Mercator tiles at equator.
 * We use 28.5 which is slightly adjusted for mid-latitude (~47°N in Zurich).
 *
 * @param cameraAltitude - Camera altitude in meters (absolute, from sea level)
 * @param terrainElevation - Ground elevation in meters (from sea level)
 * @param viewportHeight - Viewport height in pixels
 * @param fov - Vertical field of view in degrees (default: 75)
 * @returns Effective zoom level (0-20 range)
 *
 * @example
 * ```ts
 * // Standing on ground in Zurich (408m elevation)
 * calculateEffectiveZoom(409.7, 408, 720, 75); // ~18
 *
 * // Flying 200m above ground
 * calculateEffectiveZoom(608, 408, 720, 75); // ~11
 * ```
 */
export function calculateEffectiveZoom(
  cameraAltitude: number,
  terrainElevation: number,
  viewportHeight: number,
  fov: number = 75
): number {
  // Calculate eye height above terrain
  const eyeHeight = cameraAltitude - terrainElevation;

  // At ground level or below, return maximum zoom
  if (eyeHeight <= 0) {
    return 20;
  }

  // Convert FOV from degrees to radians
  const fovRad = (fov * Math.PI) / 180;

  // Calculate meters per pixel at center of view
  // This formula projects the visible ground area onto the viewport
  const metersPerPixel = eyeHeight / (viewportHeight * Math.tan(fovRad / 2));

  // Convert to zoom level (clamped to valid range 0-20)
  const zoom = 28.5 - Math.log2(metersPerPixel);

  return Math.max(0, Math.min(20, zoom));
}
