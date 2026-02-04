"""
Material and color definitions for rendered mode.

Defines visual styles that can be applied to Blender-rendered tiles.
Each style specifies colors for buildings, vegetation, infrastructure,
and lighting parameters.

Also includes data-driven material mappings:
- BUILDING_TYPE_MATERIALS: Maps Zurich building types (art) to wall/roof colors
- TREE_SPECIES_COLORS: Maps tree species to seasonal foliage colors

Usage:
    from .materials import STYLES, get_style, get_building_material, get_tree_color

    style = get_style("google_earth")
    building_color = style.building_wall

    # Data-driven materials
    wall_color, roof_color = get_building_material("Gebaeude_Wohngebaeude")
    foliage_color = get_tree_color("Acer pseudoplatanus", "autumn")
"""

from dataclasses import dataclass, field
from typing import Tuple, Dict, Optional

# Type alias for RGB colors (0.0-1.0 range)
RGB = Tuple[float, float, float]


# =============================================================================
# BUILDING TYPE MATERIALS
# =============================================================================
# Maps Zurich building types (art field from Stadt Zürich data) to colors.
# These represent typical Swiss building appearances.

@dataclass
class BuildingMaterial:
    """Material properties for a building type."""
    wall: RGB
    roof: RGB
    wall_roughness: float = 0.8
    roof_roughness: float = 0.85
    description: str = ""


# Zurich building type -> material mapping
# Based on Stadt Zürich Gebäude-Typen from open data
BUILDING_TYPE_MATERIALS: Dict[str, BuildingMaterial] = {
    # Residential buildings - warm, traditional Swiss style
    "Gebaeude_Wohngebaeude": BuildingMaterial(
        wall=(0.92, 0.88, 0.82),  # Warm cream/beige
        roof=(0.55, 0.35, 0.28),  # Terracotta red-brown
        description="Residential buildings",
    ),
    "Gebaeude_Wohngebaeude_mit_Gewerbe": BuildingMaterial(
        wall=(0.88, 0.85, 0.80),  # Slightly warmer beige
        roof=(0.50, 0.38, 0.30),  # Brown-red
        description="Mixed residential/commercial",
    ),

    # Commercial buildings - cooler, more modern
    "Gebaeude_Handel": BuildingMaterial(
        wall=(0.82, 0.84, 0.86),  # Cool gray-blue
        roof=(0.35, 0.38, 0.42),  # Dark gray
        wall_roughness=0.6,  # Smoother, more glass-like
        description="Commercial/retail buildings",
    ),
    "Gebaeude_Buerohaus": BuildingMaterial(
        wall=(0.78, 0.80, 0.85),  # Office gray-blue
        roof=(0.30, 0.32, 0.38),  # Dark slate
        wall_roughness=0.5,  # Glassy
        description="Office buildings",
    ),

    # Industrial buildings - utilitarian gray
    "Gebaeude_Industrie": BuildingMaterial(
        wall=(0.70, 0.70, 0.72),  # Industrial gray
        roof=(0.40, 0.42, 0.45),  # Metal roof
        roof_roughness=0.7,  # Metallic
        description="Industrial buildings",
    ),
    "Gebaeude_Gewerbe": BuildingMaterial(
        wall=(0.75, 0.73, 0.70),  # Warm industrial
        roof=(0.38, 0.36, 0.35),  # Dark brown-gray
        description="Trade/craft buildings",
    ),

    # Public buildings - distinctive character
    "Gebaeude_Verwaltung": BuildingMaterial(
        wall=(0.85, 0.85, 0.82),  # Neutral stone
        roof=(0.45, 0.42, 0.38),  # Brown slate
        description="Administrative/government buildings",
    ),
    "Gebaeude_Schule": BuildingMaterial(
        wall=(0.90, 0.88, 0.82),  # Warm institutional
        roof=(0.48, 0.35, 0.28),  # Red-brown
        description="School buildings",
    ),
    "Gebaeude_Kirche": BuildingMaterial(
        wall=(0.82, 0.80, 0.75),  # Stone gray
        roof=(0.35, 0.32, 0.30),  # Dark gray/copper
        description="Churches/religious buildings",
    ),
    "Gebaeude_Spital": BuildingMaterial(
        wall=(0.92, 0.92, 0.90),  # Clean white
        roof=(0.45, 0.45, 0.48),  # Gray
        description="Hospital buildings",
    ),

    # Utility buildings - simple, functional
    "Gebaeude_Nebengebaeude": BuildingMaterial(
        wall=(0.78, 0.75, 0.70),  # Simple beige-gray
        roof=(0.50, 0.45, 0.40),  # Brown
        description="Ancillary/utility buildings",
    ),
    "Gebaeude_Garage": BuildingMaterial(
        wall=(0.72, 0.72, 0.72),  # Concrete gray
        roof=(0.55, 0.55, 0.58),  # Flat gray
        description="Garages/parking structures",
    ),

    # Special buildings
    "Gebaeude_Museum": BuildingMaterial(
        wall=(0.88, 0.86, 0.82),  # Stone/plaster
        roof=(0.42, 0.45, 0.48),  # Distinctive dark
        description="Museums",
    ),
    "Gebaeude_Theater": BuildingMaterial(
        wall=(0.85, 0.82, 0.78),  # Warm stone
        roof=(0.38, 0.35, 0.32),  # Dark brown
        description="Theaters/cultural venues",
    ),

    # Default fallback
    "default": BuildingMaterial(
        wall=(0.85, 0.82, 0.78),  # Neutral warm
        roof=(0.45, 0.38, 0.32),  # Brown
        description="Default building style",
    ),
}


def get_building_material(building_type: Optional[str]) -> BuildingMaterial:
    """Get material for a building type.

    Args:
        building_type: Building type string (art field from data)

    Returns:
        BuildingMaterial with wall and roof colors
    """
    if building_type and building_type in BUILDING_TYPE_MATERIALS:
        return BUILDING_TYPE_MATERIALS[building_type]
    return BUILDING_TYPE_MATERIALS["default"]


@dataclass
class RenderStyle:
    """Visual style for rendered tiles.

    All colors are RGB tuples in 0.0-1.0 range.
    Lighting values control sun and ambient intensity.
    """

    name: str
    description: str = ""

    # Building colors
    building_wall: RGB = (0.85, 0.82, 0.78)  # Warm beige
    building_roof: RGB = (0.45, 0.35, 0.30)  # Brown-red terracotta
    building_roughness: float = 0.8  # Matte surface

    # Vegetation
    tree_foliage: RGB = (0.25, 0.45, 0.20)  # Forest green
    tree_trunk: RGB = (0.35, 0.25, 0.18)  # Brown bark
    grass: RGB = (0.35, 0.50, 0.25)  # Lawn green

    # Infrastructure
    street: RGB = (0.35, 0.35, 0.38)  # Asphalt gray
    sidewalk: RGB = (0.70, 0.68, 0.65)  # Light concrete
    water: RGB = (0.20, 0.35, 0.50)  # Blue

    # Terrain/ground
    terrain: RGB = (0.45, 0.42, 0.38)  # Earthy brown
    terrain_roughness: float = 0.95  # Very matte

    # Lighting
    sun_strength: float = 3.0
    sun_color: RGB = (1.0, 0.98, 0.95)  # Warm white
    ambient_strength: float = 0.3
    sky_color: RGB = (0.7, 0.8, 1.0)  # Light blue

    # Render quality
    default_samples: int = 64

    def to_dict(self) -> Dict:
        """Convert style to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "building_wall": list(self.building_wall),
            "building_roof": list(self.building_roof),
            "building_roughness": self.building_roughness,
            "tree_foliage": list(self.tree_foliage),
            "tree_trunk": list(self.tree_trunk),
            "grass": list(self.grass),
            "street": list(self.street),
            "sidewalk": list(self.sidewalk),
            "water": list(self.water),
            "terrain": list(self.terrain),
            "terrain_roughness": self.terrain_roughness,
            "sun_strength": self.sun_strength,
            "sun_color": list(self.sun_color),
            "ambient_strength": self.ambient_strength,
            "sky_color": list(self.sky_color),
            "default_samples": self.default_samples,
        }


# Predefined visual styles
STYLES: Dict[str, RenderStyle] = {
    "default": RenderStyle(
        name="Default",
        description="Clean, neutral colors suitable for most uses",
    ),
    "google_earth": RenderStyle(
        name="Google Earth",
        description="Realistic, muted tones similar to Google Earth 3D",
        building_wall=(0.90, 0.88, 0.85),  # Lighter beige
        building_roof=(0.50, 0.40, 0.35),  # Muted brown
        tree_foliage=(0.30, 0.42, 0.25),  # Slightly desaturated green
        grass=(0.40, 0.48, 0.30),  # More natural grass
        terrain=(0.50, 0.47, 0.42),  # Neutral earth
        sun_strength=2.5,
        ambient_strength=0.35,
    ),
    "simcity": RenderStyle(
        name="SimCity",
        description="Vibrant, game-like colors inspired by city builders",
        building_wall=(0.95, 0.90, 0.80),  # Bright cream
        building_roof=(0.60, 0.25, 0.20),  # Vivid red
        tree_foliage=(0.20, 0.55, 0.15),  # Bright green
        grass=(0.30, 0.60, 0.20),  # Lush lawn
        terrain=(0.50, 0.45, 0.35),
        sun_strength=3.5,
        sky_color=(0.6, 0.75, 1.0),  # Brighter sky
        default_samples=48,  # Slightly lower for faster renders
    ),
    "zurich": RenderStyle(
        name="Zurich",
        description="Colors matching Zurich's actual building palette",
        building_wall=(0.88, 0.85, 0.80),  # Swiss beige/cream
        building_roof=(0.40, 0.32, 0.28),  # Dark brown tiles
        tree_foliage=(0.22, 0.40, 0.18),  # Central European forest
        grass=(0.32, 0.45, 0.22),  # Alpine meadow
        terrain=(0.48, 0.44, 0.38),
        sun_strength=2.8,
        sun_color=(1.0, 0.97, 0.92),  # Swiss afternoon light
    ),
    "winter": RenderStyle(
        name="Winter",
        description="Cool tones with snow-covered ground",
        building_wall=(0.92, 0.90, 0.88),  # Pale buildings
        building_roof=(0.35, 0.30, 0.28),  # Dark roofs with snow patches
        tree_foliage=(0.20, 0.32, 0.18),  # Darker evergreen
        tree_trunk=(0.30, 0.22, 0.16),
        grass=(0.85, 0.88, 0.90),  # Snow-covered ground
        terrain=(0.80, 0.83, 0.87),  # Snowy terrain
        sun_strength=2.0,  # Weaker winter sun
        sun_color=(1.0, 0.98, 1.0),  # Cool white
        sky_color=(0.75, 0.82, 0.95),  # Pale winter sky
        ambient_strength=0.4,  # More ambient from snow reflection
    ),
    "evening": RenderStyle(
        name="Evening",
        description="Warm golden hour lighting",
        building_wall=(0.90, 0.82, 0.70),  # Warm-lit walls
        building_roof=(0.50, 0.38, 0.30),
        tree_foliage=(0.28, 0.42, 0.18),
        grass=(0.38, 0.48, 0.22),
        terrain=(0.52, 0.45, 0.35),
        sun_strength=2.2,
        sun_color=(1.0, 0.85, 0.65),  # Golden light
        sky_color=(0.85, 0.75, 0.60),  # Orange-tinted sky
        ambient_strength=0.25,
    ),
    "blueprint": RenderStyle(
        name="Blueprint",
        description="Technical blueprint-style rendering",
        building_wall=(0.25, 0.35, 0.50),  # Blue buildings
        building_roof=(0.20, 0.30, 0.45),  # Darker blue roofs
        building_roughness=0.5,
        tree_foliage=(0.30, 0.40, 0.50),  # Blue-tinted trees
        tree_trunk=(0.25, 0.32, 0.42),
        grass=(0.20, 0.30, 0.45),  # Blue ground
        terrain=(0.18, 0.25, 0.38),
        sun_strength=2.0,
        sun_color=(0.9, 0.95, 1.0),  # Cool white
        sky_color=(0.15, 0.20, 0.35),  # Dark blue background
        ambient_strength=0.5,  # More ambient for flat look
        default_samples=32,
    ),
}


def get_style(name: str) -> RenderStyle:
    """Get a render style by name.

    Args:
        name: Style name (case-insensitive)

    Returns:
        RenderStyle instance

    Raises:
        ValueError: If style name is not found
    """
    name_lower = name.lower()
    if name_lower not in STYLES:
        available = ", ".join(sorted(STYLES.keys()))
        raise ValueError(f"Unknown style '{name}'. Available: {available}")
    return STYLES[name_lower]


def list_styles() -> Dict[str, str]:
    """List all available styles with descriptions.

    Returns:
        Dict mapping style name to description
    """
    return {name: style.description for name, style in STYLES.items()}


# =============================================================================
# TREE SPECIES COLORS (Season-aware)
# =============================================================================
# Maps tree genus (first word of species) to seasonal foliage colors.
# Based on actual tree species in Zurich's Baumkataster (80k+ trees).

# Common tree genera in Zurich with their seasonal colors
TREE_SPECIES_COLORS: Dict[str, Dict[str, RGB]] = {
    # DECIDUOUS TREES - change colors with seasons
    "Acer": {  # Maple - spectacular autumn colors
        "spring": (0.45, 0.55, 0.25),  # Fresh lime green
        "summer": (0.25, 0.48, 0.20),  # Deep green
        "autumn": (0.90, 0.35, 0.12),  # Bright red-orange
        "winter": (0.40, 0.32, 0.25),  # Bare branches (brown)
    },
    "Quercus": {  # Oak - brown/gold autumn
        "spring": (0.40, 0.52, 0.22),  # Yellow-green
        "summer": (0.22, 0.45, 0.18),  # Dark forest green
        "autumn": (0.70, 0.50, 0.22),  # Brown-gold
        "winter": (0.38, 0.30, 0.22),  # Bare branches
    },
    "Fagus": {  # Beech - yellow/orange autumn
        "spring": (0.50, 0.58, 0.28),  # Bright green
        "summer": (0.25, 0.45, 0.18),  # Rich green
        "autumn": (0.85, 0.65, 0.25),  # Yellow-orange
        "winter": (0.35, 0.28, 0.22),  # Bare branches
    },
    "Tilia": {  # Linden/Lime - common in Zurich streets
        "spring": (0.48, 0.58, 0.30),  # Light green
        "summer": (0.28, 0.50, 0.22),  # Medium green
        "autumn": (0.80, 0.72, 0.30),  # Yellow
        "winter": (0.36, 0.30, 0.24),  # Bare branches
    },
    "Platanus": {  # Plane tree - very common in Zurich
        "spring": (0.45, 0.55, 0.28),  # Fresh green
        "summer": (0.30, 0.50, 0.25),  # Medium green
        "autumn": (0.75, 0.58, 0.28),  # Brown-yellow
        "winter": (0.42, 0.35, 0.28),  # Bare branches
    },
    "Betula": {  # Birch - yellow autumn
        "spring": (0.52, 0.60, 0.32),  # Bright lime
        "summer": (0.35, 0.52, 0.28),  # Light green
        "autumn": (0.90, 0.82, 0.35),  # Bright yellow
        "winter": (0.50, 0.48, 0.42),  # White bark visible
    },
    "Fraxinus": {  # Ash
        "spring": (0.42, 0.52, 0.25),  # Green
        "summer": (0.25, 0.45, 0.20),  # Dark green
        "autumn": (0.70, 0.55, 0.30),  # Yellow-brown
        "winter": (0.35, 0.30, 0.25),  # Bare
    },
    "Carpinus": {  # Hornbeam
        "spring": (0.50, 0.58, 0.30),  # Bright green
        "summer": (0.28, 0.48, 0.22),  # Medium green
        "autumn": (0.82, 0.70, 0.32),  # Golden yellow
        "winter": (0.38, 0.32, 0.26),  # Bare
    },
    "Prunus": {  # Cherry/Plum - spring blossoms, red autumn
        "spring": (0.95, 0.85, 0.88),  # Pink blossoms!
        "summer": (0.28, 0.45, 0.20),  # Green
        "autumn": (0.85, 0.40, 0.25),  # Red-orange
        "winter": (0.38, 0.30, 0.25),  # Bare
    },
    "Sorbus": {  # Rowan/Mountain Ash - red berries in autumn
        "spring": (0.45, 0.55, 0.28),  # Green
        "summer": (0.30, 0.50, 0.25),  # Medium green
        "autumn": (0.88, 0.45, 0.20),  # Orange-red
        "winter": (0.40, 0.32, 0.26),  # Bare with berries
    },
    "Castanea": {  # Chestnut
        "spring": (0.45, 0.55, 0.25),  # Green
        "summer": (0.25, 0.48, 0.20),  # Deep green
        "autumn": (0.75, 0.55, 0.25),  # Brown-gold
        "winter": (0.38, 0.30, 0.24),  # Bare
    },
    "Populus": {  # Poplar
        "spring": (0.50, 0.58, 0.30),  # Light green
        "summer": (0.32, 0.52, 0.25),  # Green
        "autumn": (0.88, 0.80, 0.35),  # Yellow
        "winter": (0.40, 0.35, 0.28),  # Bare
    },
    "Salix": {  # Willow
        "spring": (0.55, 0.62, 0.35),  # Light yellow-green
        "summer": (0.35, 0.55, 0.30),  # Fresh green
        "autumn": (0.75, 0.70, 0.35),  # Yellow
        "winter": (0.45, 0.40, 0.30),  # Bare
    },
    "Liquidambar": {  # Sweetgum - spectacular autumn
        "spring": (0.45, 0.55, 0.28),  # Green
        "summer": (0.28, 0.48, 0.22),  # Dark green
        "autumn": (0.85, 0.25, 0.18),  # Deep red-purple
        "winter": (0.38, 0.30, 0.25),  # Bare
    },
    "Ginkgo": {  # Ginkgo - bright yellow autumn
        "spring": (0.50, 0.58, 0.32),  # Bright green
        "summer": (0.35, 0.52, 0.28),  # Green
        "autumn": (0.95, 0.88, 0.30),  # Brilliant yellow
        "winter": (0.40, 0.35, 0.28),  # Bare
    },

    # EVERGREEN TREES - stay green year-round
    "Picea": {  # Spruce - classic evergreen
        "spring": (0.18, 0.38, 0.18),  # Dark green
        "summer": (0.18, 0.38, 0.18),  # Dark green
        "autumn": (0.18, 0.38, 0.18),  # Dark green
        "winter": (0.15, 0.32, 0.15),  # Slightly darker, snow-dusted
    },
    "Pinus": {  # Pine
        "spring": (0.22, 0.42, 0.20),  # Green
        "summer": (0.22, 0.42, 0.20),  # Green
        "autumn": (0.22, 0.42, 0.20),  # Green
        "winter": (0.18, 0.35, 0.17),  # Slightly darker
    },
    "Abies": {  # Fir
        "spring": (0.15, 0.35, 0.15),  # Dark green
        "summer": (0.15, 0.35, 0.15),  # Dark green
        "autumn": (0.15, 0.35, 0.15),  # Dark green
        "winter": (0.12, 0.30, 0.12),  # Darker
    },
    "Taxus": {  # Yew
        "spring": (0.18, 0.35, 0.18),  # Dark green
        "summer": (0.18, 0.35, 0.18),  # Dark green
        "autumn": (0.18, 0.35, 0.18),  # Dark green
        "winter": (0.15, 0.30, 0.15),  # Darker
    },
    "Thuja": {  # Arborvitae/Cedar
        "spring": (0.22, 0.42, 0.22),  # Green
        "summer": (0.22, 0.42, 0.22),  # Green
        "autumn": (0.22, 0.42, 0.22),  # Green
        "winter": (0.20, 0.38, 0.20),  # Slightly darker
    },
    "Juniperus": {  # Juniper
        "spring": (0.25, 0.40, 0.25),  # Blue-green
        "summer": (0.25, 0.40, 0.25),  # Blue-green
        "autumn": (0.25, 0.40, 0.25),  # Blue-green
        "winter": (0.22, 0.35, 0.22),  # Darker
    },
    "Cedrus": {  # Cedar
        "spring": (0.20, 0.40, 0.22),  # Blue-green
        "summer": (0.20, 0.40, 0.22),  # Blue-green
        "autumn": (0.20, 0.40, 0.22),  # Blue-green
        "winter": (0.18, 0.35, 0.20),  # Darker
    },
    "Sequoia": {  # Redwood (rare but present in parks)
        "spring": (0.20, 0.38, 0.20),  # Green
        "summer": (0.20, 0.38, 0.20),  # Green
        "autumn": (0.20, 0.38, 0.20),  # Green
        "winter": (0.18, 0.35, 0.18),  # Darker
    },

    # Default for unknown species
    "default": {
        "spring": (0.40, 0.55, 0.25),  # Light green
        "summer": (0.28, 0.48, 0.22),  # Medium green
        "autumn": (0.72, 0.55, 0.28),  # Mixed autumn
        "winter": (0.38, 0.32, 0.26),  # Bare branches
    },
}


def get_tree_color(
    species: Optional[str],
    season: str = "summer",
) -> RGB:
    """Get foliage color for a tree species in a given season.

    Args:
        species: Full species name (e.g., "Acer pseudoplatanus") or genus
        season: One of "spring", "summer", "autumn", "winter"

    Returns:
        RGB color tuple (0.0-1.0 range)
    """
    if season not in ("spring", "summer", "autumn", "winter"):
        season = "summer"

    if not species:
        return TREE_SPECIES_COLORS["default"][season]

    # Extract genus (first word)
    genus = species.split()[0] if species else "default"

    # Look up colors
    if genus in TREE_SPECIES_COLORS:
        return TREE_SPECIES_COLORS[genus][season]

    return TREE_SPECIES_COLORS["default"][season]


def is_evergreen(species: Optional[str]) -> bool:
    """Check if a tree species is evergreen.

    Args:
        species: Full species name or genus

    Returns:
        True if the tree stays green year-round
    """
    evergreen_genera = {
        "Picea", "Pinus", "Abies", "Taxus", "Thuja",
        "Juniperus", "Cedrus", "Sequoia", "Tsuga", "Pseudotsuga",
    }

    if not species:
        return False

    genus = species.split()[0] if species else ""
    return genus in evergreen_genera
