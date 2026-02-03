/**
 * useMouseLook - Pointer lock and mouse movement tracking
 *
 * Manages pointer lock API and accumulates mouse movement deltas
 * for smooth camera rotation in the game loop.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { MouseDelta } from '@/types';

interface UseMouseLookOptions {
  /** Target element for pointer lock */
  targetRef: React.RefObject<HTMLElement | null>;
  /** Enable/disable mouse look */
  enabled?: boolean;
}

interface UseMouseLookResult {
  /** Whether pointer is currently locked */
  isLocked: boolean;
  /** Request pointer lock (call on click) */
  requestLock: () => void;
  /** Release pointer lock */
  releaseLock: () => void;
  /** Consume and reset accumulated mouse delta */
  consumeDelta: () => MouseDelta;
}

/**
 * Hook to manage pointer lock and mouse movement for first-person camera
 */
export function useMouseLook(options: UseMouseLookOptions): UseMouseLookResult {
  const { targetRef, enabled = true } = options;

  const [isLocked, setIsLocked] = useState(false);

  // Use ref to avoid stale closure in event handlers
  const isLockedRef = useRef(isLocked);
  isLockedRef.current = isLocked;

  // Accumulate mouse movement between frames
  const deltaRef = useRef<MouseDelta>({ x: 0, y: 0 });

  /**
   * Request pointer lock on the target element
   */
  const requestLock = useCallback(() => {
    if (!enabled || !targetRef.current) {
      console.warn('Cannot request pointer lock: enabled=', enabled, 'target=', targetRef.current);
      return;
    }

    // Request pointer lock
    const element = targetRef.current;
    if (element.requestPointerLock) {
      element.requestPointerLock();
    } else {
      console.warn('requestPointerLock not supported');
    }
  }, [enabled, targetRef]);

  /**
   * Release pointer lock
   */
  const releaseLock = useCallback(() => {
    if (document.pointerLockElement) {
      document.exitPointerLock?.();
    }
  }, []);

  /**
   * Consume accumulated delta and reset it
   */
  const consumeDelta = useCallback((): MouseDelta => {
    const delta = { ...deltaRef.current };
    deltaRef.current = { x: 0, y: 0 };
    return delta;
  }, []);

  // Main effect for pointer lock events
  useEffect(() => {
    if (!enabled) {
      releaseLock();
      return;
    }

    /**
     * Handle pointer lock state changes
     */
    const handleLockChange = () => {
      const pointerLockElement = document.pointerLockElement;
      const target = targetRef.current;
      const locked = pointerLockElement === target;

      // Debug logging
      if (pointerLockElement !== null || target !== null) {
        console.log('Pointer lock change:', {
          locked,
          pointerLockElement: pointerLockElement?.tagName,
          target: target?.tagName,
          match: pointerLockElement === target,
        });
      }

      setIsLocked(locked);

      // Reset delta when lock state changes
      if (!locked) {
        deltaRef.current = { x: 0, y: 0 };
      }
    };

    /**
     * Handle pointer lock errors
     */
    const handleLockError = (event: Event) => {
      console.warn('Pointer lock error:', event);
      setIsLocked(false);
    };

    /**
     * Handle mouse movement while locked
     * Uses ref to always check current lock state (avoids stale closure)
     */
    const handleMouseMove = (event: MouseEvent) => {
      // Use ref to get current lock state (avoids stale closure)
      if (!isLockedRef.current) return;

      // Accumulate movement delta
      deltaRef.current.x += event.movementX;
      deltaRef.current.y += event.movementY;
    };

    document.addEventListener('pointerlockchange', handleLockChange);
    document.addEventListener('pointerlockerror', handleLockError);
    document.addEventListener('mousemove', handleMouseMove);

    // Check initial state (in case we're already locked)
    handleLockChange();

    return () => {
      document.removeEventListener('pointerlockchange', handleLockChange);
      document.removeEventListener('pointerlockerror', handleLockError);
      document.removeEventListener('mousemove', handleMouseMove);
    };
  }, [enabled, releaseLock, targetRef]);

  // Release lock when disabled or unmounted
  useEffect(() => {
    if (!enabled) {
      releaseLock();
    }

    return () => {
      releaseLock();
    };
  }, [enabled, releaseLock]);

  // Handle Escape key to release lock (browser handles this, but we sync state)
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && isLockedRef.current) {
        // Browser will release lock, we just ensure state sync
        setIsLocked(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return {
    isLocked,
    requestLock,
    releaseLock,
    consumeDelta,
  };
}
