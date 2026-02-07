/**
 * Types for VectorViewer component
 */

export interface VectorViewerProps {
  className?: string;
}

export interface LayerVisibility {
  water: boolean;
  buildings: boolean;
  building_shadows: boolean;
  roofs: boolean;
  transportation: boolean;
  railway: boolean;
  trees: boolean;
  poi: boolean;
  labels: boolean;
}

export interface TileVariant {
  id: 'clean' | 'wobble' | 'tilt' | 'wobble-tilt';
  name: string;
  description: string;
  pmtilesUrl: string;
}

export interface StylePreset {
  id: 'sketchy' | 'technical' | 'artistic' | 'minimal' | 'zigzag';
  name: string;
  description: string;
  icon: string;
  styleUrl: string;
}

export interface FeatureProperties {
  id?: string;
  name?: string;
  height?: number;
  elevation?: number;
  art?: string;
  class?: string;
  subclass?: string;
  material?: string;
  slope_angle?: number;
  [key: string]: unknown;
}

export interface ClickedFeature {
  layer: string;
  properties: FeatureProperties;
  coordinates: [number, number];
}
