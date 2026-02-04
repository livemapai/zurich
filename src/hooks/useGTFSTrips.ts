/**
 * useGTFSTrips Hook
 *
 * React hook for streaming GTFS trip data with automatic chunk management.
 * Loads master index once, then fetches hourly chunks on-demand as time changes.
 *
 * Features:
 * - Automatic chunk loading based on current hour
 * - Time-window filtering for visible trips
 * - Memory-efficient with LRU chunk eviction
 * - Loading state for UI feedback
 *
 * @example
 * ```typescript
 * function TransitLayer({ timeOfDay }: { timeOfDay: number }) {
 *   const { trips, isLoading, error } = useGTFSTrips(timeOfDay * 60);
 *
 *   if (isLoading) return <LoadingIndicator />;
 *   if (error) return <ErrorMessage error={error} />;
 *
 *   return <TripsLayer data={trips} currentTime={timeOfDay * 60} />;
 * }
 * ```
 */

import { useState, useEffect, useRef, useMemo } from "react";
import type { RenderableTrip, BinaryRoute } from "@/types";
import { GTFSChunkManager } from "@/lib/gtfs";

/**
 * Configuration for the GTFS trips hook.
 */
export interface UseGTFSTripsConfig {
	/** URL to the binary GTFS file */
	binaryUrl?: string;
	/** Whether to enable the hook (default: true) */
	enabled?: boolean;
	/** Fallback to JSON if binary not available */
	fallbackJsonUrl?: string;
}

/**
 * Return type for the useGTFSTrips hook.
 */
export interface UseGTFSTripsResult {
	/** Trips ready for rendering */
	trips: RenderableTrip[];
	/** Whether initial index is loading */
	isLoading: boolean;
	/** Whether chunks are currently being fetched */
	isChunksLoading: boolean;
	/** Error message if loading failed */
	error: string | null;
	/** Set of currently loaded hours */
	loadedHours: Set<number>;
	/** Total trips across all loaded chunks */
	totalTrips: number;
	/** All available routes */
	routes: BinaryRoute[];
	/** Whether using binary format (vs JSON fallback) */
	isBinaryMode: boolean;
}

/**
 * Default binary GTFS URL.
 */
const DEFAULT_BINARY_URL = "/data/gtfs/gtfs-trips.bin";

/**
 * Default JSON fallback URL.
 */
const DEFAULT_JSON_URL = "/data/zurich-tram-trips.json";

/**
 * JSON trip data structure for fallback mode.
 */
interface JsonTripData {
	metadata: { trip_count: number };
	trips: Array<{
		route_short_name: string;
		route_type: number;
		route_color: string;
		headsign: string;
		path: [number, number, number][];
		timestamps: number[];
	}>;
}

/**
 * Hook for streaming GTFS trip data with automatic chunk management.
 * Tries binary format first, falls back to JSON if binary unavailable.
 *
 * @param currentTimeSeconds - Current time in seconds since midnight (0-86400)
 * @param config - Optional configuration
 * @returns Trip data and loading state
 */
export function useGTFSTrips(
	currentTimeSeconds: number,
	config: UseGTFSTripsConfig = {}
): UseGTFSTripsResult {
	const {
		binaryUrl = DEFAULT_BINARY_URL,
		enabled = true,
		fallbackJsonUrl = DEFAULT_JSON_URL,
	} = config;

	// State
	const [trips, setTrips] = useState<RenderableTrip[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [isChunksLoading, setIsChunksLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [loadedHours, setLoadedHours] = useState<Set<number>>(new Set());
	const [totalTrips, setTotalTrips] = useState(0);
	const [routes, setRoutes] = useState<BinaryRoute[]>([]);
	const [isBinaryMode, setIsBinaryMode] = useState(true);

	// JSON fallback data (when binary unavailable)
	const [jsonTrips, setJsonTrips] = useState<JsonTripData | null>(null);

	// Manager ref (persists across renders)
	const managerRef = useRef<GTFSChunkManager | null>(null);
	const initializingRef = useRef(false);

	// Calculate current hour
	const currentHour = useMemo(
		() => Math.floor(currentTimeSeconds / 3600),
		[currentTimeSeconds]
	);

	// Initialize manager - tries binary first, falls back to JSON
	useEffect(() => {
		if (!enabled) return;
		if (initializingRef.current) return;

		async function init() {
			initializingRef.current = true;
			setIsLoading(true);
			setError(null);

			try {
				// Try binary format first
				const manager = new GTFSChunkManager(binaryUrl);
				await manager.initialize();

				// Load initial chunks BEFORE marking as ready
				// This prevents the "no trips until 9 AM" bug where chunk loading
				// was deferred to an effect that wouldn't run until currentHour changed
				await manager.updateActiveChunks(currentHour);

				managerRef.current = manager;
				setRoutes(manager.getRoutes());
				setIsBinaryMode(true);

				// Update state with loaded chunk info
				const state = manager.getLoadingState();
				setLoadedHours(state.loadedHours);
				setTotalTrips(state.totalTrips);

				setIsLoading(false);

				console.log(`[useGTFSTrips] Initialized with binary format, loaded hour ${currentHour}`);
			} catch (err) {
				console.warn("[useGTFSTrips] Binary format failed, falling back to JSON", err);

				// Binary failed, try JSON fallback
				try {
					const response = await fetch(fallbackJsonUrl);
					if (!response.ok) {
						throw new Error(`HTTP ${response.status}`);
					}
					const data: JsonTripData = await response.json();

					setJsonTrips(data);
					setIsBinaryMode(false);
					setTotalTrips(data.metadata.trip_count);
					setIsLoading(false);

					console.log(`[useGTFSTrips] Loaded JSON fallback: ${data.metadata.trip_count} trips`);
				} catch (jsonErr) {
					setError(`Failed to load GTFS data: ${jsonErr}`);
					setIsLoading(false);
				}
			} finally {
				initializingRef.current = false;
			}
		}

		init();

		// Cleanup on unmount
		return () => {
			if (managerRef.current) {
				managerRef.current.dispose();
				managerRef.current = null;
			}
		};
	// Note: currentHour is included because we load initial chunks during init.
	// The initializingRef prevents re-initialization if currentHour changes.
	}, [enabled, binaryUrl, fallbackJsonUrl, currentHour]);

	// Update chunks when hour changes
	useEffect(() => {
		if (!enabled || !managerRef.current) return;

		async function updateChunks() {
			const manager = managerRef.current;
			if (!manager) return;

			setIsChunksLoading(true);

			try {
				await manager.updateActiveChunks(currentHour);

				// Update state from manager
				const state = manager.getLoadingState();
				setLoadedHours(state.loadedHours);
				setTotalTrips(state.totalTrips);
				setIsChunksLoading(state.isChunksLoading);
			} catch (err) {
				console.error("[useGTFSTrips] Failed to update chunks:", err);
			} finally {
				setIsChunksLoading(false);
			}
		}

		updateChunks();
	}, [enabled, currentHour]);

	// Get visible trips when time changes (more frequent than hour changes)
	useEffect(() => {
		if (!enabled) return;

		// Binary mode: use ChunkManager
		if (isBinaryMode && managerRef.current?.isReady()) {
			const visibleTrips = managerRef.current.getVisibleTrips(currentTimeSeconds);
			setTrips(visibleTrips);
			return;
		}

		// JSON fallback mode: filter trips by time window
		if (!isBinaryMode && jsonTrips) {
			const timeWindow = 1800; // ±30 minutes in seconds

			const filteredTrips = jsonTrips.trips
				.filter((trip) => {
					if (!trip.timestamps?.length) return false;
					const firstTimestamp = trip.timestamps[0] ?? 0;
					const lastTimestamp = trip.timestamps[trip.timestamps.length - 1] ?? 0;

					// Trip is active if it overlaps with our time window
					return (
						firstTimestamp <= currentTimeSeconds + timeWindow &&
						lastTimestamp >= currentTimeSeconds - timeWindow
					);
				})
				.map((trip): RenderableTrip => ({
					path: trip.path,
					timestamps: trip.timestamps,
					route_color: trip.route_color,
					route_short_name: trip.route_short_name,
					route_type: trip.route_type,
					headsign: trip.headsign,
					route_id: trip.route_short_name, // VBZ uses route_short_name as route_id
				}));

			setTrips(filteredTrips);
		}
	}, [enabled, currentTimeSeconds, loadedHours, isBinaryMode, jsonTrips]); // Re-run when chunks load or mode changes

	return {
		trips,
		isLoading,
		isChunksLoading,
		error,
		loadedHours,
		totalTrips,
		routes,
		isBinaryMode,
	};
}

/**
 * Helper hook to check if binary GTFS is available.
 * Useful for conditional rendering of binary vs JSON mode.
 */
export function useGTFSBinaryAvailable(binaryUrl: string = DEFAULT_BINARY_URL): boolean {
	const [available, setAvailable] = useState<boolean | null>(null);

	useEffect(() => {
		async function check() {
			try {
				// HEAD request to check if file exists
				const response = await fetch(binaryUrl, { method: "HEAD" });
				setAvailable(response.ok);
			} catch {
				setAvailable(false);
			}
		}

		check();
	}, [binaryUrl]);

	return available ?? false;
}
