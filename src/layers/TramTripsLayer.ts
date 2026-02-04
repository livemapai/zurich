/**
 * Tram Trips Layer Factory
 *
 * Creates a deck.gl TripsLayer for animated tram visualization using GTFS data.
 * Trams move along their routes based on timestamps synchronized with TimeSlider.
 *
 * Data source: VBZ GTFS (Stadt Zürich Open Data)
 *
 * @example
 * ```typescript
 * import { createTramTripsLayer } from "@/layers";
 *
 * const layer = createTramTripsLayer(tramTripsData.trips, {
 * 	currentTime: 28800,
 * 	trailLength: 180,
 * 	opacity: 0.8,
 * });
 * ```
 */

import { TripsLayer } from "@deck.gl/geo-layers";
import type { TramTrip } from "@/types";

// Re-export types for convenience
export type { TramTrip };

/**
 * Configuration for tram trips layer
 */
export interface TramTripsLayerConfig {
	/** Layer ID (default: "tram-trips") */
	id?: string;
	/** Current time in seconds since midnight (0-86400) */
	currentTime: number;
	/** Trail length in seconds (default: 180 = 3 minutes) */
	trailLength?: number;
	/** Layer opacity 0-1 (default: 1.0) */
	opacity?: number;
	/** Whether layer is visible (default: true) */
	visible?: boolean;
	/** Whether layer is pickable (default: false) */
	pickable?: boolean;
	/** Set of visible route short names (undefined = show all routes) */
	visibleRoutes?: Set<string>;
	/**
	 * Flatten paths to 2D (strip z-coordinates).
	 * Use true for MapView with flat basemap, false for FirstPersonView with terrain.
	 * Default: false
	 */
	flatPaths?: boolean;
}

/** Default configuration values */
const DEFAULT_CONFIG: Required<
	Omit<TramTripsLayerConfig, "currentTime" | "visibleRoutes">
> & {
	currentTime: number;
	visibleRoutes: Set<string> | undefined;
} = {
	id: "tram-trips",
	currentTime: 0,
	trailLength: 180,
	opacity: 1.0,
	visible: true,
	pickable: false,
	visibleRoutes: undefined,
	flatPaths: false,
};

/**
 * Parse hex color string to RGBA array.
 *
 * @param hex - Hex color string (e.g., "#00a1e0" or "00a1e0")
 * @param alpha - Alpha value 0-1 (default: 1.0)
 * @returns RGBA array [r, g, b, a] with values 0-255
 *
 * @example
 * ```typescript
 * hexToRgba("#00a1e0", 0.8); // [0, 161, 224, 204]
 * hexToRgba("ff0000", 1.0);  // [255, 0, 0, 255]
 * ```
 */
function hexToRgba(
	hex: string,
	alpha: number = 1.0,
): [number, number, number, number] {
	const cleanHex = hex.replace("#", "");
	let r = parseInt(cleanHex.substring(0, 2), 16);
	let g = parseInt(cleanHex.substring(2, 4), 16);
	let b = parseInt(cleanHex.substring(4, 6), 16);
	const a = Math.round(alpha * 255);

	// Replace pure black with visible dark gray (VBZ lines 7, 50, 51 use #000000)
	if (r === 0 && g === 0 && b === 0) {
		r = 100;
		g = 100;
		b = 100;
	}

	return [r, g, b, a];
}

/**
 * Create a tram trips layer for animated visualization.
 *
 * Renders trams as animated paths along their routes, synchronized with
 * the current time. Each tram is colored by its route's official VBZ color.
 *
 * @param data - Array of TramTrip objects from GTFS data
 * @param config - Layer configuration options
 * @returns Configured TripsLayer instance
 *
 * @example
 * ```typescript
 * const layer = createTramTripsLayer(tripsData.trips, {
 * 	currentTime: timeOfDay * 60,
 * 	trailLength: 180,
 * 	opacity: 0.9,
 * });
 * ```
 */
export function createTramTripsLayer(
	data: TramTrip[],
	config: TramTripsLayerConfig,
): TripsLayer<TramTrip> {
	const cfg = { ...DEFAULT_CONFIG, ...config };

	if (!data || data.length === 0) {
		return new TripsLayer<TramTrip>({
			id: cfg.id,
			data: [],
			visible: false,
		});
	}

	if (cfg.currentTime < 0) {
		return new TripsLayer<TramTrip>({
			id: cfg.id,
			data: [],
			visible: false,
		});
	}

	// Filter by visible routes if specified
	const filteredData = cfg.visibleRoutes
		? data.filter((trip) => cfg.visibleRoutes!.has(trip.route_short_name))
		: data;

	return new TripsLayer<TramTrip>({
		id: cfg.id,
		data: filteredData,
		visible: cfg.visible,
		// Strip z-coordinates for flat MapView, keep 3D for FirstPersonView
		getPath: cfg.flatPaths
			? (d) => d.path.map((p) => [p[0], p[1]] as [number, number])
			: (d) => d.path,
		getTimestamps: (d) => d.timestamps,
		getColor: (d) => hexToRgba(d.route_color, cfg.opacity),
		currentTime: cfg.currentTime,
		trailLength: cfg.trailLength,
		widthMinPixels: 5,
		widthUnits: "meters",
		getWidth: 3.5,
		capRounded: true,
		fadeTrail: true,
		pickable: cfg.pickable,
	});
}
