/**
 * AI Styles Viewer Types
 *
 * Shared type definitions for the styles viewer components.
 */

/** Generator type for AI tiles */
export type GeneratorType = 'gemini' | 'controlnet';

/** Metadata for a single AI-generated tile style */
export interface StyleInfo {
  name: string;
  displayName: string;
  description: string;
  colors: string[];
  tiles: number;
  totalTiles: number;
  bounds: [number, number, number, number]; // [west, south, east, north]
  zoom: number;
  generatedAt: string | null;
  /** Generator used: "gemini" for ai-*, "controlnet" for sd-* */
  generator: GeneratorType;
}

/** Satellite imagery configuration */
export interface SatelliteConfig {
  name: string;
  displayName: string;
  description: string;
  colors: string[];
  url: string;
  tileSize: number;
}

/** Complete styles manifest from ai-styles.json */
export interface StylesManifest {
  styles: StyleInfo[];
  satellite: SatelliteConfig;
  generatedAt: string;
  defaultBounds: [number, number, number, number];
  defaultZoom: number;
}

/** Props for StylePanel component */
export interface StylePanelProps {
  manifest: StylesManifest | null;
  selectedStyle: string;
  onStyleSelect: (styleName: string) => void;
  isLoading: boolean;
}

/** Props for StylesViewer component */
export interface StylesViewerProps {
  className?: string;
}
