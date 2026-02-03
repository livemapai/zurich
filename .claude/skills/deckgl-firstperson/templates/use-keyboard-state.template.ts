/**
 * useKeyboardState Hook
 *
 * Tracks WASD + modifier key state for movement controls
 */

import { useState, useEffect, useCallback } from 'react';
import type { KeyboardState } from '@/types';

const INITIAL_STATE: KeyboardState = {
  forward: false,
  backward: false,
  left: false,
  right: false,
  up: false,      // Q key - fly up
  down: false,    // E key - fly down
  run: false,
  jump: false,
};

const KEY_MAP: Record<string, keyof KeyboardState> = {
  KeyW: 'forward',
  KeyS: 'backward',
  KeyA: 'left',
  KeyD: 'right',
  KeyQ: 'up',       // Fly up
  KeyE: 'down',     // Fly down
  ShiftLeft: 'run',
  ShiftRight: 'run',
  Space: 'jump',
  // Arrow keys as alternatives
  ArrowUp: 'forward',
  ArrowDown: 'backward',
  ArrowLeft: 'left',
  ArrowRight: 'right',
};

export function useKeyboardState(): KeyboardState {
  const [state, setState] = useState<KeyboardState>(INITIAL_STATE);

  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    const key = KEY_MAP[event.code];
    if (key) {
      event.preventDefault();
      setState((prev) => ({ ...prev, [key]: true }));
    }
  }, []);

  const handleKeyUp = useCallback((event: KeyboardEvent) => {
    const key = KEY_MAP[event.code];
    if (key) {
      setState((prev) => ({ ...prev, [key]: false }));
    }
  }, []);

  const handleBlur = useCallback(() => {
    // Reset all keys when window loses focus
    setState(INITIAL_STATE);
  }, []);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', handleBlur);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('blur', handleBlur);
    };
  }, [handleKeyDown, handleKeyUp, handleBlur]);

  return state;
}
