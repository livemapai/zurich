/**
 * PipelineViewer Types
 *
 * TypeScript interfaces for the MapLibre vector tile pipeline
 * educational visualization.
 */

/** Stage identifiers for the 6 pipeline stages */
export type StageId =
  | 'data-sources'
  | 'tiling'
  | 'encoding'
  | 'schema'
  | 'style'
  | 'render';

/** Individual stage configuration */
export interface StageConfig {
  id: StageId;
  number: number;
  title: string;
  shortTitle: string;
  description: string;
  insight: string;
}

/** Runtime state for each stage */
export interface StageState {
  id: StageId;
  visited: boolean;
  data: Record<string, unknown>;
}

/** Overall pipeline state */
export interface PipelineState {
  currentStage: number;
  stages: StageState[];
}

/** Props for stage components */
export interface StageProps {
  isActive: boolean;
  onDataChange?: (data: Record<string, unknown>) => void;
}

/** Data source types for Stage 1 */
export type DataSourceType = 'osm' | 'geojson' | 'shapefile' | 'postgis';

export interface DataSource {
  id: DataSourceType;
  name: string;
  description: string;
  format: string;
  sampleCode: string;
}

/** Tile coordinates for Stage 2 */
export interface TileCoordinate {
  z: number;
  x: number;
  y: number;
}

/** MVT geometry commands for Stage 3 */
export type GeometryCommandType = 'MoveTo' | 'LineTo' | 'ClosePath';

export interface GeometryCommand {
  type: GeometryCommandType;
  x?: number;
  y?: number;
  dx?: number;
  dy?: number;
}

/** Layer schema for Stage 4 */
export interface LayerSchema {
  id: string;
  geometryType: 'Point' | 'LineString' | 'Polygon';
  fields: Record<string, 'String' | 'Number' | 'Boolean'>;
  description: string;
}

/** Style layer for Stage 5 */
export interface StyleLayer {
  id: string;
  type: 'fill' | 'line' | 'symbol' | 'circle' | 'fill-extrusion';
  sourceLayer: string;
  paint: Record<string, unknown>;
  layout?: Record<string, unknown>;
  filter?: unknown[];
}

/** Render stats for Stage 6 */
export interface RenderStats {
  drawCalls: number;
  triangles: number;
  frameTime: number;
  tilesLoaded: number;
}

/** Navigation direction */
export type NavigationDirection = 'next' | 'prev';

/** Code panel language types */
export type CodeLanguage = 'json' | 'typescript' | 'protobuf';
