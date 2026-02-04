"""
Extract intermediate products from Blender shadow buffer for deck.gl enhancement.

This script demonstrates extracting useful data products:
1. Building mask (rooftops) - for LOD transitions
2. Ground contact shadows (AO) - for grounding buildings
3. Edge maps - for wireframe overlays
4. Tree crown silhouettes - for billboard generation
5. Shadow probability/softness - for soft AO textures
"""

import numpy as np
from PIL import Image, ImageFilter
from pathlib import Path
from typing import Tuple
import cv2


def load_shadow_buffer(path: str) -> np.ndarray:
    """Load shadow buffer as float32 array."""
    img = Image.open(path).convert("L")
    return np.array(img).astype(np.float32) / 255.0


def extract_building_mask(shadow_buffer: np.ndarray, percentile: float = 85) -> np.ndarray:
    """Extract bright areas (rooftops/lit surfaces) as building mask.

    In the shadow buffer:
    - Rooftops are brightest (direct sunlight, no occlusion)
    - Streets are medium gray (some ambient)
    - Shadows are dark

    Uses percentile-based threshold to adapt to different shadow buffer ranges.

    Returns:
        Binary mask where 1 = likely rooftop/building top
    """
    # Use adaptive threshold based on percentile
    threshold = np.percentile(shadow_buffer, percentile)
    mask = (shadow_buffer > threshold).astype(np.float32)
    return mask


def extract_shadow_contact(shadow_buffer: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    """Extract ground contact shadows (ambient occlusion proxy).

    These are the darkest areas right at building bases where
    light has the hardest time reaching.

    Perfect for making buildings feel "grounded" in deck.gl.

    Returns:
        Float array where higher = stronger AO effect needed
    """
    # Invert: we want dark areas to be high values
    inverted = 1.0 - shadow_buffer

    # Apply morphological operations to get contact regions
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))

    # Erode to focus on deep shadow areas
    eroded = cv2.erode(inverted, kernel, iterations=1)

    # Blur for soft falloff
    ao_map = cv2.GaussianBlur(eroded, (kernel_size * 2 + 1, kernel_size * 2 + 1), 0)

    return ao_map


def extract_edge_map(shadow_buffer: np.ndarray, low: int = 50, high: int = 150) -> np.ndarray:
    """Extract edges using Canny edge detection.

    The shadow buffer has sharp transitions at:
    - Building edges (rooftop to shadow)
    - Shadow terminator lines
    - Tree crown boundaries

    Returns:
        Binary edge map
    """
    # Convert to uint8 for Canny
    img_uint8 = (shadow_buffer * 255).astype(np.uint8)

    # Canny edge detection
    edges = cv2.Canny(img_uint8, low, high)

    return edges.astype(np.float32) / 255.0


def extract_shadow_softness(shadow_buffer: np.ndarray) -> np.ndarray:
    """Extract shadow softness/gradient map.

    Areas with gradual transitions = soft shadows (penumbra)
    Areas with sharp transitions = hard shadows

    This can be used as a "soft AO" texture in deck.gl.

    Returns:
        Gradient magnitude map (high = sharp transition)
    """
    # Sobel gradients
    grad_x = cv2.Sobel(shadow_buffer, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(shadow_buffer, cv2.CV_32F, 0, 1, ksize=3)

    # Gradient magnitude
    magnitude = np.sqrt(grad_x**2 + grad_y**2)

    # Normalize
    magnitude = magnitude / (magnitude.max() + 1e-6)

    return magnitude


def extract_tree_silhouettes(
    shadow_buffer: np.ndarray,
    building_mask: np.ndarray,
    min_blob_size: int = 50,
    max_blob_size: int = 2000,
) -> Tuple[np.ndarray, list]:
    """Extract tree crown silhouettes from shadow buffer.

    Trees cast distinctive circular/irregular shadows different from
    the rectangular building shadows.

    Returns:
        (tree_mask, list of (x, y, radius) for detected crowns)
    """
    # Get shadow regions (dark areas) - use adaptive threshold
    shadow_threshold = np.percentile(shadow_buffer, 30)
    shadow_mask = (shadow_buffer < shadow_threshold).astype(np.uint8)

    # Dilate building mask to exclude nearby shadows
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    building_dilated = cv2.dilate(building_mask.astype(np.uint8), kernel, iterations=1)

    # Remove building regions
    non_building_shadow = shadow_mask & (~building_dilated)

    # Find contours (potential tree shadows)
    contours, _ = cv2.findContours(
        non_building_shadow,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    tree_mask = np.zeros_like(shadow_buffer)
    tree_crowns = []

    for contour in contours:
        area = cv2.contourArea(contour)

        # Filter by size (trees are small-medium blobs)
        if min_blob_size < area < max_blob_size:
            # Get enclosing circle
            (x, y), radius = cv2.minEnclosingCircle(contour)

            # Check circularity (trees are roughly circular)
            perimeter = cv2.arcLength(contour, True)
            circularity = 4 * np.pi * area / (perimeter**2 + 1e-6)

            if circularity > 0.3:  # Reasonably circular
                tree_crowns.append((int(x), int(y), int(radius)))
                cv2.drawContours(tree_mask, [contour], -1, 1.0, -1)

    return tree_mask, tree_crowns


def create_ao_texture(
    shadow_buffer: np.ndarray,
    contact_strength: float = 0.7,
    soft_strength: float = 0.3,
) -> np.ndarray:
    """Create ambient occlusion texture for deck.gl ground plane.

    Combines:
    - Contact shadows (at building bases)
    - Soft shadow gradients (for penumbra)

    Returns:
        AO texture where 0 = full shadow, 1 = no shadow
    """
    # Get contact shadows
    contact = extract_shadow_contact(shadow_buffer)

    # Get soft shadow regions
    soft = 1.0 - shadow_buffer

    # Blend
    ao = contact * contact_strength + soft * soft_strength

    # Clamp
    ao = np.clip(ao, 0, 1)

    # Invert for typical AO convention (1 = no occlusion)
    return 1.0 - ao


def save_product(array: np.ndarray, path: str, colormap: str = None):
    """Save array as image, optionally with colormap."""
    if colormap:
        import matplotlib.pyplot as plt
        plt.imsave(path, array, cmap=colormap)
    else:
        img = Image.fromarray((array * 255).astype(np.uint8))
        img.save(path)


def process_shadow_buffer(input_path: str, output_dir: str):
    """Process shadow buffer and extract all intermediate products."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading shadow buffer: {input_path}")
    shadow = load_shadow_buffer(input_path)
    print(f"  Shape: {shadow.shape}")
    print(f"  Range: [{shadow.min():.2f}, {shadow.max():.2f}]")

    # 1. Building/rooftop mask
    print("\nExtracting building mask...")
    building_mask = extract_building_mask(shadow)
    save_product(building_mask, output_dir / "01_building_mask.png")
    print(f"  Saved: 01_building_mask.png")

    # 2. Ground contact AO
    print("\nExtracting contact shadows (AO)...")
    contact_ao = extract_shadow_contact(shadow)
    save_product(contact_ao, output_dir / "02_contact_ao.png")
    save_product(contact_ao, output_dir / "02_contact_ao_heat.png", colormap="hot")
    print(f"  Saved: 02_contact_ao.png")

    # 3. Edge map
    print("\nExtracting edge map...")
    edges = extract_edge_map(shadow)
    save_product(edges, output_dir / "03_edge_map.png")
    print(f"  Saved: 03_edge_map.png")

    # 4. Shadow softness/gradient
    print("\nExtracting shadow softness map...")
    softness = extract_shadow_softness(shadow)
    save_product(softness, output_dir / "04_shadow_softness.png")
    save_product(softness, output_dir / "04_shadow_softness_heat.png", colormap="plasma")
    print(f"  Saved: 04_shadow_softness.png")

    # 5. Tree silhouettes
    print("\nExtracting tree silhouettes...")
    tree_mask, crowns = extract_tree_silhouettes(shadow, building_mask)
    save_product(tree_mask, output_dir / "05_tree_silhouettes.png")
    print(f"  Found {len(crowns)} potential tree crowns")
    print(f"  Saved: 05_tree_silhouettes.png")

    # 6. Combined AO texture (ready for deck.gl)
    print("\nCreating combined AO texture...")
    ao_texture = create_ao_texture(shadow)
    save_product(ao_texture, output_dir / "06_ao_texture.png")
    print(f"  Saved: 06_ao_texture.png")

    # 7. Create comparison image
    print("\nCreating comparison grid...")
    create_comparison_grid(
        shadow, building_mask, contact_ao, edges, softness, tree_mask, ao_texture,
        output_dir / "07_comparison.png"
    )
    print(f"  Saved: 07_comparison.png")

    print("\n✓ All products extracted!")
    return {
        "building_mask": building_mask,
        "contact_ao": contact_ao,
        "edges": edges,
        "softness": softness,
        "tree_mask": tree_mask,
        "tree_crowns": crowns,
        "ao_texture": ao_texture,
    }


def create_comparison_grid(
    shadow, building_mask, contact_ao, edges, softness, tree_mask, ao_texture,
    output_path: str
):
    """Create side-by-side comparison of all products."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 4, figsize=(16, 8))

    titles = [
        ("Original Shadow Buffer", shadow, "gray"),
        ("Building Mask", building_mask, "gray"),
        ("Contact AO", contact_ao, "hot"),
        ("Edge Map", edges, "gray"),
        ("Shadow Softness", softness, "plasma"),
        ("Tree Silhouettes", tree_mask, "Greens"),
        ("Combined AO", ao_texture, "gray"),
        ("Inverted AO (for deck.gl)", 1 - ao_texture, "gray"),
    ]

    for ax, (title, data, cmap) in zip(axes.flat, titles):
        ax.imshow(data, cmap=cmap)
        ax.set_title(title, fontsize=10)
        ax.axis("off")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        # Default to test output
        input_path = "test_output/blender/real_shadow_buffer.png"
        output_dir = "test_output/intermediates"
    else:
        input_path = sys.argv[1]
        output_dir = sys.argv[2] if len(sys.argv) > 2 else "test_output/intermediates"

    process_shadow_buffer(input_path, output_dir)
