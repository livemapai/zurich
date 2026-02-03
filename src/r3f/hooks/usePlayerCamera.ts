/**
 * usePlayerCamera - Camera Control Hook
 *
 * Integrates mouse look with Three.js camera control.
 * Updates camera rotation based on mouse movement when pointer is locked.
 */

import { useRef, useCallback, useEffect } from 'react';
import { useThree, useFrame } from '@react-three/fiber';
import { CONFIG } from '@/lib/config';

interface UsePlayerCameraOptions {
  enabled?: boolean;
  sensitivity?: number;
  pitchMin?: number;
  pitchMax?: number;
}

export function usePlayerCamera(options: UsePlayerCameraOptions = {}) {
  const {
    enabled = true,
    sensitivity = CONFIG.mouse.sensitivityX,
    pitchMin = CONFIG.camera.pitchMin,
    pitchMax = CONFIG.camera.pitchMax,
  } = options;

  const { camera, gl } = useThree();

  const bearingRef = useRef(0);
  const pitchRef = useRef(0);
  const isLockedRef = useRef(false);
  const mouseDeltaRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const handleLockChange = () => {
      isLockedRef.current = document.pointerLockElement === gl.domElement;
    };
    document.addEventListener('pointerlockchange', handleLockChange);
    return () => document.removeEventListener('pointerlockchange', handleLockChange);
  }, [gl.domElement]);

  useEffect(() => {
    if (!enabled) return;
    const handleMouseMove = (e: MouseEvent) => {
      if (!isLockedRef.current) return;
      mouseDeltaRef.current.x += e.movementX;
      mouseDeltaRef.current.y += e.movementY;
    };
    document.addEventListener('mousemove', handleMouseMove);
    return () => document.removeEventListener('mousemove', handleMouseMove);
  }, [enabled]);

  // Initialize camera rotation on mount to look at horizon (pitch = 0)
  // This runs once to set up the camera before any mouse input is received.
  // Without this, the camera keeps Three.js default rotation until mouse moves.
  useEffect(() => {
    camera.rotation.order = 'YXZ';
    camera.rotation.y = -(bearingRef.current * Math.PI) / 180;
    camera.rotation.x = -(pitchRef.current * Math.PI) / 180;
  }, [camera]);

  useFrame(() => {
    if (!enabled) return;

    // Mouse look requires pointer lock - clear deltas and skip if not locked
    if (!isLockedRef.current) {
      mouseDeltaRef.current.x = 0;
      mouseDeltaRef.current.y = 0;
      return;
    }

    const delta = mouseDeltaRef.current;
    if (delta.x === 0 && delta.y === 0) return;

    bearingRef.current += delta.x * sensitivity;
    pitchRef.current += delta.y * sensitivity * (CONFIG.mouse.invertY ? -1 : 1);

    bearingRef.current = ((bearingRef.current % 360) + 360) % 360;
    pitchRef.current = Math.max(pitchMin, Math.min(pitchMax, pitchRef.current));

    const yaw = -(bearingRef.current * Math.PI) / 180;
    const pitch = -(pitchRef.current * Math.PI) / 180;

    camera.rotation.order = 'YXZ';
    camera.rotation.y = yaw;
    camera.rotation.x = pitch;

    mouseDeltaRef.current.x = 0;
    mouseDeltaRef.current.y = 0;
  });

  const requestLock = useCallback(() => {
    gl.domElement.requestPointerLock();
  }, [gl.domElement]);

  return {
    bearingRef,
    pitchRef,
    requestLock,
    isLockedRef,
  };
}

export default usePlayerCamera;
