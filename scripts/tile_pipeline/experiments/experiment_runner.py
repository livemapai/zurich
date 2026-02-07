#!/usr/bin/env python3
"""
Comprehensive Tile Stitching Experiment Runner.

Tests multiple stitching approaches systematically and logs results.

Usage:
    python -m scripts.tile_pipeline.experiments.experiment_runner \\
        --source scripts/tile_pipeline/assets/stitching_tests/raw \\
        --prompt "architectural pencil sketch" \\
        --approaches 1,3,7

    # Run all approaches
    python -m scripts.tile_pipeline.experiments.experiment_runner \\
        --source scripts/tile_pipeline/assets/stitching_tests/raw \\
        --prompt "architectural pencil sketch" \\
        --all
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .utils import TileGrid, load_tile_grid, save_tile_grid, stitch_full_grid, save_image
from .analysis import SeamAnalyzer, generate_comparison_grid, generate_seam_heatmap
from .approaches import APPROACHES
from .approaches.base import BaseApproach


class ExperimentRunner:
    """
    Orchestrates tile stitching experiments across multiple approaches.
    """

    def __init__(
        self,
        source_dir: Path,
        user_prompt: str,
        output_dir: Optional[Path] = None,
        temperature: float = 0.3,
        api_key: Optional[str] = None,
    ):
        self.source_dir = Path(source_dir)
        self.user_prompt = user_prompt
        self.output_dir = output_dir or Path("scripts/tile_pipeline/experiments")
        self.temperature = temperature
        self.api_key = api_key

        self.analyzer = SeamAnalyzer()
        self.results = []

    def load_source_tiles(self) -> TileGrid:
        """Load source tiles from directory."""
        print(f"\n📦 Loading source tiles from: {self.source_dir}")
        grid = load_tile_grid(self.source_dir)
        print(f"   Found {len(grid)} tiles: {', '.join(sorted(grid.labels))}")
        return grid

    def run_approach(self, approach_id: int, source_grid: TileGrid) -> dict:
        """Run a single approach and return results."""
        approach_cls = APPROACHES.get(approach_id)
        if approach_cls is None:
            print(f"❌ Unknown approach ID: {approach_id}")
            return None

        # Create output directory for this approach
        approach_dir = self.output_dir / f"approach_{approach_id:02d}_{approach_cls.approach_name}"

        # Instantiate and run approach
        approach = approach_cls(
            user_prompt=self.user_prompt,
            temperature=self.temperature,
            api_key=self.api_key,
        )

        result = approach.execute(source_grid, approach_dir)

        # Analyze seams
        if result.tiles and len(result.tiles) > 0:
            analysis = self.analyzer.analyze_grid(result.tiles)
            result.seam_score = float(analysis.overall_score)

            # Generate seam heatmap
            heatmap_path = approach_dir / "seam_heatmap.png"
            try:
                generate_seam_heatmap(result.tiles, heatmap_path)
            except Exception as e:
                print(f"  Warning: Could not generate heatmap: {e}")

            # Save analysis
            analysis_path = approach_dir / "analysis.json"
            self._save_analysis(analysis_path, result, analysis)

        self.results.append(result)
        return result

    def run_approaches(self, approach_ids: list[int], source_grid: TileGrid):
        """Run multiple approaches."""
        print(f"\n🚀 Running {len(approach_ids)} approaches...")

        for i, aid in enumerate(approach_ids, 1):
            print(f"\n{'━' * 60}")
            print(f"  Approach {i}/{len(approach_ids)}")
            print(f"{'━' * 60}")

            try:
                self.run_approach(aid, source_grid)
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted by user")
                break
            except Exception as e:
                print(f"\n❌ Error running approach {aid}: {e}")
                continue

    def run_all(self, source_grid: TileGrid):
        """Run all registered approaches."""
        all_ids = [aid for aid, _, _ in APPROACHES]
        self.run_approaches(all_ids, source_grid)

    def generate_comparison(self):
        """Generate comparison outputs."""
        if not self.results:
            print("No results to compare")
            return

        comparison_dir = self.output_dir / "comparison"
        comparison_dir.mkdir(parents=True, exist_ok=True)

        # Generate side-by-side comparison
        print("\n📊 Generating comparison grid...")
        generate_comparison_grid(
            self.results,
            comparison_dir / "side_by_side.png"
        )

        # Generate rankings
        print("\n📝 Generating rankings...")
        self._generate_rankings(comparison_dir / "rankings.md")

        # Save full results JSON
        self._save_results_json(comparison_dir / "results.json")

    def _save_analysis(self, path: Path, result, analysis):
        """Save analysis results to JSON."""
        data = {
            "approach_id": result.approach_id,
            "approach_name": result.approach_name,
            "elapsed_seconds": float(result.elapsed_seconds),
            "api_calls": result.api_calls,
            "tiles_generated": len(result.tiles) if result.tiles else 0,
            "seam_analysis": {
                "overall_score": float(analysis.overall_score),
                "horizontal_score": float(analysis.horizontal_score),
                "vertical_score": float(analysis.vertical_score),
                "worst_seam": {
                    "tiles": f"{analysis.worst_seam.tile1_label}-{analysis.worst_seam.tile2_label}",
                    "type": analysis.worst_seam.edge_type,
                    "mean_diff": float(analysis.worst_seam.mean_diff),
                } if analysis.worst_seam else None,
            }
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def _generate_rankings(self, path: Path):
        """Generate markdown rankings file."""
        sorted_results = sorted(self.results, key=lambda r: r.seam_score)

        lines = [
            "# Approach Rankings",
            "",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## By Seam Quality (Lower = Better)",
            "",
            "| Rank | Approach | Seam Score | Time | API Calls |",
            "|------|----------|------------|------|-----------|",
        ]

        for i, result in enumerate(sorted_results, 1):
            medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else "  "))
            lines.append(
                f"| {medal} {i} | {result.approach_name} | "
                f"{result.seam_score:.2f} | {result.elapsed_seconds:.1f}s | {result.api_calls} |"
            )

        lines.extend([
            "",
            "## By Cost Efficiency (API Calls)",
            "",
            "| Rank | Approach | API Calls | Seam Score |",
            "|------|----------|-----------|------------|",
        ])

        by_cost = sorted(self.results, key=lambda r: r.api_calls)
        for i, result in enumerate(by_cost, 1):
            lines.append(
                f"| {i} | {result.approach_name} | "
                f"{result.api_calls} | {result.seam_score:.2f} |"
            )

        lines.extend([
            "",
            "## Recommendations",
            "",
            "Based on the results:",
            "",
        ])

        if sorted_results:
            best = sorted_results[0]
            lines.append(f"- **Best Quality**: {best.approach_name} (score: {best.seam_score:.2f})")

        if by_cost:
            cheapest = by_cost[0]
            lines.append(f"- **Most Efficient**: {cheapest.approach_name} ({cheapest.api_calls} calls)")

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write("\n".join(lines))

        print(f"   Saved rankings to: {path}")

    def _save_results_json(self, path: Path):
        """Save all results to JSON."""
        data = {
            "experiment": {
                "timestamp": datetime.now().isoformat(),
                "source_dir": str(self.source_dir),
                "prompt": self.user_prompt,
                "temperature": self.temperature,
            },
            "results": [
                {
                    "approach_id": r.approach_id,
                    "approach_name": r.approach_name,
                    "elapsed_seconds": r.elapsed_seconds,
                    "api_calls": r.api_calls,
                    "seam_score": r.seam_score,
                    "tiles_generated": len(r.tiles) if r.tiles else 0,
                }
                for r in self.results
            ],
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        print(f"   Saved results JSON to: {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Run tile stitching experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run specific approaches
  python -m scripts.tile_pipeline.experiments.experiment_runner \\
      --source scripts/tile_pipeline/assets/stitching_tests/raw \\
      --prompt "architectural pencil sketch" \\
      --approaches 1,3,7

  # Run all approaches
  python -m scripts.tile_pipeline.experiments.experiment_runner \\
      --source scripts/tile_pipeline/assets/stitching_tests/raw \\
      --prompt "architectural pencil sketch" \\
      --all

  # List available approaches
  python -m scripts.tile_pipeline.experiments.experiment_runner --list
        """,
    )

    parser.add_argument(
        "--source", "-s",
        type=Path,
        help="Directory containing source tiles (A-L)",
    )
    parser.add_argument(
        "--prompt", "-p",
        type=str,
        help="Style prompt for tile generation",
    )
    parser.add_argument(
        "--approaches", "-a",
        type=str,
        help="Comma-separated list of approach IDs to run (e.g., 1,3,7)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all approaches",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("scripts/tile_pipeline/experiments"),
        help="Output directory for results",
    )
    parser.add_argument(
        "--temperature", "-t",
        type=float,
        default=0.3,
        help="Generation temperature (0.0-1.0)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="API key (or set GOOGLE_API_KEY env var)",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available approaches and exit",
    )

    args = parser.parse_args()

    # List approaches
    if args.list:
        print("\n📋 Available Approaches:")
        print("=" * 60)
        for aid, name, cls in APPROACHES:
            print(f"  {aid:2d}. {name:30s} - {cls.description}")
        print("=" * 60)
        return

    # Validate required args
    if not args.source:
        print("Error: --source is required", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    if not args.prompt:
        print("Error: --prompt is required", file=sys.stderr)
        sys.exit(1)

    if not args.source.exists():
        print(f"Error: Source directory not found: {args.source}", file=sys.stderr)
        sys.exit(1)

    # Parse approach IDs
    if args.all:
        approach_ids = [aid for aid, _, _ in APPROACHES]
    elif args.approaches:
        try:
            approach_ids = [int(x.strip()) for x in args.approaches.split(",")]
        except ValueError:
            print("Error: Invalid approach IDs. Use comma-separated integers.", file=sys.stderr)
            sys.exit(1)
    else:
        print("Error: Specify --approaches or --all", file=sys.stderr)
        sys.exit(1)

    # Run experiments
    print("\n" + "═" * 60)
    print("  🧪 Tile Stitching Experiment Runner")
    print("═" * 60)
    print(f"  Source:      {args.source}")
    print(f"  Prompt:      {args.prompt[:50]}{'...' if len(args.prompt) > 50 else ''}")
    print(f"  Temperature: {args.temperature}")
    print(f"  Approaches:  {approach_ids}")
    print(f"  Output:      {args.output}")
    print("═" * 60)

    runner = ExperimentRunner(
        source_dir=args.source,
        user_prompt=args.prompt,
        output_dir=args.output,
        temperature=args.temperature,
        api_key=args.api_key,
    )

    # Load source tiles
    source_grid = runner.load_source_tiles()

    if len(source_grid) == 0:
        print("❌ No source tiles found", file=sys.stderr)
        sys.exit(1)

    # Run approaches
    start_time = time.time()
    runner.run_approaches(approach_ids, source_grid)
    total_time = time.time() - start_time

    # Generate comparison
    runner.generate_comparison()

    # Summary
    print("\n" + "═" * 60)
    print("  ✅ Experiment Complete")
    print("═" * 60)
    print(f"  Total time:     {total_time:.1f}s")
    print(f"  Approaches run: {len(runner.results)}")
    print(f"  Results at:     {args.output}")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
