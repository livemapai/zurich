#!/usr/bin/env python3
"""Pytest configuration and shared fixtures."""
import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_obj_content():
    """Sample OBJ file content for testing."""
    return """# Sample building
v 2683000 1248000 400
v 2683010 1248000 400
v 2683010 1248010 400
v 2683000 1248010 400
v 2683000 1248000 420
v 2683010 1248000 420
v 2683010 1248010 420
v 2683000 1248010 420
f 1 2 3 4
f 5 6 7 8
f 1 2 6 5
f 2 3 7 6
f 3 4 8 7
f 4 1 5 8
"""


@pytest.fixture
def sample_geojson():
    """Sample GeoJSON for testing."""
    return {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": "EPSG:4326"}
        },
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": "building_001",
                    "height": 20.0,
                    "baseElevation": 400.0
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [8.541, 47.376],
                        [8.542, 47.376],
                        [8.542, 47.377],
                        [8.541, 47.377],
                        [8.541, 47.376]
                    ]]
                }
            }
        ]
    }
