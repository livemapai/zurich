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
    /** Minimum altitude for fly mode (just above Zurich ground level ~408m) */
    minAltitude: 410,
    /** Maximum altitude for fly mode */
    maxAltitude: 1000,
  },

  /** Movement speeds in meters per second */
  movement: {
    walk: 4.0,
    run: 8.0,
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
    /** Minimum pitch angle (looking down) */
    pitchMin: -89,
    /** Maximum pitch angle (looking up) */
    pitchMax: 89,
    /** Minimum altitude above ground */
    minAltitude: 0.5,
  },

  /** Data paths */
  data: {
    buildings: '/data/zurich-buildings.geojson',
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
} as const;

/** Type for the config object */
export type Config = typeof CONFIG;
