"""
Photoshop-style blend modes for LAB color space compositing.

These blend modes operate on normalized values (0-1 for lightness in LAB,
or 0-255 converted to 0-1 for RGB). All functions are vectorized with NumPy.

Each blend mode supports an opacity parameter for partial blending.
"""

import numpy as np
from numpy.typing import NDArray
from typing import Literal


BlendMode = Literal["multiply", "soft_light", "screen", "overlay", "normal"]


def _normalize_lightness(L: NDArray[np.float64]) -> NDArray[np.float64]:
    """Normalize LAB lightness (0-100) to 0-1 range."""
    return L / 100.0


def _denormalize_lightness(L_norm: NDArray[np.float64]) -> NDArray[np.float64]:
    """Convert normalized lightness back to LAB range (0-100)."""
    return np.clip(L_norm * 100.0, 0, 100)


def multiply(
    base: NDArray[np.float64],
    blend: NDArray[np.float64],
    opacity: float = 1.0
) -> NDArray[np.float64]:
    """Multiply blend mode - darkens the image.

    Formula: result = base × blend

    This is the standard blend mode for shadows. Multiplying by a gray
    value darkens proportionally; pure white (1.0) has no effect,
    pure black (0.0) results in black.

    Args:
        base: Base layer (LAB lightness or normalized 0-1 values)
        blend: Blend layer (0-1 grayscale, where 0=black, 1=white)
        opacity: Blend strength (0-1)

    Returns:
        Blended result in same range as input
    """
    # Only expand blend if base has more dimensions (e.g., base is RGB)
    if base.ndim > blend.ndim:
        blend = blend[..., np.newaxis]

    result = base * blend
    return base * (1 - opacity) + result * opacity


def screen(
    base: NDArray[np.float64],
    blend: NDArray[np.float64],
    opacity: float = 1.0
) -> NDArray[np.float64]:
    """Screen blend mode - lightens the image.

    Formula: result = 1 - (1 - base) × (1 - blend)

    The inverse of multiply. Useful for highlights and lightening effects.
    Pure black (0.0) has no effect, pure white (1.0) results in white.

    Args:
        base: Base layer (normalized 0-1)
        blend: Blend layer (normalized 0-1)
        opacity: Blend strength (0-1)

    Returns:
        Blended result (0-1)
    """
    if base.ndim > blend.ndim:
        blend = blend[..., np.newaxis]

    result = 1 - (1 - base) * (1 - blend)
    return base * (1 - opacity) + result * opacity


def soft_light(
    base: NDArray[np.float64],
    blend: NDArray[np.float64],
    opacity: float = 1.0
) -> NDArray[np.float64]:
    """Soft Light blend mode - gentle contrast enhancement.

    This is the Photoshop formula which produces smoother results
    than the simpler Pegtop formula.

    Formula (Photoshop):
        if blend <= 0.5: result = base - (1 - 2×blend) × base × (1 - base)
        if blend > 0.5:  result = base + (2×blend - 1) × (D(base) - base)
        where D(x) = sqrt(x) if x <= 0.25, else ((16x-12)x+4)x

    Soft Light is ideal for hillshade overlays because it preserves
    colors while adding subtle depth. Values below 0.5 darken slightly,
    values above 0.5 lighten slightly.

    Args:
        base: Base layer (normalized 0-1)
        blend: Blend layer (normalized 0-1)
        opacity: Blend strength (0-1)

    Returns:
        Blended result (0-1)
    """
    if base.ndim > blend.ndim:
        blend = blend[..., np.newaxis]

    # D function for Photoshop Soft Light
    def D(x: NDArray[np.float64]) -> NDArray[np.float64]:
        return np.where(
            x <= 0.25,
            ((16 * x - 12) * x + 4) * x,
            np.sqrt(x)
        )

    # Apply formula based on blend value
    result = np.where(
        blend <= 0.5,
        base - (1 - 2 * blend) * base * (1 - base),
        base + (2 * blend - 1) * (D(base) - base)
    )

    return base * (1 - opacity) + result * opacity


def overlay(
    base: NDArray[np.float64],
    blend: NDArray[np.float64],
    opacity: float = 1.0
) -> NDArray[np.float64]:
    """Overlay blend mode - combines multiply and screen.

    Formula:
        if base <= 0.5: result = 2 × base × blend
        if base > 0.5:  result = 1 - 2 × (1 - base) × (1 - blend)

    Overlay darkens dark areas and lightens light areas, based on the
    base layer. This increases contrast while preserving highlights
    and shadows.

    Args:
        base: Base layer (normalized 0-1)
        blend: Blend layer (normalized 0-1)
        opacity: Blend strength (0-1)

    Returns:
        Blended result (0-1)
    """
    if base.ndim > blend.ndim:
        blend = blend[..., np.newaxis]

    result = np.where(
        base <= 0.5,
        2 * base * blend,
        1 - 2 * (1 - base) * (1 - blend)
    )

    return base * (1 - opacity) + result * opacity


def normal(
    base: NDArray[np.float64],
    blend: NDArray[np.float64],
    opacity: float = 1.0
) -> NDArray[np.float64]:
    """Normal blend mode - simple alpha compositing.

    Args:
        base: Base layer
        blend: Blend layer
        opacity: Blend strength (0-1)

    Returns:
        Blended result
    """
    return base * (1 - opacity) + blend * opacity


def apply_blend(
    base: NDArray[np.float64],
    blend: NDArray[np.float64],
    mode: BlendMode,
    opacity: float = 1.0
) -> NDArray[np.float64]:
    """Apply a blend mode by name.

    Args:
        base: Base layer (normalized 0-1 or LAB)
        blend: Blend layer
        mode: One of "multiply", "soft_light", "screen", "overlay", "normal"
        opacity: Blend strength (0-1)

    Returns:
        Blended result

    Raises:
        ValueError: If mode is not recognized
    """
    modes = {
        "multiply": multiply,
        "soft_light": soft_light,
        "screen": screen,
        "overlay": overlay,
        "normal": normal,
    }

    if mode not in modes:
        raise ValueError(f"Unknown blend mode: {mode}. Use one of {list(modes.keys())}")

    return modes[mode](base, blend, opacity)


def blend_lab_lightness(
    lab: NDArray[np.float64],
    blend_mask: NDArray[np.float64],
    mode: BlendMode = "multiply",
    opacity: float = 1.0
) -> NDArray[np.float64]:
    """Apply blend mode to LAB lightness channel only.

    This is the primary compositing function for shadows and hillshade,
    which should affect brightness without shifting colors.

    Args:
        lab: LAB image of shape (H, W, 3)
        blend_mask: Grayscale mask of shape (H, W) with values 0-1
            where 0 = darken fully, 1 = no change (for multiply mode)
        mode: Blend mode to apply
        opacity: Blend strength

    Returns:
        LAB image with modified lightness
    """
    result = lab.copy()

    # Normalize lightness to 0-1 for blending
    L_norm = _normalize_lightness(lab[..., 0])

    # Apply blend
    L_blended = apply_blend(L_norm, blend_mask, mode, opacity)

    # Convert back to LAB range
    result[..., 0] = _denormalize_lightness(L_blended)

    return result


def blend_lab_color_shift(
    lab: NDArray[np.float64],
    shift_a: NDArray[np.float64],
    shift_b: NDArray[np.float64],
    mask: NDArray[np.float64],
    strength: float = 1.0
) -> NDArray[np.float64]:
    """Apply color shift to LAB a and b channels based on mask.

    Used for Imhof-style warm/cool tinting where sunlit slopes
    get yellow tint and shaded slopes get blue tint.

    Args:
        lab: LAB image of shape (H, W, 3)
        shift_a: Amount to shift 'a' channel (green-red axis)
        shift_b: Amount to shift 'b' channel (blue-yellow axis)
        mask: Mask of shape (H, W) controlling where shift applies (0-1)
        strength: Overall strength of the color shift

    Returns:
        LAB image with shifted colors
    """
    result = lab.copy()

    # Apply masked color shifts
    result[..., 1] += shift_a * mask * strength
    result[..., 2] += shift_b * mask * strength

    # Clamp to valid LAB range
    result[..., 1] = np.clip(result[..., 1], -128, 127)
    result[..., 2] = np.clip(result[..., 2], -128, 127)

    return result
