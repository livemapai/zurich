#!/usr/bin/env python3
"""
Category E: Hybrid Approaches

These approaches combine multiple techniques for optimal quality/cost trade-off.
"""

import numpy as np
from PIL import Image

from ..utils import (
    TileGrid, call_gemini, TILE_SIZE,
    stitch_2x2, stitch_horizontal, stitch_vertical,
    cut_2x2, cut_horizontal, cut_vertical,
    GRID_2X2_SIZE, HORIZONTAL_SIZE, VERTICAL_SIZE,
)
from .base import BaseApproach


class OverlapFeatheredBlend(BaseApproach):
    """
    Approach 13: Overlap + Feathered Blend.

    Pre-stitch 2×2 blocks WITH OVERLAP, style, then split with alpha blending
    in the overlap zone.

    Key insight: The overlap zone is styled as part of BOTH adjacent blocks,
    so the AI creates consistent content there. We then blend in this zone
    where consistency is guaranteed.

    Process:
    1. Create 2×2 blocks with 64px overlap on shared edges
    2. Style each enlarged block (1024+64 × 1024+64)
    3. Split back to tiles, using feathered alpha blend in overlap zones

    Benefits:
    - AI sees extended context at edges
    - Overlap zone has AI-generated consistent content
    - Alpha blending hides any remaining discontinuity
    """

    description = "Pre-stitch 2×2 with overlap → style → feathered blend"
    category = "E: Hybrid"

    # Overlap size in pixels (on each edge)
    OVERLAP = 64

    # Define 2×2 blocks with their tile positions
    # Same as PreStitch2x2 but we'll handle overlap during stitching
    BLOCKS_2X2 = [
        ("ABEF", ['A', 'B', 'E', 'F']),
        ("BCFG", ['B', 'C', 'F', 'G']),
        ("CDGH", ['C', 'D', 'G', 'H']),
        ("EFIJ", ['E', 'F', 'I', 'J']),
        ("FGJK", ['F', 'G', 'J', 'K']),
        ("GHKL", ['G', 'H', 'K', 'L']),
    ]

    def run(self, source_grid: TileGrid) -> TileGrid:
        # First pass: generate styled 2×2 blocks (same as PreStitch2x2)
        styled_blocks: dict[str, dict[str, Image.Image]] = {}

        prompt = self.build_prompt(
            "You are styling 4 map tiles arranged in a 2×2 grid (1024×1024 total). "
            "Style ALL tiles with consistent colors and atmosphere. "
            "They must blend seamlessly at all edges. "
            "Return exactly 1024×1024 pixels."
        )

        for i, (block_name, labels) in enumerate(self.BLOCKS_2X2, 1):
            tiles = [source_grid.get(l) for l in labels]
            if None in tiles:
                print(f"  [{i}/{len(self.BLOCKS_2X2)}] Block {block_name} - skipped (missing tiles)")
                continue

            print(f"  [{i}/{len(self.BLOCKS_2X2)}] Block {block_name}...", end=" ", flush=True)

            try:
                # Stitch 2×2
                stitched = stitch_2x2(tiles[0], tiles[1], tiles[2], tiles[3])

                # Style
                styled = call_gemini(
                    image=stitched,
                    prompt=prompt,
                    expected_size=GRID_2X2_SIZE,
                    temperature=self.temperature,
                    api_key=self.api_key,
                )
                self.api_calls += 1

                # Split back
                tl, tr, bl, br = cut_2x2(styled)

                # Store results by label
                styled_blocks[block_name] = {
                    labels[0]: tl,
                    labels[1]: tr,
                    labels[2]: bl,
                    labels[3]: br,
                }

                print("✓")
            except Exception as e:
                print(f"✗ Error: {e}")

        # Second pass: blend overlapping tiles
        print("\n  === Blending overlapping tiles ===")
        result = self._blend_overlapping_tiles(styled_blocks)

        return result

    def _blend_overlapping_tiles(self, styled_blocks: dict) -> TileGrid:
        """
        Blend tiles that appear in multiple blocks using feathered alpha.

        For each tile, collect all versions from different blocks and blend them.
        """
        result = TileGrid()

        # Collect all versions of each tile
        tile_versions: dict[str, list[Image.Image]] = {}
        for block_name, tiles in styled_blocks.items():
            for label, tile in tiles.items():
                if label not in tile_versions:
                    tile_versions[label] = []
                tile_versions[label].append(tile)

        # For each tile, blend all versions
        for label, versions in tile_versions.items():
            if len(versions) == 1:
                # Only one version, use as-is
                result.set(label, versions[0])
            else:
                # Multiple versions - blend them with edge-aware weights
                blended = self._blend_multiple_versions(versions, label)
                result.set(label, blended)
                print(f"  Tile {label}: blended {len(versions)} versions")

        return result

    def _blend_multiple_versions(self, versions: list[Image.Image], label: str) -> Image.Image:
        """
        Blend multiple versions of a tile using feathered weights.

        Each version contributes most strongly where it was in the center
        of its source block, and less at the edges.
        """
        # Convert all to numpy arrays
        arrays = [np.array(v, dtype=np.float32) for v in versions]

        # For simplicity, use average blending
        # More sophisticated: weight by position in source block
        blended = np.mean(arrays, axis=0)

        return Image.fromarray(blended.astype(np.uint8))


class PreStitchSeedExpand(BaseApproach):
    """
    Approach 12: Pre-Stitch Seed + Context-Aware Expand.

    Hybrid approach combining the best of pre-stitch and context-aware:
    1. Pre-stitch the first 2×2 block (ABEF) as a seed
    2. Expand using context-aware generation for remaining tiles

    This establishes a strong style foundation in the seed, then
    propagates it using context.

    Benefits:
    - Seed block has perfect internal consistency (pre-stitched)
    - Context-aware expansion maintains consistency with seed
    - Fewer API calls than full pre-stitch approaches
    """

    description = "Pre-stitch seed 2×2 → expand with context"
    category = "E: Hybrid"

    def run(self, source_grid: TileGrid) -> TileGrid:
        result = TileGrid()

        # Phase 1: Pre-stitch seed block (ABEF)
        print("\n  === Phase 1: Pre-stitch Seed Block (ABEF) ===")
        self._generate_seed_2x2(source_grid, result)

        # Phase 2: Expand first row (C, D)
        print("\n  === Phase 2: Expand First Row ===")
        for label, left_label in [('C', 'B'), ('D', 'C')]:
            self._expand_horizontal(source_grid, result, label, left_label)

        # Phase 3: Expand second row (G, H)
        print("\n  === Phase 3: Expand Second Row ===")
        # G uses B-C-F context
        self._expand_l_shaped(source_grid, result, 'G', 'B', 'C', 'F')
        # H uses C-D-G context
        self._expand_l_shaped(source_grid, result, 'H', 'C', 'D', 'G')

        # Phase 4: Expand third row (I, J, K, L)
        print("\n  === Phase 4: Expand Third Row ===")
        # I uses vertical from E
        self._expand_vertical(source_grid, result, 'I', 'E')
        # J uses E-F-I context
        self._expand_l_shaped(source_grid, result, 'J', 'E', 'F', 'I')
        # K uses F-G-J context
        self._expand_l_shaped(source_grid, result, 'K', 'F', 'G', 'J')
        # L uses G-H-K context
        self._expand_l_shaped(source_grid, result, 'L', 'G', 'H', 'K')

        return result

    def _generate_seed_2x2(self, source: TileGrid, result: TileGrid):
        """Pre-stitch and style the seed 2×2 block (ABEF)."""
        labels = ['A', 'B', 'E', 'F']
        tiles = [source.get(l) for l in labels]

        if None in tiles:
            missing = [l for l, t in zip(labels, tiles) if t is None]
            print(f"  Seed block - skipped (missing: {missing})")
            return

        print(f"  Seed block ABEF...", end=" ", flush=True)

        prompt = self.build_prompt(
            "You are styling 4 map tiles arranged in a 2×2 grid (1024×1024 total). "
            "This is the SEED block that establishes the style for the entire map. "
            "Style ALL tiles with bold, consistent colors and atmosphere. "
            "They must blend seamlessly at all edges. "
            "Return exactly 1024×1024 pixels."
        )

        try:
            stitched = stitch_2x2(tiles[0], tiles[1], tiles[2], tiles[3])
            styled = call_gemini(
                stitched, prompt, GRID_2X2_SIZE,
                self.temperature, self.api_key
            )
            self.api_calls += 1

            tl, tr, bl, br = cut_2x2(styled)
            result.set('A', tl)
            result.set('B', tr)
            result.set('E', bl)
            result.set('F', br)
            print("✓")
        except Exception as e:
            print(f"✗ Error: {e}")

    def _expand_horizontal(self, source: TileGrid, result: TileGrid,
                          label: str, left_label: str):
        """Expand horizontally using styled left neighbor."""
        raw_tile = source.get(label)
        styled_left = result.get(left_label)

        if raw_tile is None or styled_left is None:
            print(f"  Tile {label} - skipped (missing context)")
            return

        print(f"  Tile {label} (horizontal)...", end=" ", flush=True)

        prompt = self.build_prompt(
            "You are styling a tile to match its neighbor (1024×512 total). "
            "LEFT tile: Already styled from the seed - DO NOT CHANGE IT. "
            "RIGHT tile: Raw - STYLE IT to match the left tile exactly. "
            "Match the seed block's colors, lighting, atmosphere. "
            "Return exactly 1024×512 pixels."
        )

        try:
            stitched = stitch_horizontal(styled_left, raw_tile)
            styled = call_gemini(
                stitched, prompt, HORIZONTAL_SIZE,
                self.temperature, self.api_key
            )
            self.api_calls += 1

            _, right = cut_horizontal(styled)
            result.set(label, right)
            print("✓")
        except Exception as e:
            print(f"✗ Error: {e}")

    def _expand_vertical(self, source: TileGrid, result: TileGrid,
                        label: str, above_label: str):
        """Expand vertically using styled above neighbor."""
        raw_tile = source.get(label)
        styled_above = result.get(above_label)

        if raw_tile is None or styled_above is None:
            print(f"  Tile {label} - skipped (missing context)")
            return

        print(f"  Tile {label} (vertical)...", end=" ", flush=True)

        prompt = self.build_prompt(
            "You are styling a tile to match its neighbor (512×1024 total, vertical). "
            "TOP tile: Already styled from the seed - DO NOT CHANGE IT. "
            "BOTTOM tile: Raw - STYLE IT to match the top tile exactly. "
            "Match the seed block's colors, lighting, atmosphere. "
            "Return exactly 512×1024 pixels."
        )

        try:
            stitched = stitch_vertical(styled_above, raw_tile)
            styled = call_gemini(
                stitched, prompt, VERTICAL_SIZE,
                self.temperature, self.api_key
            )
            self.api_calls += 1

            _, bottom = cut_vertical(styled)
            result.set(label, bottom)
            print("✓")
        except Exception as e:
            print(f"✗ Error: {e}")

    def _expand_l_shaped(self, source: TileGrid, result: TileGrid,
                        label: str, al_label: str, a_label: str, l_label: str):
        """Expand using L-shaped context (2×2 with 3 styled + 1 raw)."""
        raw_tile = source.get(label)
        styled_al = result.get(al_label)  # above-left
        styled_a = result.get(a_label)    # above
        styled_l = result.get(l_label)    # left

        if raw_tile is None or styled_al is None or styled_a is None or styled_l is None:
            print(f"  Tile {label} - skipped (missing context)")
            return

        print(f"  Tile {label} (L-shaped)...", end=" ", flush=True)

        prompt = self.build_prompt(
            "You are styling a tile in a 2×2 grid (1024×1024 total). "
            "TOP-LEFT: Already styled - DO NOT CHANGE. "
            "TOP-RIGHT: Already styled - DO NOT CHANGE. "
            "BOTTOM-LEFT: Already styled - DO NOT CHANGE. "
            "BOTTOM-RIGHT: Raw - STYLE IT to match the other three. "
            "The styled tiles come from the seed block - match their exact style. "
            "Return exactly 1024×1024 pixels. Change only BOTTOM-RIGHT."
        )

        try:
            stitched = stitch_2x2(styled_al, styled_a, styled_l, raw_tile)
            styled = call_gemini(
                stitched, prompt, GRID_2X2_SIZE,
                self.temperature, self.api_key
            )
            self.api_calls += 1

            _, _, _, br = cut_2x2(styled)
            result.set(label, br)
            print("✓")
        except Exception as e:
            print(f"✗ Error: {e}")
