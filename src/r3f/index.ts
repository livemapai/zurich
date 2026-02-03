/**
 * React Three Fiber (R3F) Module
 *
 * Game-ready 3D experience using:
 * - three + @react-three/fiber for 3D rendering
 * - @react-three/rapier for physics
 * - @react-three/postprocessing for visual effects
 */

// Components
export { Scene } from './components/Scene';
export { Lighting } from './components/Lighting';
export { FirstPersonCamera } from './components/FirstPersonCamera';
export { Player } from './components/Player';
export { Effects } from './components/Effects';
export { AdaptiveEffects } from './components/AdaptiveEffects';
export { GameUI } from './components/GameUI';
export { LODInstancedMesh } from './components/LODInstancedMesh';

// Layers
export { TileGround } from './layers/TileGround';
export { Buildings } from './layers/Buildings';
export { BuildingColliders } from './layers/BuildingColliders';
export { Trees } from './layers/Trees';
export { StreetLights } from './layers/StreetLights';

// Geometry utilities
export * from './geometry/tileUtils';
export * from './geometry/buildingGeometry';
export * from './geometry/convertMesh';

// Hooks
export { usePlayerCamera } from './hooks/usePlayerCamera';
export { usePlayerMovement } from './hooks/usePlayerMovement';
export { useDistanceFilter, useDistanceFilterIndices } from './hooks/useDistanceFilter';
export { useSpatialChunks, useSpatialChunkStats } from './hooks/useSpatialChunks';
export { useFPSMonitor, useFPS, useFPSAverage, FPSMonitor } from './hooks/useFPSMonitor';
export { useBuildingSpatialFilter } from './hooks/useBuildingSpatialFilter';
export { useTileManager } from './hooks/useTileManager';

// Systems
export { SpatialChunkManager, createSpatialChunkManager } from './systems/SpatialChunkManager';
export { TileManager, createTileManager } from './systems/TileManager';
export type { TileIndex, TileInfo, LoadedTile } from './systems/TileManager';

// Stores
export {
  usePerformanceStore,
  usePerformanceSelector,
  recordFrame,
  setQualityTier,
  resetPerformanceStore,
} from './stores/performanceStore';
export type { PerformanceState, QualityTier } from './stores/performanceStore';
