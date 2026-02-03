// ============================================================================
// Coordinate Types
// ============================================================================

/** WGS84 coordinates [longitude, latitude] in degrees */
export type LngLat = [lng: number, lat: number];

/** Position in meters relative to origin */
export type MetersPosition = [x: number, y: number];

/** Swiss LV95 coordinates [Easting, Northing] in meters */
export type LV95Coordinates = [E: number, N: number];

/** 3D position with altitude */
export type Position3D = [lng: number, lat: number, altitude: number];

// ============================================================================
// Zurich Constants
// ============================================================================

/** Zurich city center coordinates - positioned south of building cluster for better initial view */
export const ZURICH_CENTER: LngLat = [8.5437, 47.3739];

/** Zurich base ground elevation in meters above sea level */
export const ZURICH_BASE_ELEVATION = 408;

/** Zurich bounding box */
export interface ZurichBounds {
  minLng: number;
  maxLng: number;
  minLat: number;
  maxLat: number;
}

export const ZURICH_BOUNDS: ZurichBounds = {
  minLng: 8.48,
  maxLng: 8.60,
  minLat: 47.34,
  maxLat: 47.42,
};

/** Meters per degree at Zurich latitude (~47°N) */
export const METERS_PER_DEGREE = {
  lng: 75500, // 1° longitude ≈ 75,500m at 47°N
  lat: 111320, // 1° latitude ≈ 111,320m
} as const;

// ============================================================================
// View State Types
// ============================================================================

/** First-person view state for deck.gl */
export interface FirstPersonViewState {
  /** Geographic longitude anchor (WGS84 degrees) */
  longitude: number;
  /** Geographic latitude anchor (WGS84 degrees) */
  latitude: number;
  /** Meter offset from geographic anchor [east, north, up] */
  position: [number, number, number];
  /** Compass bearing: 0 = North, 90 = East, 180 = South, 270 = West */
  bearing: number;
  /** Vertical look angle: -90 = straight up, 0 = horizon, +90 = straight down */
  pitch: number;
  /** Vertical field of view in degrees (optional, for view config) */
  fov?: number;
  /** Near clipping plane in meters (optional, for view config) */
  near?: number;
  /** Far clipping plane in meters (optional, for view config) */
  far?: number;
}

/** Minimap view state */
export interface MapViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  bearing: number;
  pitch: number;
}

// ============================================================================
// Player Types
// ============================================================================

/** Player physical dimensions */
export interface PlayerDimensions {
  /** Height of camera/eyes above ground in meters */
  eyeHeight: number;
  /** Collision radius in meters */
  collisionRadius: number;
}

/** Movement speed configuration */
export interface MovementSpeeds {
  /** Walking speed in meters/second */
  walk: number;
  /** Running speed in meters/second (with shift) */
  run: number;
}

/** Keyboard input state */
export interface KeyboardState {
  forward: boolean;
  backward: boolean;
  left: boolean;
  right: boolean;
  run: boolean;
  jump: boolean;
}

/** Player velocity in meters/second */
export interface Velocity {
  x: number; // East/West
  y: number; // North/South
  z: number; // Up/Down (vertical)
}

// ============================================================================
// Game State
// ============================================================================

/** Complete game state */
export interface GameState {
  /** Current view state */
  viewState: FirstPersonViewState;
  /** Current velocity */
  velocity: Velocity;
  /** Whether pointer lock is active */
  isPointerLocked: boolean;
  /** Whether game is paused */
  isPaused: boolean;
  /** Time of last frame in ms */
  lastFrameTime: number;
}

// ============================================================================
// GeoJSON Types for Buildings
// ============================================================================

/** Properties for a building feature */
export interface BuildingProperties {
  /** Unique building identifier */
  id: string;
  /** Building height in meters */
  height: number;
  /** Ground elevation in meters (optional) */
  elevation?: number;
  /** Building name (optional) */
  name?: string;
  /** Building type/category (optional) */
  type?: string;
}

/** A single building polygon coordinate ring */
export type PolygonRing = LngLat[];

/** GeoJSON Polygon geometry */
export interface PolygonGeometry {
  type: 'Polygon';
  coordinates: PolygonRing[];
}

/** GeoJSON MultiPolygon geometry */
export interface MultiPolygonGeometry {
  type: 'MultiPolygon';
  coordinates: PolygonRing[][];
}

/** Building geometry can be Polygon or MultiPolygon */
export type BuildingGeometry = PolygonGeometry | MultiPolygonGeometry;

/** GeoJSON Feature for a building */
export interface BuildingFeature {
  type: 'Feature';
  id?: string | number;
  properties: BuildingProperties;
  geometry: BuildingGeometry;
}

/** GeoJSON FeatureCollection for buildings */
export interface BuildingCollection {
  type: 'FeatureCollection';
  features: BuildingFeature[];
}

// ============================================================================
// Collision Detection Types
// ============================================================================

/** Axis-aligned bounding box */
export interface AABB {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

/** Building collision data for spatial index */
export interface BuildingCollider extends AABB {
  /** Reference to original building */
  buildingId: string;
  /** Building polygon for precise collision */
  polygon: LngLat[];
  /** Building height for vertical collision */
  height: number;
}

/** Result of a collision check */
export interface CollisionResult {
  /** Whether collision occurred */
  collides: boolean;
  /** Adjusted position after wall sliding */
  position: LngLat;
  /** Normal of collision surface (for wall sliding) */
  normal?: MetersPosition;
}

/** RBush bounding box with feature reference */
export interface CollisionBBox {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
  /** Reference to the building feature */
  feature: BuildingFeature;
}

/** Terrain heightmap data structure */
export interface TerrainData {
  /** Width of heightmap in pixels */
  width: number;
  /** Height of heightmap in pixels */
  height: number;
  /** Raw elevation data (row-major order, meters) */
  data: Float32Array;
  /** Bounds of the terrain */
  bounds: {
    minLng: number;
    maxLng: number;
    minLat: number;
    maxLat: number;
    minElev: number;
    maxElev: number;
  };
}

/** Result of terrain elevation query */
export interface TerrainQuery {
  /** Elevation at queried point in meters */
  elevation: number;
  /** Whether the query point was within terrain bounds */
  inBounds: boolean;
}

// ============================================================================
// Terrain Types
// ============================================================================

/** Terrain elevation data point */
export interface TerrainPoint {
  position: LngLat;
  elevation: number;
}

/** Terrain grid for interpolation */
export interface TerrainGrid {
  /** Grid origin (southwest corner) */
  origin: LngLat;
  /** Grid cell size in degrees */
  cellSize: number;
  /** Number of cells in X direction */
  width: number;
  /** Number of cells in Y direction */
  height: number;
  /** Elevation data (row-major order) */
  elevations: Float32Array;
}

/** Terrain sampling result */
export interface TerrainSample {
  /** Elevation at sampled point */
  elevation: number;
  /** Surface normal (for slope detection) */
  normal?: [number, number, number];
}

// ============================================================================
// Layer Configuration Types
// ============================================================================

/** Base layer configuration */
export interface LayerConfig {
  id: string;
  visible: boolean;
  opacity: number;
}

/** Buildings layer configuration */
export interface BuildingsLayerConfig extends LayerConfig {
  /** Whether to extrude buildings */
  extruded: boolean;
  /** Whether to show wireframe */
  wireframe: boolean;
  /** Fill color [R, G, B, A] */
  fillColor: [number, number, number, number];
  /** Line color for wireframe */
  lineColor: [number, number, number, number];
}

/** Terrain layer configuration */
export interface TerrainLayerConfig extends LayerConfig {
  /** Terrain mesh resolution */
  meshResolution: number;
  /** Vertical exaggeration factor */
  elevationScale: number;
}

/** Complete layer stack configuration */
export interface LayerStackConfig {
  buildings: BuildingsLayerConfig;
  terrain: TerrainLayerConfig;
}

// ============================================================================
// Utility Types
// ============================================================================

/** Mouse movement delta */
export interface MouseDelta {
  x: number;
  y: number;
}

/** Generic 2D vector */
export interface Vector2 {
  x: number;
  y: number;
}

/** Generic 3D vector */
export interface Vector3 {
  x: number;
  y: number;
  z: number;
}

/** Time delta for animation */
export interface FrameTiming {
  /** Time since last frame in seconds */
  deltaTime: number;
  /** Total elapsed time in seconds */
  elapsedTime: number;
}
