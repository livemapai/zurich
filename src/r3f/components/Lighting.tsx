/**
 * Lighting - Scene Lighting Configuration
 *
 * Provides lighting that matches the deck.gl viewer for visual consistency:
 * - Ambient light: 0.4 intensity (soft fill)
 * - Directional light: 1.0 intensity, direction [-1, -2, -3]
 *
 * The directional light simulates late afternoon sun from the northwest,
 * creating subtle shadows on building facades.
 *
 * COORDINATE MAPPING:
 * deck.gl direction: [-1, -2, -3] means light comes FROM [1, 2, 3]
 * Three.js position: We position the light at [1, 2, 3] (normalized direction)
 */

import { useRef } from 'react';
import * as THREE from 'three';

interface LightingProps {
  /** Ambient light intensity (default: 0.4) */
  ambientIntensity?: number;
  /** Directional light intensity (default: 1.0) */
  directionalIntensity?: number;
  /** Show debug helpers for light positions */
  debug?: boolean;
  /** Enable shadows from directional light */
  shadows?: boolean;
  /** Shadow map size (default: 2048) */
  shadowMapSize?: number;
}

export function Lighting({
  ambientIntensity = 0.4,
  directionalIntensity = 1.0,
  debug: _debug = false,
  shadows = true,
  shadowMapSize = 2048,
}: LightingProps) {
  const directionalRef = useRef<THREE.DirectionalLight>(null);

  // Note: useHelper disabled due to type compatibility issues
  // Debug visualization can be added back when needed

  // Normalize deck.gl light direction [-1, -2, -3] and flip to position
  // Light position = -direction (light comes FROM this position)
  // Magnitude scaling for shadow camera coverage
  const lightDistance = 500;
  const direction = new THREE.Vector3(-1, -2, -3).normalize();
  const lightPosition: [number, number, number] = [
    -direction.x * lightDistance,
    -direction.y * lightDistance,
    -direction.z * lightDistance,
  ];

  return (
    <>
      {/* Ambient light - soft fill to prevent pure black shadows */}
      <ambientLight intensity={ambientIntensity} color="#ffffff" />

      {/* Directional light - main scene illumination */}
      <directionalLight
        ref={directionalRef}
        position={lightPosition}
        intensity={directionalIntensity}
        color="#fffff0" // Warm white matching deck.gl
        castShadow={shadows}
        shadow-mapSize-width={shadowMapSize}
        shadow-mapSize-height={shadowMapSize}
        shadow-camera-near={1}
        shadow-camera-far={lightDistance * 2}
        shadow-camera-left={-500}
        shadow-camera-right={500}
        shadow-camera-top={500}
        shadow-camera-bottom={-500}
        shadow-bias={-0.0001}
      />

      {/* Hemisphere light - subtle sky/ground color variation */}
      <hemisphereLight
        intensity={0.2}
        color="#87ceeb" // Sky blue
        groundColor="#8b7355" // Earth brown
      />
    </>
  );
}

export default Lighting;
