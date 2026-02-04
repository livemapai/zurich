"""
Data-driven style presets combining season, time of day, and visual parameters.

These presets combine multiple parameters to create complete rendering configurations:
- Season: affects tree colors (via tree_species.py)
- Time of day: affects sun position and lighting
- Weather: affects snow coverage, color grading
- Style: affects overall mood (realistic, stylized, etc.)

Usage:
    from .style_presets import get_style_preset, STYLE_PRESETS

    preset = get_style_preset("winter")
    season = preset.season  # "winter"
    snow_coverage = preset.snow_coverage  # 0.8
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List


@dataclass
class DataDrivenStylePreset:
    """Complete style configuration combining all rendering parameters.

    This brings together:
    - Season (for tree colors via materials.py)
    - Time of day (for sun position via time_presets.py)
    - Weather effects (snow, rain, fog)
    - Color grading (saturation, temperature shift)
    - Special effects (neon, bloom, etc.)
    """

    name: str
    description: str

    # Season - drives tree color selection
    season: str = "summer"  # spring, summer, autumn, winter

    # Time of day - drives sun position
    time_of_day: str = "afternoon"  # morning, noon, afternoon, evening, night

    # Sun parameters (override time_presets if specified)
    sun_altitude: Optional[float] = None  # Degrees above horizon
    sun_azimuth: Optional[float] = None  # Degrees from north
    sun_warmth: float = 1.0  # Color temperature multiplier (0=cold, 1=neutral, 2=warm)
    sun_strength: float = 3.0  # Light intensity

    # Weather effects
    snow_coverage: float = 0.0  # 0.0-1.0, how much snow on surfaces
    rain_wetness: float = 0.0  # 0.0-1.0, wet surface reflectivity
    fog_density: float = 0.0  # 0.0-1.0, atmospheric fog

    # Use real data
    use_building_types: bool = True  # Use per-building materials
    use_tree_species: bool = True  # Use per-tree species colors
    use_street_lights: bool = False  # Enable street light points

    # Color grading
    saturation: float = 1.0  # 0.0-2.0
    contrast: float = 1.0  # 0.0-2.0
    temperature_shift: float = 0.0  # -1.0 (cold blue) to +1.0 (warm orange)
    brightness: float = 1.0  # 0.5-1.5

    # Sky appearance
    sky_color: tuple = (0.7, 0.8, 1.0)  # RGB
    ambient_strength: float = 0.3

    # LLM variation settings
    allow_llm_variation: bool = True  # Allow LLM to adjust colors
    variation_seed: Optional[int] = None  # For reproducible LLM variations

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "season": self.season,
            "time_of_day": self.time_of_day,
            "sun_altitude": self.sun_altitude,
            "sun_azimuth": self.sun_azimuth,
            "sun_warmth": self.sun_warmth,
            "sun_strength": self.sun_strength,
            "snow_coverage": self.snow_coverage,
            "rain_wetness": self.rain_wetness,
            "fog_density": self.fog_density,
            "use_building_types": self.use_building_types,
            "use_tree_species": self.use_tree_species,
            "use_street_lights": self.use_street_lights,
            "saturation": self.saturation,
            "contrast": self.contrast,
            "temperature_shift": self.temperature_shift,
            "brightness": self.brightness,
            "sky_color": list(self.sky_color),
            "ambient_strength": self.ambient_strength,
            "allow_llm_variation": self.allow_llm_variation,
            "variation_seed": self.variation_seed,
        }


# =============================================================================
# PREDEFINED STYLE PRESETS
# =============================================================================

STYLE_PRESETS: Dict[str, DataDrivenStylePreset] = {
    # Seasonal presets
    "spring": DataDrivenStylePreset(
        name="Spring",
        description="Fresh spring colors with cherry blossoms and new leaves",
        season="spring",
        time_of_day="morning",
        sun_warmth=1.1,
        sun_strength=3.2,
        saturation=1.1,
        temperature_shift=0.1,
        sky_color=(0.65, 0.78, 1.0),
    ),

    "summer": DataDrivenStylePreset(
        name="Summer",
        description="Lush summer with full green canopy",
        season="summer",
        time_of_day="afternoon",
        sun_altitude=55,
        sun_strength=3.5,
        saturation=1.0,
        sky_color=(0.6, 0.75, 1.0),
    ),

    "autumn": DataDrivenStylePreset(
        name="Autumn",
        description="Spectacular fall colors - red maples, golden beeches",
        season="autumn",
        time_of_day="afternoon",
        sun_altitude=30,
        sun_warmth=1.4,
        sun_strength=2.8,
        saturation=1.15,
        temperature_shift=0.2,
        sky_color=(0.72, 0.78, 0.92),
    ),

    "winter": DataDrivenStylePreset(
        name="Winter",
        description="Snow-covered scene with bare deciduous trees",
        season="winter",
        time_of_day="afternoon",
        sun_altitude=20,
        sun_warmth=0.7,
        sun_strength=2.0,
        snow_coverage=0.8,
        saturation=0.85,
        temperature_shift=-0.15,
        brightness=1.1,  # Brighter from snow reflection
        sky_color=(0.75, 0.82, 0.95),
        ambient_strength=0.4,
    ),

    # Time-of-day presets
    "golden_hour": DataDrivenStylePreset(
        name="Golden Hour",
        description="Warm sunset lighting with long shadows",
        season="summer",
        time_of_day="evening",
        sun_altitude=12,
        sun_azimuth=280,
        sun_warmth=1.8,
        sun_strength=2.2,
        saturation=1.1,
        temperature_shift=0.35,
        sky_color=(0.85, 0.75, 0.60),
    ),

    "night": DataDrivenStylePreset(
        name="Night",
        description="City at night with street lights",
        season="summer",
        time_of_day="night",
        sun_altitude=-10,
        sun_strength=0.1,
        use_street_lights=True,
        saturation=0.8,
        brightness=0.4,
        sky_color=(0.05, 0.08, 0.15),
        ambient_strength=0.1,
    ),

    # Weather presets
    "overcast": DataDrivenStylePreset(
        name="Overcast",
        description="Cloudy day with soft, diffuse lighting",
        season="summer",
        time_of_day="noon",
        sun_altitude=45,
        sun_strength=1.5,
        fog_density=0.1,
        saturation=0.85,
        contrast=0.9,
        sky_color=(0.75, 0.78, 0.82),
        ambient_strength=0.5,
    ),

    "rainy": DataDrivenStylePreset(
        name="Rainy",
        description="Wet surfaces after rain",
        season="autumn",
        time_of_day="afternoon",
        sun_strength=1.8,
        rain_wetness=0.7,
        fog_density=0.15,
        saturation=0.9,
        temperature_shift=-0.1,
        sky_color=(0.65, 0.68, 0.75),
        ambient_strength=0.45,
    ),

    "foggy": DataDrivenStylePreset(
        name="Foggy",
        description="Morning fog with reduced visibility",
        season="autumn",
        time_of_day="morning",
        sun_altitude=15,
        sun_strength=1.5,
        fog_density=0.4,
        saturation=0.75,
        contrast=0.8,
        sky_color=(0.80, 0.82, 0.85),
        ambient_strength=0.6,
    ),

    # Stylized/Creative presets
    "cyberpunk": DataDrivenStylePreset(
        name="Cyberpunk",
        description="Neon-lit night city with pink/cyan glow",
        season="summer",
        time_of_day="night",
        sun_altitude=-15,
        sun_strength=0.05,
        use_street_lights=True,
        rain_wetness=0.8,  # Wet reflective streets
        saturation=1.3,
        contrast=1.2,
        temperature_shift=-0.2,  # Cool base
        sky_color=(0.08, 0.02, 0.12),  # Purple night
        ambient_strength=0.15,
        allow_llm_variation=True,  # LLM picks neon colors
    ),

    "watercolor": DataDrivenStylePreset(
        name="Watercolor",
        description="Soft, artistic watercolor-like rendering",
        season="summer",
        time_of_day="afternoon",
        sun_strength=2.5,
        saturation=0.7,
        contrast=0.75,
        brightness=1.1,
        sky_color=(0.82, 0.85, 0.92),
        ambient_strength=0.5,
        allow_llm_variation=True,
    ),

    "vintage": DataDrivenStylePreset(
        name="Vintage",
        description="Warm, nostalgic film-like appearance",
        season="summer",
        time_of_day="afternoon",
        sun_warmth=1.5,
        sun_strength=2.8,
        saturation=0.85,
        contrast=0.95,
        temperature_shift=0.25,
        brightness=1.05,
        sky_color=(0.78, 0.75, 0.68),
    ),

    # Default - pure data-driven
    "default": DataDrivenStylePreset(
        name="Default",
        description="Clean, realistic rendering using data-driven materials",
        season="summer",
        time_of_day="afternoon",
        sun_strength=3.0,
        use_building_types=True,
        use_tree_species=True,
    ),

    # Isometric 3D view - shows building facades
    "isometric": DataDrivenStylePreset(
        name="Isometric 3D",
        description="Tilted camera showing building walls for 3D depth",
        season="summer",
        time_of_day="afternoon",
        sun_altitude=35,
        sun_azimuth=225,
        sun_strength=3.0,
        use_building_types=True,
        use_tree_species=True,
    ),

    "isometric_golden": DataDrivenStylePreset(
        name="Isometric Golden Hour",
        description="Dramatic isometric view with golden hour lighting",
        season="summer",
        time_of_day="evening",
        sun_altitude=15,
        sun_azimuth=260,
        sun_warmth=1.6,
        sun_strength=2.5,
        temperature_shift=0.3,
        use_building_types=True,
        use_tree_species=True,
    ),
}


def get_style_preset(name: str) -> DataDrivenStylePreset:
    """Get a style preset by name.

    Args:
        name: Preset name (case-insensitive)

    Returns:
        DataDrivenStylePreset configuration

    Raises:
        ValueError: If preset not found
    """
    name_lower = name.lower().replace("-", "_").replace(" ", "_")
    if name_lower not in STYLE_PRESETS:
        available = ", ".join(sorted(STYLE_PRESETS.keys()))
        raise ValueError(f"Unknown preset '{name}'. Available: {available}")
    return STYLE_PRESETS[name_lower]


def list_style_presets() -> Dict[str, str]:
    """List all available presets with descriptions.

    Returns:
        Dict mapping preset name to description
    """
    return {name: preset.description for name, preset in STYLE_PRESETS.items()}


def get_seasonal_presets() -> List[str]:
    """Get list of season-based presets."""
    return ["spring", "summer", "autumn", "winter"]


def get_creative_presets() -> List[str]:
    """Get list of creative/stylized presets."""
    return ["cyberpunk", "watercolor", "vintage"]
