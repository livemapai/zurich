// ============================================================================
// COORDINATE SYSTEM REFERENCE
// ============================================================================
/**
 * deck.gl FirstPersonView Coordinate System
 *
 * The FirstPersonView uses a hybrid geographic/meter coordinate system:
 *
 * GEOGRAPHIC ANCHOR (WGS84 degrees):
 *   - longitude: degrees east of prime meridian (e.g., 8.5437° for Zurich)
 *   - latitude: degrees north of equator (e.g., 47.3739° for Zurich)
 *
 * METER OFFSET from anchor:
 *   - position[0]: meters east of anchor (always 0 in this app - we update lng/lat directly)
 *   - position[1]: meters north of anchor (always 0 in this app - we update lng/lat directly)
 *   - position[2]: ABSOLUTE altitude in meters above sea level (NOT offset!)
 *
 * ALTITUDE SYSTEM:
 *   - Ground elevation at Zurich city center: ~408m above sea level
 *   - Eye height: 1.7m above ground
 *   - Standing altitude = ground elevation + eye height = ~409.7m
 *   - Flying allows altitude up to CONFIG.player.maxAltitude (1000m default)
 *   - Minimum altitude = terrain elevation + eye height (can't go below ground)
 *
 * MOVEMENT:
 *   - Horizontal: We update longitude/latitude directly (in degrees)
 *   - Vertical: We update position[2] (in meters, absolute altitude)
 *   - Conversion: 1° longitude ≈ 75,500m, 1° latitude ≈ 111,320m at 47°N
 *
 * BEARING (compass direction camera is facing):
 *   - 0° = North, 90° = East, 180° = South, 270° = West
 *
 * PITCH (vertical look angle):
 *   - 0° = horizon, negative = looking up, positive = looking down
 */

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

/**
 * Zurich base ground elevation for the coordinate system.
 * Zurich city center is approximately 408m above sea level (WGS84).
 * This aligns with Mapterhorn terrain tiles which use absolute elevation.
 * Camera altitude = base elevation + eye height (408 + 1.7 = 409.7m).
 */
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
	maxLng: 8.6,
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
	up: boolean; // Q key - fly up
	down: boolean; // E key - fly down
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
	type: "Polygon";
	coordinates: PolygonRing[];
}

/** GeoJSON MultiPolygon geometry */
export interface MultiPolygonGeometry {
	type: "MultiPolygon";
	coordinates: PolygonRing[][];
}

/** Building geometry can be Polygon or MultiPolygon */
export type BuildingGeometry = PolygonGeometry | MultiPolygonGeometry;

/** GeoJSON Feature for a building */
export interface BuildingFeature {
	type: "Feature";
	id?: string | number;
	properties: BuildingProperties;
	geometry: BuildingGeometry;
}

/** GeoJSON FeatureCollection for buildings */
export interface BuildingCollection {
	type: "FeatureCollection";
	features: BuildingFeature[];
}

// ============================================================================
// GeoJSON Types for Trees
// ============================================================================

/** Properties for a tree feature */
export interface TreeProperties {
	/** Unique tree identifier */
	id: string;
	/** Latin species name */
	species?: string;
	/** German species name */
	species_de?: string;
	/** Tree height in meters */
	height: number;
	/** Crown diameter in meters */
	crown_diameter: number;
	/** Trunk diameter in meters */
	trunk_diameter: number;
	/** Year planted (optional) */
	year_planted?: number;
	/** Ground elevation in meters (from terrain) */
	elevation?: number;
}

/** GeoJSON Point geometry */
export interface PointGeometry {
	type: "Point";
	coordinates: LngLat;
}

/** GeoJSON Feature for a tree */
export interface TreeFeature {
	type: "Feature";
	properties: TreeProperties;
	geometry: PointGeometry;
}

/** GeoJSON FeatureCollection for trees */
export interface TreeCollection {
	type: "FeatureCollection";
	features: TreeFeature[];
}

// ============================================================================
// GeoJSON Types for Lights
// ============================================================================

/** Properties for a light feature */
export interface LightProperties {
	/** Unique light identifier */
	id: string;
	/** Light type (street, path, decorative, etc.) */
	type?: string;
	/** Pole height in meters (default: 6m) */
	height: number;
	/** Power consumption in watts (optional) */
	power?: number | null;
	/** Lamp fixture type (optional) */
	lamp_type?: string | null;
	/** Ground elevation in meters (from terrain) */
	elevation?: number;
}

/** GeoJSON Feature for a light */
export interface LightFeature {
	type: "Feature";
	properties: LightProperties;
	geometry: PointGeometry;
}

/** GeoJSON FeatureCollection for lights */
export interface LightCollection {
	type: "FeatureCollection";
	features: LightFeature[];
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

/**
 * Vertical range for 3D collision checking
 *
 * Models the player as a vertical cylinder - from feet level to head level.
 * Used to determine if a player's vertical position overlaps with a building's
 * vertical extent (elevation to elevation + height).
 */
export interface AltitudeRange {
	/** Minimum altitude (feet level) in meters above sea level */
	min: number;
	/** Maximum altitude (head level) in meters above sea level */
	max: number;
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

// ============================================================================
// GeoJSON Types for Tram Infrastructure
// ============================================================================

/** Tram track segment properties from VBZ data */
export interface TramTrackProperties {
	/** Unique object identifier */
	objectid: number;
	/** Street/location name */
	streckengleisbezeichnung: string;
	/** Track number (e.g., "70-3") */
	streckengleisnummer: string;
	/** Track direction type: "Auswärtsgleis" (outbound) or "Einwärtsgleis" (inbound) */
	streckengleistyptext: string;
}

/** GeoJSON MultiLineString geometry */
export interface MultiLineStringGeometry {
	type: "MultiLineString";
	coordinates: [number, number][][];
}

/** GeoJSON Feature for a tram track segment */
export interface TramTrackFeature {
	type: "Feature";
	properties: TramTrackProperties;
	geometry: MultiLineStringGeometry;
}

/** GeoJSON FeatureCollection for tram tracks */
export interface TramTrackCollection {
	type: "FeatureCollection";
	features: TramTrackFeature[];
}

/** Overhead pole properties from VBZ data */
export interface OverheadPoleProperties {
	/** Unique object identifier */
	objectid: number;
	/** Pole identification number */
	nummer: string;
	/** Top of pole elevation (absolute meters above sea level) */
	hoehemastok: number;
	/** Bottom of pole elevation (absolute meters above sea level) */
	hoehemastuk: number;
	/** Pole orientation angle in degrees */
	orientierung: number;
}

/** GeoJSON MultiPoint geometry */
export interface MultiPointGeometry {
	type: "MultiPoint";
	coordinates: [number, number][];
}

/** GeoJSON Feature for an overhead pole */
export interface OverheadPoleFeature {
	type: "Feature";
	properties: OverheadPoleProperties;
	geometry: MultiPointGeometry;
}

/** GeoJSON FeatureCollection for overhead poles */
export interface OverheadPoleCollection {
	type: "FeatureCollection";
	features: OverheadPoleFeature[];
}

/** Processed tram track path for rendering */
export interface TramTrackPath {
	/** 3D path coordinates [lng, lat, elevation] */
	path: [number, number, number][];
	/** Track direction for coloring */
	direction: string;
	/** Street/location name */
	name: string;
}

/** Processed overhead pole for rendering */
export interface ProcessedPole {
	/** Position [lng, lat] */
	position: [number, number];
	/** Top of pole elevation (absolute) */
	topHeight: number;
	/** Bottom of pole elevation (absolute) */
	bottomHeight: number;
}

// ============================================================================
// GTFS Tram Trips Types
// ============================================================================

/**
 * GTFS route type enumeration for transit classification.
 *
 * @see https://gtfs.org/schedule/reference/#routestxt
 */
export enum RouteType {
	/** Tram, Streetcar, Light rail */
	Tram = 0,
	/** Subway, Metro */
	Subway = 1,
	/** Rail */
	Rail = 2,
	/** Bus */
	Bus = 3,
	/** Ferry */
	Ferry = 4,
	/** Cable tram */
	CableTram = 5,
	/** Aerial lift (gondola, aerial tramway) */
	AerialLift = 6,
	/** Funicular */
	Funicular = 7,
}

/**
 * Human-readable labels for route types.
 */
export const ROUTE_TYPE_LABELS: Record<RouteType, string> = {
	[RouteType.Tram]: "Trams",
	[RouteType.Subway]: "Subway",
	[RouteType.Rail]: "Rail",
	[RouteType.Bus]: "Buses",
	[RouteType.Ferry]: "Ferries",
	[RouteType.CableTram]: "Cable Trams",
	[RouteType.AerialLift]: "Aerial Lifts",
	[RouteType.Funicular]: "Funiculars",
};

/**
 * Transit trip data for deck.gl TripsLayer.
 *
 * Supports all GTFS transit types: trams, buses, ferries, funiculars, etc.
 * Uses parallel arrays (path + timestamps) for efficient JSON serialization.
 *
 * @example
 * ```typescript
 * const trip: TramTrip = {
 * 	route_id: "10",
 * 	route_type: 0,
 * 	route_short_name: "10",
 * 	route_color: "#00a1e0",
 * 	headsign: "Bahnhof Oerlikon",
 * 	path: [[8.54, 47.37, 410.5], [8.55, 47.38, 412.0]],
 * 	timestamps: [28800, 28920],
 * };
 * ```
 */
export interface TramTrip {
	/** GTFS route identifier */
	route_id: string;
	/** GTFS route type (0=Tram, 3=Bus, 4=Ferry, 6=Gondola, 7=Funicular) */
	route_type: RouteType;
	/** Short route name (e.g., "10", "11") */
	route_short_name: string;
	/** Route color in hex format (e.g., "#00a1e0") */
	route_color: string;
	/** Trip destination/headsign (e.g., "Bahnhof Oerlikon") */
	headsign: string;
	/** Path coordinates: [lng, lat, elevation] for each point */
	path: [number, number, number][];
	/** Timestamps in seconds since midnight, one per path point */
	timestamps: number[];
}

/**
 * Complete tram trips dataset with metadata.
 *
 * @example
 * ```typescript
 * const data: TramTripsData = await fetch("/data/zurich-tram-trips.json").then((r) => r.json());
 * console.log(`Loaded ${data.metadata.trip_count} trips`);
 * ```
 */
export interface TramTripsData {
	/** Array of tram trips */
	trips: TramTrip[];
	/** Dataset metadata */
	metadata: {
		/** Total number of trips */
		trip_count: number;
		/** Number of unique routes */
		route_count: number;
		/** ISO timestamp when data was generated */
		generated: string;
		/** Data source description */
		source: string;
		/** License information */
		license: string;
	};
}

// Re-export binary GTFS types
export * from "./gtfs-binary";
