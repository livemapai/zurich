"""
Tile compositing orchestrator.

Combines all layers (satellite, hillshade, shadows) into final photorealistic tiles.
All compositing is done in LAB color space for perceptually accurate blending.

Compositing Stack (bottom to top):
1. Base Satellite Imagery (SWISSIMAGE 10cm)
2. Hillshade + Imhof Color Shifts (soft light blend)
3. Building Shadows (multiply blend)
4. Tree Shadows (multiply blend)
5. Ambient Occlusion (multiply blend)

V2 Pipeline (with shadow removal + ray tracing):
1. Satellite with baked shadows removed (via AI inpainting)
2. Hillshade + Imhof Color Shifts
3. Ray-traced shadows from 3D scene
4. Time-of-day color grading
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
from numpy.typing import NDArray

from .color_space import rgb_to_lab, lab_to_rgb
from .blend_modes import blend_lab_lightness, blend_lab_color_shift
from .config import PipelineConfig
from .time_presets import TimePreset, get_preset


@dataclass
class TileLayers:
    """Container for all layers needed for compositing."""

    satellite: NDArray[np.uint8]  # RGB (H, W, 3)
    hillshade: NDArray[np.float32]  # Grayscale (H, W) values 0-1
    imhof_shift_a: NDArray[np.float32]  # LAB 'a' shift (H, W)
    imhof_shift_b: NDArray[np.float32]  # LAB 'b' shift (H, W)
    building_shadows: NDArray[np.float32]  # Grayscale (H, W) values 0-1
    tree_shadows: Optional[NDArray[np.float32]] = None  # Grayscale (H, W)
    ambient_occlusion: Optional[NDArray[np.float32]] = None  # Grayscale (H, W)


class TileCompositor:
    """Composites multiple layers into final photorealistic tiles."""

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        preset: Optional[TimePreset] = None,
    ):
        """Initialize compositor.

        Args:
            config: Pipeline configuration
            preset: Time preset for lighting parameters
        """
        self.config = config or PipelineConfig()
        self.preset = preset or get_preset("afternoon")

    def composite(self, layers: TileLayers) -> NDArray[np.uint8]:
        """Composite all layers into final RGB image.

        Args:
            layers: TileLayers container with all source layers

        Returns:
            Final composited RGB image (H, W, 3)
        """
        # Convert satellite to LAB for perceptual blending
        lab = rgb_to_lab(layers.satellite)

        # 1. Apply hillshade (soft light on lightness)
        lab = blend_lab_lightness(
            lab,
            layers.hillshade,
            mode=self.config.blend.hillshade_mode,
            opacity=self.config.blend.hillshade_opacity,
        )

        # 2. Apply Imhof color shifts (warm/cool tinting)
        lab = blend_lab_color_shift(
            lab,
            shift_a=layers.imhof_shift_a,
            shift_b=layers.imhof_shift_b,
            mask=np.ones_like(layers.hillshade),  # Apply everywhere
            strength=1.0,  # Shifts already have strength baked in
        )

        # 3. Apply building shadows (multiply on lightness)
        lab = blend_lab_lightness(
            lab,
            layers.building_shadows,
            mode=self.config.blend.building_shadow_mode,
            opacity=self.config.blend.building_shadow_opacity,
        )

        # 4. Apply tree shadows if present
        if layers.tree_shadows is not None:
            lab = blend_lab_lightness(
                lab,
                layers.tree_shadows,
                mode=self.config.blend.tree_shadow_mode,
                opacity=self.config.blend.tree_shadow_opacity,
            )

        # 5. Apply ambient occlusion if present
        if layers.ambient_occlusion is not None:
            lab = blend_lab_lightness(
                lab,
                layers.ambient_occlusion,
                mode=self.config.blend.ambient_occlusion_mode,
                opacity=self.config.blend.ambient_occlusion_opacity,
            )

        # Convert back to RGB
        return lab_to_rgb(lab)

    def composite_simple(
        self,
        satellite: NDArray[np.uint8],
        hillshade: NDArray[np.float32],
        shadows: NDArray[np.float32],
    ) -> NDArray[np.uint8]:
        """Simplified compositing with minimal layers.

        Useful for quick previews or when vector data isn't available.

        Args:
            satellite: RGB satellite imagery
            hillshade: Hillshade mask (0.5 = neutral)
            shadows: Combined shadow mask (1.0 = no shadow)

        Returns:
            Composited RGB image
        """
        lab = rgb_to_lab(satellite)

        # Apply hillshade
        lab = blend_lab_lightness(
            lab,
            hillshade,
            mode="soft_light",
            opacity=0.5,
        )

        # Apply shadows
        lab = blend_lab_lightness(
            lab,
            shadows,
            mode="multiply",
            opacity=0.6,
        )

        return lab_to_rgb(lab)


def composite_tile(
    satellite: NDArray[np.uint8],
    elevation: NDArray[np.float32],
    buildings: list,
    trees: list,
    bounds: tuple[float, float, float, float],
    config: Optional[PipelineConfig] = None,
    preset_name: str = "afternoon",
) -> NDArray[np.uint8]:
    """High-level function to composite a complete tile.

    This is the main entry point for tile generation, coordinating
    all layer generation and compositing.

    Args:
        satellite: RGB satellite imagery (H, W, 3)
        elevation: Elevation array (H, W) in meters
        buildings: List of building features
        trees: List of tree features
        bounds: (west, south, east, north) in WGS84
        config: Pipeline configuration
        preset_name: Name of time preset to use

    Returns:
        Final composited RGB image
    """
    from .hillshade import compute_hillshade_with_imhof
    from .shadows import create_shadow_layers
    from .sources.elevation import meters_per_pixel

    config = config or PipelineConfig()
    preset = get_preset(preset_name)
    size = satellite.shape[0]

    # Compute cell size for hillshade
    lat_center = (bounds[1] + bounds[3]) / 2
    # Use zoom 17 as reference (typical high-detail zoom)
    cell_size = meters_per_pixel(lat_center, 17) * (512 / size)

    # Generate hillshade with Imhof color shifts
    hillshade_data = compute_hillshade_with_imhof(
        elevation,
        cell_size,
        azimuth=preset.azimuth,
        altitude=preset.altitude,
        warm_strength=preset.warm_strength,
        cool_strength=preset.cool_strength,
    )

    # Generate shadow layers
    shadow_data = create_shadow_layers(
        buildings,
        trees,
        bounds,
        size,
        sun_azimuth=preset.azimuth,
        sun_altitude=preset.altitude,
        building_darkness=1.0 - preset.shadow_darkness,
        tree_darkness=1.0 - preset.shadow_darkness * 0.7,
        ao_darkness=1.0 - preset.shadow_darkness * 0.5,
    )

    # Create layer container
    layers = TileLayers(
        satellite=satellite,
        hillshade=hillshade_data["hillshade"],
        imhof_shift_a=hillshade_data["shift_a"],
        imhof_shift_b=hillshade_data["shift_b"],
        building_shadows=shadow_data["buildings"],
        tree_shadows=shadow_data["trees"],
        ambient_occlusion=shadow_data["ambient_occlusion"],
    )

    # Composite and return
    compositor = TileCompositor(config, preset)
    return compositor.composite(layers)


def preview_layers(
    layers: TileLayers,
) -> dict[str, NDArray[np.uint8]]:
    """Generate preview images of individual layers.

    Useful for debugging and visualizing each component.

    Args:
        layers: TileLayers container

    Returns:
        Dictionary of layer names to RGB preview images
    """
    def grayscale_to_rgb(arr: NDArray[np.float32]) -> NDArray[np.uint8]:
        """Convert grayscale 0-1 to RGB 0-255."""
        gray = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
        return np.stack([gray, gray, gray], axis=-1)

    previews = {
        "satellite": layers.satellite,
        "hillshade": grayscale_to_rgb(layers.hillshade),
        "building_shadows": grayscale_to_rgb(layers.building_shadows),
    }

    if layers.tree_shadows is not None:
        previews["tree_shadows"] = grayscale_to_rgb(layers.tree_shadows)

    if layers.ambient_occlusion is not None:
        previews["ambient_occlusion"] = grayscale_to_rgb(layers.ambient_occlusion)

    # Imhof color shifts as color visualization
    shift_viz = np.zeros((*layers.imhof_shift_a.shape, 3), dtype=np.uint8)
    shift_viz[..., 0] = np.clip(layers.imhof_shift_a * 5 + 128, 0, 255).astype(np.uint8)
    shift_viz[..., 1] = 128
    shift_viz[..., 2] = np.clip(layers.imhof_shift_b * 5 + 128, 0, 255).astype(np.uint8)
    previews["imhof_shifts"] = shift_viz

    return previews


# =============================================================================
# V2 Pipeline: Shadow Removal + Ray-Traced Shadows
# =============================================================================


@dataclass
class TileLayersV2:
    """Container for V2 pipeline layers (with shadow removal)."""

    clean_base: NDArray[np.uint8]      # Shadow-removed satellite RGB
    hillshade: NDArray[np.float32]     # Grayscale (H, W) values 0-1
    imhof_shift_a: NDArray[np.float32] # LAB 'a' shift
    imhof_shift_b: NDArray[np.float32] # LAB 'b' shift
    ray_traced_shadows: NDArray[np.float32]  # From ray tracer (H, W)
    ambient_occlusion: Optional[NDArray[np.float32]] = None


class TileCompositorV2:
    """V2 compositor with shadow removal and ray tracing.

    This compositor uses:
    1. AI inpainting to remove baked shadows from satellite imagery
    2. Ray tracing to generate accurate shadows from 3D scene
    3. Time-of-day color grading for atmospheric effects

    Example:
        compositor = TileCompositorV2(preset=get_preset("golden_hour"))
        result = compositor.composite(layers)
    """

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        preset: Optional[TimePreset] = None,
    ):
        """Initialize V2 compositor.

        Args:
            config: Pipeline configuration
            preset: Time preset for lighting/color parameters
        """
        self.config = config or PipelineConfig()
        self.preset = preset or get_preset("afternoon")

    def composite(self, layers: TileLayersV2) -> NDArray[np.uint8]:
        """Composite V2 layers into final image.

        Args:
            layers: TileLayersV2 with clean base and ray-traced shadows

        Returns:
            Final composited RGB image (H, W, 3)
        """
        # Convert clean base to LAB
        lab = rgb_to_lab(layers.clean_base)

        # 1. Apply hillshade (soft light on lightness)
        lab = blend_lab_lightness(
            lab,
            layers.hillshade,
            mode=self.config.blend.hillshade_mode,
            opacity=self.config.blend.hillshade_opacity,
        )

        # 2. Apply Imhof color shifts
        lab = blend_lab_color_shift(
            lab,
            shift_a=layers.imhof_shift_a,
            shift_b=layers.imhof_shift_b,
            mask=np.ones_like(layers.hillshade),
            strength=1.0,
        )

        # 3. Apply ray-traced shadows
        lab = blend_lab_lightness(
            lab,
            layers.ray_traced_shadows,
            mode="multiply",
            opacity=0.85,  # Slightly more prominent for ray-traced
        )

        # 4. Apply ambient occlusion if present
        if layers.ambient_occlusion is not None:
            lab = blend_lab_lightness(
                lab,
                layers.ambient_occlusion,
                mode="multiply",
                opacity=self.config.blend.ambient_occlusion_opacity,
            )

        # 5. Apply time-of-day color grading
        lab = self._apply_color_grade(lab)

        return lab_to_rgb(lab)

    def _apply_color_grade(self, lab: NDArray[np.float64]) -> NDArray[np.float64]:
        """Apply time-of-day color grading.

        Golden hour: warmer (increased b)
        Blue hour: cooler (decreased b, slight a shift)
        Noon: neutral
        """
        result = lab.copy()

        # Get color grade strength from preset
        # Lower sun = stronger color grade
        grade_strength = max(0, 1 - self.preset.altitude / 60) * 0.3

        if self.preset.altitude < 15:
            # Blue hour (very low sun) - cool blue tint
            result[..., 2] -= grade_strength * 10  # Shift towards blue
            result[..., 1] -= grade_strength * 3   # Slight towards green
        elif self.preset.altitude < 30:
            # Golden hour - warm orange tint
            result[..., 2] += grade_strength * 15  # Shift towards yellow
            result[..., 1] += grade_strength * 5   # Slight towards red
        # Above 30 degrees: neutral, no color grade

        # Clamp to valid LAB range
        result[..., 1] = np.clip(result[..., 1], -128, 127)
        result[..., 2] = np.clip(result[..., 2], -128, 127)

        return result


def composite_tile_v2(
    satellite: NDArray[np.uint8],
    elevation: NDArray[np.float32],
    buildings: list,
    trees: list,
    bounds: tuple[float, float, float, float],
    config: Optional[PipelineConfig] = None,
    preset_name: str = "afternoon",
    remove_shadows: bool = True,
    shadow_removal_method: str = "lama",
    ray_trace_samples: int = 1,
    progress_callback: Optional[callable] = None,
    use_blender: bool = False,
    blender_samples: int = 16,
) -> NDArray[np.uint8]:
    """High-level V2 function with shadow removal and ray tracing.

    This is the main entry point for the V2 tile pipeline that produces
    beautiful tiles with consistent, controllable shadows.

    Pipeline steps:
    1. Remove baked shadows from satellite imagery (AI inpainting)
    2. Build 3D scene from buildings + trees + terrain
    3. Ray trace new shadows from configured sun position
       - Option A (default): Trimesh CPU ray tracing
       - Option B (use_blender=True): Blender Cycles GPU ray tracing
    4. Composite with hillshade and color grading

    Args:
        satellite: RGB satellite imagery (H, W, 3)
        elevation: Elevation array (H, W) in meters
        buildings: List of building features
        trees: List of tree features
        bounds: (west, south, east, north) in WGS84
        config: Pipeline configuration
        preset_name: Time preset ("morning", "afternoon", "evening", "golden_hour")
        remove_shadows: Whether to remove baked shadows first
        shadow_removal_method: "lama", "color_transfer", or "replicate"
        ray_trace_samples: Samples per pixel for trimesh (1=hard, 4+=soft shadows)
        progress_callback: Optional callback(stage, progress) for updates
        use_blender: Use Blender Cycles for GPU-accelerated shadow rendering
        blender_samples: Render samples when using Blender (16-64 typical)

    Returns:
        Final composited RGB image with ray-traced shadows

    Example:
        # Using trimesh (CPU)
        result = composite_tile_v2(
            satellite=satellite_image,
            elevation=elevation_data,
            buildings=building_features,
            trees=tree_features,
            bounds=(8.53, 47.37, 8.55, 47.39),
            preset_name="golden_hour",
            remove_shadows=True,
            ray_trace_samples=4,  # Soft shadows
        )

        # Using Blender (GPU - faster for complex scenes)
        result = composite_tile_v2(
            satellite=satellite_image,
            elevation=elevation_data,
            buildings=building_features,
            trees=tree_features,
            bounds=(8.53, 47.37, 8.55, 47.39),
            preset_name="golden_hour",
            use_blender=True,
            blender_samples=32,
        )
    """
    from .hillshade import compute_hillshade_with_imhof
    from .sources.elevation import meters_per_pixel
    from .shadow_remover import ShadowRemover, RemovalMethod
    from .scene_builder import SceneBuilder
    from .raytracer import TileRaytracer, SunPosition, RayTracerConfig

    config = config or PipelineConfig()
    preset = get_preset(preset_name)
    size = satellite.shape[0]

    def report_progress(stage: str, progress: float):
        if progress_callback:
            progress_callback(stage, progress)

    # Step 1: Remove baked shadows (optional but recommended)
    report_progress("shadow_removal", 0.0)
    if remove_shadows:
        try:
            remover = ShadowRemover(
                method=RemovalMethod(shadow_removal_method),
                shadow_threshold=0.4,
            )
            result = remover.remove(satellite)
            clean_base = result.image
            report_progress("shadow_removal", 1.0)
        except Exception as e:
            print(f"Warning: Shadow removal failed ({e}), using original")
            clean_base = satellite
    else:
        clean_base = satellite
    report_progress("shadow_removal", 1.0)

    # Step 2: Build 3D scene (only needed for trimesh raytracer)
    scene_mesh = None
    if not use_blender:
        report_progress("scene_building", 0.0)
        builder = SceneBuilder(bounds, size)

        # Add terrain
        if elevation is not None and elevation.size > 0:
            builder.add_terrain(elevation, z_scale=1.0)
        else:
            builder.add_ground_plane()

        # Add buildings
        if buildings:
            builder.add_buildings(buildings)

        # Add trees
        if trees:
            builder.add_trees(trees)

        scene_mesh = builder.build()
        report_progress("scene_building", 1.0)
    else:
        # Blender builds its own scene internally
        report_progress("scene_building", 0.0)
        report_progress("scene_building", 1.0)

    # Step 3: Ray trace shadows
    report_progress("ray_tracing", 0.0)

    if use_blender:
        # Use Blender Cycles for GPU-accelerated shadow rendering
        from .blender_shadows import (
            BlenderShadowRenderer,
            BlenderConfig,
            SunPosition as BlenderSunPosition,
        )

        blender_config = BlenderConfig(
            image_size=size,
            samples=blender_samples,
            shadow_darkness=1.0 - preset.shadow_darkness,
            use_gpu=True,
        )
        blender_renderer = BlenderShadowRenderer(config=blender_config)
        blender_sun = BlenderSunPosition(
            azimuth=preset.azimuth,
            altitude=preset.altitude,
        )

        def blender_progress(stage, p):
            report_progress("ray_tracing", p * 0.9)  # Reserve 10% for loading

        ray_traced_shadows = blender_renderer.render(
            buildings=buildings,
            trees=trees,
            elevation=elevation,
            bounds=bounds,
            sun=blender_sun,
            progress_callback=blender_progress,
        )
    else:
        # Use trimesh CPU ray tracing (original method)
        rt_config = RayTracerConfig(
            image_size=size,
            samples_per_pixel=ray_trace_samples,
            shadow_darkness=1.0 - preset.shadow_darkness,
        )
        raytracer = TileRaytracer(scene_mesh, bounds, rt_config)
        sun = SunPosition(azimuth=preset.azimuth, altitude=preset.altitude)

        def rt_progress(p):
            report_progress("ray_tracing", p)

        ray_traced_shadows = raytracer.render(
            sun,
            elevation_grid=elevation,
            progress_callback=rt_progress,
        )

    report_progress("ray_tracing", 1.0)

    # Step 4: Generate hillshade
    report_progress("hillshade", 0.0)
    lat_center = (bounds[1] + bounds[3]) / 2
    cell_size = meters_per_pixel(lat_center, 17) * (512 / size)

    hillshade_data = compute_hillshade_with_imhof(
        elevation,
        cell_size,
        azimuth=preset.azimuth,
        altitude=preset.altitude,
        warm_strength=preset.warm_strength,
        cool_strength=preset.cool_strength,
    )
    report_progress("hillshade", 1.0)

    # Step 5: Composite
    report_progress("compositing", 0.0)
    layers = TileLayersV2(
        clean_base=clean_base,
        hillshade=hillshade_data["hillshade"],
        imhof_shift_a=hillshade_data["shift_a"],
        imhof_shift_b=hillshade_data["shift_b"],
        ray_traced_shadows=ray_traced_shadows,
        ambient_occlusion=None,  # Could add from raytracer.render_multi_bounce
    )

    compositor = TileCompositorV2(config, preset)
    result = compositor.composite(layers)
    report_progress("compositing", 1.0)

    return result


def preview_v2_pipeline(
    satellite: NDArray[np.uint8],
    elevation: NDArray[np.float32],
    buildings: list,
    trees: list,
    bounds: tuple[float, float, float, float],
    preset_name: str = "afternoon",
) -> dict[str, NDArray[np.uint8]]:
    """Generate preview images of each V2 pipeline stage.

    Useful for debugging and comparing pipeline stages.

    Args:
        satellite: Input satellite image
        elevation: Elevation data
        buildings: Building features
        trees: Tree features
        bounds: Tile bounds
        preset_name: Time preset name

    Returns:
        Dictionary of stage names to RGB preview images
    """
    from .shadow_remover import ShadowRemover, RemovalMethod
    from .scene_builder import SceneBuilder
    from .raytracer import TileRaytracer, SunPosition, RayTracerConfig
    from .hillshade import compute_hillshade_with_imhof
    from .sources.elevation import meters_per_pixel

    size = satellite.shape[0]
    preset = get_preset(preset_name)
    previews = {}

    def to_rgb(arr: NDArray[np.float32]) -> NDArray[np.uint8]:
        """Convert grayscale 0-1 to RGB."""
        gray = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
        return np.stack([gray, gray, gray], axis=-1)

    # 1. Original
    previews["01_original"] = satellite

    # 2. Shadow mask
    from .shadow_analyzer import create_shadow_probability_map
    shadow_prob = create_shadow_probability_map(satellite)
    previews["02_shadow_mask"] = to_rgb(shadow_prob)

    # 3. Shadow removed
    try:
        remover = ShadowRemover(method=RemovalMethod.COLOR_TRANSFER)
        result = remover.remove(satellite)
        previews["03_shadow_removed"] = result.image
    except Exception:
        previews["03_shadow_removed"] = satellite

    # 4. Ray-traced shadows
    builder = SceneBuilder(bounds, size)
    if elevation is not None:
        builder.add_terrain(elevation)
    else:
        builder.add_ground_plane()
    if buildings:
        builder.add_buildings(buildings)
    if trees:
        builder.add_trees(trees)
    mesh = builder.build()

    rt_config = RayTracerConfig(image_size=size, samples_per_pixel=1)
    raytracer = TileRaytracer(mesh, bounds, rt_config)
    sun = SunPosition(azimuth=preset.azimuth, altitude=preset.altitude)
    rt_shadows = raytracer.render(sun, elevation)
    previews["04_ray_traced_shadows"] = to_rgb(rt_shadows)

    # 5. Hillshade
    if elevation is not None:
        lat_center = (bounds[1] + bounds[3]) / 2
        cell_size = meters_per_pixel(lat_center, 17) * (512 / size)
        hs_data = compute_hillshade_with_imhof(
            elevation, cell_size,
            azimuth=preset.azimuth,
            altitude=preset.altitude,
        )
        previews["05_hillshade"] = to_rgb(hs_data["hillshade"])

    # 6. Final composite
    try:
        final = composite_tile_v2(
            satellite, elevation, buildings, trees, bounds,
            preset_name=preset_name,
            remove_shadows=True,
            shadow_removal_method="color_transfer",
            ray_trace_samples=1,
        )
        previews["06_final_composite"] = final
    except Exception as e:
        print(f"Final composite failed: {e}")

    return previews
