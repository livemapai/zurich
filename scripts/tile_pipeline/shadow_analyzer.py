"""
Shadow detection and analysis for satellite imagery.

Detects existing baked-in shadows in satellite tiles to enable
intelligent shadow neutralization before relighting.

Techniques used:
1. Luminosity histogram analysis - identify shadow/highlight distribution
2. Edge-based shadow detection - shadows create distinct edges
3. Color temperature analysis - shadows are cooler (more blue)
4. Estimated sun position from shadow direction
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage
from PIL import Image, ImageFilter


@dataclass
class ShadowAnalysis:
    """Results from analyzing shadows in an image."""

    # Shadow statistics
    shadow_percentage: float  # 0-100% of image in shadow
    shadow_intensity: float  # Average darkness of shadows (0-1)
    highlight_intensity: float  # Average brightness of highlights (0-1)

    # Estimated sun position from shadow direction
    estimated_sun_azimuth: float  # Degrees from north
    estimated_sun_altitude: float  # Degrees above horizon

    # Shadow mask (binary: 1=shadow, 0=lit)
    shadow_mask: NDArray[np.float32]

    # Quality metrics
    contrast_ratio: float  # Dynamic range
    shadow_edge_sharpness: float  # How hard/soft are shadow edges


def analyze_shadows(
    image: NDArray[np.uint8],
    shadow_threshold: float = 0.35,
    highlight_threshold: float = 0.7,
) -> ShadowAnalysis:
    """Analyze an image for existing shadows.

    Args:
        image: RGB image array (H, W, 3)
        shadow_threshold: Luminosity below this = shadow (0-1)
        highlight_threshold: Luminosity above this = highlight (0-1)

    Returns:
        ShadowAnalysis with detection results
    """
    # Convert to luminosity (perceived brightness)
    # Using Rec. 709 coefficients
    luminosity = (
        0.2126 * image[..., 0] +
        0.7152 * image[..., 1] +
        0.0722 * image[..., 2]
    ) / 255.0

    # Create shadow mask
    shadow_mask = (luminosity < shadow_threshold).astype(np.float32)
    highlight_mask = luminosity > highlight_threshold

    # Calculate statistics
    shadow_pixels = luminosity[shadow_mask > 0.5]
    highlight_pixels = luminosity[highlight_mask]

    shadow_percentage = (shadow_mask.sum() / shadow_mask.size) * 100
    shadow_intensity = shadow_pixels.mean() if len(shadow_pixels) > 0 else 0.0
    highlight_intensity = highlight_pixels.mean() if len(highlight_pixels) > 0 else 1.0

    # Contrast ratio
    contrast_ratio = highlight_intensity / max(shadow_intensity, 0.01)

    # Estimate sun direction from shadow edges
    sun_azimuth, sun_altitude = _estimate_sun_position(shadow_mask, luminosity)

    # Shadow edge sharpness (gradient magnitude at shadow boundaries)
    shadow_edges = ndimage.sobel(shadow_mask)
    edge_sharpness = np.abs(shadow_edges).mean()

    return ShadowAnalysis(
        shadow_percentage=shadow_percentage,
        shadow_intensity=shadow_intensity,
        highlight_intensity=highlight_intensity,
        estimated_sun_azimuth=sun_azimuth,
        estimated_sun_altitude=sun_altitude,
        shadow_mask=shadow_mask,
        contrast_ratio=contrast_ratio,
        shadow_edge_sharpness=edge_sharpness,
    )


def _estimate_sun_position(
    shadow_mask: NDArray[np.float32],
    luminosity: NDArray[np.float32],
) -> Tuple[float, float]:
    """Estimate sun position from shadow patterns.

    Uses gradient direction of luminosity at shadow edges to
    determine dominant shadow direction, then infers sun position.

    Returns:
        (azimuth, altitude) in degrees
    """
    # Compute gradients
    grad_y, grad_x = np.gradient(luminosity)

    # Find shadow edges (transition zones)
    shadow_edges = ndimage.sobel(shadow_mask)
    edge_mask = np.abs(shadow_edges) > 0.1

    if edge_mask.sum() < 100:
        # Not enough edges, return default (afternoon SW sun)
        return (225.0, 45.0)

    # Get gradient directions at edges
    edge_grad_x = grad_x[edge_mask]
    edge_grad_y = grad_y[edge_mask]

    # Weighted by gradient magnitude
    magnitudes = np.sqrt(edge_grad_x**2 + edge_grad_y**2)
    weights = magnitudes / (magnitudes.sum() + 1e-8)

    # Average direction (shadow direction is where gradients point from light to dark)
    avg_dx = np.sum(edge_grad_x * weights)
    avg_dy = np.sum(edge_grad_y * weights)

    # Convert to angle (note: image y-axis is inverted)
    # Shadows point away from sun, so sun is opposite direction
    shadow_angle = math.atan2(-avg_dy, avg_dx)  # Radians, 0 = east

    # Convert to azimuth (0 = north, clockwise)
    # Image coordinates: +x = east, +y = south (inverted)
    sun_azimuth = (90 - math.degrees(shadow_angle) + 180) % 360

    # Estimate altitude from shadow length/intensity ratio
    # (rough approximation - shadows are darker when sun is lower)
    shadow_darkness = 1.0 - (luminosity[shadow_mask > 0.5].mean() if shadow_mask.sum() > 0 else 0.5)
    # Lower sun = longer shadows = darker average
    estimated_altitude = 30 + (1 - shadow_darkness) * 40  # Range 30-70°

    return (sun_azimuth, estimated_altitude)


def detect_shadow_regions(
    image: NDArray[np.uint8],
    min_region_size: int = 100,
) -> NDArray[np.int32]:
    """Detect and label individual shadow regions.

    Args:
        image: RGB image array
        min_region_size: Minimum pixels for a valid shadow region

    Returns:
        Label array where each shadow region has a unique integer ID
    """
    # Get shadow mask from analysis
    analysis = analyze_shadows(image)

    # Clean up with morphological operations
    shadow_binary = (analysis.shadow_mask > 0.5).astype(np.uint8)

    # Close small gaps
    kernel = np.ones((5, 5), dtype=np.uint8)
    shadow_binary = ndimage.binary_closing(shadow_binary, kernel)

    # Remove small noise
    shadow_binary = ndimage.binary_opening(shadow_binary, kernel)

    # Label connected components
    labels, num_labels = ndimage.label(shadow_binary)

    # Remove small regions
    for i in range(1, num_labels + 1):
        if (labels == i).sum() < min_region_size:
            labels[labels == i] = 0

    # Relabel to remove gaps in IDs
    unique_labels = np.unique(labels)
    for new_id, old_id in enumerate(unique_labels):
        labels[labels == old_id] = new_id

    return labels


def create_shadow_probability_map(
    image: NDArray[np.uint8],
    temperature_weight: float = 0.3,
    luminosity_weight: float = 0.5,
    texture_weight: float = 0.2,
) -> NDArray[np.float32]:
    """Create a soft shadow probability map.

    Combines multiple cues to create a probability map where
    higher values indicate higher likelihood of being in shadow.

    Args:
        image: RGB image array
        temperature_weight: Weight for color temperature cue
        luminosity_weight: Weight for darkness cue
        texture_weight: Weight for texture/detail loss cue

    Returns:
        Probability map (H, W) with values 0-1
    """
    h, w = image.shape[:2]

    # 1. Luminosity-based probability
    luminosity = (
        0.2126 * image[..., 0] +
        0.7152 * image[..., 1] +
        0.0722 * image[..., 2]
    ) / 255.0

    # Shadows are dark - use sigmoid for soft threshold
    lum_prob = 1.0 / (1.0 + np.exp(10 * (luminosity - 0.35)))

    # 2. Color temperature probability (shadows are cooler/bluer)
    # Calculate color temperature as R-B difference
    r = image[..., 0].astype(np.float32)
    b = image[..., 2].astype(np.float32)

    # Normalize
    color_temp = (r - b) / 255.0  # Positive = warm, negative = cool

    # Shadows are cooler (more blue)
    temp_prob = 1.0 / (1.0 + np.exp(5 * (color_temp + 0.1)))

    # 3. Texture/detail probability
    # Shadows often have less visible detail due to reduced dynamic range
    gray = luminosity * 255
    local_std = ndimage.generic_filter(gray, np.std, size=7)
    max_std = local_std.max() + 1e-8

    # Low texture = might be shadow (but could also be uniform surfaces)
    texture_prob = 1.0 - (local_std / max_std)

    # Combine probabilities
    shadow_prob = (
        luminosity_weight * lum_prob +
        temperature_weight * temp_prob +
        texture_weight * texture_prob
    )

    # Normalize to 0-1
    shadow_prob = np.clip(shadow_prob, 0, 1)

    return shadow_prob.astype(np.float32)


def estimate_capture_time(
    analysis: ShadowAnalysis,
    latitude: float = 47.37,  # Zurich default
    month: int = 6,  # June default (summer capture)
) -> dict:
    """Estimate when the aerial photo was captured.

    Uses shadow analysis to estimate capture time based on
    sun position calculations for the given location.

    Args:
        analysis: Shadow analysis results
        latitude: Latitude of image location
        month: Estimated month of capture

    Returns:
        Dictionary with estimated capture time info
    """
    sun_az = analysis.estimated_sun_azimuth
    sun_alt = analysis.estimated_sun_altitude

    # Solar noon is when sun is due south (azimuth ~180°)
    # Morning: azimuth < 180°, Afternoon: azimuth > 180°

    if sun_az < 180:
        period = "morning"
        # Hours before noon proportional to azimuth difference
        hours_from_noon = (180 - sun_az) / 15  # ~15° per hour
    else:
        period = "afternoon"
        hours_from_noon = (sun_az - 180) / 15

    # Solar noon in Switzerland is approximately 12:30 in summer (due to timezone)
    solar_noon = 12.5  # 12:30

    if period == "morning":
        estimated_hour = solar_noon - hours_from_noon
    else:
        estimated_hour = solar_noon + hours_from_noon

    # Format as time string
    hours = int(estimated_hour)
    minutes = int((estimated_hour - hours) * 60)
    time_str = f"{hours:02d}:{minutes:02d}"

    return {
        "period": period,
        "estimated_hour": estimated_hour,
        "time_string": time_str,
        "sun_azimuth": sun_az,
        "sun_altitude": sun_alt,
        "confidence": "medium" if 30 < sun_alt < 60 else "low",
    }
