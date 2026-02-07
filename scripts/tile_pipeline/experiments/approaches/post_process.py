#!/usr/bin/env python3
"""
Category D: Post-Processing Approaches

These approaches first generate styled tiles independently, then
apply post-processing to fix seams.
"""

import numpy as np
from PIL import Image

from ..utils import (
    TileGrid, call_gemini, TILE_SIZE,
    stitch_horizontal, stitch_vertical,
    cut_horizontal, cut_vertical,
    blend_edges,
    HORIZONTAL_SIZE, VERTICAL_SIZE,
)
from .base import BaseApproach


class IndividualEdgeBlend(BaseApproach):
    """
    Approach 10: Individual tiles + edge blending.

    1. Style all tiles independently (like Approach 1)
    2. Blend overlapping edges between adjacent tiles

    Quick fix that may work for some styles but can blur details
    at seams.
    """

    description = "Individual tiles → blend edges (32px)"
    category = "D: Post-Processing"

    def __init__(self, user_prompt: str, temperature: float = 0.3,
                 api_key=None, blend_width: int = 32):
        super().__init__(user_prompt, temperature, api_key)
        self.blend_width = blend_width

    def run(self, source_grid: TileGrid) -> TileGrid:
        # Phase 1: Style all tiles individually
        print("\n  === Phase 1: Individual Styling ===")
        styled = TileGrid()

        labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']
        total = len([l for l in labels if source_grid.get(l)])

        prompt = self.build_prompt(
            "You are styling a single 512×512 map tile. "
            "Return exactly 512×512 pixels."
        )

        for i, label in enumerate(labels, 1):
            tile = source_grid.get(label)
            if tile is None:
                continue

            print(f"  [{i}/{total}] Tile {label}...", end=" ", flush=True)

            try:
                result = call_gemini(
                    image=tile,
                    prompt=prompt,
                    expected_size=(TILE_SIZE, TILE_SIZE),
                    temperature=self.temperature,
                    api_key=self.api_key,
                )
                styled.set(label, result)
                self.api_calls += 1
                print("✓")
            except Exception as e:
                print(f"✗ Error: {e}")

        # Phase 2: Blend edges
        print(f"\n  === Phase 2: Edge Blending ({self.blend_width}px) ===")
        result = self._blend_all_edges(styled)

        return result

    def _blend_all_edges(self, styled: TileGrid) -> TileGrid:
        """Blend edges between all adjacent tile pairs."""
        result = TileGrid()

        # Copy all tiles to result (we'll modify in place)
        for label in styled.labels:
            tile = styled.get(label)
            if tile:
                result.set(label, tile.copy())

        # Define horizontal adjacent pairs (left, right)
        h_pairs = [
            ('A', 'B'), ('B', 'C'), ('C', 'D'),
            ('E', 'F'), ('F', 'G'), ('G', 'H'),
            ('I', 'J'), ('J', 'K'), ('K', 'L'),
        ]

        # Define vertical adjacent pairs (top, bottom)
        v_pairs = [
            ('A', 'E'), ('B', 'F'), ('C', 'G'), ('D', 'H'),
            ('E', 'I'), ('F', 'J'), ('G', 'K'), ('H', 'L'),
        ]

        # Blend horizontal edges
        print("  Blending horizontal edges...", end=" ", flush=True)
        for left_label, right_label in h_pairs:
            left = result.get(left_label)
            right = result.get(right_label)
            if left is None or right is None:
                continue

            blended_left, blended_right = blend_edges(
                left, right, 'horizontal', self.blend_width
            )
            result.set(left_label, blended_left)
            result.set(right_label, blended_right)
        print("✓")

        # Blend vertical edges
        print("  Blending vertical edges...", end=" ", flush=True)
        for top_label, bottom_label in v_pairs:
            top = result.get(top_label)
            bottom = result.get(bottom_label)
            if top is None or bottom is None:
                continue

            blended_top, blended_bottom = blend_edges(
                top, bottom, 'vertical', self.blend_width
            )
            result.set(top_label, blended_top)
            result.set(bottom_label, blended_bottom)
        print("✓")

        return result


class IndividualStitcherPass(BaseApproach):
    """
    Approach 11: Individual tiles + stitcher pass.

    1. Style all tiles independently (like Approach 1)
    2. For each adjacent pair, run a "stitcher" API call that
       asks the AI to fix the seam while preserving interior content

    Two-phase approach that may give better results than simple blending.
    """

    description = "Individual tiles → AI stitcher pass"
    category = "D: Post-Processing"

    def run(self, source_grid: TileGrid) -> TileGrid:
        # Phase 1: Style all tiles individually
        print("\n  === Phase 1: Individual Styling ===")
        styled = TileGrid()

        labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']
        total = len([l for l in labels if source_grid.get(l)])

        prompt = self.build_prompt(
            "You are styling a single 512×512 map tile. "
            "Return exactly 512×512 pixels."
        )

        for i, label in enumerate(labels, 1):
            tile = source_grid.get(label)
            if tile is None:
                continue

            print(f"  [{i}/{total}] Tile {label}...", end=" ", flush=True)

            try:
                result = call_gemini(
                    image=tile,
                    prompt=prompt,
                    expected_size=(TILE_SIZE, TILE_SIZE),
                    temperature=self.temperature,
                    api_key=self.api_key,
                )
                styled.set(label, result)
                self.api_calls += 1
                print("✓")
            except Exception as e:
                print(f"✗ Error: {e}")

        # Phase 2: Stitcher pass for horizontal edges
        print("\n  === Phase 2: Horizontal Stitcher Pass ===")
        h_pairs = [
            ('A', 'B'), ('B', 'C'), ('C', 'D'),
            ('E', 'F'), ('F', 'G'), ('G', 'H'),
            ('I', 'J'), ('J', 'K'), ('K', 'L'),
        ]

        result = TileGrid()
        for label in styled.labels:
            tile = styled.get(label)
            if tile:
                result.set(label, tile.copy())

        for left_label, right_label in h_pairs:
            self._stitch_horizontal_pair(result, left_label, right_label)

        # Phase 3: Stitcher pass for vertical edges
        print("\n  === Phase 3: Vertical Stitcher Pass ===")
        v_pairs = [
            ('A', 'E'), ('B', 'F'), ('C', 'G'), ('D', 'H'),
            ('E', 'I'), ('F', 'J'), ('G', 'K'), ('H', 'L'),
        ]

        for top_label, bottom_label in v_pairs:
            self._stitch_vertical_pair(result, top_label, bottom_label)

        return result

    def _stitch_horizontal_pair(self, grid: TileGrid, left_label: str, right_label: str):
        """Fix the seam between two horizontally adjacent tiles."""
        left = grid.get(left_label)
        right = grid.get(right_label)

        if left is None or right is None:
            return

        print(f"  Stitching {left_label}+{right_label}...", end=" ", flush=True)

        stitcher_prompt = (
            "These are two ALREADY STYLED map tiles placed side-by-side (1024×512 total). "
            "They have a visible seam/discontinuity at the center edge. "
            "FIX THE SEAM by smoothly blending colors at the boundary. "
            "PRESERVE the interior content of both tiles - only modify near the edge. "
            "Return exactly 1024×512 pixels."
        )

        try:
            stitched = stitch_horizontal(left, right)
            fixed = call_gemini(
                stitched, stitcher_prompt, HORIZONTAL_SIZE,
                self.temperature, self.api_key
            )
            self.api_calls += 1

            fixed_left, fixed_right = cut_horizontal(fixed)
            grid.set(left_label, fixed_left)
            grid.set(right_label, fixed_right)
            print("✓")
        except Exception as e:
            print(f"✗ Error: {e}")

    def _stitch_vertical_pair(self, grid: TileGrid, top_label: str, bottom_label: str):
        """Fix the seam between two vertically adjacent tiles."""
        top = grid.get(top_label)
        bottom = grid.get(bottom_label)

        if top is None or bottom is None:
            return

        print(f"  Stitching {top_label}+{bottom_label}...", end=" ", flush=True)

        stitcher_prompt = (
            "These are two ALREADY STYLED map tiles stacked vertically (512×1024 total). "
            "They have a visible seam/discontinuity at the center edge. "
            "FIX THE SEAM by smoothly blending colors at the boundary. "
            "PRESERVE the interior content of both tiles - only modify near the edge. "
            "Return exactly 512×1024 pixels."
        )

        try:
            stitched = stitch_vertical(top, bottom)
            fixed = call_gemini(
                stitched, stitcher_prompt, VERTICAL_SIZE,
                self.temperature, self.api_key
            )
            self.api_calls += 1

            fixed_top, fixed_bottom = cut_vertical(fixed)
            grid.set(top_label, fixed_top)
            grid.set(bottom_label, fixed_bottom)
            print("✓")
        except Exception as e:
            print(f"✗ Error: {e}")
