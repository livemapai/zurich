/**
 * useViewportBounds Hook
 *
 * Extracts geographic bounds from deck.gl viewState using WebMercatorViewport.
 * Debounces updates to avoid excessive recalculation during pan/zoom.
 *
 * @example
 * ```tsx
 * const bounds = useViewportBounds(viewState, width, height);
 * const visibleRoutes = getRoutesInViewport(trips, bounds);
 * ```
 */

import { useMemo, useState, useEffect, useRef } from "react";
import { WebMercatorViewport } from "@deck.gl/core";

/** Geographic bounding box in WGS84 coordinates */
export interface ViewportBounds {
	/** Minimum longitude (west edge) */
	minLng: number;
	/** Maximum longitude (east edge) */
	maxLng: number;
	/** Minimum latitude (south edge) */
	minLat: number;
	/** Maximum latitude (north edge) */
	maxLat: number;
}

/** Minimum viewState properties needed for bounds calculation */
export interface MinimalViewState {
	longitude: number;
	latitude: number;
	zoom: number;
	pitch?: number;
	bearing?: number;
}

/**
 * Calculate viewport bounds from viewState (no debouncing).
 * Useful for immediate bounds calculation in event handlers.
 *
 * @param viewState - deck.gl view state with position and zoom
 * @param width - Viewport width in pixels
 * @param height - Viewport height in pixels
 * @returns Geographic bounding box
 */
export function getViewportBounds(
	viewState: MinimalViewState,
	width: number,
	height: number
): ViewportBounds {
	// Create a WebMercatorViewport to unproject screen coordinates
	const viewport = new WebMercatorViewport({
		width,
		height,
		longitude: viewState.longitude,
		latitude: viewState.latitude,
		zoom: viewState.zoom,
		pitch: viewState.pitch ?? 0,
		bearing: viewState.bearing ?? 0,
	});

	// Get corners of the viewport in geographic coordinates
	// Note: For tilted views (pitch > 0), this is an approximation
	const nw = viewport.unproject([0, 0]) as [number, number]; // Top-left
	const ne = viewport.unproject([width, 0]) as [number, number]; // Top-right
	const se = viewport.unproject([width, height]) as [number, number]; // Bottom-right
	const sw = viewport.unproject([0, height]) as [number, number]; // Bottom-left

	// Calculate bounding box from all four corners
	// This handles rotated/tilted views where corners don't align with cardinal directions
	return {
		minLng: Math.min(nw[0], ne[0], se[0], sw[0]),
		maxLng: Math.max(nw[0], ne[0], se[0], sw[0]),
		minLat: Math.min(nw[1], ne[1], se[1], sw[1]),
		maxLat: Math.max(nw[1], ne[1], se[1], sw[1]),
	};
}

/**
 * Hook to get debounced viewport bounds from deck.gl viewState.
 *
 * Updates are debounced to avoid excessive recalculation during
 * continuous pan/zoom operations. The bounds expand slightly to
 * prevent routes from popping in/out at edges during interaction.
 *
 * @param viewState - deck.gl view state
 * @param width - Viewport width in pixels
 * @param height - Viewport height in pixels
 * @param debounceMs - Debounce delay in milliseconds (default: 100)
 * @returns Geographic bounding box, debounced
 */
export function useViewportBounds(
	viewState: MinimalViewState,
	width: number,
	height: number,
	debounceMs: number = 100
): ViewportBounds {
	// Calculate immediate bounds for memoization
	const immediateBounds = useMemo(
		() => getViewportBounds(viewState, width, height),
		[viewState.longitude, viewState.latitude, viewState.zoom, viewState.pitch ?? 0, viewState.bearing ?? 0, width, height]
	);

	// Debounced state
	const [debouncedBounds, setDebouncedBounds] = useState(immediateBounds);
	const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	// Debounce the bounds updates
	useEffect(() => {
		if (timeoutRef.current) {
			clearTimeout(timeoutRef.current);
		}

		timeoutRef.current = setTimeout(() => {
			setDebouncedBounds(immediateBounds);
		}, debounceMs);

		return () => {
			if (timeoutRef.current) {
				clearTimeout(timeoutRef.current);
			}
		};
	}, [immediateBounds, debounceMs]);

	return debouncedBounds;
}

/**
 * Expand bounds by a percentage to prevent edge popping.
 *
 * @param bounds - Original bounds
 * @param expandFactor - Expansion factor (0.1 = 10% expansion)
 * @returns Expanded bounds
 */
export function expandBounds(
	bounds: ViewportBounds,
	expandFactor: number = 0.1
): ViewportBounds {
	const lngRange = bounds.maxLng - bounds.minLng;
	const latRange = bounds.maxLat - bounds.minLat;

	return {
		minLng: bounds.minLng - lngRange * expandFactor,
		maxLng: bounds.maxLng + lngRange * expandFactor,
		minLat: bounds.minLat - latRange * expandFactor,
		maxLat: bounds.maxLat + latRange * expandFactor,
	};
}
