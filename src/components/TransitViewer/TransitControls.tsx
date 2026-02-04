/**
 * TransitControls Component
 *
 * Minimal dark-themed controls for time playback.
 * Positioned at bottom center with cyan accent color.
 *
 * @example
 * ```tsx
 * <TransitControls
 *   timeOfDay={480}
 *   onTimeChange={setTimeOfDay}
 *   isPlaying={true}
 *   onPlayPause={() => setIsPlaying(!isPlaying)}
 *   speed={600}
 *   onSpeedChange={setSpeed}
 *   tripCount={142}
 *   totalTrips={1500}
 * />
 * ```
 */

import { useCallback, useMemo } from "react";

/** Props for TransitControls */
export interface TransitControlsProps {
	/** Current time in minutes since midnight */
	timeOfDay: number;
	/** Callback when time changes */
	onTimeChange: (time: number) => void;
	/** Whether time is playing */
	isPlaying: boolean;
	/** Callback for play/pause toggle */
	onPlayPause: () => void;
	/** Current speed multiplier */
	speed: number;
	/** Callback when speed changes */
	onSpeedChange: (speed: number) => void;
	/** Number of currently visible trips */
	tripCount: number;
	/** Total number of trips in dataset */
	totalTrips: number;
	/** Minimum time in minutes */
	minTime?: number;
	/** Maximum time in minutes */
	maxTime?: number;
	/** Whether using binary GTFS mode */
	isBinaryMode?: boolean;
}

/** Speed options for the selector */
const SPEED_OPTIONS = [
	{ value: 1, label: "1×" },
	{ value: 30, label: "30×" },
	{ value: 60, label: "60×" },
	{ value: 120, label: "120×" },
	{ value: 300, label: "300×" },
] as const;

/**
 * Format minutes to HH:MM string.
 *
 * @param minutes - Minutes since midnight
 * @returns Formatted time string
 */
function formatTime(minutes: number): string {
	const hours = Math.floor(minutes / 60);
	const mins = Math.floor(minutes % 60);
	return `${hours.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}`;
}

/**
 * TransitControls - Time playback controls for transit viewer
 */
export function TransitControls({
	timeOfDay,
	onTimeChange,
	isPlaying,
	onPlayPause,
	speed,
	onSpeedChange,
	tripCount,
	totalTrips,
	minTime = 300,
	maxTime = 1320,
	isBinaryMode = false,
}: TransitControlsProps) {
	// Handle slider change
	const handleSliderChange = useCallback(
		(e: React.ChangeEvent<HTMLInputElement>) => {
			onTimeChange(parseFloat(e.target.value));
		},
		[onTimeChange]
	);

	// Handle speed change
	const handleSpeedChange = useCallback(
		(e: React.ChangeEvent<HTMLSelectElement>) => {
			onSpeedChange(parseInt(e.target.value, 10));
		},
		[onSpeedChange]
	);

	// Format time display
	const timeDisplay = useMemo(() => formatTime(timeOfDay), [timeOfDay]);

	return (
		<div className="transit-controls">
			{/* Play/Pause button */}
			<button
				className="transit-play-btn"
				onClick={onPlayPause}
				title={isPlaying ? "Pause (Space)" : "Play (Space)"}
			>
				{isPlaying ? (
					<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
						<rect x="6" y="4" width="4" height="16" />
						<rect x="14" y="4" width="4" height="16" />
					</svg>
				) : (
					<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
						<path d="M8 5v14l11-7z" />
					</svg>
				)}
			</button>

			{/* Time display */}
			<div className="transit-time-display">
				<span className="transit-time-value">{timeDisplay}</span>
			</div>

			{/* Time slider */}
			<div className="transit-slider-container">
				<input
					type="range"
					className="transit-slider"
					min={minTime}
					max={maxTime}
					step={1}
					value={timeOfDay}
					onChange={handleSliderChange}
				/>
			</div>

			{/* Speed selector */}
			<select
				className="transit-speed-select"
				value={speed}
				onChange={handleSpeedChange}
				title="Playback speed"
			>
				{SPEED_OPTIONS.map((opt) => (
					<option key={opt.value} value={opt.value}>
						{opt.label}
					</option>
				))}
			</select>

			{/* Trip count badge */}
			<div
				className="transit-trip-badge"
				title={`${tripCount} active trips of ${totalTrips} total${isBinaryMode ? " (Binary)" : ""}`}
			>
				<span className="transit-trip-count">{tripCount.toLocaleString()}</span>
				<span className="transit-trip-label">
					{totalTrips > 0 ? `/ ${totalTrips.toLocaleString()}` : "trips"}
				</span>
			</div>
		</div>
	);
}
