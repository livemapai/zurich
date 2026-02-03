import { describe, it, expect } from 'vitest';
import {
  ZURICH_CENTER,
  ZURICH_BOUNDS,
  METERS_PER_DEGREE,
  DEFAULT_POSITION,
  DEG_TO_RAD,
  RAD_TO_DEG,
  metersToDegreesLng,
  metersToDegreesLat,
  degreesLngToMeters,
  degreesLatToMeters,
  clamp,
  lerp,
  normalizeAngle,
} from './constants';

describe('constants', () => {
  describe('ZURICH_CENTER', () => {
    it('should be valid WGS84 coordinates', () => {
      // ZURICH_CENTER is [lng, lat] tuple
      const [lng, lat] = ZURICH_CENTER;
      expect(lng).toBeGreaterThan(8);
      expect(lng).toBeLessThan(9);
      expect(lat).toBeGreaterThan(47);
      expect(lat).toBeLessThan(48);
    });
  });

  describe('ZURICH_BOUNDS', () => {
    it('should contain ZURICH_CENTER', () => {
      const [lng, lat] = ZURICH_CENTER;
      expect(lng).toBeGreaterThan(ZURICH_BOUNDS.minLng);
      expect(lng).toBeLessThan(ZURICH_BOUNDS.maxLng);
      expect(lat).toBeGreaterThan(ZURICH_BOUNDS.minLat);
      expect(lat).toBeLessThan(ZURICH_BOUNDS.maxLat);
    });
  });

  describe('METERS_PER_DEGREE', () => {
    it('should have realistic values for ~47°N latitude', () => {
      // At 47°N, 1 degree longitude ≈ 75,500m
      expect(METERS_PER_DEGREE.lng).toBeGreaterThan(70000);
      expect(METERS_PER_DEGREE.lng).toBeLessThan(80000);
      // 1 degree latitude ≈ 111,320m
      expect(METERS_PER_DEGREE.lat).toBeGreaterThan(110000);
      expect(METERS_PER_DEGREE.lat).toBeLessThan(112000);
    });
  });

  describe('DEFAULT_POSITION', () => {
    it('should be a valid 3D position', () => {
      expect(DEFAULT_POSITION).toHaveLength(3);
      expect(DEFAULT_POSITION[0]).toBe(ZURICH_CENTER[0]);
      expect(DEFAULT_POSITION[1]).toBe(ZURICH_CENTER[1]);
      expect(DEFAULT_POSITION[2]).toBeGreaterThan(0); // Relative altitude for overview
    });
  });
});

describe('coordinate conversion', () => {
  describe('metersToDegreesLng', () => {
    it('should convert meters to degrees', () => {
      const meters = METERS_PER_DEGREE.lng;
      expect(metersToDegreesLng(meters)).toBeCloseTo(1, 5);
    });

    it('should handle zero', () => {
      expect(metersToDegreesLng(0)).toBe(0);
    });
  });

  describe('metersToDegreesLat', () => {
    it('should convert meters to degrees', () => {
      const meters = METERS_PER_DEGREE.lat;
      expect(metersToDegreesLat(meters)).toBeCloseTo(1, 5);
    });
  });

  describe('degreesLngToMeters', () => {
    it('should be inverse of metersToDegreesLng', () => {
      const meters = 1000;
      const degrees = metersToDegreesLng(meters);
      expect(degreesLngToMeters(degrees)).toBeCloseTo(meters, 5);
    });
  });

  describe('degreesLatToMeters', () => {
    it('should be inverse of metersToDegreesLat', () => {
      const meters = 1000;
      const degrees = metersToDegreesLat(meters);
      expect(degreesLatToMeters(degrees)).toBeCloseTo(meters, 5);
    });
  });
});

describe('utility functions', () => {
  describe('clamp', () => {
    it('should clamp values within range', () => {
      expect(clamp(5, 0, 10)).toBe(5);
      expect(clamp(-5, 0, 10)).toBe(0);
      expect(clamp(15, 0, 10)).toBe(10);
    });

    it('should handle edge cases', () => {
      expect(clamp(0, 0, 10)).toBe(0);
      expect(clamp(10, 0, 10)).toBe(10);
    });
  });

  describe('lerp', () => {
    it('should interpolate between values', () => {
      expect(lerp(0, 10, 0)).toBe(0);
      expect(lerp(0, 10, 1)).toBe(10);
      expect(lerp(0, 10, 0.5)).toBe(5);
    });

    it('should handle negative values', () => {
      expect(lerp(-10, 10, 0.5)).toBe(0);
    });
  });

  describe('normalizeAngle', () => {
    it('should normalize angles to [0, 360)', () => {
      expect(normalizeAngle(0)).toBe(0);
      expect(normalizeAngle(90)).toBe(90);
      expect(normalizeAngle(360)).toBe(0);
      expect(normalizeAngle(450)).toBe(90);
      expect(normalizeAngle(-90)).toBe(270);
      expect(normalizeAngle(-360)).toBe(0);
    });
  });

  describe('DEG_TO_RAD and RAD_TO_DEG', () => {
    it('should be inverses', () => {
      expect(DEG_TO_RAD * RAD_TO_DEG).toBeCloseTo(1, 10);
    });

    it('should convert correctly', () => {
      expect(180 * DEG_TO_RAD).toBeCloseTo(Math.PI, 10);
      expect(Math.PI * RAD_TO_DEG).toBeCloseTo(180, 10);
    });
  });
});
