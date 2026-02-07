/**
 * Data Loaders
 *
 * Exports all data loading utilities.
 */

export {
  loadBuildings,
  loadBuildingsWithTimeout,
  type LoadBuildingsResult,
  type BuildingStats,
} from './buildings';

export {
  loadShadows,
  extractShadowsFromMapLibre,
  generateShadowFromBuilding,
  type ShadowFeature,
  type ShadowCollection,
  type ShadowProperties,
  type ShadowPolygon,
  type LoadShadowsResult,
} from './shadowLoader';
