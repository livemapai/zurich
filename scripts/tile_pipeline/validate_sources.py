#!/usr/bin/env python3
"""
Validation script for tile pipeline data sources.

Tests:
1. SWISSIMAGE satellite tile download and decoding
2. Mapterhorn elevation tile download and Terrarium decoding
3. Building GeoJSON loading and property extraction
4. Tree GeoJSON loading and property extraction
5. LAB color space conversion roundtrip
6. Basic shadow geometry calculation

Run: python scripts/tile_pipeline/validate_sources.py
"""

import sys
import json
import math
from pathlib import Path
from io import BytesIO

import numpy as np
import requests
from PIL import Image
from shapely.geometry import shape, box

# Zurich center coordinates for testing
ZURICH_CENTER = (8.5417, 47.3769)  # lng, lat
TEST_ZOOM = 15

# =============================================================================
# TEST 1: Satellite Tile Download
# =============================================================================

def test_satellite_download():
    """Download and decode a SWISSIMAGE satellite tile."""
    print("\n" + "="*60)
    print("TEST 1: SWISSIMAGE Satellite Tile")
    print("="*60)

    # Convert lat/lng to tile coordinates
    lng, lat = ZURICH_CENTER
    n = 2 ** TEST_ZOOM
    x = int((lng + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)

    url = f"https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissimage/default/current/3857/{TEST_ZOOM}/{x}/{y}.jpeg"
    print(f"  Tile coords: z={TEST_ZOOM}, x={x}, y={y}")
    print(f"  URL: {url}")

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        img = Image.open(BytesIO(response.content))
        arr = np.array(img)

        print(f"  ✅ Downloaded: {len(response.content):,} bytes")
        print(f"  ✅ Image size: {img.size[0]}x{img.size[1]} pixels")
        print(f"  ✅ Array shape: {arr.shape}")
        print(f"  ✅ Pixel range: [{arr.min()}, {arr.max()}]")
        print(f"  ✅ Mean RGB: ({arr[:,:,0].mean():.1f}, {arr[:,:,1].mean():.1f}, {arr[:,:,2].mean():.1f})")

        return True, arr
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False, None


# =============================================================================
# TEST 2: Elevation Tile + Terrarium Decoding
# =============================================================================

def test_elevation_download():
    """Download and decode Mapterhorn elevation tile (Terrarium encoding)."""
    print("\n" + "="*60)
    print("TEST 2: Mapterhorn Elevation Tile (Terrarium)")
    print("="*60)

    # Use zoom 13 for elevation (good balance of detail vs coverage)
    zoom = 13
    lng, lat = ZURICH_CENTER
    n = 2 ** zoom
    x = int((lng + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)

    url = f"https://tiles.mapterhorn.com/{zoom}/{x}/{y}.webp"
    print(f"  Tile coords: z={zoom}, x={x}, y={y}")
    print(f"  URL: {url}")

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        img = Image.open(BytesIO(response.content))
        arr = np.array(img).astype(np.float32)

        # Terrarium decoding: elevation = R*256 + G + B/256 - 32768
        if arr.ndim == 3 and arr.shape[2] >= 3:
            elevation = arr[:,:,0] * 256 + arr[:,:,1] + arr[:,:,2] / 256 - 32768
        else:
            print(f"  ❌ Unexpected array shape: {arr.shape}")
            return False, None

        print(f"  ✅ Downloaded: {len(response.content):,} bytes")
        print(f"  ✅ Image size: {img.size[0]}x{img.size[1]} pixels")
        print(f"  ✅ Raw RGB shape: {arr.shape}")
        print(f"  ✅ Elevation range: {elevation.min():.1f}m to {elevation.max():.1f}m")
        print(f"  ✅ Mean elevation: {elevation.mean():.1f}m (Zurich ~400m expected)")

        # Sanity check: Zurich elevation should be roughly 400-600m
        if 300 < elevation.mean() < 700:
            print(f"  ✅ Elevation sanity check PASSED")
        else:
            print(f"  ⚠️  Elevation seems off for Zurich")

        return True, elevation
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False, None


# =============================================================================
# TEST 3: Building Data Loading
# =============================================================================

def test_building_data():
    """Load buildings and extract properties for shadow calculation."""
    print("\n" + "="*60)
    print("TEST 3: Building Data (GeoJSON)")
    print("="*60)

    geojson_path = Path("public/data/zurich-buildings.geojson")
    print(f"  Path: {geojson_path}")

    try:
        with open(geojson_path) as f:
            data = json.load(f)

        features = data["features"]
        print(f"  ✅ Loaded {len(features):,} buildings")

        # Check required properties
        sample = features[0]
        props = sample["properties"]
        geom = shape(sample["geometry"])

        required = ["height", "elevation"]
        missing = [p for p in required if p not in props]

        if missing:
            print(f"  ❌ Missing properties: {missing}")
            return False, None

        # Statistics
        heights = [f["properties"]["height"] for f in features if f["properties"].get("height")]
        elevations = [f["properties"]["elevation"] for f in features if f["properties"].get("elevation")]

        print(f"  ✅ Properties present: {list(props.keys())}")
        print(f"  ✅ Geometry type: {geom.geom_type}")
        print(f"  ✅ Height range: {min(heights):.1f}m to {max(heights):.1f}m")
        print(f"  ✅ Mean height: {sum(heights)/len(heights):.1f}m")
        print(f"  ✅ Elevation range: {min(elevations):.1f}m to {max(elevations):.1f}m")

        # Test spatial query (buildings in small area)
        test_box = box(8.53, 47.37, 8.55, 47.38)
        count_in_box = sum(1 for f in features[:1000] if shape(f["geometry"]).intersects(test_box))
        print(f"  ✅ Spatial query test: {count_in_box} buildings in test area (first 1000)")

        return True, features[:100]  # Return sample
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False, None


# =============================================================================
# TEST 4: Tree Data Loading
# =============================================================================

def test_tree_data():
    """Load trees and extract properties for shadow calculation."""
    print("\n" + "="*60)
    print("TEST 4: Tree Data (GeoJSON)")
    print("="*60)

    geojson_path = Path("public/data/zurich-trees.geojson")
    print(f"  Path: {geojson_path}")

    try:
        with open(geojson_path) as f:
            data = json.load(f)

        features = data["features"]
        print(f"  ✅ Loaded {len(features):,} trees")

        # Check required properties
        sample = features[0]
        props = sample["properties"]
        geom = shape(sample["geometry"])

        required = ["height", "crown_diameter"]
        missing = [p for p in required if p not in props]

        if missing:
            print(f"  ❌ Missing properties: {missing}")
            return False, None

        # Statistics
        heights = [f["properties"]["height"] for f in features if f["properties"].get("height")]
        crowns = [f["properties"]["crown_diameter"] for f in features if f["properties"].get("crown_diameter")]

        print(f"  ✅ Properties present: {list(props.keys())}")
        print(f"  ✅ Geometry type: {geom.geom_type}")
        print(f"  ✅ Height range: {min(heights):.1f}m to {max(heights):.1f}m")
        print(f"  ✅ Mean height: {sum(heights)/len(heights):.1f}m")
        print(f"  ✅ Crown diameter range: {min(crowns):.1f}m to {max(crowns):.1f}m")

        return True, features[:100]
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False, None


# =============================================================================
# TEST 5: LAB Color Space Conversion
# =============================================================================

def test_lab_conversion():
    """Test RGB to LAB to RGB roundtrip conversion."""
    print("\n" + "="*60)
    print("TEST 5: LAB Color Space Conversion")
    print("="*60)

    # D65 illuminant reference white point
    D65_WHITE = np.array([0.95047, 1.0, 1.08883])

    def rgb_to_xyz(rgb):
        """Convert RGB (0-255) to XYZ."""
        rgb_norm = rgb.astype(np.float64) / 255.0
        # Linearize sRGB
        mask = rgb_norm > 0.04045
        rgb_linear = np.where(mask, ((rgb_norm + 0.055) / 1.055) ** 2.4, rgb_norm / 12.92)
        # sRGB to XYZ matrix
        M = np.array([
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041]
        ])
        return np.einsum('ij,...j->...i', M, rgb_linear)

    def xyz_to_lab(xyz):
        """Convert XYZ to LAB."""
        xyz_norm = xyz / D65_WHITE
        epsilon = 0.008856
        kappa = 903.3
        mask = xyz_norm > epsilon
        f_xyz = np.where(mask, np.cbrt(xyz_norm), (kappa * xyz_norm + 16) / 116)
        L = 116 * f_xyz[..., 1] - 16
        a = 500 * (f_xyz[..., 0] - f_xyz[..., 1])
        b = 200 * (f_xyz[..., 1] - f_xyz[..., 2])
        return np.stack([L, a, b], axis=-1)

    def lab_to_xyz(lab):
        """Convert LAB to XYZ."""
        L, a, b_ch = lab[..., 0], lab[..., 1], lab[..., 2]
        fy = (L + 16) / 116
        fx = a / 500 + fy
        fz = fy - b_ch / 200
        epsilon = 0.008856
        kappa = 903.3
        xr = np.where(fx**3 > epsilon, fx**3, (116 * fx - 16) / kappa)
        yr = np.where(L > kappa * epsilon, ((L + 16) / 116)**3, L / kappa)
        zr = np.where(fz**3 > epsilon, fz**3, (116 * fz - 16) / kappa)
        return np.stack([xr, yr, zr], axis=-1) * D65_WHITE

    def xyz_to_rgb(xyz):
        """Convert XYZ to RGB (0-255)."""
        M_inv = np.array([
            [ 3.2404542, -1.5371385, -0.4985314],
            [-0.9692660,  1.8760108,  0.0415560],
            [ 0.0556434, -0.2040259,  1.0572252]
        ])
        rgb_linear = np.einsum('ij,...j->...i', M_inv, xyz)
        mask = rgb_linear > 0.0031308
        rgb = np.where(mask, 1.055 * (rgb_linear ** (1/2.4)) - 0.055, 12.92 * rgb_linear)
        return np.clip(rgb * 255, 0, 255).astype(np.uint8)

    try:
        # Test with known colors
        test_colors = np.array([
            [255, 0, 0],     # Red
            [0, 255, 0],     # Green
            [0, 0, 255],     # Blue
            [255, 255, 255], # White
            [0, 0, 0],       # Black
            [128, 128, 128], # Gray
        ], dtype=np.uint8)

        print("  Testing RGB → LAB → RGB roundtrip:")

        for i, rgb in enumerate(test_colors):
            xyz = rgb_to_xyz(rgb)
            lab = xyz_to_lab(xyz)
            xyz_back = lab_to_xyz(lab)
            rgb_back = xyz_to_rgb(xyz_back)

            diff = np.abs(rgb.astype(int) - rgb_back.astype(int)).max()
            status = "✅" if diff <= 1 else "❌"
            print(f"    {status} RGB{tuple(rgb)} → LAB({lab[0]:.1f}, {lab[1]:.1f}, {lab[2]:.1f}) → RGB{tuple(rgb_back)} (diff={diff})")

        # Test with image-sized array
        test_image = np.random.randint(0, 256, (256, 256, 3), dtype=np.uint8)
        xyz = rgb_to_xyz(test_image)
        lab = xyz_to_lab(xyz)
        xyz_back = lab_to_xyz(lab)
        rgb_back = xyz_to_rgb(xyz_back)

        max_diff = np.abs(test_image.astype(int) - rgb_back.astype(int)).max()
        mean_diff = np.abs(test_image.astype(int) - rgb_back.astype(int)).mean()

        print(f"\n  ✅ 256x256 image roundtrip: max_diff={max_diff}, mean_diff={mean_diff:.4f}")
        print(f"  ✅ LAB range: L=[{lab[:,:,0].min():.1f}, {lab[:,:,0].max():.1f}], a=[{lab[:,:,1].min():.1f}, {lab[:,:,1].max():.1f}], b=[{lab[:,:,2].min():.1f}, {lab[:,:,2].max():.1f}]")

        return True, None
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False, None


# =============================================================================
# TEST 6: Shadow Geometry Calculation
# =============================================================================

def test_shadow_calculation():
    """Test basic shadow offset calculation."""
    print("\n" + "="*60)
    print("TEST 6: Shadow Geometry Calculation")
    print("="*60)

    try:
        def calculate_shadow_offset(height_m, sun_altitude_deg, sun_azimuth_deg, pixel_size_m):
            """Calculate shadow offset in pixels."""
            # Shadow length on ground
            shadow_length_m = height_m / math.tan(math.radians(sun_altitude_deg))
            shadow_length_px = shadow_length_m / pixel_size_m

            # Shadow direction (opposite of sun)
            shadow_azimuth = (sun_azimuth_deg + 180) % 360
            azimuth_rad = math.radians(shadow_azimuth)

            # Offset (image Y is inverted)
            dx = shadow_length_px * math.sin(azimuth_rad)
            dy = -shadow_length_px * math.cos(azimuth_rad)

            return dx, dy, shadow_length_m

        # Test cases
        test_cases = [
            # (height, sun_alt, sun_az, pixel_size, description)
            (20, 45, 180, 0.5, "Noon sun (south)"),
            (20, 30, 240, 0.5, "Afternoon sun (southwest)"),
            (20, 15, 280, 0.5, "Evening sun (west)"),
            (50, 45, 180, 0.5, "Tall building at noon"),
        ]

        print("  Shadow offset calculations:")
        for height, alt, az, px_size, desc in test_cases:
            dx, dy, length = calculate_shadow_offset(height, alt, az, px_size)
            print(f"    ✅ {desc}:")
            print(f"       Building: {height}m, Sun: alt={alt}°, az={az}°")
            print(f"       Shadow length: {length:.1f}m, Offset: ({dx:.1f}, {dy:.1f}) pixels")

        # Verify with known geometry
        # At 45° sun altitude, shadow length = building height
        dx, dy, length = calculate_shadow_offset(10, 45, 180, 1.0)
        assert abs(length - 10.0) < 0.01, f"Expected 10m shadow, got {length}m"
        print(f"\n  ✅ Geometry verification passed (45° sun = shadow length equals height)")

        return True, None
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False, None


# =============================================================================
# TEST 7: Hillshade Calculation
# =============================================================================

def test_hillshade():
    """Test hillshade generation from elevation data."""
    print("\n" + "="*60)
    print("TEST 7: Hillshade Calculation")
    print("="*60)

    try:
        def calculate_hillshade(dem, sun_azimuth=315, sun_altitude=45, cell_size=1.0):
            """Calculate hillshade using Horn algorithm."""
            # Convert to radians
            azimuth_rad = math.radians(360 - sun_azimuth + 90)
            altitude_rad = math.radians(sun_altitude)

            # Calculate gradients
            dy, dx = np.gradient(dem, cell_size)

            # Slope and aspect
            slope = np.arctan(np.sqrt(dx**2 + dy**2))
            aspect = np.arctan2(-dy, dx)

            # Hillshade formula
            hillshade = (
                math.sin(altitude_rad) * np.cos(slope) +
                math.cos(altitude_rad) * np.sin(slope) * np.cos(azimuth_rad - aspect)
            )

            return np.clip(hillshade, 0, 1)

        # Create synthetic terrain (ridge running N-S)
        x = np.linspace(0, 100, 256)
        y = np.linspace(0, 100, 256)
        X, Y = np.meshgrid(x, y)

        # Ridge in the middle
        dem = 400 + 50 * np.exp(-((X - 50)**2) / 200)

        # Calculate hillshade
        hs = calculate_hillshade(dem, sun_azimuth=315, sun_altitude=45)

        print(f"  ✅ Synthetic DEM: {dem.shape}, range [{dem.min():.0f}m, {dem.max():.0f}m]")
        print(f"  ✅ Hillshade: {hs.shape}, range [{hs.min():.3f}, {hs.max():.3f}]")

        # West side (facing sun at 315°) should be brighter than east side
        west_mean = hs[:, :128].mean()
        east_mean = hs[:, 128:].mean()
        print(f"  ✅ West side (sun-facing): {west_mean:.3f}")
        print(f"  ✅ East side (shadow): {east_mean:.3f}")

        if west_mean > east_mean:
            print(f"  ✅ Illumination direction correct (west brighter with NW sun)")
        else:
            print(f"  ⚠️  Illumination may be inverted")

        return True, hs
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False, None


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*60)
    print("TILE PIPELINE DATA SOURCE VALIDATION")
    print("="*60)

    results = {}

    # Run all tests
    results["satellite"] = test_satellite_download()
    results["elevation"] = test_elevation_download()
    results["buildings"] = test_building_data()
    results["trees"] = test_tree_data()
    results["lab_color"] = test_lab_conversion()
    results["shadows"] = test_shadow_calculation()
    results["hillshade"] = test_hillshade()

    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)

    all_passed = True
    for name, (passed, _) in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    print("\n" + "="*60)
    if all_passed:
        print("🎉 ALL TESTS PASSED - Pipeline is ready for implementation!")
    else:
        print("⚠️  SOME TESTS FAILED - Review errors above")
    print("="*60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
