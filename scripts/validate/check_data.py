#!/usr/bin/env python3
"""
Validate GeoJSON data for deck.gl compatibility.

Checks:
- Valid GeoJSON structure
- Coordinates in expected range (WGS84 for Zurich)
- Required properties present
- Building heights are reasonable
"""

import json
from pathlib import Path
from typing import Optional
import sys


# Expected bounds for cities in WGS84 (from DATA_SOURCES.md)
ZURICH_BOUNDS = {
    "min_lng": 8.448,
    "max_lng": 8.626,
    "min_lat": 47.320,
    "max_lat": 47.435
}

LUCERNE_BOUNDS = {
    "min_lng": 8.20,
    "max_lng": 8.45,
    "min_lat": 46.95,
    "max_lat": 47.10
}

# Map of city names to bounds
CITY_BOUNDS = {
    "zurich": ZURICH_BOUNDS,
    "lucerne": LUCERNE_BOUNDS,
    "luzern": LUCERNE_BOUNDS,  # German spelling
}


class ValidationError:
    def __init__(self, feature_id: str, issue: str, details: str = ""):
        self.feature_id = feature_id
        self.issue = issue
        self.details = details

    def __str__(self):
        return f"[{self.feature_id}] {self.issue}: {self.details}"


def validate_coordinate(lng: float, lat: float, bounds: dict = ZURICH_BOUNDS) -> Optional[str]:
    """Check if coordinate is within expected bounds."""
    if lng < bounds["min_lng"] or lng > bounds["max_lng"]:
        return f"Longitude {lng} outside bounds [{bounds['min_lng']}, {bounds['max_lng']}]"
    if lat < bounds["min_lat"] or lat > bounds["max_lat"]:
        return f"Latitude {lat} outside bounds [{bounds['min_lat']}, {bounds['max_lat']}]"
    return None


def validate_feature(feature: dict, index: int) -> list[ValidationError]:
    """Validate a single GeoJSON feature."""
    errors = []
    feature_id = feature.get("properties", {}).get("id", f"feature_{index}")

    # Check geometry exists
    if "geometry" not in feature:
        errors.append(ValidationError(feature_id, "Missing geometry"))
        return errors

    geom = feature["geometry"]

    # Check geometry type
    if geom["type"] not in ["Polygon", "MultiPolygon"]:
        errors.append(ValidationError(
            feature_id,
            "Unexpected geometry type",
            f"Got {geom['type']}, expected Polygon or MultiPolygon"
        ))
        return errors

    # Check coordinates
    if "coordinates" not in geom:
        errors.append(ValidationError(feature_id, "Missing coordinates"))
        return errors

    coords = geom["coordinates"]

    # Get sample coordinates to check
    sample_coords = []
    if geom["type"] == "Polygon":
        if coords and coords[0]:
            sample_coords = coords[0][:5]  # First 5 coords of outer ring
    elif geom["type"] == "MultiPolygon":
        if coords and coords[0] and coords[0][0]:
            sample_coords = coords[0][0][:5]

    # Validate sample coordinates
    for coord in sample_coords:
        if len(coord) < 2:
            errors.append(ValidationError(feature_id, "Invalid coordinate", str(coord)))
            continue

        lng, lat = coord[0], coord[1]

        # Check if coordinates are swapped (lat, lng instead of lng, lat)
        if lng > 40 and lat < 10:
            errors.append(ValidationError(
                feature_id,
                "Coordinates appear swapped",
                f"[{lng}, {lat}] looks like [lat, lng]"
            ))
            break

        # Check bounds
        bounds_error = validate_coordinate(lng, lat)
        if bounds_error:
            errors.append(ValidationError(feature_id, "Coordinate out of bounds", bounds_error))
            break

    # Check properties
    props = feature.get("properties", {})

    # Height validation (if present)
    if "height" in props:
        height = props["height"]
        if not isinstance(height, (int, float)):
            errors.append(ValidationError(feature_id, "Invalid height type", str(type(height))))
        elif height < 0:
            errors.append(ValidationError(feature_id, "Negative height", str(height)))
        elif height > 500:
            errors.append(ValidationError(feature_id, "Unrealistic height", f"{height}m"))

    return errors


def validate_geojson(filepath: Path, sample_size: int = 1000) -> tuple[bool, list[ValidationError]]:
    """
    Validate a GeoJSON file.

    Args:
        filepath: Path to GeoJSON file
        sample_size: Number of features to validate (0 = all)

    Returns:
        (is_valid, list of errors)
    """
    errors = []

    # Check file exists
    if not filepath.exists():
        return False, [ValidationError("file", "File not found", str(filepath))]

    # Try to parse
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [ValidationError("file", "Invalid JSON", str(e))]

    # Check structure
    if data.get("type") != "FeatureCollection":
        return False, [ValidationError("file", "Not a FeatureCollection")]

    if "features" not in data or not isinstance(data["features"], list):
        return False, [ValidationError("file", "Missing or invalid features array")]

    features = data["features"]
    total = len(features)

    # Sample features if too many
    if sample_size > 0 and total > sample_size:
        import random
        indices = random.sample(range(total), sample_size)
        sample = [(i, features[i]) for i in indices]
        print(f"Validating {sample_size} of {total} features...")
    else:
        sample = list(enumerate(features))
        print(f"Validating all {total} features...")

    # Validate features
    for index, feature in sample:
        feature_errors = validate_feature(feature, index)
        errors.extend(feature_errors)

        # Stop if too many errors
        if len(errors) > 100:
            errors.append(ValidationError(
                "validation",
                "Too many errors",
                "Stopping after 100 errors"
            ))
            break

    is_valid = len(errors) == 0
    return is_valid, errors


def print_summary(filepath: Path, is_valid: bool, errors: list[ValidationError]) -> None:
    """Print validation summary."""
    print(f"\n{'='*60}")
    print(f"File: {filepath}")
    print(f"Status: {'✓ VALID' if is_valid else '✗ INVALID'}")

    if errors:
        print(f"\nFound {len(errors)} issues:")
        for error in errors[:20]:  # Show first 20
            print(f"  • {error}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")

    print(f"{'='*60}\n")


def get_bounds_for_file(filepath: Path) -> dict:
    """Determine appropriate bounds based on file path."""
    name = filepath.name.lower()
    if "lucerne" in name or "luzern" in name:
        return LUCERNE_BOUNDS
    return ZURICH_BOUNDS


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate GeoJSON data")
    parser.add_argument(
        "file",
        type=Path,
        help="GeoJSON file to validate"
    )
    parser.add_argument(
        "--sample", "-n",
        type=int,
        default=1000,
        help="Number of features to sample (0 = all)"
    )
    parser.add_argument(
        "--bounds", "-b",
        choices=["zurich", "lucerne", "auto"],
        default="auto",
        help="City bounds to validate against (default: auto-detect from filename)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error code if validation fails"
    )

    args = parser.parse_args()

    # Determine bounds
    if args.bounds == "auto":
        bounds = get_bounds_for_file(args.file)
    else:
        bounds = CITY_BOUNDS.get(args.bounds, ZURICH_BOUNDS)

    print(f"Using bounds: {args.bounds if args.bounds != 'auto' else 'auto-detected'}")

    is_valid, errors = validate_geojson(args.file, args.sample)
    print_summary(args.file, is_valid, errors)

    if args.strict and not is_valid:
        sys.exit(1)


if __name__ == "__main__":
    main()
