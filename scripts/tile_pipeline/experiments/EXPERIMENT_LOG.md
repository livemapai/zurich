# Tile Stitching Experiment Log

This file documents experiment runs and their results.

---

## Template for New Experiments

Copy this template for each experiment run:

```markdown
## Experiment: [Name]

**Date:** YYYY-MM-DD HH:MM

### Configuration
- **Source:** [source tile directory]
- **Style Prompt:** [prompt used]
- **Temperature:** [0.0-1.0]
- **API Model:** Gemini 2.5 Flash Image

### Approaches Tested
[List which approaches were run]

### Results Summary

| Approach | Time | API Calls | Seam Score | Visual Rating | Notes |
|----------|------|-----------|------------|---------------|-------|
| 1. Individual | Xs | X | X.XX | ⭐⭐ | ... |
| 2. ... | ... | ... | ... | ... | ... |

### Visual Rating Guide
- ⭐ - Poor: Very visible seams, color drift
- ⭐⭐ - Below Average: Noticeable seams
- ⭐⭐⭐ - Average: Some seams visible on close inspection
- ⭐⭐⭐⭐ - Good: Seams barely visible
- ⭐⭐⭐⭐⭐ - Excellent: Seamless, professional quality

### Detailed Observations

#### Approach X: [Name]
- **Time:** X seconds
- **API Calls:** X
- **Seam Score:** X.XX
- **Visual Rating:** ⭐⭐⭐
- **Observations:**
  - [What worked well]
  - [What didn't work]
  - [Specific seam issues noted]
- **Screenshot:** [link to stitched_result.png]

### Recommendations
- **Best Overall:** Approach X (reason)
- **Best Value:** Approach Y (reason)
- **Best for Production:** Approach Z (reason)

### Files Generated
- `comparison/side_by_side.png`
- `comparison/rankings.md`
- `comparison/results.json`
- `approach_XX_*/stitched_result.png` (for each approach)
```

---

## Experiment History

<!-- Add new experiments below, most recent first -->

### Experiment: Extended Pre-Stitch Testing (3×3, Full Grid, Overlap Blend)

**Date:** 2026-02-05 20:15

### Configuration
- **Source:** `scripts/tile_pipeline/assets/stitching_tests/raw`
- **Style Prompt:** "architectural pencil sketch"
- **Temperature:** 0.3
- **API Model:** Gemini 2.5 Flash Image

### Approaches Tested
- 4: Pre-Stitch 3×3
- 6: Pre-Stitch Full Grid
- 13: Overlap + Feathered Blend (NEW)

### Results Summary

| Approach | Time | API Calls | Seam Score | Visual Rating | Notes |
|----------|------|-----------|------------|---------------|-------|
| 6. Full Grid | 9.4s | 1 | **8.25** | ⭐⭐⭐⭐⭐ | Perfect! No visible seams |
| 4. 3×3 | 17.9s | 2 | 14.09 | ⭐⭐⭐⭐ | Visible seam between blocks |
| 13. Overlap Blend | 47.3s | 6 | 25.75 | ⭐⭐ | Ghosting, inconsistent |

### Detailed Observations

#### Approach 6: Pre-Stitch Full Grid 🏆
- **Time:** 9.4 seconds
- **API Calls:** 1
- **Seam Score:** 8.25 (BEST EVER!)
- **Visual Rating:** ⭐⭐⭐⭐⭐
- **Observations:**
  - Essentially perfect - no visible seams at all
  - AI treated all 12 tiles as ONE unified image
  - Consistent color palette, lighting, and pencil style throughout
  - Fastest approach (only 1 API call!)
  - Cheapest approach (only 1 API call!)
- **Screenshot:** `approach_06_pre_stitch_full_grid/stitched_result.png`

#### Approach 4: Pre-Stitch 3×3
- **Time:** 17.9 seconds
- **API Calls:** 2
- **Seam Score:** 14.09
- **Visual Rating:** ⭐⭐⭐⭐
- **Observations:**
  - Visible vertical seam between the two 3×3 blocks (between columns B-C)
  - Left block has warmer/brownish tint, right block is greener
  - Each 3×3 block internally consistent
  - Worst seam: A-B (34.71 diff)
- **Screenshot:** `approach_04_pre_stitch_3x3/stitched_result.png`

#### Approach 13: Overlap + Feathered Blend (NEW)
- **Time:** 47.3 seconds
- **API Calls:** 6
- **Seam Score:** 25.75
- **Visual Rating:** ⭐⭐
- **Observations:**
  - Blending multiple styled versions created ghosting artifacts
  - Averaging pixels doesn't average STYLE - fundamental flaw
  - Each tile still has different color interpretation
  - Worst seam: B-C (52.70 diff)
  - **Conclusion:** This approach doesn't work well - abandoned
- **Screenshot:** `approach_13_overlap_feathered_blend/stitched_result.png`

### Key Insight

**More context = better consistency.** The theoretical prediction was correct:

| More Context → | Seam Score |
|----------------|------------|
| Full Grid (12 tiles) | 8.25 |
| 3×3 (9 tiles) | 14.09 |
| 2×2 (4 tiles) | 23.52 |
| Individual (1 tile) | 30.58 |

The relationship is nearly linear! Each doubling of context roughly halves the seam score.

### Recommendations

- **Best Overall:** Approach 6 - Pre-Stitch Full Grid
  - Best quality (8.25 seam score)
  - Fastest (9.4s)
  - Cheapest (1 API call)
  - **USE THIS FOR PRODUCTION**

- **If image size limits are hit:** Fall back to Approach 4 (3×3)

- **Abandon:** Overlap + Feathered Blend (13) - doesn't work as expected

### Files Generated
- `approach_04_pre_stitch_3x3/stitched_result.png`
- `approach_06_pre_stitch_full_grid/stitched_result.png`
- `approach_13_overlap_feathered_blend/stitched_result.png`
- `comparison/rankings.md`
- `comparison/results.json`

---

### Experiment: Initial Baseline Comparison (Individual vs 2×2 vs L-Shape)

**Date:** 2026-02-05 13:46

### Configuration
- **Source:** `scripts/tile_pipeline/assets/stitching_tests/raw`
- **Style Prompt:** "architectural pencil sketch"
- **Temperature:** 0.3
- **API Model:** Gemini 2.5 Flash Image

### Approaches Tested
- 1: Individual Tiles (baseline)
- 3: Pre-Stitch 2×2
- 7: L-Shape Context

### Results Summary

| Approach | Time | API Calls | Seam Score | Visual Rating | Notes |
|----------|------|-----------|------------|---------------|-------|
| 3. Pre-Stitch 2×2 | 57.7s | 6 | 23.52 | ⭐⭐⭐ | Best of initial test |
| 7. L-Shape Context | 101.2s | 11 | 25.54 | ⭐⭐⭐ | Slower, similar quality |
| 1. Individual | 108.0s | 12 | 30.58 | ⭐⭐ | Worst - visible seams |

### Key Finding
Pre-stitch approaches outperform context-aware approaches. This led to testing larger pre-stitch sizes (3×3, full grid).

---

### Experiment: Initial Framework Setup

**Date:** 2026-02-05

**Status:** Framework created, ready for experiments

**Configuration:**
- Source: `scripts/tile_pipeline/assets/stitching_tests/raw`
- Style Prompt: (to be determined)
- Temperature: 0.3
- API Model: Gemini 2.5 Flash Image

**Approaches Available:**
1. Individual Tiles (baseline)
2. Individual + Low Temperature
3. Pre-Stitch 2×2
4. Pre-Stitch 3×3
5. Pre-Stitch Full Row
6. Pre-Stitch Full Grid
7. L-Shape Context
8. Two-Pass Reference
9. Sliding Window 2×2
10. Individual + Edge Blend
11. Individual + Stitcher Pass
12. Pre-Stitch Seed + Expand

**Next Steps:**
- [ ] Run baseline experiment with approaches 1, 3, 7, 12
- [ ] Analyze results and determine top performers
- [ ] Run full experiment with all approaches
- [ ] Document final recommendations

---

## Expected Outcomes

Based on theoretical analysis, expected rankings:

### Quality (Best to Worst)
1. Pre-Stitch Full Grid (6) - Maximum context
2. Pre-Stitch 3×3 (4) - Large context
3. Sliding Window 2×2 (9) - Thorough but expensive
4. Pre-Stitch Seed + Expand (12) - Hybrid approach
5. Two-Pass Reference (8) - Full context in Pass 2
6. L-Shape Context (7) - Progressive expansion
7. Pre-Stitch 2×2 (3) - Good local consistency
8. Pre-Stitch Full Row (5) - Row consistency only
9. Individual + Stitcher Pass (11) - Post-fix approach
10. Individual + Edge Blend (10) - Simple post-process
11. Individual Low Temp (2) - Slightly better than baseline
12. Individual (1) - Baseline, worst expected

### Cost Efficiency (Fewest API Calls)
1. Pre-Stitch Full Grid (6) - 1 call
2. Pre-Stitch Full Row (5) - 3 calls
3. Pre-Stitch 3×3 (4) - 2 calls
4. Pre-Stitch 2×2 (3) - 6 calls
5. L-Shape Context (7) - 12 calls
6. Pre-Stitch Seed + Expand (12) - ~10 calls
7. Two-Pass Reference (8) - ~24 calls
8. Individual (1, 2) - 12 calls each
9. Individual + Edge Blend (10) - 12 calls
10. Individual + Stitcher Pass (11) - 12 + 17 = 29 calls
11. Sliding Window 2×2 (9) - ~9 calls but overlapping

### Recommended Testing Order
1. **Quick baseline:** 1, 3, 7 (compare individual vs pre-stitch vs context-aware)
2. **If pre-stitch wins:** Add 4, 5, 6
3. **If context-aware wins:** Add 8, 9, 12
4. **Full comparison:** All 12 approaches

---

## Notes

- Seam score is measured as mean pixel difference at tile edges
- Lower seam score = better quality
- Visual rating is subjective but important
- API costs vary significantly between approaches
- Consider both quality and cost for production use
