/**
 * Systems barrel export
 */

// Movement
export {
  calculateVelocity,
  hasMovementInput,
  createEmptyKeyboardState,
} from './MovementController';

// Camera
export {
  applyMouseLook,
  applyMouseDelta,
  applyVelocity,
  setAltitude,
  setPosition,
  getForwardDirection,
  getRightDirection,
} from './CameraController';

// Spatial Index / Collision
export {
  SpatialIndex,
  createSpatialIndex,
} from './SpatialIndex';

// Terrain
export {
  TerrainSampler,
  createTerrainSampler,
  getDefaultElevation,
} from './TerrainSampler';

// Altitude
export {
  AltitudeSystem,
  createAltitudeSystem,
  type AltitudeSystemOptions,
} from './AltitudeSystem';
