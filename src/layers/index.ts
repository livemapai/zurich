/**
 * Layer Factories
 *
 * Exports all deck.gl layer factory functions.
 */

// Buildings layers
export {
	createBuildingsLayer,
	createMinimapBuildingsLayer,
	type BuildingsLayerConfig,
} from "./BuildingsLayer";

// Terrain layers
export {
	createTerrainLayer,
	createGridLayer,
	type TerrainLayerConfig,
	type GridLayerConfig,
} from "./TerrainLayer";

// Map tile layers
export {
	createMapTileLayer,
	OSM_TILE_URL,
	STADIA_TILE_URL,
	MAP_TILE_PROVIDERS,
	type MapTileLayerConfig,
	type MapTileProviderId,
} from "./MapTileLayer";

// Minimap layers
export {
	createMinimapLayers,
	createPlayerMarkerLayer,
	createViewConeLayer,
	type MinimapConfig,
} from "./MinimapLayers";

// Trees layers
export {
	createTreesLayer,
	createMinimapTreesLayer,
	type TreesLayerConfig,
	type TreeFeature,
	type TreeCollection,
	type TreeProperties,
	type PointGeometry,
} from "./TreesLayer";

// Lights layers
export {
	createLightsLayer,
	createMinimapLightsLayer,
	type LightsLayerConfig,
	type LightFeature,
	type LightProperties,
} from "./LightsLayer";

// Mapterhorn 3D terrain layer
export {
	createMapterhornTerrainLayer,
	TEXTURE_PROVIDERS,
	SWISS_ZOOM_THRESHOLD,
	type MapterhornTerrainLayerConfig,
	type TextureProviderId,
} from "./MapterhornTerrainLayer";

// Tram tracks layer
export {
	createTramTracksLayer,
	createMinimapTramTracksLayer,
	processTramTracks,
	type TramTracksLayerConfig,
	type TramTrackFeature,
	type TramTrackPath,
} from "./TramTracksLayer";

// Overhead poles layer
export {
	createOverheadPolesLayer,
	processOverheadPoles,
	type OverheadPolesLayerConfig,
	type OverheadPoleFeature,
	type ProcessedPole,
} from "./OverheadPolesLayer";

// Fountains layer
export {
	createFountainsLayer,
	createMinimapFountainsLayer,
	type FountainsLayerConfig,
	type FountainFeature,
	type FountainCollection,
	type FountainProperties,
} from "./FountainsLayer";

// Benches layer
export {
	createBenchesLayer,
	createMinimapBenchesLayer,
	type BenchesLayerConfig,
	type BenchFeature,
	type BenchCollection,
	type BenchProperties,
} from "./BenchesLayer";

// Toilets layer
export {
	createToiletsLayer,
	createMinimapToiletsLayer,
	type ToiletsLayerConfig,
	type ToiletFeature,
	type ToiletCollection,
	type ToiletProperties,
} from "./ToiletsLayer";

// Tram trips layer
export {
	createTramTripsLayer,
	type TramTripsLayerConfig,
	type TramTrip,
} from "./TramTripsLayer";
