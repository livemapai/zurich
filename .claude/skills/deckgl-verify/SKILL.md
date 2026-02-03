---
name: deckgl-verify
description: Verify deck.gl implementation without starting dev server. Use after making changes to confirm correctness.
allowed-tools: Read, Bash, Glob, Grep
---

# deck.gl Verification Skill

Validates implementation through type checking, unit tests, and static analysis.

## Quick Checks

### Type Check
```bash
pnpm type-check
```

### Run Tests
```bash
pnpm test
```

### Check Imports
```bash
# Verify no circular dependencies
npx madge --circular src/
```

## Full Verification Workflow

### Step 1: Type Safety
- [ ] Run `pnpm type-check`
- [ ] No errors expected
- [ ] Warnings are acceptable

### Step 2: Tests
- [ ] Run `pnpm test`
- [ ] All tests pass
- [ ] Coverage acceptable

### Step 3: Import Validation
- [ ] Check all deck.gl imports resolve
- [ ] Check @/ alias resolves
- [ ] No circular dependencies

### Step 4: Data Validation (if applicable)
- [ ] GeoJSON files parse correctly
- [ ] Coordinates are in correct format
- [ ] Building heights are positive

### Step 5: Layer Configuration
- [ ] Layer IDs are unique
- [ ] Required props provided
- [ ] Color values in valid range (0-255)

### Step 6: Constant Consistency
- [ ] All uses of `ZURICH_BASE_ELEVATION` use the same value (408)
- [ ] All uses of `METERS_PER_DEGREE` use correct values (lng: 75500, lat: 111320)
- [ ] No hardcoded elevation or conversion values (should import from types)
- [ ] Camera initial altitude matches ground + eye height

### Step 7: Coordinate System Check
- [ ] FirstPersonViewState uses dual-anchor system (longitude/latitude + position)
- [ ] `position` array contains meters, not degrees
- [ ] Movement converts velocity (m/s) to degrees before updating longitude/latitude
- [ ] Altitude in position[2] is absolute (above sea level), not relative

## Common Verification Commands

```bash
# Full type check
pnpm type-check

# Type check with watch
pnpm tsc --noEmit --watch

# Run specific test file
pnpm test src/systems/SpatialIndex.test.ts

# Validate GeoJSON
node scripts/validate-geojson.js public/data/buildings.geojson

# Check bundle size (dry run)
pnpm build --dry-run
```

## Consistency Verification Commands

Use these grep commands to check for constant consistency:

```bash
# Find hardcoded elevation values (should use ZURICH_BASE_ELEVATION)
grep -rn "408\|409\|410" src/ --include="*.ts" --include="*.tsx" | grep -v "node_modules"

# Find hardcoded meters-per-degree values (should use METERS_PER_DEGREE)
grep -rn "75500\|111320\|73000\|111000" src/ --include="*.ts" --include="*.tsx" | grep -v "node_modules"

# Verify all files use imported constants
grep -rn "ZURICH_BASE_ELEVATION\|METERS_PER_DEGREE" src/ --include="*.ts" --include="*.tsx"

# Check for position array misuse (degrees where meters expected)
grep -rn "position:\s*\[8\." src/ --include="*.ts" --include="*.tsx"  # Likely degrees, should be meters
```

## Verification Scripts

### verify-types.ts
Runs TypeScript compiler and reports errors.

### verify-data.ts
Validates GeoJSON files for correct structure.

## Troubleshooting

| Issue | Verification | Solution |
|-------|--------------|----------|
| Import errors | `pnpm type-check` | Check path aliases in tsconfig |
| Test failures | `pnpm test` | Read error messages, fix code |
| Data validation | Run verify-data.ts | Check GeoJSON structure |
| Runtime errors | Build + manual test | Use browser dev tools |

## When to Run

Run verification after:
- Creating new files
- Modifying types
- Changing imports
- Updating data files
- Before committing
