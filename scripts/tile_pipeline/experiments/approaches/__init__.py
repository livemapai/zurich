"""
Stitching approach implementations.

Each approach is a strategy for generating consistent styled tiles.
"""

from .base import BaseApproach, ApproachRegistry
from .individual import IndividualTiles, IndividualLowTemp
from .pre_stitch import PreStitch2x2, PreStitch3x3, PreStitchFullRow, PreStitchFullGrid
from .context_aware import LShapeContext, TwoPassReference, SlidingWindow2x2
from .post_process import IndividualEdgeBlend, IndividualStitcherPass
from .hybrid import PreStitchSeedExpand, OverlapFeatheredBlend

__all__ = [
    # Base
    "BaseApproach",
    "ApproachRegistry",
    # Category A: Individual
    "IndividualTiles",
    "IndividualLowTemp",
    # Category B: Pre-Stitch
    "PreStitch2x2",
    "PreStitch3x3",
    "PreStitchFullRow",
    "PreStitchFullGrid",
    # Category C: Context-Aware
    "LShapeContext",
    "TwoPassReference",
    "SlidingWindow2x2",
    # Category D: Post-Processing
    "IndividualEdgeBlend",
    "IndividualStitcherPass",
    # Category E: Hybrid
    "PreStitchSeedExpand",
    "OverlapFeatheredBlend",
]

# Registry of all approaches
APPROACHES = ApproachRegistry()
APPROACHES.register(1, "individual", IndividualTiles)
APPROACHES.register(2, "individual_low_temp", IndividualLowTemp)
APPROACHES.register(3, "pre_stitch_2x2", PreStitch2x2)
APPROACHES.register(4, "pre_stitch_3x3", PreStitch3x3)
APPROACHES.register(5, "pre_stitch_full_row", PreStitchFullRow)
APPROACHES.register(6, "pre_stitch_full_grid", PreStitchFullGrid)
APPROACHES.register(7, "l_shape_context", LShapeContext)
APPROACHES.register(8, "two_pass_reference", TwoPassReference)
APPROACHES.register(9, "sliding_window_2x2", SlidingWindow2x2)
APPROACHES.register(10, "individual_edge_blend", IndividualEdgeBlend)
APPROACHES.register(11, "individual_stitcher_pass", IndividualStitcherPass)
APPROACHES.register(12, "pre_stitch_seed_expand", PreStitchSeedExpand)
APPROACHES.register(13, "overlap_feathered_blend", OverlapFeatheredBlend)
