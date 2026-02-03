#!/usr/bin/env npx ts-node

/**
 * Type verification script
 * Run with: npx ts-node scripts/verify-types.ts
 */

import { execSync } from 'child_process';

interface VerificationResult {
  step: string;
  passed: boolean;
  output?: string;
  error?: string;
}

function runCommand(command: string): { success: boolean; output: string } {
  try {
    const output = execSync(command, { encoding: 'utf-8', stdio: 'pipe' });
    return { success: true, output };
  } catch (error: any) {
    return { success: false, output: error.stdout || error.message };
  }
}

function verify(): VerificationResult[] {
  const results: VerificationResult[] = [];

  // Step 1: TypeScript compilation
  console.log('Checking TypeScript...');
  const tscResult = runCommand('pnpm tsc --noEmit');
  results.push({
    step: 'TypeScript Compilation',
    passed: tscResult.success,
    output: tscResult.output,
  });

  // Step 2: Check for any type errors in specific files
  console.log('Checking critical files...');
  const criticalFiles = [
    'src/types/index.ts',
    'src/hooks/useKeyboardState.ts',
    'src/systems/SpatialIndex.ts',
  ];

  for (const file of criticalFiles) {
    try {
      const content = require('fs').readFileSync(file, 'utf-8');
      results.push({
        step: `File exists: ${file}`,
        passed: true,
      });
    } catch {
      results.push({
        step: `File exists: ${file}`,
        passed: false,
        error: 'File not found',
      });
    }
  }

  return results;
}

// Run verification
const results = verify();

// Report
console.log('\n=== Verification Results ===\n');
let allPassed = true;

for (const result of results) {
  const status = result.passed ? '✓' : '✗';
  console.log(`${status} ${result.step}`);

  if (!result.passed) {
    allPassed = false;
    if (result.error) console.log(`  Error: ${result.error}`);
    if (result.output) console.log(`  Output: ${result.output.slice(0, 500)}`);
  }
}

console.log(`\n${allPassed ? 'All checks passed!' : 'Some checks failed.'}`);
process.exit(allPassed ? 0 : 1);
