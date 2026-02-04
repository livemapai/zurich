/**
 * RouteFilterPanel Component
 *
 * Collapsible panel for filtering transit routes by type and individual lines.
 * Routes are grouped by type (Tram, Bus, etc.) with color-coded chips.
 *
 * @example
 * ```tsx
 * <RouteFilterPanel
 *   visible={showPanel}
 *   routes={routeInfo}
 *   onRouteToggle={(name) => toggleRoute(name)}
 *   onRouteTypeToggle={(type, enable) => toggleType(type, enable)}
 *   onAllRoutesToggle={(enable) => toggleAll(enable)}
 *   onClose={() => setShowPanel(false)}
 * />
 * ```
 */

import { useMemo, useState, useCallback } from "react";
import { RouteType, ROUTE_TYPE_LABELS } from "@/types";
import type { RouteInfo } from "@/utils/transitRoutes";

/** Props for RouteFilterPanel */
export interface RouteFilterPanelProps {
	/** Whether the panel is visible */
	visible: boolean;
	/** Array of route info objects */
	routes: RouteInfo[];
	/** Callback when a single route is toggled */
	onRouteToggle: (routeName: string) => void;
	/** Callback when all routes of a type are toggled */
	onRouteTypeToggle: (routeType: RouteType, enable: boolean) => void;
	/** Callback when all routes are toggled */
	onAllRoutesToggle: (enable: boolean) => void;
	/** Callback to close the panel */
	onClose: () => void;
}

/**
 * RouteFilterPanel - Filter transit routes by type and line
 */
export function RouteFilterPanel({
	visible,
	routes,
	onRouteToggle,
	onRouteTypeToggle,
	onAllRoutesToggle,
	onClose,
}: RouteFilterPanelProps) {
	// Track which route type groups are expanded
	const [expandedTypes, setExpandedTypes] = useState<Set<RouteType>>(
		() => new Set([RouteType.Tram])
	);

	// Group routes by type
	const routesByType = useMemo(() => {
		const grouped = new Map<RouteType, RouteInfo[]>();
		for (const route of routes) {
			const existing = grouped.get(route.type) ?? [];
			existing.push(route);
			grouped.set(route.type, existing);
		}
		// Sort by type (trams first)
		return Array.from(grouped.entries()).sort(([a], [b]) => a - b);
	}, [routes]);

	// Calculate visibility stats per type
	const typeStats = useMemo(() => {
		const stats = new Map<RouteType, { visible: number; total: number }>();
		for (const route of routes) {
			const existing = stats.get(route.type) ?? { visible: 0, total: 0 };
			existing.total++;
			if (route.visible) existing.visible++;
			stats.set(route.type, existing);
		}
		return stats;
	}, [routes]);

	// Total stats
	const totalStats = useMemo(() => {
		const visible = routes.filter((r) => r.visible).length;
		return { visible, total: routes.length };
	}, [routes]);

	// Toggle type expansion
	const toggleTypeExpanded = useCallback((type: RouteType) => {
		setExpandedTypes((prev) => {
			const next = new Set(prev);
			if (next.has(type)) {
				next.delete(type);
			} else {
				next.add(type);
			}
			return next;
		});
	}, []);

	if (!visible) {
		return null;
	}

	return (
		<div
			className="transit-route-panel"
			onPointerDown={(e) => e.stopPropagation()}
			onClick={(e) => e.stopPropagation()}
		>
			{/* Header */}
			<div className="transit-route-panel-header">
				<span className="transit-route-panel-title">Route Filter</span>
				<button
					className="transit-route-panel-close"
					onClick={onClose}
					title="Close (R)"
				>
					✕
				</button>
			</div>

			{/* Global actions */}
			<div className="transit-route-actions">
				<span className="transit-route-stats">
					{totalStats.visible} / {totalStats.total} routes
				</span>
				<div className="transit-route-action-btns">
					<button
						className="transit-route-action-btn"
						onClick={() => onAllRoutesToggle(true)}
						title="Show all routes"
					>
						All
					</button>
					<button
						className="transit-route-action-btn"
						onClick={() => onAllRoutesToggle(false)}
						title="Hide all routes"
					>
						None
					</button>
				</div>
			</div>

			{/* Route groups */}
			<div className="transit-route-groups">
				{routesByType.map(([type, typeRoutes]) => {
					const stats = typeStats.get(type);
					const isExpanded = expandedTypes.has(type);
					const allVisible = stats?.visible === stats?.total;
					const noneVisible = stats?.visible === 0;

					return (
						<div key={type} className="transit-route-group">
							{/* Type header */}
							<div
								className="transit-route-type-header"
								onClick={() => toggleTypeExpanded(type)}
							>
								<span
									className={`transit-route-type-arrow ${isExpanded ? "expanded" : ""}`}
								>
									▶
								</span>
								<span className="transit-route-type-name">
									{ROUTE_TYPE_LABELS[type]}
								</span>
								<span className="transit-route-type-count">
									{stats?.visible}/{stats?.total}
								</span>
								<div
									className="transit-route-type-actions"
									onClick={(e) => e.stopPropagation()}
								>
									<button
										className={`transit-route-type-btn ${allVisible ? "active" : ""}`}
										onClick={() => onRouteTypeToggle(type, true)}
										title={`Show all ${ROUTE_TYPE_LABELS[type].toLowerCase()}`}
									>
										✓
									</button>
									<button
										className={`transit-route-type-btn ${noneVisible ? "active" : ""}`}
										onClick={() => onRouteTypeToggle(type, false)}
										title={`Hide all ${ROUTE_TYPE_LABELS[type].toLowerCase()}`}
									>
										✗
									</button>
								</div>
							</div>

							{/* Route chips */}
							{isExpanded && (
								<div className="transit-route-chips">
									{typeRoutes.map((route) => (
										<button
											key={route.name}
											className={`transit-route-chip ${route.visible ? "visible" : "hidden"}`}
											onClick={() => onRouteToggle(route.name)}
											title={`${route.tripCount} trips`}
											style={
												{
													"--route-color": route.color,
												} as React.CSSProperties
											}
										>
											<span
												className="transit-route-chip-color"
												style={{ backgroundColor: route.color }}
											/>
											{route.name}
										</button>
									))}
								</div>
							)}
						</div>
					);
				})}
			</div>
		</div>
	);
}
