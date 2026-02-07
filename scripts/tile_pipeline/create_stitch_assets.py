#!/usr/bin/env python3
"""
Create test assets for experimenting with tile stitching approaches.

This script generates various stitched tile combinations for manual
testing with different AI platforms (Gemini, OpenAI, Claude, etc.).

Grid Layout (viewing tiles from above):
     x=34321  x=34322  x=34323
y=22949   A        B        C
y=22950   D        E        F

Output Structure:
    assets/stitching_tests/
    ├── raw/                    # Individual input tiles (A-F)
    ├── styled/                 # Corresponding styled tiles
    ├── stitched_input/         # Pre-stitched raw combinations
    └── stitched_output/        # Pre-stitched styled combinations

Usage:
    python scripts/tile_pipeline/create_stitch_assets.py \\
        --raw-source public/tiles/hybrid-isometric_golden \\
        --styled-source public/tiles/pencil-deep-styler \\
        --output scripts/tile_pipeline/assets/stitching_tests
"""

import argparse
import shutil
from pathlib import Path
from typing import Optional

from PIL import Image


# Tile mapping: letter -> (x, y) coordinates
# Full 4x3 grid covering all available tiles
TILE_MAP = {
    # Row y=22949
    "A": (34321, 22949),
    "B": (34322, 22949),
    "C": (34323, 22949),
    "D": (34324, 22949),
    # Row y=22950
    "E": (34321, 22950),
    "F": (34322, 22950),
    "G": (34323, 22950),
    "H": (34324, 22950),
    # Row y=22951
    "I": (34321, 22951),
    "J": (34322, 22951),
    "K": (34323, 22951),
    "L": (34324, 22951),
}

# Stitching patterns to generate
STITCH_PATTERNS = {
    # Horizontal strips (2 tiles)
    "horizontal_2_AB": [["A", "B"]],
    "horizontal_2_BC": [["B", "C"]],
    "horizontal_2_CD": [["C", "D"]],
    "horizontal_2_FG": [["F", "G"]],
    "horizontal_2_JK": [["J", "K"]],

    # Horizontal strips (3 tiles)
    "horizontal_3_ABC": [["A", "B", "C"]],
    "horizontal_3_BCD": [["B", "C", "D"]],
    "horizontal_3_EFG": [["E", "F", "G"]],
    "horizontal_3_IJK": [["I", "J", "K"]],

    # Horizontal strips (4 tiles - full row)
    "horizontal_4_ABCD": [["A", "B", "C", "D"]],
    "horizontal_4_EFGH": [["E", "F", "G", "H"]],
    "horizontal_4_IJKL": [["I", "J", "K", "L"]],

    # Vertical strips (2 tiles)
    "vertical_2_AE": [["A"], ["E"]],
    "vertical_2_BF": [["B"], ["F"]],
    "vertical_2_EI": [["E"], ["I"]],
    "vertical_2_FJ": [["F"], ["J"]],

    # Vertical strips (3 tiles - full column)
    "vertical_3_AEI": [["A"], ["E"], ["I"]],
    "vertical_3_BFJ": [["B"], ["F"], ["J"]],
    "vertical_3_CGK": [["C"], ["G"], ["K"]],
    "vertical_3_DHL": [["D"], ["H"], ["L"]],

    # 2x2 grids
    "grid_2x2_ABEF": [["A", "B"], ["E", "F"]],
    "grid_2x2_BCFG": [["B", "C"], ["F", "G"]],
    "grid_2x2_CDGH": [["C", "D"], ["G", "H"]],
    "grid_2x2_EFIJ": [["E", "F"], ["I", "J"]],
    "grid_2x2_FGJK": [["F", "G"], ["J", "K"]],
    "grid_2x2_GHKL": [["G", "H"], ["K", "L"]],

    # 3x2 grids (wide)
    "grid_3x2_ABCEFG": [["A", "B", "C"], ["E", "F", "G"]],
    "grid_3x2_BCDFGH": [["B", "C", "D"], ["F", "G", "H"]],
    "grid_3x2_EFGIJK": [["E", "F", "G"], ["I", "J", "K"]],

    # 2x3 grids (tall)
    "grid_2x3_ABEFI_J": [["A", "B"], ["E", "F"], ["I", "J"]],
    "grid_2x3_BCFGJK": [["B", "C"], ["F", "G"], ["J", "K"]],
    "grid_2x3_CDGHKL": [["C", "D"], ["G", "H"], ["K", "L"]],

    # 3x3 grids
    "grid_3x3_center": [["A", "B", "C"], ["E", "F", "G"], ["I", "J", "K"]],
    "grid_3x3_right": [["B", "C", "D"], ["F", "G", "H"], ["J", "K", "L"]],

    # Full 4x3 grid (all 12 tiles)
    "grid_4x3_full": [
        ["A", "B", "C", "D"],
        ["E", "F", "G", "H"],
        ["I", "J", "K", "L"],
    ],
}


def get_tile_path(source_dir: Path, x: int, y: int, zoom: int = 16) -> Path:
    """Get the path to a tile file."""
    return source_dir / str(zoom) / str(x) / f"{y}.webp"


def copy_individual_tiles(
    source_dir: Path,
    output_dir: Path,
    zoom: int = 16,
) -> dict[str, Path]:
    """Copy individual tiles to output directory with letter names."""
    tile_paths = {}

    for letter, (x, y) in TILE_MAP.items():
        source_path = get_tile_path(source_dir, x, y, zoom)

        if not source_path.exists():
            print(f"  ⚠️  Missing tile {letter}: {source_path}")
            continue

        output_path = output_dir / f"tile_{letter}.png"

        # Convert to PNG for consistency
        with Image.open(source_path) as img:
            # Resize to 512x512 if needed
            if img.size != (512, 512):
                img = img.resize((512, 512), Image.LANCZOS)
            img.save(output_path, "PNG")

        tile_paths[letter] = output_path
        print(f"  ✓ Copied tile {letter} ({x}/{y})")

    return tile_paths


def stitch_tiles(
    pattern: list[list[Optional[str]]],
    tile_paths: dict[str, Path],
    tile_size: int = 512,
) -> Optional[Image.Image]:
    """Stitch tiles according to pattern. None = empty cell (transparent)."""
    rows = len(pattern)
    cols = max(len(row) for row in pattern)

    # Create output image with alpha channel for empty cells
    width = cols * tile_size
    height = rows * tile_size
    output = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    for row_idx, row in enumerate(pattern):
        for col_idx, letter in enumerate(row):
            if letter is None:
                continue

            if letter not in tile_paths:
                print(f"  ⚠️  Missing tile {letter} for pattern")
                return None

            # Open tile and paste at position
            with Image.open(tile_paths[letter]) as tile:
                # Convert to RGBA if needed
                if tile.mode != "RGBA":
                    tile = tile.convert("RGBA")

                x = col_idx * tile_size
                y = row_idx * tile_size
                output.paste(tile, (x, y))

    return output


def create_stitched_images(
    patterns: dict[str, list[list[Optional[str]]]],
    tile_paths: dict[str, Path],
    output_dir: Path,
) -> None:
    """Create all stitched pattern images."""
    for name, pattern in patterns.items():
        result = stitch_tiles(pattern, tile_paths)

        if result is None:
            print(f"  ✗ Failed to create {name}")
            continue

        output_path = output_dir / f"{name}.png"
        result.save(output_path, "PNG")

        # Calculate dimensions
        rows = len(pattern)
        cols = max(len(row) for row in pattern)
        print(f"  ✓ Created {name} ({cols * 512}×{rows * 512})")


def generate_readme(output_dir: Path, has_raw: bool, has_styled: bool) -> None:
    """Generate README documentation for the test assets."""
    readme_content = """# Tile Stitching Test Assets

This directory contains pre-stitched tile combinations for experimenting
with different stitching approaches across AI platforms.

## Directory Structure

```
stitching_tests/
├── raw/                 # Individual input tiles (A-F)
├── styled/              # Corresponding styled tiles
├── stitched_input/      # Pre-stitched raw combinations
└── stitched_output/     # Pre-stitched styled combinations
```

## Tile Grid Layout

Looking at the tiles from above (map coordinates) - full 4×3 grid:

```
        x=34321  x=34322  x=34323  x=34324
        ───────  ───────  ───────  ───────
y=22949 │  A   │   B   │   C   │   D   │
        ───────  ───────  ───────  ───────
y=22950 │  E   │   F   │   G   │   H   │
        ───────  ───────  ───────  ───────
y=22951 │  I   │   J   │   K   │   L   │
        ───────  ───────  ───────  ───────
```

## Stitching Patterns

| Pattern | Layout | Dimensions | Purpose |
|---------|--------|------------|---------|
| `horizontal_2_AB` | A+B | 1024×512 | Test horizontal edge matching |
| `horizontal_4_ABCD` | A+B+C+D | 2048×512 | Full row stitching |
| `vertical_3_AEI` | A/E/I | 512×1536 | Full column stitching |
| `grid_2x2_BCFG` | BC/FG | 1024×1024 | Center 2×2 grid |
| `grid_3x3_center` | ABC/EFG/IJK | 1536×1536 | Large 3×3 grid |
| `grid_4x3_full` | ABCD/EFGH/IJKL | 2048×1536 | Full 12-tile grid |

## Usage for Testing

### Manual Testing with Gemini/Claude/OpenAI Web UI

1. Upload a stitched input image (e.g., `stitched_input/horizontal_2_AB.png`)
2. Use a prompt like:

```
This is two map tiles stitched side-by-side. Convert them to [style]
while ensuring the seam between tiles is completely invisible.
The output should look like a single continuous image.
```

### Testing Edge Consistency

1. Style individual tiles A and B separately
2. Compare with stitched AB output
3. Check if the seam is visible when the individual styled tiles are placed together

### Recommended Test Prompts

**For pencil/sketch styles:**
```
Transform this map tile into a detailed architectural pencil sketch.
Pay special attention to maintaining consistent line weight and shading
across any tile boundaries to ensure seamless tiling.
```

**For artistic styles:**
```
Convert this satellite map view to a [watercolor/oil painting/impressionist] style.
Ensure colors and brush strokes are consistent across the entire image
to maintain seamless tile boundaries.
```

## Expected Challenges

1. **Edge discontinuity** - Different random seeds per tile cause visible seams
2. **Scale inconsistency** - Details may be rendered at different scales
3. **Color drift** - Slight color variations between tiles
4. **Texture alignment** - Repeated patterns may not align at edges

## Comparing Approaches

| Approach | Pros | Cons |
|----------|------|------|
| Pre-stitch + style | Perfect seams | Larger image = more $, lower quality |
| Style individually | Faster, cheaper | Visible seams |
| Post-stitch blend | Can work well | Complex, may blur details |
| Stitcher model pass | Good for some styles | Extra API call |

## Notes

- All tiles are 512×512 PNG (converted from WebP source)
- Transparent areas in L-shapes indicate empty cells
- Raw tiles are from: `hybrid-isometric_golden`
- Styled tiles are from: `pencil-deep-styler`
"""

    readme_path = output_dir / "README.md"
    readme_path.write_text(readme_content)
    print(f"  ✓ Generated README.md")


def main():
    parser = argparse.ArgumentParser(
        description="Create test assets for tile stitching experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--raw-source",
        type=Path,
        default=Path("public/tiles/hybrid-isometric_golden"),
        help="Directory containing raw/input tiles",
    )
    parser.add_argument(
        "--styled-source",
        type=Path,
        default=Path("public/tiles/pencil-deep-styler"),
        help="Directory containing styled/output tiles",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scripts/tile_pipeline/assets/stitching_tests"),
        help="Output directory for test assets",
    )
    parser.add_argument(
        "--zoom",
        type=int,
        default=16,
        help="Zoom level of tiles",
    )

    args = parser.parse_args()

    # Create output directories
    output_dir = args.output
    raw_dir = output_dir / "raw"
    styled_dir = output_dir / "styled"
    stitched_input_dir = output_dir / "stitched_input"
    stitched_output_dir = output_dir / "stitched_output"

    for d in [raw_dir, styled_dir, stitched_input_dir, stitched_output_dir]:
        d.mkdir(parents=True, exist_ok=True)

    print(f"\n🧵 Creating Tile Stitching Test Assets")
    print(f"{'─' * 50}")
    print(f"  Raw source:     {args.raw_source}")
    print(f"  Styled source:  {args.styled_source}")
    print(f"  Output:         {output_dir}")
    print(f"{'─' * 50}\n")

    # Copy individual raw tiles
    has_raw = False
    if args.raw_source.exists():
        print("📦 Copying raw tiles...")
        raw_tile_paths = copy_individual_tiles(args.raw_source, raw_dir, args.zoom)
        has_raw = len(raw_tile_paths) > 0
        print()
    else:
        print(f"⚠️  Raw source not found: {args.raw_source}")
        raw_tile_paths = {}

    # Copy individual styled tiles
    has_styled = False
    if args.styled_source.exists():
        print("🎨 Copying styled tiles...")
        styled_tile_paths = copy_individual_tiles(args.styled_source, styled_dir, args.zoom)
        has_styled = len(styled_tile_paths) > 0
        print()
    else:
        print(f"⚠️  Styled source not found: {args.styled_source}")
        styled_tile_paths = {}

    # Create stitched combinations
    if raw_tile_paths:
        print("🔗 Creating stitched input patterns...")
        create_stitched_images(STITCH_PATTERNS, raw_tile_paths, stitched_input_dir)
        print()

    if styled_tile_paths:
        print("🔗 Creating stitched output patterns...")
        create_stitched_images(STITCH_PATTERNS, styled_tile_paths, stitched_output_dir)
        print()

    # Generate README
    print("📝 Generating documentation...")
    generate_readme(output_dir, has_raw, has_styled)
    print()

    # Summary
    raw_count = len(list(raw_dir.glob("*.png"))) if raw_dir.exists() else 0
    styled_count = len(list(styled_dir.glob("*.png"))) if styled_dir.exists() else 0
    stitched_in = len(list(stitched_input_dir.glob("*.png"))) if stitched_input_dir.exists() else 0
    stitched_out = len(list(stitched_output_dir.glob("*.png"))) if stitched_output_dir.exists() else 0

    print(f"{'─' * 50}")
    print(f"  ✅ Raw tiles:         {raw_count}")
    print(f"  ✅ Styled tiles:      {styled_count}")
    print(f"  ✅ Stitched inputs:   {stitched_in}")
    print(f"  ✅ Stitched outputs:  {stitched_out}")
    print(f"\n  📁 Output: {output_dir}")
    print(f"  📖 Open README: open {output_dir}/README.md")
    print(f"{'─' * 50}\n")


if __name__ == "__main__":
    main()
