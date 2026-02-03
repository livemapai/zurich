---
name: deckgl-layer
description: Scaffold a new deck.gl layer with factory function and React component. Use when adding buildings, terrain, points, or paths.
allowed-tools: Read, Write, Edit, Glob, Grep
---

# deck.gl Layer Skill

Creates deck.gl layers following the project's established patterns with proper TypeScript types and factory functions.

## Prerequisites

Before using this skill, verify:
- [ ] `src/types/index.ts` exists with core types
- [ ] deck.gl dependencies installed (`pnpm list deck.gl`)
- [ ] Layer directory exists: `src/layers/`

## Workflow

### Step 1: Gather Requirements
Ask the user or determine:
- [ ] Layer name (e.g., "Buildings", "Terrain", "Points")
- [ ] Layer type (PolygonLayer, TerrainLayer, ScatterplotLayer, etc.)
- [ ] Data format (GeoJSON, binary, etc.)
- [ ] Required properties from data

### Step 2: Read Reference Documentation
- [ ] Read `reference/polygon-layer.md` (or relevant type)
- [ ] Note required props and their types
- [ ] Check deck.gl v9 API for any changes

### Step 3: Create Type Definitions
- [ ] Create `src/layers/{LayerName}Layer.types.ts`
- [ ] Define data shape interface
- [ ] Define layer config interface
- [ ] Export all types

### Step 4: Create Layer Factory
- [ ] Create `src/layers/{LayerName}Layer.ts`
- [ ] Import deck.gl layer class
- [ ] Create factory function with typed config
- [ ] Add JSDoc documentation
- [ ] Export factory function

### Step 5: Create React Component (Optional)
- [ ] Create `src/components/layers/{LayerName}Layer.tsx`
- [ ] Use factory function internally
- [ ] Add props for visibility, data source
- [ ] Handle loading states

### Step 6: Export from Index
- [ ] Add export to `src/layers/index.ts`
- [ ] Add component export to `src/components/layers/index.ts`

### Step 7: Elevation Consistency Check

For layers with 3D elevation:
- [ ] Use `ZURICH_BASE_ELEVATION` from `@/types` (408 meters)
- [ ] Verify `elevationScale` matches expectations
- [ ] Check `getElevation` accessor returns absolute altitude (not relative)
- [ ] Ensure buildings have same elevation baseline as camera

**Elevation Checklist:**
```typescript
// CORRECT - using project constant
import { ZURICH_BASE_ELEVATION } from '@/types';

// For buildings
getElevation: () => ZURICH_BASE_ELEVATION, // Base at 408m

// For extruded polygons
getElevation: (d) => d.properties.baseElevation ?? ZURICH_BASE_ELEVATION,
```

### Step 8: Verify
- [ ] Run `pnpm type-check`
- [ ] Confirm no type errors
- [ ] Check imports resolve correctly

## Reference Files

See `reference/` directory for:
- `polygon-layer.md` - For buildings, areas, regions
- `terrain-layer.md` - For elevation/terrain
- `scatterplot-layer.md` - For point data

## Templates

Use templates from `templates/` directory:
- `layer-factory.template.ts` - Base factory pattern
- `layer-component.template.tsx` - React wrapper
- `layer-types.template.ts` - Type definitions

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Cannot find module deck.gl" | Missing dependency | Run `pnpm install` |
| Type mismatch on data | Wrong data shape | Check GeoJSON structure matches interface |
| Layer not rendering | Data is empty/null | Add null checks, log data in console |
| WebGL errors | Invalid props | Check prop values (opacity 0-1, colors 0-255) |
| "accessor" errors in v9 | Wrong type | Ensure accessor returns correct type (e.g., Position[][] not Position[]) |
| Buildings floating | Wrong base elevation | Use `ZURICH_BASE_ELEVATION` (408) |
| Buildings underground | Elevation too low | Check altitude includes ground level |
| Z-fighting/flickering | Overlapping surfaces | Adjust elevation by small offset |
| MultiPolygon not rendering | Wrong coordinate accessor | Handle both Polygon and MultiPolygon in `getPolygon` |

## Recovery

If this skill fails partway through:
1. Delete any partially created files in `src/layers/`
2. Remove exports added to index files
3. Run `pnpm type-check` to identify broken imports
4. Re-run skill from Step 1

## External References

- [deck.gl Layer Docs](https://deck.gl/docs/api-reference/layers)
- [SolidPolygonLayer](https://deck.gl/docs/api-reference/layers/solid-polygon-layer)
- [TerrainLayer](https://deck.gl/docs/api-reference/geo-layers/terrain-layer)
