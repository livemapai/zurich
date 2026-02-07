#!/usr/bin/env python3
"""
Extract pencil textures from scanned image using GIMP-style "Color to Alpha".

This replicates AJ Ashton's workflow:
1. Scan pencil lines on paper
2. Color to Alpha - remove paper, keep graphite
3. Slice into individual line patterns
4. Create tileable sprite sheet

Usage:
    python extract_pencil_textures.py /path/to/scanned_lines.webp
"""

import sys
from pathlib import Path
from PIL import Image
import numpy as np

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "public" / "tiles" / "vector"


def color_to_alpha(img: Image.Image, target_color: tuple = None,
                   contrast_boost: float = 3.5, gamma: float = 0.6,
                   preserve_color: bool = False) -> Image.Image:
    """
    GIMP-style Color to Alpha - removes paper background.

    This replicates the GIMP "Colors > Color to Alpha" filter:
    1. Calculates each pixel's "distance" from the paper color
    2. Uses distance to determine alpha (far = opaque, close = transparent)
    3. Optionally preserves original graphite color or normalizes to uniform gray

    Args:
        img: Input image (RGB or RGBA)
        target_color: RGB tuple of paper color to remove (default: auto-detect)
        contrast_boost: Multiplier to enhance pencil marks (higher = more opaque)
        gamma: Gamma correction for alpha curve (lower = more contrast)
        preserve_color: If True, keeps original pixel colors; if False, uses uniform graphite

    Returns:
        RGBA image with paper removed and transparency
    """
    # Convert to RGBA
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]

    # Auto-detect paper color by sampling multiple points along edges
    if target_color is None:
        # Sample corners and edge midpoints for robust detection
        sample_points = [
            (10, 10), (10, w-10), (h-10, 10), (h-10, w-10),  # corners
            (10, w//2), (h-10, w//2), (h//2, 10), (h//2, w-10),  # edge midpoints
            (h//4, w//4), (h//4, 3*w//4), (3*h//4, w//4), (3*h//4, 3*w//4),  # quadrant centers
        ]
        samples = [arr[min(y, h-1), min(x, w-1), :3] for y, x in sample_points]

        # Use median to be robust against pencil marks at edges
        target_color = np.median(samples, axis=0)
        print(f"  Auto-detected paper color: RGB({target_color[0]:.0f}, {target_color[1]:.0f}, {target_color[2]:.0f})")
    else:
        target_color = np.array(target_color, dtype=np.float32)

    # Extract RGB channels
    rgb = arr[:, :, :3]

    # Calculate luminance-weighted distance from paper color
    # This better captures how humans perceive graphite darkness
    diff = rgb - target_color

    # Luminance weights (ITU-R BT.709)
    weights = np.array([0.2126, 0.7152, 0.0722])
    weighted_diff = diff * weights

    # Euclidean distance in weighted RGB space
    distance = np.sqrt(np.sum(weighted_diff ** 2, axis=2))

    # Also consider simple luminance difference
    luminance = np.sum(rgb * weights, axis=2)
    paper_luminance = np.sum(target_color * weights)
    lum_diff = np.abs(luminance - paper_luminance) / 255.0

    # Combine both methods for better pencil detection
    # Higher value = more likely pencil (darker than paper)
    max_distance = np.sqrt(np.sum(weights ** 2)) * 255
    color_alpha = distance / max_distance

    # Use the stronger signal
    alpha = np.maximum(color_alpha, lum_diff)

    # Apply contrast boost and gamma for pencil enhancement
    # This curve makes faint pencil marks more visible while
    # keeping the paper fully transparent
    alpha = np.clip(alpha * contrast_boost, 0, 1)
    alpha = alpha ** gamma

    # Threshold very low alpha to prevent paper texture bleeding through
    alpha = np.where(alpha < 0.05, 0, alpha)

    # Create output array
    output = np.zeros_like(arr)

    if preserve_color:
        # Keep original colors (for colored pencils)
        output[:, :, :3] = rgb
    else:
        # Normalize to graphite color (for consistent pencil look)
        # Use a warm dark gray that matches pencil graphite
        graphite_color = np.array([42, 38, 34], dtype=np.float32)
        output[:, :, :3] = graphite_color

    # Set alpha channel
    output[:, :, 3] = alpha * 255

    return Image.fromarray(output.astype(np.uint8), 'RGBA')


def extract_line_regions(img: Image.Image, num_columns: int = 20) -> list:
    """
    Extract individual line regions from the scanned image.

    Based on visual analysis of AJ Ashton's scanned pencil patterns:
    - Image width ~950px with ruler on right edge
    - Patterns arranged left to right, roughly 30-50px spacing
    - Various line weights from hairline to heavy graphite

    Args:
        img: Input image
        num_columns: Approximate number of columns to divide into

    Returns:
        List of (x_start, width, name, description) tuples for each line region
    """
    width, height = img.size

    # Manually defined regions based on AJ Ashton's scan analysis
    # The scanned image shows patterns at these approximate x-positions:
    #
    # |dots|thin lines|dashes|symbols|medium|thick|zigzag|heavy|ruler|
    # 0   50        150    250     400   550  650   750   850  950

    regions = [
        # Thin pencil lines (left section)
        (55, 18, "pencil-line-thin", "Very thin hairline pencil stroke"),
        (80, 18, "line-thin-2", "Thin pencil line variant"),
        (105, 20, "line-thin-3", "Light thin line"),

        # Horizontal dashes / tick marks (for hatching base)
        (135, 25, "dash-short", "Short horizontal dashes"),
        (165, 25, "dash-medium", "Medium horizontal dashes"),

        # Symbol patterns (arrows, x marks)
        (200, 30, "symbol-arrow", "Arrow/direction symbols"),
        (235, 30, "symbol-x", "X marks pattern"),
        (270, 30, "symbol-cross", "Cross/plus pattern"),

        # Medium weight lines
        (310, 22, "pencil-line-medium", "Medium weight pencil stroke"),
        (340, 22, "line-medium-2", "Medium line variant"),
        (370, 25, "line-medium-3", "Slightly heavier medium line"),

        # Solid darker lines
        (405, 25, "line-solid", "Solid continuous line"),
        (440, 28, "line-solid-thick", "Thicker solid line"),

        # Zigzag/wavy patterns
        (480, 35, "zigzag-fine", "Fine zigzag pattern"),
        (525, 40, "zigzag-medium", "Medium zigzag pattern"),
        (575, 45, "zigzag-bold", "Bold zigzag pattern"),

        # Heavy graphite lines (right section)
        (630, 35, "pencil-line-thick", "Thick grainy pencil stroke"),
        (680, 40, "line-thick-grainy", "Heavy grainy graphite line"),
        (730, 45, "line-very-heavy", "Very heavy dark line"),

        # Extra thick / double lines
        (785, 50, "line-double", "Double parallel lines"),
        (845, 55, "line-extra-heavy", "Extra heavy graphite"),
    ]

    return regions


def slice_and_save(img: Image.Image, regions: list, output_dir: Path,
                   tile_height: int = 64) -> dict:
    """
    Slice regions from image and save as tileable patterns.

    Args:
        img: Color-to-alpha processed image
        regions: List of region definitions
        output_dir: Where to save individual PNGs
        tile_height: Height to crop for tileable patterns

    Returns:
        Dictionary mapping names to Image objects
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    width, height = img.size

    saved = {}

    # For vertical lines, we want to crop the middle section
    # This avoids any artifacts at the top/bottom of the scan
    y_start = height // 3
    y_end = y_start + tile_height

    for x_start, region_width, name, desc in regions:
        # Ensure we don't go out of bounds
        if x_start + region_width > width or x_start < 0:
            print(f"  Skipping {name}: out of bounds (x={x_start}, w={region_width})")
            continue

        # Crop the region
        region = img.crop((x_start, y_start, x_start + region_width, y_end))

        # Save individual pattern for debugging
        pattern_path = output_dir / f"{name}.png"
        region.save(pattern_path)
        saved[name] = region
        print(f"  Extracted: {name} ({region_width}x{tile_height})")

    return saved


def create_hatching_from_line(line_img: Image.Image, angle: float = 45,
                              spacing: int = 6) -> Image.Image:
    """
    Create diagonal hatching pattern by tiling and rotating a line texture.

    Args:
        line_img: Single pencil line image
        angle: Rotation angle in degrees (45 for NE-SW hatching)
        spacing: Pixels between each line

    Returns:
        Square hatching pattern image
    """
    size = 64
    output = Image.new('RGBA', (size, size), (0, 0, 0, 0))

    # Resize line to be thin
    line_height = 2
    line_resized = line_img.resize((size * 2, line_height), Image.LANCZOS)

    # Place lines at regular intervals
    for y in range(-size, size * 2, spacing):
        # Paste the line
        temp = Image.new('RGBA', (size * 2, size * 2), (0, 0, 0, 0))
        temp.paste(line_resized, (0, y + size))

        # Rotate around center
        rotated = temp.rotate(angle, center=(size, size), expand=False, resample=Image.BICUBIC)

        # Crop to final size
        cropped = rotated.crop((size//2, size//2, size//2 + size, size//2 + size))

        # Composite onto output
        output = Image.alpha_composite(output, cropped)

    return output


def create_crosshatch_from_line(line_img: Image.Image, spacing: int = 8) -> Image.Image:
    """
    Create cross-hatch pattern by combining two directions of hatching.
    """
    hatch1 = create_hatching_from_line(line_img, angle=45, spacing=spacing)
    hatch2 = create_hatching_from_line(line_img, angle=-45, spacing=spacing)

    # Combine with reduced opacity for second layer
    output = hatch1.copy()
    output = Image.alpha_composite(output, hatch2)

    return output


def create_water_ripple(line_img: Image.Image) -> Image.Image:
    """
    Create wavy water pattern from a pencil line.

    Uses sine waves to create horizontal ripple effect.
    """
    import math

    size = 64
    height = 32
    output = Image.new('RGBA', (size, height), (0, 0, 0, 0))

    # Get line as array for pixel manipulation
    line_arr = np.array(line_img)

    # Create wavy lines
    for y_base in range(4, height - 4, 8):
        for x in range(size):
            # Calculate wave offset
            wave = math.sin(x * 0.15) * 3 + math.sin(x * 0.08 + 1.5) * 1.5
            y = int(y_base + wave)

            if 0 <= y < height:
                # Sample from source line
                src_x = x % line_img.width
                src_y = min(line_img.height // 2, line_img.height - 1)

                if src_x < line_arr.shape[1] and src_y < line_arr.shape[0]:
                    pixel = line_arr[src_y, src_x]
                    if pixel[3] > 20:  # Only if there's alpha
                        # Reduce opacity for water
                        output.putpixel((x, y), (pixel[0], pixel[1], pixel[2], pixel[3] // 2))

    return output


def create_stipple_pattern(line_img: Image.Image, density: int = 8) -> Image.Image:
    """
    Create stipple/dot pattern by sampling points from pencil texture.
    """
    import random
    random.seed(42)

    size = 64
    output = Image.new('RGBA', (size, size), (0, 0, 0, 0))

    # Get graphite color from line image
    line_arr = np.array(line_img)
    mask = line_arr[:, :, 3] > 50
    if mask.any():
        graphite_color = tuple(int(c) for c in np.mean(line_arr[mask][:, :3], axis=0))
    else:
        graphite_color = (42, 38, 34)

    # Place dots in a semi-regular grid with randomness
    for y in range(0, size, density):
        for x in range(0, size, density):
            # Add random offset
            ox = random.randint(-2, 2)
            oy = random.randint(-2, 2)

            px = (x + ox) % size
            py = (y + oy) % size

            # Random size and opacity
            radius = random.uniform(0.5, 1.5)
            opacity = random.randint(60, 140)

            # Draw dot (simple approximation)
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    if dx*dx + dy*dy <= radius*radius:
                        fx = (px + dx) % size
                        fy = (py + dy) % size
                        current = output.getpixel((fx, fy))
                        new_alpha = min(255, current[3] + opacity // 2)
                        output.putpixel((fx, fy), (*graphite_color, new_alpha))

    return output


def create_sprite_sheet(patterns: dict, scale: int = 1) -> tuple:
    """
    Combine individual patterns into a sprite sheet.

    Args:
        patterns: Dict of name -> Image object
        scale: 1 for normal, 2 for @2x

    Returns:
        (sprite_image, sprite_index)
    """
    # Scale images if needed
    images = {}
    for name, img in patterns.items():
        if scale > 1:
            img = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)
        images[name] = img

    if not images:
        # Return empty sprite if no patterns
        return Image.new('RGBA', (1, 1), (0, 0, 0, 0)), {}

    # Calculate sprite sheet dimensions (arrange in 2 columns)
    cols = 2
    max_width = max(img.width for img in images.values())
    max_height = max(img.height for img in images.values())

    rows = (len(images) + cols - 1) // cols
    sheet_width = cols * max_width
    sheet_height = rows * max_height

    # Create sprite sheet
    sprite = Image.new('RGBA', (sheet_width, sheet_height), (0, 0, 0, 0))
    index = {}

    for i, (name, img) in enumerate(sorted(images.items())):
        col = i % cols
        row = i // cols
        x = col * max_width
        y = row * max_height

        sprite.paste(img, (x, y))

        index[name] = {
            "x": x,
            "y": y,
            "width": img.width,
            "height": img.height,
            "pixelRatio": scale
        }

    return sprite, index


def create_paper_texture(size: int = 64) -> Image.Image:
    """
    Create subtle paper texture pattern.

    This adds a light grain that simulates drawing paper.
    """
    import random
    random.seed(42)

    # Warm cream base - use int16 to avoid overflow during calculations
    arr = np.zeros((size, size, 4), dtype=np.int16)
    arr[:, :, 0] = 248  # R
    arr[:, :, 1] = 244  # G
    arr[:, :, 2] = 232  # B
    arr[:, :, 3] = 255  # A (full opacity for background)

    # Add subtle noise for paper grain
    for y in range(size):
        for x in range(size):
            variation = random.randint(-5, 5)
            arr[y, x, 0] = arr[y, x, 0] + variation
            arr[y, x, 1] = arr[y, x, 1] + variation
            arr[y, x, 2] = arr[y, x, 2] + variation - 2

    # Clip to valid range and convert to uint8
    arr = np.clip(arr, 0, 255).astype(np.uint8)

    return Image.fromarray(arr, 'RGBA')


def main():
    """Main extraction pipeline."""
    import json

    # Get input image path
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
    else:
        # Default to the downloaded AJ Ashton scan
        input_path = Path.home() / "Downloads" / "0_bI5FuF8Uj30KySiU.webp"

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        print("\nPlease provide the path to AJ Ashton's scanned pencil lines image.")
        print("Usage: python extract_pencil_textures.py /path/to/scanned_lines.webp")
        sys.exit(1)

    print("=" * 60)
    print("EXTRACTING REAL PENCIL TEXTURES")
    print("=" * 60)
    print(f"\nInput: {input_path}")
    print(f"Output: {OUTPUT_DIR}")

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    patterns_dir = OUTPUT_DIR / "patterns"
    patterns_dir.mkdir(exist_ok=True)

    # Load image
    print("\n[1/5] Loading scanned image...")
    img = Image.open(input_path)
    print(f"  Size: {img.size[0]}x{img.size[1]}")
    print(f"  Mode: {img.mode}")

    # Apply Color to Alpha
    print("\n[2/5] Applying Color to Alpha (removing paper background)...")
    processed = color_to_alpha(img, contrast_boost=3.5, gamma=0.6)

    # Save processed full image for inspection
    processed_path = OUTPUT_DIR / "pencil-processed.png"
    processed.save(processed_path)
    print(f"  Saved processed image: {processed_path}")

    # Extract line regions
    print("\n[3/5] Extracting individual line patterns...")
    regions = extract_line_regions(img)
    raw_patterns = slice_and_save(processed, regions, patterns_dir)

    # Create the final sprite patterns matching generate_style.py expectations
    print("\n[4/5] Creating MapLibre-compatible sprite patterns...")
    final_patterns = {}

    # Map extracted patterns to expected names
    # These are the names used in generate_style.py
    pattern_mapping = {
        # Primary line patterns (for roads, building outlines)
        "pencil-line-thin": ["pencil-line-thin", "line-thin-2", "line-thin-3"],
        "pencil-line-medium": ["pencil-line-medium", "line-medium-2", "line-medium-3"],
        "pencil-line-thick": ["pencil-line-thick", "line-thick-grainy", "line-very-heavy"],
    }

    # Select best available pattern for each required type
    for target_name, source_candidates in pattern_mapping.items():
        for source_name in source_candidates:
            if source_name in raw_patterns:
                pattern = raw_patterns[source_name]
                # Resize to consistent width for lines (64px wide, preserve height)
                target_width = 64
                aspect = pattern.height / pattern.width
                target_height = max(8, int(target_width * aspect))
                if target_name == "pencil-line-thin":
                    target_height = 8
                elif target_name == "pencil-line-medium":
                    target_height = 12
                elif target_name == "pencil-line-thick":
                    target_height = 16

                resized = pattern.resize((target_width, target_height), Image.LANCZOS)
                final_patterns[target_name] = resized
                print(f"  {target_name} <- {source_name} ({target_width}x{target_height})")
                break

    # Create derived patterns
    print("\n  Creating derived patterns...")

    # Get a medium line for creating hatching/crosshatch
    base_line = None
    for name in ["pencil-line-medium", "pencil-line-thin", "pencil-line-thick"]:
        if name in final_patterns:
            base_line = final_patterns[name]
            break

    if base_line is None and raw_patterns:
        # Use first available pattern
        base_line = list(raw_patterns.values())[0]

    if base_line:
        # Create hatching pattern (diagonal lines)
        hatching = create_hatching_from_line(base_line, angle=45, spacing=6)
        final_patterns["hatching-45"] = hatching
        print(f"  hatching-45 (64x64) - diagonal line pattern")

        # Create crosshatch pattern (two directions)
        crosshatch = create_crosshatch_from_line(base_line, spacing=8)
        final_patterns["crosshatch"] = crosshatch
        print(f"  crosshatch (64x64) - two-direction hatching")

        # Create stipple pattern (dots)
        stipple = create_stipple_pattern(base_line, density=8)
        final_patterns["stipple"] = stipple
        print(f"  stipple (64x64) - dot pattern")

        # Create water ripple pattern
        water = create_water_ripple(base_line)
        final_patterns["water-ripple"] = water
        print(f"  water-ripple (64x32) - wavy lines")

    # Create paper texture
    paper = create_paper_texture(64)
    final_patterns["paper-texture"] = paper
    print(f"  paper-texture (64x64) - subtle grain")

    # Create sprite sheets
    print("\n[5/5] Creating sprite sheets...")

    # 1x sprite
    sprite_1x, index_1x = create_sprite_sheet(final_patterns, scale=1)
    sprite_1x.save(OUTPUT_DIR / "sprite.png")

    with open(OUTPUT_DIR / "sprite.json", "w") as f:
        json.dump(index_1x, f, indent=2)
    print(f"  Saved: sprite.png ({sprite_1x.size[0]}x{sprite_1x.size[1]})")
    print(f"  Saved: sprite.json")

    # 2x sprite (high-DPI)
    sprite_2x, index_2x = create_sprite_sheet(final_patterns, scale=2)
    sprite_2x.save(OUTPUT_DIR / "sprite@2x.png")

    with open(OUTPUT_DIR / "sprite@2x.json", "w") as f:
        json.dump(index_2x, f, indent=2)
    print(f"  Saved: sprite@2x.png ({sprite_2x.size[0]}x{sprite_2x.size[1]})")
    print(f"  Saved: sprite@2x.json")

    # Summary
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"\nCreated {len(final_patterns)} sprite patterns:")
    for name in sorted(final_patterns.keys()):
        img = final_patterns[name]
        print(f"  - {name} ({img.width}x{img.height})")

    print(f"\nSprite files written to: {OUTPUT_DIR}")
    print("\nNext steps:")
    print("  1. Inspect sprite.png to verify texture quality")
    print("  2. Run: python3 -m scripts.vector_tiles.pipeline style")
    print("  3. View /vector route in browser")


if __name__ == "__main__":
    main()
