# Pointer Lock API Reference

## Basic Usage

```typescript
// Request pointer lock (must be from user gesture)
element.requestPointerLock();

// Check if locked
document.pointerLockElement === element;

// Exit pointer lock
document.exitPointerLock();
```

## Modern Promise-based API with unadjustedMovement

Modern browsers support:
- `requestPointerLock()` returns a Promise
- `unadjustedMovement` option for raw mouse input (no OS acceleration)

```typescript
// Try with raw input first (better for games)
try {
  await element.requestPointerLock({ unadjustedMovement: true });
} catch {
  // Fallback for browsers without unadjustedMovement support
  await element.requestPointerLock();
}
```

## Mouse Movement While Locked

```typescript
function handleMouseMove(event: MouseEvent) {
  if (document.pointerLockElement !== targetElement) return;

  // movementX/Y give delta since last event (in pixels)
  const deltaX = event.movementX;
  const deltaY = event.movementY;

  // Apply sensitivity
  const bearingDelta = deltaX * SENSITIVITY;
  const pitchDelta = deltaY * SENSITIVITY; // Positive deltaY = look down
}
```

## Complete Hook Implementation

```typescript
function useMouseLook(
  targetRef: RefObject<HTMLElement>,
  sensitivity: { x: number; y: number } = { x: 0.1, y: 0.1 }
) {
  const [isLocked, setIsLocked] = useState(false);
  const deltaRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const target = targetRef.current;
    if (!target) return;

    const handleLockChange = () => {
      setIsLocked(document.pointerLockElement === target);
    };

    const handleMouseMove = (e: MouseEvent) => {
      if (document.pointerLockElement !== target) return;

      deltaRef.current.x += e.movementX * sensitivity.x;
      deltaRef.current.y += e.movementY * sensitivity.y;
    };

    const handleClick = async () => {
      if (document.pointerLockElement !== target) {
        try {
          await target.requestPointerLock({ unadjustedMovement: true });
        } catch {
          await target.requestPointerLock();
        }
      }
    };

    document.addEventListener('pointerlockchange', handleLockChange);
    document.addEventListener('mousemove', handleMouseMove);
    target.addEventListener('click', handleClick);

    return () => {
      document.removeEventListener('pointerlockchange', handleLockChange);
      document.removeEventListener('mousemove', handleMouseMove);
      target.removeEventListener('click', handleClick);
    };
  }, [targetRef, sensitivity.x, sensitivity.y]);

  const consumeDelta = useCallback(() => {
    const delta = { ...deltaRef.current };
    deltaRef.current = { x: 0, y: 0 };
    return delta;
  }, []);

  return { isLocked, consumeDelta };
}
```

## Browser Compatibility

- Chrome: Full support (unadjustedMovement since Chrome 88)
- Firefox: Full support
- Safari: Full support (since 10.1)
- Edge: Full support

## Common Issues

1. **Must be in click handler**: Browser security requirement
2. **User can exit with Escape**: Always handle `pointerlockchange`
3. **movementX/Y can be fractional**: Don't round prematurely
4. **Safari may need webkit prefix**: Check `webkitRequestPointerLock`
5. **unadjustedMovement may throw**: Always wrap in try/catch
