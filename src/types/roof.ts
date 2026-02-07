/**
 * Types for LOD2 Roof Data
 *
 * Roof faces are extracted from Stadt Zürich LOD2 3D building models.
 * Each roof face is a 3D polygon with slope and orientation metadata.
 */

/** 3D coordinate [longitude, latitude, elevation] */
export type Position3D = [lng: number, lat: number, elevation: number];

/** Compass orientation for roof faces */
export type RoofOrientation =
	| "N"
	| "NE"
	| "E"
	| "SE"
	| "S"
	| "SW"
	| "W"
	| "NW"
	| "FLAT";

/** Roof type inferred from geometry */
export type RoofType = "gabled" | "hipped" | "flat" | "mansard" | "complex";

/** Roof material types matching materials.py definitions */
export type RoofMaterial = "roof_terracotta" | "roof_slate" | "roof_flat";

/** Properties for a roof face feature */
export interface RoofFaceProperties {
	/** Building identifier */
	building_id: string;
	/** Face index within building */
	face_index: number;
	/** Inferred roof type */
	roof_type: RoofType;
	/** Slope angle in degrees (0 = flat, 90 = vertical) */
	slope_angle: number;
	/** Compass direction the roof face points */
	orientation: RoofOrientation;
	/** Face area in square meters */
	area_m2: number;
	/** Assigned material for texturing */
	material: RoofMaterial;
	/** Building height in meters (height above terrain after processing) */
	height: number;
	/** Original ground elevation from LOD2 data (meters) */
	base_elevation: number;
	/** Mapterhorn terrain elevation at roof location (meters, added by add_roof_elevations.py) */
	terrain_elevation?: number;
	/** Difference between LOD2 base and Mapterhorn terrain (meters) */
	lod2_terrain_offset?: number;
}

/** GeoJSON Polygon geometry with 3D coordinates */
export interface Polygon3DGeometry {
	type: "Polygon";
	/** Coordinates are [[ring]] where ring is Position3D[] */
	coordinates: Position3D[][];
}

/** GeoJSON Feature for a roof face */
export interface RoofFaceFeature {
	type: "Feature";
	properties: RoofFaceProperties;
	geometry: Polygon3DGeometry;
}

/** GeoJSON FeatureCollection for roof faces */
export interface RoofFaceCollection {
	type: "FeatureCollection";
	metadata?: {
		source: string;
		stats: {
			total_buildings: number;
			buildings_with_roofs: number;
			total_roof_faces: number;
			roof_types: Record<string, number>;
			orientations: Record<string, number>;
			avg_slope: number;
		};
	};
	features: RoofFaceFeature[];
}

/** Color mapping for roof materials */
export const ROOF_MATERIAL_COLORS: Record<
	RoofMaterial,
	[number, number, number, number]
> = {
	roof_terracotta: [180, 100, 80, 255], // Warm red-brown
	roof_slate: [90, 90, 100, 255], // Dark gray-blue
	roof_flat: [140, 140, 145, 255], // Light gray
};

/** Alternative color scheme by roof type */
export const ROOF_TYPE_COLORS: Record<
	RoofType,
	[number, number, number, number]
> = {
	gabled: [180, 100, 80, 255], // Terracotta
	hipped: [160, 90, 70, 255], // Darker terracotta
	flat: [140, 140, 145, 255], // Gray
	mansard: [100, 90, 85, 255], // Dark slate
	complex: [120, 110, 100, 255], // Brown-gray
};

/** Color scheme by orientation (for visualization/debugging) */
export const ROOF_ORIENTATION_COLORS: Record<
	RoofOrientation,
	[number, number, number, number]
> = {
	N: [100, 150, 255, 255], // Blue (cool, north-facing)
	NE: [120, 180, 255, 255],
	E: [255, 200, 100, 255], // Yellow (morning sun)
	SE: [255, 180, 80, 255],
	S: [255, 120, 80, 255], // Orange (warm, south-facing)
	SW: [255, 100, 100, 255],
	W: [255, 150, 150, 255], // Pink (evening sun)
	NW: [150, 130, 200, 255],
	FLAT: [200, 200, 200, 255], // Gray (no direction)
};
