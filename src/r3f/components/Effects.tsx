/**
 * Effects - Post-Processing Visual Effects
 *
 * Adds screen-space effects for visual polish:
 * - SSAO (Screen Space Ambient Occlusion) for depth perception
 * - Bloom for light glow effects
 *
 * NOTE: SSAO is disabled by default because it's incompatible with
 * logarithmicDepthBuffer (causes horizontal banding artifacts).
 */

import { EffectComposer, SSAO, Bloom } from '@react-three/postprocessing';

interface EffectsProps {
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
}

export function Effects({
  ssaoEnabled = false, // Disabled by default - causes horizontal banding with logarithmic depth buffer
  ssaoRadius = 0.5,
  ssaoIntensity = 30,
  bloomIntensity = 0.5,
  bloomThreshold = 0.9,
}: EffectsProps) {
  // Render different EffectComposer configurations based on what's enabled
  if (ssaoEnabled) {
    return (
      <EffectComposer enableNormalPass>
        <SSAO
          samples={16}
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
    );
  }

  return (
    <EffectComposer>
      <Bloom
        intensity={bloomIntensity}
        luminanceThreshold={bloomThreshold}
        luminanceSmoothing={0.9}
        mipmapBlur
      />
    </EffectComposer>
  );
}

export default Effects;
