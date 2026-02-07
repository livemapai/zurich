"""
GeoJSON vector data loader with spatial indexing.

Loads and indexes building footprints and tree positions for efficient
tile-based queries. Uses a simple bounding box index when rtree is not
available, or rtree for better performance with large datasets.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

import numpy as np
from numpy.typing import NDArray


@dataclass
class Feature:
    """Simplified feature representation for shadow casting."""

    id: int
    geometry_type: str
    coordinates: list  # Varies by geometry type
    height: float  # Building height or tree height
    properties: dict = field(default_factory=dict)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """Get bounding box (min_x, min_y, max_x, max_y)."""
        if self.geometry_type == "Point":
            x, y = self.coordinates
            return (x, y, x, y)
        elif self.geometry_type == "Polygon":
            # Flatten all rings
            all_coords = []
            for ring in self.coordinates:
                all_coords.extend(ring)
            xs = [c[0] for c in all_coords]
            ys = [c[1] for c in all_coords]
            return (min(xs), min(ys), max(xs), max(ys))
        elif self.geometry_type == "MultiPolygon":
            all_coords = []
            for polygon in self.coordinates:
                for ring in polygon:
                    all_coords.extend(ring)
            xs = [c[0] for c in all_coords]
            ys = [c[1] for c in all_coords]
            return (min(xs), min(ys), max(xs), max(ys))
        elif self.geometry_type == "LineString":
            # LineString: coordinates is list of [x, y] points
            xs = [c[0] for c in self.coordinates]
            ys = [c[1] for c in self.coordinates]
            return (min(xs), min(ys), max(xs), max(ys))
        elif self.geometry_type == "MultiLineString":
            # MultiLineString: coordinates is list of lines
            all_coords = []
            for line in self.coordinates:
                all_coords.extend(line)
            xs = [c[0] for c in all_coords]
            ys = [c[1] for c in all_coords]
            return (min(xs), min(ys), max(xs), max(ys))
        else:
            raise ValueError(f"Unsupported geometry type: {self.geometry_type}")


class VectorSource:
    """Manages loading and spatial queries for vector data."""

    def __init__(self, geojson_path: Path, height_field: str = "height"):
        """Initialize vector source from GeoJSON file.

        Args:
            geojson_path: Path to GeoJSON file
            height_field: Property name for feature height
        """
        self.path = geojson_path
        self.height_field = height_field
        self.features: list[Feature] = []
        self._index: Optional[object] = None  # rtree.Index or None
        self._bounds_list: list[tuple[float, float, float, float]] = []

        self._load()

    def _load(self) -> None:
        """Load and index features from GeoJSON."""
        with open(self.path) as f:
            data = json.load(f)

        for i, feature in enumerate(data.get("features", [])):
            geom = feature.get("geometry", {})
            props = feature.get("properties", {})

            # Get height, with fallbacks
            height = props.get(self.height_field)
            if height is None:
                # Try common alternative names
                height = props.get("hoehe") or props.get("HOEHE") or 0
            if height is None or height == "":
                height = 0

            try:
                height = float(height)
            except (ValueError, TypeError):
                height = 0

            feat = Feature(
                id=i,
                geometry_type=geom.get("type", ""),
                coordinates=geom.get("coordinates", []),
                height=height,
                properties=props,
            )

            self.features.append(feat)
            self._bounds_list.append(feat.bounds)

        # Try to build rtree index
        self._build_index()

    def _build_index(self) -> None:
        """Build spatial index if rtree is available."""
        try:
            from rtree import index

            self._index = index.Index()
            for i, bounds in enumerate(self._bounds_list):
                self._index.insert(i, bounds)
        except ImportError:
            # Fall back to simple bounds checking
            self._index = None

    def query(
        self,
        bounds: tuple[float, float, float, float],
        min_height: float = 0,
    ) -> Iterator[Feature]:
        """Query features within bounding box.

        Args:
            bounds: (min_x, min_y, max_x, max_y) in same CRS as data
            min_height: Minimum height filter

        Yields:
            Features intersecting the bounds
        """
        min_x, min_y, max_x, max_y = bounds

        if self._index is not None:
            # Use rtree
            candidate_ids = list(self._index.intersection(bounds))
        else:
            # Brute force bbox check
            candidate_ids = []
            for i, fb in enumerate(self._bounds_list):
                fb_min_x, fb_min_y, fb_max_x, fb_max_y = fb
                # Check for intersection
                if not (fb_max_x < min_x or fb_min_x > max_x or
                        fb_max_y < min_y or fb_min_y > max_y):
                    candidate_ids.append(i)

        for idx in candidate_ids:
            feat = self.features[idx]
            if feat.height >= min_height:
                yield feat

    def __len__(self) -> int:
        return len(self.features)


def query_features_in_tile(
    source: VectorSource,
    tile_bounds: tuple[float, float, float, float],
    buffer_meters: float = 100,
    min_height: float = 0,
) -> list[Feature]:
    """Query features within a tile, with buffer for shadows.

    Shadows can extend beyond the tile boundary, so we need to query
    a larger area to capture all relevant features.

    Args:
        source: VectorSource to query
        tile_bounds: (west, south, east, north) in WGS84 degrees
        buffer_meters: Buffer around tile in meters
        min_height: Minimum feature height to include

    Returns:
        List of features
    """
    west, south, east, north = tile_bounds

    # Convert buffer from meters to degrees (approximate for Zurich)
    # At 47°N: 1° lat ≈ 111km, 1° lon ≈ 76km
    lat_buffer = buffer_meters / 111000
    lon_buffer = buffer_meters / 76000

    buffered_bounds = (
        west - lon_buffer,
        south - lat_buffer,
        east + lon_buffer,
        north + lat_buffer,
    )

    return list(source.query(buffered_bounds, min_height))


def load_buildings(
    path: Path,
    height_field: str = "height",
) -> VectorSource:
    """Load building footprints from GeoJSON.

    Args:
        path: Path to buildings GeoJSON
        height_field: Property containing building height in meters

    Returns:
        VectorSource ready for queries
    """
    return VectorSource(path, height_field)


def load_trees(
    path: Path,
    height_field: str = "estimated_height",
) -> VectorSource:
    """Load tree positions from GeoJSON.

    Note: Stadt Zürich Baumkataster doesn't have true heights,
    so we use estimated_height which is derived from crown diameter.

    Args:
        path: Path to trees GeoJSON
        height_field: Property containing tree height estimate

    Returns:
        VectorSource ready for queries
    """
    return VectorSource(path, height_field)


def estimate_tree_height(crown_diameter: float) -> float:
    """Estimate tree height from crown diameter.

    Based on typical tree proportions. Used when actual height is unavailable.

    Args:
        crown_diameter: Crown diameter in meters

    Returns:
        Estimated height in meters
    """
    # Most trees are 1.2-1.8x their crown diameter in height
    # Cap at 35m (typical max for urban trees)
    return min(crown_diameter * 1.5, 35.0)


def load_streets(
    path: Path,
    width_field: str = "width",
) -> VectorSource:
    """Load street centerlines from GeoJSON.

    Streets are LineString geometries representing road centerlines.
    The width field contains the road width in meters for buffering.

    Args:
        path: Path to streets GeoJSON
        width_field: Property containing road width in meters

    Returns:
        VectorSource ready for queries
    """
    return VectorSource(path, width_field)


def load_water_bodies(
    path: Path,
    width_field: str = "width",
) -> VectorSource:
    """Load water bodies from GeoJSON.

    Water bodies can be:
    - Polygon/MultiPolygon: Lakes, ponds (use directly)
    - LineString/MultiLineString: Rivers, streams (need buffering)

    The width field contains river width for LineString features.

    Args:
        path: Path to water bodies GeoJSON
        width_field: Property containing river width in meters

    Returns:
        VectorSource ready for queries
    """
    return VectorSource(path, width_field)


def polygon_to_pixel_mask(
    polygon_coords: list[list[tuple[float, float]]],
    bounds: tuple[float, float, float, float],
    size: int,
) -> NDArray[np.bool_]:
    """Rasterize a polygon to a pixel mask.

    Args:
        polygon_coords: List of rings, each ring is list of (x, y) coordinates
        bounds: (min_x, min_y, max_x, max_y) for the output grid
        size: Output grid size (size × size pixels)

    Returns:
        Boolean mask of shape (size, size)
    """
    from PIL import Image, ImageDraw

    min_x, min_y, max_x, max_y = bounds
    x_scale = size / (max_x - min_x)
    y_scale = size / (max_y - min_y)

    # Create image
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)

    # Transform and draw each ring
    for ring in polygon_coords:
        pixel_coords = []
        for x, y in ring:
            px = int((x - min_x) * x_scale)
            # Flip Y axis (image origin is top-left)
            py = int(size - (y - min_y) * y_scale)
            pixel_coords.append((px, py))

        if len(pixel_coords) >= 3:
            draw.polygon(pixel_coords, fill=255)

    return np.array(img) > 0
