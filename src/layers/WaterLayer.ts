/**
 * Water Layer Factory
 *
 * Creates deck.gl layers for rendering Zurich water bodies:
 * - SolidPolygonLayer for lakes and ponds (flat, blue surfaces)
 * - PathLayer for rivers and streams (width-based ribbons)
 *
 * Major water features:
 * - Zürichsee (Lake Zurich) - polygon
 * - Limmat river - linestring
 * - Sihl river - linestring
 * - Schanzengraben canal - linestring
 */

import { PathLayer } from "@deck.gl/layers";
import { SolidPolygonLayer } from "@deck.gl/layers";
import type { Layer } from "@deck.gl/core";
import { ZURICH_BASE_ELEVATION } from "@/types";
import type { WaterFeature, WaterType } from "@/types";

// Re-export types for convenience
export type { WaterFeature, WaterType };

/** Configuration for water layer */
export interface WaterLayerConfig {
	id?: string;
	opacity?: number;
	visible?: boolean;
	pickable?: boolean;
	lakeColor?: [number, number, number, number];
	riverColor?: [number, number, number, number];
}

/** Default water colors - semi-transparent blue */
const WATER_COLORS = {
	lake: [40, 100, 150, 180] as [number, number, number, number],
	river: [45, 110, 160, 175] as [number, number, number, number],
	stream: [50, 120, 170, 165] as [number, number, number, number],
	pond: [35, 90, 140, 170] as [number, number, number, number],
};

/** Default configuration values */
const DEFAULT_CONFIG: Required<WaterLayerConfig> = {
	id: "water",
	opacity: 1.0,
	visible: true,
	pickable: true,
	lakeColor: WATER_COLORS.lake,
	riverColor: WATER_COLORS.river,
};

/** Processed lake polygon for rendering */
export interface LakePolygon {
	/** Polygon coordinates (outer ring, may include holes) */
	polygon: [number, number, number][][] | [number, number, number][];
	/** Water body name */
	name: string;
	/** Water type */
	type: WaterType;
}

/** Processed river path for rendering */
export interface RiverPath {
	/** 3D path coordinates [lng, lat, elevation] */
	path: [number, number, number][];
	/** River width in meters */
	width: number;
	/** Water body name */
	name: string;
	/** Water type */
	type: WaterType;
}

/**
 * Process water features into lakes (polygons) and rivers (lines)
 */
function processWaterFeatures(features: WaterFeature[]): {
	lakes: LakePolygon[];
	rivers: RiverPath[];
} {
	const lakes: LakePolygon[] = [];
	const rivers: RiverPath[] = [];

	for (const feature of features) {
		const { properties, geometry } = feature;
		const elevation = properties.elevation ?? ZURICH_BASE_ELEVATION - 2; // Water slightly below ground

		if (geometry.type === "Polygon") {
			// Single polygon - process outer ring and holes
			const polygon = geometry.coordinates.map((ring) =>
				ring.map(
					([lng, lat]) => [lng, lat, elevation] as [number, number, number]
				)
			);
			lakes.push({
				polygon,
				name: properties.name,
				type: properties.water_type,
			});
		} else if (geometry.type === "MultiPolygon") {
			// Multiple polygons - flatten each to separate lake entries
			for (const poly of geometry.coordinates) {
				const polygon = poly.map((ring) =>
					ring.map(
						([lng, lat]) => [lng, lat, elevation] as [number, number, number]
					)
				);
				lakes.push({
					polygon,
					name: properties.name,
					type: properties.water_type,
				});
			}
		} else if (geometry.type === "LineString") {
			rivers.push({
				path: geometry.coordinates.map(
					([lng, lat]) => [lng, lat, elevation] as [number, number, number]
				),
				width: properties.width || 10,
				name: properties.name,
				type: properties.water_type,
			});
		} else if (geometry.type === "MultiLineString") {
			for (const line of geometry.coordinates) {
				rivers.push({
					path: line.map(
						([lng, lat]) => [lng, lat, elevation] as [number, number, number]
					),
					width: properties.width || 10,
					name: properties.name,
					type: properties.water_type,
				});
			}
		}
	}

	return { lakes, rivers };
}

/**
 * Get water color based on type
 */
function getWaterColor(type: WaterType): [number, number, number, number] {
	return WATER_COLORS[type] ?? WATER_COLORS.river;
}

/**
 * Create water body layers (lakes + rivers)
 *
 * Returns an array of layers:
 * - SolidPolygonLayer for lakes/ponds (if any)
 * - PathLayer for rivers/streams (if any)
 *
 * @param data - Array of WaterFeature objects
 * @param config - Layer configuration options
 * @returns Array of deck.gl layers
 */
export function createWaterLayers(
	data: WaterFeature[],
	config: WaterLayerConfig = {}
): Layer[] {
	const cfg = { ...DEFAULT_CONFIG, ...config };
	const { lakes, rivers } = processWaterFeatures(data);
	const layers: Layer[] = [];

	// Lakes as flat polygons
	if (lakes.length > 0) {
		layers.push(
			new SolidPolygonLayer<LakePolygon>({
				id: `${cfg.id}-lakes`,
				data: lakes,
				visible: cfg.visible,
				opacity: cfg.opacity,

				// Polygon coordinates (handles both simple and complex polygons)
				getPolygon: (d) => d.polygon,

				// Color by water type
				getFillColor: (d) => getWaterColor(d.type),

				// Flat surface (not extruded)
				extruded: false,

				pickable: cfg.pickable,
			})
		);
	}

	// Rivers as wide paths
	if (rivers.length > 0) {
		layers.push(
			new PathLayer<RiverPath>({
				id: `${cfg.id}-rivers`,
				data: rivers,
				visible: cfg.visible,
				opacity: cfg.opacity,

				// 3D path coordinates
				getPath: (d) => d.path,

				// Color by water type
				getColor: (d) => getWaterColor(d.type),

				// Width from properties
				getWidth: (d) => d.width,
				widthUnits: "meters",
				widthMinPixels: 2,

				// Smooth rendering for natural appearance
				jointRounded: true,
				capRounded: true,

				pickable: cfg.pickable,
			})
		);
	}

	return layers;
}

/**
 * Create minimap water layers (2D, simpler)
 */
export function createMinimapWaterLayers(
	data: WaterFeature[],
	config: Partial<WaterLayerConfig> = {}
): Layer[] {
	const cfg = {
		...DEFAULT_CONFIG,
		id: "minimap-water",
		pickable: false,
		...config,
	};

	const { lakes, rivers } = processWaterFeatures(data);
	const layers: Layer[] = [];

	if (lakes.length > 0) {
		layers.push(
			new SolidPolygonLayer<LakePolygon>({
				id: `${cfg.id}-lakes`,
				data: lakes,
				visible: cfg.visible,
				opacity: cfg.opacity,
				getPolygon: (d) => d.polygon,
				getFillColor: (d) => getWaterColor(d.type),
				extruded: false,
				pickable: false,
			})
		);
	}

	if (rivers.length > 0) {
		layers.push(
			new PathLayer<RiverPath>({
				id: `${cfg.id}-rivers`,
				data: rivers,
				visible: cfg.visible,
				opacity: cfg.opacity,
				getPath: (d) => d.path,
				getColor: (d) => getWaterColor(d.type),
				getWidth: (d) => d.width,
				widthUnits: "meters",
				widthMinPixels: 1,
				jointRounded: true,
				capRounded: true,
				pickable: false,
			})
		);
	}

	return layers;
}
