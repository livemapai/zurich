#!/usr/bin/env python3
"""Tests for OBJ to GeoJSON conversion."""
import pytest
import numpy as np
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from convert.obj_to_geojson import (
    parse_obj_file,
    extract_footprint,
    convert_obj_to_feature,
    create_sample_buildings,
)


SAMPLE_CUBE_OBJ = """# Simple cube 1x1x1
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
v 0 0 1
v 1 0 1
v 1 1 1
v 0 1 1
f 1 2 3 4
f 5 6 7 8
"""


class TestParseObjFile:
    """Tests for OBJ file parsing."""

    def test_parses_vertices(self):
        """Test vertex parsing from OBJ."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.obj', delete=False) as f:
            f.write(SAMPLE_CUBE_OBJ)
            f.flush()
            result = parse_obj_file(Path(f.name))

        assert 'vertices' in result
        assert len(result['vertices']) == 8

    def test_parses_faces(self):
        """Test face parsing from OBJ."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.obj', delete=False) as f:
            f.write(SAMPLE_CUBE_OBJ)
            f.flush()
            result = parse_obj_file(Path(f.name))

        assert 'faces' in result
        assert len(result['faces']) == 2

    def test_vertex_coordinates_correct(self):
        """Test vertex coordinates are parsed correctly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.obj', delete=False) as f:
            f.write(SAMPLE_CUBE_OBJ)
            f.flush()
            result = parse_obj_file(Path(f.name))

        vertices = result['vertices']
        # First vertex should be [0, 0, 0]
        assert np.allclose(vertices[0], [0, 0, 0])
        # Last vertex should be [0, 1, 1]
        assert np.allclose(vertices[-1], [0, 1, 1])

    def test_handles_comments(self):
        """Test that comments are ignored."""
        obj_with_comments = """# This is a comment
        v 1 2 3
        # Another comment
        v 4 5 6
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.obj', delete=False) as f:
            f.write(obj_with_comments)
            f.flush()
            result = parse_obj_file(Path(f.name))

        assert len(result['vertices']) == 2


class TestExtractFootprint:
    """Tests for building footprint extraction."""

    def test_extracts_base_elevation(self):
        """Test base elevation is minimum Z."""
        vertices = np.array([
            [0, 0, 10],
            [1, 0, 10],
            [1, 1, 10],
            [0, 1, 10],
            [0, 0, 20],
            [1, 0, 20],
            [1, 1, 20],
            [0, 1, 20],
        ])
        _, base_elevation, _ = extract_footprint(vertices, [])

        assert base_elevation == 10.0

    def test_calculates_height(self):
        """Test height is difference between max and min Z."""
        vertices = np.array([
            [0, 0, 100],
            [1, 0, 100],
            [0, 0, 150],
            [1, 0, 150],
        ])
        _, _, height = extract_footprint(vertices, [])

        assert height == 50.0

    def test_empty_vertices_returns_empty(self):
        """Test empty input returns empty footprint."""
        vertices = np.array([])
        footprint, base, height = extract_footprint(vertices.reshape(0, 3), [])

        assert len(footprint) == 0
        assert base == 0
        assert height == 0


class TestCreateSampleBuildings:
    """Tests for sample building generation."""

    def test_creates_correct_count(self):
        """Test correct number of buildings are created."""
        import json

        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            output_path = Path(f.name)

        create_sample_buildings(output_path, count=50)

        with open(output_path) as f:
            data = json.load(f)

        assert len(data['features']) == 50

    def test_features_have_required_properties(self):
        """Test features have height and baseElevation."""
        import json

        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            output_path = Path(f.name)

        create_sample_buildings(output_path, count=10)

        with open(output_path) as f:
            data = json.load(f)

        for feature in data['features']:
            assert 'height' in feature['properties']
            assert 'baseElevation' in feature['properties']
            assert feature['properties']['height'] > 0

    def test_output_is_valid_geojson(self):
        """Test output is valid GeoJSON FeatureCollection."""
        import json

        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            output_path = Path(f.name)

        create_sample_buildings(output_path, count=5)

        with open(output_path) as f:
            data = json.load(f)

        assert data['type'] == 'FeatureCollection'
        assert 'features' in data
        assert all(f['type'] == 'Feature' for f in data['features'])
