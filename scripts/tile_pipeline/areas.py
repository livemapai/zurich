"""
Predefined area bounds for Zürich neighborhoods.

Usage:
    from tile_pipeline.areas import AREAS, get_area_bounds

    # Get bounds for a neighborhood
    bounds = get_area_bounds("hauptbahnhof")

    # List all areas
    for name, area in AREAS.items():
        print(f"{name}: {area.description}")
"""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class Area:
    """A named geographic area with bounds."""

    name: str
    description: str
    bounds: Tuple[float, float, float, float]  # west, south, east, north

    @property
    def center(self) -> Tuple[float, float]:
        """Return center point (lng, lat)."""
        w, s, e, n = self.bounds
        return ((w + e) / 2, (s + n) / 2)

    @property
    def bounds_str(self) -> str:
        """Return bounds as comma-separated string."""
        return ",".join(f"{x:.4f}" for x in self.bounds)


# Predefined Zürich areas
AREAS: Dict[str, Area] = {
    # Central landmarks
    "hauptbahnhof": Area(
        "Hauptbahnhof",
        "Main train station and Europaallee",
        (8.535, 47.375, 8.545, 47.382),
    ),
    "bellevue": Area(
        "Bellevue",
        "Bellevue square and Sechseläutenplatz",
        (8.543, 47.365, 8.548, 47.372),
    ),
    "limmatquai": Area(
        "Limmatquai",
        "River promenade with historic buildings",
        (8.540, 47.368, 8.548, 47.378),
    ),
    "niederdorf": Area(
        "Niederdorf",
        "Old town pedestrian zone",
        (8.538, 47.368, 8.548, 47.375),
    ),
    "bahnhofstrasse": Area(
        "Bahnhofstrasse",
        "Main shopping street",
        (8.536, 47.367, 8.542, 47.378),
    ),
    # University area
    "eth": Area(
        "ETH/University",
        "ETH Zentrum and University of Zürich",
        (8.545, 47.375, 8.555, 47.382),
    ),
    "polyterrasse": Area(
        "Polyterrasse",
        "ETH terrace with city views",
        (8.545, 47.375, 8.550, 47.378),
    ),
    # Churches
    "grossmuenster": Area(
        "Grossmünster",
        "Iconic twin-tower church",
        (8.543, 47.369, 8.547, 47.372),
    ),
    "fraumuenster": Area(
        "Fraumünster",
        "Church with Chagall windows",
        (8.540, 47.368, 8.544, 47.371),
    ),
    "landesmuseum": Area(
        "Landesmuseum",
        "Swiss National Museum",
        (8.537, 47.378, 8.542, 47.382),
    ),
    # Districts
    "zurich_west": Area(
        "Zürich West",
        "Former industrial area, now trendy district",
        (8.500, 47.385, 8.525, 47.400),
    ),
    "oerlikon": Area(
        "Oerlikon",
        "Northern business district",
        (8.540, 47.400, 8.570, 47.420),
    ),
    "seefeld": Area(
        "Seefeld",
        "Lakeside residential area",
        (8.548, 47.350, 8.565, 47.368),
    ),
    "enge": Area(
        "Enge",
        "Wealthy residential area near lake",
        (8.525, 47.355, 8.545, 47.368),
    ),
    "wiedikon": Area(
        "Wiedikon",
        "Residential district south of center",
        (8.505, 47.365, 8.535, 47.380),
    ),
    "altstetten": Area(
        "Altstetten",
        "Western residential and commercial district",
        (8.475, 47.385, 8.505, 47.405),
    ),
    "wipkingen": Area(
        "Wipkingen",
        "Charming hillside neighborhood",
        (8.520, 47.390, 8.540, 47.405),
    ),
    # Lakefront
    "buerkliplatz": Area(
        "Bürkliplatz",
        "Lake promenade and boat landings",
        (8.538, 47.363, 8.544, 47.368),
    ),
    "utoquai": Area(
        "Utoquai",
        "Eastern lakefront promenade",
        (8.544, 47.355, 8.555, 47.368),
    ),
    # Demo/Test areas
    "city_center": Area(
        "City Center",
        "Core downtown area (good for demos)",
        (8.530, 47.365, 8.555, 47.385),
    ),
    "demo_small": Area(
        "Demo (Small)",
        "Tiny test area - ~4 tiles at z16",
        (8.538, 47.374, 8.544, 47.378),
    ),
    "demo_medium": Area(
        "Demo (Medium)",
        "Medium test area - ~16 tiles at z16",
        (8.535, 47.370, 8.550, 47.380),
    ),
    # Full coverage
    "full_zurich": Area(
        "Full Zürich",
        "Complete city coverage (~700 tiles at z16)",
        (8.440, 47.320, 8.630, 47.440),
    ),
}


def get_area_bounds(name: str) -> Tuple[float, float, float, float]:
    """
    Get bounds for a named area.

    Args:
        name: Area name (case-insensitive, underscores/hyphens/spaces normalized)

    Returns:
        Tuple of (west, south, east, north) coordinates

    Raises:
        ValueError: If area name is not found
    """
    # Normalize the key
    key = name.lower().replace(" ", "_").replace("-", "_")

    if key not in AREAS:
        available = ", ".join(sorted(AREAS.keys()))
        raise ValueError(f"Unknown area '{name}'. Available: {available}")

    return AREAS[key].bounds


def get_area(name: str) -> Area:
    """
    Get an Area object by name.

    Args:
        name: Area name (case-insensitive, underscores/hyphens/spaces normalized)

    Returns:
        Area object with name, description, and bounds

    Raises:
        ValueError: If area name is not found
    """
    key = name.lower().replace(" ", "_").replace("-", "_")

    if key not in AREAS:
        available = ", ".join(sorted(AREAS.keys()))
        raise ValueError(f"Unknown area '{name}'. Available: {available}")

    return AREAS[key]


def list_areas() -> None:
    """Print all available areas to stdout."""
    print("Available Zürich areas:\n")

    # Group by category
    categories = {
        "Central": ["hauptbahnhof", "bellevue", "limmatquai", "niederdorf", "bahnhofstrasse"],
        "University": ["eth", "polyterrasse"],
        "Churches & Museums": ["grossmuenster", "fraumuenster", "landesmuseum"],
        "Districts": ["zurich_west", "oerlikon", "seefeld", "enge", "wiedikon", "altstetten", "wipkingen"],
        "Lakefront": ["buerkliplatz", "utoquai"],
        "Demo/Test": ["demo_small", "demo_medium", "city_center"],
        "Full Coverage": ["full_zurich"],
    }

    for category, keys in categories.items():
        print(f"  {category}:")
        for key in keys:
            if key in AREAS:
                area = AREAS[key]
                print(f"    {key:20s} - {area.description}")
        print()


def estimate_tiles(bounds: Tuple[float, float, float, float], zoom: int) -> int:
    """
    Estimate number of tiles for given bounds at a zoom level.

    Args:
        bounds: (west, south, east, north) coordinates
        zoom: Zoom level

    Returns:
        Estimated tile count
    """
    import math

    w, s, e, n = bounds

    def lng_to_tile_x(lng: float, z: int) -> int:
        return int((lng + 180.0) / 360.0 * (2**z))

    def lat_to_tile_y(lat: float, z: int) -> int:
        lat_rad = math.radians(lat)
        return int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * (2**z))

    x_min = lng_to_tile_x(w, zoom)
    x_max = lng_to_tile_x(e, zoom)
    y_min = lat_to_tile_y(n, zoom)  # Note: y is inverted
    y_max = lat_to_tile_y(s, zoom)

    return (x_max - x_min + 1) * (y_max - y_min + 1)


if __name__ == "__main__":
    list_areas()
