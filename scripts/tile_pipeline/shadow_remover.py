"""
Shadow removal from satellite imagery using AI inpainting.

Removes baked-in shadows from aerial/satellite imagery to create a
clean base for re-lighting with ray-traced shadows. This enables
consistent, controllable shadow appearance across all tiles.

Methods:
1. LaMa (default) - High quality local inpainting
2. Color Transfer - Fast fallback using nearby lit regions
3. Replicate API - Cloud-based inpainting for maximum quality
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable
import math

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage
from PIL import Image, ImageFilter

from .shadow_analyzer import create_shadow_probability_map, analyze_shadows
from .color_space import rgb_to_lab, lab_to_rgb


class RemovalMethod(Enum):
    """Available shadow removal methods."""
    LAMA = "lama"           # Local AI inpainting (best quality)
    COLOR_TRANSFER = "color_transfer"  # Fast color sampling
    REPLICATE = "replicate"  # Cloud API (requires API key)


@dataclass
class RemovalResult:
    """Result from shadow removal operation."""

    image: NDArray[np.uint8]      # Shadow-free RGB image
    mask: NDArray[np.float32]     # Shadow mask that was used (0-1)
    method: RemovalMethod         # Method that was used
    confidence: float             # Estimated quality (0-1)

    # Optional debug info
    original_shadow_percentage: float = 0.0
    remaining_shadow_percentage: float = 0.0


class ShadowRemover:
    """Removes baked shadows from satellite/aerial imagery.

    The shadow remover detects shadows using multiple cues (luminosity,
    color temperature, texture) and then fills those regions using
    AI inpainting to estimate what the ground looks like without shadows.

    Example:
        remover = ShadowRemover()
        result = remover.remove(satellite_image)
        clean_image = result.image
    """

    def __init__(
        self,
        method: RemovalMethod = RemovalMethod.LAMA,
        shadow_threshold: float = 0.4,
        min_shadow_size: int = 50,
        dilate_mask: int = 3,
    ):
        """Initialize shadow remover.

        Args:
            method: Which removal method to use
            shadow_threshold: Probability threshold for shadow detection (0-1)
            min_shadow_size: Minimum shadow region size in pixels
            dilate_mask: Pixels to dilate shadow mask for better edge coverage
        """
        self.method = method
        self.shadow_threshold = shadow_threshold
        self.min_shadow_size = min_shadow_size
        self.dilate_mask = dilate_mask

        # Lazy-load LaMa model
        self._lama_model = None

    def remove(
        self,
        image: NDArray[np.uint8],
        mask: Optional[NDArray[np.float32]] = None,
    ) -> RemovalResult:
        """Remove shadows from an image.

        Args:
            image: RGB image array (H, W, 3)
            mask: Optional pre-computed shadow mask (0-1).
                  If None, will be auto-detected.

        Returns:
            RemovalResult with shadow-free image and metadata
        """
        # Step 1: Detect shadows if no mask provided
        if mask is None:
            mask = self._detect_shadow_mask(image)

        # Calculate original shadow coverage
        original_shadow_pct = (mask > self.shadow_threshold).mean() * 100

        # Step 2: Remove shadows using selected method
        if self.method == RemovalMethod.LAMA:
            result_image = self._remove_with_lama(image, mask)
            confidence = 0.85
        elif self.method == RemovalMethod.COLOR_TRANSFER:
            result_image = self._remove_with_color_transfer(image, mask)
            confidence = 0.6
        elif self.method == RemovalMethod.REPLICATE:
            result_image = self._remove_with_replicate(image, mask)
            confidence = 0.9
        else:
            raise ValueError(f"Unknown method: {self.method}")

        # Step 3: Verify removal quality
        new_mask = self._detect_shadow_mask(result_image)
        remaining_shadow_pct = (new_mask > self.shadow_threshold).mean() * 100

        # Adjust confidence based on remaining shadows
        if remaining_shadow_pct > original_shadow_pct * 0.5:
            confidence *= 0.7  # Reduce if many shadows remain

        return RemovalResult(
            image=result_image,
            mask=mask,
            method=self.method,
            confidence=confidence,
            original_shadow_percentage=original_shadow_pct,
            remaining_shadow_percentage=remaining_shadow_pct,
        )

    def _detect_shadow_mask(self, image: NDArray[np.uint8]) -> NDArray[np.float32]:
        """Detect shadows and create a clean binary mask.

        Uses the shadow probability map and cleans it up with
        morphological operations for better inpainting results.
        """
        # Get soft probability map
        prob_map = create_shadow_probability_map(image)

        # Threshold to binary
        binary_mask = (prob_map > self.shadow_threshold).astype(np.float32)

        # Clean up small noise
        if self.min_shadow_size > 0:
            binary_mask = self._remove_small_regions(binary_mask, self.min_shadow_size)

        # Dilate to ensure complete coverage of shadow edges
        if self.dilate_mask > 0:
            kernel = np.ones((self.dilate_mask, self.dilate_mask))
            binary_mask = ndimage.binary_dilation(binary_mask, kernel).astype(np.float32)

        # Feather edges slightly for better blending
        binary_mask = ndimage.gaussian_filter(binary_mask, sigma=1.0)

        return binary_mask.astype(np.float32)

    def _remove_small_regions(
        self,
        mask: NDArray[np.float32],
        min_size: int,
    ) -> NDArray[np.float32]:
        """Remove small regions from binary mask."""
        labeled, num_features = ndimage.label(mask > 0.5)

        for i in range(1, num_features + 1):
            region_size = (labeled == i).sum()
            if region_size < min_size:
                mask[labeled == i] = 0

        return mask

    def _remove_with_lama(
        self,
        image: NDArray[np.uint8],
        mask: NDArray[np.float32],
    ) -> NDArray[np.uint8]:
        """Remove shadows using LaMa inpainting model.

        LaMa (Large Mask Inpainting) is a state-of-the-art inpainting model
        that works well for large mask regions like shadows.
        """
        try:
            from simple_lama_inpainting import SimpleLama

            if self._lama_model is None:
                self._lama_model = SimpleLama()

            # Convert to PIL Images (LaMa expects this)
            pil_image = Image.fromarray(image)
            pil_mask = Image.fromarray((mask * 255).astype(np.uint8))

            # Run inpainting
            result = self._lama_model(pil_image, pil_mask)

            return np.array(result)

        except ImportError:
            print("Warning: simple-lama-inpainting not installed. "
                  "Falling back to color transfer method.")
            print("Install with: pip install simple-lama-inpainting")
            return self._remove_with_color_transfer(image, mask)

    def _remove_with_color_transfer(
        self,
        image: NDArray[np.uint8],
        mask: NDArray[np.float32],
    ) -> NDArray[np.float32]:
        """Remove shadows using color transfer from lit regions.

        This is a fast fallback method that:
        1. Identifies shadow regions
        2. Samples colors from nearby lit regions
        3. Transfers/adjusts colors to fill shadows

        Quality is lower than AI methods but very fast.
        """
        # Work in LAB color space for perceptual correctness
        lab = rgb_to_lab(image)

        # Create lit region mask (inverse of shadow)
        lit_mask = 1.0 - mask
        lit_region = lit_mask > 0.5
        shadow_region = mask > 0.5

        if not shadow_region.any() or not lit_region.any():
            # No shadows or no lit areas - return original
            return image

        # Calculate statistics of lit regions
        lit_L_mean = lab[lit_region, 0].mean()
        lit_L_std = lab[lit_region, 0].std()
        lit_a_mean = lab[lit_region, 1].mean()
        lit_b_mean = lab[lit_region, 2].mean()

        # Calculate statistics of shadow regions
        shadow_L_mean = lab[shadow_region, 0].mean()
        shadow_L_std = max(lab[shadow_region, 0].std(), 0.1)  # Avoid div by zero

        # Create result
        result_lab = lab.copy()

        # Lightness adjustment: transfer mean and std from lit to shadow
        # L' = (L - shadow_mean) * (lit_std / shadow_std) + lit_mean
        L_adjusted = (result_lab[..., 0] - shadow_L_mean) * (lit_L_std / shadow_L_std) + lit_L_mean

        # Blend adjusted lightness into shadow regions
        blend_factor = mask[..., np.newaxis] if mask.ndim == 2 else mask
        result_lab[..., 0] = (
            result_lab[..., 0] * (1 - mask) +
            L_adjusted * mask
        )

        # Slight color shift towards lit region colors (shadows are often cooler)
        color_shift_strength = 0.3
        result_lab[..., 1] = (
            result_lab[..., 1] * (1 - mask * color_shift_strength) +
            lit_a_mean * mask * color_shift_strength
        )
        result_lab[..., 2] = (
            result_lab[..., 2] * (1 - mask * color_shift_strength) +
            lit_b_mean * mask * color_shift_strength
        )

        # Convert back to RGB
        result = lab_to_rgb(result_lab)

        # Final Gaussian blur at edges for smooth blending
        edge_mask = ndimage.sobel(mask) > 0.1
        if edge_mask.any():
            blurred = ndimage.gaussian_filter(result.astype(np.float32), sigma=[2, 2, 0])
            edge_blend = edge_mask[..., np.newaxis].astype(np.float32)
            result = (result * (1 - edge_blend) + blurred * edge_blend).astype(np.uint8)

        return result

    def _remove_with_replicate(
        self,
        image: NDArray[np.uint8],
        mask: NDArray[np.float32],
    ) -> NDArray[np.uint8]:
        """Remove shadows using Replicate API (cloud-based).

        Uses Stable Diffusion inpainting for highest quality.
        Requires REPLICATE_API_TOKEN environment variable.
        """
        import os

        api_token = os.environ.get("REPLICATE_API_TOKEN")
        if not api_token:
            print("Warning: REPLICATE_API_TOKEN not set. "
                  "Falling back to color transfer method.")
            return self._remove_with_color_transfer(image, mask)

        try:
            import replicate
            import base64
            from io import BytesIO

            # Convert to base64 for API
            pil_image = Image.fromarray(image)
            pil_mask = Image.fromarray((mask * 255).astype(np.uint8))

            def to_base64(img: Image.Image) -> str:
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                return base64.b64encode(buffer.getvalue()).decode()

            # Call Replicate API
            output = replicate.run(
                "stability-ai/stable-diffusion-inpainting",
                input={
                    "image": f"data:image/png;base64,{to_base64(pil_image)}",
                    "mask": f"data:image/png;base64,{to_base64(pil_mask)}",
                    "prompt": "satellite aerial view ground texture, seamless",
                    "negative_prompt": "shadow, dark, black",
                    "num_inference_steps": 25,
                    "guidance_scale": 7.5,
                }
            )

            # Download and return result
            import requests
            response = requests.get(output[0])
            result_image = Image.open(BytesIO(response.content))
            return np.array(result_image.convert("RGB"))

        except Exception as e:
            print(f"Warning: Replicate API failed: {e}. "
                  "Falling back to color transfer method.")
            return self._remove_with_color_transfer(image, mask)


def remove_shadows(
    image: NDArray[np.uint8],
    method: str = "lama",
    **kwargs,
) -> NDArray[np.uint8]:
    """Convenience function to remove shadows from an image.

    Args:
        image: RGB image array (H, W, 3)
        method: "lama", "color_transfer", or "replicate"
        **kwargs: Additional arguments passed to ShadowRemover

    Returns:
        Shadow-free RGB image

    Example:
        clean = remove_shadows(satellite_tile)
        clean = remove_shadows(tile, method="color_transfer")  # Fast fallback
    """
    method_enum = RemovalMethod(method)
    remover = ShadowRemover(method=method_enum, **kwargs)
    result = remover.remove(image)
    return result.image


def create_shadow_removal_mask(
    image: NDArray[np.uint8],
    threshold: float = 0.4,
    min_size: int = 50,
    dilate: int = 3,
) -> NDArray[np.float32]:
    """Create a shadow mask suitable for inpainting.

    This is useful when you want to use your own inpainting method
    but need the shadow detection from this module.

    Args:
        image: RGB image array
        threshold: Shadow probability threshold (0-1)
        min_size: Minimum shadow region size in pixels
        dilate: Dilation amount in pixels

    Returns:
        Binary mask (0-1) where 1 = shadow region
    """
    remover = ShadowRemover(
        shadow_threshold=threshold,
        min_shadow_size=min_size,
        dilate_mask=dilate,
    )
    return remover._detect_shadow_mask(image)
