/**
 * Transit Route Utilities
 *
 * Utility functions for extracting and grouping route information
 * from GTFS trip data. Extracted from ZurichViewer for reuse.
 *
 * @example
 * ```typescript
 * import { extractRouteInfo, groupRoutesByType } from "@/utils/transitRoutes";
 *
 * const routeInfo = extractRouteInfo(trips, visibleRoutes);
 * const grouped = groupRoutesByType(routeInfo);
 * ```
 */

import { RouteType } from "@/types";
import type { RenderableTrip } from "@/types";

/**
 * Route information for display in UI panels.
 */
export interface RouteInfo {
	/** Route short name (e.g., "10", "31") */
	name: string;
	/** GTFS route type (Tram, Bus, etc.) */
	type: RouteType;
	/** Route color in hex format */
	color: string;
	/** Number of trips for this route */
	tripCount: number;
	/** Whether this route is currently visible */
	visible: boolean;
}

/**
 * Extract unique route information from trip data.
 *
 * Deduplicates trips by route name, counting trips per route
 * and marking visibility based on the visibleRoutes set.
 *
 * @param trips - Array of renderable trips
 * @param visibleRoutes - Set of visible route names
 * @returns Sorted array of route info objects
 *
 * @example
 * ```typescript
 * const trips = useGTFSTrips(timeSeconds).trips;
 * const visibleRoutes = new Set(["10", "11", "12"]);
 * const routeInfo = extractRouteInfo(trips, visibleRoutes);
 * // Returns: [{ name: "10", type: 0, color: "#00a1e0", tripCount: 42, visible: true }, ...]
 * ```
 */
export function extractRouteInfo(
	trips: RenderableTrip[],
	visibleRoutes: Set<string>
): RouteInfo[] {
	if (!trips?.length) return [];

	// Group trips by route to get unique routes with their properties
	const routeMap = new Map<
		string,
		{ type: RouteType; color: string; tripCount: number }
	>();

	for (const trip of trips) {
		const existing = routeMap.get(trip.route_short_name);
		if (existing) {
			existing.tripCount++;
		} else {
			routeMap.set(trip.route_short_name, {
				type: trip.route_type,
				color: trip.route_color,
				tripCount: 1,
			});
		}
	}

	return Array.from(routeMap.entries())
		.map(([name, info]) => ({
			name,
			type: info.type,
			color: info.color,
			tripCount: info.tripCount,
			visible: visibleRoutes.has(name),
		}))
		.sort((a, b) => {
			// Sort by type first, then by name (numerically if possible)
			if (a.type !== b.type) return a.type - b.type;
			const aNum = parseInt(a.name, 10);
			const bNum = parseInt(b.name, 10);
			if (!isNaN(aNum) && !isNaN(bNum)) return aNum - bNum;
			return a.name.localeCompare(b.name);
		});
}

/**
 * Group route info by route type.
 *
 * Creates a map from RouteType to arrays of RouteInfo,
 * sorted by type (Tram first, then Bus, etc.).
 *
 * @param routes - Array of route info objects
 * @returns Map from RouteType to RouteInfo arrays
 *
 * @example
 * ```typescript
 * const grouped = groupRoutesByType(routeInfo);
 * // Returns: Map {
 * //   0 (Tram) => [{ name: "2", ... }, { name: "10", ... }],
 * //   3 (Bus) => [{ name: "31", ... }, { name: "32", ... }]
 * // }
 * ```
 */
export function groupRoutesByType(
	routes: RouteInfo[]
): Map<RouteType, RouteInfo[]> {
	const grouped = new Map<RouteType, RouteInfo[]>();

	for (const route of routes) {
		const existing = grouped.get(route.type) ?? [];
		existing.push(route);
		grouped.set(route.type, existing);
	}

	// Sort entries by route type (trams first, then buses, etc.)
	return new Map(
		Array.from(grouped.entries()).sort(([a], [b]) => a - b)
	);
}

/**
 * Get all unique route names from trips.
 *
 * @param trips - Array of renderable trips
 * @returns Set of route short names
 */
export function getAllRouteNames(trips: RenderableTrip[]): Set<string> {
	return new Set(trips.map((trip) => trip.route_short_name));
}

/**
 * Get route names filtered by type.
 *
 * @param trips - Array of renderable trips
 * @param routeType - GTFS route type to filter by
 * @returns Set of route short names of the specified type
 */
export function getRouteNamesByType(
	trips: RenderableTrip[],
	routeType: RouteType
): Set<string> {
	return new Set(
		trips
			.filter((trip) => trip.route_type === routeType)
			.map((trip) => trip.route_short_name)
	);
}
