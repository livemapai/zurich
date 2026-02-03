/**
 * Sun position calculator for time-of-day lighting
 *
 * Calculates realistic sun direction, color, and intensity based on
 * time of day for Zurich latitude (~47°N).
 */

/**
 * Light configuration for a specific time of day
 */
export interface SunLighting {
  /** Direction vector for directional light [x, y, z] (pointing toward light source) */
  direction: [number, number, number];
  /** RGB color for directional light [0-255] */
  sunColor: [number, number, number];
  /** Intensity multiplier for directional light [0-1] */
  sunIntensity: number;
  /** RGB color for ambient light [0-255] */
  ambientColor: [number, number, number];
  /** Intensity multiplier for ambient light [0-1] */
  ambientIntensity: number;
  /** Background sky color as CSS color string */
  skyColor: string;
}

/**
 * Time presets for quick selection
 */
export const TIME_PRESETS = {
  dawn: 6 * 60, // 6:00
  morning: 9 * 60, // 9:00
  noon: 12 * 60, // 12:00
  golden: 19 * 60, // 19:00
} as const;

/**
 * Convert time in minutes (from midnight) to formatted HH:MM string
 */
export function formatTime(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`;
}

/**
 * Calculate sun position and lighting parameters for a given time
 *
 * Uses a simplified solar position model appropriate for Zurich (~47°N):
 * - Sun moves from east (morning) to south (noon) to west (evening)
 * - Elevation peaks around noon and drops to horizon at sunrise/sunset
 *
 * @param timeMinutes - Time of day in minutes from midnight (e.g., 720 = 12:00)
 * @returns Lighting configuration for the given time
 */
export function calculateSunLighting(timeMinutes: number): SunLighting {
  // Clamp time to valid range (5:00 - 22:00)
  const time = Math.max(5 * 60, Math.min(22 * 60, timeMinutes));

  // Calculate sun's progress through the day (0 at sunrise, 1 at sunset)
  // Sunrise ~5:00 (300 min), Sunset ~22:00 (1320 min)
  const dayStart = 5 * 60; // 5:00
  const dayEnd = 22 * 60; // 22:00
  const dayLength = dayEnd - dayStart;
  const dayProgress = (time - dayStart) / dayLength; // 0-1

  // Sun azimuth: moves from east (90°) through south (180°) to west (270°)
  // At sunrise: 90°, at noon: 180°, at sunset: 270°
  const azimuthDeg = 90 + dayProgress * 180;
  const azimuthRad = (azimuthDeg * Math.PI) / 180;

  // Sun elevation: peaks at solar noon (~12:00)
  // Uses a sine curve that peaks at noon
  // Elevation range: 0° at sunrise/sunset, ~60° at noon (summer solstice at 47°N)
  const noonProgress = Math.abs(dayProgress - 0.5) * 2; // 0 at noon, 1 at sunrise/sunset
  const maxElevation = 55; // degrees (approximate for Zurich summer)
  const elevationDeg = maxElevation * Math.cos(noonProgress * Math.PI / 2);
  const elevationRad = (elevationDeg * Math.PI) / 180;

  // Convert spherical coordinates to direction vector
  // deck.gl expects direction pointing FROM the light source
  // So we negate to get the direction light is coming FROM
  const cosElev = Math.cos(elevationRad);
  const sinElev = Math.sin(elevationRad);
  const cosAz = Math.cos(azimuthRad);
  const sinAz = Math.sin(azimuthRad);

  // Direction vector: [east, north, up] → negate for "light coming from"
  const direction: [number, number, number] = [
    -cosElev * sinAz, // X: east-west component
    -cosElev * cosAz, // Y: north-south component
    -sinElev, // Z: vertical component
  ];

  // Calculate light color based on sun elevation
  // Low sun = warm orange/red, high sun = neutral white
  const sunColor = calculateSunColor(elevationDeg);
  const sunIntensity = calculateSunIntensity(elevationDeg);

  // Ambient light varies with time (darker at dawn/dusk)
  const ambientColor = calculateAmbientColor(elevationDeg);
  const ambientIntensity = calculateAmbientIntensity(elevationDeg);

  // Sky color transitions through the day
  const skyColor = calculateSkyColor(time);

  return {
    direction,
    sunColor,
    sunIntensity,
    ambientColor,
    ambientIntensity,
    skyColor,
  };
}

/**
 * Calculate sun color based on elevation angle
 * Low angles = warm orange/red (Rayleigh scattering)
 * High angles = neutral white
 */
function calculateSunColor(elevationDeg: number): [number, number, number] {
  // Normalize elevation (0 at horizon, 1 at 60°+)
  const t = Math.min(1, elevationDeg / 30);

  // Color gradient: warm orange → golden yellow → neutral white
  // At horizon (t=0): [255, 180, 100] - warm orange
  // At high noon (t=1): [255, 252, 240] - warm white
  return [
    255, // Red stays constant
    Math.round(180 + t * 72), // Green: 180 → 252
    Math.round(100 + t * 140), // Blue: 100 → 240
  ];
}

/**
 * Calculate sun intensity based on elevation
 * Low angles have reduced intensity due to atmospheric absorption
 */
function calculateSunIntensity(elevationDeg: number): number {
  // Intensity ramps up from 0.3 at horizon to 1.0 at 30°+
  if (elevationDeg <= 0) return 0.3;
  if (elevationDeg >= 30) return 1.0;
  return 0.3 + (elevationDeg / 30) * 0.7;
}

/**
 * Calculate ambient light color based on time of day
 */
function calculateAmbientColor(elevationDeg: number): [number, number, number] {
  // Ambient light shifts from warm at low sun to neutral at high sun
  const t = Math.min(1, elevationDeg / 30);

  return [
    Math.round(255 - t * 10), // Slightly cooler red at noon
    Math.round(240 + t * 15), // More neutral green
    Math.round(220 + t * 35), // More blue at noon
  ];
}

/**
 * Calculate ambient intensity based on sun elevation
 */
function calculateAmbientIntensity(elevationDeg: number): number {
  // Ambient light increases with sun elevation
  // Dawn/dusk: 0.4, Midday: 0.8
  if (elevationDeg <= 0) return 0.4;
  if (elevationDeg >= 45) return 0.8;
  return 0.4 + (elevationDeg / 45) * 0.4;
}

/**
 * Calculate sky background color based on time
 */
function calculateSkyColor(timeMinutes: number): string {
  // Time-based sky color transitions
  const hour = timeMinutes / 60;

  // Pre-dawn / post-dusk (very early/late)
  if (hour < 5.5 || hour > 21.5) {
    return '#0a1628'; // Deep night blue
  }

  // Dawn (5:00 - 7:00)
  if (hour < 7) {
    const t = (hour - 5) / 2; // 0 at 5:00, 1 at 7:00
    // Transition from dark blue to orange/pink
    const r = Math.round(10 + t * 150);
    const g = Math.round(22 + t * 80);
    const b = Math.round(40 + t * 40);
    return `rgb(${r}, ${g}, ${b})`;
  }

  // Morning (7:00 - 9:00)
  if (hour < 9) {
    const t = (hour - 7) / 2;
    // Transition from orange to blue
    const r = Math.round(160 - t * 130);
    const g = Math.round(102 + t * 40);
    const b = Math.round(80 + t * 80);
    return `rgb(${r}, ${g}, ${b})`;
  }

  // Day (9:00 - 17:00)
  if (hour < 17) {
    return '#1a6faf'; // Clear blue sky
  }

  // Afternoon (17:00 - 19:00)
  if (hour < 19) {
    const t = (hour - 17) / 2;
    // Transition to golden hour
    const r = Math.round(26 + t * 140);
    const g = Math.round(111 - t * 20);
    const b = Math.round(175 - t * 60);
    return `rgb(${r}, ${g}, ${b})`;
  }

  // Sunset (19:00 - 21:00)
  if (hour < 21) {
    const t = (hour - 19) / 2;
    // Transition from orange to deep blue
    const r = Math.round(166 - t * 140);
    const g = Math.round(91 - t * 60);
    const b = Math.round(115 - t * 70);
    return `rgb(${r}, ${g}, ${b})`;
  }

  // Dusk (21:00 - 22:00)
  const t = (hour - 21);
  const r = Math.round(26 - t * 16);
  const g = Math.round(31 - t * 9);
  const b = Math.round(45 - t * 5);
  return `rgb(${r}, ${g}, ${b})`;
}
