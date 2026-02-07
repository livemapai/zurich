/**
 * Tiles Viewer Types
 *
 * Type definitions for the tile gallery viewer.
 */

import type { StyleInfo, StylesManifest } from '@/components/StylesViewer/types';

export type { StyleInfo, StylesManifest };

/** Tile coordinate with path */
export interface TileInfo {
  x: number;
  y: number;
  z: number;
  path: string;
}

/** Props for TilesViewer component */
export interface TilesViewerProps {
  className?: string;
}
