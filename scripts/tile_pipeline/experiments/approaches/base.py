#!/usr/bin/env python3
"""
Base class for tile stitching approaches.

All approaches inherit from BaseApproach and implement the `run` method.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Type

from ..utils import TileGrid, ExperimentResult, save_tile_grid, stitch_full_grid, save_image


# Base system prompt for all styling
BASE_PROMPT = """You are a cinematic map tile artist styling urban scenes from a STRAIGHT-DOWN TOP VIEW.

CAMERA: 90° nadir view - looking STRAIGHT DOWN. NOT isometric. Think Google Maps satellite.

SCENE ELEMENTS (from above):
- BUILDINGS: Flat rooftop shapes (rectangles, L-shapes). You see ROOFS, not walls.
- TREES: Round/fluffy circles - tree canopies from above.
- STREETS: Flat gray/brown strips between buildings.
- GRASS/PARKS: Flat green areas.

CRITICAL:
1. PRESERVE GEOMETRY - All shapes/positions stay EXACTLY the same.
2. KEEP TOP-DOWN VIEW - No perspective, no tilt, no isometric angle.
3. NO TEXT/LABELS - No watermarks or UI elements."""


class BaseApproach(ABC):
    """
    Abstract base class for tile stitching approaches.

    Subclasses must implement the `run` method which takes raw tiles
    and returns styled tiles.
    """

    # Class attributes set by subclasses
    approach_id: int = 0
    approach_name: str = "base"
    description: str = "Base approach (not implemented)"
    category: str = "unknown"

    def __init__(
        self,
        user_prompt: str,
        temperature: float = 0.3,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the approach.

        Args:
            user_prompt: The style prompt (e.g., "architectural pencil sketch")
            temperature: Generation temperature (0.0-1.0)
            api_key: Optional API key (uses GOOGLE_API_KEY env var if not provided)
        """
        self.user_prompt = user_prompt
        self.temperature = temperature
        self.api_key = api_key
        self.api_calls = 0

    @abstractmethod
    def run(self, source_grid: TileGrid) -> TileGrid:
        """
        Run the approach on source tiles.

        Args:
            source_grid: TileGrid containing raw source tiles (A-L)

        Returns:
            TileGrid containing styled tiles
        """
        pass

    def execute(
        self,
        source_grid: TileGrid,
        output_dir: Optional[Path] = None,
    ) -> ExperimentResult:
        """
        Execute the approach and measure performance.

        Args:
            source_grid: TileGrid containing raw source tiles
            output_dir: Optional directory to save results

        Returns:
            ExperimentResult with timing and metrics
        """
        print(f"\n{'═' * 60}")
        print(f"Approach {self.approach_id}: {self.approach_name}")
        print(f"Category: {self.category}")
        print(f"Description: {self.description}")
        print(f"Temperature: {self.temperature}")
        print(f"{'═' * 60}")

        self.api_calls = 0
        start_time = time.time()

        try:
            result_grid = self.run(source_grid)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            result_grid = TileGrid()

        elapsed = time.time() - start_time

        # Save results if output directory provided
        if output_dir and result_grid.tiles:
            output_dir.mkdir(parents=True, exist_ok=True)

            # Save individual tiles
            tiles_dir = output_dir / "output"
            save_tile_grid(result_grid, tiles_dir)

            # Save stitched result
            stitched = stitch_full_grid(result_grid)
            save_image(stitched, output_dir / "stitched_result.png")

            print(f"\n  Saved to: {output_dir}")

        print(f"\n{'─' * 60}")
        print(f"  Time: {elapsed:.1f}s")
        print(f"  API calls: {self.api_calls}")
        print(f"  Tiles generated: {len(result_grid)}")
        print(f"{'─' * 60}\n")

        return ExperimentResult(
            approach_id=self.approach_id,
            approach_name=self.approach_name,
            tiles=result_grid,
            elapsed_seconds=elapsed,
            api_calls=self.api_calls,
        )

    def build_prompt(self, context: str = "") -> str:
        """
        Build the full prompt for API calls.

        Args:
            context: Additional context about what's being styled

        Returns:
            Full prompt string
        """
        prompt = BASE_PROMPT

        if context:
            prompt += f"\n\n{context}"

        prompt += f"\n\nStyle: {self.user_prompt}"
        prompt += "\n\nReturn the styled image."

        return prompt


class ApproachRegistry:
    """Registry of all available approaches."""

    def __init__(self):
        self._approaches: dict[int, tuple[str, Type[BaseApproach]]] = {}

    def register(self, approach_id: int, name: str, cls: Type[BaseApproach]):
        """Register an approach."""
        self._approaches[approach_id] = (name, cls)
        cls.approach_id = approach_id
        cls.approach_name = name

    def get(self, approach_id: int) -> Optional[Type[BaseApproach]]:
        """Get approach class by ID."""
        if approach_id in self._approaches:
            return self._approaches[approach_id][1]
        return None

    def get_by_name(self, name: str) -> Optional[Type[BaseApproach]]:
        """Get approach class by name."""
        for aid, (aname, cls) in self._approaches.items():
            if aname == name:
                return cls
        return None

    def list_all(self) -> list[tuple[int, str, Type[BaseApproach]]]:
        """List all registered approaches."""
        return [(aid, name, cls) for aid, (name, cls) in sorted(self._approaches.items())]

    def __iter__(self):
        for aid, (name, cls) in sorted(self._approaches.items()):
            yield aid, name, cls
