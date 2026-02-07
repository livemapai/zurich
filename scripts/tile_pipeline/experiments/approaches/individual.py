#!/usr/bin/env python3
"""
Category A: Individual Tile Approaches (Baseline)

These approaches style each tile independently without any context.
Expected to show visible seams and color drift.
"""

from ..utils import TileGrid, call_gemini, TILE_SIZE
from .base import BaseApproach


class IndividualTiles(BaseApproach):
    """
    Approach 1: Style each tile independently.

    This is the baseline approach - each tile is styled with no awareness
    of its neighbors. Expected to produce visible seams due to:
    - Random seed differences between calls
    - No context about surrounding tiles
    - Color/style drift across the grid
    """

    description = "Style each tile independently (baseline)"
    category = "A: Baseline"

    def run(self, source_grid: TileGrid) -> TileGrid:
        result = TileGrid()

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
                styled = call_gemini(
                    image=tile,
                    prompt=prompt,
                    expected_size=(TILE_SIZE, TILE_SIZE),
                    temperature=self.temperature,
                    api_key=self.api_key,
                )
                result.set(label, styled)
                self.api_calls += 1
                print("✓")
            except Exception as e:
                print(f"✗ Error: {e}")

        return result


class IndividualLowTemp(BaseApproach):
    """
    Approach 2: Style each tile independently with low temperature.

    Same as Approach 1, but uses temperature=0.1 for more deterministic
    generation. May reduce color drift but seams will still be visible.
    """

    description = "Individual tiles with low temperature (0.1)"
    category = "A: Baseline"

    def __init__(self, user_prompt: str, temperature: float = 0.1, api_key=None):
        # Force low temperature
        super().__init__(user_prompt, temperature=0.1, api_key=api_key)

    def run(self, source_grid: TileGrid) -> TileGrid:
        result = TileGrid()

        labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']
        total = len([l for l in labels if source_grid.get(l)])

        prompt = self.build_prompt(
            "You are styling a single 512×512 map tile. "
            "Be as consistent as possible with colors and style. "
            "Return exactly 512×512 pixels."
        )

        for i, label in enumerate(labels, 1):
            tile = source_grid.get(label)
            if tile is None:
                continue

            print(f"  [{i}/{total}] Tile {label} (low temp)...", end=" ", flush=True)

            try:
                styled = call_gemini(
                    image=tile,
                    prompt=prompt,
                    expected_size=(TILE_SIZE, TILE_SIZE),
                    temperature=self.temperature,
                    api_key=self.api_key,
                )
                result.set(label, styled)
                self.api_calls += 1
                print("✓")
            except Exception as e:
                print(f"✗ Error: {e}")

        return result
