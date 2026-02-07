# LOD2 Roof Investigation Log

**Date**: 2026-02-05
**Issue**: Roofs looked wrong - too few and not overlapping with existing buildings

---

## Summary of Findings

### Root Causes Identified

1. **Test Run Limitation**: Initial test only extracted 200 buildings (`max_buildings=200`)
2. **Overly Restrictive Filter**: Original filter required building keywords; most files were filtered out
3. **Limited LOD2 Dataset**: Stadt Zürich LOD2 data only covers ~3% of buildings

### What Was Fixed

1. Changed filter from "include keywords" to "exclude non-buildings"
2. Removed `max_buildings` limit
3. Expanded extraction to cover full LOD2 dataset

### Final Numbers

| Metric | Before | After |
|--------|--------|-------|
| Buildings extracted | 200 | 2,163 |
| Roof faces | 809 | 13,461 |
| Coverage | 11.9% of area | 3% of buildings |

---

## Detailed Investigation

### 1. ZIP File Analysis

The Stadt Zürich LOD2 ZIP contains 18,107 OBJ files:

| Category | Count | Percentage |
|----------|-------|------------|
| Fences (Zaun) | 15,339 | 85% |
| Buildings (Gebaeude) | 1,997 | 11% |
| Walls (Mauer) | 532 | 3% |
| Other (bridges, etc.) | 239 | 1% |

**Insight**: The majority of files are fences, not buildings!

### 2. Filter Logic

**Original Filter** (too restrictive):
```python
building_keywords = ['Gebaeude', 'Wohnhaus', 'Kirche', ...]
# Only included files matching these keywords
```

**Fixed Filter** (exclusion-based):
```python
exclude_keywords = ['zaun', 'mauer', 'fence', 'wall', 'befestigung', 'bruecke', 'steg', 'bohlenweg']
# Include everything EXCEPT non-buildings
```

This captures all building types including:
- Sakralbau (churches, chapels)
- Gastgewerbe (hospitality)
- Nebengebaeude (auxiliary buildings)
- Various historic structures

### 3. Coordinate System

Stadt Zürich LOD2 uses a **rotated coordinate system**:

```
OBJ File Format:
v X Y Z
Where:
  X = LV95 Easting (correct)
  Y = Elevation in meters
  Z = -LV95 Northing (INVERTED!)
```

**Conversion applied**:
```python
e = x        # Easting = X
n = -z       # Northing = -Z (invert!)
elev = y     # Elevation = Y
```

### 4. Coverage Analysis

| Dataset | Bounds (WGS84) | Building Count |
|---------|----------------|----------------|
| WFS Buildings | lng 8.46-8.62, lat 47.32-47.43 | 65,677 |
| LOD2 Roofs | lng 8.47-8.60, lat 47.32-47.43 | 2,163 |

**Coverage**: LOD2 has 3D models for only ~3% of WFS buildings.

This is a **fundamental limitation** of the Stadt Zürich LOD2 dataset - it simply doesn't include most buildings.

### 5. Coordinate Alignment Verification

Sample comparison:
- Roof coordinate: [8.543117, 47.371579]
- Nearest WFS building: [8.543160, 47.371630]
- Distance: ~6.6 meters

**Conclusion**: Coordinates ARE aligned correctly. The issue is coverage, not alignment.

---

## File Changes Made

### Modified Files

1. **`scripts/download/lod2_buildings.py`**
   - Changed filter from keyword-matching to exclusion-based
   - Now extracts all building types, not just "Gebaeude"

2. **`src/components/ZurichViewer/ZurichViewer.tsx`**
   - Added `roofs` state variable
   - Added roofs layer to render pipeline
   - Added to LayerPanel for toggle control

3. **`src/layers/RoofsLayer.ts`**
   - Removed fixed `elevationOffset` hack
   - Now uses `terrain_elevation` from pre-processed data
   - Coordinates are terrain-relative for proper deck.gl positioning

4. **`src/types/roof.ts`**
   - Added `terrain_elevation` and `lod2_terrain_offset` properties

### New Files

1. **`scripts/terrain/add_roof_elevations.py`**
   - Pre-calculates Mapterhorn terrain elevation for each roof
   - Converts LOD2 absolute Z to height-above-terrain
   - Stores terrain_elevation for runtime positioning

### Generated Files

| File | Size | Contents |
|------|------|----------|
| `public/data/zurich-roofs.geojson` | 5.8 MB | 13,461 roof faces with terrain data |
| `data/raw/lod2-buildings/` | ~50 MB | 2,163 OBJ files |
| `data/raw/lod2-buildings.zip` | 361 MB | Cached source ZIP |

---

## Data Quality

### Roof Statistics

| Roof Type | Count | Percentage |
|-----------|-------|------------|
| Gabled | 1,538 | 71% |
| Complex | 397 | 18% |
| Hipped | 189 | 9% |
| Flat | 38 | 2% |
| Mansard | 1 | <1% |

### Elevation Range

- Minimum: 391.3m (valley)
- Maximum: 667.7m (hill)
- Mean: 449.5m
- Zurich base: ~408m

**Verdict**: Elevations are correct!

---

## Elevation Mismatch Issue (FIXED - Proper Solution)

### The Problem

After initial deployment, roofs appeared visually misaligned - floating "in front of" or "below" the WFS buildings instead of on top of them.

**Analysis revealed**:
- WFS buildings: `terrain_elevation + height = building_top` (e.g., 412m + 22m = 434m)
- LOD2 roofs: absolute elevation from 3D model (e.g., 423m)
- **Average difference: LOD2 roofs are ~10.7m BELOW WFS building tops**

| Building | WFS Base | WFS Height | WFS Top | LOD2 Roof | Difference |
|----------|----------|------------|---------|-----------|------------|
| Sample 1 | 412.5m   | 21.6m      | 434.1m  | 423.3m    | 10.8m      |
| Sample 2 | 410.4m   | 16.5m      | 426.9m  | 419.3m    | 7.6m       |
| Sample 3 | 411.0m   | 25.4m      | 436.4m  | 419.0m    | 17.4m      |

### Root Cause

The WFS building heights appear to be measured from ground to ridge, while LOD2 stores actual geometric elevations. The two datasets use compatible horizontal coordinates but incompatible vertical measurements. Additionally, LOD2 uses a different terrain model than Mapterhorn (used by deck.gl).

### Initial Fix (Temporary Hack)

Initially added a fixed `elevationOffset` parameter (default: 10m) - but this was a rough approximation that didn't account for terrain variations.

### Proper Fix (Terrain Pre-calculation)

Created `scripts/terrain/add_roof_elevations.py` to pre-calculate terrain-relative coordinates:

1. **Fetch Mapterhorn terrain elevation** at each roof face centroid
2. **Convert LOD2 absolute Z** to height-above-terrain: `height = lod2_z - lod2_base`
3. **Store terrain_elevation** property for runtime positioning
4. **Update coordinates** to `[lng, lat, height_above_terrain]`

At runtime, `RoofsLayer.ts` adds terrain elevation back:
```typescript
const terrainElevation = feature.properties.terrain_elevation ?? feature.properties.base_elevation;
return [coord[0], coord[1], terrainElevation + heightAboveTerrain] as Position3D;
```

### Statistics After Processing

```
Terrain elevation range: 395.5m - 654.5m
Mean terrain elevation: 440.8m

Roof height range: 0.2m - 66.5m
Mean roof height: 13.8m

LOD2-Mapterhorn offset range: -15.7m - 6.3m
Mean offset: -3.5m
```

The LOD2-Mapterhorn offset shows the terrain models differ by up to 15m in some locations, confirming why a fixed offset was inadequate.

---

## Known Limitations

1. **Low Coverage**: LOD2 data only covers ~3% of buildings
2. **Elevation Offset**: Requires manual calibration (default 10m may not be perfect for all buildings)
3. **Sparse Distribution**: Roofs appear sporadically, not uniformly

---

## Recommendations

### Option A: Accept Limited Coverage
Use LOD2 roofs as-is for the ~3% of buildings that have them. The remaining buildings will show with flat roofs.

### Option B: Investigate Alternative Data Sources
- Check if swissBUILDINGS3D has better coverage
- Look for Stadt Zürich 2.0 updates

### Option C: Hybrid Approach
- Use LOD2 for detailed buildings where available
- Generate procedural roofs for buildings without LOD2 data

---

## How to Verify in Viewer

1. Start the viewer (externally)
2. Press `L` to open Layer Panel
3. Find "3D Roofs (LOD2)" under Infrastructure
4. Toggle to see the 13,461 roof faces
5. Fly to city center (lng ~8.54, lat ~47.37) to see most roofs

---

## Technical Details

### Extraction Pipeline

```
LOD2 ZIP (361 MB)
    ↓ filter out fences/walls
2,163 OBJ files
    ↓ parse vertices & faces
    ↓ compute normals
    ↓ classify roof vs wall (normal.z > 0.3)
    ↓ convert LV95 → WGS84
13,461 roof face polygons
    ↓ assign materials by slope
zurich-roofs.geojson (5.8 MB)
```

### Key Code References

- Download/Extract: `scripts/download/lod2_buildings.py:191-218`
- Roof Classification: `scripts/process/extract_roof_faces.py:264-338`
- Coordinate Transform: `scripts/convert/transform_coords.py`
- Terrain Pre-calculation: `scripts/terrain/add_roof_elevations.py`
- Layer Rendering: `src/layers/RoofsLayer.ts`
- Type Definitions: `src/types/roof.ts`

---

## Appendix: Sample GeoJSON Feature

```json
{
  "type": "Feature",
  "properties": {
    "building_id": "Wohngebaeude_140289_1_3D",
    "face_index": 0,
    "roof_type": "gabled",
    "slope_angle": 35.2,
    "orientation": "SE",
    "area_m2": 45.3,
    "material": "roof_terracotta",
    "height": 15.2,
    "base_elevation": 412.0
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[8.543117, 47.371579, 427.2], ...]]
  }
}
```
