#!/usr/bin/env python3
"""
Category B: Pre-Stitch Then Style Approaches

These approaches stitch multiple raw tiles together, style the combined
image, then split back into individual tiles.

Key insight: By styling tiles together, the AI sees them as one continuous
image and applies consistent colors/style across the seams.
"""

from ..utils import (
    TileGrid, call_gemini, TILE_SIZE,
    stitch_2x2, stitch_3x3, stitch_row, stitch_full_grid,
    cut_2x2, cut_3x3, cut_row, cut_full_grid,
    GRID_2X2_SIZE, GRID_3X3_SIZE, ROW_4_SIZE, GRID_4X3_SIZE,
)
from .base import BaseApproach


class PreStitch2x2(BaseApproach):
    """
    Approach 3: Pre-stitch 2×2 blocks, style, then split.

    Process in overlapping 2×2 blocks to ensure good coverage:
    - Block 1: ABEF (top-left corner)
    - Block 2: BCFG (offset right)
    - Block 3: CDGH (top-right corner)
    - Block 4: EFIJ (middle-left)
    - Block 5: FGJK (center)
    - Block 6: GHKL (middle-right)

    Each tile appears in multiple blocks; final result uses most recent styling.
    """

    description = "Pre-stitch 2×2 blocks → style → split"
    category = "B: Pre-Stitch"

    # Define 2×2 blocks with their tile positions
    BLOCKS_2X2 = [
        # (block_name, [top_left, top_right, bottom_left, bottom_right])
        ("ABEF", ['A', 'B', 'E', 'F']),
        ("BCFG", ['B', 'C', 'F', 'G']),
        ("CDGH", ['C', 'D', 'G', 'H']),
        ("EFIJ", ['E', 'F', 'I', 'J']),
        ("FGJK", ['F', 'G', 'J', 'K']),
        ("GHKL", ['G', 'H', 'K', 'L']),
    ]

    def run(self, source_grid: TileGrid) -> TileGrid:
        result = TileGrid()

        prompt = self.build_prompt(
            "You are styling 4 map tiles arranged in a 2×2 grid (1024×1024 total). "
            "Style ALL tiles with consistent colors and atmosphere. "
            "They must blend seamlessly at all edges. "
            "Return exactly 1024×1024 pixels."
        )

        for i, (block_name, labels) in enumerate(self.BLOCKS_2X2, 1):
            # Check if all tiles in block exist
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

                # Store results (later blocks overwrite earlier)
                result.set(labels[0], tl)
                result.set(labels[1], tr)
                result.set(labels[2], bl)
                result.set(labels[3], br)

                print("✓")
            except Exception as e:
                print(f"✗ Error: {e}")

        return result


class PreStitch3x3(BaseApproach):
    """
    Approach 4: Pre-stitch 3×3 blocks, style, then split.

    Process in overlapping 3×3 blocks:
    - Block 1: ABC/EFG/IJK (left side)
    - Block 2: BCD/FGH/JKL (right side)

    Larger context = better consistency, but more expensive API calls.
    """

    description = "Pre-stitch 3×3 blocks → style → split"
    category = "B: Pre-Stitch"

    # Define 3×3 blocks
    BLOCKS_3X3 = [
        # (block_name, [9 tiles in row-major order])
        ("ABC_EFG_IJK", ['A', 'B', 'C', 'E', 'F', 'G', 'I', 'J', 'K']),
        ("BCD_FGH_JKL", ['B', 'C', 'D', 'F', 'G', 'H', 'J', 'K', 'L']),
    ]

    def run(self, source_grid: TileGrid) -> TileGrid:
        result = TileGrid()

        prompt = self.build_prompt(
            "You are styling 9 map tiles arranged in a 3×3 grid (1536×1536 total). "
            "Style ALL tiles with consistent colors, lighting, and atmosphere. "
            "They must blend seamlessly at all edges. "
            "Return exactly 1536×1536 pixels."
        )

        for i, (block_name, labels) in enumerate(self.BLOCKS_3X3, 1):
            tiles = [source_grid.get(l) for l in labels]
            if None in tiles:
                print(f"  [{i}/{len(self.BLOCKS_3X3)}] Block {block_name} - skipped (missing tiles)")
                continue

            print(f"  [{i}/{len(self.BLOCKS_3X3)}] Block {block_name}...", end=" ", flush=True)

            try:
                # Stitch 3×3
                stitched = stitch_3x3(tiles)

                # Style
                styled = call_gemini(
                    image=stitched,
                    prompt=prompt,
                    expected_size=GRID_3X3_SIZE,
                    temperature=self.temperature,
                    api_key=self.api_key,
                )
                self.api_calls += 1

                # Split back
                split_tiles = cut_3x3(styled)

                # Store results
                for label, tile in zip(labels, split_tiles):
                    result.set(label, tile)

                print("✓")
            except Exception as e:
                print(f"✗ Error: {e}")

        return result


class PreStitchFullRow(BaseApproach):
    """
    Approach 5: Pre-stitch full rows (4 tiles), style, then split.

    Process each row independently:
    - Row 1: ABCD
    - Row 2: EFGH
    - Row 3: IJKL

    Good for horizontal continuity within rows, but may have
    seams between rows.
    """

    description = "Pre-stitch full rows (4 tiles) → style → split"
    category = "B: Pre-Stitch"

    ROWS = [
        ("ABCD", ['A', 'B', 'C', 'D']),
        ("EFGH", ['E', 'F', 'G', 'H']),
        ("IJKL", ['I', 'J', 'K', 'L']),
    ]

    def run(self, source_grid: TileGrid) -> TileGrid:
        result = TileGrid()

        prompt = self.build_prompt(
            "You are styling 4 map tiles arranged in a horizontal row (2048×512 total). "
            "Style ALL tiles with consistent colors and atmosphere. "
            "They must blend seamlessly at all horizontal edges. "
            "Return exactly 2048×512 pixels."
        )

        for i, (row_name, labels) in enumerate(self.ROWS, 1):
            tiles = [source_grid.get(l) for l in labels]
            if None in tiles:
                print(f"  [{i}/{len(self.ROWS)}] Row {row_name} - skipped (missing tiles)")
                continue

            print(f"  [{i}/{len(self.ROWS)}] Row {row_name}...", end=" ", flush=True)

            try:
                # Stitch row
                stitched = stitch_row(tiles)

                # Style
                styled = call_gemini(
                    image=stitched,
                    prompt=prompt,
                    expected_size=ROW_4_SIZE,
                    temperature=self.temperature,
                    api_key=self.api_key,
                )
                self.api_calls += 1

                # Split back
                split_tiles = cut_row(styled, 4)

                # Store results
                for label, tile in zip(labels, split_tiles):
                    result.set(label, tile)

                print("✓")
            except Exception as e:
                print(f"✗ Error: {e}")

        return result


class PreStitchFullGrid(BaseApproach):
    """
    Approach 6: Pre-stitch entire grid (4×3 = 12 tiles), style, then split.

    Style all 12 tiles as a single 2048×1536 image.

    Pros: Best possible seam consistency
    Cons: Very large image may exceed API limits or reduce quality
    """

    description = "Pre-stitch entire 4×3 grid → style → split"
    category = "B: Pre-Stitch"

    def run(self, source_grid: TileGrid) -> TileGrid:
        # Check we have all tiles
        labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']
        missing = [l for l in labels if source_grid.get(l) is None]
        if missing:
            print(f"  Missing tiles: {missing}")
            return TileGrid()

        prompt = self.build_prompt(
            "You are styling 12 map tiles arranged in a 4×3 grid (2048×1536 total). "
            "Style ALL tiles with consistent colors, lighting, and atmosphere. "
            "They must blend seamlessly at all edges. "
            "Return exactly 2048×1536 pixels."
        )

        print(f"  Full grid (12 tiles)...", end=" ", flush=True)

        try:
            # Stitch full grid
            stitched = stitch_full_grid(source_grid)

            # Style
            styled = call_gemini(
                image=stitched,
                prompt=prompt,
                expected_size=GRID_4X3_SIZE,
                temperature=self.temperature,
                api_key=self.api_key,
            )
            self.api_calls += 1

            # Split back
            result = cut_full_grid(styled)

            print("✓")
            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return TileGrid()
