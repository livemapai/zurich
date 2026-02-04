# Tile Pipeline Data Validation Results

**Date**: 2026-02-03
**Status**: ✅ ALL TESTS PASSED

---

## 1. External Services

### SWISSIMAGE Satellite (swisstopo)
- **URL**: `wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissimage/default/current/3857/{z}/{x}/{y}.jpeg`
- **Status**: ✅ Working (HTTP 200)
- **Tile Size**: 256×256 pixels
- **Format**: JPEG
- **Resolution**: 10cm/pixel at full zoom
- **License**: Free (OGD since March 2021)

### Mapterhorn Elevation Tiles
- **URL**: `tiles.mapterhorn.com/{z}/{x}/{y}.webp`
- **Status**: ✅ Working (HTTP 200)
- **Tile Size**: 512×512 pixels
- **Encoding**: Terrarium RGB (`elevation = R×256 + G + B/256 - 32768`)
- **Elevation Range (Zurich)**: 399m to 676m ✓

---

## 2. Local Vector Data

### Buildings (`zurich-buildings.geojson`)
| Property | Status | Value |
|----------|--------|-------|
| Total features | ✅ | 65,677 |
| Geometry type | ✅ | Polygon |
| `height` | ✅ | 0.1m - 193.9m (mean: 14.5m) |
| `elevation` | ✅ | 393.6m - 854.3m |
| File size | ✅ | 44.5 MB |

### Trees (`zurich-trees.geojson`)
| Property | Status | Value |
|----------|--------|-------|
| Total features | ✅ | 80,484 |
| Geometry type | ✅ | Point |
| `height` | ⚠️ | **Default 10m** (not real data) |
| `crown_diameter` | ✅ | 1.0m - 44.0m (mean: 7.1m) |
| `species` | ✅ | Available |
| File size | ✅ | 21.8 MB |

#### Tree Height Estimation
Since actual heights are not provided, we can estimate from crown diameter:

```python
# Allometric relationship for urban trees
estimated_height = min(crown_diameter * 1.5, 35)  # Cap at 35m
```

| Size Class | Crown Diameter | Estimated Height | Count |
|------------|----------------|------------------|-------|
| Small | < 5m | 1.5 - 7.5m | 24,682 (30.7%) |
| Medium | 5 - 15m | 7.5 - 22.5m | 50,882 (63.2%) |
| Large | > 15m | 22.5 - 35m | 4,920 (6.1%) |

---

## 3. Algorithm Validation

### LAB Color Space Conversion
- **Roundtrip accuracy**: max diff = 1 (out of 255), mean diff = 0.46
- **Status**: ✅ Suitable for compositing

### Shadow Geometry
- **Formula verified**: `shadow_length = height / tan(sun_altitude)`
- **45° sun altitude**: shadow length equals building height ✓
- **Direction calculation**: Correct (opposite of sun azimuth)

### Hillshade (Horn Algorithm)
- **Implementation**: ✅ Working
- **Illumination direction**: Correct (NW sun lights NW-facing slopes)

---

## 4. Dependencies

### Already Available
| Package | Version Required | Status |
|---------|------------------|--------|
| numpy | ≥1.26.0 | ✅ |
| scipy | ≥1.11.0 | ✅ |
| pillow | ≥10.0.0 | ✅ |
| shapely | ≥2.0.0 | ✅ |
| requests | ≥2.31.0 | ✅ |
| rasterio | ≥1.3.0 | ✅ |
| tqdm | ≥4.66.0 | ✅ |

### Need to Add
| Package | Purpose | Required |
|---------|---------|----------|
| pysolar | Sun position calculation | Recommended |
| rtree | Spatial indexing (fast queries) | Recommended |

**Note**: Both `pysolar` and `rtree` can be worked around:
- Sun position: Use astronomical formulas (implemented in validation script)
- Spatial index: Use bounding box filtering + Shapely (slower but works)

---

## 5. Tile Count Estimates

| Zoom | Tiles (Zurich) | Pixels | Est. Storage |
|------|----------------|--------|--------------|
| 14 | ~20 | 5M | ~2 MB |
| 15 | ~80 | 20M | ~8 MB |
| 16 | ~320 | 84M | ~32 MB |
| 17 | ~1,280 | 335M | ~128 MB |
| 18 | ~5,120 | 1.3B | ~512 MB |
| **Total** | **~6,820** | **1.7B** | **~680 MB** |

---

## 6. Known Limitations

1. **Tree heights are estimates** - Stadt Zürich doesn't provide actual measurements
2. **SWISSIMAGE zoom limit** - Returns HTTP 400 outside Switzerland bounds
3. **Processing time** - Full Zurich at zoom 18 will take ~25 minutes (4 workers)

---

## 7. Conclusion

**The pipeline is READY for implementation.** All critical data sources are:
- ✅ Accessible and working
- ✅ In correct formats
- ✅ Have required properties (or reasonable alternatives)
- ✅ License-compatible (free OGD)

The only caveat is tree height estimation, which is acceptable for shadow rendering purposes.
