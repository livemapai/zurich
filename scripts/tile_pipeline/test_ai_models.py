#!/usr/bin/env python3
"""
Test script for AI-powered tile relighting models.

This script allows testing and comparing different AI models for
satellite tile shadow neutralization and relighting.

Usage:
    # Check API availability and setup instructions
    python -m scripts.tile_pipeline.test_ai_models --setup

    # Test IC-Light on a sample tile
    python -m scripts.tile_pipeline.test_ai_models --model iclight --tile 16/34322/22950

    # Test Gemini on a sample tile
    python -m scripts.tile_pipeline.test_ai_models --model gemini --tile 16/34322/22950

    # Compare all available approaches side-by-side
    python -m scripts.tile_pipeline.test_ai_models --compare-all --output ai_test_output/

    # Test with different lighting presets
    python -m scripts.tile_pipeline.test_ai_models --model gemini --preset morning_golden

    # Test custom prompt
    python -m scripts.tile_pipeline.test_ai_models --model gemini --custom-prompt "Remove all shadows, even lighting"

Evaluation Criteria:
1. Are building edges still sharp and accurate?
2. Do shadows look natural or artificial?
3. Is the lighting consistent across the tile?
4. Are small details (cars, trees, roads) preserved?
5. Would it blend well with adjacent tiles?
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def load_test_tile(
    z: int = 16,
    x: int = 34322,
    y: int = 22950,
    cache_dir: Optional[Path] = None,
) -> np.ndarray:
    """Load a test satellite tile."""
    from scripts.tile_pipeline.sources.satellite import SatelliteSource
    from scripts.tile_pipeline.config import PipelineConfig

    config = PipelineConfig()
    cache_dir = cache_dir or config.cache_dir

    source = SatelliteSource(cache_dir=cache_dir)
    return source.fetch_and_resize(z, x, y, 512)


def compute_metrics(
    original: np.ndarray,
    processed: np.ndarray,
) -> dict:
    """Compute quality metrics between original and processed images.

    Args:
        original: Original RGB image
        processed: Processed RGB image

    Returns:
        Dictionary of metric names to values
    """
    from scipy import ndimage

    # Convert to float for calculations
    orig_f = original.astype(np.float32) / 255.0
    proc_f = processed.astype(np.float32) / 255.0

    # 1. Mean difference (how much the image changed)
    mean_diff = np.mean(np.abs(orig_f - proc_f))

    # 2. SSIM-like structural comparison (simplified)
    # Compare local means and variances
    window_size = 11

    def local_stats(img: np.ndarray) -> tuple:
        """Compute local mean and variance."""
        # Convert to grayscale
        gray = np.mean(img, axis=-1)
        mean = ndimage.uniform_filter(gray, size=window_size)
        sq_mean = ndimage.uniform_filter(gray ** 2, size=window_size)
        var = sq_mean - mean ** 2
        return mean, var

    orig_mean, orig_var = local_stats(orig_f)
    proc_mean, proc_var = local_stats(proc_f)

    # Structural similarity (simplified SSIM)
    c1, c2 = 0.01 ** 2, 0.03 ** 2
    ssim_map = ((2 * orig_mean * proc_mean + c1) * (2 * np.sqrt(orig_var * proc_var) + c2)) / \
               ((orig_mean ** 2 + proc_mean ** 2 + c1) * (orig_var + proc_var + c2))
    ssim = np.mean(ssim_map)

    # 3. Edge preservation (compare Sobel edges)
    def edge_magnitude(img: np.ndarray) -> np.ndarray:
        gray = np.mean(img, axis=-1)
        sx = ndimage.sobel(gray, axis=0)
        sy = ndimage.sobel(gray, axis=1)
        return np.sqrt(sx ** 2 + sy ** 2)

    orig_edges = edge_magnitude(orig_f)
    proc_edges = edge_magnitude(proc_f)

    # Edge correlation
    edge_corr = np.corrcoef(orig_edges.flatten(), proc_edges.flatten())[0, 1]

    # 4. Color shift (mean color change)
    orig_mean_color = np.mean(orig_f, axis=(0, 1))
    proc_mean_color = np.mean(proc_f, axis=(0, 1))
    color_shift = np.linalg.norm(proc_mean_color - orig_mean_color)

    # 5. Shadow coverage change
    def estimate_shadow_coverage(img: np.ndarray) -> float:
        """Estimate percentage of image in shadow."""
        gray = np.mean(img, axis=-1)
        return np.mean(gray < 0.35) * 100

    orig_shadow = estimate_shadow_coverage(orig_f)
    proc_shadow = estimate_shadow_coverage(proc_f)

    return {
        "mean_difference": mean_diff,
        "structural_similarity": ssim,
        "edge_preservation": edge_corr,
        "color_shift": color_shift,
        "original_shadow_pct": orig_shadow,
        "processed_shadow_pct": proc_shadow,
        "shadow_reduction_pct": orig_shadow - proc_shadow,
    }


def create_comparison_grid(
    images: list[tuple[str, np.ndarray]],
    output_path: Path,
    title: Optional[str] = None,
) -> None:
    """Create a labeled comparison grid of images.

    Args:
        images: List of (label, image) tuples
        output_path: Where to save the grid
        title: Optional title for the grid
    """
    if not images:
        return

    # Grid layout
    n = len(images)
    cols = min(3, n)
    rows = (n + cols - 1) // cols

    # Image dimensions
    h, w = images[0][1].shape[:2]
    label_height = 40
    title_height = 50 if title else 0
    padding = 10

    # Create canvas
    canvas_w = cols * w + (cols + 1) * padding
    canvas_h = rows * (h + label_height) + (rows + 1) * padding + title_height

    canvas = np.ones((canvas_h, canvas_w, 3), dtype=np.uint8) * 240  # Light gray

    # Convert to PIL for text drawing
    pil_canvas = Image.fromarray(canvas)
    draw = ImageDraw.Draw(pil_canvas)

    # Try to get a decent font
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except (IOError, OSError):
        font = ImageFont.load_default()
        title_font = font

    # Draw title
    if title:
        draw.text(
            (canvas_w // 2 - 100, 15),
            title,
            fill=(50, 50, 50),
            font=title_font,
        )

    # Place images and labels
    for i, (label, img) in enumerate(images):
        row = i // cols
        col = i % cols

        x = col * (w + padding) + padding
        y = row * (h + label_height + padding) + padding + title_height

        # Draw label background
        draw.rectangle(
            [x, y, x + w, y + label_height - 5],
            fill=(255, 255, 255),
        )
        draw.text(
            (x + 10, y + 10),
            label,
            fill=(30, 30, 30),
            font=font,
        )

        # Paste image
        pil_img = Image.fromarray(img)
        pil_canvas.paste(pil_img, (x, y + label_height))

    pil_canvas.save(output_path)


def test_single_model(
    model_name: str,
    tile: np.ndarray,
    preset: str,
    output_dir: Path,
    custom_prompt: Optional[str] = None,
) -> dict:
    """Test a single AI model on a tile.

    Args:
        model_name: "iclight" or "gemini"
        tile: Input satellite tile
        preset: Lighting preset name
        output_dir: Output directory
        custom_prompt: Optional custom prompt (overrides preset)

    Returns:
        Dictionary with results and metrics
    """
    from scripts.tile_pipeline.ai_relighter import (
        AIModel,
        get_relighter,
        LIGHTING_PRESETS,
        RelightingPrompt,
    )

    print(f"\n{'=' * 50}")
    print(f"Testing {model_name.upper()}")
    print('=' * 50)

    model = AIModel(model_name)

    try:
        relighter = get_relighter(model, cache_dir=output_dir / "cache")
    except ValueError as e:
        print(f"  ERROR: {e}")
        print(f"  Skipping {model_name}...")
        return {"error": str(e)}

    # Prepare prompt
    if custom_prompt:
        prompt = RelightingPrompt(
            lighting=custom_prompt,
            shadows="natural shadows",
            quality="photorealistic, preserve details",
        )
    else:
        prompt = LIGHTING_PRESETS[preset]

    print(f"  Preset: {preset}")
    print(f"  Prompt: {prompt.to_iclight_prompt() if model == AIModel.ICLIGHT else prompt.to_gemini_prompt()[:80]}...")

    # Run relighting
    print("  Processing...")
    try:
        result = relighter.relight(tile, prompt)
    except Exception as e:
        print(f"  ERROR during relighting: {e}")
        return {"error": str(e)}

    print(f"  Processing time: {result.processing_time_ms}ms")
    if result.cost_estimate:
        print(f"  Estimated cost: ${result.cost_estimate:.3f}")

    # Save result
    output_path = output_dir / f"{model_name}_{preset}.png"
    Image.fromarray(result.image).save(output_path)
    print(f"  Saved: {output_path}")

    # Compute metrics
    metrics = compute_metrics(tile, result.image)
    print(f"\n  Metrics:")
    print(f"    Mean difference: {metrics['mean_difference']:.4f}")
    print(f"    Structural similarity: {metrics['structural_similarity']:.4f}")
    print(f"    Edge preservation: {metrics['edge_preservation']:.4f}")
    print(f"    Color shift: {metrics['color_shift']:.4f}")
    print(f"    Shadow reduction: {metrics['shadow_reduction_pct']:.1f}%")

    return {
        "model": model_name,
        "preset": preset,
        "result": result,
        "metrics": metrics,
    }


def test_compare_all(
    tile: np.ndarray,
    output_dir: Path,
    z: int,
    x: int,
    y: int,
) -> None:
    """Compare all available approaches on the same tile.

    Includes:
    - Original satellite image
    - Algorithmic shadow neutralization (current approach)
    - IC-Light (if available)
    - Gemini (if available)
    """
    from scripts.tile_pipeline.ai_relighter import check_api_availability, LIGHTING_PRESETS
    from scripts.tile_pipeline.shadow_neutralizer import (
        neutralize_shadows,
        adaptive_shadow_removal,
        create_shadow_free_base,
    )

    print("\n" + "=" * 60)
    print("COMPREHENSIVE COMPARISON TEST")
    print("=" * 60)
    print(f"Tile: {z}/{x}/{y}")
    print(f"Output: {output_dir.absolute()}")

    availability = check_api_availability()
    print(f"\nAPI Availability:")
    print(f"  IC-Light (fal.ai): {'Yes' if availability['iclight'] else 'No'}")
    print(f"  Gemini (Google AI): {'Yes' if availability['gemini'] else 'No'}")

    results = []
    preset = "afternoon"

    # 1. Original
    print("\n--- Original ---")
    Image.fromarray(tile).save(output_dir / "00_original.png")
    results.append(("Original", tile))

    # 2. Algorithmic - Light
    print("\n--- Algorithmic (Light) ---")
    algo_light = neutralize_shadows(
        tile,
        target_shadow_level=0.40,
        temperature_correction=0.3,
        detail_enhancement=0.2,
        transition_softness=10.0,
    )
    Image.fromarray(algo_light).save(output_dir / "01_algo_light.png")
    results.append(("Algo: Light", algo_light))

    # 3. Algorithmic - Adaptive
    print("\n--- Algorithmic (Adaptive) ---")
    algo_adaptive = adaptive_shadow_removal(tile)
    Image.fromarray(algo_adaptive).save(output_dir / "02_algo_adaptive.png")
    results.append(("Algo: Adaptive", algo_adaptive))

    # 4. Algorithmic - Aggressive
    print("\n--- Algorithmic (Aggressive) ---")
    algo_aggressive = create_shadow_free_base(tile, aggressive=True)
    Image.fromarray(algo_aggressive).save(output_dir / "03_algo_aggressive.png")
    results.append(("Algo: Aggressive", algo_aggressive))

    # 5. IC-Light (if available)
    if availability["iclight"]:
        result = test_single_model("iclight", tile, preset, output_dir)
        if "result" in result:
            results.append(("IC-Light", result["result"].image))
    else:
        print("\n--- IC-Light: SKIPPED (no API key) ---")

    # 6. Gemini (if available)
    if availability["gemini"]:
        result = test_single_model("gemini", tile, preset, output_dir)
        if "result" in result:
            results.append(("Gemini", result["result"].image))
    else:
        print("\n--- Gemini: SKIPPED (no API key) ---")

    # Create comparison grid
    print("\n--- Creating Comparison Grid ---")
    create_comparison_grid(
        results,
        output_dir / "comparison_all_methods.png",
        title=f"Shadow Neutralization Comparison - {z}/{x}/{y}",
    )
    print(f"  Saved: {output_dir / 'comparison_all_methods.png'}")

    # Create metrics summary
    print("\n--- Metrics Summary ---")
    metrics_report = ["Method,Mean Diff,SSIM,Edge Pres,Color Shift,Shadow Reduction"]

    for name, img in results:
        if name == "Original":
            continue
        metrics = compute_metrics(tile, img)
        metrics_report.append(
            f"{name},"
            f"{metrics['mean_difference']:.4f},"
            f"{metrics['structural_similarity']:.4f},"
            f"{metrics['edge_preservation']:.4f},"
            f"{metrics['color_shift']:.4f},"
            f"{metrics['shadow_reduction_pct']:.1f}"
        )
        print(f"  {name}:")
        print(f"    Shadow reduction: {metrics['shadow_reduction_pct']:.1f}%")
        print(f"    Edge preservation: {metrics['edge_preservation']:.4f}")

    # Save metrics
    metrics_path = output_dir / "metrics_summary.csv"
    metrics_path.write_text("\n".join(metrics_report))
    print(f"\n  Metrics saved: {metrics_path}")

    print("\n" + "=" * 60)
    print("COMPARISON COMPLETE")
    print("=" * 60)
    print("\nKey files to review:")
    print(f"  - {output_dir / 'comparison_all_methods.png'}")
    print(f"  - {output_dir / 'metrics_summary.csv'}")


def test_multiple_tiles(
    tiles: list[tuple[int, int, int]],
    model_name: str,
    output_dir: Path,
    preset: str,
) -> None:
    """Test a model on multiple tiles for consistency check.

    Args:
        tiles: List of (z, x, y) tile coordinates
        model_name: Model to test
        output_dir: Output directory
        preset: Lighting preset
    """
    print("\n" + "=" * 60)
    print(f"MULTI-TILE CONSISTENCY TEST - {model_name.upper()}")
    print("=" * 60)

    results = []

    for z, x, y in tiles:
        print(f"\nLoading tile {z}/{x}/{y}...")
        try:
            tile = load_test_tile(z, x, y)
            result = test_single_model(model_name, tile, preset, output_dir / f"{z}_{x}_{y}")
            if "result" in result:
                results.append((f"{z}/{x}/{y}", result["result"].image))
                # Also save original for comparison
                Image.fromarray(tile).save(output_dir / f"{z}_{x}_{y}" / "original.png")
        except Exception as e:
            print(f"  Error loading tile: {e}")

    # Create multi-tile comparison
    if results:
        create_comparison_grid(
            results,
            output_dir / "multi_tile_comparison.png",
            title=f"{model_name.upper()} - Multiple Tiles",
        )
        print(f"\nMulti-tile comparison: {output_dir / 'multi_tile_comparison.png'}")


def main():
    parser = argparse.ArgumentParser(
        description="Test AI-powered tile relighting models"
    )
    parser.add_argument(
        "--setup", action="store_true",
        help="Show API setup instructions"
    )
    parser.add_argument(
        "--model", type=str, choices=["iclight", "gemini"],
        help="AI model to test"
    )
    parser.add_argument(
        "--compare-all", action="store_true",
        help="Compare all available methods"
    )
    parser.add_argument(
        "--tile", type=str, default="16/34322/22950",
        help="Tile coordinates as z/x/y (default: 16/34322/22950)"
    )
    parser.add_argument(
        "--preset", type=str, default="afternoon",
        choices=["morning_golden", "afternoon", "evening_golden", "overcast", "neutral"],
        help="Lighting preset (default: afternoon)"
    )
    parser.add_argument(
        "--custom-prompt", type=str,
        help="Custom prompt (overrides preset)"
    )
    parser.add_argument(
        "--multi-tile", action="store_true",
        help="Test on multiple tiles for consistency"
    )
    parser.add_argument(
        "--output", type=str, default="ai_test_output",
        help="Output directory (default: ai_test_output)"
    )

    args = parser.parse_args()

    # Parse tile coordinates
    z, x, y = map(int, args.tile.split("/"))
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.setup:
        from scripts.tile_pipeline.ai_relighter import print_setup_instructions
        print_setup_instructions()
        return

    if args.compare_all:
        print("Loading test tile...")
        tile = load_test_tile(z, x, y)
        test_compare_all(tile, output_dir, z, x, y)
        return

    if args.multi_tile:
        if not args.model:
            print("ERROR: --model required with --multi-tile")
            return
        # Test on multiple tiles around Zurich
        tiles = [
            (16, 34322, 22950),  # Downtown
            (16, 34323, 22951),  # Different area
            (16, 34321, 22949),  # More vegetation
        ]
        test_multiple_tiles(tiles, args.model, output_dir, args.preset)
        return

    if args.model:
        print("Loading test tile...")
        tile = load_test_tile(z, x, y)
        test_single_model(
            args.model,
            tile,
            args.preset,
            output_dir,
            args.custom_prompt,
        )
        return

    # Default: show help
    parser.print_help()
    print("\n\nQuick start:")
    print("  1. Run --setup to check API availability")
    print("  2. Run --compare-all to compare all methods")
    print("  3. Run --model gemini to test Gemini specifically")


if __name__ == "__main__":
    main()
