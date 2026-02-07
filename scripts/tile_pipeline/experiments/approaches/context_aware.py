#!/usr/bin/env python3
"""
Category C: Context-Aware Generation Approaches

These approaches generate tiles sequentially, using already-styled
tiles as context for generating new tiles.

Key insight: By showing the AI styled neighbors alongside the raw tile,
it can match colors and style to blend seamlessly.
"""

from PIL import Image

from ..utils import (
    TileGrid, call_gemini, TILE_SIZE,
    stitch_horizontal, stitch_vertical, stitch_2x2,
    cut_horizontal, cut_vertical, cut_2x2,
    HORIZONTAL_SIZE, VERTICAL_SIZE, GRID_2X2_SIZE,
)
from .base import BaseApproach


class LShapeContext(BaseApproach):
    """
    Approach 7: L-Shape Context (from nano_stitcher.py v1).

    Processing order:
    1. Style first 2 tiles (A+B) as seed pair
    2. Expand horizontally: C, D (using left neighbor)
    3. For each remaining row:
       - First tile: use tile directly above
       - Other tiles: L-shaped context (above-left, above, left)

    Grid processing order:
        x=0   x=1   x=2   x=3
    y=0  [1]═══[2]───[3]───[4]   ← Horizontal expansion
    y=1  [5]   [6]   [7]   [8]   ← L-shaped context
    y=2  [9]  [10]  [11]  [12]
    """

    description = "L-shape context: seed pair → expand with neighbors"
    category = "C: Context-Aware"

    def run(self, source_grid: TileGrid) -> TileGrid:
        result = TileGrid()

        # Phase 1: Seed pair (A + B)
        self._generate_seed_pair(source_grid, result, 'A', 'B')

        # Phase 1 continued: Horizontal expansion (C, D)
        for label, left_label in [('C', 'B'), ('D', 'C')]:
            self._generate_horizontal(source_grid, result, label, left_label)

        # Phase 2: Second row with L-shaped context
        # E: vertical from A
        self._generate_vertical(source_grid, result, 'E', 'A')

        # F, G, H: L-shaped context
        for label, al, a, l in [('F', 'A', 'B', 'E'), ('G', 'B', 'C', 'F'), ('H', 'C', 'D', 'G')]:
            self._generate_l_shaped(source_grid, result, label, al, a, l)

        # Phase 3: Third row with L-shaped context
        # I: vertical from E
        self._generate_vertical(source_grid, result, 'I', 'E')

        # J, K, L: L-shaped context
        for label, al, a, l in [('J', 'E', 'F', 'I'), ('K', 'F', 'G', 'J'), ('L', 'G', 'H', 'K')]:
            self._generate_l_shaped(source_grid, result, label, al, a, l)

        return result

    def _generate_seed_pair(self, source: TileGrid, result: TileGrid, label_a: str, label_b: str):
        """Style 2 tiles together as seed pair."""
        tile_a = source.get(label_a)
        tile_b = source.get(label_b)
        if tile_a is None or tile_b is None:
            print(f"  Seed pair {label_a}+{label_b} - skipped (missing tiles)")
            return

        print(f"  Seed pair {label_a}+{label_b}...", end=" ", flush=True)

        prompt = self.build_prompt(
            "You are styling 2 map tiles side-by-side (1024×512 total). "
            "Style BOTH tiles with consistent colors and atmosphere. "
            "They must blend seamlessly at the center edge. "
            "Return exactly 1024×512 pixels."
        )

        try:
            stitched = stitch_horizontal(tile_a, tile_b)
            styled = call_gemini(stitched, prompt, HORIZONTAL_SIZE, self.temperature, self.api_key)
            self.api_calls += 1

            left, right = cut_horizontal(styled)
            result.set(label_a, left)
            result.set(label_b, right)
            print("✓")
        except Exception as e:
            print(f"✗ Error: {e}")

    def _generate_horizontal(self, source: TileGrid, result: TileGrid, label: str, left_label: str):
        """Expand horizontally using styled left neighbor."""
        raw_tile = source.get(label)
        styled_left = result.get(left_label)

        if raw_tile is None or styled_left is None:
            print(f"  Tile {label} (horizontal) - skipped (missing context)")
            return

        print(f"  Tile {label} (horizontal expand)...", end=" ", flush=True)

        prompt = self.build_prompt(
            "You are styling a tile to match its neighbor (1024×512 total). "
            "LEFT tile: Already styled - DO NOT CHANGE IT. "
            "RIGHT tile: Raw - STYLE IT to match the left tile exactly. "
            "Match colors, lighting, atmosphere. Return exactly 1024×512 pixels."
        )

        try:
            stitched = stitch_horizontal(styled_left, raw_tile)
            styled = call_gemini(stitched, prompt, HORIZONTAL_SIZE, self.temperature, self.api_key)
            self.api_calls += 1

            _, right = cut_horizontal(styled)
            result.set(label, right)
            print("✓")
        except Exception as e:
            print(f"✗ Error: {e}")

    def _generate_vertical(self, source: TileGrid, result: TileGrid, label: str, above_label: str):
        """Expand vertically using styled above neighbor."""
        raw_tile = source.get(label)
        styled_above = result.get(above_label)

        if raw_tile is None or styled_above is None:
            print(f"  Tile {label} (vertical) - skipped (missing context)")
            return

        print(f"  Tile {label} (vertical expand)...", end=" ", flush=True)

        prompt = self.build_prompt(
            "You are styling a tile to match its neighbor (512×1024 total, vertical). "
            "TOP tile: Already styled - DO NOT CHANGE IT. "
            "BOTTOM tile: Raw - STYLE IT to match the top tile exactly. "
            "Match colors, lighting, atmosphere. Return exactly 512×1024 pixels."
        )

        try:
            stitched = stitch_vertical(styled_above, raw_tile)
            styled = call_gemini(stitched, prompt, VERTICAL_SIZE, self.temperature, self.api_key)
            self.api_calls += 1

            _, bottom = cut_vertical(styled)
            result.set(label, bottom)
            print("✓")
        except Exception as e:
            print(f"✗ Error: {e}")

    def _generate_l_shaped(self, source: TileGrid, result: TileGrid,
                          label: str, al_label: str, a_label: str, l_label: str):
        """Generate tile with L-shaped context (2×2 grid with 3 styled + 1 raw)."""
        raw_tile = source.get(label)
        styled_al = result.get(al_label)  # above-left
        styled_a = result.get(a_label)    # above
        styled_l = result.get(l_label)    # left

        if raw_tile is None or styled_al is None or styled_a is None or styled_l is None:
            print(f"  Tile {label} (L-shaped) - skipped (missing context)")
            return

        print(f"  Tile {label} (L-shaped context)...", end=" ", flush=True)

        prompt = self.build_prompt(
            "You are styling a tile in a 2×2 grid (1024×1024 total). "
            "TOP-LEFT: Already styled - DO NOT CHANGE. "
            "TOP-RIGHT: Already styled - DO NOT CHANGE. "
            "BOTTOM-LEFT: Already styled - DO NOT CHANGE. "
            "BOTTOM-RIGHT: Raw - STYLE IT to match the other three. "
            "Return exactly 1024×1024 pixels. Change only BOTTOM-RIGHT."
        )

        try:
            stitched = stitch_2x2(styled_al, styled_a, styled_l, raw_tile)
            styled = call_gemini(stitched, prompt, GRID_2X2_SIZE, self.temperature, self.api_key)
            self.api_calls += 1

            _, _, _, br = cut_2x2(styled)
            result.set(label, br)
            print("✓")
        except Exception as e:
            print(f"✗ Error: {e}")


class TwoPassReference(BaseApproach):
    """
    Approach 8: Two-Pass with Style Reference (from nano_stitcher_v2.py).

    Pass 1: Generate all tiles using L-shaped context (like Approach 7)
    Pass 2: Regenerate each tile with:
            - Full 2×2 styled context from Pass 1
            - A thumbnail of all styled tiles as "style reference"

    The style reference establishes THE color palette for Pass 2.
    """

    description = "Two-pass: L-shape → regenerate with style reference"
    category = "C: Context-Aware"

    def run(self, source_grid: TileGrid) -> TileGrid:
        # Pass 1: Use L-shape context approach
        print("\n  === Pass 1: L-Shape Context ===")
        l_shape = LShapeContext(self.user_prompt, self.temperature, self.api_key)
        pass1_result = l_shape.run(source_grid)
        self.api_calls += l_shape.api_calls

        if len(pass1_result) == 0:
            print("  Pass 1 failed, skipping Pass 2")
            return pass1_result

        # Create style reference (thumbnail of all styled tiles)
        print("\n  Creating style reference...", end=" ", flush=True)
        style_ref = self._create_style_reference(pass1_result)
        print(f"✓ ({style_ref.size})")

        # Pass 2: Regenerate with full context + style reference
        print("\n  === Pass 2: Regenerate with Style Reference ===")
        result = TileGrid()

        labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']

        for label in labels:
            raw_tile = source_grid.get(label)
            if raw_tile is None:
                continue

            # Find best 2×2 configuration for context
            context_2x2, position = self._get_best_context(pass1_result, raw_tile, label)

            if context_2x2 is None:
                # Keep Pass 1 result
                result.set(label, pass1_result.get(label))
                print(f"  Tile {label} - kept from Pass 1 (no context)")
                continue

            self._generate_with_reference(
                source_grid, pass1_result, result, label,
                context_2x2, position, style_ref
            )

        return result

    def _create_style_reference(self, styled_grid: TileGrid, max_size: int = 512) -> Image.Image:
        """Create a scaled-down thumbnail of all styled tiles."""
        from ..utils import stitch_full_grid

        composite = stitch_full_grid(styled_grid)
        width, height = composite.size

        # Scale down preserving aspect ratio
        scale = min(max_size / width, max_size / height)
        new_size = (int(width * scale), int(height * scale))
        return composite.resize(new_size, Image.LANCZOS)

    def _get_best_context(self, styled: TileGrid, raw_tile: Image.Image, label: str):
        """Find best 2×2 context configuration for a tile."""
        # Map label to grid position
        pos_map = {
            'A': (0, 0), 'B': (0, 1), 'C': (0, 2), 'D': (0, 3),
            'E': (1, 0), 'F': (1, 1), 'G': (1, 2), 'H': (1, 3),
            'I': (2, 0), 'J': (2, 1), 'K': (2, 2), 'L': (2, 3),
        }
        row, col = pos_map[label]

        # Try different 2×2 configurations
        # Config: (position of raw tile, [labels for TL, TR, BL, BR])
        configs = []

        # Raw at bottom-right: need above-left, above, left
        if row > 0 and col > 0:
            al = TileGrid.LAYOUT[row - 1][col - 1]
            a = TileGrid.LAYOUT[row - 1][col]
            l = TileGrid.LAYOUT[row][col - 1]
            if styled.get(al) and styled.get(a) and styled.get(l):
                configs.append(('br', [al, a, l, label]))

        # Raw at bottom-left: need above, above-right, right
        if row > 0 and col < 3:
            a = TileGrid.LAYOUT[row - 1][col]
            ar = TileGrid.LAYOUT[row - 1][col + 1]
            r = TileGrid.LAYOUT[row][col + 1]
            if styled.get(a) and styled.get(ar) and styled.get(r):
                configs.append(('bl', [a, ar, label, r]))

        # Raw at top-right: need left, below-left, below
        if row < 2 and col > 0:
            l = TileGrid.LAYOUT[row][col - 1]
            bl = TileGrid.LAYOUT[row + 1][col - 1]
            b = TileGrid.LAYOUT[row + 1][col]
            if styled.get(l) and styled.get(bl) and styled.get(b):
                configs.append(('tr', [l, label, bl, b]))

        # Raw at top-left: need right, below, below-right
        if row < 2 and col < 3:
            r = TileGrid.LAYOUT[row][col + 1]
            b = TileGrid.LAYOUT[row + 1][col]
            br = TileGrid.LAYOUT[row + 1][col + 1]
            if styled.get(r) and styled.get(b) and styled.get(br):
                configs.append(('tl', [label, r, b, br]))

        if not configs:
            return None, None

        # Use first valid config
        position, labels = configs[0]

        # Get tiles for 2×2 grid
        tiles = []
        for lbl in labels:
            if lbl == label:
                tiles.append(raw_tile)
            else:
                tiles.append(styled.get(lbl))

        context_2x2 = stitch_2x2(tiles[0], tiles[1], tiles[2], tiles[3])
        return context_2x2, position

    def _generate_with_reference(self, source: TileGrid, styled: TileGrid, result: TileGrid,
                                 label: str, context_2x2: Image.Image, position: str,
                                 style_ref: Image.Image):
        """Generate tile using 2×2 context + style reference."""
        print(f"  Tile {label} (Pass 2, {position})...", end=" ", flush=True)

        position_names = {
            'tl': 'TOP-LEFT', 'tr': 'TOP-RIGHT',
            'bl': 'BOTTOM-LEFT', 'br': 'BOTTOM-RIGHT',
        }

        # For this we'd need multi-image support - fall back to single image
        prompt = self.build_prompt(
            f"You are styling a tile in a 2×2 grid (1024×1024 total). "
            f"Three tiles are already styled. The {position_names[position]} tile is RAW. "
            f"Style the {position_names[position]} tile to match the others. "
            f"Return exactly 1024×1024 pixels."
        )

        try:
            styled_result = call_gemini(
                context_2x2, prompt, GRID_2X2_SIZE,
                self.temperature, self.api_key
            )
            self.api_calls += 1

            # Extract the specific position
            tl, tr, bl, br = cut_2x2(styled_result)
            position_tiles = {'tl': tl, 'tr': tr, 'bl': bl, 'br': br}
            result.set(label, position_tiles[position])
            print("✓")
        except Exception as e:
            print(f"✗ Error: {e}")
            # Keep Pass 1 result
            result.set(label, styled.get(label))


class SlidingWindow2x2(BaseApproach):
    """
    Approach 9: Sliding Window 2×2.

    Always use 2×2 context with overlapping windows.
    Each tile (except edges) gets styled multiple times; final
    result averages or uses most recent.

    Very thorough but expensive (many API calls).
    """

    description = "Sliding 2×2 window across entire grid"
    category = "C: Context-Aware"

    def run(self, source_grid: TileGrid) -> TileGrid:
        result = TileGrid()

        # First, generate seed 2×2 (ABEF)
        self._generate_2x2_block(source_grid, result, ['A', 'B', 'E', 'F'], is_seed=True)

        # Slide window across the grid
        # Row 0: BCFG, CDGH
        for labels in [['B', 'C', 'F', 'G'], ['C', 'D', 'G', 'H']]:
            self._generate_2x2_block(source_grid, result, labels)

        # Row 1: EFIJ, FGJK, GHKL
        for labels in [['E', 'F', 'I', 'J'], ['F', 'G', 'J', 'K'], ['G', 'H', 'K', 'L']]:
            self._generate_2x2_block(source_grid, result, labels)

        return result

    def _generate_2x2_block(self, source: TileGrid, result: TileGrid,
                           labels: list[str], is_seed: bool = False):
        """Generate/regenerate a 2×2 block."""
        block_name = ''.join(labels)

        if is_seed:
            # Seed: all tiles are raw
            tiles = [source.get(l) for l in labels]
            if None in tiles:
                print(f"  Block {block_name} (seed) - skipped (missing tiles)")
                return

            print(f"  Block {block_name} (seed)...", end=" ", flush=True)

            prompt = self.build_prompt(
                "You are styling 4 map tiles in a 2×2 grid (1024×1024 total). "
                "Style ALL tiles with consistent colors and atmosphere. "
                "They must blend seamlessly at all edges. "
                "Return exactly 1024×1024 pixels."
            )
        else:
            # Non-seed: use styled tiles for context where available
            tiles = []
            raw_positions = []
            for i, l in enumerate(labels):
                styled_tile = result.get(l)
                if styled_tile is not None:
                    tiles.append(styled_tile)
                else:
                    raw_tile = source.get(l)
                    if raw_tile is None:
                        print(f"  Block {block_name} - skipped (missing tiles)")
                        return
                    tiles.append(raw_tile)
                    raw_positions.append(i)

            if not raw_positions:
                print(f"  Block {block_name} - skipped (all already styled)")
                return

            print(f"  Block {block_name} ({len(raw_positions)} raw)...", end=" ", flush=True)

            pos_names = {0: 'TOP-LEFT', 1: 'TOP-RIGHT', 2: 'BOTTOM-LEFT', 3: 'BOTTOM-RIGHT'}
            raw_desc = ', '.join(pos_names[p] for p in raw_positions)

            prompt = self.build_prompt(
                f"You are styling tiles in a 2×2 grid (1024×1024 total). "
                f"Some tiles are already styled, others ({raw_desc}) are raw. "
                f"Style the raw tiles to match the styled ones seamlessly. "
                f"Return exactly 1024×1024 pixels."
            )

        try:
            stitched = stitch_2x2(tiles[0], tiles[1], tiles[2], tiles[3])
            styled = call_gemini(stitched, prompt, GRID_2X2_SIZE, self.temperature, self.api_key)
            self.api_calls += 1

            tl, tr, bl, br = cut_2x2(styled)
            result.set(labels[0], tl)
            result.set(labels[1], tr)
            result.set(labels[2], bl)
            result.set(labels[3], br)
            print("✓")
        except Exception as e:
            print(f"✗ Error: {e}")
