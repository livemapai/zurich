/**
 * Binary GTFS Types
 *
 * Type definitions for the binary GTFS format with shape deduplication
 * and hourly chunking for efficient streaming.
 *
 * Binary format allows:
 * - HTTP Range requests for on-demand chunk loading
 * - 95% memory reduction vs full JSON
 * - Direct TypedArray usage with deck.gl
 */

import { RouteType } from "./index";

// ============================================================================
// Master Index Types (loaded once at startup)
// ============================================================================

/**
 * Deduplicated shape data.
 * Many trips share the same route shape - storing once saves ~80% of data.
 */
export interface BinaryShape {
	/** Number of coordinate points in this shape */
	pointCount: number;
	/** Coordinate data as Float32Array [lng, lat, elev, lng, lat, elev, ...] */
	coordinates: Float32Array;
}

/**
 * Route metadata from the route lookup table.
 */
export interface BinaryRoute {
	/** Short route name (e.g., "10", "11", "33") */
	name: string;
	/** GTFS route type (0=Tram, 3=Bus, etc.) */
	type: RouteType;
	/** Route color as RGB tuple [r, g, b] */
	color: [number, number, number];
}

/**
 * Chunk metadata for HTTP Range request targeting.
 */
export interface ChunkInfo {
	/** Hour this chunk covers (4-27 for overnight support) */
	hour: number;
	/** Byte offset in the binary file */
	byteOffset: number;
	/** Byte size of this chunk */
	byteSize: number;
}

/**
 * Master index loaded at startup (~7MB).
 * Contains all shapes and lookup tables, enabling efficient trip rendering.
 */
export interface GTFSMasterIndex {
	/** Version of the binary format */
	version: number;
	/** Map of shape index to shape data */
	shapes: Map<number, BinaryShape>;
	/** Map of route index to route metadata */
	routes: Map<number, BinaryRoute>;
	/** Map of headsign index to headsign string */
	headsigns: Map<number, string>;
	/** Map of hour to chunk info for Range requests */
	chunkIndex: Map<number, ChunkInfo>;
	/** Total byte size of master index (for progress reporting) */
	indexSize: number;
}

// ============================================================================
// Chunk Types (loaded on-demand per hour)
// ============================================================================

/**
 * A trip as loaded from binary chunk.
 * References shapes/routes/headsigns by index into master tables.
 */
export interface BinaryTrip {
	/** Index into master shape table */
	shapeIndex: number;
	/** Index into master route table */
	routeIndex: number;
	/** Index into master headsign table */
	headsignIndex: number;
	/** Timestamps as Float32Array (seconds since midnight) */
	timestamps: Float32Array;
	/** First timestamp for quick filtering */
	startTime: number;
}

/**
 * A loaded chunk with all trips for a specific hour.
 */
export interface LoadedChunk {
	/** Hour this chunk covers */
	hour: number;
	/** All trips starting in this hour */
	trips: BinaryTrip[];
	/** When this chunk was loaded (for LRU eviction) */
	loadedAt: number;
}

// ============================================================================
// Renderable Types (passed to deck.gl layer)
// ============================================================================

/**
 * Trip data resolved for rendering.
 * This is what the TramTripsLayer expects - coordinates + timestamps as arrays.
 */
export interface RenderableTrip {
	/** Path coordinates: [lng, lat, elevation][] */
	path: [number, number, number][];
	/** Timestamps in seconds since midnight, one per path point */
	timestamps: number[];
	/** Route color in hex format (e.g., "#00a1e0") */
	route_color: string;
	/** Short route name (e.g., "10", "11") */
	route_short_name: string;
	/** GTFS route type (0=Tram, 3=Bus, etc.) */
	route_type: RouteType;
	/** Trip destination/headsign */
	headsign: string;
	/** Route ID (same as route_short_name for VBZ) */
	route_id: string;
}

// ============================================================================
// Loading State Types
// ============================================================================

/**
 * State of the GTFS chunk manager.
 */
export interface GTFSLoadingState {
	/** Whether master index is loading */
	isIndexLoading: boolean;
	/** Whether any chunks are currently loading */
	isChunksLoading: boolean;
	/** Error message if loading failed */
	error: string | null;
	/** Set of hours currently being loaded */
	loadingHours: Set<number>;
	/** Set of hours already loaded */
	loadedHours: Set<number>;
	/** Total trips available across all loaded chunks */
	totalTrips: number;
}

// ============================================================================
// Binary Format Constants
// ============================================================================

/**
 * Magic number for binary format validation.
 */
export const GTFS_BINARY_MAGIC = 0x53465447; // "GTFS" as little-endian uint32

/**
 * Current binary format version.
 */
export const GTFS_BINARY_VERSION = 1;

/**
 * Header size in bytes (8 uint32 fields).
 */
export const GTFS_HEADER_SIZE = 32;

/**
 * Trip record header size in bytes (before timestamps).
 */
export const GTFS_TRIP_HEADER_SIZE = 20;

/**
 * Minimum supported hour (4:00 AM).
 */
export const GTFS_MIN_HOUR = 4;

/**
 * Maximum supported hour (27:00 = 3:00 AM next day).
 */
export const GTFS_MAX_HOUR = 27;
