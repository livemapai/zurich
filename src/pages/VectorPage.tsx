/**
 * VectorPage - Vector Tiles Viewer Page
 *
 * Displays Zurich vector tiles using PMTiles and MapLibre
 * with layer controls and feature inspection.
 *
 * Route: /vector
 */

import { VectorViewer } from '@/components/VectorViewer';
import '@/styles/vector-page.css';

export function VectorPage() {
  return <VectorViewer />;
}

export default VectorPage;
