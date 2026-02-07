#!/usr/bin/env python3
"""
Side-by-side comparison of source vs v1 vs v2 for specific tiles.
"""

from pathlib import Path
from PIL import Image, ImageDraw

def load_image(path: Path) -> Image.Image:
    with Image.open(path) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        return img.copy()

def main():
    # Compare specific tiles
    tiles_to_compare = [
        (34322, 22950),  # Interior tile
        (34321, 22949),  # Corner tile
    ]

    output_dir = Path("output/debug_geometry")
    output_dir.mkdir(parents=True, exist_ok=True)

    for x, y in tiles_to_compare:
        source_path = Path(f"public/tiles/hybrid-golden_hour/16/{x}/{y}.webp")
        v1_path = Path(f"public/tiles/nano-winter-stitched/16/{x}/{y}.webp")
        v2_path = Path(f"public/tiles/nano-winter-stitched-v2/16/{x}/{y}.webp")

        images = []
        labels = []

        for path, label in [(source_path, "Source"), (v1_path, "v1 (L-shaped)"), (v2_path, "v2 (style ref)")]:
            if path.exists():
                images.append(load_image(path))
                labels.append(label)
            else:
                print(f"Missing: {path}")

        if len(images) < 2:
            print(f"Skipping tile ({x}, {y}) - not enough images")
            continue

        # Create side-by-side comparison
        width = sum(img.width for img in images) + (len(images) - 1) * 10
        height = max(img.height for img in images) + 40

        comparison = Image.new("RGB", (width, height), (40, 40, 40))
        draw = ImageDraw.Draw(comparison)

        x_offset = 0
        for img, label in zip(images, labels):
            comparison.paste(img, (x_offset, 30))
            draw.text((x_offset + 10, 5), label, fill=(255, 255, 255))
            x_offset += img.width + 10

        out_path = output_dir / f"compare_{x}_{y}.png"
        comparison.save(out_path)
        print(f"Saved: {out_path}")

    print(f"\nOpen with: open {output_dir}")

if __name__ == "__main__":
    main()
