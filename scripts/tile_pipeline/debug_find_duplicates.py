#!/usr/bin/env python3
"""Find duplicate tiles in a style output."""

import hashlib
from collections import defaultdict
from pathlib import Path
from PIL import Image

def load_image(path: Path) -> Image.Image:
    with Image.open(path) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        return img.copy()

def image_hash(img: Image.Image) -> str:
    """Get a hash of image content."""
    return hashlib.md5(img.tobytes()).hexdigest()

def find_duplicates(style_dir: Path):
    """Find tiles with identical content."""
    hashes = defaultdict(list)

    for webp_file in sorted(style_dir.rglob("*.webp")):
        if "_backup" in webp_file.name:
            continue

        img = load_image(webp_file)
        h = image_hash(img)

        # Extract coords
        parts = webp_file.parts
        for i, part in enumerate(parts):
            if part.isdigit() and len(part) <= 2:
                x = int(parts[i + 1])
                y = int(parts[i + 2].replace(".webp", ""))
                hashes[h].append((x, y, webp_file))
                break

    print(f"Checking {style_dir.name}...")
    print(f"Total tiles: {sum(len(v) for v in hashes.values())}")
    print(f"Unique tiles: {len(hashes)}")

    duplicates = {h: tiles for h, tiles in hashes.items() if len(tiles) > 1}

    if duplicates:
        print(f"\n❌ Found {len(duplicates)} groups of duplicates:")
        for h, tiles in duplicates.items():
            coords = [f"({x},{y})" for x, y, _ in tiles]
            print(f"  Hash {h[:8]}: {' = '.join(coords)}")
    else:
        print("\n✅ No duplicates found!")

    return duplicates

def main():
    styles = [
        "nano-cyberpunk-v2",
        "nano-winter-stitched-v2",
        "nano-winter-stitched",
        "hybrid-golden_hour",
    ]

    for style in styles:
        style_dir = Path(f"public/tiles/{style}")
        if style_dir.exists():
            find_duplicates(style_dir)
            print()

if __name__ == "__main__":
    main()
