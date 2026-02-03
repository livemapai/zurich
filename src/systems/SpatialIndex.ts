/**
 * SpatialIndex - RBush-based collision detection
 *
 * Uses RBush for fast spatial queries and provides:
 * - Building loading into spatial index
 * - Point collision detection
 * - Circle (player) collision detection with wall normal
 */

import RBush from 'rbush';
import type {
  BuildingFeature,
  BuildingCollection,
  CollisionBBox,
  CollisionResult,
  LngLat,
  MetersPosition,
} from '@/types';
import { METERS_PER_DEGREE } from '@/types';
import { CONFIG } from '@/lib/config';
import { pointInPolygon, closestPointOnSegment, segmentNormalToPoint } from '@/utils/math';

/**
 * SpatialIndex class for building collision detection
 */
export class SpatialIndex {
  private tree: RBush<CollisionBBox>;
  private loaded: boolean = false;

  constructor() {
    this.tree = new RBush<CollisionBBox>();
  }

  /**
   * Check if buildings have been loaded
   */
  isLoaded(): boolean {
    return this.loaded;
  }

  /**
   * Get the number of buildings in the index
   */
  getCount(): number {
    return this.tree.all().length;
  }

  /**
   * Load buildings into the spatial index
   */
  load(buildings: BuildingCollection): void {
    const items: CollisionBBox[] = [];

    for (const feature of buildings.features) {
      const bbox = this.featureToBBox(feature);
      if (bbox) {
        items.push(bbox);
      }
    }

    this.tree.load(items);
    this.loaded = true;
  }

  /**
   * Clear all buildings from the index
   */
  clear(): void {
    this.tree.clear();
    this.loaded = false;
  }

  /**
   * Convert a building feature to a bounding box with reference
   */
  private featureToBBox(feature: BuildingFeature): CollisionBBox | null {
    const geometry = feature.geometry;

    if (geometry.type === 'Polygon') {
      const ring = geometry.coordinates[0];
      if (!ring || ring.length === 0) return null;
      return this.polygonToBBox(ring, feature);
    } else if (geometry.type === 'MultiPolygon') {
      // For MultiPolygon, calculate bbox that encompasses all polygons
      let minX = Infinity;
      let minY = Infinity;
      let maxX = -Infinity;
      let maxY = -Infinity;

      for (const polygon of geometry.coordinates) {
        const ring = polygon[0];
        if (!ring) continue;
        for (const coord of ring) {
          minX = Math.min(minX, coord[0]);
          minY = Math.min(minY, coord[1]);
          maxX = Math.max(maxX, coord[0]);
          maxY = Math.max(maxY, coord[1]);
        }
      }

      if (!isFinite(minX)) return null;

      return { minX, minY, maxX, maxY, feature };
    }

    return null;
  }

  /**
   * Convert a polygon ring to a bounding box
   */
  private polygonToBBox(ring: LngLat[], feature: BuildingFeature): CollisionBBox {
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;

    for (const coord of ring) {
      minX = Math.min(minX, coord[0]);
      minY = Math.min(minY, coord[1]);
      maxX = Math.max(maxX, coord[0]);
      maxY = Math.max(maxY, coord[1]);
    }

    return { minX, minY, maxX, maxY, feature };
  }

  /**
   * Get the outer ring of a building's polygon
   */
  private getOuterRing(feature: BuildingFeature): LngLat[] {
    const geometry = feature.geometry;
    if (geometry.type === 'Polygon') {
      return geometry.coordinates[0] ?? [];
    } else if (geometry.type === 'MultiPolygon') {
      // Return the first polygon's outer ring
      // For more accurate collision, could merge all polygons
      const firstPoly = geometry.coordinates[0];
      return firstPoly?.[0] ?? [];
    }
    return [];
  }

  /**
   * Check if a point collides with any building
   */
  checkPointCollision(point: LngLat): boolean {
    if (!this.loaded) return false;

    // Query RBush for candidates
    const candidates = this.tree.search({
      minX: point[0],
      minY: point[1],
      maxX: point[0],
      maxY: point[1],
    });

    // Check precise collision with each candidate
    for (const candidate of candidates) {
      const ring = this.getOuterRing(candidate.feature);
      if (pointInPolygon(point, ring)) {
        return true;
      }
    }

    return false;
  }

  /**
   * Check collision for a circle (player) at a position
   *
   * @param position - Center of the collision circle [lng, lat]
   * @param radiusMeters - Radius in meters
   * @returns CollisionResult with collision status and wall normal if colliding
   */
  checkCollision(position: LngLat, radiusMeters?: number): CollisionResult {
    const radius = radiusMeters ?? CONFIG.player.collisionRadius;

    if (!this.loaded) {
      return { collides: false, position };
    }

    // Convert radius to degrees for bbox query
    const radiusLng = radius / METERS_PER_DEGREE.lng;
    const radiusLat = radius / METERS_PER_DEGREE.lat;

    // Query RBush for candidates near the position
    const candidates = this.tree.search({
      minX: position[0] - radiusLng,
      minY: position[1] - radiusLat,
      maxX: position[0] + radiusLng,
      maxY: position[1] + radiusLat,
    });

    // Check precise collision with each candidate
    for (const candidate of candidates) {
      const ring = this.getOuterRing(candidate.feature);

      // First check if point is inside polygon
      if (pointInPolygon(position, ring)) {
        const normal = this.calculatePushoutNormal(position, ring);
        return { collides: true, position, normal };
      }

      // Then check if circle intersects any edge
      const edgeCollision = this.checkCircleEdgeCollision(position, radius, ring);
      if (edgeCollision) {
        return edgeCollision;
      }
    }

    return { collides: false, position };
  }

  /**
   * Calculate the normal vector to push out of a polygon
   */
  private calculatePushoutNormal(point: LngLat, ring: LngLat[]): MetersPosition {
    let closestDist = Infinity;
    let closestNormal: MetersPosition = [1, 0];

    // Find the closest edge and its normal
    for (let i = 0; i < ring.length - 1; i++) {
      const segStart = ring[i];
      const segEnd = ring[i + 1];
      if (!segStart || !segEnd) continue;

      const closest = closestPointOnSegment(point, segStart, segEnd);
      const dx = (point[0] - closest[0]) * METERS_PER_DEGREE.lng;
      const dy = (point[1] - closest[1]) * METERS_PER_DEGREE.lat;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist < closestDist) {
        closestDist = dist;
        closestNormal = segmentNormalToPoint(point, segStart, segEnd);
      }
    }

    return closestNormal;
  }

  /**
   * Check if a circle collides with any edge of a polygon
   */
  private checkCircleEdgeCollision(
    center: LngLat,
    radiusMeters: number,
    ring: LngLat[]
  ): CollisionResult | null {
    for (let i = 0; i < ring.length - 1; i++) {
      const segStart = ring[i];
      const segEnd = ring[i + 1];
      if (!segStart || !segEnd) continue;

      const closest = closestPointOnSegment(center, segStart, segEnd);

      // Calculate distance in meters
      const dx = (center[0] - closest[0]) * METERS_PER_DEGREE.lng;
      const dy = (center[1] - closest[1]) * METERS_PER_DEGREE.lat;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist < radiusMeters) {
        // Calculate normal pointing from edge towards center
        const normal = segmentNormalToPoint(center, segStart, segEnd);
        return { collides: true, position: center, normal };
      }
    }

    return null;
  }

  /**
   * Slide velocity along a wall normal
   *
   * @param velocity - Original velocity [vx, vy] in m/s
   * @param normal - Wall normal [nx, ny] normalized
   * @returns Adjusted velocity after wall slide
   */
  slideVelocity(velocity: MetersPosition, normal: MetersPosition): MetersPosition {
    // Project velocity onto wall tangent
    // tangent = perpendicular to normal = [-ny, nx]
    const tangent: MetersPosition = [-normal[1], normal[0]];

    // Dot product of velocity with tangent
    const dot = velocity[0] * tangent[0] + velocity[1] * tangent[1];

    // Slide velocity = projection onto tangent
    return [tangent[0] * dot, tangent[1] * dot];
  }
}

/**
 * Create a new SpatialIndex instance
 */
export function createSpatialIndex(): SpatialIndex {
  return new SpatialIndex();
}
