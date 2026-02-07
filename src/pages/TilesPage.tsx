/**
 * TilesPage - Tile Gallery Page
 *
 * Displays generated tile images in a gallery grid for easy review.
 * Shows all tiles from the selected style with their coordinates.
 *
 * Route: /tiles
 */

import { TilesViewer } from '@/components/TilesViewer';
import '@/styles/tiles-page.css';

export function TilesPage() {
  return <TilesViewer />;
}

export default TilesPage;
