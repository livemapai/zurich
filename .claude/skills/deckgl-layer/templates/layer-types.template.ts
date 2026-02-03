/**
 * Type definitions for {LayerName}Layer
 */

export interface {LayerName}Properties {
  id: string;
  // Add feature-specific properties
}

export interface {LayerName}Feature {
  type: 'Feature';
  geometry: {
    type: '{GeometryType}'; // 'Polygon' | 'Point' | 'LineString'
    coordinates: {CoordinateType}; // number[][] | number[] | number[][][]
  };
  properties: {LayerName}Properties;
}

export interface {LayerName}LayerConfig {
  visible?: boolean;
  opacity?: number;
  pickable?: boolean;
}
