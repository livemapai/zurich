#!/usr/bin/env python3
"""Tests for coordinate transformation."""
import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from convert.transform_coords import transform_coordinate, transform_ring


# Known reference points (verified with pyproj)
ZURICH_CENTER_LV95 = (2683000, 1248000)
ZURICH_CENTER_WGS84 = (8.5376903, 47.3768627)  # Actual pyproj transformation result


class TestTransformCoordinate:
    """Tests for single coordinate transformation."""

    def test_zurich_center_transformation(self):
        """Test transformation of Zurich city center."""
        lng, lat = transform_coordinate(*ZURICH_CENTER_LV95)
        assert abs(lng - ZURICH_CENTER_WGS84[0]) < 0.001
        assert abs(lat - ZURICH_CENTER_WGS84[1]) < 0.001

    def test_result_within_zurich_bounds(self):
        """Test transformed coords are in WGS84 Zurich bounds."""
        lng, lat = transform_coordinate(2680000, 1245000)
        assert 8.448 <= lng <= 8.626, f"Longitude {lng} out of bounds"
        assert 47.320 <= lat <= 47.435, f"Latitude {lat} out of bounds"

    def test_returns_tuple_of_floats(self):
        """Test return type is tuple of floats."""
        result = transform_coordinate(2683000, 1248000)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(v, float) for v in result)

    def test_precision_is_reasonable(self):
        """Test coordinates have reasonable precision (7 decimal places)."""
        lng, lat = transform_coordinate(2683000, 1248000)
        # Should have at most 7 decimal places
        assert len(str(lng).split('.')[-1]) <= 7
        assert len(str(lat).split('.')[-1]) <= 7


class TestTransformRing:
    """Tests for polygon ring transformation."""

    def test_transforms_all_coordinates(self):
        """Test all coordinates in ring are transformed."""
        ring = [
            [2683000, 1248000],
            [2683100, 1248000],
            [2683100, 1248100],
            [2683000, 1248100],
            [2683000, 1248000],  # Closed ring
        ]
        result = transform_ring(ring)

        assert len(result) == len(ring)
        # All should be in WGS84 range
        for coord in result:
            assert 8.0 < coord[0] < 9.0  # Longitude
            assert 47.0 < coord[1] < 48.0  # Latitude

    def test_preserves_ring_closure(self):
        """Test closed ring remains closed after transformation."""
        ring = [
            [2683000, 1248000],
            [2683100, 1248000],
            [2683000, 1248000],
        ]
        result = transform_ring(ring)
        assert result[0] == result[-1]
