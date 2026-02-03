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
