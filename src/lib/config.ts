/**
 * Application configuration
 *
 * Centralized settings for the 3D viewer
 */

/**
 * Vercel Blob base URL for large GTFS files
 * Set VITE_BLOB_BASE_URL in .env.local or Vercel environment variables
 * Example: https://abc123.public.blob.vercel-storage.com
 */
const BLOB_BASE_URL = import.meta.env.VITE_BLOB_BASE_URL as string | undefined;

/**
 * Get data URL - uses Vercel Blob for large GTFS files in production,
 * local paths for development or when BLOB_BASE_URL is not set
 *
 * @param localPath - Path starting with / (e.g., "/data/file.json")
 * @param useBlobForLargeFiles - If true and BLOB_BASE_URL is set, use Blob URL
 */
function getDataUrl(localPath: string, useBlobForLargeFiles = false): string {
	if (useBlobForLargeFiles && BLOB_BASE_URL) {
		// Strip leading slash and add to blob URL
		const blobPath = localPath.replace(/^\//, "");
		return `${BLOB_BASE_URL}/${blobPath}`;
	}
	return localPath;
}

/** City-specific configurations */
export const CITIES = {
	zurich: {
		name: "Zürich",
		center: { longitude: 8.5417, latitude: 47.3769 },
		baseElevation: 408,
		bounds: {
			min_lng: 8.448,
			max_lng: 8.626,
			min_lat: 47.320,
			max_lat: 47.435,
		},
		boundsLV95: {
			min_e: 2676000,
			max_e: 2689000,
			min_n: 1241000,
			max_n: 1254000,
		},
		transitOperator: "VBZ",
	},
	lucerne: {
		name: "Luzern",
		center: { longitude: 8.3093, latitude: 47.0502 },
		baseElevation: 436,
		bounds: {
			min_lng: 8.20,
			max_lng: 8.45,
			min_lat: 46.95,
			max_lat: 47.10,
		},
		boundsLV95: {
			min_e: 2655000,
			max_e: 2680000,
			min_n: 1200000,
			max_n: 1225000,
		},
		transitOperator: "VBL",
	},
} as const;

export type CityId = keyof typeof CITIES;

export const CONFIG = {
	/** Rendering settings */
	render: {
		/** Vertical field of view in degrees */
		fov: 75,
		/** Near clipping plane in meters */
		near: 0.1,
		/** Far clipping plane in meters */
		far: 10000,
		/** Target frame rate */
		targetFps: 60,
	},

	/** Player settings */
	player: {
		/** Total height in meters */
		height: 1.8,
		/** Camera/eye height from ground */
		eyeHeight: 1.7,
		/** Collision radius in meters */
		collisionRadius: 0.3,
		/** Maximum step-up height in meters */
		stepHeight: 0.3,
		/** Maximum altitude for fly mode */
		maxAltitude: 1000,
	},

	/** Movement speeds in meters per second */
	movement: {
		walk: 4.0,
		run: 12.0,
		/** Altitude scaling: meters above terrain per 1x speed multiplier (40m = 2x, 400m = 11x) */
		altitudeScaleFactor: 40.0,
		/** Maximum speed multiplier cap (effectively uncapped for fast high-altitude travel) */
		maxSpeedMultiplier: 500.0,
		/** Keyboard turn rate in degrees per second */
		turnRate: 90,
	},

	/** Mouse sensitivity (degrees per pixel) */
	mouse: {
		sensitivityX: 0.1,
		sensitivityY: 0.1,
		/** Invert Y axis */
		invertY: false,
	},

	/** Camera constraints */
	camera: {
		/** Minimum pitch angle (looking down) in degrees */
		pitchMin: -89,
		/** Maximum pitch angle (looking up) in degrees */
		pitchMax: 89,
		// Note: minAltitude removed - now calculated dynamically from terrain via AltitudeSystem
	},

	/** Data paths (v=2 cache bust for terrain elevation update, v=4 for dual-mode transit) */
	data: {
		buildings: "/data/zurich-buildings.geojson?v=2",
		/** LOD2 roof faces from Stadt Zürich 3D building data */
		roofs: "/data/zurich-roofs.geojson",
		trees: "/data/zurich-trees.geojson?v=2",
		lights: "/data/zurich-lights.geojson?v=2",
		tramTracks: "/data/zurich-tram-tracks.geojson",
		tramPoles: "/data/zurich-tram-poles.geojson",
		/** All transit trips (flat, no elevation) - for "all routes" mode (244MB - uses Blob in production) */
		tramTrips: getDataUrl("/data/zurich-tram-trips.json", true),
		/** Limited transit trips with terrain elevation - for 3D terrain mode (59MB - uses Blob in production) */
		tramTripsTerrain: getDataUrl("/data/zurich-tram-trips-terrain.json", true),
		/** Binary GTFS trips with chunking - for memory-optimized streaming (40MB - uses Blob in production) */
		tramTripsBinary: getDataUrl("/data/gtfs/gtfs-trips.bin", true),
		/** Chunk manifest for binary GTFS - uses Blob in production */
		tramTripsManifest: getDataUrl("/data/gtfs/gtfs-trips.manifest.json", true),
		fountains: "/data/zurich-fountains.geojson?v=2",
		benches: "/data/zurich-benches.geojson?v=2",
		toilets: "/data/zurich-toilets.geojson?v=2",
		streets: "/data/zurich-streets.geojson",
		water: "/data/zurich-water.geojson",
		terrain: "/data/terrain.png",
		tileIndex: "/data/tiles/buildings/tile-index.json",
	},

	/** Lucerne-specific data paths */
	lucerneData: {
		buildings: "/data/lucerne/lucerne-buildings.geojson",
		trees: "/data/lucerne/lucerne-trees.geojson",
		fountains: "/data/lucerne/lucerne-fountains.geojson",
		benches: "/data/lucerne/lucerne-benches.geojson",
		toilets: "/data/lucerne/lucerne-toilets.geojson",
		heritage: "/data/lucerne/lucerne-heritage.geojson",
		trails: "/data/lucerne/lucerne-trails.geojson",
		/** VBL transit trips */
		transitTrips: "/data/lucerne/lucerne-vbl-trips.json",
		/** Binary GTFS (if generated) */
		transitBinary: "/data/lucerne/gtfs/lucerne-gtfs.bin",
		transitManifest: "/data/lucerne/gtfs/lucerne-gtfs.manifest.json",
	},

	/** Debug settings */
	debug: {
		/** Show debug panel */
		showDebugPanel: import.meta.env.DEV,
		/** Log performance metrics */
		logPerformance: false,
	},

	/** Performance optimization settings */
	performance: {
		/** Maximum distance to render buildings in meters */
		buildingRenderDistance: 750,
		/** Maximum distance to render trees in meters */
		treeRenderDistance: 500,
		/** Maximum distance to render street lights in meters */
		lightRenderDistance: 300,
		/** Maximum distance to create building colliders in meters */
		colliderRadius: 100,
		/** Maximum number of active building colliders */
		maxActiveColliders: 500,
		/** SSAO sample count by quality tier [low, medium, high] */
		ssaoSamples: [4, 8, 16] as const,
		/** Enable bloom by quality tier [low, medium, high] */
		bloomEnabled: [false, true, true] as const,
		/** Render distance multiplier by quality tier [low, medium, high] */
		renderDistanceMultiplier: [0.5, 0.75, 1.0] as const,
		/** FPS threshold below which to reduce quality */
		fpsThresholdLow: 30,
		/** FPS threshold above which to increase quality */
		fpsThresholdHigh: 55,
		/** Number of frames to average for FPS calculation */
		fpsAverageFrames: 30,
	},
} as const;

/** Type for the config object */
export type Config = typeof CONFIG;
