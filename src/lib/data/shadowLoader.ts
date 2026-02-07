/**
 * Shadow Data Loader
 *
 * Loads shadow polygon data from PMTiles vector tiles or GeoJSON,
 * and computes additional attributes needed for gradient rendering.
 */

/**
 * Coordinate pair [longitude, latitude]
 */
export type Coordinate = [number, number];

/**
 * Shadow polygon coordinates (outer ring only for simplicity)
 */
export type ShadowPolygon = Coordinate[][];

/**
 * Properties for a shadow feature
 */
export interface ShadowProperties {
  /** Building ID that casts this shadow */
  buildingId?: string;
  /** Height of the building casting this shadow */
  height?: number;
  /** Centroid of the shadow polygon [lng, lat] */
  centroid: [number, number];
  /** Maximum distance from centroid to any edge (for gradient calculation) */
  maxRadius: number;
  /** Pre-computed opacity for this shadow (0-1) */
  opacity?: number;
  /** Distance from source building edge (for penumbra calculation) */
  distanceFromSource?: number;
  /** Ring index for multi-ring gradient rendering */
  ringIndex?: number;
}

/**
 * GeoJSON Feature for a shadow polygon
 */
export interface ShadowFeature {
  type: 'Feature';
  properties: ShadowProperties;
  geometry: {
    type: 'Polygon';
    coordinates: ShadowPolygon;
  };
}

/**
 * Shadow data collection
 */
export interface ShadowCollection {
  type: 'FeatureCollection';
  features: ShadowFeature[];
}

/**
 * Result of loading shadow data
 */
export interface LoadShadowsResult {
  features: ShadowFeature[];
  stats: {
    count: number;
    avgRadius: number;
    totalArea: number;
  };
}

/**
 * Raw GeoJSON feature type for input
 */
interface RawGeoJSONFeature {
  type: string;
  properties?: Record<string, unknown>;
  geometry: {
    type: string;
    coordinates: unknown;
  };
}

/**
 * Raw GeoJSON FeatureCollection for input
 */
interface RawFeatureCollection {
  type: string;
  features: RawGeoJSONFeature[];
}

/**
 * Calculate the centroid of a polygon
 */
function calculateCentroid(coordinates: ShadowPolygon): [number, number] {
  const outerRing = coordinates[0];
  if (!outerRing || outerRing.length === 0) {
    return [0, 0];
  }

  let sumX = 0;
  let sumY = 0;

  // Use simple average of vertices (fast approximation)
  for (const [x, y] of outerRing) {
    sumX += x;
    sumY += y;
  }

  return [sumX / outerRing.length, sumY / outerRing.length];
}

/**
 * Calculate the maximum distance from centroid to any vertex
 */
function calculateMaxRadius(
  coordinates: ShadowPolygon,
  centroid: [number, number]
): number {
  const outerRing = coordinates[0];
  if (!outerRing || outerRing.length === 0) {
    return 0;
  }

  let maxDist = 0;
  const [cx, cy] = centroid;

  for (const [x, y] of outerRing) {
    // Use simple Euclidean distance (sufficient for small areas)
    const dist = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2);
    if (dist > maxDist) {
      maxDist = dist;
    }
  }

  return maxDist;
}

/**
 * Calculate approximate polygon area using shoelace formula
 */
function calculateArea(coordinates: ShadowPolygon): number {
  const outerRing = coordinates[0];
  if (!outerRing || outerRing.length < 3) {
    return 0;
  }

  let area = 0;
  const n = outerRing.length;

  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const current = outerRing[i];
    const next = outerRing[j];
    if (current && next) {
      area += current[0] * next[1];
      area -= next[0] * current[1];
    }
  }

  return Math.abs(area / 2);
}

/**
 * Process raw shadow features to add gradient attributes
 */
function processShadowFeatures(
  features: RawGeoJSONFeature[]
): ShadowFeature[] {
  return features
    .filter((f) => f.geometry?.type === 'Polygon')
    .map((feature, index) => {
      const coordinates = feature.geometry.coordinates as ShadowPolygon;
      const centroid = calculateCentroid(coordinates);
      const maxRadius = calculateMaxRadius(coordinates, centroid);

      const properties: ShadowProperties = {
        buildingId: (feature.properties?.buildingId as string) ?? `shadow-${index}`,
        height: (feature.properties?.height as number) ?? undefined,
        centroid,
        maxRadius,
        opacity: 1, // Default full opacity, can be modified for gradient
      };

      return {
        type: 'Feature' as const,
        properties,
        geometry: {
          type: 'Polygon' as const,
          coordinates,
        },
      };
    });
}

/**
 * Load shadow data from a GeoJSON URL
 *
 * @param url - URL to the shadow GeoJSON file
 * @param onProgress - Optional progress callback
 */
export async function loadShadows(
  url: string,
  onProgress?: (progress: number) => void
): Promise<LoadShadowsResult> {
  onProgress?.(0);

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to load shadows: ${response.status} ${response.statusText}`);
  }

  onProgress?.(30);

  const data = await response.json() as RawFeatureCollection;

  if (!data.features || !Array.isArray(data.features)) {
    throw new Error('Invalid GeoJSON: missing features array');
  }

  onProgress?.(60);

  const features = processShadowFeatures(data.features);

  // Calculate statistics
  let totalRadius = 0;
  let totalArea = 0;

  for (const feature of features) {
    totalRadius += feature.properties.maxRadius;
    totalArea += calculateArea(feature.geometry.coordinates);
  }

  const stats = {
    count: features.length,
    avgRadius: features.length > 0 ? totalRadius / features.length : 0,
    totalArea,
  };

  onProgress?.(100);

  return { features, stats };
}

/**
 * Extract shadow polygons from MapLibre vector tile features
 *
 * This function converts MapLibre's queryRenderedFeatures results
 * into our shadow format for deck.gl rendering.
 *
 * @param features - MapLibre rendered features from shadow layer
 */
export function extractShadowsFromMapLibre(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  features: readonly any[]
): ShadowFeature[] {
  const shadowFeatures: ShadowFeature[] = [];

  for (const feature of features) {
    if (feature.geometry.type !== 'Polygon') {
      continue;
    }

    const coordinates = feature.geometry.coordinates as ShadowPolygon;
    const centroid = calculateCentroid(coordinates);
    const maxRadius = calculateMaxRadius(coordinates, centroid);

    shadowFeatures.push({
      type: 'Feature',
      properties: {
        buildingId: (feature.properties?.id as string) ?? undefined,
        height: (feature.properties?.height as number) ?? undefined,
        centroid,
        maxRadius,
        opacity: 1,
      },
      geometry: {
        type: 'Polygon',
        coordinates,
      },
    });
  }

  return shadowFeatures;
}

/**
 * Generate shadow polygons from building data dynamically
 *
 * Creates shadow polygons by projecting building footprints
 * based on sun position. This is a client-side alternative
 * to pre-computed shadows.
 *
 * @param buildingCoords - Building polygon coordinates
 * @param buildingHeight - Height of the building in meters
 * @param sunAzimuth - Sun azimuth in degrees (0=North)
 * @param sunAltitude - Sun altitude in degrees above horizon
 */
export function generateShadowFromBuilding(
  buildingCoords: Coordinate[][],
  buildingHeight: number,
  sunAzimuth: number,
  sunAltitude: number
): ShadowPolygon {
  // Convert sun position to shadow projection vector
  // Shadow falls opposite to sun direction
  const shadowAzimuth = (sunAzimuth + 180) % 360;
  const azimuthRad = (shadowAzimuth * Math.PI) / 180;
  const altitudeRad = (sunAltitude * Math.PI) / 180;

  // Shadow length = building height / tan(altitude)
  // Capped to avoid infinite shadows at sunset
  const shadowLength = Math.min(
    buildingHeight / Math.tan(Math.max(altitudeRad, 0.05)),
    buildingHeight * 10 // Cap at 10x building height
  );

  // Convert to degree offsets (approximate at Zurich latitude)
  // 1° longitude ≈ 75,500m, 1° latitude ≈ 111,320m
  const dxMeters = Math.sin(azimuthRad) * shadowLength;
  const dyMeters = Math.cos(azimuthRad) * shadowLength;
  const dxDeg = dxMeters / 75500;
  const dyDeg = dyMeters / 111320;

  // Project building footprint to create shadow polygon
  // Shadow is formed by connecting building corners to their projections
  const outerRing = buildingCoords[0];
  if (!outerRing) {
    return [[]];
  }

  const shadowRing: Coordinate[] = [];

  // Simple approach: offset all vertices by shadow vector
  for (const coord of outerRing) {
    if (coord) {
      shadowRing.push([coord[0] + dxDeg, coord[1] + dyDeg]);
    }
  }

  return [shadowRing];
}
