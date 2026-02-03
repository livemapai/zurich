import { useMemo } from 'react';
import { LightingEffect, AmbientLight, DirectionalLight } from '@deck.gl/core';
import { calculateSunLighting, type SunLighting } from '@/utils';

/**
 * Hook result containing the lighting effect and current lighting parameters
 */
export interface UseSunLightingResult {
  /** Memoized LightingEffect for deck.gl */
  lightingEffect: LightingEffect;
  /** Current lighting parameters (for debugging/display) */
  lighting: SunLighting;
}

/**
 * Hook that creates a dynamic LightingEffect based on time of day
 *
 * This hook replaces the static lightingEffect constant, allowing
 * the scene lighting to change dynamically as the user adjusts the time slider.
 *
 * @param timeOfDay - Time in minutes from midnight (e.g., 720 = 12:00)
 * @returns Memoized LightingEffect and current lighting parameters
 *
 * @example
 * ```tsx
 * const [timeOfDay, setTimeOfDay] = useState(12 * 60); // noon
 * const { lightingEffect, lighting } = useSunLighting(timeOfDay);
 *
 * return (
 *   <DeckGL effects={[lightingEffect]} style={{ background: lighting.skyColor }}>
 *     ...
 *   </DeckGL>
 * );
 * ```
 */
export function useSunLighting(timeOfDay: number): UseSunLightingResult {
  // Calculate lighting parameters based on time
  const lighting = useMemo(() => calculateSunLighting(timeOfDay), [timeOfDay]);

  // Create memoized LightingEffect that updates when lighting changes
  const lightingEffect = useMemo(() => {
    return new LightingEffect({
      ambientLight: new AmbientLight({
        color: lighting.ambientColor,
        intensity: lighting.ambientIntensity,
      }),
      directionalLight: new DirectionalLight({
        color: lighting.sunColor,
        intensity: lighting.sunIntensity,
        direction: lighting.direction,
      }),
    });
  }, [
    lighting.ambientColor,
    lighting.ambientIntensity,
    lighting.sunColor,
    lighting.sunIntensity,
    lighting.direction,
  ]);

  return { lightingEffect, lighting };
}
