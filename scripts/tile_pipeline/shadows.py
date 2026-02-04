"""
Building and tree shadow casting for photorealistic tiles.

Computes cast shadows based on sun position and feature heights.
All shadow operations produce grayscale masks suitable for multiply blending.

Shadow types:
- Building shadows: Hard-edged cast shadows projected on ground
- Tree shadows: Soft elliptical shadows with Gaussian blur
- Ambient occlusion: Contact shadows at building bases
"""

import math
from typing import Optional

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw, ImageFilter

from .sources.vector import Feature, polygon_to_pixel_mask


def compute_shadow_offset(
    height: float,
    sun_azimuth: float,
    sun_altitude: float,
) -> tuple[float, float]:
    """Compute shadow offset (dx, dy) for a given height and sun position.

    Args:
        height: Feature height in meters
        sun_azimuth: Sun azimuth in degrees (0=N, 90=E, 180=S, 270=W)
        sun_altitude: Sun altitude in degrees above horizon

    Returns:
        Tuple of (dx, dy) offset in meters
        Positive dx = east, positive dy = north
    """
    if sun_altitude <= 0:
        return (0, 0)

    # Shadow length
    length = height / math.tan(math.radians(sun_altitude))

    # Shadow direction (opposite of sun)
    shadow_azimuth = (sun_azimuth + 180) % 360

    # Convert to dx, dy (azimuth 0=N, increases clockwise)
    dx = length * math.sin(math.radians(shadow_azimuth))
    dy = length * math.cos(math.radians(shadow_azimuth))

    return (dx, dy)


def building_shadows(
    features: list[Feature],
    bounds: tuple[float, float, float, float],
    size: int,
    sun_azimuth: float,
    sun_altitude: float,
    darkness: float = 0.8,
) -> NDArray[np.float32]:
    """Render building cast shadows.

    Creates a shadow mask where:
    - 1.0 = no shadow (full light)
    - darkness value = in shadow

    Args:
        features: Building features with height and polygon coordinates
        bounds: (west, south, east, north) in WGS84 degrees
        size: Output size in pixels
        sun_azimuth: Sun azimuth in degrees
        sun_altitude: Sun altitude in degrees
        darkness: Shadow darkness (0=black, 1=no effect)

    Returns:
        Shadow mask of shape (size, size) with values darkness to 1.0
    """
    # Initialize with full light
    shadow_mask = np.ones((size, size), dtype=np.float32)

    west, south, east, north = bounds
    x_range = east - west
    y_range = north - south

    # Meters per degree at this latitude
    lat_center = (south + north) / 2
    meters_per_deg_x = 111000 * math.cos(math.radians(lat_center))
    meters_per_deg_y = 111000

    # Pixels per meter
    pixels_per_meter_x = size / (x_range * meters_per_deg_x)
    pixels_per_meter_y = size / (y_range * meters_per_deg_y)

    for feature in features:
        if feature.height <= 0:
            continue

        if feature.geometry_type not in ("Polygon", "MultiPolygon"):
            continue

        # Get shadow offset in degrees
        dx_m, dy_m = compute_shadow_offset(feature.height, sun_azimuth, sun_altitude)
        dx_deg = dx_m / meters_per_deg_x
        dy_deg = dy_m / meters_per_deg_y

        # Get polygon coordinates
        if feature.geometry_type == "Polygon":
            polygons = [feature.coordinates]
        else:  # MultiPolygon
            polygons = feature.coordinates

        for polygon in polygons:
            # Outer ring only for shadow (holes don't cast shadows)
            outer_ring = polygon[0]

            # Create shadow polygon by offsetting vertices
            shadow_ring = [(x + dx_deg, y + dy_deg) for x, y in outer_ring]

            # Create combined footprint + shadow polygon
            # This creates the characteristic shadow shape
            _render_shadow_polygon(
                shadow_mask,
                outer_ring,
                shadow_ring,
                bounds,
                size,
                1.0 - darkness,
            )

    return shadow_mask


def _render_shadow_polygon(
    mask: NDArray[np.float32],
    footprint: list[tuple[float, float]],
    shadow: list[tuple[float, float]],
    bounds: tuple[float, float, float, float],
    size: int,
    shadow_value: float,
) -> None:
    """Render a shadow polygon onto the mask in-place.

    Creates a shadow that extends from building footprint to shadow outline.
    """
    west, south, east, north = bounds

    def to_pixel(x: float, y: float) -> tuple[int, int]:
        px = int((x - west) / (east - west) * size)
        py = int((north - y) / (north - south) * size)  # Flip Y
        return (px, py)

    # Create image for this shadow
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)

    # Draw the shadow polygon (outline connects footprint to shadow)
    # Method: draw lines between corresponding vertices
    for i in range(len(footprint)):
        # Quad from footprint edge to shadow edge
        fp1 = to_pixel(*footprint[i])
        fp2 = to_pixel(*footprint[(i + 1) % len(footprint)])
        sh1 = to_pixel(*shadow[i])
        sh2 = to_pixel(*shadow[(i + 1) % len(shadow)])

        # Draw as polygon (trapezoid connecting the two edges)
        quad = [fp1, fp2, sh2, sh1]
        draw.polygon(quad, fill=255)

    # Draw the shadow footprint (far end)
    shadow_pixels = [to_pixel(x, y) for x, y in shadow]
    if len(shadow_pixels) >= 3:
        draw.polygon(shadow_pixels, fill=255)

    # Apply to mask (multiply to accumulate shadows)
    shadow_arr = np.array(img) / 255.0
    mask *= (1 - shadow_arr * shadow_value)


def tree_shadows(
    features: list[Feature],
    bounds: tuple[float, float, float, float],
    size: int,
    sun_azimuth: float,
    sun_altitude: float,
    darkness: float = 0.6,
    blur_radius: int = 5,
) -> NDArray[np.float32]:
    """Render soft tree shadows.

    Tree shadows are rendered as ellipses with Gaussian blur to simulate
    the diffuse nature of canopy shadows.

    Args:
        features: Tree features with height and point coordinates
        bounds: (west, south, east, north) in WGS84 degrees
        size: Output size in pixels
        sun_azimuth: Sun azimuth in degrees
        sun_altitude: Sun altitude in degrees
        darkness: Shadow darkness (0=black, 1=no effect)
        blur_radius: Gaussian blur radius in pixels

    Returns:
        Shadow mask of shape (size, size)
    """
    shadow_mask = np.ones((size, size), dtype=np.float32)

    west, south, east, north = bounds
    x_range = east - west
    y_range = north - south

    lat_center = (south + north) / 2
    meters_per_deg_x = 111000 * math.cos(math.radians(lat_center))
    meters_per_deg_y = 111000

    # Create shadow image
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)

    for feature in features:
        if feature.height <= 0:
            continue

        if feature.geometry_type != "Point":
            continue

        x, y = feature.coordinates

        # Get shadow offset
        dx_m, dy_m = compute_shadow_offset(feature.height, sun_azimuth, sun_altitude)
        dx_deg = dx_m / meters_per_deg_x
        dy_deg = dy_m / meters_per_deg_y

        # Shadow center
        shadow_x = x + dx_deg
        shadow_y = y + dy_deg

        # Convert to pixels
        px = int((shadow_x - west) / x_range * size)
        py = int((north - shadow_y) / y_range * size)

        # Ellipse size based on crown (estimate 3m radius for typical tree)
        crown_radius = feature.properties.get("crown_diameter", 6) / 2
        crown_px = int(crown_radius / (x_range * meters_per_deg_x) * size)
        crown_px = max(2, crown_px)

        # Draw ellipse (elongated in shadow direction)
        shadow_length_px = int(feature.height * 0.5 / (y_range * meters_per_deg_y) * size)
        shadow_length_px = max(crown_px, shadow_length_px)

        # Bounding box for ellipse
        bbox = [
            px - crown_px,
            py - shadow_length_px,
            px + crown_px,
            py + shadow_length_px,
        ]
        draw.ellipse(bbox, fill=180)  # Partial opacity

    # Apply Gaussian blur
    img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Convert to mask
    shadow_arr = np.array(img) / 255.0
    shadow_mask = 1 - shadow_arr * (1 - darkness)

    return shadow_mask.astype(np.float32)


def ambient_occlusion(
    features: list[Feature],
    bounds: tuple[float, float, float, float],
    size: int,
    radius_meters: float = 3.0,
    darkness: float = 0.4,
) -> NDArray[np.float32]:
    """Render ambient occlusion at building bases.

    Creates subtle darkening around building footprints to simulate
    contact shadows where buildings meet the ground.

    Args:
        features: Building features with polygon coordinates
        bounds: (west, south, east, north) in WGS84 degrees
        size: Output size in pixels
        radius_meters: AO falloff radius in meters
        darkness: Maximum darkness (0=black, 1=no effect)

    Returns:
        AO mask of shape (size, size)
    """
    west, south, east, north = bounds
    x_range = east - west
    y_range = north - south

    lat_center = (south + north) / 2
    meters_per_deg_x = 111000 * math.cos(math.radians(lat_center))
    meters_per_deg_y = 111000

    # Blur radius in pixels
    blur_px = int(radius_meters / (x_range * meters_per_deg_x) * size)
    blur_px = max(1, blur_px)

    # Create footprint mask
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)

    for feature in features:
        if feature.geometry_type not in ("Polygon", "MultiPolygon"):
            continue

        if feature.geometry_type == "Polygon":
            polygons = [feature.coordinates]
        else:
            polygons = feature.coordinates

        for polygon in polygons:
            outer_ring = polygon[0]
            pixels = []
            for x, y in outer_ring:
                px = int((x - west) / x_range * size)
                py = int((north - y) / y_range * size)
                pixels.append((px, py))

            if len(pixels) >= 3:
                draw.polygon(pixels, fill=255)

    # Blur to create falloff
    img = img.filter(ImageFilter.GaussianBlur(radius=blur_px))

    # Invert and scale
    ao_arr = np.array(img) / 255.0
    ao_mask = 1 - ao_arr * (1 - darkness)

    return ao_mask.astype(np.float32)


def combine_shadow_masks(
    *masks: NDArray[np.float32],
) -> NDArray[np.float32]:
    """Combine multiple shadow masks using multiply blending.

    Each mask has values where 1.0 = no shadow and lower values = shadow.
    Multiplying them accumulates shadows correctly.

    Args:
        *masks: Shadow mask arrays

    Returns:
        Combined shadow mask
    """
    result = np.ones_like(masks[0])
    for mask in masks:
        result *= mask
    return result


def create_shadow_layers(
    buildings: list[Feature],
    trees: list[Feature],
    bounds: tuple[float, float, float, float],
    size: int,
    sun_azimuth: float,
    sun_altitude: float,
    building_darkness: float = 0.8,
    tree_darkness: float = 0.6,
    ao_darkness: float = 0.4,
    tree_blur: int = 5,
) -> dict[str, NDArray[np.float32]]:
    """Create all shadow layers for a tile.

    Returns separate masks for each shadow type for flexible compositing.

    Args:
        buildings: Building features
        trees: Tree features
        bounds: Tile bounds in WGS84
        size: Output size in pixels
        sun_azimuth: Sun azimuth in degrees
        sun_altitude: Sun altitude in degrees
        building_darkness: Building shadow darkness
        tree_darkness: Tree shadow darkness
        ao_darkness: Ambient occlusion darkness
        tree_blur: Blur radius for tree shadows

    Returns:
        Dictionary with 'buildings', 'trees', 'ambient_occlusion' masks
    """
    return {
        "buildings": building_shadows(
            buildings, bounds, size, sun_azimuth, sun_altitude, building_darkness
        ),
        "trees": tree_shadows(
            buildings, bounds, size, sun_azimuth, sun_altitude, tree_darkness, tree_blur
        ) if trees else np.ones((size, size), dtype=np.float32),
        "ambient_occlusion": ambient_occlusion(
            buildings, bounds, size, darkness=ao_darkness
        ),
    }
