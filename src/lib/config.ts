/**
 * Application configuration
 *
 * Centralized settings for the 3D viewer
 */

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

  /** Data paths (v=2 cache bust for terrain elevation update) */
  data: {
    buildings: '/data/zurich-buildings.geojson?v=2',
    trees: '/data/zurich-trees.geojson?v=2',
    lights: '/data/zurich-lights.geojson?v=2',
    tramTracks: '/data/zurich-tram-tracks.geojson',
    tramPoles: '/data/zurich-tram-poles.geojson',
    fountains: '/data/zurich-fountains.geojson?v=2',
    benches: '/data/zurich-benches.geojson?v=2',
    toilets: '/data/zurich-toilets.geojson?v=2',
    terrain: '/data/terrain.png',
    tileIndex: '/data/tiles/buildings/tile-index.json',
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
