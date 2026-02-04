"""
Material and color definitions for rendered mode.

Defines visual styles that can be applied to Blender-rendered tiles.
Each style specifies colors for buildings, vegetation, infrastructure,
and lighting parameters.

Usage:
    from .materials import STYLES, get_style

    style = get_style("google_earth")
    building_color = style.building_wall
"""

from dataclasses import dataclass, field
from typing import Tuple, Dict

# Type alias for RGB colors (0.0-1.0 range)
RGB = Tuple[float, float, float]


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
