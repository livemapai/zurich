"""
Shadow neutralization and intelligent relighting for satellite imagery.

Based on research from:
- Silva et al. (2017) shadow detection in aerial imagery
- LAB color space shadow detection (low L and B values)
- Local tone mapping for shadow recovery
- Color constancy principles for temperature correction

Techniques:
1. Shadow-aware tone mapping - lift shadows while preserving highlights
2. Color temperature correction - neutralize blue cast in shadows
3. Detail recovery - enhance local contrast in shadow regions
4. Soft shadow transition - avoid harsh edges between corrected/uncorrected
"""

import math
from typing import Optional, Tuple

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage
from PIL import Image, ImageFilter

from .color_space import rgb_to_lab, lab_to_rgb
from .shadow_analyzer import analyze_shadows, create_shadow_probability_map, ShadowAnalysis


def neutralize_shadows(
    image: NDArray[np.uint8],
    target_shadow_level: float = 0.45,
    temperature_correction: float = 0.5,
    detail_enhancement: float = 0.3,
    transition_softness: float = 15.0,
) -> NDArray[np.uint8]:
    """Neutralize baked-in shadows in satellite imagery.

    Lifts shadow areas to a more neutral level while preserving
    color relationships and detail.

    Args:
        image: RGB image array (H, W, 3)
        target_shadow_level: Target luminosity for shadow areas (0-1)
        temperature_correction: Amount of blue cast removal (0-1)
        detail_enhancement: Local contrast boost in shadows (0-1)
        transition_softness: Blur radius for soft transitions (pixels)

    Returns:
        Shadow-neutralized RGB image
    """
    # Analyze existing shadows
    analysis = analyze_shadows(image)

    # Create soft shadow probability map
    shadow_prob = create_shadow_probability_map(image)

    # Apply Gaussian blur for soft transitions
    shadow_prob = ndimage.gaussian_filter(shadow_prob, sigma=transition_softness)

    # Convert to LAB for perceptual processing
    lab = rgb_to_lab(image)

    # 1. Lift shadow luminosity
    lab = _lift_shadow_luminosity(
        lab, shadow_prob, target_shadow_level, analysis.shadow_intensity
    )

    # 2. Correct color temperature (remove blue cast)
    lab = _correct_shadow_temperature(lab, shadow_prob, temperature_correction)

    # 3. Enhance local detail in shadows
    if detail_enhancement > 0:
        lab = _enhance_shadow_detail(lab, shadow_prob, detail_enhancement)

    # Convert back to RGB
    return lab_to_rgb(lab)


def _lift_shadow_luminosity(
    lab: NDArray[np.float32],
    shadow_prob: NDArray[np.float32],
    target_level: float,
    current_shadow_intensity: float,
) -> NDArray[np.float32]:
    """Lift luminosity in shadow areas.

    Uses a tone curve that lifts shadows more than midtones,
    preserving highlight detail.
    """
    L = lab[..., 0].copy()  # L channel is 0-100

    # Calculate lift amount based on how dark current shadows are
    # and how bright we want them to be
    current_shadow_L = current_shadow_intensity * 100
    target_shadow_L = target_level * 100
    max_lift = target_shadow_L - current_shadow_L

    if max_lift <= 0:
        return lab

    # Apply lift with falloff based on luminosity
    # Darker pixels get lifted more
    luminosity_factor = 1.0 - (L / 100.0)  # 1.0 for black, 0.0 for white
    luminosity_factor = np.clip(luminosity_factor, 0, 1)

    # Combine with shadow probability
    lift_mask = shadow_prob * luminosity_factor

    # Apply lift (use sqrt for gentler curve)
    lift_amount = max_lift * np.sqrt(lift_mask)
    L = L + lift_amount

    # Clamp to valid range
    lab[..., 0] = np.clip(L, 0, 100)

    return lab


def _correct_shadow_temperature(
    lab: NDArray[np.float32],
    shadow_prob: NDArray[np.float32],
    strength: float,
) -> NDArray[np.float32]:
    """Correct cool color cast in shadow areas.

    Shadows in aerial photography typically have a blue cast
    due to skylight illumination. This shifts the color toward
    neutral/warm to match sunlit areas.
    """
    if strength <= 0:
        return lab

    # B channel in LAB: negative = blue, positive = yellow
    b_channel = lab[..., 2].copy()

    # Shadows typically have negative B values (blue cast)
    # Shift toward neutral (0) or slightly warm (positive)

    # Only correct where there's actually a blue cast
    blue_cast_mask = (b_channel < 0).astype(np.float32)

    # Correction amount: move toward neutral
    correction = -b_channel * strength * shadow_prob * blue_cast_mask

    lab[..., 2] = b_channel + correction

    return lab


def _enhance_shadow_detail(
    lab: NDArray[np.float32],
    shadow_prob: NDArray[np.float32],
    strength: float,
) -> NDArray[np.float32]:
    """Enhance local contrast in shadow regions.

    Applies unsharp mask / local contrast enhancement
    specifically in shadow areas to recover lost detail.
    """
    if strength <= 0:
        return lab

    L = lab[..., 0].copy()

    # Create low-frequency version (blur)
    L_blur = ndimage.gaussian_filter(L, sigma=20)

    # High-frequency detail = original - blur
    detail = L - L_blur

    # Boost detail in shadows
    boost = 1.0 + (strength * shadow_prob)
    boosted_detail = detail * boost

    # Recombine
    L_enhanced = L_blur + boosted_detail

    # Soft clip to avoid artifacts
    lab[..., 0] = np.clip(L_enhanced, 0, 100)

    return lab


def adaptive_shadow_removal(
    image: NDArray[np.uint8],
    analysis: Optional[ShadowAnalysis] = None,
) -> NDArray[np.uint8]:
    """Automatically adjust parameters based on image analysis.

    Analyzes the image and chooses optimal parameters for
    shadow neutralization.
    """
    if analysis is None:
        analysis = analyze_shadows(image)

    # Adjust parameters based on analysis
    # More shadow coverage = more aggressive lifting
    shadow_coverage = analysis.shadow_percentage / 100.0

    # Darker shadows = more lift needed
    shadow_darkness = 1.0 - analysis.shadow_intensity

    # High contrast = be more careful
    is_high_contrast = analysis.contrast_ratio > 5.0

    # Calculate adaptive parameters
    if is_high_contrast:
        # Be conservative to avoid blowing out highlights
        target_level = 0.40 + (shadow_darkness * 0.1)
        temp_correction = 0.3
        detail_enhancement = 0.2
    else:
        target_level = 0.45 + (shadow_darkness * 0.15)
        temp_correction = 0.5
        detail_enhancement = 0.4

    # More shadows = stronger transition softness
    transition_softness = 10.0 + (shadow_coverage * 20.0)

    return neutralize_shadows(
        image,
        target_shadow_level=target_level,
        temperature_correction=temp_correction,
        detail_enhancement=detail_enhancement,
        transition_softness=transition_softness,
    )


def relight_image(
    image: NDArray[np.uint8],
    new_sun_azimuth: float,
    new_sun_altitude: float,
    shadow_darkness: float = 0.7,
    preserve_original_lighting: float = 0.3,
) -> NDArray[np.uint8]:
    """Relight an image with a new sun position.

    First neutralizes existing shadows, then applies new computed
    lighting from the specified sun position.

    Args:
        image: RGB image array
        new_sun_azimuth: New sun azimuth (degrees from north)
        new_sun_altitude: New sun altitude (degrees above horizon)
        shadow_darkness: Darkness of new shadows (0=black, 1=none)
        preserve_original_lighting: How much original lighting to keep (0-1)

    Returns:
        Relit RGB image
    """
    # First neutralize existing shadows
    neutralized = adaptive_shadow_removal(image)

    # If we want to preserve some original character
    if preserve_original_lighting > 0:
        # Blend neutralized with original
        blend_factor = 1.0 - preserve_original_lighting
        neutralized = (
            neutralized.astype(np.float32) * blend_factor +
            image.astype(np.float32) * preserve_original_lighting
        ).astype(np.uint8)

    # Note: Actual shadow casting based on new sun position
    # is done in the compositor with elevation data.
    # This function prepares the base image.

    return neutralized


def create_shadow_free_base(
    image: NDArray[np.uint8],
    aggressive: bool = False,
) -> NDArray[np.uint8]:
    """Create a shadow-free base image for relighting.

    Attempts to remove all visible shadows to create a
    uniformly lit base that can be relit from any direction.

    Args:
        image: RGB image array
        aggressive: If True, use more aggressive shadow removal

    Returns:
        Shadow-free base image
    """
    if aggressive:
        # Multiple passes for stubborn shadows
        result = image
        for _ in range(2):
            result = neutralize_shadows(
                result,
                target_shadow_level=0.55,
                temperature_correction=0.7,
                detail_enhancement=0.5,
                transition_softness=20.0,
            )
        return result
    else:
        return neutralize_shadows(
            image,
            target_shadow_level=0.50,
            temperature_correction=0.6,
            detail_enhancement=0.4,
            transition_softness=15.0,
        )


def match_lighting_to_preset(
    image: NDArray[np.uint8],
    preset_azimuth: float,
    preset_altitude: float,
) -> Tuple[NDArray[np.uint8], dict]:
    """Prepare image to match a lighting preset.

    Analyzes the image to determine how well it matches the
    target preset, and returns adjustment recommendations.

    Args:
        image: RGB image array
        preset_azimuth: Target sun azimuth
        preset_altitude: Target sun altitude

    Returns:
        Tuple of (prepared image, adjustment info dict)
    """
    analysis = analyze_shadows(image)

    # Calculate how different the existing lighting is
    azimuth_diff = abs(analysis.estimated_sun_azimuth - preset_azimuth)
    if azimuth_diff > 180:
        azimuth_diff = 360 - azimuth_diff

    altitude_diff = abs(analysis.estimated_sun_altitude - preset_altitude)

    # If lighting is similar, less correction needed
    lighting_similarity = 1.0 - (azimuth_diff / 180.0) - (altitude_diff / 90.0)
    lighting_similarity = max(0.0, min(1.0, lighting_similarity))

    adjustment_info = {
        "original_azimuth": analysis.estimated_sun_azimuth,
        "original_altitude": analysis.estimated_sun_altitude,
        "target_azimuth": preset_azimuth,
        "target_altitude": preset_altitude,
        "azimuth_difference": azimuth_diff,
        "altitude_difference": altitude_diff,
        "lighting_similarity": lighting_similarity,
        "shadow_coverage": analysis.shadow_percentage,
        "recommendation": _get_recommendation(lighting_similarity, azimuth_diff),
    }

    # Prepare image based on similarity
    if lighting_similarity > 0.7:
        # Similar lighting - just enhance, don't remove shadows
        prepared = neutralize_shadows(
            image,
            target_shadow_level=0.40,
            temperature_correction=0.3,
            detail_enhancement=0.2,
            transition_softness=10.0,
        )
    elif lighting_similarity > 0.4:
        # Moderate difference - partial shadow removal
        prepared = neutralize_shadows(
            image,
            target_shadow_level=0.45,
            temperature_correction=0.5,
            detail_enhancement=0.3,
            transition_softness=15.0,
        )
    else:
        # Very different lighting - aggressive shadow removal
        prepared = create_shadow_free_base(image, aggressive=True)

    return prepared, adjustment_info


def _get_recommendation(similarity: float, azimuth_diff: float) -> str:
    """Get a text recommendation based on analysis."""
    if similarity > 0.7:
        return "Original lighting closely matches target. Light enhancement applied."
    elif similarity > 0.4:
        if azimuth_diff > 90:
            return "Sun direction differs significantly. Shadows partially neutralized."
        else:
            return "Moderate lighting difference. Balanced shadow correction applied."
    else:
        return "Lighting is very different from target. Aggressive shadow removal applied."
