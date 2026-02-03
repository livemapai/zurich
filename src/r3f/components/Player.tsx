/**
 * Player - First-Person Player Controller
 *
 * Combines camera control and movement into a physics-based player.
 * Uses a capsule collider for smooth collision with buildings.
 * Includes terrain following for ground-level walking.
 */

import { useRef } from 'react';
import { useThree, useFrame } from '@react-three/fiber';
import { RigidBody, CapsuleCollider } from '@react-three/rapier';
import type { RapierRigidBody } from '@react-three/rapier';
import { CONFIG } from '@/lib/config';
import { geoToScene, sceneToGeo, xzToLngLat } from '@/lib/coordinateSystem';
import { ZURICH_CENTER } from '@/types';
import { usePlayerCamera } from '../hooks/usePlayerCamera';
import { usePlayerMovement } from '../hooks/usePlayerMovement';

interface PlayerProps {
  /** Initial longitude (default: Zurich center) */
  longitude?: number;
  /** Initial latitude (default: Zurich center) */
  latitude?: number;
  /** Initial altitude in meters (default: eye height) */
  altitude?: number;
  /** Whether player control is enabled */
  enabled?: boolean;
  /** Callback with current position */
  onPositionChange?: (pos: { lng: number; lat: number; alt: number }) => void;
  /** Function to get terrain elevation at a position */
  getTerrainElevation?: (lng: number, lat: number) => number;
}

export function Player({
  longitude = ZURICH_CENTER[0],
  latitude = ZURICH_CENTER[1],
  altitude = CONFIG.player.eyeHeight,
  enabled = true,
  onPositionChange,
  getTerrainElevation,
}: PlayerProps) {
  const { camera } = useThree();
  const rigidBodyRef = useRef<RapierRigidBody>(null);

  // Camera control (mouse look)
  const { bearingRef } = usePlayerCamera({ enabled });

  // Movement control (keyboard)
  const { velocityRef } = usePlayerMovement({ bearingRef, enabled });

  // Initial position in scene coordinates
  const initialPos = useRef(geoToScene(longitude, latitude, altitude));

  // Track if player is flying (Q/E pressed)
  const isFlyingRef = useRef(false);

  // Sync camera with rigid body position
  useFrame((_, delta) => {
    if (!rigidBodyRef.current || !enabled) return;

    const rb = rigidBodyRef.current;
    const velocity = velocityRef.current;

    // Check if player is using fly controls
    isFlyingRef.current = Math.abs(velocity.y) > 0.1;

    // Only move if there's velocity input (pointer lock only affects mouse look, not WASD)
    if (velocity.lengthSq() > 0.001) {
      const currentPos = rb.translation();

      // Calculate new horizontal position
      const newX = currentPos.x + velocity.x * delta;
      const newZ = currentPos.z + velocity.z * delta;

      // Calculate new altitude
      let newY = currentPos.y + velocity.y * delta;

      // Terrain following when not flying
      if (!isFlyingRef.current && getTerrainElevation) {
        const lngLat = xzToLngLat(newX, newZ);
        const terrainHeight = getTerrainElevation(lngLat[0], lngLat[1]);
        const minAltitude = terrainHeight + CONFIG.player.eyeHeight;

        // Smoothly follow terrain when walking
        if (newY < minAltitude + 0.5) {
          newY = minAltitude + (newY - minAltitude) * 0.3; // Smooth interpolation
        }
        // Clamp to minimum
        newY = Math.max(minAltitude, newY);
      } else {
        // Just clamp to eye height when no terrain data
        newY = Math.max(CONFIG.player.eyeHeight, newY);
      }

      // Clamp to max altitude
      newY = Math.min(CONFIG.player.maxAltitude, newY);

      // Apply kinematic movement
      rb.setNextKinematicTranslation({ x: newX, y: newY, z: newZ });
    }

    // Sync camera position with rigid body
    const pos = rb.translation();
    camera.position.set(pos.x, pos.y, pos.z);

    // Report position change
    if (onPositionChange) {
      const geo = sceneToGeo(pos.x, pos.y, pos.z);
      onPositionChange({ lng: geo.lng, lat: geo.lat, alt: geo.altitude });
    }
  });

  return (
    <RigidBody
      ref={rigidBodyRef}
      type="kinematicPosition"
      position={initialPos.current}
      colliders={false}
      enabledRotations={[false, false, false]}
    >
      <CapsuleCollider
        args={[CONFIG.player.height / 2 - CONFIG.player.collisionRadius, CONFIG.player.collisionRadius]}
      />
    </RigidBody>
  );
}

export default Player;
