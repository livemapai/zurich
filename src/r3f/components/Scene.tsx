/**
 * Scene - Main R3F Scene Wrapper
 *
 * Provides the core scene setup including:
 * - Suspense boundary for async loading
 * - Color management
 * - Scene-level configuration
 *
 * Children are rendered inside a Suspense boundary to handle
 * async geometry/texture loading gracefully.
 */

import { Suspense, type ReactNode } from 'react';
import { Lighting } from './Lighting';

interface SceneProps {
  /** Child components to render in the scene */
  children: ReactNode;
  /** Whether to show the loading fallback */
  showFallback?: boolean;
}

/**
 * Fallback shown while scene content loads.
 * A simple indicator that something is loading.
 */
function LoadingFallback() {
  return (
    <mesh position={[0, 1, 0]}>
      <boxGeometry args={[1, 1, 1]} />
      <meshBasicMaterial color="#4a9eff" wireframe />
    </mesh>
  );
}

/**
 * Scene wrapper component.
 *
 * Wraps children in a Suspense boundary and provides
 * standard lighting matching the deck.gl viewer.
 */
export function Scene({ children, showFallback = true }: SceneProps) {
  return (
    <Suspense fallback={showFallback ? <LoadingFallback /> : null}>
      {/* Standard lighting setup */}
      <Lighting />

      {/* Scene content */}
      {children}
    </Suspense>
  );
}

export default Scene;
