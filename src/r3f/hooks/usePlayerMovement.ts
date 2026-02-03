/**
 * usePlayerMovement - Keyboard Movement Hook
 *
 * Handles WASD movement relative to camera bearing.
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
  enabled?: boolean;
  walkSpeed?: number;
  runSpeed?: number;
  flySpeed?: number;
}

export function usePlayerMovement(options: UsePlayerMovementOptions) {
  const {
    bearingRef,
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

  // Calculate velocity each frame
  useFrame(() => {
    if (!enabled) return;

    const input = keysRef.current;
    const speed = input.run ? runSpeed : walkSpeed;
    const bearing = bearingRef.current;
    const bearingRad = (bearing * Math.PI) / 180;

    const forwardX = Math.sin(bearingRad);
    const forwardZ = -Math.cos(bearingRad);
    const rightX = Math.cos(bearingRad);
    const rightZ = Math.sin(bearingRad);

    let vx = 0, vz = 0, vy = 0;

    if (input.forward) { vx += forwardX; vz += forwardZ; }
    if (input.backward) { vx -= forwardX; vz -= forwardZ; }
    if (input.left) { vx -= rightX; vz -= rightZ; }
    if (input.right) { vx += rightX; vz += rightZ; }

    // Normalize horizontal
    const hLen = Math.sqrt(vx * vx + vz * vz);
    if (hLen > 0) {
      vx = (vx / hLen) * speed;
      vz = (vz / hLen) * speed;
    }

    if (input.up) vy = flySpeed;
    if (input.down) vy = -flySpeed;

    velocityRef.current.set(vx, vy, vz);
  });

  return { velocityRef, keysRef };
}

export default usePlayerMovement;
