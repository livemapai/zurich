/**
 * FirstPersonCamera - Static First-Person Camera
 *
 * A camera positioned at the player's eye level, initially looking north.
 * This is a static implementation that will be enhanced in Phase 5
 * with player physics and movement controls.
 *
 * CAMERA COORDINATE SYSTEM:
 * - Three.js: Y is up, -Z is forward (into the screen)
 * - Position [0, eyeHeight, 0] places camera at origin at eye level
 * - Looking at [0, eyeHeight, -100] faces north (negative Z)
 *
 * CONVERSION FROM DECK.GL:
 * - deck.gl bearing 0 = North = Three.js rotation.y 0 (looking at -Z)
 * - deck.gl pitch 0 = horizon = Three.js rotation.x 0
 */

import { useEffect, useRef } from 'react';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { CONFIG } from '@/lib/config';
import { geoToScene } from '@/lib/coordinateSystem';
import { ZURICH_CENTER } from '@/types';

interface FirstPersonCameraProps {
  /** Initial longitude (default: Zurich center) */
  longitude?: number;
  /** Initial latitude (default: Zurich center) */
  latitude?: number;
  /** Initial altitude in meters (default: eye height) */
  altitude?: number;
  /** Initial bearing in degrees (default: 0 = North) */
  bearing?: number;
  /** Initial pitch in degrees (default: 0 = horizon) */
  pitch?: number;
  /** Field of view in degrees (default: from config) */
  fov?: number;
}

/**
 * FirstPersonCamera positions and orients the main camera.
 * In Phase 5, this will be replaced with a physics-driven camera.
 */
export function FirstPersonCamera({
  longitude = ZURICH_CENTER[0],
  latitude = ZURICH_CENTER[1],
  altitude = CONFIG.player.eyeHeight,
  bearing = 0,
  pitch = 0,
  fov = CONFIG.render.fov,
}: FirstPersonCameraProps) {
  const { camera } = useThree();
  const initialized = useRef(false);

  useEffect(() => {
    // Only initialize once to avoid overwriting dynamic changes
    if (initialized.current) return;
    initialized.current = true;

    // Convert geographic position to scene coordinates
    const [x, y, z] = geoToScene(longitude, latitude, altitude);

    // Set camera position
    camera.position.set(x, y, z);

    // Set camera rotation
    // bearing: 0 = North (-Z) in Three.js, 90 = East (+X)
    // Convert bearing to Y rotation (radians, counter-clockwise)
    const rotationY = -((bearing * Math.PI) / 180);

    // pitch: 0 = horizon, positive = looking down
    // Convert to X rotation (radians, negative = looking down)
    const rotationX = -((pitch * Math.PI) / 180);

    // Apply rotation using Euler angles (order: YXZ for FPS-style camera)
    camera.rotation.order = 'YXZ';
    camera.rotation.set(rotationX, rotationY, 0);

    // Update FOV if it's a PerspectiveCamera
    if (camera instanceof THREE.PerspectiveCamera) {
      camera.fov = fov;
      camera.near = CONFIG.render.near;
      camera.far = CONFIG.render.far;
      camera.updateProjectionMatrix();
    }

    console.log(`Camera initialized at scene position: [${x.toFixed(1)}, ${y.toFixed(1)}, ${z.toFixed(1)}]`);
  }, [camera, longitude, latitude, altitude, bearing, pitch, fov]);

  // This component doesn't render anything visible
  return null;
}

export default FirstPersonCamera;
