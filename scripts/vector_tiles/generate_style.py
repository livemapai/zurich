#!/usr/bin/env python3
"""
MapLibre Style Generator for Zurich Vector Tiles

Generates a hand-drawn/pencil sketch style with:
- Stacked outlines for sketchy building edges
- Irregular dash patterns for pencil strokes
- Parchment paper background
- Soft layered shadows
- Sepia/monochromatic color palette
"""

import json
from pathlib import Path
from typing import Any, Dict, List

# Hand-drawn pencil color palette (sepia/monochromatic)
COLORS = {
    # Paper background (warm parchment)
    "background": "#f8f4e8",
    "paper_texture": "#f5f0e0",

    # Pencil strokes (graphite tones)
    "pencil_dark": "#2a2520",
    "pencil_medium": "#4a4540",
    "pencil_light": "#6a6560",
    "pencil_faint": "#8a8580",

    # Building fills (subtle warm tones)
    "building_fill": "#ece6d8",
    "building_residential": "#f0e8d8",
    "building_commercial": "#e8e4dc",
    "building_industrial": "#e0dcd4",
    "building_public": "#e8e0d0",

    # Shadows (soft graphite)
    "shadow_dark": "#3a3530",
    "shadow_medium": "#5a5550",
    "shadow_light": "#7a7570",

    # Roofs (terracotta and slate pencil shades)
    "roof_warm": "#8a6a5a",
    "roof_cool": "#6a6a6a",
    "roof_default": "#7a7068",

    # Water (light blue-gray wash)
    "water_fill": "#d8e4ec",
    "water_stroke": "#98a8b8",

    # Trees (soft green-gray)
    "tree_fill": "#889888",
    "tree_stroke": "#687868",

    # Streets (paper showing through)
    "street_fill": "#f5f0e4",
    "street_stroke": "#9a9590",

    # Labels
    "label_text": "#3a3028",
    "label_halo": "#f8f4e8",
}


# =============================================================================
# PENCIL STYLE PRESETS
# =============================================================================
# Predefined combinations of patterns and dash arrays for different looks.
#
# Available patterns (24 total in sprite sheet):
#   Procedural: pencil-line-thin, pencil-line-medium, pencil-line-thick,
#               paper-texture, hatching-45, crosshatch, stipple, water-ripple
#   External:   dash-medium, dash-short, line-medium-2, line-medium-3,
#               line-solid, line-solid-thick, line-thick-grainy, line-thin-2,
#               line-thin-3, line-very-heavy, symbol-arrow, symbol-cross,
#               symbol-x, zigzag-bold, zigzag-fine, zigzag-medium
# =============================================================================

STYLE_PRESETS = {
    # -------------------------------------------------------------------------
    # Sketchy - Loose, hand-drawn appearance with patterns
    # -------------------------------------------------------------------------
    "sketchy": {
        "name": "Sketchy",
        "description": "Loose, hand-drawn appearance with pencil textures",
        "patterns": {
            "water_edge": "pencil-line-medium",
            "water_surface": "water-ripple",
            "building_outline": None,  # Use stacked dasharrays (patterns don't work on lines)
            "building_texture": "stipple",
            "building_shadow": "crosshatch",
            "roof_shading": "hatching-45",
            "roof_outline": None,
            "street_edge_left": "pencil-line-thin",
            "street_edge_right": "pencil-line-thin",
            "footway": None,
            "railway_ties": None,
        },
        "dashes": {
            # Increased dash segments for visibility: was [4, 2, 1, 2], now [6, 3, 2, 3]
            "building_outline": [6, 3, 2, 3],  # Irregular dash for pencil overrun
            "footway": [1, 3],
            "railway_ties": [0.5, 2],
            "roof_outline": [3, 2, 1, 2],
        },
    },

    # -------------------------------------------------------------------------
    # Technical - Clean architectural drawing style
    # -------------------------------------------------------------------------
    "technical": {
        "name": "Technical",
        "description": "Clean architectural drawing with precise lines",
        "patterns": {
            "water_edge": "line-solid",
            "water_surface": None,
            "building_outline": None,
            "building_texture": None,
            "building_shadow": "hatching-45",
            "roof_shading": "hatching-45",
            "roof_outline": None,
            "street_edge_left": None,
            "street_edge_right": None,
            "footway": None,
            "railway_ties": None,
        },
        "dashes": {
            "building_outline": None,  # Solid lines
            "street_edge_left": None,
            "street_edge_right": None,
            "footway": [2, 4],
            "railway_ties": [1, 3],
            "roof_outline": None,
        },
    },

    # -------------------------------------------------------------------------
    # Artistic - Bold, expressive strokes with heavy patterns
    # -------------------------------------------------------------------------
    "artistic": {
        "name": "Artistic",
        "description": "Bold, expressive strokes with heavy textures",
        "patterns": {
            "water_edge": "line-very-heavy",
            "water_surface": "zigzag-fine",
            "building_outline": None,  # Use thick solid lines (patterns don't work on lines)
            "building_texture": "crosshatch",
            "building_shadow": "crosshatch",
            "roof_shading": "crosshatch",
            "roof_outline": None,
            "street_edge_left": "pencil-line-thick",
            "street_edge_right": "pencil-line-thick",
            "footway": None,
            "railway_ties": None,
        },
        "dashes": {
            "building_outline": None,  # Solid thick lines for bold artistic look
            "footway": [2, 2],
            "railway_ties": [1, 2],
            "roof_outline": [5, 2, 2, 2],
        },
    },

    # -------------------------------------------------------------------------
    # Minimal - Subtle lines, minimal textures
    # -------------------------------------------------------------------------
    "minimal": {
        "name": "Minimal",
        "description": "Subtle lines with minimal textures",
        "patterns": {
            "water_edge": "pencil-line-thin",
            "water_surface": None,
            "building_outline": None,
            "building_texture": None,
            "building_shadow": None,
            "roof_shading": None,
            "roof_outline": None,
            "street_edge_left": None,
            "street_edge_right": None,
            "footway": None,
            "railway_ties": None,
        },
        "dashes": {
            "building_outline": [8, 4],
            "street_edge_left": [10, 5],
            "street_edge_right": [10, 5],
            "footway": [1, 4],
            "railway_ties": [0.5, 3],
            "roof_outline": [6, 3],
        },
    },

    # -------------------------------------------------------------------------
    # Zigzag - Playful wavy lines throughout
    # -------------------------------------------------------------------------
    "zigzag": {
        "name": "Zigzag",
        "description": "Playful wavy lines for a whimsical look",
        "patterns": {
            "water_edge": "zigzag-medium",
            "water_surface": "water-ripple",
            "building_outline": None,  # Use stacked dasharrays (patterns don't work on lines)
            "building_texture": "stipple",
            "building_shadow": "hatching-45",
            "roof_shading": "hatching-45",
            "roof_outline": None,
            "street_edge_left": "zigzag-fine",
            "street_edge_right": "zigzag-fine",
            "footway": None,
            "railway_ties": None,
        },
        "dashes": {
            "building_outline": [3, 1, 1, 1, 2, 1],  # Playful irregular dash
            "footway": [1, 2, 1, 3],
            "railway_ties": [0.5, 1.5],
            "roof_outline": [2, 1, 1, 2],
        },
    },
}

# Active preset (change this to switch styles, or use --preset flag)
ACTIVE_PRESET = "sketchy"


def get_active_preset() -> dict:
    """Get the currently active style preset."""
    return STYLE_PRESETS.get(ACTIVE_PRESET, STYLE_PRESETS["sketchy"])


# =============================================================================
# PENCIL PATTERN CONFIGURATION (derived from active preset)
# =============================================================================

def _build_config_from_preset():
    """Build PENCIL_CONFIG and DASH_CONFIG from active preset."""
    preset = get_active_preset()
    return preset["patterns"], preset["dashes"]


PENCIL_CONFIG, DASH_CONFIG = _build_config_from_preset()


def get_pattern(feature_type: str) -> str | None:
    """Get the pattern name for a feature type, or None for solid/dash."""
    return PENCIL_CONFIG.get(feature_type)


def get_dasharray(feature_type: str) -> list[float] | None:
    """Get the dash array for a feature type, or None for solid line."""
    return DASH_CONFIG.get(feature_type)


def create_source_definition() -> Dict[str, Any]:
    """Create the PMTiles source definition."""
    return {
        "zurich": {
            "type": "vector",
            "url": "pmtiles://zurich-vector.pmtiles",
            "attribution": "&copy; Stadt Zürich (Open Data), swisstopo"
        }
    }


def create_background_layers() -> List[Dict[str, Any]]:
    """Create parchment paper background with texture overlay."""
    return [
        # Base background color
        {
            "id": "background",
            "type": "background",
            "paint": {
                "background-color": COLORS["background"]
            }
        }
        # Note: Background pattern would require a fill layer with geometry
        # MapLibre background type doesn't support fill-pattern
    ]


def create_water_layers() -> List[Dict[str, Any]]:
    """Create water with hand-drawn wash effect using sprite patterns."""
    layers = []

    # Water fill (light wash)
    layers.append({
        "id": "water-fill",
        "type": "fill",
        "source": "zurich",
        "source-layer": "water",
        "paint": {
            "fill-color": COLORS["water_fill"],
            "fill-opacity": 0.7
        }
    })

    # Water surface pattern overlay (uses sprite if configured)
    surface_pattern = get_pattern("water_surface")
    if surface_pattern:
        layers.append({
            "id": "water-pattern",
            "type": "fill",
            "source": "zurich",
            "source-layer": "water",
            "minzoom": 14,
            "paint": {
                "fill-pattern": surface_pattern,
                "fill-opacity": 0.3
            }
        })

    # Water edge - pencil line pattern or solid line
    edge_pattern = get_pattern("water_edge")
    if edge_pattern:
        layers.append({
            "id": "water-edge-1",
            "type": "line",
            "source": "zurich",
            "source-layer": "water",
            "paint": {
                "line-pattern": edge_pattern,
                "line-width": 12,
                "line-opacity": 0.6
            }
        })
    else:
        # Fallback: solid sketchy line with optional dasharray
        paint: Dict[str, Any] = {
            "line-color": COLORS["water_stroke"],
            "line-width": 2,
            "line-opacity": 0.7
        }
        dasharray = get_dasharray("water_edge")
        if dasharray:
            paint["line-dasharray"] = dasharray
        layers.append({
            "id": "water-edge-1",
            "type": "line",
            "source": "zurich",
            "source-layer": "water",
            "paint": paint
        })

    # Water edge - solid sketchy backup (secondary stroke for depth)
    layers.append({
        "id": "water-edge-2",
        "type": "line",
        "source": "zurich",
        "source-layer": "water",
        "paint": {
            "line-color": COLORS["water_stroke"],
            "line-width": 1,
            "line-opacity": 0.4,
            "line-offset": 2
        }
    })

    return layers


def create_building_layers() -> List[Dict[str, Any]]:
    """Create buildings with stacked sketch outlines and hatching patterns."""
    layers = []

    # Shadow layer 1 (furthest, lightest)
    layers.append({
        "id": "building-shadow-3",
        "type": "fill",
        "source": "zurich",
        "source-layer": "building_shadows",
        "minzoom": 14,
        "paint": {
            "fill-color": COLORS["shadow_light"],
            "fill-opacity": 0.08,
            "fill-translate": [1, 1]
        }
    })

    # Shadow layer 2
    layers.append({
        "id": "building-shadow-2",
        "type": "fill",
        "source": "zurich",
        "source-layer": "building_shadows",
        "minzoom": 14,
        "paint": {
            "fill-color": COLORS["shadow_medium"],
            "fill-opacity": 0.1,
        }
    })

    # Shadow layer 3 (closest, darkest)
    layers.append({
        "id": "building-shadow-1",
        "type": "fill",
        "source": "zurich",
        "source-layer": "building_shadows",
        "minzoom": 15,
        "paint": {
            "fill-color": COLORS["shadow_dark"],
            "fill-opacity": 0.12,
            "fill-translate": [-1, -1]
        }
    })

    # Shadow hatching pattern (configurable crosshatch for pencil shading)
    shadow_pattern = get_pattern("building_shadow")
    if shadow_pattern:
        layers.append({
            "id": "building-shadow-hatching",
            "type": "fill",
            "source": "zurich",
            "source-layer": "building_shadows",
            "minzoom": 16,
            "paint": {
                "fill-pattern": shadow_pattern,
                "fill-opacity": 0.15
            }
        })

    # Building fill
    layers.append({
        "id": "building-fill",
        "type": "fill",
        "source": "zurich",
        "source-layer": "buildings",
        "minzoom": 12,
        "paint": {
            "fill-color": [
                "match",
                ["get", "art"],
                "Gebaeude_Wohnen", COLORS["building_residential"],
                "Wohngebaeude", COLORS["building_residential"],
                "Gebaeude_Industrie", COLORS["building_industrial"],
                "Industriegebaeude", COLORS["building_industrial"],
                "Gebaeude_Gewerbe", COLORS["building_commercial"],
                "Gewerbegebaeude", COLORS["building_commercial"],
                "Gebaeude_oeffentlich", COLORS["building_public"],
                COLORS["building_fill"]
            ],
            "fill-opacity": 0.95
        }
    })

    # Building texture overlay (configurable stipple for paper grain effect)
    texture_pattern = get_pattern("building_texture")
    if texture_pattern:
        layers.append({
            "id": "building-texture",
            "type": "fill",
            "source": "zurich",
            "source-layer": "buildings",
            "minzoom": 16,
            "paint": {
                "fill-pattern": texture_pattern,
                "fill-opacity": 0.08
            }
        })

    # ==========================================================================
    # BUILDING OUTLINES - Solid lines with dasharray for hand-drawn effect
    # ==========================================================================
    # Note: line-pattern doesn't work reliably on polygon boundaries in MapLibre
    # Using solid/dashed lines instead for consistent rendering

    # Get configurable dasharray from preset (or default to irregular sketch)
    outline_dasharray = get_dasharray("building_outline")

    # Sketch outline 1 - main pencil stroke (darker, outer)
    outline_1_paint: Dict[str, Any] = {
        "line-color": COLORS["pencil_dark"],
        "line-width": [
            "interpolate", ["linear"], ["zoom"],
            14, 1.5,
            16, 2.0,
            18, 3.0
        ],
        "line-opacity": 0.85
    }
    if outline_dasharray:
        outline_1_paint["line-dasharray"] = outline_dasharray

    layers.append({
        "id": "building-outline-1",
        "type": "line",
        "source": "zurich",
        "source-layer": "buildings",
        "minzoom": 14,
        "paint": outline_1_paint
    })

    # Sketch outline 2 - secondary pencil stroke (lighter, inner shadow)
    outline_2_paint: Dict[str, Any] = {
        "line-color": COLORS["pencil_medium"],
        "line-width": [
            "interpolate", ["linear"], ["zoom"],
            15, 1.0,
            18, 2.0
        ],
        "line-opacity": 0.5,
        "line-offset": -2.5
    }
    if outline_dasharray:
        outline_2_paint["line-dasharray"] = outline_dasharray

    layers.append({
        "id": "building-outline-2",
        "type": "line",
        "source": "zurich",
        "source-layer": "buildings",
        "minzoom": 15,
        "paint": outline_2_paint
    })

    return layers


def create_roof_layers() -> List[Dict[str, Any]]:
    """Create roofs with hatching pattern for pencil shading effect."""
    layers = []

    # Roof fill base color
    layers.append({
        "id": "roof-fill",
        "type": "fill",
        "source": "zurich",
        "source-layer": "roofs",
        "minzoom": 16,
        "paint": {
            "fill-color": [
                "match",
                ["get", "material"],
                "roof_terracotta", COLORS["roof_warm"],
                "terracotta", COLORS["roof_warm"],
                "roof_slate", COLORS["roof_cool"],
                "slate", COLORS["roof_cool"],
                COLORS["roof_default"]
            ],
            "fill-opacity": [
                "interpolate", ["linear"],
                ["coalesce", ["get", "slope_angle"], 20],
                0, 0.3,
                45, 0.6
            ]
        }
    })

    # Roof shading pattern overlay (configurable hatching for pencil effect)
    shading_pattern = get_pattern("roof_shading")
    if shading_pattern:
        layers.append({
            "id": "roof-pattern",
            "type": "fill",
            "source": "zurich",
            "source-layer": "roofs",
            "minzoom": 17,
            "paint": {
                "fill-pattern": shading_pattern,
                "fill-opacity": [
                    "interpolate", ["linear"],
                    ["coalesce", ["get", "slope_angle"], 20],
                    0, 0.1,
                    45, 0.25
                ]
            }
        })

    # Roof outline - main pencil line
    layers.append({
        "id": "roof-outline-1",
        "type": "line",
        "source": "zurich",
        "source-layer": "roofs",
        "minzoom": 16,
        "paint": {
            "line-color": COLORS["pencil_medium"],
            "line-width": 0.8,
            "line-opacity": 0.7
        }
    })

    # Roof outline - secondary lighter stroke with configurable dasharray
    outline_dasharray = get_dasharray("roof_outline") or [3, 2, 1, 2]
    layers.append({
        "id": "roof-outline-2",
        "type": "line",
        "source": "zurich",
        "source-layer": "roofs",
        "minzoom": 17,
        "paint": {
            "line-color": COLORS["pencil_light"],
            "line-width": 0.4,
            "line-opacity": 0.4,
            "line-offset": -0.5,
            "line-dasharray": outline_dasharray
        }
    })

    return layers


def create_transportation_layers() -> List[Dict[str, Any]]:
    """Create streets with hand-drawn pencil strokes."""
    layers = []

    # Street shadow/casing (sketchy)
    layers.append({
        "id": "street-casing",
        "type": "line",
        "source": "zurich",
        "source-layer": "transportation",
        "minzoom": 12,
        "layout": {
            "line-cap": "round",
            "line-join": "round"
        },
        "paint": {
            "line-color": COLORS["street_stroke"],
            "line-width": [
                "interpolate", ["exponential", 1.5], ["zoom"],
                12, 1.5,
                14, 4,
                18, 14
            ],
            "line-opacity": 0.4
        }
    })

    # Street fill (paper color)
    layers.append({
        "id": "street-fill",
        "type": "line",
        "source": "zurich",
        "source-layer": "transportation",
        "minzoom": 12,
        "layout": {
            "line-cap": "round",
            "line-join": "round"
        },
        "paint": {
            "line-color": COLORS["street_fill"],
            "line-width": [
                "interpolate", ["exponential", 1.5], ["zoom"],
                12, 0.8,
                14, 3,
                18, 12
            ]
        }
    })

    # Street edge - left pencil stroke (configurable pattern or dasharray)
    left_pattern = get_pattern("street_edge_left")
    left_dasharray = get_dasharray("street_edge_left") or [6, 2, 2, 2]

    left_paint: Dict[str, Any] = {
        "line-color": COLORS["pencil_medium"],
        "line-width": [
            "interpolate", ["linear"], ["zoom"],
            14, 0.5,
            18, 1.2
        ],
        "line-opacity": 0.6,
        "line-offset": [
            "interpolate", ["exponential", 1.5], ["zoom"],
            14, -1.5,
            18, -6
        ]
    }

    if left_pattern:
        left_paint["line-pattern"] = left_pattern
    else:
        left_paint["line-dasharray"] = left_dasharray

    layers.append({
        "id": "street-edge-left",
        "type": "line",
        "source": "zurich",
        "source-layer": "transportation",
        "minzoom": 14,
        "layout": {
            "line-cap": "round",
            "line-join": "round"
        },
        "paint": left_paint
    })

    # Street edge - right pencil stroke (configurable pattern or dasharray)
    right_pattern = get_pattern("street_edge_right")
    right_dasharray = get_dasharray("street_edge_right") or [4, 3, 1, 3]

    right_paint: Dict[str, Any] = {
        "line-color": COLORS["pencil_medium"],
        "line-width": [
            "interpolate", ["linear"], ["zoom"],
            14, 0.5,
            18, 1.2
        ],
        "line-opacity": 0.6,
        "line-offset": [
            "interpolate", ["exponential", 1.5], ["zoom"],
            14, 1.5,
            18, 6
        ]
    }

    if right_pattern:
        right_paint["line-pattern"] = right_pattern
    else:
        right_paint["line-dasharray"] = right_dasharray

    layers.append({
        "id": "street-edge-right",
        "type": "line",
        "source": "zurich",
        "source-layer": "transportation",
        "minzoom": 14,
        "layout": {
            "line-cap": "round",
            "line-join": "round"
        },
        "paint": right_paint
    })

    # Footway - dotted pencil (configurable dasharray)
    footway_dasharray = get_dasharray("footway") or [1, 3]
    layers.append({
        "id": "street-footway",
        "type": "line",
        "source": "zurich",
        "source-layer": "transportation",
        "minzoom": 15,
        "filter": ["in", ["get", "class"], ["literal", ["footway", "pedestrian", "cycleway"]]],
        "layout": {
            "line-cap": "round",
            "line-join": "round"
        },
        "paint": {
            "line-color": COLORS["pencil_faint"],
            "line-width": 1.5,
            "line-opacity": 0.5,
            "line-dasharray": footway_dasharray
        }
    })

    return layers


def create_railway_layers() -> List[Dict[str, Any]]:
    """Create tram tracks with railroad tie pattern."""
    layers = []

    # Track bed
    layers.append({
        "id": "railway-track-bed",
        "type": "line",
        "source": "zurich",
        "source-layer": "railway",
        "minzoom": 13,
        "paint": {
            "line-color": COLORS["pencil_faint"],
            "line-width": [
                "interpolate", ["linear"], ["zoom"],
                13, 2,
                18, 6
            ],
            "line-opacity": 0.3
        }
    })

    # Track rails - left
    layers.append({
        "id": "railway-rail-left",
        "type": "line",
        "source": "zurich",
        "source-layer": "railway",
        "minzoom": 14,
        "paint": {
            "line-color": COLORS["pencil_dark"],
            "line-width": 1,
            "line-opacity": 0.7,
            "line-offset": -1.5
        }
    })

    # Track rails - right
    layers.append({
        "id": "railway-rail-right",
        "type": "line",
        "source": "zurich",
        "source-layer": "railway",
        "minzoom": 14,
        "paint": {
            "line-color": COLORS["pencil_dark"],
            "line-width": 1,
            "line-opacity": 0.7,
            "line-offset": 1.5
        }
    })

    # Track ties (cross hatches) - configurable dasharray
    ties_dasharray = get_dasharray("railway_ties") or [0.5, 2]
    layers.append({
        "id": "railway-ties",
        "type": "line",
        "source": "zurich",
        "source-layer": "railway",
        "minzoom": 15,
        "paint": {
            "line-color": COLORS["pencil_medium"],
            "line-width": 3,
            "line-opacity": 0.5,
            "line-dasharray": ties_dasharray
        }
    })

    return layers


def create_tree_layers() -> List[Dict[str, Any]]:
    """Create trees with scribble circle effect."""
    return [
        # Tree shadow
        {
            "id": "tree-shadow",
            "type": "circle",
            "source": "zurich",
            "source-layer": "trees",
            "minzoom": 14,
            "paint": {
                "circle-color": COLORS["shadow_light"],
                "circle-radius": [
                    "interpolate", ["linear"], ["zoom"],
                    14, 2.5,
                    16, 5,
                    18, 10
                ],
                "circle-opacity": 0.15,
                "circle-translate": [2, 2],
                "circle-blur": 0.5
            }
        },
        # Tree fill (soft)
        {
            "id": "tree-fill",
            "type": "circle",
            "source": "zurich",
            "source-layer": "trees",
            "minzoom": 14,
            "paint": {
                "circle-color": COLORS["tree_fill"],
                "circle-radius": [
                    "interpolate", ["linear"], ["zoom"],
                    14, 2,
                    16, 4,
                    18, [
                        "interpolate", ["linear"],
                        ["coalesce", ["get", "crown"], 5],
                        2, 5,
                        10, 14
                    ]
                ],
                "circle-opacity": 0.6,
                "circle-blur": 0.3
            }
        },
        # Tree outline (scribble effect - multiple strokes)
        {
            "id": "tree-outline-1",
            "type": "circle",
            "source": "zurich",
            "source-layer": "trees",
            "minzoom": 15,
            "paint": {
                "circle-color": "transparent",
                "circle-stroke-color": COLORS["tree_stroke"],
                "circle-stroke-width": [
                    "interpolate", ["linear"], ["zoom"],
                    15, 0.8,
                    18, 1.5
                ],
                "circle-radius": [
                    "interpolate", ["linear"], ["zoom"],
                    15, 3,
                    18, [
                        "interpolate", ["linear"],
                        ["coalesce", ["get", "crown"], 5],
                        2, 5,
                        10, 14
                    ]
                ],
                "circle-stroke-opacity": 0.7
            }
        },
        # Tree outline 2 (slightly offset for sketch effect)
        {
            "id": "tree-outline-2",
            "type": "circle",
            "source": "zurich",
            "source-layer": "trees",
            "minzoom": 16,
            "paint": {
                "circle-color": "transparent",
                "circle-stroke-color": COLORS["tree_stroke"],
                "circle-stroke-width": 0.5,
                "circle-radius": [
                    "interpolate", ["linear"], ["zoom"],
                    16, 4.5,
                    18, [
                        "+",
                        ["interpolate", ["linear"],
                         ["coalesce", ["get", "crown"], 5],
                         2, 5,
                         10, 14],
                        1.5
                    ]
                ],
                "circle-stroke-opacity": 0.3,
                "circle-translate": [0.5, -0.5]
            }
        }
    ]


def create_poi_layers() -> List[Dict[str, Any]]:
    """Create POI with hand-drawn marker style."""
    return [
        # Amenity POI
        {
            "id": "poi-amenity",
            "type": "circle",
            "source": "zurich",
            "source-layer": "poi",
            "minzoom": 16,
            "filter": ["==", ["get", "class"], "amenity"],
            "paint": {
                "circle-color": COLORS["paper_texture"],
                "circle-radius": [
                    "interpolate", ["linear"], ["zoom"],
                    16, 3,
                    18, 6
                ],
                "circle-opacity": 0.9,
                "circle-stroke-color": [
                    "match",
                    ["get", "subclass"],
                    "fountain", "#6688aa",
                    "bench", "#886644",
                    "toilets", "#886688",
                    COLORS["pencil_medium"]
                ],
                "circle-stroke-width": 1.5
            }
        },
        # Infrastructure POI (smaller, lighter)
        {
            "id": "poi-infrastructure",
            "type": "circle",
            "source": "zurich",
            "source-layer": "poi",
            "minzoom": 17,
            "filter": ["==", ["get", "class"], "infrastructure"],
            "paint": {
                "circle-color": [
                    "match",
                    ["get", "subclass"],
                    "street_lamp", "#aa9944",
                    COLORS["pencil_faint"]
                ],
                "circle-radius": 2,
                "circle-opacity": 0.5
            }
        }
    ]


def create_label_layers() -> List[Dict[str, Any]]:
    """Create hand-lettered style labels."""
    return [
        # Street labels
        {
            "id": "street-label",
            "type": "symbol",
            "source": "zurich",
            "source-layer": "transportation",
            "minzoom": 15,
            "filter": ["has", "name"],
            "layout": {
                "symbol-placement": "line",
                "text-field": ["get", "name"],
                "text-font": ["Noto Sans Regular"],
                "text-size": [
                    "interpolate", ["linear"], ["zoom"],
                    15, 9,
                    18, 13
                ],
                "text-max-angle": 25,
                "text-padding": 30,
                "text-letter-spacing": 0.05
            },
            "paint": {
                "text-color": COLORS["pencil_dark"],
                "text-halo-color": COLORS["label_halo"],
                "text-halo-width": 2,
                "text-halo-blur": 0.5
            }
        },
        # Fountain labels
        {
            "id": "fountain-label",
            "type": "symbol",
            "source": "zurich",
            "source-layer": "poi",
            "minzoom": 17,
            "filter": [
                "all",
                ["==", ["get", "subclass"], "fountain"],
                ["has", "name"]
            ],
            "layout": {
                "text-field": ["get", "name"],
                "text-font": ["Noto Sans Regular"],
                "text-size": 9,
                "text-offset": [0, 1.2],
                "text-anchor": "top",
                "text-letter-spacing": 0.02
            },
            "paint": {
                "text-color": "#6688aa",
                "text-halo-color": COLORS["label_halo"],
                "text-halo-width": 1.5
            }
        }
    ]


def set_active_preset(preset_name: str) -> None:
    """
    Set the active style preset and rebuild configs.

    Args:
        preset_name: Name of preset (sketchy, technical, artistic, minimal, zigzag)
    """
    global ACTIVE_PRESET, PENCIL_CONFIG, DASH_CONFIG

    if preset_name not in STYLE_PRESETS:
        raise ValueError(f"Unknown preset: {preset_name}. Available: {list(STYLE_PRESETS.keys())}")

    ACTIVE_PRESET = preset_name
    PENCIL_CONFIG, DASH_CONFIG = _build_config_from_preset()


def create_style(output_path: Path, verbose: bool = False,
                 preset: str | None = None) -> Dict[str, Any]:
    """
    Generate complete hand-drawn MapLibre style.json.

    Args:
        output_path: Path to write style.json
        verbose: Print layer info
        preset: Style preset name (sketchy, technical, artistic, minimal, zigzag)

    Returns:
        Complete style dictionary
    """
    # Apply preset if specified
    if preset:
        set_active_preset(preset)
        if verbose:
            print(f"\nUsing preset: {preset} - {get_active_preset()['description']}")

    preset_info = get_active_preset()

    # Collect all layers in render order (bottom to top)
    layers = []

    # Background (parchment paper)
    layers.extend(create_background_layers())

    # Water (wash effect)
    layers.extend(create_water_layers())

    # Buildings (stacked sketchy outlines)
    layers.extend(create_building_layers())

    # Roofs (hatching)
    layers.extend(create_roof_layers())

    # Transportation (pencil strokes)
    layers.extend(create_transportation_layers())

    # Railway (ties pattern)
    layers.extend(create_railway_layers())

    # Trees (scribble circles)
    layers.extend(create_tree_layers())

    # POI (hand-drawn markers)
    layers.extend(create_poi_layers())

    # Labels (hand-lettered)
    layers.extend(create_label_layers())

    # Build complete style
    style = {
        "version": 8,
        "name": f"Zurich {preset_info['name']}",
        "metadata": {
            "mapbox:autocomposite": False,
            "maputnik:renderer": "mlgljs",
            "generator": "zurich-vector-tiles-pipeline",
            "style-type": "hand-drawn-pencil",
            "pencil-preset": ACTIVE_PRESET,
            "pencil-preset-description": preset_info["description"],
        },
        "sources": create_source_definition(),
        "sprite": "/tiles/vector/sprite",
        "glyphs": "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
        "layers": layers,
        "center": [8.5417, 47.3769],
        "zoom": 15,
        "bearing": 0,
        "pitch": 0
    }

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(style, f, indent=2)

    if verbose:
        print(f"\nStyle layers ({len(layers)} total):")
        for layer in layers:
            min_zoom = layer.get("minzoom", 0)
            max_zoom = layer.get("maxzoom", 24)
            source_layer = layer.get("source-layer", "-")
            print(f"  {layer['id']:25} z{min_zoom}-{max_zoom:2}  ({source_layer})")

    return style


def create_all_preset_styles(output_dir: Path, verbose: bool = False) -> None:
    """
    Generate style files for all presets.

    Args:
        output_dir: Directory to write style files
        verbose: Print layer info
    """
    print("\n" + "=" * 60)
    print("GENERATING ALL PRESET STYLES")
    print("=" * 60)

    for preset_name, preset_config in STYLE_PRESETS.items():
        output_path = output_dir / f"zurich-style-{preset_name}.json"
        create_style(output_path, verbose=False, preset=preset_name)
        print(f"  ✓ {preset_name:12} → {output_path.name}")

    # Also create default style (using sketchy preset)
    default_path = output_dir / "zurich-style.json"
    create_style(default_path, verbose=verbose, preset="sketchy")
    print(f"  ✓ {'default':12} → {default_path.name} (sketchy)")

    print(f"\nGenerated {len(STYLE_PRESETS) + 1} style files")


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Generate MapLibre pencil style")
    parser.add_argument("output", nargs="?", default="test-style.json",
                        help="Output file path")
    parser.add_argument("--preset", "-p", choices=list(STYLE_PRESETS.keys()),
                        default="sketchy", help="Style preset to use")
    parser.add_argument("--all-presets", "-a", action="store_true",
                        help="Generate all preset styles")
    parser.add_argument("--list-presets", "-l", action="store_true",
                        help="List available presets")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print layer info")

    args = parser.parse_args()

    if args.list_presets:
        print("\nAvailable style presets:")
        print("-" * 60)
        for name, config in STYLE_PRESETS.items():
            print(f"  {name:12} - {config['description']}")
        print()
        sys.exit(0)

    output = Path(args.output)

    if args.all_presets:
        create_all_preset_styles(output.parent if output.suffix == ".json" else output,
                                 verbose=args.verbose)
    else:
        create_style(output, verbose=args.verbose, preset=args.preset)
        print(f"\nWrote style to: {output}")
