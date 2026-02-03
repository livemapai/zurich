/**
 * useMouseLook Hook
 *
 * Manages pointer lock and accumulates mouse movement for camera control
 * Supports unadjustedMovement for raw mouse input (no OS acceleration)
 */

import { useState, useEffect, useCallback, useRef, type RefObject } from 'react';
import { MOUSE_SENSITIVITY } from '@/types';

export interface MouseLookState {
  isLocked: boolean;
  consumeDelta: () => { x: number; y: number };
  requestLock: () => void;
  exitLock: () => void;
}

export function useMouseLook(
  targetRef: RefObject<HTMLElement | null>,
  sensitivity = MOUSE_SENSITIVITY
): MouseLookState {
  const [isLocked, setIsLocked] = useState(false);
  const deltaRef = useRef({ x: 0, y: 0 });

  // Handle pointer lock state changes
  useEffect(() => {
    const handleLockChange = () => {
      const isNowLocked = document.pointerLockElement === targetRef.current;
      setIsLocked(isNowLocked);

      // Reset delta when lock state changes
      if (!isNowLocked) {
        deltaRef.current = { x: 0, y: 0 };
      }
    };

    const handleLockError = () => {
      console.warn('Pointer lock request failed');
      setIsLocked(false);
    };

    document.addEventListener('pointerlockchange', handleLockChange);
    document.addEventListener('pointerlockerror', handleLockError);

    return () => {
      document.removeEventListener('pointerlockchange', handleLockChange);
      document.removeEventListener('pointerlockerror', handleLockError);
    };
  }, [targetRef]);

  // Handle mouse movement while locked
  useEffect(() => {
    const handleMouseMove = (event: MouseEvent) => {
      if (document.pointerLockElement !== targetRef.current) return;

      // Accumulate movement scaled by sensitivity
      deltaRef.current.x += event.movementX * sensitivity.x;
      deltaRef.current.y += event.movementY * sensitivity.y;
    };

    document.addEventListener('mousemove', handleMouseMove);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
    };
  }, [targetRef, sensitivity.x, sensitivity.y]);

  // Consume accumulated delta (resets to zero)
  const consumeDelta = useCallback(() => {
    const delta = { ...deltaRef.current };
    deltaRef.current = { x: 0, y: 0 };
    return delta;
  }, []);

  // Request pointer lock with unadjustedMovement support
  const requestLock = useCallback(async () => {
    const target = targetRef.current;
    if (target && document.pointerLockElement !== target) {
      try {
        // Try with raw input first (better for games, no OS acceleration)
        await target.requestPointerLock({ unadjustedMovement: true });
      } catch {
        // Fallback for browsers without unadjustedMovement support
        try {
          await target.requestPointerLock();
        } catch (e) {
          console.warn('Pointer lock request failed:', e);
        }
      }
    }
  }, [targetRef]);

  // Exit pointer lock
  const exitLock = useCallback(() => {
    if (document.pointerLockElement) {
      document.exitPointerLock();
    }
  }, []);

  return { isLocked, consumeDelta, requestLock, exitLock };
}
