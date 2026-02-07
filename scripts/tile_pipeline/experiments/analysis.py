#!/usr/bin/env python3
"""
Seam Analysis and Comparison Tools.

Provides quantitative metrics for evaluating tile stitching quality.
"""

import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .utils import TileGrid, TILE_SIZE, stitch_full_grid


@dataclass
class SeamMetrics:
    """Metrics for a single seam (edge between two tiles)."""
    edge_type: str          # 'horizontal' or 'vertical'
    tile1_label: str
    tile2_label: str
    mean_diff: float        # Mean absolute difference at edge
    max_diff: float         # Maximum absolute difference
    std_diff: float         # Standard deviation of differences
    gradient_continuity: float  # How well gradients match across edge


@dataclass
class GridAnalysis:
    """Complete analysis of a tile grid."""
    seam_metrics: list[SeamMetrics]
    overall_score: float    # Lower is better
    horizontal_score: float # Score for horizontal edges
    vertical_score: float   # Score for vertical edges
    worst_seam: SeamMetrics # The seam with highest mean_diff


class SeamAnalyzer:
    """
    Analyzes seam quality between adjacent tiles.

    Seam quality is measured by:
    - Pixel difference at edges
    - Gradient continuity (do patterns continue across seams?)
    - Color consistency
    """

    def __init__(self, edge_width: int = 4):
        """
        Initialize analyzer.

        Args:
            edge_width: Number of pixels to analyze at each edge
        """
        self.edge_width = edge_width

    def analyze_grid(self, grid: TileGrid) -> GridAnalysis:
        """
        Analyze all seams in a tile grid.

        Returns GridAnalysis with detailed metrics.
        """
        metrics = []

        # Analyze horizontal seams (left-right adjacency)
        h_pairs = [
            ('A', 'B'), ('B', 'C'), ('C', 'D'),
            ('E', 'F'), ('F', 'G'), ('G', 'H'),
            ('I', 'J'), ('J', 'K'), ('K', 'L'),
        ]
        for left, right in h_pairs:
            m = self._analyze_horizontal_seam(grid, left, right)
            if m:
                metrics.append(m)

        # Analyze vertical seams (top-bottom adjacency)
        v_pairs = [
            ('A', 'E'), ('B', 'F'), ('C', 'G'), ('D', 'H'),
            ('E', 'I'), ('F', 'J'), ('G', 'K'), ('H', 'L'),
        ]
        for top, bottom in v_pairs:
            m = self._analyze_vertical_seam(grid, top, bottom)
            if m:
                metrics.append(m)

        if not metrics:
            return GridAnalysis(
                seam_metrics=[],
                overall_score=float('inf'),
                horizontal_score=float('inf'),
                vertical_score=float('inf'),
                worst_seam=None,
            )

        # Calculate aggregate scores
        h_scores = [m.mean_diff for m in metrics if m.edge_type == 'horizontal']
        v_scores = [m.mean_diff for m in metrics if m.edge_type == 'vertical']

        overall = np.mean([m.mean_diff for m in metrics])
        h_avg = np.mean(h_scores) if h_scores else 0
        v_avg = np.mean(v_scores) if v_scores else 0
        worst = max(metrics, key=lambda m: m.mean_diff)

        return GridAnalysis(
            seam_metrics=metrics,
            overall_score=overall,
            horizontal_score=h_avg,
            vertical_score=v_avg,
            worst_seam=worst,
        )

    def _analyze_horizontal_seam(self, grid: TileGrid,
                                  left_label: str, right_label: str) -> Optional[SeamMetrics]:
        """Analyze the seam between horizontally adjacent tiles."""
        left = grid.get(left_label)
        right = grid.get(right_label)

        if left is None or right is None:
            return None

        # Get edge strips
        left_arr = np.array(left, dtype=np.float32)
        right_arr = np.array(right, dtype=np.float32)

        # Right edge of left tile
        left_edge = left_arr[:, -self.edge_width:]
        # Left edge of right tile
        right_edge = right_arr[:, :self.edge_width]

        # Compute differences
        diff = np.abs(left_edge - right_edge)
        mean_diff = np.mean(diff)
        max_diff = np.max(diff)
        std_diff = np.std(diff)

        # Gradient continuity: compare gradients at the boundary
        left_gradient = np.gradient(left_arr, axis=1)[:, -1]
        right_gradient = np.gradient(right_arr, axis=1)[:, 0]
        gradient_continuity = np.mean(np.abs(left_gradient - right_gradient))

        return SeamMetrics(
            edge_type='horizontal',
            tile1_label=left_label,
            tile2_label=right_label,
            mean_diff=mean_diff,
            max_diff=max_diff,
            std_diff=std_diff,
            gradient_continuity=gradient_continuity,
        )

    def _analyze_vertical_seam(self, grid: TileGrid,
                                top_label: str, bottom_label: str) -> Optional[SeamMetrics]:
        """Analyze the seam between vertically adjacent tiles."""
        top = grid.get(top_label)
        bottom = grid.get(bottom_label)

        if top is None or bottom is None:
            return None

        # Get edge strips
        top_arr = np.array(top, dtype=np.float32)
        bottom_arr = np.array(bottom, dtype=np.float32)

        # Bottom edge of top tile
        top_edge = top_arr[-self.edge_width:, :]
        # Top edge of bottom tile
        bottom_edge = bottom_arr[:self.edge_width, :]

        # Compute differences
        diff = np.abs(top_edge - bottom_edge)
        mean_diff = np.mean(diff)
        max_diff = np.max(diff)
        std_diff = np.std(diff)

        # Gradient continuity
        top_gradient = np.gradient(top_arr, axis=0)[-1, :]
        bottom_gradient = np.gradient(bottom_arr, axis=0)[0, :]
        gradient_continuity = np.mean(np.abs(top_gradient - bottom_gradient))

        return SeamMetrics(
            edge_type='vertical',
            tile1_label=top_label,
            tile2_label=bottom_label,
            mean_diff=mean_diff,
            max_diff=max_diff,
            std_diff=std_diff,
            gradient_continuity=gradient_continuity,
        )


def generate_comparison_grid(results: list, output_path: Path):
    """
    Generate a side-by-side comparison image of all approaches.

    Args:
        results: List of ExperimentResult objects
        output_path: Path to save the comparison image
    """
    if not results:
        print("No results to compare")
        return

    # Filter results with tiles
    valid_results = [r for r in results if r.tiles and len(r.tiles) > 0]
    if not valid_results:
        print("No valid results to compare")
        return

    # Calculate grid dimensions
    # Each result gets a 2048x1536 cell (4x3 tiles) + label area
    label_height = 80
    cell_width = 2048 // 2   # Scale down by 2
    cell_height = 1536 // 2 + label_height

    # Arrange in 3 columns
    cols = 3
    rows = (len(valid_results) + cols - 1) // cols

    total_width = cols * cell_width
    total_height = rows * cell_height

    # Create comparison image
    comparison = Image.new("RGB", (total_width, total_height), (240, 240, 240))
    draw = ImageDraw.Draw(comparison)

    # Try to use a nice font, fall back to default
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        small_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except:
        font = ImageFont.load_default()
        small_font = font

    for i, result in enumerate(valid_results):
        row = i // cols
        col = i % cols
        x = col * cell_width
        y = row * cell_height

        # Draw stitched result
        if result.tiles:
            stitched = stitch_full_grid(result.tiles)
            # Scale down
            scaled = stitched.resize((cell_width, cell_height - label_height), Image.LANCZOS)
            comparison.paste(scaled, (x, y + label_height))

        # Draw label
        label = f"{result.approach_id}. {result.approach_name}"
        info = f"Time: {result.elapsed_seconds:.1f}s | API: {result.api_calls} | Score: {result.seam_score:.1f}"

        draw.rectangle([x, y, x + cell_width, y + label_height], fill=(50, 50, 50))
        draw.text((x + 10, y + 10), label, fill="white", font=font)
        draw.text((x + 10, y + 45), info, fill=(200, 200, 200), font=small_font)

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    comparison.save(output_path, "PNG")
    print(f"Saved comparison grid to: {output_path}")


def generate_seam_heatmap(grid: TileGrid, output_path: Path, edge_width: int = 32):
    """
    Generate a heatmap showing seam quality across the grid.

    Brighter areas = worse seams.
    """
    # Create full stitched image
    stitched = stitch_full_grid(grid)
    arr = np.array(stitched, dtype=np.float32)

    # Create heatmap
    height, width = arr.shape[:2]
    heatmap = np.zeros((height, width), dtype=np.float32)

    # Mark horizontal seams
    for col in range(1, 4):  # Between columns 0-1, 1-2, 2-3
        x = col * TILE_SIZE
        # Calculate difference between left and right of seam
        left = arr[:, x - edge_width:x]
        right = arr[:, x:x + edge_width]
        diff = np.mean(np.abs(left - right), axis=(1, 2))
        # Paint seam area
        for dy in range(-edge_width, edge_width):
            heatmap[:, x + dy] = diff

    # Mark vertical seams
    for row in range(1, 3):  # Between rows 0-1, 1-2
        y = row * TILE_SIZE
        top = arr[y - edge_width:y, :]
        bottom = arr[y:y + edge_width, :]
        diff = np.mean(np.abs(top - bottom), axis=(0, 2))
        for dx in range(-edge_width, edge_width):
            heatmap[y + dx, :] = diff

    # Normalize and colorize
    heatmap = (heatmap / heatmap.max() * 255).astype(np.uint8)

    # Apply colormap (red = bad, blue = good)
    from PIL import ImageOps
    heatmap_img = Image.fromarray(heatmap)
    heatmap_colored = ImageOps.colorize(heatmap_img, "blue", "red")

    # Composite with original (50% blend)
    stitched_rgb = stitched.convert("RGB")
    composite = Image.blend(stitched_rgb, heatmap_colored, 0.4)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    composite.save(output_path, "PNG")
    print(f"Saved seam heatmap to: {output_path}")
