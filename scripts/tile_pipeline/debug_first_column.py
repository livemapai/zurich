#!/usr/bin/env python3
"""Debug the first column styling issue."""

from pathlib import Path
from PIL import Image, ImageDraw

def load_image(path: Path) -> Image.Image:
    with Image.open(path) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        return img.copy()

def main():
    output_dir = Path("output/debug_first_col")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Compare first column tiles between source and cyberpunk-v2
    tiles = [
        (34321, 22949),
        (34321, 22950),
        (34321, 22951),
    ]

    for x, y in tiles:
        source = Path(f"public/tiles/hybrid-golden_hour/16/{x}/{y}.webp")
        styled = Path(f"public/tiles/nano-cyberpunk-v2/16/{x}/{y}.webp")

        if not source.exists() or not styled.exists():
            print(f"Missing tile ({x}, {y})")
            continue

        src_img = load_image(source)
        sty_img = load_image(styled)

        # Side by side
        comparison = Image.new("RGB", (1024 + 20, 512 + 40), (40, 40, 40))
        comparison.paste(src_img, (5, 30))
        comparison.paste(sty_img, (512 + 15, 30))

        draw = ImageDraw.Draw(comparison)
        draw.text((5, 5), f"Tile ({x}, {y})", fill=(255, 255, 255))
        draw.text((5, 20), "Source", fill=(200, 200, 200))
        draw.text((512 + 15, 20), "Cyberpunk V2", fill=(200, 200, 200))

        out_path = output_dir / f"compare_{x}_{y}.png"
        comparison.save(out_path)
        print(f"Saved: {out_path}")

        # Check average color to detect styling
        sty_pixels = list(sty_img.getdata())
        avg_r = sum(p[0] for p in sty_pixels) / len(sty_pixels)
        avg_g = sum(p[1] for p in sty_pixels) / len(sty_pixels)
        avg_b = sum(p[2] for p in sty_pixels) / len(sty_pixels)
        print(f"  Avg color: R={avg_r:.0f}, G={avg_g:.0f}, B={avg_b:.0f}")

        # Cyberpunk should be dark with blue/purple tones
        is_dark = (avg_r + avg_g + avg_b) / 3 < 100
        is_blue_purple = avg_b > avg_g and avg_b > avg_r * 0.8
        print(f"  Dark: {is_dark}, Blue/Purple tones: {is_blue_purple}")

    print(f"\nOpen: open {output_dir}")

if __name__ == "__main__":
    main()
