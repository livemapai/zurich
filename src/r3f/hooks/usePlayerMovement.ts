/**
 * usePlayerMovement - Keyboard Movement Hook
 *
 * Handles WASD movement with look-direction flying.
 * Forward/backward moves in the 3D direction the camera faces (including pitch).
 * Strafe (A/D) stays horizontal for intuitive FPS controls.
 * Q/E provides pure vertical movement for hover control.
 */

import { useRef, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { CONFIG } from '@/lib/config';

interface MovementInput {
  forward: boolean;
  backward: boolean;
  left: boolean;
  right: boolean;
  up: boolean;
  down: boolean;
  run: boolean;
}

interface UsePlayerMovementOptions {
  bearingRef: React.RefObject<number>;
  camera?: THREE.Camera;
  enabled?: boolean;
  walkSpeed?: number;
  runSpeed?: number;
  flySpeed?: number;
}

// Reusable vectors to avoid allocation in render loop
const _forward = new THREE.Vector3();
const _right = new THREE.Vector3();
const _velocity = new THREE.Vector3();

export function usePlayerMovement(options: UsePlayerMovementOptions) {
  const {
    bearingRef,
    camera,
    enabled = true,
    walkSpeed = CONFIG.movement.walk,
    runSpeed = CONFIG.movement.run,
    flySpeed = CONFIG.movement.walk,
  } = options;

  const velocityRef = useRef(new THREE.Vector3());
  const keysRef = useRef<MovementInput>({
    forward: false,
    backward: false,
    left: false,
    right: false,
    up: false,
    down: false,
    run: false,
  });

  // Keyboard event handlers
  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.code) {
        case 'KeyW': keysRef.current.forward = true; break;
        case 'KeyS': keysRef.current.backward = true; break;
        case 'KeyA': keysRef.current.left = true; break;
        case 'KeyD': keysRef.current.right = true; break;
        case 'KeyQ': keysRef.current.up = true; break;
        case 'KeyE': keysRef.current.down = true; break;
        case 'ShiftLeft':
        case 'ShiftRight': keysRef.current.run = true; break;
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      switch (e.code) {
        case 'KeyW': keysRef.current.forward = false; break;
        case 'KeyS': keysRef.current.backward = false; break;
        case 'KeyA': keysRef.current.left = false; break;
        case 'KeyD': keysRef.current.right = false; break;
        case 'KeyQ': keysRef.current.up = false; break;
        case 'KeyE': keysRef.current.down = false; break;
        case 'ShiftLeft':
        case 'ShiftRight': keysRef.current.run = false; break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [enabled]);

  // Calculate velocity each frame using look-direction flying
  useFrame(() => {
    if (!enabled) return;

    const input = keysRef.current;
    const speed = input.run ? runSpeed : walkSpeed;
    const bearing = bearingRef.current;
    const bearingRad = (bearing * Math.PI) / 180;

    // Get 3D forward direction from camera (includes pitch for look-direction flying)
    if (camera) {
      camera.getWorldDirection(_forward);
    } else {
      // Fallback: horizontal only if no camera reference
      _forward.set(Math.sin(bearingRad), 0, -Math.cos(bearingRad));
    }

    // Right vector stays horizontal for intuitive strafing
    // (perpendicular to bearing in XZ plane, ignoring pitch)
    _right.set(
      Math.sin(bearingRad + Math.PI / 2),
      0,
      -Math.cos(bearingRad + Math.PI / 2)
    );

    // Build velocity from input
    _velocity.set(0, 0, 0);

    // Forward/backward uses 3D look direction (fly up when looking up)
    if (input.forward) _velocity.add(_forward);
    if (input.backward) _velocity.sub(_forward);

    // Strafe stays horizontal
    if (input.left) _velocity.sub(_right);
    if (input.right) _velocity.add(_right);

    // Normalize diagonal movement and apply speed
    if (_velocity.lengthSq() > 0) {
      _velocity.normalize().multiplyScalar(speed);
    }

    // Q/E for pure vertical control (hover mode)
    if (input.up) _velocity.y += flySpeed;
    if (input.down) _velocity.y -= flySpeed;

    velocityRef.current.copy(_velocity);
  });

  return { velocityRef, keysRef };
}

export default usePlayerMovement;
