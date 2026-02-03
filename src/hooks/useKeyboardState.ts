/**
 * useKeyboardState - Track WASD + modifier key state
 *
 * Tracks keyboard input for movement controls.
 * Ignores input when focus is in text fields.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { KeyboardState } from '@/types';
import { createEmptyKeyboardState } from '@/systems';

interface UseKeyboardStateOptions {
  /** Enable/disable keyboard tracking */
  enabled?: boolean;
}

interface UseKeyboardStateResult {
  /** Current keyboard state (for React components) */
  keyboard: KeyboardState;
  /** Get current keyboard state (stable function for game loop) */
  getKeyboard: () => KeyboardState;
  /** Reset all keys to unpressed state */
  reset: () => void;
}

/**
 * Map key codes to keyboard state keys
 */
const KEY_MAP: Record<string, keyof KeyboardState> = {
  KeyW: 'forward',
  KeyS: 'backward',
  KeyA: 'left',
  KeyD: 'right',
  ArrowUp: 'forward',
  ArrowDown: 'backward',
  ArrowLeft: 'left',
  ArrowRight: 'right',
  ShiftLeft: 'run',
  ShiftRight: 'run',
  Space: 'jump',
};

/**
 * Check if the event target is an input field
 */
function isInputField(target: EventTarget | null): boolean {
  if (!target || !(target instanceof Element)) return false;

  return (
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement ||
    target.getAttribute('contenteditable') === 'true'
  );
}

/**
 * Hook to track keyboard state for movement controls
 */
export function useKeyboardState(
  options: UseKeyboardStateOptions = {}
): UseKeyboardStateResult {
  const { enabled = true } = options;

  const [keyboard, setKeyboard] = useState<KeyboardState>(createEmptyKeyboardState);

  // Use ref to track current state without causing re-renders on every key
  const keyboardRef = useRef<KeyboardState>(keyboard);

  const reset = useCallback(() => {
    const empty = createEmptyKeyboardState();
    keyboardRef.current = empty;
    setKeyboard(empty);
  }, []);

  // Stable getter function for game loop (avoids stale closures)
  const getKeyboard = useCallback(() => keyboardRef.current, []);

  useEffect(() => {
    if (!enabled) {
      reset();
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      // Ignore if typing in an input field
      if (isInputField(event.target)) {
        return;
      }

      const stateKey = KEY_MAP[event.code];
      if (!stateKey) return;

      // Prevent default for movement keys (but allow browser shortcuts)
      if (!event.metaKey && !event.ctrlKey) {
        event.preventDefault();
      }

      // Only update if state changed
      if (!keyboardRef.current[stateKey]) {
        keyboardRef.current = {
          ...keyboardRef.current,
          [stateKey]: true,
        };
        setKeyboard(keyboardRef.current);
      }
    };

    const handleKeyUp = (event: KeyboardEvent) => {
      const stateKey = KEY_MAP[event.code];
      if (!stateKey) return;

      // Only update if state changed
      if (keyboardRef.current[stateKey]) {
        keyboardRef.current = {
          ...keyboardRef.current,
          [stateKey]: false,
        };
        setKeyboard(keyboardRef.current);
      }
    };

    // Handle window blur (release all keys when window loses focus)
    const handleBlur = () => {
      reset();
    };

    // Handle visibility change (release all keys when tab becomes hidden)
    const handleVisibilityChange = () => {
      if (document.hidden) {
        reset();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', handleBlur);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('blur', handleBlur);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [enabled, reset]);

  return { keyboard, getKeyboard, reset };
}
