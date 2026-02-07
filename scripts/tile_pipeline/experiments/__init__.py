"""
Comprehensive Tile Stitching Experimentation Framework.

This package provides a systematic way to test and compare different
tile stitching approaches for AI-powered map styling.

12 Approaches to Test:
  Category A (Baseline):
    1. Individual Tiles
    2. Individual + Low Temperature

  Category B (Pre-Stitch):
    3. Pre-Stitch 2×2
    4. Pre-Stitch 3×3
    5. Pre-Stitch Full Row
    6. Pre-Stitch Full Grid

  Category C (Context-Aware):
    7. L-Shape Context (v1)
    8. Two-Pass + Reference (v2)
    9. Sliding Window 2×2

  Category D (Post-Processing):
    10. Individual + Edge Blend
    11. Individual + Stitcher Pass

  Category E (Hybrid):
    12. Pre-Stitch Seed + Expand

Usage:
    from experiments import ExperimentRunner
    runner = ExperimentRunner(source_dir, prompt)
    runner.run_all()
"""

from .experiment_runner import ExperimentRunner
from .analysis import SeamAnalyzer, generate_comparison_grid

__all__ = [
    "ExperimentRunner",
    "SeamAnalyzer",
    "generate_comparison_grid",
]
