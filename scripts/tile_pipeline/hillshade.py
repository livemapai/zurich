"""
Hillshade computation with Imhof-style color tinting.

Implements Horn's hillshade algorithm plus multi-directional lighting
following Eduard Imhof's Swiss cartographic tradition. Includes warm/cool
color shifts to enhance depth perception.

References:
- Horn, B.K.P. (1981) "Hill shading and the reflectance map"
- Imhof, E. (1982) "Cartographic Relief Presentation"
- ESRI multi-directional hillshade (ArcGIS)
"""

import numpy as np
from numpy.typing import NDArray

from .sources.elevation import compute_slope_aspect


def horn_hillshade(
    elevation: NDArray[np.float32],
    cell_size: float,
    azimuth: float = 315.0,
    altitude: float = 45.0,
) -> NDArray[np.float32]:
    """Compute hillshade using Horn's algorithm.

    This is the classic single-light-source hillshade used in most GIS software.

    Args:
        elevation: Elevation array in meters
        cell_size: Size of each cell in meters
        azimuth: Sun azimuth in degrees (0=N, 90=E, 180=S, 270=W)
        altitude: Sun altitude in degrees above horizon (0-90)

    Returns:
        Hillshade array with values 0-1 (0=shadow, 1=bright)
    """
    # Compute slope and aspect
    slope, aspect = compute_slope_aspect(elevation, cell_size)

    # Convert sun position to radians
    zenith = np.radians(90 - altitude)
    azimuth_rad = np.radians(azimuth)

    # Horn's hillshade formula
    hillshade = (
        np.cos(zenith) * np.cos(slope) +
        np.sin(zenith) * np.sin(slope) * np.cos(azimuth_rad - aspect)
    )

    # Normalize to 0-1 range
    return np.clip(hillshade, 0, 1).astype(np.float32)


def multidirectional_hillshade(
    elevation: NDArray[np.float32],
    cell_size: float,
    altitude: float = 45.0,
) -> NDArray[np.float32]:
    """Compute multi-directional hillshade following Imhof's method.

    Uses 5 light sources with Imhof's traditional weights:
    - NW (315°): 50% - primary illumination
    - W (270°), N (0°), SW (225°), NE (45°): 12.5% each

    This eliminates the "flat spots" that appear when terrain faces
    directly away from a single light source.

    Args:
        elevation: Elevation array in meters
        cell_size: Size of each cell in meters
        altitude: Sun altitude in degrees above horizon

    Returns:
        Hillshade array with values 0-1
    """
    # Imhof weights for 5 light sources
    azimuths = [315, 270, 0, 225, 45]
    weights = [0.50, 0.125, 0.125, 0.125, 0.125]

    # Compute weighted sum
    result = np.zeros_like(elevation, dtype=np.float32)
    for azimuth, weight in zip(azimuths, weights):
        hs = horn_hillshade(elevation, cell_size, azimuth, altitude)
        result += hs * weight

    return result


def compute_illumination_mask(
    elevation: NDArray[np.float32],
    cell_size: float,
    azimuth: float = 315.0,
    altitude: float = 45.0,
) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    """Compute separate lit and shadow masks for color tinting.

    Returns two masks:
    - lit_mask: Areas facing the sun (for warm tint)
    - shadow_mask: Areas facing away from sun (for cool tint)

    Args:
        elevation: Elevation array in meters
        cell_size: Size of each cell in meters
        azimuth: Sun azimuth in degrees
        altitude: Sun altitude in degrees

    Returns:
        Tuple of (lit_mask, shadow_mask) with values 0-1
    """
    slope, aspect = compute_slope_aspect(elevation, cell_size)
    azimuth_rad = np.radians(azimuth)

    # Compute how much each pixel faces the sun
    # cos(azimuth - aspect) is +1 when facing sun, -1 when facing away
    sun_facing = np.cos(azimuth_rad - aspect)

    # Also factor in slope steepness
    slope_factor = np.sin(slope)

    # Lit mask: facing sun AND steep enough to matter
    lit_mask = np.clip(sun_facing * slope_factor + 0.5, 0, 1)

    # Shadow mask: facing away from sun
    shadow_mask = np.clip(-sun_facing * slope_factor + 0.5, 0, 1)

    return lit_mask.astype(np.float32), shadow_mask.astype(np.float32)


def imhof_color_shift(
    hillshade: NDArray[np.float32],
    elevation: NDArray[np.float32],
    cell_size: float,
    azimuth: float = 315.0,
    warm_strength: float = 0.3,
    cool_strength: float = 0.4,
) -> tuple[NDArray[np.float32], NDArray[np.float32], NDArray[np.float32]]:
    """Compute Imhof-style color shift values for LAB space.

    Generates shift values for the LAB 'a' and 'b' channels:
    - Sunny slopes: shift toward yellow (+b) and slightly red (+a)
    - Shaded slopes: shift toward blue (-b) and slightly green (-a)

    This creates the characteristic warm/cool contrast of Swiss maps.

    Args:
        hillshade: Hillshade array (0-1)
        elevation: Elevation array in meters
        cell_size: Cell size in meters
        azimuth: Sun azimuth in degrees
        warm_strength: Strength of warm tint (0-1)
        cool_strength: Strength of cool tint (0-1)

    Returns:
        Tuple of (shift_L, shift_a, shift_b) arrays
        - shift_L: Lightness modification (usually 0)
        - shift_a: Red-green axis shift
        - shift_b: Yellow-blue axis shift
    """
    lit_mask, shadow_mask = compute_illumination_mask(
        elevation, cell_size, azimuth
    )

    # LAB color shift values
    # Warm tint (sunlit): slightly red (+a), yellow (+b)
    warm_a = 5.0 * warm_strength
    warm_b = 15.0 * warm_strength

    # Cool tint (shadow): slightly green (-a), blue (-b)
    cool_a = -3.0 * cool_strength
    cool_b = -12.0 * cool_strength

    # Apply based on illumination
    shift_a = lit_mask * warm_a + shadow_mask * cool_a
    shift_b = lit_mask * warm_b + shadow_mask * cool_b

    # No lightness shift (handled by hillshade blend)
    shift_L = np.zeros_like(shift_a)

    return shift_L, shift_a, shift_b


def create_hillshade_layer(
    elevation: NDArray[np.float32],
    cell_size: float,
    azimuth: float = 315.0,
    altitude: float = 45.0,
    multidirectional: bool = True,
) -> NDArray[np.float32]:
    """Create a hillshade layer ready for blending.

    Converts hillshade values to blend-ready format where:
    - 0.5 = neutral (no change when soft-light blended)
    - < 0.5 = darken
    - > 0.5 = lighten

    Args:
        elevation: Elevation array in meters
        cell_size: Cell size in meters
        azimuth: Sun azimuth (for single-source mode)
        altitude: Sun altitude in degrees
        multidirectional: Use Imhof multi-directional lighting

    Returns:
        Hillshade array scaled for soft-light blending (0-1)
    """
    if multidirectional:
        hs = multidirectional_hillshade(elevation, cell_size, altitude)
    else:
        hs = horn_hillshade(elevation, cell_size, azimuth, altitude)

    # Scale to 0.3-0.7 range for softer effect
    # This prevents over-darkening or over-brightening
    return 0.3 + hs * 0.4


def ambient_light_estimation(
    elevation: NDArray[np.float32],
    cell_size: float,
    search_radius: int = 5,
) -> NDArray[np.float32]:
    """Estimate ambient light based on local terrain openness.

    Valleys receive less ambient light than ridges. This is computed
    by comparing each cell's elevation to its neighborhood.

    Args:
        elevation: Elevation array in meters
        cell_size: Cell size in meters (unused, for API consistency)
        search_radius: Radius in cells for neighborhood analysis

    Returns:
        Ambient light factor (0-1) where 0 = enclosed valley, 1 = exposed ridge
    """
    from scipy.ndimage import uniform_filter

    # Local mean elevation
    local_mean = uniform_filter(elevation, size=2 * search_radius + 1, mode="nearest")

    # Difference from local mean
    relative_height = elevation - local_mean

    # Normalize: positive = above average (more light), negative = below
    max_diff = np.percentile(np.abs(relative_height), 95) + 0.01

    # Map to 0.5-1.0 range (even valleys get some ambient light)
    ambient = 0.5 + 0.5 * np.clip(relative_height / max_diff, -1, 1)

    return ambient.astype(np.float32)


def compute_hillshade_with_imhof(
    elevation: NDArray[np.float32],
    cell_size: float,
    azimuth: float = 240.0,
    altitude: float = 35.0,
    warm_strength: float = 0.3,
    cool_strength: float = 0.4,
) -> dict[str, NDArray[np.float32]]:
    """Compute complete hillshade package for tile compositing.

    Returns all components needed for Imhof-style relief:
    - hillshade: Main hillshade for lightness blending
    - shift_a: Color shift for LAB 'a' channel
    - shift_b: Color shift for LAB 'b' channel
    - ambient: Ambient light estimation

    Args:
        elevation: Elevation array in meters
        cell_size: Cell size in meters
        azimuth: Sun azimuth in degrees
        altitude: Sun altitude in degrees
        warm_strength: Warm tint strength
        cool_strength: Cool tint strength

    Returns:
        Dictionary with 'hillshade', 'shift_a', 'shift_b', 'ambient' arrays
    """
    # Main hillshade (multi-directional)
    hillshade = create_hillshade_layer(
        elevation, cell_size, azimuth, altitude, multidirectional=True
    )

    # Imhof color shifts
    _, shift_a, shift_b = imhof_color_shift(
        hillshade, elevation, cell_size, azimuth, warm_strength, cool_strength
    )

    # Ambient light
    ambient = ambient_light_estimation(elevation, cell_size)

    return {
        "hillshade": hillshade,
        "shift_a": shift_a,
        "shift_b": shift_b,
        "ambient": ambient,
    }
