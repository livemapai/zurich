"""
Data source loaders for the tile rendering pipeline.

Provides unified access to:
- SWISSIMAGE satellite imagery (WMTS)
- Mapterhorn terrain elevation (Terrarium-encoded WebP)
- Stadt Zürich vector data (buildings, trees)
"""

from .satellite import fetch_satellite_tile, SatelliteSource
from .elevation import fetch_elevation_tile, decode_terrarium, ElevationSource
from .vector import VectorSource, query_features_in_tile

__all__ = [
    "fetch_satellite_tile",
    "SatelliteSource",
    "fetch_elevation_tile",
    "decode_terrarium",
    "ElevationSource",
    "VectorSource",
    "query_features_in_tile",
]
