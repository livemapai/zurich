/**
 * Sun Position Hook for Shadow Calculations
 *
 * Calculates sun azimuth and altitude based on time of day,
 * used for gradient shadow direction and intensity.
 *
 * Uses the SunCalc library for accurate astronomical calculations.
 */

import { useMemo } from 'react';
import SunCalc from 'suncalc';
import { ZURICH_CENTER } from '@/types';

/**
 * Sun position data for shadow rendering
 */
export interface SunPosition {
  /** Sun azimuth in degrees (0=North, 90=East, 180=South, 270=West) */
  azimuth: number;
  /** Sun altitude in degrees above horizon (0=horizon, 90=zenith) */
  altitude: number;
  /** Shadow direction in degrees (opposite of azimuth, where shadow falls) */
  shadowAzimuth: number;
  /** Shadow length multiplier (longer at low sun angles) */
  shadowLengthFactor: number;
  /** Whether the sun is above the horizon */
  isDaytime: boolean;
}

/**
 * Convert time in minutes from midnight to a Date object for today
 */
function minutesToDate(timeMinutes: number): Date {
  const now = new Date();
  const hours = Math.floor(timeMinutes / 60);
  const minutes = timeMinutes % 60;
  return new Date(now.getFullYear(), now.getMonth(), now.getDate(), hours, minutes);
}

/**
 * Hook that calculates sun position for a given time of day
 *
 * @param timeOfDay - Time in minutes from midnight (e.g., 720 = 12:00)
 * @returns Sun position data including azimuth, altitude, and shadow direction
 *
 * @example
 * ```tsx
 * const [timeOfDay, setTimeOfDay] = useState(14 * 60); // 14:00
 * const sunPosition = useSunPosition(timeOfDay);
 *
 * // Use in shadow layer
 * <GradientShadowLayer
 *   sunAzimuth={sunPosition.azimuth}
 *   sunAltitude={sunPosition.altitude}
 * />
 * ```
 */
export function useSunPosition(timeOfDay: number): SunPosition {
  return useMemo(() => {
    const date = minutesToDate(timeOfDay);
    const [lng, lat] = ZURICH_CENTER;

    // Get sun position from SunCalc (returns azimuth and altitude in radians)
    const sunPos = SunCalc.getPosition(date, lat, lng);

    // Convert from radians to degrees
    // SunCalc azimuth: 0 = South, measured clockwise (non-standard)
    // We want: 0 = North, 90 = East (standard compass)
    // Conversion: compass = (sunCalc + 180) % 360
    const azimuthDeg = ((sunPos.azimuth * 180) / Math.PI + 180) % 360;
    const altitudeDeg = (sunPos.altitude * 180) / Math.PI;

    // Shadow falls opposite to sun direction
    const shadowAzimuth = (azimuthDeg + 180) % 360;

    // Calculate shadow length factor based on sun altitude
    // At low sun angles, shadows are much longer
    // shadow_length = object_height / tan(altitude)
    // We normalize this to a multiplier where 1.0 = sun at 45°
    const altitudeRad = Math.max(0.01, sunPos.altitude); // Clamp to avoid divide by zero
    const shadowLengthFactor = 1 / Math.tan(altitudeRad);

    // Sun is considered "up" if altitude > 0
    const isDaytime = altitudeDeg > 0;

    return {
      azimuth: azimuthDeg,
      altitude: Math.max(0, altitudeDeg), // Clamp negative to 0
      shadowAzimuth,
      shadowLengthFactor: Math.min(10, shadowLengthFactor), // Cap extreme values
      isDaytime,
    };
  }, [timeOfDay]);
}
