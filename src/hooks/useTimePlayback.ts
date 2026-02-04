/**
 * useTimePlayback Hook
 *
 * Extracted RAF-based time animation for reuse across viewers.
 * Provides smooth time progression with configurable speed and bounds.
 *
 * @example
 * ```typescript
 * function TransitViewer() {
 *   const {
 *     timeOfDay,
 *     setTimeOfDay,
 *     isPlaying,
 *     setIsPlaying,
 *     speed,
 *     setSpeed,
 *     timeSeconds,
 *   } = useTimePlayback({ initialTime: 480 }); // Start at 8:00
 *
 *   return (
 *     <TripsLayer currentTime={timeSeconds} ... />
 *   );
 * }
 * ```
 */

import { useState, useEffect, useCallback, useRef } from "react";

/**
 * Configuration options for the time playback hook.
 */
export interface UseTimePlaybackOptions {
	/** Initial time in minutes since midnight (default: 480 = 8:00) */
	initialTime?: number;
	/** Minimum time in minutes (default: 300 = 5:00) */
	minTime?: number;
	/** Maximum time in minutes (default: 1320 = 22:00) */
	maxTime?: number;
	/** Default speed multiplier (default: 600 = 10 sim-minutes per real second) */
	defaultSpeed?: number;
	/** Whether to auto-play on mount (default: false) */
	autoPlay?: boolean;
}

/**
 * Return type for the useTimePlayback hook.
 */
export interface UseTimePlaybackResult {
	/** Current time of day in minutes since midnight (0-1440) */
	timeOfDay: number;
	/** Set the time of day in minutes */
	setTimeOfDay: (time: number) => void;
	/** Whether time is currently advancing */
	isPlaying: boolean;
	/** Start or stop time progression */
	setIsPlaying: (playing: boolean) => void;
	/** Toggle play/pause state */
	togglePlaying: () => void;
	/** Current speed multiplier */
	speed: number;
	/** Set the speed multiplier */
	setSpeed: (speed: number) => void;
	/** Current time in seconds since midnight (for GTFS timestamps) */
	timeSeconds: number;
	/** Minimum time bound in minutes */
	minTime: number;
	/** Maximum time bound in minutes */
	maxTime: number;
}

/** Default values for time playback */
const DEFAULTS = {
	initialTime: 480, // 8:00 AM
	minTime: 300, // 5:00 AM
	maxTime: 1320, // 10:00 PM
	defaultSpeed: 60, // 60x = 1 sim-minute per real second
	autoPlay: false,
} as const;

/**
 * Hook for smooth time progression using requestAnimationFrame.
 *
 * Features:
 * - Smooth RAF-based animation (no jank)
 * - Configurable speed multiplier (1x to 3600x)
 * - Automatic wrap-around at time bounds
 * - Provides both minutes and seconds for different use cases
 *
 * @param options - Configuration options
 * @returns Time state and control functions
 */
export function useTimePlayback(
	options: UseTimePlaybackOptions = {}
): UseTimePlaybackResult {
	const {
		initialTime = DEFAULTS.initialTime,
		minTime = DEFAULTS.minTime,
		maxTime = DEFAULTS.maxTime,
		defaultSpeed = DEFAULTS.defaultSpeed,
		autoPlay = DEFAULTS.autoPlay,
	} = options;

	// State
	const [timeOfDay, setTimeOfDayState] = useState(initialTime);
	const [isPlaying, setIsPlaying] = useState(autoPlay);
	const [speed, setSpeed] = useState(defaultSpeed);

	// Ref for RAF to access latest state without re-subscribing
	const timeRef = useRef(timeOfDay);
	timeRef.current = timeOfDay;

	// Wrapped setter that clamps to bounds
	const setTimeOfDay = useCallback(
		(time: number) => {
			const clamped = Math.max(minTime, Math.min(maxTime, time));
			setTimeOfDayState(clamped);
		},
		[minTime, maxTime]
	);

	// Toggle helper
	const togglePlaying = useCallback(() => {
		setIsPlaying((prev) => !prev);
	}, []);

	// RAF-based time advancement
	useEffect(() => {
		if (!isPlaying) return;

		let lastTime = performance.now();
		let animationId: number;

		const tick = (now: number) => {
			const deltaMs = now - lastTime;
			lastTime = now;

			// Convert: deltaMs * speed / 60000 = minutes to add
			// speed=600 means 600 sim-seconds per real-second = 10 sim-minutes/sec
			const deltaMinutes = (deltaMs / 1000) * (speed / 60);

			setTimeOfDayState((prev) => {
				const next = prev + deltaMinutes;
				// Wrap at maxTime back to minTime
				return next > maxTime ? minTime : next;
			});

			animationId = requestAnimationFrame(tick);
		};

		animationId = requestAnimationFrame(tick);
		return () => cancelAnimationFrame(animationId);
	}, [isPlaying, speed, minTime, maxTime]);

	// Compute seconds for GTFS timestamps
	const timeSeconds = timeOfDay * 60;

	return {
		timeOfDay,
		setTimeOfDay,
		isPlaying,
		setIsPlaying,
		togglePlaying,
		speed,
		setSpeed,
		timeSeconds,
		minTime,
		maxTime,
	};
}
