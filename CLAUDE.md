# Zurich 3D Walkthrough

A 3D walkable visualization of Zurich using deck.gl with open data from Stadt Zürich.

## Quick Start

```bash
# Install dependencies
pnpm install

# Create sample data
python scripts/run-pipeline.py

# Type check (do NOT start dev server)
pnpm type-check

# Run tests
pnpm test
```

## Important Rules

- **NEVER start the dev server** (`pnpm dev`)
- **NEVER run build** (`pnpm build`)
- Verify changes with `pnpm type-check` and `pnpm test` only

## Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| deck.gl | 9.x | 3D visualization |
| React | 19.x | UI framework |
| TypeScript | 5.7 | Type safety |
| Vite | 6.x | Bundler |
| RBush | 3.x | Spatial indexing |

## Project Structure

```
src/
├── components/          # React components
│   ├── ZurichViewer/   # Main 3D viewer
│   ├── Minimap/        # Navigation map
│   ├── Controls/       # UI overlays
│   └── Loading/        # Loading screen
├── hooks/              # React hooks
│   ├── useKeyboardState.ts   # WASD input
│   ├── useMouseLook.ts       # Pointer lock
│   ├── useGameLoop.ts        # RAF loop
│   ├── useCollisionDetection.ts
│   └── useTerrainElevation.ts
├── systems/            # Game systems
│   ├── MovementController.ts # Velocity calc
│   ├── CameraController.ts   # View state
│   ├── SpatialIndex.ts       # RBush collision
│   └── TerrainSampler.ts     # Elevation
├── layers/             # deck.gl layers
│   ├── BuildingsLayer.ts
│   ├── TerrainLayer.ts
│   └── MinimapLayers.ts
├── lib/                # Configuration
│   ├── config.ts
│   ├── constants.ts
│   └── data/           # Data loaders
├── types/              # TypeScript types
├── utils/              # Utilities
└── styles/             # CSS
```

## Key Concepts

### Coordinate Systems

| System | Format | Usage |
|--------|--------|-------|
| WGS84 | [lng, lat] degrees | deck.gl |
| LV95 | [E, N] meters | Source data |

Conversion at Zurich (~47°N):
- 1° longitude ≈ 75,500m
- 1° latitude ≈ 111,320m

### FirstPersonView

```typescript
interface FirstPersonViewState {
  position: [lng, lat, altitude]; // WGS84 + meters
  bearing: number;  // 0=North, 90=East
  pitch: number;    // -90=up, +90=down
}
```

### Movement Flow

```
Keyboard → Velocity (m/s) → Collision Check → Position (degrees)
                                    ↓
                              Wall Slide
                                    ↓
                              Terrain Lock
```

## Phase Execution

Execute phases in order. Each phase file contains detailed instructions:

1. `.claude/plans/phases/00-foundation.md` - Project setup
2. `.claude/plans/phases/01-skills.md` - Claude Code skills
3. `.claude/plans/phases/02-data-pipeline.md` - Data processing
4. `.claude/plans/phases/03-core-app.md` - React shell
5. `.claude/plans/phases/04-controls.md` - WASD + collision
6. `.claude/plans/phases/05-layers.md` - Building rendering
7. `.claude/plans/phases/06-polish.md` - UI polish

**To execute:** Tell Claude to "Read and execute `.claude/plans/phases/0X-name.md`"

## Skills (After Phase 1)

| Skill | Purpose |
|-------|---------|
| `/deckgl-layer` | Create deck.gl layers |
| `/deckgl-data` | Create data loaders |
| `/deckgl-firstperson` | First-person navigation |
| `/deckgl-verify` | Verify without dev server |

## Data Pipeline

```bash
# Create sample data (for development)
python scripts/run-pipeline.py

# Download real data (optional)
python scripts/run-pipeline.py --real-data

# Validate output
python scripts/validate/check-data.py public/data/zurich-buildings.geojson
```

## Configuration

All settings in `src/lib/config.ts`:

```typescript
CONFIG.player.eyeHeight    // Camera height (1.7m)
CONFIG.movement.walk       // Walk speed (4 m/s)
CONFIG.movement.run        // Run speed (8 m/s)
CONFIG.mouse.sensitivityX  // Mouse sensitivity
CONFIG.camera.pitchMin     // Look down limit
CONFIG.camera.pitchMax     // Look up limit
```

## Documentation

| File | Content |
|------|---------|
| `docs/ARCHITECTURE.md` | System design |
| `docs/DATA_SOURCES.md` | Open data info |
| `docs/CONTROLS.md` | Navigation system |
| `docs/LAYERS.md` | Rendering layers |

## Commands

```bash
pnpm install       # Install dependencies
pnpm type-check    # TypeScript validation
pnpm test          # Run tests
pnpm test:watch    # Tests in watch mode
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Type errors | Run `pnpm type-check` |
| Missing dependencies | Run `pnpm install` |
| No building data | Run `python scripts/run-pipeline.py` |
| Import errors | Check `@/` aliases in tsconfig.json |
| Collision not working | Verify buildings loaded in debug panel |

## Spatial Query CLI

Query buildings, amenities, and shadows via the tile pipeline CLI:

```bash
# Route-building queries
python -m scripts.tile_pipeline.cli route-buildings --route 11
python -m scripts.tile_pipeline.cli route-buildings --list --type tram --sort-by benches
python -m scripts.tile_pipeline.cli route-stats
python -m scripts.tile_pipeline.cli compare-routes 4 11 15

# Shadow queries
python -m scripts.tile_pipeline.cli shadow --lat 47.376 --lng 8.54 --time 14:00
python -m scripts.tile_pipeline.cli balcony --lat 47.376 --lng 8.54 --floor 5

# Amenity queries
python -m scripts.tile_pipeline.cli nearest --lat 47.376 --lng 8.54 --type bench
python -m scripts.tile_pipeline.cli find --lat 47.376 --lng 8.54 --type fountain --radius 200
```

### Rebuilding the Spatial Index

If transit or building data changes, rebuild the index:

```bash
python -m scripts.preprocess.build_route_building_index -v
```

## Data Sources

| Data | Source | License |
|------|--------|---------|
| Buildings | data.stadt-zuerich.ch | CC0 |
| Terrain | swisstopo swissALTI3D | Open |
| Transit (GTFS) | opentransportdata.swiss | Open |
| Benches, Fountains, Toilets | data.stadt-zuerich.ch | CC0 |
| Trees | data.stadt-zuerich.ch | CC0 |
