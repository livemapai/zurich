import { describe, it, expect } from 'vitest';
import { CONFIG } from './config';

describe('CONFIG', () => {
  describe('render settings', () => {
    it('should have valid FOV', () => {
      expect(CONFIG.render.fov).toBeGreaterThan(30);
      expect(CONFIG.render.fov).toBeLessThan(120);
    });

    it('should have valid clipping planes', () => {
      expect(CONFIG.render.near).toBeGreaterThan(0);
      expect(CONFIG.render.near).toBeLessThan(1);
      expect(CONFIG.render.far).toBeGreaterThan(1000);
    });

    it('should have reasonable frame rate target', () => {
      expect(CONFIG.render.targetFps).toBeGreaterThanOrEqual(30);
      expect(CONFIG.render.targetFps).toBeLessThanOrEqual(144);
    });
  });

  describe('player settings', () => {
    it('should have realistic human dimensions', () => {
      expect(CONFIG.player.height).toBeGreaterThan(1.5);
      expect(CONFIG.player.height).toBeLessThan(2.2);
      expect(CONFIG.player.eyeHeight).toBeLessThan(CONFIG.player.height);
      expect(CONFIG.player.eyeHeight).toBeGreaterThan(1.4);
    });

    it('should have reasonable collision radius', () => {
      expect(CONFIG.player.collisionRadius).toBeGreaterThan(0.1);
      expect(CONFIG.player.collisionRadius).toBeLessThan(0.5);
    });

    it('should have reasonable step height', () => {
      expect(CONFIG.player.stepHeight).toBeGreaterThan(0.1);
      expect(CONFIG.player.stepHeight).toBeLessThan(0.5);
    });
  });

  describe('movement settings', () => {
    it('should have realistic walking speed', () => {
      // Average human walking speed: 1.4 m/s, fast walk: 2-3 m/s
      expect(CONFIG.movement.walk).toBeGreaterThan(1);
      expect(CONFIG.movement.walk).toBeLessThan(10);
    });

    it('should have run speed faster than walk', () => {
      expect(CONFIG.movement.run).toBeGreaterThan(CONFIG.movement.walk);
    });
  });

  describe('mouse settings', () => {
    it('should have reasonable sensitivity', () => {
      expect(CONFIG.mouse.sensitivityX).toBeGreaterThan(0);
      expect(CONFIG.mouse.sensitivityX).toBeLessThan(1);
      expect(CONFIG.mouse.sensitivityY).toBeGreaterThan(0);
      expect(CONFIG.mouse.sensitivityY).toBeLessThan(1);
    });

    it('should have invertY as boolean', () => {
      expect(typeof CONFIG.mouse.invertY).toBe('boolean');
    });
  });

  describe('camera settings', () => {
    it('should have valid pitch limits', () => {
      expect(CONFIG.camera.pitchMin).toBeLessThan(0);
      expect(CONFIG.camera.pitchMax).toBeGreaterThan(0);
      expect(CONFIG.camera.pitchMin).toBeGreaterThanOrEqual(-90);
      expect(CONFIG.camera.pitchMax).toBeLessThanOrEqual(90);
    });
    // Note: minAltitude removed - now calculated dynamically from terrain via AltitudeSystem
  });

  describe('data paths', () => {
    it('should have required data paths', () => {
      expect(CONFIG.data.buildings).toBeDefined();
      expect(CONFIG.data.terrain).toBeDefined();
      expect(typeof CONFIG.data.buildings).toBe('string');
      expect(typeof CONFIG.data.terrain).toBe('string');
    });
  });
});
