#!/usr/bin/env python3
"""Tests for GeoJSON validation."""
import pytest
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from validate.check_data import (
    validate_coordinate,
    validate_feature,
    validate_geojson,
    ZURICH_BOUNDS,
)


class TestValidateCoordinate:
    """Tests for coordinate validation."""

    def test_valid_zurich_coordinate(self):
        """Test valid Zurich coordinate passes."""
        error = validate_coordinate(8.54, 47.37)
        assert error is None

    def test_invalid_longitude_too_low(self):
        """Test longitude below bounds fails."""
        error = validate_coordinate(8.0, 47.37)
        assert error is not None
        assert "Longitude" in error

    def test_invalid_longitude_too_high(self):
        """Test longitude above bounds fails."""
        error = validate_coordinate(9.0, 47.37)
        assert error is not None
        assert "Longitude" in error

    def test_invalid_latitude_too_low(self):
        """Test latitude below bounds fails."""
        error = validate_coordinate(8.54, 47.0)
        assert error is not None
        assert "Latitude" in error

    def test_invalid_latitude_too_high(self):
        """Test latitude above bounds fails."""
        error = validate_coordinate(8.54, 48.0)
        assert error is not None
        assert "Latitude" in error

    def test_bounds_edge_values_pass(self):
        """Test coordinates at exact bounds pass."""
        # Test minimum bounds
        error = validate_coordinate(
            ZURICH_BOUNDS["min_lng"],
            ZURICH_BOUNDS["min_lat"]
        )
        assert error is None

        # Test maximum bounds
        error = validate_coordinate(
            ZURICH_BOUNDS["max_lng"],
            ZURICH_BOUNDS["max_lat"]
        )
        assert error is None


class TestValidateFeature:
    """Tests for feature validation."""

    def test_valid_feature_passes(self):
        """Test valid feature has no errors."""
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[8.54, 47.37], [8.55, 47.37], [8.55, 47.38], [8.54, 47.37]]]
            },
            "properties": {
                "id": "test_1",
                "height": 20.0
            }
        }
        errors = validate_feature(feature, 0)
        assert len(errors) == 0

    def test_missing_geometry_fails(self):
        """Test feature without geometry fails."""
        feature = {
            "type": "Feature",
            "properties": {"id": "test_1"}
        }
        errors = validate_feature(feature, 0)
        assert len(errors) > 0
        assert any("Missing geometry" in str(e) for e in errors)

    def test_negative_height_fails(self):
        """Test negative building height is caught."""
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[8.54, 47.37], [8.55, 47.37], [8.54, 47.37]]]
            },
            "properties": {"height": -5}
        }
        errors = validate_feature(feature, 0)
        assert any("Negative height" in str(e) for e in errors)

    def test_unrealistic_height_fails(self):
        """Test unrealistic height (>500m) is caught."""
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[8.54, 47.37], [8.55, 47.37], [8.54, 47.37]]]
            },
            "properties": {"height": 600}
        }
        errors = validate_feature(feature, 0)
        assert any("Unrealistic height" in str(e) for e in errors)

    def test_swapped_coordinates_detected(self):
        """Test lat/lng swap is detected."""
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                # Swapped: [lat, lng] instead of [lng, lat]
                "coordinates": [[[47.37, 8.54], [47.38, 8.55], [47.37, 8.54]]]
            },
            "properties": {}
        }
        errors = validate_feature(feature, 0)
        assert any("swapped" in str(e).lower() for e in errors)


class TestValidateGeojson:
    """Tests for full GeoJSON file validation."""

    def test_valid_file_passes(self):
        """Test valid GeoJSON file passes validation."""
        data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[8.54, 47.37], [8.55, 47.37], [8.55, 47.38], [8.54, 47.37]]]
                    },
                    "properties": {"id": "test_1", "height": 20}
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            json.dump(data, f)
            filepath = Path(f.name)

        is_valid, errors = validate_geojson(filepath, sample_size=0)
        assert is_valid
        assert len(errors) == 0

    def test_missing_file_fails(self):
        """Test missing file returns error."""
        is_valid, errors = validate_geojson(Path("/nonexistent/file.geojson"))
        assert not is_valid
        assert any("not found" in str(e).lower() for e in errors)

    def test_invalid_json_fails(self):
        """Test invalid JSON returns error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            f.write("not valid json {{{")
            filepath = Path(f.name)

        is_valid, errors = validate_geojson(filepath)
        assert not is_valid
        assert any("Invalid JSON" in str(e) for e in errors)

    def test_not_feature_collection_fails(self):
        """Test non-FeatureCollection fails."""
        data = {"type": "Feature", "geometry": None, "properties": {}}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            json.dump(data, f)
            filepath = Path(f.name)

        is_valid, errors = validate_geojson(filepath)
        assert not is_valid
        assert any("FeatureCollection" in str(e) for e in errors)
