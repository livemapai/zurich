/**
 * VehicleLabelsLayer
 *
 * TextLayer factory for displaying route numbers on active vehicles.
 * Uses collision detection to prevent overlapping labels.
 *
 * @example
 * ```typescript
 * const positions = getActiveVehiclePositions(trips, timeSeconds, visibleRoutes);
 * const labelsLayer = createVehicleLabelsLayer(positions, {
 *   visible: viewState.zoom >= 16,
 * });
 * ```
 */

import { TextLayer } from "@deck.gl/layers";
import type { VehiclePosition } from "@/utils/vehiclePosition";

/** Configuration for vehicle labels layer */
export interface VehicleLabelsLayerConfig {
	/** Layer id prefix (default: "vehicle-labels") */
	id?: string;
	/** Whether labels are visible (use for zoom-based visibility) */
	visible?: boolean;
	/** Font size in pixels (default: 14) */
	fontSize?: number;
	/** Background opacity 0-255 (default: 220) */
	backgroundOpacity?: number;
	/** Enable collision detection (default: true) */
	collisionEnabled?: boolean;
	/** Collision test scale - larger values create more spacing (default: 2) */
	collisionScale?: number;
}

/**
 * Parse hex color to RGB array.
 *
 * @param hex - Hex color string (e.g., "#00a1e0")
 * @returns RGB array [r, g, b]
 */
function hexToRgb(hex: string): [number, number, number] {
	const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
	if (result && result[1] && result[2] && result[3]) {
		return [
			parseInt(result[1], 16),
			parseInt(result[2], 16),
			parseInt(result[3], 16),
		];
	}
	return [255, 255, 255]; // Default to white
}

/**
 * Determine if a color is "light" (needs dark text).
 *
 * Uses relative luminance formula to decide text color.
 *
 * @param rgb - RGB color array
 * @returns True if color is light
 */
function isLightColor(rgb: [number, number, number]): boolean {
	// Relative luminance formula
	const luminance = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255;
	return luminance > 0.5;
}

/**
 * Create a TextLayer for vehicle route labels.
 *
 * Features:
 * - Route number displayed at vehicle position
 * - Background color matches route color
 * - Text color auto-adjusts for contrast
 * - Collision detection prevents overlap
 * - Billboard mode keeps labels facing camera
 *
 * @param positions - Array of vehicle positions from getActiveVehiclePositions
 * @param config - Layer configuration options
 * @returns Configured TextLayer instance
 */
export function createVehicleLabelsLayer(
	positions: VehiclePosition[],
	config: VehicleLabelsLayerConfig = {}
): TextLayer<VehiclePosition> {
	const {
		id = "vehicle-labels",
		visible = true,
		fontSize = 14,
		backgroundOpacity = 220,
		collisionEnabled = true,
		collisionScale = 2,
	} = config;

	return new TextLayer<VehiclePosition>({
		id,
		data: positions,
		visible,

		// Position and text accessors
		getPosition: (d) => d.position,
		getText: (d) => d.routeName,

		// Styling - larger sizes for better visibility
		getSize: fontSize,
		sizeUnits: "pixels",
		sizeMinPixels: 14,
		sizeMaxPixels: 32,

		// Text color - white or black based on background luminance
		getColor: (d) => {
			const rgb = hexToRgb(d.color);
			return isLightColor(rgb) ? [0, 0, 0, 255] : [255, 255, 255, 255];
		},

		// Background with more padding to prevent clipping
		background: true,
		getBackgroundColor: (d) => {
			const rgb = hexToRgb(d.color);
			return [rgb[0], rgb[1], rgb[2], backgroundOpacity];
		},
		backgroundPadding: [8, 6], // [horizontal, vertical] - increased padding

		// Font - use monospace for consistent number width
		fontFamily: "'SF Mono', Monaco, Consolas, monospace",
		fontWeight: "bold" as const,

		// Text anchor - center the text on the position
		getTextAnchor: "middle",
		getAlignmentBaseline: "center",

		// Billboard mode - labels always face camera
		billboard: true,

		// Pixel offset to position label slightly above the vehicle
		getPixelOffset: [0, -12],

		// Collision detection to prevent overlapping labels
		...(collisionEnabled && {
			characterSet: "auto",
			collisionTestProps: {
				sizeScale: collisionScale,
			},
		}),

		// Picking (for interactivity if needed)
		pickable: false,

		// Update triggers
		updateTriggers: {
			getPosition: positions,
			getText: positions,
			getColor: positions,
			getBackgroundColor: positions,
		},
	});
}

/**
 * Get minimum zoom level for vehicle labels to be visible.
 * Labels only shown when zoomed in enough to see individual vehicles.
 */
export const VEHICLE_LABELS_MIN_ZOOM = 15;

/**
 * Helper to determine if labels should be visible at current zoom.
 *
 * @param zoom - Current map zoom level
 * @returns True if labels should be visible
 */
export function shouldShowVehicleLabels(zoom: number): boolean {
	return zoom >= VEHICLE_LABELS_MIN_ZOOM;
}
