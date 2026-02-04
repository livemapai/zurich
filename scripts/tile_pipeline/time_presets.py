"""
Time-of-day lighting presets for the tile rendering pipeline.

Each preset configures sun position, color temperature, and shadow parameters
to create a specific mood or lighting condition. Presets are based on typical
sun positions in Zurich (47.4°N latitude).

Sun positions are simplified approximations - for precise calculations,
use pysolar or similar ephemeris library.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TimePreset:
    """Complete lighting configuration for a time of day."""

    name: str
    description: str

    # Sun position
    azimuth: float  # Degrees from north (0=N, 90=E, 180=S, 270=W)
    altitude: float  # Degrees above horizon

    # Color temperature (Kelvin, for future use in white balance)
    color_temperature: int

    # Shadow parameters
    shadow_darkness: float  # 0-1, how dark shadows appear
    shadow_softness: float  # 0-1, how soft shadow edges are

    # Imhof color shift strengths
    warm_strength: float  # 0-1, yellow tint on sunny slopes
    cool_strength: float  # 0-1, blue tint on shaded slopes

    # Ambient light level
    ambient_level: float  # 0-1, overall brightness


# Predefined time presets
PRESETS: dict[str, TimePreset] = {
    "morning_golden": TimePreset(
        name="Morning Golden Hour",
        description="Early morning with warm, low-angle light from the east-southeast",
        azimuth=95.0,   # ESE
        altitude=15.0,  # Low sun, long shadows
        color_temperature=3500,  # Warm orange
        shadow_darkness=0.5,     # Lighter shadows (more fill light)
        shadow_softness=0.4,     # Moderate softness
        warm_strength=0.5,       # Strong warm tint
        cool_strength=0.2,       # Subtle cool tint
        ambient_level=0.6,
    ),

    "morning": TimePreset(
        name="Mid-Morning",
        description="Pleasant morning light from the southeast",
        azimuth=120.0,  # SE
        altitude=30.0,
        color_temperature=4500,
        shadow_darkness=0.55,
        shadow_softness=0.3,
        warm_strength=0.35,
        cool_strength=0.25,
        ambient_level=0.7,
    ),

    "noon": TimePreset(
        name="High Noon",
        description="Harsh midday light from the south, short shadows",
        azimuth=180.0,  # S
        altitude=55.0,  # High sun (summer-ish)
        color_temperature=5500,  # Neutral daylight
        shadow_darkness=0.7,     # Darker, more contrast
        shadow_softness=0.2,     # Sharper edges
        warm_strength=0.2,       # Minimal color shift
        cool_strength=0.2,
        ambient_level=0.85,
    ),

    "afternoon": TimePreset(
        name="Afternoon",
        description="Classic afternoon light from the southwest",
        azimuth=240.0,  # SW
        altitude=35.0,
        color_temperature=5000,
        shadow_darkness=0.6,
        shadow_softness=0.3,
        warm_strength=0.3,
        cool_strength=0.35,
        ambient_level=0.75,
    ),

    "evening_golden": TimePreset(
        name="Evening Golden Hour",
        description="Warm sunset light from the west, dramatic long shadows",
        azimuth=280.0,  # W
        altitude=12.0,  # Very low sun
        color_temperature=3200,  # Deep warm
        shadow_darkness=0.45,    # Softer shadows (more ambient)
        shadow_softness=0.5,     # Soft edges
        warm_strength=0.6,       # Strong warm tint
        cool_strength=0.15,      # Minimal cool (warm ambient)
        ambient_level=0.55,
    ),

    "overcast": TimePreset(
        name="Overcast",
        description="Diffuse light with minimal shadows, even illumination",
        azimuth=180.0,  # Direction doesn't matter much
        altitude=45.0,
        color_temperature=6500,  # Cool, cloudy
        shadow_darkness=0.2,     # Very faint shadows
        shadow_softness=0.8,     # Very soft
        warm_strength=0.1,
        cool_strength=0.15,      # Slight cool cast
        ambient_level=0.8,
    ),

    "twilight": TimePreset(
        name="Civil Twilight",
        description="Post-sunset blue hour, sun below horizon",
        azimuth=290.0,  # WNW (where sun set)
        altitude=5.0,   # Just below horizon effect
        color_temperature=7500,  # Cool blue
        shadow_darkness=0.25,
        shadow_softness=0.7,
        warm_strength=0.0,       # No warm tint
        cool_strength=0.5,       # Strong cool cast
        ambient_level=0.4,
    ),

    "dramatic": TimePreset(
        name="Dramatic",
        description="High contrast theatrical lighting for impact",
        azimuth=270.0,  # W
        altitude=20.0,
        color_temperature=4000,
        shadow_darkness=0.85,    # Very dark shadows
        shadow_softness=0.15,    # Sharp edges
        warm_strength=0.4,
        cool_strength=0.5,       # Strong contrast
        ambient_level=0.5,
    ),

    "flat": TimePreset(
        name="Flat",
        description="Minimal relief for base map use, very subtle shading",
        azimuth=315.0,  # NW (classic cartographic)
        altitude=60.0,
        color_temperature=5500,
        shadow_darkness=0.3,
        shadow_softness=0.6,
        warm_strength=0.1,
        cool_strength=0.1,
        ambient_level=0.9,
    ),
}


def get_preset(name: str) -> TimePreset:
    """Get a time preset by name.

    Args:
        name: Preset name (case-insensitive)

    Returns:
        TimePreset configuration

    Raises:
        KeyError: If preset name not found
    """
    name_lower = name.lower().replace(" ", "_").replace("-", "_")
    if name_lower not in PRESETS:
        available = ", ".join(sorted(PRESETS.keys()))
        raise KeyError(f"Unknown preset '{name}'. Available: {available}")
    return PRESETS[name_lower]


def list_presets() -> list[str]:
    """List all available preset names."""
    return sorted(PRESETS.keys())


def calculate_sun_position(
    latitude: float,
    longitude: float,
    datetime_utc: Optional[str] = None,
) -> tuple[float, float]:
    """Calculate sun position for a given location and time.

    This is a simplified calculation. For precise results, use pysolar.

    Args:
        latitude: Latitude in degrees
        longitude: Longitude in degrees
        datetime_utc: ISO format datetime string (e.g., "2024-07-15T14:00:00")
                     If None, returns a default afternoon position.

    Returns:
        Tuple of (azimuth, altitude) in degrees
    """
    if datetime_utc is None:
        # Default to afternoon position for Zurich
        return (240.0, 35.0)

    # Try to use pysolar if available
    try:
        from pysolar import solar
        from datetime import datetime

        dt = datetime.fromisoformat(datetime_utc.replace("Z", "+00:00"))
        altitude = solar.get_altitude(latitude, longitude, dt)
        azimuth = solar.get_azimuth(latitude, longitude, dt)
        # pysolar uses different azimuth convention, convert to ours
        # pysolar: 0=S, 90=W, -90=E
        # ours: 0=N, 90=E, 180=S, 270=W
        azimuth = (180 - azimuth) % 360

        return (azimuth, max(0, altitude))

    except ImportError:
        # Fallback: return preset based on rough time of day
        import re

        match = re.search(r"T(\d{2}):", datetime_utc)
        if match:
            hour = int(match.group(1))
            if hour < 9:
                return get_preset("morning_golden").azimuth, get_preset("morning_golden").altitude
            elif hour < 12:
                return get_preset("morning").azimuth, get_preset("morning").altitude
            elif hour < 15:
                return get_preset("noon").azimuth, get_preset("noon").altitude
            elif hour < 18:
                return get_preset("afternoon").azimuth, get_preset("afternoon").altitude
            else:
                return get_preset("evening_golden").azimuth, get_preset("evening_golden").altitude

        return (240.0, 35.0)  # Default afternoon


def create_custom_preset(
    azimuth: float,
    altitude: float,
    **overrides: float,
) -> TimePreset:
    """Create a custom preset with specific sun position.

    Starts with "afternoon" defaults and applies overrides.

    Args:
        azimuth: Sun azimuth in degrees
        altitude: Sun altitude in degrees
        **overrides: Any TimePreset field to override

    Returns:
        Custom TimePreset
    """
    base = PRESETS["afternoon"]

    return TimePreset(
        name=overrides.get("name", "Custom"),
        description=overrides.get("description", f"Custom preset (az={azimuth}°, alt={altitude}°)"),
        azimuth=azimuth,
        altitude=altitude,
        color_temperature=int(overrides.get("color_temperature", base.color_temperature)),
        shadow_darkness=overrides.get("shadow_darkness", base.shadow_darkness),
        shadow_softness=overrides.get("shadow_softness", base.shadow_softness),
        warm_strength=overrides.get("warm_strength", base.warm_strength),
        cool_strength=overrides.get("cool_strength", base.cool_strength),
        ambient_level=overrides.get("ambient_level", base.ambient_level),
    )
