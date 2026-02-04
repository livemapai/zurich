/**
 * Vehicle Position Utilities
 *
 * Functions for interpolating vehicle positions along their paths
 * based on GTFS timestamp data. Used for vehicle labels.
 *
 * @example
 * ```typescript
 * const position = getVehiclePosition(trip, currentTimeSeconds);
 * if (position) {
 *   renderLabel(trip.route_short_name, position);
 * }
 * ```
 */

import type { RenderableTrip } from "@/types";

/** Vehicle position with route metadata for labeling */
export interface VehiclePosition {
	/** Route short name (e.g., "11", "4") */
	routeName: string;
	/** Current position [lng, lat] */
	position: [number, number];
	/** Route color in hex format */
	color: string;
	/** Direction of travel in degrees (0 = north, 90 = east) */
	bearing: number;
}

/**
 * Calculate bearing between two points.
 *
 * @param from - Start point [lng, lat]
 * @param to - End point [lng, lat]
 * @returns Bearing in degrees (0 = north, 90 = east)
 */
function calculateBearing(
	from: [number, number],
	to: [number, number]
): number {
	const dLng = to[0] - from[0];
	const dLat = to[1] - from[1];

	// Convert to radians
	const y = dLng * Math.cos((from[1] * Math.PI) / 180);
	const x = dLat;

	// Calculate angle and convert to degrees
	let bearing = (Math.atan2(y, x) * 180) / Math.PI;

	// Normalize to 0-360
	if (bearing < 0) bearing += 360;

	return bearing;
}

/**
 * Get interpolated vehicle position along a trip path.
 *
 * Uses binary search to find the current segment, then linearly
 * interpolates the position based on elapsed time within that segment.
 *
 * @param trip - Trip with path and timestamps
 * @param currentTime - Current time in seconds since midnight
 * @returns Position with metadata, or null if trip is not active
 *
 * @example
 * ```typescript
 * // At 8:15 AM (8 * 60 * 60 + 15 * 60 = 29700 seconds)
 * const pos = getVehiclePosition(trip, 29700);
 * // Returns: { routeName: "11", position: [8.54, 47.37], color: "#00a1e0", bearing: 45 }
 * ```
 */
export function getVehiclePosition(
	trip: RenderableTrip,
	currentTime: number
): VehiclePosition | null {
	const { timestamps, path, route_short_name, route_color } = trip;

	// Trip needs at least 2 points
	if (timestamps.length < 2 || path.length < 2) {
		return null;
	}

	const startTime = timestamps[0]!;
	const endTime = timestamps[timestamps.length - 1]!;

	// Trip not active (hasn't started or already finished)
	if (currentTime < startTime || currentTime > endTime) {
		return null;
	}

	// Binary search to find the segment containing currentTime
	let lo = 0;
	let hi = timestamps.length - 1;

	while (lo < hi) {
		const mid = (lo + hi) >> 1;
		if (timestamps[mid]! <= currentTime) {
			lo = mid + 1;
		} else {
			hi = mid;
		}
	}

	// lo is now the first index where timestamp > currentTime
	// So the segment is [lo-1, lo]
	const i = Math.max(0, lo - 1);
	const nextI = Math.min(i + 1, timestamps.length - 1);

	// Handle edge case where we're exactly at the end
	if (i === nextI) {
		const point = path[i];
		if (!point) return null;
		return {
			routeName: route_short_name,
			position: [point[0], point[1]],
			color: route_color,
			bearing: 0,
		};
	}

	// Get points safely
	const point1 = path[i];
	const point2 = path[nextI];
	if (!point1 || !point2) return null;

	// Calculate interpolation factor
	const segmentDuration = timestamps[nextI]! - timestamps[i]!;
	const t = segmentDuration > 0
		? (currentTime - timestamps[i]!) / segmentDuration
		: 0;

	// Clamp t to [0, 1]
	const tClamped = Math.max(0, Math.min(1, t));

	// Interpolate position
	const lng1 = point1[0];
	const lat1 = point1[1];
	const lng2 = point2[0];
	const lat2 = point2[1];

	const lng = lng1 + tClamped * (lng2 - lng1);
	const lat = lat1 + tClamped * (lat2 - lat1);

	// Calculate bearing from current segment
	const bearing = calculateBearing([lng1, lat1], [lng2, lat2]);

	return {
		routeName: route_short_name,
		position: [lng, lat],
		color: route_color,
		bearing,
	};
}

/**
 * Get all active vehicle positions from a list of trips.
 *
 * Filters trips to only those currently active (between start and end times),
 * then calculates interpolated positions for each.
 *
 * @param trips - Array of trips to check
 * @param currentTime - Current time in seconds since midnight
 * @param visibleRoutes - Optional set of visible route names (for filtering)
 * @returns Array of vehicle positions for active, visible trips
 *
 * @example
 * ```typescript
 * const positions = getActiveVehiclePositions(trips, timeSeconds, visibleRoutes);
 * // Use with TextLayer for labels
 * ```
 */
export function getActiveVehiclePositions(
	trips: RenderableTrip[],
	currentTime: number,
	visibleRoutes?: Set<string>
): VehiclePosition[] {
	const positions: VehiclePosition[] = [];

	for (const trip of trips) {
		// Skip if route not visible
		if (visibleRoutes && !visibleRoutes.has(trip.route_short_name)) {
			continue;
		}

		const position = getVehiclePosition(trip, currentTime);
		if (position) {
			positions.push(position);
		}
	}

	return positions;
}

/**
 * Deduplicate vehicle positions by route name.
 *
 * When multiple vehicles of the same route are nearby, only show one label.
 * Uses a simple grid-based approach to avoid clustered labels.
 *
 * @param positions - Array of vehicle positions
 * @param gridSize - Grid cell size in degrees (default: 0.001 ≈ 100m)
 * @returns Deduplicated positions with one vehicle per route per grid cell
 */
export function deduplicateByGrid(
	positions: VehiclePosition[],
	gridSize: number = 0.001
): VehiclePosition[] {
	// Track which route+grid combinations we've seen
	const seen = new Set<string>();
	const result: VehiclePosition[] = [];

	for (const pos of positions) {
		// Calculate grid cell
		const gridX = Math.floor(pos.position[0] / gridSize);
		const gridY = Math.floor(pos.position[1] / gridSize);
		const key = `${pos.routeName}:${gridX}:${gridY}`;

		if (!seen.has(key)) {
			seen.add(key);
			result.push(pos);
		}
	}

	return result;
}
