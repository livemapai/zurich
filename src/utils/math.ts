/**
 * Math utilities for vector operations
 */

import type { Velocity, LngLat, MetersPosition } from '@/types';

/**
 * Calculate the length/magnitude of a velocity vector
 */
export function velocityLength(v: Velocity): number {
  return Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
}

/**
 * Calculate the 2D length (XY plane) of a velocity vector
 */
export function velocityLength2D(v: Velocity): number {
  return Math.sqrt(v.x * v.x + v.y * v.y);
}

/**
 * Normalize a velocity vector to unit length (3D)
 * Returns zero vector if input is zero
 */
export function normalizeVelocity(v: Velocity): Velocity {
  const len = velocityLength(v);
  if (len === 0) return { x: 0, y: 0, z: 0 };
  return {
    x: v.x / len,
    y: v.y / len,
    z: v.z / len,
  };
}

/**
 * Normalize a velocity vector in 2D (XY plane), preserving Z
 * Returns zero vector if XY is zero
 */
export function normalizeVelocity2D(v: Velocity): Velocity {
  const len = velocityLength2D(v);
  if (len === 0) return { x: 0, y: 0, z: v.z };
  return {
    x: v.x / len,
    y: v.y / len,
    z: v.z,
  };
}

/**
 * Scale a velocity vector by a scalar
 */
export function scaleVelocity(v: Velocity, scale: number): Velocity {
  return {
    x: v.x * scale,
    y: v.y * scale,
    z: v.z * scale,
  };
}

/**
 * Add two velocity vectors
 */
export function addVelocity(a: Velocity, b: Velocity): Velocity {
  return {
    x: a.x + b.x,
    y: a.y + b.y,
    z: a.z + b.z,
  };
}

/**
 * Subtract velocity b from velocity a
 */
export function subtractVelocity(a: Velocity, b: Velocity): Velocity {
  return {
    x: a.x - b.x,
    y: a.y - b.y,
    z: a.z - b.z,
  };
}

/**
 * Calculate dot product of two 2D vectors (MetersPosition)
 */
export function dot2D(a: MetersPosition, b: MetersPosition): number {
  return a[0] * b[0] + a[1] * b[1];
}

/**
 * Calculate the 2D distance between two LngLat points
 * Note: This is approximate and only works for small distances
 */
export function distance2D(a: LngLat, b: LngLat): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  return Math.sqrt(dx * dx + dy * dy);
}

/**
 * Check if a point is inside a polygon using ray casting algorithm
 */
export function pointInPolygon(point: LngLat, polygon: LngLat[]): boolean {
  if (polygon.length < 3) return false;

  const x = point[0];
  const y = point[1];
  let inside = false;

  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const pi = polygon[i];
    const pj = polygon[j];
    if (!pi || !pj) continue;

    const xi = pi[0];
    const yi = pi[1];
    const xj = pj[0];
    const yj = pj[1];

    const intersect =
      yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi;

    if (intersect) {
      inside = !inside;
    }
  }

  return inside;
}

/**
 * Find the closest point on a line segment to a given point
 */
export function closestPointOnSegment(
  point: LngLat,
  segStart: LngLat,
  segEnd: LngLat
): LngLat {
  const px = point[0];
  const py = point[1];
  const ax = segStart[0];
  const ay = segStart[1];
  const bx = segEnd[0];
  const by = segEnd[1];

  const abx = bx - ax;
  const aby = by - ay;
  const apx = px - ax;
  const apy = py - ay;

  const ab2 = abx * abx + aby * aby;
  if (ab2 === 0) {
    return segStart;
  }

  const t = Math.max(0, Math.min(1, (apx * abx + apy * aby) / ab2));

  return [ax + t * abx, ay + t * aby];
}

/**
 * Calculate the normal vector pointing from a line segment towards a point
 */
export function segmentNormalToPoint(
  point: LngLat,
  segStart: LngLat,
  segEnd: LngLat
): MetersPosition {
  const closest = closestPointOnSegment(point, segStart, segEnd);
  const dx = point[0] - closest[0];
  const dy = point[1] - closest[1];
  const len = Math.sqrt(dx * dx + dy * dy);

  if (len === 0) {
    // Point is on the segment, return perpendicular to segment
    const segDx = segEnd[0] - segStart[0];
    const segDy = segEnd[1] - segStart[1];
    const segLen = Math.sqrt(segDx * segDx + segDy * segDy);
    if (segLen === 0) return [1, 0];
    // Return perpendicular (rotate 90 degrees)
    return [-segDy / segLen, segDx / segLen];
  }

  return [dx / len, dy / len];
}

/**
 * Check if two line segments intersect
 */
export function segmentsIntersect(
  a1: LngLat,
  a2: LngLat,
  b1: LngLat,
  b2: LngLat
): boolean {
  const d1 = direction(b1, b2, a1);
  const d2 = direction(b1, b2, a2);
  const d3 = direction(a1, a2, b1);
  const d4 = direction(a1, a2, b2);

  if (((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) &&
      ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))) {
    return true;
  }

  if (d1 === 0 && onSegment(b1, b2, a1)) return true;
  if (d2 === 0 && onSegment(b1, b2, a2)) return true;
  if (d3 === 0 && onSegment(a1, a2, b1)) return true;
  if (d4 === 0 && onSegment(a1, a2, b2)) return true;

  return false;
}

/**
 * Calculate the cross product direction
 */
function direction(p1: LngLat, p2: LngLat, p3: LngLat): number {
  return (p3[0] - p1[0]) * (p2[1] - p1[1]) - (p2[0] - p1[0]) * (p3[1] - p1[1]);
}

/**
 * Check if a point is on a segment
 */
function onSegment(p1: LngLat, p2: LngLat, p3: LngLat): boolean {
  return (
    Math.min(p1[0], p2[0]) <= p3[0] &&
    p3[0] <= Math.max(p1[0], p2[0]) &&
    Math.min(p1[1], p2[1]) <= p3[1] &&
    p3[1] <= Math.max(p1[1], p2[1])
  );
}
