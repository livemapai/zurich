# Transit Data Pipeline

Complete documentation for the GTFS transit data pipeline from VBZ source data to deck.gl visualization.

## Overview

| Metric | Value |
|--------|-------|
| Routes | ~365 (trams, buses, ferries, funiculars) |
| Trips | ~29,000 daily |
| Source | VBZ/ZVV GTFS |
| JSON Size | ~244 MB |
| Binary Size | ~40 MB |
| Memory Savings | ~95% runtime reduction |

The pipeline transforms VBZ GTFS data into an optimized binary format for real-time transit visualization using deck.gl's TripsLayer.

## Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TRANSIT DATA PIPELINE                              │
└─────────────────────────────────────────────────────────────────────────────┘

   VBZ GTFS ZIP                    JSON                         Binary
  ┌──────────────┐             ┌──────────────┐             ┌──────────────┐
  │ routes.txt   │             │              │             │              │
  │ stops.txt    │  gtfs_      │ zurich-tram- │  gtfs_to_   │ gtfs-trips   │
  │ trips.txt    │────────────▶│ trips.json   │────────────▶│ .bin         │
  │ stop_times   │  trips.py   │              │  binary.py  │              │
  │ shapes.txt   │             │ (244 MB)     │             │ (40 MB)      │
  └──────────────┘             └──────────────┘             └──────────────┘
        │                            │                            │
        │                            │                            │
        ▼                            ▼                            ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                          TypeScript Consumer                              │
  │                                                                           │
  │  ┌───────────────────┐    ┌───────────────────┐    ┌──────────────────┐  │
  │  │  ChunkManager.ts  │───▶│  useGTFSTrips.ts  │───▶│ TramTripsLayer   │  │
  │  │  (HTTP Range)     │    │  (React hook)      │    │ (deck.gl)        │  │
  │  └───────────────────┘    └───────────────────┘    └──────────────────┘  │
  └──────────────────────────────────────────────────────────────────────────┘
```

## 1. Data Source

### VBZ GTFS Feed

- **URL**: https://data.stadt-zuerich.ch/dataset/vbz_fahrplandaten_gtfs
- **Format**: GTFS (General Transit Feed Specification)
- **License**: CC0 (Public Domain)
- **Update Frequency**: Yearly releases (e.g., `2025_google_transit.zip`)

### GTFS Route Types

| Code | Type | Example |
|------|------|---------|
| 0 | Tram/Light Rail | Lines 2-17 |
| 1 | Subway/Metro | - |
| 2 | Rail (S-Bahn) | S-Bahn lines |
| 3 | Bus | Bus network |
| 4 | Ferry | Lake Zurich ferries |
| 5 | Cable Tram | Polybahn |
| 6 | Aerial Lift | Cable cars |
| 7 | Funicular | Rigiblick, Dolderbahn |

### Files Used

| File | Purpose |
|------|---------|
| `routes.txt` | Route metadata (name, type, color) |
| `stops.txt` | Stop locations (lat/lon) |
| `trips.txt` | Trip definitions with shape references |
| `stop_times.txt` | Arrival/departure times per stop |
| `shapes.txt` | Route geometry waypoints |

## 2. Download Pipeline

### gtfs_trips.py

**Location**: `scripts/download/gtfs_trips.py`

Downloads and processes GTFS data into JSON format suitable for deck.gl TripsLayer.

#### Processing Steps

1. **Download** - Fetches yearly GTFS ZIP (tries current year, falls back to previous)
2. **Parse Routes** - Extracts route metadata (all transit types)
3. **Parse Stops** - Loads stop locations
4. **Parse Trips** - Links trips to routes and shapes
5. **Parse Stop Times** - Loads arrival/departure times
6. **Parse Shapes** - Loads route geometry
7. **Interpolate Timestamps** - Calculates timestamp for each shape point
8. **Add Elevation** - Samples terrain height per waypoint (optional)

#### Timestamp Interpolation

The key algorithm matches stops to shape points, then linearly interpolates timestamps based on distance:

```python
# For each shape point between stops:
progress = cumulative_distance / total_segment_distance
timestamp = start_time + progress * (end_time - start_time)
```

#### Output Format

```json
{
  "trips": [{
    "route_id": "10",
    "route_short_name": "10",
    "route_type": 0,
    "route_color": "#00a1e0",
    "headsign": "Bahnhof Oerlikon",
    "path": [[8.54, 47.37, 410.5], [8.55, 47.38, 412.0]],
    "timestamps": [28800, 28920]
  }],
  "metadata": {
    "trip_count": 29346,
    "route_count": 365,
    "generated": "2025-02-04T10:30:00",
    "source": "VBZ GTFS (data.stadt-zuerich.ch)",
    "license": "CC0 Public Domain",
    "has_elevation": true
  }
}
```

#### Usage

```bash
# Full download with elevation
python3 scripts/download/gtfs_trips.py

# Without elevation (faster, smaller)
python3 scripts/download/gtfs_trips.py --no-elevation

# Limited trips for testing
python3 scripts/download/gtfs_trips.py --limit 10
```

## 3. Binary Conversion

### gtfs_to_binary.py

**Location**: `scripts/download/gtfs_to_binary.py`

Converts JSON to optimized binary format with shape deduplication and hourly chunking.

#### Optimizations

| Technique | Savings |
|-----------|---------|
| Shape deduplication | ~80% (29k trips → ~1,878 unique shapes) |
| Hourly chunking | On-demand loading via HTTP Range |
| Binary encoding | Smaller than JSON strings |
| Float32 coordinates | Sufficient precision for visualization |

#### Shape Deduplication

Many trips share identical routes. Shapes are deduplicated by hashing:

```python
# Hash based on first/last coordinates + length
key = f"{first[0]:.4f},{first[1]:.4f}|{last[0]:.4f},{last[1]:.4f}|{len(coords)}"
shape_hash = hashlib.md5(key.encode()).hexdigest()[:16]
```

#### Hourly Chunking

Trips are grouped by start hour (4:00 to 27:00 for overnight trips):

| Hour | Description |
|------|-------------|
| 4-5 | Early morning |
| 6-8 | Morning rush |
| 12-13 | Midday |
| 16-18 | Evening rush |
| 22-27 | Night service (27:00 = 03:00 next day) |

#### Usage

```bash
# Convert JSON to binary
python3 scripts/download/gtfs_to_binary.py

# Custom paths
python3 scripts/download/gtfs_to_binary.py \
  --input public/data/zurich-tram-trips.json \
  --output public/data/gtfs/gtfs-trips.bin
```

## 4. Binary File Format

### File Structure

```
┌─────────────────────────────────────────────────────────────────┐
│ HEADER (32 bytes)                                               │
│ ┌─────────┬─────────┬─────────┬─────────┬─────────┬───────────┐│
│ │ Magic   │ Version │ Shapes  │ Routes  │Headsigns│ Chunks    ││
│ │ "GTFS"  │ uint32  │ uint32  │ uint32  │ uint32  │ uint32    ││
│ │ 4 bytes │ 4 bytes │ 4 bytes │ 4 bytes │ 4 bytes │ 4 bytes   ││
│ └─────────┴─────────┴─────────┴─────────┴─────────┴───────────┘│
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ Shape Table Offset (uint32) │ Route Table Offset (uint32)  ││
│ └─────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│ SHAPE TABLE (~7 MB) - Loaded once, kept in memory               │
│ ┌───────────────────────────────────────────────────────────────│
│ │ For each shape:                                               │
│ │   point_count: uint32                                         │
│ │   coordinates: float32[point_count * 3]  (lng, lat, elev)    │
│ └───────────────────────────────────────────────────────────────│
├─────────────────────────────────────────────────────────────────┤
│ ROUTE TABLE                                                     │
│ ┌───────────────────────────────────────────────────────────────│
│ │ For each route: nameOffset(u32), type(u8), r(u8), g(u8), b(u8)│
│ │ Followed by: null-terminated route name strings               │
│ └───────────────────────────────────────────────────────────────│
├─────────────────────────────────────────────────────────────────┤
│ HEADSIGN TABLE                                                  │
│ ┌───────────────────────────────────────────────────────────────│
│ │ Offset table: uint32[headsign_count]                          │
│ │ Followed by: null-terminated headsign strings                 │
│ └───────────────────────────────────────────────────────────────│
├─────────────────────────────────────────────────────────────────┤
│ CHUNK INDEX                                                     │
│ ┌───────────────────────────────────────────────────────────────│
│ │ For hours 4-27:                                               │
│ │   hour: uint32, byte_offset: uint32, byte_size: uint32       │
│ └───────────────────────────────────────────────────────────────│
├─────────────────────────────────────────────────────────────────┤
│ HOURLY CHUNKS - Loaded on-demand via HTTP Range                 │
│ ┌───────────────────────────────────────────────────────────────│
│ │ Chunk 04: [trip_count: u32][Trip][Trip]...                   │
│ │ Chunk 05: [trip_count: u32][Trip][Trip]...                   │
│ │ ...                                                           │
│ │ Chunk 27: [trip_count: u32][Trip][Trip]...                   │
│ └───────────────────────────────────────────────────────────────│
└─────────────────────────────────────────────────────────────────┘
```

### Trip Record Format

Each trip within a chunk (20 byte header + variable timestamps):

| Field | Type | Bytes | Description |
|-------|------|-------|-------------|
| shape_index | uint32 | 4 | Index into shape table |
| route_index | uint16 | 2 | Index into route table |
| headsign_index | uint16 | 2 | Index into headsign table |
| timestamp_count | uint32 | 4 | Number of timestamps |
| start_time | uint32 | 4 | First timestamp (seconds since midnight) |
| reserved | uint32 | 4 | Future use |
| timestamps | uint32[] | 4×n | Absolute timestamps |

### Constants

```typescript
// src/types/gtfs-binary.ts
export const GTFS_BINARY_MAGIC = 0x53465447;  // "GTFS" little-endian
export const GTFS_BINARY_VERSION = 1;
export const GTFS_HEADER_SIZE = 32;
export const GTFS_TRIP_HEADER_SIZE = 20;
export const GTFS_MIN_HOUR = 4;
export const GTFS_MAX_HOUR = 27;
```

## 5. TypeScript Consumer

### ChunkManager.ts

**Location**: `src/lib/gtfs/ChunkManager.ts`

Manages binary GTFS data with HTTP Range requests for on-demand loading.

#### Memory Management

```
┌─────────────────────────────────────────────────────────────┐
│                    ChunkManager Memory                       │
├─────────────────────────────────────────────────────────────┤
│ Master Index (always loaded):                                │
│   - Shape table: ~7 MB (1,878 shapes × ~4KB avg)            │
│   - Route table: ~50 KB                                      │
│   - Headsign table: ~100 KB                                  │
│   - Chunk index: ~300 bytes                                  │
├─────────────────────────────────────────────────────────────┤
│ Active Chunks (LRU, max 3-5):                               │
│   - Current hour ± 1 hour window                             │
│   - ~500 KB per chunk average                                │
│   - Evicted when outside window                              │
└─────────────────────────────────────────────────────────────┘
```

#### API

```typescript
const manager = new GTFSChunkManager("/data/gtfs/gtfs-trips.bin");

// Initialize - loads master index (~7 MB)
await manager.initialize();

// Load chunks for current hour ± 1
await manager.updateActiveChunks(12);  // Loads hours 11, 12, 13

// Get trips visible at current time
const trips = manager.getVisibleTrips(43200);  // noon

// Check state
const state = manager.getLoadingState();
// { isIndexLoading, isChunksLoading, loadedHours, totalTrips }
```

### useGTFSTrips Hook

**Location**: `src/hooks/useGTFSTrips.ts`

React hook for streaming GTFS data with automatic chunk management.

#### Features

- **Auto-detection**: Tries binary format, falls back to JSON
- **Chunk updates**: Automatically loads chunks as time changes
- **Time filtering**: Returns trips within ±30 minute window
- **Loading states**: Provides UI feedback during loading

#### Usage

```typescript
function TransitLayer({ timeOfDay }: { timeOfDay: number }) {
  const {
    trips,           // RenderableTrip[] ready for deck.gl
    isLoading,       // Initial load in progress
    isChunksLoading, // Chunk fetch in progress
    error,           // Error message if failed
    isBinaryMode,    // true if using binary format
    totalTrips       // Total available trips
  } = useGTFSTrips(timeOfDay * 60);  // Convert minutes to seconds

  if (isLoading) return <LoadingIndicator />;
  if (error) return <ErrorMessage error={error} />;

  return (
    <TripsLayer
      data={trips}
      currentTime={timeOfDay * 60}
      getPath={d => d.path}
      getTimestamps={d => d.timestamps}
      getColor={d => hexToRgb(d.route_color)}
    />
  );
}
```

## 6. Regeneration Commands

### Full Pipeline

```bash
# Step 1: Download and process GTFS to JSON
python3 scripts/download/gtfs_trips.py
# Output: public/data/zurich-tram-trips.json (~244 MB)

# Step 2: Convert to binary format
python3 scripts/download/gtfs_to_binary.py
# Output: public/data/gtfs/gtfs-trips.bin (~40 MB)
#         public/data/gtfs/gtfs-trips.manifest.json
```

### Quick Test (Limited Data)

```bash
# Download with trip limit (faster for testing)
python3 scripts/download/gtfs_trips.py --limit 5

# Convert to binary
python3 scripts/download/gtfs_to_binary.py
```

### Without Elevation

```bash
# Skip terrain elevation (faster, smaller)
python3 scripts/download/gtfs_trips.py --no-elevation
```

### Verify Output

```bash
# Check file sizes
ls -lh public/data/zurich-tram-trips.json
ls -lh public/data/gtfs/

# Inspect manifest
cat public/data/gtfs/gtfs-trips.manifest.json | jq '.shapes, .routes, .chunks | length'
```

## 7. Memory Comparison

### File Sizes

| Format | File Size | Notes |
|--------|-----------|-------|
| JSON | ~244 MB | Full trips with coordinates |
| Binary | ~40 MB | Shape deduplication, binary encoding |
| Reduction | **84%** | |

### Runtime Memory

| Mode | Peak Memory | Notes |
|------|-------------|-------|
| JSON (full load) | ~630 MB | All trips parsed as JS objects |
| Binary (streaming) | ~12 MB | Master index + 3 chunks |
| Reduction | **95%** | |

### Why Binary is Better

1. **Shape Deduplication**: 29,000 trips share ~1,878 unique shapes
2. **On-Demand Loading**: Only 3 hours loaded at once
3. **No JSON Parsing**: Direct TypedArray usage
4. **HTTP Range Requests**: Server sends only requested bytes
5. **LRU Eviction**: Memory stays bounded

## 8. Code References

| Component | Location | Purpose |
|-----------|----------|---------|
| GTFS Parser | `scripts/download/gtfs_trips.py` | Download and process GTFS |
| Binary Converter | `scripts/download/gtfs_to_binary.py` | JSON → Binary |
| Chunk Manager | `src/lib/gtfs/ChunkManager.ts` | Binary reader |
| React Hook | `src/hooks/useGTFSTrips.ts` | React integration |
| Type Definitions | `src/types/gtfs-binary.ts` | TypeScript types |
| Trips Layer | `src/layers/TramTripsLayer.ts` | deck.gl rendering |

## 9. Troubleshooting

### Binary Format Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Invalid magic number | Corrupted/wrong file | Regenerate with `gtfs_to_binary.py` |
| Version mismatch | Old binary format | Regenerate binary file |
| Chunk fetch failed | Server doesn't support Range | Check server headers |

### JSON Fallback

The hook automatically falls back to JSON if binary fails:

```typescript
const { isBinaryMode } = useGTFSTrips(currentTime);
// isBinaryMode === false means JSON fallback is active
```

### HTTP Range Support

Binary streaming requires HTTP Range request support. Check with:

```bash
curl -I -H "Range: bytes=0-31" /path/to/gtfs-trips.bin
# Should return: HTTP/1.1 206 Partial Content
```

### Memory Issues

If you see memory warnings:

1. Ensure binary format is being used (`isBinaryMode === true`)
2. Check that LRU eviction is working (logs show "Evicted chunk for hour X")
3. Reduce `MAX_CACHED_CHUNKS` in ChunkManager if needed
