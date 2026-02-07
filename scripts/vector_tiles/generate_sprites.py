#!/usr/bin/env python3
"""
Generate pencil-style sprite textures for MapLibre.

Creates:
- Pencil line strokes (various widths)
- Paper texture
- Hatching patterns
- Cross-hatch patterns

Output:
- sprite.png (combined sprite sheet)
- sprite.json (index file)
- sprite@2x.png (high-DPI version)
- sprite@2x.json (high-DPI index)
"""

import json
import random
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

try:
    from noise import pnoise2
    HAS_NOISE = True
except ImportError:
    HAS_NOISE = False

# Directories
OUTPUT_DIR = Path(__file__).parent.parent.parent / "public" / "tiles" / "vector"
PATTERNS_DIR = OUTPUT_DIR / "patterns"


def create_pencil_line(width: int, height: int, thickness: float = 2.0,
                       color: tuple = (42, 37, 32), seed: int = 42) -> Image.Image:
    """
    Create a horizontal pencil line texture with natural variation.

    Args:
        width: Image width (should be power of 2)
        height: Image height
        thickness: Base line thickness
        color: RGB color tuple
        seed: Random seed for reproducibility
    """
    random.seed(seed)
    np.random.seed(seed)

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw multiple slightly offset lines for pencil effect
    center_y = height // 2

    for i in range(3):  # Multiple passes for texture
        opacity = 180 - i * 40  # Decreasing opacity
        y_offset = (i - 1) * 0.5  # Slight vertical offset

        points = []
        for x in range(width):
            # Add wobble using sine waves and noise
            wobble = math.sin(x * 0.1 + seed) * 0.5
            if HAS_NOISE:
                wobble += pnoise2(x * 0.05, seed * 0.1) * 1.0
            else:
                wobble += random.gauss(0, 0.3)

            y = center_y + y_offset + wobble
            points.append((x, y))

        # Draw the line
        for j in range(len(points) - 1):
            x1, y1 = points[j]
            x2, y2 = points[j + 1]

            # Variable thickness
            t = thickness * (0.8 + random.random() * 0.4)

            # Gaps for pencil texture
            if random.random() > 0.92:
                continue

            draw.line([(x1, y1), (x2, y2)],
                     fill=(*color, opacity),
                     width=max(1, int(t)))

    # Add slight blur for softer edges
    img = img.filter(ImageFilter.GaussianBlur(radius=0.3))

    return img


def create_paper_texture(width: int, height: int, seed: int = 42) -> Image.Image:
    """
    Create a subtle paper/parchment texture.
    """
    random.seed(seed)
    np.random.seed(seed)

    # Base color (warm cream)
    base_color = np.array([248, 244, 232])

    # Create noise pattern
    img_array = np.zeros((height, width, 4), dtype=np.uint8)

    for y in range(height):
        for x in range(width):
            # Multiple octaves of noise for paper grain
            if HAS_NOISE:
                n1 = pnoise2(x * 0.1, y * 0.1, octaves=2) * 8
                n2 = pnoise2(x * 0.3 + 100, y * 0.3 + 100, octaves=1) * 4
                variation = n1 + n2
            else:
                variation = random.gauss(0, 4)

            color = np.clip(base_color + variation, 0, 255).astype(np.uint8)
            img_array[y, x] = [color[0], color[1], color[2], 255]

    img = Image.fromarray(img_array, 'RGBA')
    return img


def create_hatching(width: int, height: int, spacing: int = 4,
                    angle: float = 45, color: tuple = (90, 85, 80)) -> Image.Image:
    """
    Create diagonal hatching pattern.
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Calculate line parameters
    rad = math.radians(angle)
    dx = math.cos(rad)
    dy = math.sin(rad)

    # Draw diagonal lines
    max_dist = int(math.sqrt(width**2 + height**2))

    for offset in range(-max_dist, max_dist, spacing):
        # Start and end points
        if angle == 45:
            x1, y1 = offset, 0
            x2, y2 = offset + height, height
        elif angle == -45:
            x1, y1 = offset, height
            x2, y2 = offset + height, 0
        else:
            # General angle
            x1 = offset
            y1 = 0
            x2 = offset + int(height / math.tan(rad)) if rad != 0 else offset
            y2 = height

        # Add wobble
        wobble1 = random.gauss(0, 0.5)
        wobble2 = random.gauss(0, 0.5)

        # Variable opacity for texture
        opacity = random.randint(100, 180)

        draw.line([(x1 + wobble1, y1), (x2 + wobble2, y2)],
                 fill=(*color, opacity),
                 width=1)

    return img


def create_crosshatch(width: int, height: int, spacing: int = 6,
                      color: tuple = (90, 85, 80)) -> Image.Image:
    """
    Create cross-hatch pattern (two directions).
    """
    img1 = create_hatching(width, height, spacing, 45, color)
    img2 = create_hatching(width, height, spacing, -45, color)

    # Blend the two
    img1.paste(img2, (0, 0), img2)
    return img1


def create_dots_pattern(width: int, height: int, spacing: int = 8,
                        color: tuple = (70, 65, 60)) -> Image.Image:
    """
    Create stipple/dots pattern for shading.
    """
    random.seed(42)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for y in range(0, height, spacing):
        for x in range(0, width, spacing):
            # Random offset
            ox = random.randint(-1, 1)
            oy = random.randint(-1, 1)

            # Random size and opacity
            r = random.uniform(0.5, 1.5)
            opacity = random.randint(80, 160)

            draw.ellipse([x + ox - r, y + oy - r, x + ox + r, y + oy + r],
                        fill=(*color, opacity))

    return img


def load_external_patterns(scale: int = 1) -> dict[str, dict]:
    """
    Load pattern images from the /patterns/ directory.

    These are pre-extracted pencil stroke textures that supplement
    the procedurally generated patterns.

    Args:
        scale: 1 for normal, 2 for @2x (will scale the image)

    Returns:
        Dictionary mapping pattern name to config dict with 'image', 'width', 'height'
    """
    patterns = {}

    if not PATTERNS_DIR.exists():
        print(f"  Warning: Patterns directory not found: {PATTERNS_DIR}")
        return patterns

    for png_path in sorted(PATTERNS_DIR.glob("*.png")):
        name = png_path.stem  # filename without extension

        try:
            img = Image.open(png_path).convert("RGBA")

            # Scale for @2x if needed
            if scale > 1:
                new_size = (img.width * scale, img.height * scale)
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            patterns[name] = {
                "image": img,
                "width": img.width,
                "height": img.height,
            }
            print(f"  Loaded external pattern: {name} ({img.width}x{img.height})")
        except Exception as e:
            print(f"  Warning: Failed to load {png_path}: {e}")

    return patterns


def create_water_ripple(width: int, height: int,
                        color: tuple = (152, 168, 184)) -> Image.Image:
    """
    Create horizontal wavy lines for water.
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw wavy horizontal lines
    for y_base in range(4, height - 4, 8):
        points = []
        for x in range(width):
            wave = math.sin(x * 0.15) * 2 + math.sin(x * 0.08) * 1
            if HAS_NOISE:
                wave += pnoise2(x * 0.1, y_base * 0.1) * 1
            y = y_base + wave
            points.append((x, y))

        # Draw as connected line
        for i in range(len(points) - 1):
            opacity = random.randint(60, 120)
            draw.line([points[i], points[i+1]],
                     fill=(*color, opacity),
                     width=1)

    return img


def generate_sprite_sheet(scale: int = 1, include_external: bool = True) -> tuple[Image.Image, dict]:
    """
    Generate the complete sprite sheet and index.

    Args:
        scale: 1 for normal, 2 for @2x high-DPI
        include_external: Whether to include patterns from /patterns/ directory

    Returns:
        (sprite_image, sprite_index)
    """
    s = scale  # Shorthand

    # Define procedurally generated patterns
    procedural_patterns = {
        "pencil-line-thin": {
            "generator": lambda: create_pencil_line(64*s, 8*s, thickness=1.5*s),
            "width": 64*s, "height": 8*s
        },
        "pencil-line-medium": {
            "generator": lambda: create_pencil_line(64*s, 12*s, thickness=2.5*s, seed=43),
            "width": 64*s, "height": 12*s
        },
        "pencil-line-thick": {
            "generator": lambda: create_pencil_line(64*s, 16*s, thickness=4*s, seed=44),
            "width": 64*s, "height": 16*s
        },
        "paper-texture": {
            "generator": lambda: create_paper_texture(64*s, 64*s),
            "width": 64*s, "height": 64*s
        },
        "hatching-45": {
            "generator": lambda: create_hatching(64*s, 64*s, spacing=4*s),
            "width": 64*s, "height": 64*s
        },
        "crosshatch": {
            "generator": lambda: create_crosshatch(64*s, 64*s, spacing=6*s),
            "width": 64*s, "height": 64*s
        },
        "stipple": {
            "generator": lambda: create_dots_pattern(64*s, 64*s, spacing=6*s),
            "width": 64*s, "height": 64*s
        },
        "water-ripple": {
            "generator": lambda: create_water_ripple(64*s, 32*s),
            "width": 64*s, "height": 32*s
        },
    }

    # Load external patterns from /patterns/ directory
    external_patterns = {}
    if include_external:
        print(f"\n  Loading external patterns (scale={scale}x)...")
        external_patterns = load_external_patterns(scale)

    # Combine all patterns (external patterns can override procedural ones)
    all_patterns = list(procedural_patterns.items())
    for name, config in external_patterns.items():
        # Skip if already in procedural (prefer procedural for base patterns)
        if name not in procedural_patterns:
            all_patterns.append((name, config))

    total_count = len(all_patterns)
    print(f"  Total patterns: {total_count} ({len(procedural_patterns)} procedural + {len(external_patterns)} external)")

    # Calculate sprite sheet dimensions - use 4 columns for more patterns
    cols = 4
    rows = (total_count + cols - 1) // cols

    # Find max dimensions across all patterns
    max_w = 64 * s  # Default cell width
    max_h = 64 * s  # Default cell height
    for name, config in all_patterns:
        if "width" in config:
            max_w = max(max_w, config["width"])
        if "height" in config:
            max_h = max(max_h, config["height"])

    sheet_width = cols * max_w
    sheet_height = rows * max_h

    # Create sprite sheet
    sprite = Image.new("RGBA", (sheet_width, sheet_height), (0, 0, 0, 0))
    index = {}

    # Place each pattern
    for i, (name, config) in enumerate(all_patterns):
        col = i % cols
        row = i // cols

        x = col * max_w
        y = row * max_h

        # Generate or get the pattern image
        if "generator" in config:
            pattern_img = config["generator"]()
            width = config["width"]
            height = config["height"]
        else:
            # External pattern - already loaded
            pattern_img = config["image"]
            width = config["width"]
            height = config["height"]

        # Paste into sprite sheet
        sprite.paste(pattern_img, (x, y))

        # Add to index
        index[name] = {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "pixelRatio": scale
        }

        print(f"  Added: {name} ({width}x{height}) at ({x}, {y})")

    return sprite, index


def main():
    """Generate sprite files."""
    print("=" * 60)
    print("GENERATING PENCIL SPRITE TEXTURES")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate 1x sprites
    print("\nGenerating 1x sprites...")
    sprite_1x, index_1x = generate_sprite_sheet(scale=1)

    sprite_1x.save(OUTPUT_DIR / "sprite.png")
    with open(OUTPUT_DIR / "sprite.json", "w") as f:
        json.dump(index_1x, f, indent=2)

    print(f"  Saved: sprite.png ({sprite_1x.size[0]}x{sprite_1x.size[1]})")
    print(f"  Saved: sprite.json")

    # Generate 2x sprites (high-DPI)
    print("\nGenerating 2x sprites (high-DPI)...")
    sprite_2x, index_2x = generate_sprite_sheet(scale=2)

    sprite_2x.save(OUTPUT_DIR / "sprite@2x.png")
    with open(OUTPUT_DIR / "sprite@2x.json", "w") as f:
        json.dump(index_2x, f, indent=2)

    print(f"  Saved: sprite@2x.png ({sprite_2x.size[0]}x{sprite_2x.size[1]})")
    print(f"  Saved: sprite@2x.json")

    print("\n" + "=" * 60)
    print("SPRITE GENERATION COMPLETE")
    print("=" * 60)
    print(f"\nPatterns available: {list(index_1x.keys())}")


if __name__ == "__main__":
    main()
