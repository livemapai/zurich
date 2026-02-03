/**
 * SpatialIndex
 *
 * RBush-based spatial index for collision detection
 */

import RBush from 'rbush';
import type { BuildingFeature, CollisionBBox, CollisionResult } from '@/types';

export class SpatialIndex {
  private tree: RBush<CollisionBBox>;
  private isLoaded: boolean = false;

  constructor() {
    this.tree = new RBush<CollisionBBox>();
  }

  /**
   * Load building features into the spatial index
   */
  load(features: BuildingFeature[]): void {
    const bboxes = features.map((feature) => this.extractBBox(feature));
    this.tree.load(bboxes);
    this.isLoaded = true;
  }

  /**
   * Clear all data from the index
   */
  clear(): void {
    this.tree.clear();
    this.isLoaded = false;
  }

  /**
   * Check if index has been loaded with data
   */
  get loaded(): boolean {
    return this.isLoaded;
  }

  /**
   * Query buildings near a point
   */
  queryNearby(
    lng: number,
    lat: number,
    radiusDegrees: number
  ): CollisionBBox[] {
    return this.tree.search({
      minX: lng - radiusDegrees,
      minY: lat - radiusDegrees,
      maxX: lng + radiusDegrees,
      maxY: lat + radiusDegrees,
    });
  }

  /**
   * Check collision at a point
   */
  checkCollision(
    lng: number,
    lat: number,
    radiusDegrees: number = 0.00001 // ~1m at Zurich latitude
  ): CollisionResult {
    const nearby = this.queryNearby(lng, lat, radiusDegrees);

    for (const bbox of nearby) {
      const polygon = this.getOuterRing(bbox.feature);

      if (this.pointInPolygon(lng, lat, polygon)) {
        const normal = this.findNearestEdgeNormal(lng, lat, polygon);

        return {
          collides: true,
          building: bbox.feature,
          normal,
        };
      }
    }

    return { collides: false };
  }

  /**
   * Extract bounding box from a building feature
   */
  private extractBBox(feature: BuildingFeature): CollisionBBox {
    const coords = this.getOuterRing(feature);

    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;

    for (const coord of coords) {
      const [x, y] = coord;
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }

    return { minX, minY, maxX, maxY, feature };
  }

  /**
   * Get outer ring coordinates from a feature
   */
  private getOuterRing(feature: BuildingFeature): number[][] {
    const coords = feature.geometry.coordinates;

    if (feature.geometry.type === 'MultiPolygon') {
      // Take first polygon's outer ring
      return (coords as number[][][][])[0][0];
    }

    // Polygon: first array is outer ring
    return (coords as number[][][])[0];
  }

  /**
   * Ray-casting point-in-polygon test
   */
  private pointInPolygon(x: number, y: number, polygon: number[][]): boolean {
    let inside = false;

    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const xi = polygon[i][0];
      const yi = polygon[i][1];
      const xj = polygon[j][0];
      const yj = polygon[j][1];

      if (
        yi > y !== yj > y &&
        x < ((xj - xi) * (y - yi)) / (yj - yi) + xi
      ) {
        inside = !inside;
      }
    }

    return inside;
  }

  /**
   * Find normal of nearest edge for wall sliding
   */
  private findNearestEdgeNormal(
    x: number,
    y: number,
    polygon: number[][]
  ): { x: number; y: number } {
    let minDist = Infinity;
    let nearestNormal = { x: 0, y: 1 };

    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const x1 = polygon[j][0];
      const y1 = polygon[j][1];
      const x2 = polygon[i][0];
      const y2 = polygon[i][1];

      // Distance from point to line segment
      const dist = this.pointToSegmentDistance(x, y, x1, y1, x2, y2);

      if (dist < minDist) {
        minDist = dist;

        // Calculate outward normal
        const dx = x2 - x1;
        const dy = y2 - y1;
        const len = Math.sqrt(dx * dx + dy * dy);

        // Perpendicular (pointing outward from polygon)
        nearestNormal = {
          x: -dy / len,
          y: dx / len,
        };

        // Ensure normal points outward (toward the test point)
        const toPoint = { x: x - x1, y: y - y1 };
        const dot = nearestNormal.x * toPoint.x + nearestNormal.y * toPoint.y;
        if (dot < 0) {
          nearestNormal.x = -nearestNormal.x;
          nearestNormal.y = -nearestNormal.y;
        }
      }
    }

    return nearestNormal;
  }

  /**
   * Distance from point to line segment
   */
  private pointToSegmentDistance(
    px: number,
    py: number,
    x1: number,
    y1: number,
    x2: number,
    y2: number
  ): number {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const lengthSq = dx * dx + dy * dy;

    if (lengthSq === 0) {
      return Math.sqrt((px - x1) ** 2 + (py - y1) ** 2);
    }

    let t = ((px - x1) * dx + (py - y1) * dy) / lengthSq;
    t = Math.max(0, Math.min(1, t));

    const nearestX = x1 + t * dx;
    const nearestY = y1 + t * dy;

    return Math.sqrt((px - nearestX) ** 2 + (py - nearestY) ** 2);
  }
}

// Singleton instance
export const spatialIndex = new SpatialIndex();
