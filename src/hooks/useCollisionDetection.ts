/**
 * useCollisionDetection - Building collision detection hook
 *
 * Manages the spatial index for building collision detection.
 * Provides collision checking and wall sliding.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { BuildingCollection, CollisionResult, LngLat, Velocity } from '@/types';
import { METERS_PER_DEGREE } from '@/types';
import { SpatialIndex, createSpatialIndex } from '@/systems';

interface UseCollisionDetectionOptions {
  /** Building data to load */
  buildings?: BuildingCollection;
  /** Player collision radius in meters */
  collisionRadius?: number;
}

interface UseCollisionDetectionResult {
  /** Whether buildings are loaded into the index */
  isLoaded: boolean;
  /** Number of buildings in the index */
  buildingCount: number;
  /** Check collision at a position */
  checkCollision: (position: LngLat) => CollisionResult;
  /** Move with collision detection and wall sliding */
  moveWithCollision: (
    currentPos: LngLat,
    velocity: Velocity,
    deltaTime: number
  ) => LngLat;
}

/**
 * Hook to manage collision detection with buildings
 */
export function useCollisionDetection(
  options: UseCollisionDetectionOptions = {}
): UseCollisionDetectionResult {
  const { buildings, collisionRadius } = options;

  const [isLoaded, setIsLoaded] = useState(false);
  const [buildingCount, setBuildingCount] = useState(0);

  // Spatial index stored in ref to avoid re-renders
  const indexRef = useRef<SpatialIndex>(createSpatialIndex());

  // Load buildings when they change
  useEffect(() => {
    const index = indexRef.current;

    if (buildings && buildings.features.length > 0) {
      index.clear();
      index.load(buildings);
      setIsLoaded(true);
      setBuildingCount(index.getCount());
    } else {
      index.clear();
      setIsLoaded(false);
      setBuildingCount(0);
    }
  }, [buildings]);

  /**
   * Check collision at a position
   */
  const checkCollision = useCallback(
    (position: LngLat): CollisionResult => {
      return indexRef.current.checkCollision(position, collisionRadius);
    },
    [collisionRadius]
  );

  /**
   * Move with collision detection and wall sliding
   *
   * Returns the final valid position after collision response
   */
  const moveWithCollision = useCallback(
    (currentPos: LngLat, velocity: Velocity, deltaTime: number): LngLat => {
      const index = indexRef.current;

      // If no movement, return current position
      if (velocity.x === 0 && velocity.y === 0) {
        return currentPos;
      }

      // Calculate proposed position
      const deltaLng = (velocity.x * deltaTime) / METERS_PER_DEGREE.lng;
      const deltaLat = (velocity.y * deltaTime) / METERS_PER_DEGREE.lat;

      const proposedPos: LngLat = [
        currentPos[0] + deltaLng,
        currentPos[1] + deltaLat,
      ];

      // Check collision at proposed position
      const collision = index.checkCollision(proposedPos, collisionRadius);

      if (!collision.collides) {
        // No collision, move to proposed position
        return proposedPos;
      }

      // Wall sliding: project velocity onto wall tangent
      if (collision.normal) {
        const slidVel = index.slideVelocity(
          [velocity.x, velocity.y],
          collision.normal
        );

        // Calculate slid position
        const slidDeltaLng = (slidVel[0] * deltaTime) / METERS_PER_DEGREE.lng;
        const slidDeltaLat = (slidVel[1] * deltaTime) / METERS_PER_DEGREE.lat;

        const slidPos: LngLat = [
          currentPos[0] + slidDeltaLng,
          currentPos[1] + slidDeltaLat,
        ];

        // Check collision at slid position
        const slidCollision = index.checkCollision(slidPos, collisionRadius);

        if (!slidCollision.collides) {
          // Slide succeeded
          return slidPos;
        }
      }

      // Both moves failed, stay in place
      return currentPos;
    },
    [collisionRadius]
  );

  return {
    isLoaded,
    buildingCount,
    checkCollision,
    moveWithCollision,
  };
}
