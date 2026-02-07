/**
 * Streets Layer Factory
 *
 * Creates deck.gl PathLayer for rendering Zurich street centerlines.
 * Streets are rendered as width-proportional ribbons colored by type:
 * - Dark gray: Hauptstrasse (major roads)
 * - Medium gray: Verbindungsstrasse, Sammelstrasse
 * - Light gray: Quartierstrasse, Wohnstrasse
 * - Beige: Fussweg, Fussgaengerzone (pedestrian)
 *
 * Data: ~10,000 street segments from Stadt Zürich WFS
 */

import { PathLayer } from "@deck.gl/layers";
import { ZURICH_BASE_ELEVATION } from "@/types";
import type { StreetFeature, StreetType } from "@/types";

// Re-export types for convenience
export type { StreetFeature, StreetType };

/** Configuration for streets layer */
export interface StreetsLayerConfig {
	id?: string;
	opacity?: number;
	visible?: boolean;
	pickable?: boolean;
}

/** Color mapping by street type - dark to light based on importance */
const STREET_COLORS: Record<string, [number, number, number, number]> = {
	// Major roads - darker, more prominent
	Hauptstrasse: [60, 60, 70, 220],
	Verbindungsstrasse: [70, 70, 80, 210],
	Sammelstrasse: [80, 80, 90, 200],
	// Neighborhood roads - medium gray
	Quartierstrasse: [100, 100, 110, 190],
	Wohnstrasse: [110, 110, 120, 180],
	// Pedestrian - lighter, warmer tone
	Fussweg: [140, 135, 125, 170],
	Fussgaengerzone: [150, 145, 135, 160],
	// Default fallback
	default: [90, 90, 100, 185],
};

/** Default configuration values */
const DEFAULT_CONFIG: Required<StreetsLayerConfig> = {
	id: "streets",
	opacity: 1.0,
	visible: true,
	pickable: false,
};

/** Processed street path for rendering */
export interface StreetPath {
	/** 3D path coordinates [lng, lat, elevation] */
	path: [number, number, number][];
	/** Street width in meters */
	width: number;
	/** Street classification type */
	type: StreetType;
	/** Street name */
	name: string;
}

/**
 * Process street features into flat path array
 *
 * LineString and MultiLineString geometries are processed into individual paths,
 * each with 3D coordinates at ground elevation.
 *
 * @param features - Array of StreetFeature from GeoJSON
 * @returns Array of processed paths ready for PathLayer
 */
export function processStreets(features: StreetFeature[]): StreetPath[] {
	return features.flatMap((feature) => {
		const { properties, geometry } = feature;
		const coords =
			geometry.type === "LineString"
				? [geometry.coordinates]
				: geometry.coordinates;

		return coords.map((line) => ({
			path: line.map(
				([lng, lat]) =>
					[lng, lat, properties.elevation ?? ZURICH_BASE_ELEVATION] as [
						number,
						number,
						number,
					]
			),
			width: properties.width || 6,
			type: properties.street_type || "Quartierstrasse",
			name: properties.street_name || "",
		}));
	});
}

/** Default street color fallback */
const DEFAULT_STREET_COLOR: [number, number, number, number] = [90, 90, 100, 185];

/**
 * Get color for a street type
 */
function getStreetColor(type: StreetType): [number, number, number, number] {
	return STREET_COLORS[type] ?? DEFAULT_STREET_COLOR;
}

/**
 * Create a 3D streets layer
 *
 * Renders street centerlines as colored ribbons on the ground.
 * Width and color are determined by street classification.
 *
 * @param data - Array of StreetFeature objects
 * @param config - Layer configuration options
 */
export function createStreetsLayer(
	data: StreetFeature[],
	config: StreetsLayerConfig = {}
): PathLayer<StreetPath> {
	const cfg = { ...DEFAULT_CONFIG, ...config };
	const paths = processStreets(data);

	return new PathLayer<StreetPath>({
		id: cfg.id,
		data: paths,
		visible: cfg.visible,
		opacity: cfg.opacity,

		// 3D path coordinates
		getPath: (d) => d.path,

		// Color by street type
		getColor: (d) => getStreetColor(d.type),

		// Width from street classification
		getWidth: (d) => d.width,
		widthUnits: "meters",
		widthMinPixels: 1, // Ensure visibility at all zoom levels

		// Smooth path rendering
		jointRounded: true,
		capRounded: true,

		pickable: cfg.pickable,
	});
}

/** Processed street path for 2D minimap rendering */
interface StreetPath2D {
	/** 2D path coordinates [lng, lat] */
	path: [number, number][];
	/** Street width in meters */
	width: number;
	/** Street classification type */
	type: StreetType;
}

/**
 * Process street features into flat 2D path array (for minimap)
 */
function processStreets2D(features: StreetFeature[]): StreetPath2D[] {
	return features.flatMap((feature) => {
		const { properties, geometry } = feature;
		const coords =
			geometry.type === "LineString"
				? [geometry.coordinates]
				: geometry.coordinates;

		return coords.map((line) => ({
			path: line.map(([lng, lat]) => [lng, lat] as [number, number]),
			width: properties.width || 6,
			type: properties.street_type || "Quartierstrasse",
		}));
	});
}

/**
 * Create a minimap streets layer (2D, simpler)
 *
 * @param data - Array of StreetFeature objects
 * @param config - Layer configuration options
 */
export function createMinimapStreetsLayer(
	data: StreetFeature[],
	config: Partial<StreetsLayerConfig> = {}
): PathLayer<StreetPath2D> {
	const cfg = {
		...DEFAULT_CONFIG,
		id: "minimap-streets",
		pickable: false,
		...config,
	};

	const paths = processStreets2D(data);

	return new PathLayer<StreetPath2D>({
		id: cfg.id,
		data: paths,
		visible: cfg.visible,
		opacity: cfg.opacity,
		getPath: (d) => d.path,
		getColor: (d) => getStreetColor(d.type),
		getWidth: (d) => d.width,
		widthUnits: "meters",
		widthMinPixels: 1,
		jointRounded: true,
		capRounded: true,
		pickable: cfg.pickable,
	});
}
