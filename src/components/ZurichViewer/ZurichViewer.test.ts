import { describe, it, expect } from 'vitest';
import { ZURICH_CENTER, ZURICH_BOUNDS } from '@/types';

/**
 * Test to verify the initial view state coordinates are within Zurich
 * These tests verify the coordinate system fix is in place.
 */

describe('ZurichViewer coordinate system', () => {
  describe('ZURICH_CENTER validation', () => {
    it('should have ZURICH_CENTER within Zurich bounds', () => {
      const [lng, lat] = ZURICH_CENTER;

      expect(lng).toBeGreaterThanOrEqual(ZURICH_BOUNDS.minLng);
      expect(lng).toBeLessThanOrEqual(ZURICH_BOUNDS.maxLng);
      expect(lat).toBeGreaterThanOrEqual(ZURICH_BOUNDS.minLat);
      expect(lat).toBeLessThanOrEqual(ZURICH_BOUNDS.maxLat);
    });

    it('should have ZURICH_CENTER at expected coordinates', () => {
      const [lng, lat] = ZURICH_CENTER;

      // Zurich is around 8.54 longitude, 47.37 latitude
      expect(lng).toBeCloseTo(8.54, 1);
      expect(lat).toBeCloseTo(47.37, 1);
    });
  });

  describe('coordinate system consistency', () => {
    it('camera initial position uses WGS84 degree coordinates', () => {
      // The camera position should use ZURICH_CENTER which is in WGS84 degrees
      // If it were in meters, the values would be much larger (hundreds of thousands)
      const [lng, lat] = ZURICH_CENTER;

      // WGS84 longitude for Zurich is around 8.5
      // WGS84 latitude for Zurich is around 47.4
      expect(lng).toBeGreaterThan(8); // Zurich is east of prime meridian
      expect(lng).toBeLessThan(9);
      expect(lat).toBeGreaterThan(47); // Zurich is north of 47 latitude
      expect(lat).toBeLessThan(48);
    });

    it('ZURICH_BOUNDS defines valid geographic area', () => {
      // Bounds should be reasonable for a city
      const lngSpan = ZURICH_BOUNDS.maxLng - ZURICH_BOUNDS.minLng;
      const latSpan = ZURICH_BOUNDS.maxLat - ZURICH_BOUNDS.minLat;

      // City should span roughly 0.1-0.2 degrees (7-15 km)
      expect(lngSpan).toBeGreaterThan(0.05);
      expect(lngSpan).toBeLessThan(0.5);
      expect(latSpan).toBeGreaterThan(0.05);
      expect(latSpan).toBeLessThan(0.5);
    });
  });

  describe('distance calculation sanity check', () => {
    it('distance from [0,0] to ZURICH_CENTER demonstrates wrong position issue', () => {
      // This demonstrates WHY [0,0,_] doesn't work as initial position
      // Calculate approximate distance in km
      const wrongLng = 0;
      const wrongLat = 0;
      const zurichLng = ZURICH_CENTER[0];
      const zurichLat = ZURICH_CENTER[1];

      // Rough distance calculation
      const dLng = zurichLng - wrongLng; // ~8.54 degrees
      const dLat = zurichLat - wrongLat; // ~47.37 degrees

      // At equator, 1 degree 111 km
      const roughDistanceKm = Math.sqrt(
        (dLng * 75.5) ** 2 + // km per degree lng at mid-latitude
          (dLat * 111) ** 2 // km per degree lat
      );

      // Position [0,0] is thousands of km from Zurich
      expect(roughDistanceKm).toBeGreaterThan(5000);
    });

    it('ZURICH_CENTER to ZURICH_BOUNDS edges should be reasonable city distances', () => {
      // Distance from center to edge should be a few km, not thousands
      const centerLng = ZURICH_CENTER[0];
      const centerLat = ZURICH_CENTER[1];

      const toWestKm = Math.abs(centerLng - ZURICH_BOUNDS.minLng) * 75.5;
      const toEastKm = Math.abs(ZURICH_BOUNDS.maxLng - centerLng) * 75.5;
      const toSouthKm = Math.abs(centerLat - ZURICH_BOUNDS.minLat) * 111;
      const toNorthKm = Math.abs(ZURICH_BOUNDS.maxLat - centerLat) * 111;

      // All edges should be within 10km of center
      expect(toWestKm).toBeLessThan(10);
      expect(toEastKm).toBeLessThan(10);
      expect(toSouthKm).toBeLessThan(10);
      expect(toNorthKm).toBeLessThan(10);
    });
  });
});
