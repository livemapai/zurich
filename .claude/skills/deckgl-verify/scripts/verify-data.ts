#!/usr/bin/env npx ts-node

/**
 * Data verification script for GeoJSON files
 * Run with: npx ts-node scripts/verify-data.ts
 */

import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

interface ValidationError {
  file: string;
  issue: string;
  details?: string;
}

function validateGeoJSON(filePath: string): ValidationError[] {
  const errors: ValidationError[] = [];

  if (!existsSync(filePath)) {
    errors.push({ file: filePath, issue: 'File not found' });
    return errors;
  }

  try {
    const content = readFileSync(filePath, 'utf-8');
    const data = JSON.parse(content);

    // Check FeatureCollection
    if (data.type !== 'FeatureCollection') {
      errors.push({
        file: filePath,
        issue: 'Not a FeatureCollection',
        details: `Found type: ${data.type}`,
      });
    }

    // Check features array
    if (!Array.isArray(data.features)) {
      errors.push({
        file: filePath,
        issue: 'Missing features array',
      });
      return errors;
    }

    console.log(`Found ${data.features.length} features in ${filePath}`);

    // Sample validation (first 10 features)
    const sample = data.features.slice(0, 10);

    for (let i = 0; i < sample.length; i++) {
      const feature = sample[i];

      // Check geometry
      if (!feature.geometry) {
        errors.push({
          file: filePath,
          issue: `Feature ${i} missing geometry`,
        });
        continue;
      }

      // Check coordinates
      if (!feature.geometry.coordinates) {
        errors.push({
          file: filePath,
          issue: `Feature ${i} missing coordinates`,
        });
        continue;
      }

      // Check coordinate format (should be [lng, lat])
      const coords = feature.geometry.coordinates;
      if (feature.geometry.type === 'Polygon' && coords[0]?.[0]) {
        const firstCoord = coords[0][0];
        const [lng, lat] = firstCoord;

        // Zurich bounds check
        if (lng < 8 || lng > 9 || lat < 47 || lat > 48) {
          errors.push({
            file: filePath,
            issue: `Feature ${i} coordinates outside Zurich bounds`,
            details: `[${lng}, ${lat}]`,
          });
        }
      }

      // Check properties
      if (feature.properties) {
        const height = feature.properties.height;
        if (height !== undefined && (height < 0 || height > 500)) {
          errors.push({
            file: filePath,
            issue: `Feature ${i} invalid height`,
            details: `height: ${height}`,
          });
        }
      }
    }
  } catch (e: any) {
    errors.push({
      file: filePath,
      issue: 'Parse error',
      details: e.message,
    });
  }

  return errors;
}

// Main
const dataDir = join(process.cwd(), 'public', 'data');
const files = ['zurich-buildings.geojson'];

console.log('=== Data Verification ===\n');

let totalErrors = 0;

for (const file of files) {
  const filePath = join(dataDir, file);
  const errors = validateGeoJSON(filePath);

  if (errors.length === 0) {
    console.log(`✓ ${file} - Valid`);
  } else {
    console.log(`✗ ${file} - ${errors.length} issues:`);
    for (const error of errors) {
      console.log(`  - ${error.issue}${error.details ? `: ${error.details}` : ''}`);
    }
    totalErrors += errors.length;
  }
}

console.log(`\n${totalErrors === 0 ? 'All data valid!' : `${totalErrors} issues found.`}`);
process.exit(totalErrors === 0 ? 0 : 1);
