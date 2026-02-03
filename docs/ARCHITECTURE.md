# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              React Application                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                          App Component                           │   │
│  │  ┌────────────────────────────────────────────────────────────┐ │   │
│  │  │                      ZurichViewer                          │ │   │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │ │   │
│  │  │  │   DeckGL     │  │   Minimap    │  │ ControlsOverlay  │ │ │   │
│  │  │  │ (FirstPerson │  │ (Orthographic│  │                  │ │ │   │
│  │  │  │    View)     │  │    View)     │  │                  │ │ │   │
│  │  │  └──────┬───────┘  └──────────────┘  └──────────────────┘ │ │   │
│  │  └─────────│──────────────────────────────────────────────────┘ │   │
│  └────────────│────────────────────────────────────────────────────┘   │
│               │                                                         │
│               ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         deck.gl Layers                           │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │   │
│  │  │  BuildingsLayer │  │  TerrainLayer   │  │  MinimapLayers  │  │   │
│  │  │  (SolidPolygon) │  │  (SolidPolygon) │  │  (Scatterplot)  │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                              Game Systems                                │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │ MovementController│  │ CameraController │  │    SpatialIndex      │  │
│  │  (velocity calc)  │  │  (view state)    │  │     (RBush)          │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────────────────────────────┐    │
│  │ TerrainSampler   │  │              Game Loop                    │    │
│  │  (elevation)     │  │  (requestAnimationFrame @ 60fps)         │    │
│  └──────────────────┘  └──────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                              React Hooks                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │ useKeyboardState│  │  useMouseLook   │  │     useGameLoop         │ │
│  │   (WASD keys)   │  │ (pointer lock)  │  │  (RAF timing)           │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘ │
│  ┌─────────────────────────────┐  ┌─────────────────────────────────┐  │
│  │   useCollisionDetection     │  │    useTerrainElevation          │  │
│  │     (RBush queries)         │  │     (height sampling)           │  │
│  └─────────────────────────────┘  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Movement Update Cycle (per frame)

```
┌─────────────────┐
│   Game Loop     │
│   (deltaTime)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌─────────────────┐
│ useKeyboardState│      │  useMouseLook   │
│    (WASD)       │      │ (mouse delta)   │
└────────┬────────┘      └────────┬────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐      ┌─────────────────┐
│ MovementController     │ CameraController │
│ keyboard → velocity    │ delta → rotation │
└────────┬────────┘      └────────┬────────┘
         │                        │
         ├────────────────────────┘
         │
         ▼
┌─────────────────┐
│ Proposed        │
│ Position        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ SpatialIndex    │
│ (collision)     │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐  ┌───────────────┐
│ Clear │  │  Collision    │
│       │  │  Wall Slide   │
└───┬───┘  └───────┬───────┘
    │              │
    └──────┬───────┘
           │
           ▼
┌─────────────────┐
│ TerrainSampler  │
│ (get elevation) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Final ViewState │
│ position +      │
│ rotation        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ React setState  │
│ → Re-render     │
└─────────────────┘
```

## Key Components

### ZurichViewer

Main component that orchestrates:
- deck.gl DeckGL component with FirstPersonView
- Game loop via useGameLoop
- Input handling via useKeyboardState and useMouseLook
- Collision detection via useCollisionDetection
- Layer creation and management

### SpatialIndex

RBush-based spatial index for efficient collision queries:
- Bulk loads building bounding boxes
- O(log n) spatial queries
- Point-in-polygon tests for precise collision
- Wall normal calculation for sliding

### CameraController

Manages FirstPersonViewState:
- Mouse look (bearing/pitch rotation)
- Position updates from velocity
- Altitude clamping for terrain following
- Pitch limits to prevent gimbal lock

## Performance Considerations

### Target: 60 FPS

1. **RBush Spatial Index**
   - O(log n) queries vs O(n) naive search
   - Handles 50k+ buildings efficiently

2. **Layer Memoization**
   - Layers recreated only when data changes
   - useMemo prevents unnecessary recalculation

3. **Delta Time Clamping**
   - Max 100ms delta prevents physics explosions
   - Smooth animation even with frame drops

4. **Pointer Lock**
   - Raw mouse movement, no DOM overhead
   - Delta accumulation for frame sync

## Coordinate Systems

### WGS84 (EPSG:4326)
- Used by deck.gl
- Longitude/Latitude in degrees
- Position: [lng, lat, altitude_meters]

### Swiss LV95 (EPSG:2056)
- Source data format
- Easting/Northing in meters
- Converted in data pipeline

### Movement Calculations
- Velocity in meters/second
- Converted to degrees using:
  - `METERS_PER_DEGREE.lng ≈ 75,500` (at 47°N)
  - `METERS_PER_DEGREE.lat ≈ 111,320`
