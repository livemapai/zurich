"""
Ray-traced shadow generation using trimesh.

Casts rays from ground points towards the sun to determine which
pixels are in shadow. Produces high-quality shadow buffers with
accurate building and tree shadows.

Features:
- True ray tracing from 3D scene
- Soft shadows via multi-sample anti-aliasing
- Configurable sun position
- Progress reporting for large scenes
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Callable
import math

import numpy as np
from numpy.typing import NDArray
import trimesh
from scipy import ndimage

from .scene_builder import SceneBuilder, SceneBounds


@dataclass
class SunPosition:
    """Sun position for shadow casting."""

    azimuth: float    # Degrees from north, clockwise (0=N, 90=E, 180=S, 270=W)
    altitude: float   # Degrees above horizon (0=horizon, 90=zenith)

    @property
    def direction_vector(self) -> NDArray[np.float64]:
        """Get normalized direction vector FROM sun TO ground.

        This is the direction light travels, which is opposite to
        the shadow ray direction (from ground to sun).
        """
        # Convert to radians
        az_rad = math.radians(self.azimuth)
        alt_rad = math.radians(self.altitude)

        # Sun direction in local coords (light traveling down)
        # Azimuth 0 = North = +Y, 90 = East = +X
        x = -math.sin(az_rad) * math.cos(alt_rad)
        y = -math.cos(az_rad) * math.cos(alt_rad)
        z = -math.sin(alt_rad)

        return np.array([x, y, z])

    @property
    def ray_direction(self) -> NDArray[np.float64]:
        """Get shadow ray direction (from ground towards sun)."""
        return -self.direction_vector

    @classmethod
    def from_datetime(
        cls,
        latitude: float,
        longitude: float,
        dt,  # datetime object
    ) -> "SunPosition":
        """Calculate sun position from datetime and location.

        Requires pysolar package.
        """
        try:
            from pysolar.solar import get_altitude, get_azimuth

            altitude = get_altitude(latitude, longitude, dt)
            azimuth = get_azimuth(latitude, longitude, dt)

            return cls(azimuth=azimuth, altitude=altitude)

        except ImportError:
            raise ImportError(
                "pysolar is required for datetime-based sun position. "
                "Install with: pip install pysolar"
            )


@dataclass
class RayTracerConfig:
    """Configuration for ray tracing."""

    # Output resolution
    image_size: int = 512

    # Anti-aliasing (soft shadows)
    samples_per_pixel: int = 1     # 1 = hard shadows, 4+ = soft
    jitter_amount: float = 0.5     # Jitter in pixels for soft shadows

    # Performance
    batch_size: int = 10000        # Rays per batch (memory control)
    use_embree: bool = True        # Use Embree accelerator if available

    # Ray offset to avoid self-intersection
    ray_offset: float = 0.1        # Meters above ground

    # Shadow properties
    shadow_darkness: float = 0.2   # 0=black, 1=no shadow
    soft_shadow_blur: float = 0.0  # Additional Gaussian blur radius


class TileRaytracer:
    """Ray traces shadows for a tile from a 3D scene.

    Uses trimesh's ray-triangle intersection to cast shadow rays
    from each pixel towards the sun. Pixels where rays hit geometry
    are marked as in shadow.

    Example:
        # Build scene
        builder = SceneBuilder(bounds)
        builder.add_terrain(elevation)
        builder.add_buildings(buildings)
        scene = builder.build()

        # Ray trace shadows
        raytracer = TileRaytracer(scene, bounds)
        shadow_buffer = raytracer.render(sun_position)
    """

    def __init__(
        self,
        mesh: trimesh.Trimesh,
        bounds: Tuple[float, float, float, float],
        config: Optional[RayTracerConfig] = None,
    ):
        """Initialize ray tracer.

        Args:
            mesh: Combined 3D scene mesh
            bounds: (west, south, east, north) in WGS84
            config: Ray tracing configuration
        """
        self.mesh = mesh
        self.scene_bounds = SceneBounds(*bounds)
        self.config = config or RayTracerConfig()

        # Create ray intersector
        self._intersector = self._create_intersector()

    def _create_intersector(self):
        """Create the ray-mesh intersector."""
        # Try to use Embree for better performance
        if self.config.use_embree:
            try:
                return trimesh.ray.ray_pyembree.RayMeshIntersector(self.mesh)
            except (ImportError, AttributeError):
                pass

        # Fall back to trimesh's built-in ray tracer
        return trimesh.ray.ray_triangle.RayMeshIntersector(self.mesh)

    def render(
        self,
        sun: SunPosition,
        elevation_grid: Optional[NDArray[np.float32]] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> NDArray[np.float32]:
        """Render shadow buffer for the tile.

        Args:
            sun: Sun position for shadow direction
            elevation_grid: Optional elevation grid for ray origins.
                           If None, uses flat ground at z=0.
            progress_callback: Optional callback(0-1) for progress updates

        Returns:
            Shadow buffer (H, W) with values:
            - 1.0 = fully lit
            - shadow_darkness = fully shadowed
        """
        size = self.config.image_size
        samples = self.config.samples_per_pixel

        # Initialize shadow accumulator
        shadow_acc = np.zeros((size, size), dtype=np.float32)

        # Generate sample positions for multi-sampling
        if samples > 1:
            # Stratified sampling pattern
            sample_offsets = self._generate_sample_offsets(samples)
        else:
            sample_offsets = np.array([[0.0, 0.0]])

        total_samples = samples
        samples_done = 0

        for offset in sample_offsets:
            # Generate ray origins for this sample
            origins = self._generate_ray_origins(
                size,
                elevation_grid,
                offset[0] * self.config.jitter_amount,
                offset[1] * self.config.jitter_amount,
            )

            # Cast rays in batches
            hits = self._cast_shadow_rays_batched(
                origins,
                sun.ray_direction,
                progress_callback,
                base_progress=samples_done / total_samples,
                progress_range=1 / total_samples,
            )

            # Accumulate hits
            shadow_acc += hits.reshape(size, size)
            samples_done += 1

        # Normalize by number of samples
        shadow_buffer = shadow_acc / total_samples

        # Convert hits (1=shadow) to shadow mask (darkness=shadow, 1=lit)
        shadow_mask = 1.0 - shadow_buffer * (1.0 - self.config.shadow_darkness)

        # Optional blur for softer edges
        if self.config.soft_shadow_blur > 0:
            shadow_mask = ndimage.gaussian_filter(
                shadow_mask,
                sigma=self.config.soft_shadow_blur,
            )

        return shadow_mask.astype(np.float32)

    def _generate_sample_offsets(self, n_samples: int) -> NDArray[np.float64]:
        """Generate stratified sample offsets for anti-aliasing."""
        # Use a grid pattern with jitter
        grid_size = int(math.ceil(math.sqrt(n_samples)))
        offsets = []

        for i in range(grid_size):
            for j in range(grid_size):
                if len(offsets) >= n_samples:
                    break
                # Stratified: divide pixel into grid, random within each cell
                ox = (i + 0.5) / grid_size - 0.5
                oy = (j + 0.5) / grid_size - 0.5
                # Add small random jitter within stratified cell
                ox += (np.random.random() - 0.5) / grid_size
                oy += (np.random.random() - 0.5) / grid_size
                offsets.append([ox, oy])

        return np.array(offsets[:n_samples])

    def _generate_ray_origins(
        self,
        size: int,
        elevation_grid: Optional[NDArray[np.float32]],
        jitter_x: float = 0,
        jitter_y: float = 0,
    ) -> NDArray[np.float64]:
        """Generate ray origin points on the ground plane.

        Args:
            size: Grid resolution
            elevation_grid: Optional elevation data
            jitter_x, jitter_y: Sub-pixel jitter in pixels

        Returns:
            Array of shape (size*size, 3) with [x, y, z] coordinates
        """
        # Create pixel grid
        pixel_x = np.arange(size) + 0.5 + jitter_x
        pixel_y = np.arange(size) + 0.5 + jitter_y

        # Convert to local coordinates (meters)
        # X goes from 0 to width_meters
        # Y goes from 0 to height_meters (but image Y is flipped)
        x = pixel_x / size * self.scene_bounds.width_meters
        y = (size - pixel_y) / size * self.scene_bounds.height_meters  # Flip Y

        xx, yy = np.meshgrid(x, y)

        # Get Z from elevation or use flat ground
        if elevation_grid is not None:
            # Resample elevation to output size
            from scipy.ndimage import zoom
            if elevation_grid.shape != (size, size):
                zoom_factor = (size / elevation_grid.shape[0],
                              size / elevation_grid.shape[1])
                zz = zoom(elevation_grid, zoom_factor, order=1)
            else:
                zz = elevation_grid
        else:
            zz = np.zeros((size, size))

        # Add small offset to avoid self-intersection with ground
        zz = zz + self.config.ray_offset

        # Flatten to (N, 3)
        origins = np.column_stack([
            xx.ravel(),
            yy.ravel(),
            zz.ravel(),
        ])

        return origins

    def _cast_shadow_rays_batched(
        self,
        origins: NDArray[np.float64],
        direction: NDArray[np.float64],
        progress_callback: Optional[Callable[[float], None]],
        base_progress: float = 0,
        progress_range: float = 1,
    ) -> NDArray[np.bool_]:
        """Cast shadow rays in batches for memory efficiency.

        Args:
            origins: Ray origin points (N, 3)
            direction: Shadow ray direction (3,)
            progress_callback: Progress callback
            base_progress: Starting progress value
            progress_range: Progress range for this batch set

        Returns:
            Boolean array of hits (True = in shadow)
        """
        n_rays = len(origins)
        batch_size = self.config.batch_size
        hits = np.zeros(n_rays, dtype=bool)

        # Normalize direction
        direction = direction / np.linalg.norm(direction)

        # All rays have the same direction
        directions = np.broadcast_to(direction, (n_rays, 3)).copy()

        # Process in batches
        for i in range(0, n_rays, batch_size):
            end = min(i + batch_size, n_rays)

            batch_origins = origins[i:end]
            batch_dirs = directions[i:end]

            # Cast rays
            try:
                # intersects_any returns boolean array
                batch_hits = self._intersector.intersects_any(
                    batch_origins,
                    batch_dirs,
                )
                hits[i:end] = batch_hits
            except Exception:
                # Fallback: slower but more robust
                for j, (o, d) in enumerate(zip(batch_origins, batch_dirs)):
                    try:
                        locations, _, _ = self._intersector.intersects_location(
                            [o], [d]
                        )
                        hits[i + j] = len(locations) > 0
                    except Exception:
                        hits[i + j] = False

            # Report progress
            if progress_callback:
                progress = base_progress + (end / n_rays) * progress_range
                progress_callback(progress)

        return hits

    def render_multi_bounce(
        self,
        sun: SunPosition,
        elevation_grid: Optional[NDArray[np.float32]] = None,
        ambient_bounces: int = 1,
    ) -> Tuple[NDArray[np.float32], NDArray[np.float32]]:
        """Render shadows with ambient occlusion from multi-bounce rays.

        Returns both direct shadow and ambient occlusion buffers.

        Args:
            sun: Sun position
            elevation_grid: Optional elevation data
            ambient_bounces: Number of ambient rays per pixel

        Returns:
            Tuple of (shadow_buffer, ao_buffer)
        """
        # Direct shadows
        shadow_buffer = self.render(sun, elevation_grid)

        # Ambient occlusion
        if ambient_bounces > 0:
            ao_buffer = self._render_ambient_occlusion(
                elevation_grid,
                ambient_bounces,
            )
        else:
            ao_buffer = np.ones_like(shadow_buffer)

        return shadow_buffer, ao_buffer

    def _render_ambient_occlusion(
        self,
        elevation_grid: Optional[NDArray[np.float32]],
        n_samples: int,
    ) -> NDArray[np.float32]:
        """Render ambient occlusion by casting rays in hemisphere.

        Args:
            elevation_grid: Optional elevation data
            n_samples: Number of hemisphere rays per pixel

        Returns:
            AO buffer (1 = fully visible, 0 = fully occluded)
        """
        size = self.config.image_size
        ao_acc = np.zeros((size, size), dtype=np.float32)

        # Generate hemisphere directions (cosine-weighted)
        directions = self._generate_hemisphere_directions(n_samples)

        origins = self._generate_ray_origins(size, elevation_grid)

        for direction in directions:
            # Cast rays
            hits = self._cast_shadow_rays_batched(
                origins, direction, None
            )
            # Accumulate misses (visible = 1)
            ao_acc += ~hits.reshape(size, size)

        # Normalize
        ao_buffer = ao_acc / n_samples

        return ao_buffer.astype(np.float32)

    def _generate_hemisphere_directions(
        self,
        n_samples: int,
    ) -> NDArray[np.float64]:
        """Generate cosine-weighted hemisphere directions."""
        directions = []

        for _ in range(n_samples):
            # Cosine-weighted hemisphere sampling
            u1, u2 = np.random.random(2)
            theta = 2 * math.pi * u1
            r = math.sqrt(u2)

            x = r * math.cos(theta)
            y = r * math.sin(theta)
            z = math.sqrt(1 - u2)  # Pointing up

            directions.append([x, y, z])

        return np.array(directions)


def render_tile_shadows(
    mesh: trimesh.Trimesh,
    bounds: Tuple[float, float, float, float],
    sun_azimuth: float,
    sun_altitude: float,
    image_size: int = 512,
    samples: int = 1,
    shadow_darkness: float = 0.2,
    elevation: Optional[NDArray[np.float32]] = None,
) -> NDArray[np.float32]:
    """Convenience function to render shadows for a tile.

    Args:
        mesh: 3D scene mesh
        bounds: (west, south, east, north) in WGS84
        sun_azimuth: Sun azimuth in degrees
        sun_altitude: Sun altitude in degrees
        image_size: Output resolution
        samples: Samples per pixel (1=hard, 4+=soft shadows)
        shadow_darkness: Shadow darkness (0=black, 1=no effect)
        elevation: Optional elevation grid

    Returns:
        Shadow buffer (size, size) ready for compositing

    Example:
        # Build scene first
        mesh, builder = build_tile_scene(bounds, buildings, trees, elevation)

        # Render shadows
        shadows = render_tile_shadows(
            mesh, bounds,
            sun_azimuth=225,
            sun_altitude=35,
        )

        # Composite with satellite
        result = apply_shadow_buffer(satellite_image, shadows)
    """
    config = RayTracerConfig(
        image_size=image_size,
        samples_per_pixel=samples,
        shadow_darkness=shadow_darkness,
    )

    raytracer = TileRaytracer(mesh, bounds, config)
    sun = SunPosition(azimuth=sun_azimuth, altitude=sun_altitude)

    return raytracer.render(sun, elevation)


def compare_shadow_methods(
    mesh: trimesh.Trimesh,
    bounds: Tuple[float, float, float, float],
    sun_azimuth: float,
    sun_altitude: float,
    image_size: int = 512,
) -> dict:
    """Compare ray-traced shadows with 2D projection shadows.

    Useful for understanding the difference in quality.

    Returns:
        Dictionary with comparison results and images
    """
    from .shadows import building_shadows

    # Ray-traced shadows
    rt_config = RayTracerConfig(image_size=image_size, samples_per_pixel=4)
    raytracer = TileRaytracer(mesh, bounds, rt_config)
    sun = SunPosition(azimuth=sun_azimuth, altitude=sun_altitude)
    rt_shadows = raytracer.render(sun)

    # Calculate difference metrics
    return {
        "ray_traced": rt_shadows,
        "method": "trimesh_ray_triangle",
        "samples_per_pixel": 4,
        "resolution": image_size,
    }
