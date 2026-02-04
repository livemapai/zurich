/**
 * LayerPanel Component
 *
 * UI panel for toggling visibility of map layers.
 * Organizes layers by category (Nature, Transport, POI, etc.)
 * Includes per-route toggles for transit animation.
 */

import { useCallback, useState, useMemo } from "react";
import {
	TEXTURE_PROVIDERS,
	type TextureProviderId,
} from "@/layers/MapterhornTerrainLayer";
import {
	MAP_TILE_PROVIDERS,
	type MapTileProviderId,
} from "@/layers/MapTileLayer";
import { RouteType, ROUTE_TYPE_LABELS } from "@/types";

/** Single layer definition */
export interface LayerDefinition {
	/** Unique layer identifier */
	id: string;
	/** Display name */
	name: string;
	/** Category for grouping */
	category: string;
	/** Current visibility state */
	visible: boolean;
	/** Layer opacity (0-1) */
	opacity?: number;
	/** Whether this layer supports opacity control */
	supportsOpacity?: boolean;
	/** Feature count (optional) */
	count?: number;
}

/** Transit route information for per-line toggles */
export interface RouteInfo {
	/** Route short name (e.g., "10", "31") */
	name: string;
	/** GTFS route type */
	type: RouteType;
	/** Route color in hex */
	color: string;
	/** Number of trips for this route */
	tripCount: number;
	/** Whether this route is currently visible */
	visible: boolean;
}

export interface LayerPanelProps {
	/** Array of layer definitions */
	layers: LayerDefinition[];
	/** Callback when layer visibility is toggled */
	onToggle: (layerId: string) => void;
	/** Callback when layer opacity is changed */
	onOpacityChange?: (layerId: string, opacity: number) => void;
	/** Whether the panel is visible */
	visible?: boolean;
	/** Current terrain texture provider ID */
	terrainTexture?: TextureProviderId;
	/** Callback when terrain texture is changed */
	onTextureChange?: (providerId: TextureProviderId) => void;
	/** Current map tile style provider ID */
	mapTileStyle?: MapTileProviderId;
	/** Callback when map tile style is changed */
	onMapTileStyleChange?: (providerId: MapTileProviderId) => void;
	/** Transit routes for per-line toggles */
	routes?: RouteInfo[];
	/** Callback when a route is toggled */
	onRouteToggle?: (routeName: string) => void;
	/** Callback when all routes of a type are toggled */
	onRouteTypeToggle?: (routeType: RouteType, enable: boolean) => void;
	/** Callback when all routes are toggled */
	onAllRoutesToggle?: (enable: boolean) => void;
}

/** Group layers by category */
function groupByCategory(
  layers: LayerDefinition[]
): Record<string, LayerDefinition[]> {
  return layers.reduce(
    (acc, layer) => {
      const category = layer.category;
      if (!acc[category]) {
        acc[category] = [];
      }
      acc[category].push(layer);
      return acc;
    },
    {} as Record<string, LayerDefinition[]>
  );
}

/**
 * LayerPanel - UI for toggling layer visibility
 */
export function LayerPanel({
	layers,
	onToggle,
	onOpacityChange,
	visible = true,
	terrainTexture = "osm",
	onTextureChange,
	mapTileStyle = "voyager",
	onMapTileStyleChange,
	routes = [],
	onRouteToggle,
	onRouteTypeToggle,
	onAllRoutesToggle,
}: LayerPanelProps) {
	const grouped = groupByCategory(layers);

	// Track which route type groups are expanded
	const [expandedTypes, setExpandedTypes] = useState<Set<RouteType>>(
		() => new Set([RouteType.Tram])
	);

	const handleToggle = useCallback(
		(layerId: string) => {
			onToggle(layerId);
		},
		[onToggle]
	);

	const handleOpacityChange = useCallback(
		(layerId: string, e: React.ChangeEvent<HTMLInputElement>) => {
			onOpacityChange?.(layerId, parseFloat(e.target.value));
		},
		[onOpacityChange]
	);

	const handleTextureChange = useCallback(
		(e: React.ChangeEvent<HTMLSelectElement>) => {
			onTextureChange?.(e.target.value as TextureProviderId);
		},
		[onTextureChange]
	);

	const handleMapTileStyleChange = useCallback(
		(e: React.ChangeEvent<HTMLSelectElement>) => {
			onMapTileStyleChange?.(e.target.value as MapTileProviderId);
		},
		[onMapTileStyleChange]
	);

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

	// Check if 3D terrain is enabled to show texture selector
	const terrain3dLayer = layers.find((l) => l.id === "terrain3d");
	const showTextureSelector = terrain3dLayer?.visible ?? false;

	// Check if flat map tiles is enabled to show style selector
	const mapTilesLayer = layers.find((l) => l.id === "mapTiles");
	const showMapTileStyleSelector = mapTilesLayer?.visible ?? false;

	// Check if Transit Animation layer is visible
	const tramTripsLayer = layers.find((l) => l.id === "tramTrips");
	const showRouteToggles =
		tramTripsLayer?.visible && routes.length > 0;

	// Group routes by type
	const routesByType = useMemo(() => {
		const grouped = new Map<RouteType, RouteInfo[]>();
		for (const route of routes) {
			const existing = grouped.get(route.type) ?? [];
			existing.push(route);
			grouped.set(route.type, existing);
		}
		// Sort entries by route type (trams first, then buses, etc.)
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

	if (!visible) {
		return null;
	}

	return (
		<div
			className="layer-panel"
			onPointerDown={(e) => e.stopPropagation()}
			onClick={(e) => e.stopPropagation()}
		>
			<div className="layer-panel-header">Layers</div>
			{Object.entries(grouped).map(([category, items]) => (
				<div key={category} className="layer-category">
					<h4>{category}</h4>
					{items.map((layer) => (
						<div key={layer.id} className="layer-item-container">
							<label className="layer-item">
								<input
									type="checkbox"
									checked={layer.visible}
									onChange={() => handleToggle(layer.id)}
								/>
								<span className="layer-name">{layer.name}</span>
								{layer.count !== undefined && (
									<span className="layer-count">
										({layer.count.toLocaleString()})
									</span>
								)}
							</label>
							{layer.supportsOpacity && layer.visible && (
								<div className="layer-opacity">
									<input
										type="range"
										min="0"
										max="1"
										step="0.1"
										value={layer.opacity ?? 1}
										onChange={(e) => handleOpacityChange(layer.id, e)}
										className="opacity-slider"
									/>
									<span className="opacity-value">
										{Math.round((layer.opacity ?? 1) * 100)}%
									</span>
								</div>
							)}
						</div>
					))}
					{/* Texture selector - shown under Base Map when 3D terrain is enabled */}
					{category === "Base Map" && showTextureSelector && (
						<div className="texture-selector">
							<label className="texture-label">
								<span>Ground Texture</span>
								<select value={terrainTexture} onChange={handleTextureChange}>
									{Object.entries(TEXTURE_PROVIDERS).map(([id, provider]) => (
										<option key={id} value={id}>
											{provider.name}
										</option>
									))}
								</select>
							</label>
						</div>
					)}
					{/* Map tile style selector - shown under Base Map when flat tiles is enabled */}
					{category === "Base Map" && showMapTileStyleSelector && (
						<div className="texture-selector">
							<label className="texture-label">
								<span>Map Style</span>
								<select value={mapTileStyle} onChange={handleMapTileStyleChange}>
									{Object.entries(MAP_TILE_PROVIDERS).map(([id, provider]) => (
										<option key={id} value={id}>
											{provider.name}
										</option>
									))}
								</select>
							</label>
						</div>
					)}
					{/* Route toggles - shown under Transit when Transit Animation is enabled */}
					{category === "Transit" && showRouteToggles && (
						<div className="route-toggles">
							<div className="route-toggles-header">
								<span className="route-toggles-title">Routes</span>
								<div className="route-toggles-actions">
									<button
										className="route-action-btn"
										onClick={() => onAllRoutesToggle?.(true)}
										title="Show all routes"
									>
										All
									</button>
									<button
										className="route-action-btn"
										onClick={() => onAllRoutesToggle?.(false)}
										title="Hide all routes"
									>
										None
									</button>
								</div>
							</div>
							<div className="route-groups-container">
								{routesByType.map(([type, typeRoutes]) => {
									const stats = typeStats.get(type);
									const isExpanded = expandedTypes.has(type);
									const allVisible =
										stats?.visible === stats?.total;
									const noneVisible = stats?.visible === 0;

									return (
										<div key={type} className="route-type-group">
											<div
												className="route-type-header"
												onClick={() => toggleTypeExpanded(type)}
											>
												<span
													className={`route-type-arrow ${isExpanded ? "expanded" : ""}`}
												>
													▶
												</span>
												<span className="route-type-name">
													{ROUTE_TYPE_LABELS[type]} ({stats?.visible}/
													{stats?.total})
												</span>
												<div
													className="route-type-actions"
													onClick={(e) => e.stopPropagation()}
												>
													<button
														className={`route-type-btn ${allVisible ? "active" : ""}`}
														onClick={() => onRouteTypeToggle?.(type, true)}
														title={`Show all ${ROUTE_TYPE_LABELS[type].toLowerCase()}`}
													>
														✓
													</button>
													<button
														className={`route-type-btn ${noneVisible ? "active" : ""}`}
														onClick={() => onRouteTypeToggle?.(type, false)}
														title={`Hide all ${ROUTE_TYPE_LABELS[type].toLowerCase()}`}
													>
														✗
													</button>
												</div>
											</div>
											{isExpanded && (
												<div className="route-chips">
													{typeRoutes.map((route) => (
														<button
															key={route.name}
															className={`route-chip ${route.visible ? "visible" : "hidden"}`}
															onClick={() => onRouteToggle?.(route.name)}
															title={`${route.tripCount} trips`}
															style={{
																"--route-color": route.color,
															} as React.CSSProperties}
														>
															<span
																className="route-chip-color"
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
					)}
				</div>
			))}
		</div>
	);
}
