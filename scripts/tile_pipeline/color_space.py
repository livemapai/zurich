"""
Color space conversions for perceptually accurate compositing.

Implements RGB ↔ XYZ ↔ LAB conversions using pure NumPy for performance.
All operations are vectorized for efficient tile processing.

LAB color space separates lightness (L) from chromaticity (a, b), enabling
perceptually uniform blending that avoids the color shifts seen in RGB.

References:
- CIE 1976 LAB color space specification
- sRGB to XYZ transformation (IEC 61966-2-1)
"""

import numpy as np
from numpy.typing import NDArray


# D65 illuminant reference white point
D65_WHITE = np.array([0.95047, 1.0, 1.08883])

# sRGB to XYZ transformation matrix
SRGB_TO_XYZ = np.array([
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041]
])

# XYZ to sRGB transformation matrix (inverse)
XYZ_TO_SRGB = np.array([
    [ 3.2404542, -1.5371385, -0.4985314],
    [-0.9692660,  1.8760108,  0.0415560],
    [ 0.0556434, -0.2040259,  1.0572252]
])


def _srgb_to_linear(srgb: NDArray[np.float64]) -> NDArray[np.float64]:
    """Convert sRGB (gamma-corrected) to linear RGB.

    The sRGB transfer function has a linear portion near black and
    a gamma curve (~2.4) for the rest.
    """
    linear = np.where(
        srgb <= 0.04045,
        srgb / 12.92,
        ((srgb + 0.055) / 1.055) ** 2.4
    )
    return linear


def _linear_to_srgb(linear: NDArray[np.float64]) -> NDArray[np.float64]:
    """Convert linear RGB to sRGB (gamma-corrected)."""
    srgb = np.where(
        linear <= 0.0031308,
        linear * 12.92,
        1.055 * (linear ** (1 / 2.4)) - 0.055
    )
    return np.clip(srgb, 0, 1)


def _xyz_to_lab_f(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """LAB forward transformation function.

    Uses cube root for values > delta³, linear for smaller values
    to avoid numerical issues near zero.
    """
    delta = 6 / 29
    return np.where(
        t > delta ** 3,
        np.cbrt(t),
        t / (3 * delta ** 2) + 4 / 29
    )


def _lab_to_xyz_f(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """LAB inverse transformation function."""
    delta = 6 / 29
    return np.where(
        t > delta,
        t ** 3,
        3 * delta ** 2 * (t - 4 / 29)
    )


def rgb_to_xyz(rgb: NDArray[np.uint8]) -> NDArray[np.float64]:
    """Convert RGB image (0-255) to XYZ color space.

    Args:
        rgb: Image array of shape (H, W, 3) with uint8 values

    Returns:
        XYZ array of shape (H, W, 3) with float64 values
    """
    # Normalize to 0-1 range
    rgb_normalized = rgb.astype(np.float64) / 255.0

    # sRGB gamma correction to linear
    linear = _srgb_to_linear(rgb_normalized)

    # Apply transformation matrix
    # Reshape for matrix multiplication: (H, W, 3) -> (H*W, 3) -> transpose
    h, w = rgb.shape[:2]
    linear_flat = linear.reshape(-1, 3)
    xyz_flat = linear_flat @ SRGB_TO_XYZ.T

    return xyz_flat.reshape(h, w, 3)


def xyz_to_rgb(xyz: NDArray[np.float64]) -> NDArray[np.uint8]:
    """Convert XYZ color space to RGB image (0-255).

    Args:
        xyz: XYZ array of shape (H, W, 3) with float64 values

    Returns:
        RGB array of shape (H, W, 3) with uint8 values
    """
    h, w = xyz.shape[:2]
    xyz_flat = xyz.reshape(-1, 3)

    # Apply inverse transformation matrix
    linear_flat = xyz_flat @ XYZ_TO_SRGB.T
    linear = linear_flat.reshape(h, w, 3)

    # Clamp negative values from out-of-gamut colors
    linear = np.clip(linear, 0, None)

    # Apply gamma correction
    srgb = _linear_to_srgb(linear)

    # Convert to uint8
    return (srgb * 255).astype(np.uint8)


def xyz_to_lab(xyz: NDArray[np.float64]) -> NDArray[np.float64]:
    """Convert XYZ to LAB color space.

    Args:
        xyz: XYZ array of shape (H, W, 3)

    Returns:
        LAB array of shape (H, W, 3) where:
        - L: Lightness (0-100)
        - a: Green-Red axis (~-128 to +127)
        - b: Blue-Yellow axis (~-128 to +127)
    """
    # Normalize by D65 white point
    xyz_normalized = xyz / D65_WHITE

    # Apply forward transformation
    f_xyz = _xyz_to_lab_f(xyz_normalized)

    # Compute LAB values
    L = 116 * f_xyz[..., 1] - 16
    a = 500 * (f_xyz[..., 0] - f_xyz[..., 1])
    b = 200 * (f_xyz[..., 1] - f_xyz[..., 2])

    return np.stack([L, a, b], axis=-1)


def lab_to_xyz(lab: NDArray[np.float64]) -> NDArray[np.float64]:
    """Convert LAB to XYZ color space.

    Args:
        lab: LAB array of shape (H, W, 3)

    Returns:
        XYZ array of shape (H, W, 3)
    """
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]

    # Compute f(Y), f(X), f(Z)
    f_Y = (L + 16) / 116
    f_X = f_Y + a / 500
    f_Z = f_Y - b / 200

    # Apply inverse transformation and denormalize
    X = _lab_to_xyz_f(f_X) * D65_WHITE[0]
    Y = _lab_to_xyz_f(f_Y) * D65_WHITE[1]
    Z = _lab_to_xyz_f(f_Z) * D65_WHITE[2]

    return np.stack([X, Y, Z], axis=-1)


def rgb_to_lab(rgb: NDArray[np.uint8]) -> NDArray[np.float64]:
    """Convert RGB image (0-255) to LAB color space.

    This is the main function for preparing images for perceptual blending.

    Args:
        rgb: Image array of shape (H, W, 3) with uint8 values

    Returns:
        LAB array of shape (H, W, 3) with:
        - L: 0-100
        - a: ~-128 to +127
        - b: ~-128 to +127
    """
    xyz = rgb_to_xyz(rgb)
    return xyz_to_lab(xyz)


def lab_to_rgb(lab: NDArray[np.float64]) -> NDArray[np.uint8]:
    """Convert LAB color space to RGB image (0-255).

    This is the main function for converting composited results back to RGB.

    Args:
        lab: LAB array of shape (H, W, 3)

    Returns:
        RGB array of shape (H, W, 3) with uint8 values
    """
    xyz = lab_to_xyz(lab)
    return xyz_to_rgb(xyz)


def adjust_lightness(
    lab: NDArray[np.float64],
    factor: float
) -> NDArray[np.float64]:
    """Adjust the lightness channel of a LAB image.

    Args:
        lab: LAB array of shape (H, W, 3)
        factor: Multiplier for lightness (1.0 = no change)

    Returns:
        LAB array with adjusted lightness
    """
    result = lab.copy()
    result[..., 0] = np.clip(result[..., 0] * factor, 0, 100)
    return result


def blend_lab(
    base: NDArray[np.float64],
    overlay: NDArray[np.float64],
    alpha: float = 0.5
) -> NDArray[np.float64]:
    """Simple alpha blend in LAB space.

    More perceptually accurate than RGB blending.

    Args:
        base: Base LAB image
        overlay: Overlay LAB image
        alpha: Blend factor (0 = base, 1 = overlay)

    Returns:
        Blended LAB image
    """
    return base * (1 - alpha) + overlay * alpha
