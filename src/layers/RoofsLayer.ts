/**
 * Roofs Layer Factory
 *
 * Creates deck.gl layers for rendering 3D roof faces from LOD2 building data.
 * Unlike the BuildingsLayer which extrudes flat footprints, this layer renders
 * actual roof geometry (gabled, hipped, flat) as pre-positioned 3D polygons.
 *
 * Each roof face is a polygon with 3D coordinates (lng, lat, elevation) that
 * forms part of the building's actual roof topology.
 */

import { SolidPolygonLayer } from "@deck.gl/layers";
import type {
	RoofFaceFeature,
	RoofMaterial,
	RoofOrientation,
	RoofType,
	Position3D,
} from "@/types/roof";
import {
	ROOF_MATERIAL_COLORS,
	ROOF_TYPE_COLORS,
	ROOF_ORIENTATION_COLORS,
} from "@/types/roof";

/** Color mode for roof visualization */
export type RoofColorMode = "material" | "type" | "orientation" | "slope";

export interface RoofsLayerConfig {
	id?: string;
	/** How to color roofs: by material, type, orientation, or slope angle */
	colorMode?: RoofColorMode;
	/** Custom fill color (overrides colorMode) */
	fillColor?: [number, number, number, number];
	/** Highlight color on hover */
	highlightColor?: [number, number, number, number];
	opacity?: number;
	pickable?: boolean;
	autoHighlight?: boolean;
	/** Filter by roof type */
	roofTypeFilter?: RoofType[];
	/** Filter by material */
	materialFilter?: RoofMaterial[];
	/** Minimum slope angle to display (degrees) */
	minSlopeAngle?: number;
	/** Maximum slope angle to display (degrees) */
	maxSlopeAngle?: number;
}

const DEFAULT_CONFIG: Required<Omit<RoofsLayerConfig, "roofTypeFilter" | "materialFilter">> & {
	roofTypeFilter?: RoofType[];
	materialFilter?: RoofMaterial[];
} = {
	id: "roofs",
	colorMode: "material",
	fillColor: [180, 100, 80, 255],
	highlightColor: [255, 220, 150, 255],
	opacity: 1,
	pickable: true,
	autoHighlight: true,
	roofTypeFilter: undefined,
	materialFilter: undefined,
	minSlopeAngle: 0,
	maxSlopeAngle: 90,
};

/**
 * Get color for a roof face based on color mode
 */
function getRoofColor(
	feature: RoofFaceFeature,
	colorMode: RoofColorMode,
	customColor?: [number, number, number, number]
): [number, number, number, number] {
	if (customColor) {
		return customColor;
	}

	const props = feature.properties;

	switch (colorMode) {
		case "material":
			return (
				ROOF_MATERIAL_COLORS[props.material as RoofMaterial] ??
				ROOF_MATERIAL_COLORS.roof_terracotta
			);

		case "type":
			return (
				ROOF_TYPE_COLORS[props.roof_type as RoofType] ??
				ROOF_TYPE_COLORS.complex
			);

		case "orientation":
			return (
				ROOF_ORIENTATION_COLORS[props.orientation as RoofOrientation] ??
				ROOF_ORIENTATION_COLORS.FLAT
			);

		case "slope": {
			// Color gradient from flat (gray) to steep (red)
			const slope = Math.min(props.slope_angle, 60) / 60; // Normalize to 0-1
			const r = Math.round(140 + slope * 115);
			const g = Math.round(140 - slope * 60);
			const b = Math.round(145 - slope * 65);
			return [r, g, b, 255];
		}

		default:
			return ROOF_MATERIAL_COLORS.roof_terracotta;
	}
}

/**
 * Extract 3D polygon coordinates from a roof face feature
 *
 * After terrain pre-processing, coordinates are in [lng, lat, height_above_terrain]
 * format. We add the Mapterhorn terrain_elevation to get absolute positioning
 * that aligns with deck.gl's TerrainLayer.
 *
 * @param feature - Roof face feature with terrain-relative coordinates
 */
function getPolygonCoordinates(feature: RoofFaceFeature): Position3D[] {
	const coords = feature.geometry.coordinates[0];
	if (!coords) return [];

	// Get terrain elevation from pre-processed data (added by add_roof_elevations.py)
	// Falls back to base_elevation if terrain_elevation not present
	const terrainElevation =
		feature.properties.terrain_elevation ?? feature.properties.base_elevation;

	// Coordinates are now [lng, lat, height_above_terrain] from pre-processing
	// Add terrain elevation to get absolute Z for deck.gl positioning
	return coords.map((coord) => {
		const heightAboveTerrain = coord.length >= 3 ? coord[2] : 0;
		return [
			coord[0],
			coord[1],
			terrainElevation + heightAboveTerrain,
		] as Position3D;
	});
}

/**
 * Filter roof faces based on configuration
 */
function filterRoofFaces(
	data: RoofFaceFeature[],
	config: RoofsLayerConfig
): RoofFaceFeature[] {
	return data.filter((feature) => {
		const props = feature.properties;

		// Filter by roof type
		if (config.roofTypeFilter && config.roofTypeFilter.length > 0) {
			if (!config.roofTypeFilter.includes(props.roof_type as RoofType)) {
				return false;
			}
		}

		// Filter by material
		if (config.materialFilter && config.materialFilter.length > 0) {
			if (!config.materialFilter.includes(props.material as RoofMaterial)) {
				return false;
			}
		}

		// Filter by slope angle
		const minSlope = config.minSlopeAngle ?? 0;
		const maxSlope = config.maxSlopeAngle ?? 90;
		if (props.slope_angle < minSlope || props.slope_angle > maxSlope) {
			return false;
		}

		return true;
	});
}

/**
 * Create a 3D roofs layer from LOD2 roof face data
 *
 * Unlike BuildingsLayer which extrudes flat footprints, this layer renders
 * actual roof geometry as non-extruded 3D polygons at their correct positions.
 *
 * @param data - Array of RoofFaceFeature objects
 * @param config - Layer configuration options
 */
export function createRoofsLayer(
	data: RoofFaceFeature[],
	config: RoofsLayerConfig = {}
): SolidPolygonLayer<RoofFaceFeature> {
	const mergedConfig = { ...DEFAULT_CONFIG, ...config };

	// Apply filters
	const filteredData = filterRoofFaces(data, mergedConfig);

	// Log statistics
	if (data.length > 0) {
		const roofTypes = new Map<string, number>();
		const materials = new Map<string, number>();
		for (const f of filteredData) {
			roofTypes.set(
				f.properties.roof_type,
				(roofTypes.get(f.properties.roof_type) ?? 0) + 1
			);
			materials.set(
				f.properties.material,
				(materials.get(f.properties.material) ?? 0) + 1
			);
		}
		console.log(
			`[Roofs] ${filteredData.length}/${data.length} faces displayed`
		);
		console.log(`[Roofs] Types:`, Object.fromEntries(roofTypes));
		console.log(`[Roofs] Materials:`, Object.fromEntries(materials));
	}

	return new SolidPolygonLayer<RoofFaceFeature>({
		id: mergedConfig.id,
		data: filteredData,
		getPolygon: (d) => getPolygonCoordinates(d),
		// Roofs are not extruded - they're already positioned in 3D
		extruded: false,
		getFillColor: (d) =>
			getRoofColor(
				d,
				mergedConfig.colorMode,
				config.fillColor // Only use custom color if explicitly set
			),
		highlightColor: mergedConfig.highlightColor,
		opacity: mergedConfig.opacity,
		pickable: mergedConfig.pickable,
		autoHighlight: mergedConfig.autoHighlight,
		// Force z-coordinate to be used (critical for 3D positioning)
		_full3d: true,
		material: {
			ambient: 0.4,
			diffuse: 0.6,
			shininess: 20,
			specularColor: [50, 50, 55],
		},
		updateTriggers: {
			getFillColor: [mergedConfig.colorMode, config.fillColor],
		},
	});
}

/**
 * Create a minimap-compatible roofs layer (2D, flat)
 *
 * @param data - Array of RoofFaceFeature objects
 * @param config - Layer configuration options
 */
export function createMinimapRoofsLayer(
	data: RoofFaceFeature[],
	config: Partial<RoofsLayerConfig> = {}
): SolidPolygonLayer<RoofFaceFeature> {
	const mergedConfig = {
		...DEFAULT_CONFIG,
		id: "minimap-roofs",
		pickable: false,
		autoHighlight: false,
		colorMode: "material" as RoofColorMode,
		...config,
	};

	const filteredData = filterRoofFaces(data, mergedConfig);

	return new SolidPolygonLayer<RoofFaceFeature>({
		id: mergedConfig.id,
		data: filteredData,
		// For minimap, project to 2D (ignore elevation)
		getPolygon: (d) => {
			const coords = d.geometry.coordinates[0] ?? [];
			return coords.map((c) => [c[0], c[1], 0] as Position3D);
		},
		extruded: false,
		getFillColor: (d) => getRoofColor(d, mergedConfig.colorMode),
		opacity: mergedConfig.opacity,
		pickable: false,
	});
}

// Re-export types for convenience
export type {
	RoofFaceFeature,
	RoofFaceCollection,
	RoofFaceProperties,
	RoofMaterial,
	RoofType,
	RoofOrientation,
} from "@/types/roof";
