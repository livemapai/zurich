# Game Loop Reference

## requestAnimationFrame Pattern

```typescript
function useGameLoop(
  callback: (deltaTime: number) => void,
  isActive: boolean = true
) {
  const callbackRef = useRef(callback);
  const frameRef = useRef<number>();
  const lastTimeRef = useRef<number>();

  // Keep callback ref updated
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!isActive) return;

    const loop = (time: number) => {
      if (lastTimeRef.current !== undefined) {
        // Delta time in SECONDS
        const deltaTime = (time - lastTimeRef.current) / 1000;

        // Clamp to avoid huge jumps (e.g., tab was inactive)
        const clampedDelta = Math.min(deltaTime, 0.1);

        callbackRef.current(clampedDelta);
      }

      lastTimeRef.current = time;
      frameRef.current = requestAnimationFrame(loop);
    };

    frameRef.current = requestAnimationFrame(loop);

    return () => {
      if (frameRef.current !== undefined) {
        cancelAnimationFrame(frameRef.current);
      }
    };
  }, [isActive]);
}
```

## Fixed Timestep (Physics)

For deterministic physics, use fixed timestep with interpolation:

```typescript
const FIXED_STEP = 1 / 60; // 60 updates per second
let accumulator = 0;

function fixedUpdate(deltaTime: number) {
  accumulator += deltaTime;

  while (accumulator >= FIXED_STEP) {
    // Physics update at fixed rate
    physicsStep(FIXED_STEP);
    accumulator -= FIXED_STEP;
  }

  // Interpolation factor for rendering
  const alpha = accumulator / FIXED_STEP;
  render(alpha);
}
```

## Frame Timing Best Practices

1. **Always use deltaTime**: Never assume 60fps
2. **Clamp deltaTime**: Avoid huge jumps when tab resumes
3. **Use ref for callback**: Avoid recreating RAF each render
4. **Clean up on unmount**: Cancel pending frame
5. **Check isActive flag**: Allow pausing the loop
