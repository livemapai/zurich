/**
 * AdaptiveEffects - Performance-Aware Post-Processing
 *
 * Wraps @react-three/postprocessing effects with adaptive quality.
 * Automatically adjusts bloom based on FPS.
 *
 * FEATURES:
 * - Bloom: disabled at low quality, enabled otherwise
 * - Integrates with performanceStore for automatic adjustment
 * - Includes FPS monitor component
 *
 * NOTE: SSAO is disabled by default because it's incompatible with
 * logarithmicDepthBuffer (causes horizontal banding artifacts).
 * Use ssaoEnabled=true only if NOT using logarithmic depth buffer.
 *
 * USAGE:
 * Replace <Effects /> with <AdaptiveEffects /> in your scene:
 * ```tsx
 * <Scene>
 *   ...
 *   <AdaptiveEffects />
 * </Scene>
 * ```
 */

import { EffectComposer, SSAO, Bloom } from '@react-three/postprocessing';
import { usePerformanceSelector } from '../stores/performanceStore';
import { FPSMonitor } from '../hooks/useFPSMonitor';

interface AdaptiveEffectsProps {
  /** Enable SSAO (default: false - incompatible with logarithmic depth buffer) */
  ssaoEnabled?: boolean;
  /** SSAO radius (default: 0.5) */
  ssaoRadius?: number;
  /** SSAO intensity (default: 30) */
  ssaoIntensity?: number;
  /** Bloom intensity (default: 0.5) */
  bloomIntensity?: number;
  /** Bloom luminance threshold (default: 0.9) */
  bloomThreshold?: number;
  /** Whether to track and adapt to FPS (default: true) */
  adaptive?: boolean;
}

/**
 * AdaptiveEffects - Post-processing with automatic quality adjustment.
 *
 * This component monitors FPS and adjusts effect quality accordingly:
 * - Low quality: no bloom
 * - Medium/High quality: bloom enabled
 *
 * SSAO is disabled by default due to incompatibility with logarithmic depth buffer.
 */
export function AdaptiveEffects({
  ssaoEnabled = false, // Disabled by default - causes horizontal banding with logarithmic depth buffer
  ssaoRadius = 0.5,
  ssaoIntensity = 30,
  bloomIntensity = 0.5,
  bloomThreshold = 0.9,
  adaptive = true,
}: AdaptiveEffectsProps) {
  // Subscribe to quality settings from performance store
  const ssaoSamples = usePerformanceSelector((s) => s.ssaoSamples);
  const bloomEnabled = usePerformanceSelector((s) => s.bloomEnabled);

  // No effects needed if both SSAO and bloom are disabled
  if (!ssaoEnabled && !bloomEnabled) {
    return adaptive ? <FPSMonitor /> : null;
  }

  return (
    <>
      {/* FPS monitor updates performance store */}
      {adaptive && <FPSMonitor />}

      {/* Render different EffectComposer configurations based on what's enabled */}
      {ssaoEnabled && bloomEnabled && (
        <EffectComposer enableNormalPass>
          <SSAO
            samples={ssaoSamples}
            radius={ssaoRadius}
            intensity={ssaoIntensity}
            luminanceInfluence={0.5}
          />
          <Bloom
            intensity={bloomIntensity}
            luminanceThreshold={bloomThreshold}
            luminanceSmoothing={0.9}
            mipmapBlur
          />
        </EffectComposer>
      )}

      {ssaoEnabled && !bloomEnabled && (
        <EffectComposer enableNormalPass>
          <SSAO
            samples={ssaoSamples}
            radius={ssaoRadius}
            intensity={ssaoIntensity}
            luminanceInfluence={0.5}
          />
        </EffectComposer>
      )}

      {!ssaoEnabled && bloomEnabled && (
        <EffectComposer>
          <Bloom
            intensity={bloomIntensity}
            luminanceThreshold={bloomThreshold}
            luminanceSmoothing={0.9}
            mipmapBlur
          />
        </EffectComposer>
      )}
    </>
  );
}

export default AdaptiveEffects;
