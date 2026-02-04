/**
 * TransitViewer Component
 *
 * A clean, focused visualization of Zurich's public transit network.
 * Inspired by the deck.gl trips example with dark theme and animated trails.
 *
 * @example
 * ```tsx
 * <TransitViewer
 *   onLoadProgress={(p) => setProgress(p)}
 *   onError={(e) => setError(e)}
 * />
 * ```
 */

import { useState, useEffect, useMemo, useCallback } from "react";
import DeckGL from "@deck.gl/react";
import { MapView, LightingEffect, AmbientLight, PointLight } from "@deck.gl/core";

import { useTimePlayback, useGTFSTrips } from "@/hooks";
import { createTramTripsLayer, createMapTileLayer, CARTO_DARK_URL } from "@/layers";
import { CONFIG } from "@/lib/config";
import { RouteType } from "@/types";
import { extractRouteInfo, getAllRouteNames, getRouteNamesByType } from "@/utils/transitRoutes";

import { TransitControls } from "./TransitControls";
import { RouteFilterPanel } from "./RouteFilterPanel";

/** Props for TransitViewer component */
export interface TransitViewerProps {
	/** Progress callback (0-100) */
	onLoadProgress?: (progress: number) => void;
	/** Error callback */
	onError?: (error: Error) => void;
}

/** Initial camera position - centered on Zurich HB */
const INITIAL_VIEW_STATE = {
	longitude: 8.5417,
	latitude: 47.3769,
	zoom: 13,
	pitch: 45,
	bearing: 0,
};

/** Create lighting effect for depth */
const createLightingEffect = () =>
	new LightingEffect({
		ambientLight: new AmbientLight({
			color: [255, 255, 255],
			intensity: 1.0,
		}),
		pointLight: new PointLight({
			color: [255, 255, 255],
			intensity: 2.0,
			position: [8.54, 47.38, 8000],
		}),
	});


/**
 * TransitViewer - Main transit visualization component
 *
 * Features:
 * - Dark themed map with animated transit trails
 * - Time playback controls with variable speed
 * - Route filtering by type and individual lines
 */
export function TransitViewer({ onLoadProgress, onError }: TransitViewerProps) {
	// Time playback state (extracted hook)
	const {
		timeOfDay,
		setTimeOfDay,
		isPlaying,
		togglePlaying,
		speed,
		setSpeed,
		timeSeconds,
		minTime,
		maxTime,
	} = useTimePlayback({
		initialTime: 480, // 8:00 AM
		autoPlay: true,
	});

	// Trip data from GTFS binary/JSON
	const {
		trips,
		isLoading: tripsLoading,
		totalTrips,
		isBinaryMode,
		error: tripsError,
	} = useGTFSTrips(timeSeconds, {
		binaryUrl: CONFIG.data.tramTripsBinary,
		enabled: true,
	});

	// Route visibility state
	const [visibleRoutes, setVisibleRoutes] = useState<Set<string>>(new Set());
	const [showRoutePanel, setShowRoutePanel] = useState(false);

	// View state
	const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);

	// Initialize all routes as visible when trips load
	useEffect(() => {
		if (trips.length > 0 && visibleRoutes.size === 0) {
			const allRoutes = getAllRouteNames(trips);
			setVisibleRoutes(allRoutes);
		}
	}, [trips, visibleRoutes.size]);

	// Progress reporting
	useEffect(() => {
		if (tripsLoading) {
			onLoadProgress?.(30);
		} else {
			onLoadProgress?.(100);
		}
	}, [tripsLoading, onLoadProgress]);

	// Error handling
	useEffect(() => {
		if (tripsError) {
			onError?.(new Error(tripsError));
		}
	}, [tripsError, onError]);

	// Route info for filter panel
	const routeInfo = useMemo(
		() => extractRouteInfo(trips, visibleRoutes),
		[trips, visibleRoutes]
	);

	// Handle individual route toggle
	const handleRouteToggle = useCallback((routeName: string) => {
		setVisibleRoutes((prev) => {
			const next = new Set(prev);
			if (next.has(routeName)) {
				next.delete(routeName);
			} else {
				next.add(routeName);
			}
			return next;
		});
	}, []);

	// Handle toggling all routes of a type
	const handleRouteTypeToggle = useCallback(
		(routeType: RouteType, enable: boolean) => {
			const routesOfType = getRouteNamesByType(trips, routeType);

			setVisibleRoutes((prev) => {
				const next = new Set(prev);
				for (const route of routesOfType) {
					if (enable) {
						next.add(route);
					} else {
						next.delete(route);
					}
				}
				return next;
			});
		},
		[trips]
	);

	// Handle toggling all routes
	const handleAllRoutesToggle = useCallback(
		(enable: boolean) => {
			if (enable) {
				setVisibleRoutes(getAllRouteNames(trips));
			} else {
				setVisibleRoutes(new Set());
			}
		},
		[trips]
	);

	// Toggle route panel with R key
	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.code === "KeyR" && !e.ctrlKey && !e.metaKey) {
				setShowRoutePanel((prev) => !prev);
			}
			// Space to toggle play
			if (e.code === "Space" && !e.ctrlKey && !e.metaKey) {
				e.preventDefault();
				togglePlaying();
			}
		};
		window.addEventListener("keydown", handleKeyDown);
		return () => window.removeEventListener("keydown", handleKeyDown);
	}, [togglePlaying]);

	// Lighting effect (memoized)
	const lightingEffect = useMemo(() => createLightingEffect(), []);

	// Create layers
	const layers = useMemo(() => {
		const basemap = createMapTileLayer({
			id: "transit-basemap",
			tileUrl: CARTO_DARK_URL,
			flatBounds: true, // Use 2D bounds for MapView with flat transit data
		});

		if (trips.length === 0) return [basemap];

		return [
			basemap,
			createTramTripsLayer(trips, {
				currentTime: timeSeconds,
				trailLength: 180,
				opacity: 0.9,
				visibleRoutes: visibleRoutes.size > 0 ? visibleRoutes : undefined,
				flatPaths: true, // Use 2D paths for MapView
			}),
		];
	}, [trips, timeSeconds, visibleRoutes]);

	// View configuration
	const views = useMemo(
		() =>
			new MapView({
				id: "transit-map",
				controller: true,
				repeat: true,
			}),
		[]
	);

	// Handle view state change
	const handleViewStateChange = useCallback(
		(params: { viewState: Record<string, unknown> }) => {
			setViewState(params.viewState as typeof INITIAL_VIEW_STATE);
		},
		[]
	);

	return (
		<div className="transit-viewer">
			<DeckGL
				views={views}
				viewState={viewState}
				onViewStateChange={handleViewStateChange}
				controller={true}
				layers={layers}
				effects={[lightingEffect]}
				style={{ background: "#0a0a0f" }}
				onError={(error) => {
					console.error("DeckGL error:", error);
					onError?.(error instanceof Error ? error : new Error(String(error)));
				}}
			/>

			{/* Time controls */}
			<TransitControls
				timeOfDay={timeOfDay}
				onTimeChange={setTimeOfDay}
				isPlaying={isPlaying}
				onPlayPause={togglePlaying}
				speed={speed}
				onSpeedChange={setSpeed}
				tripCount={trips.length}
				totalTrips={totalTrips}
				minTime={minTime}
				maxTime={maxTime}
				isBinaryMode={isBinaryMode}
			/>

			{/* Route filter panel */}
			<RouteFilterPanel
				visible={showRoutePanel}
				routes={routeInfo}
				onRouteToggle={handleRouteToggle}
				onRouteTypeToggle={handleRouteTypeToggle}
				onAllRoutesToggle={handleAllRoutesToggle}
				onClose={() => setShowRoutePanel(false)}
			/>

			{/* Filter toggle button */}
			<button
				className="transit-filter-toggle"
				onClick={() => setShowRoutePanel((prev) => !prev)}
				title="Toggle route filter (R)"
			>
				<span className="transit-filter-icon">⚙</span>
				<span className="transit-filter-label">Routes</span>
			</button>

			{/* Keyboard hints */}
			<div className="transit-hints">
				<span><kbd>Space</kbd> Play/Pause</span>
				<span><kbd>R</kbd> Routes</span>
			</div>
		</div>
	);
}
