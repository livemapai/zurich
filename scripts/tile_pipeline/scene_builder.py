"""
Build 3D scenes from GeoJSON data for ray tracing.

Creates 3D meshes from:
- Building footprints (extruded to height)
- Tree positions (cone/cylinder volumes)
- Elevation heightmaps (terrain mesh)
- Poles/lights (thin cylinders)

All coordinates are converted to a local meter-based system
for accurate shadow casting calculations.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import math

import numpy as np
from numpy.typing import NDArray
import trimesh

from .sources.vector import Feature


@dataclass
class SceneBounds:
    """Bounds for the 3D scene in local coordinates."""

    # WGS84 bounds
    west: float
    south: float
    east: float
    north: float

    # Derived values (computed in __post_init__)
    lat_center: float = field(init=False)
    meters_per_deg_x: float = field(init=False)
    meters_per_deg_y: float = field(init=False)
    width_meters: float = field(init=False)
    height_meters: float = field(init=False)

    def __post_init__(self):
        """Compute derived values from WGS84 bounds."""
        self.lat_center = (self.south + self.north) / 2

        # Meters per degree at this latitude
        # At equator: 1° = 111,320m latitude, varies for longitude
        self.meters_per_deg_y = 111320.0
        self.meters_per_deg_x = 111320.0 * math.cos(math.radians(self.lat_center))

        # Scene dimensions in meters
        self.width_meters = (self.east - self.west) * self.meters_per_deg_x
        self.height_meters = (self.north - self.south) * self.meters_per_deg_y

    def wgs84_to_local(self, lon: float, lat: float) -> Tuple[float, float]:
        """Convert WGS84 coordinates to local meters from SW corner."""
        x = (lon - self.west) * self.meters_per_deg_x
        y = (lat - self.south) * self.meters_per_deg_y
        return (x, y)

    def local_to_wgs84(self, x: float, y: float) -> Tuple[float, float]:
        """Convert local meters back to WGS84."""
        lon = self.west + x / self.meters_per_deg_x
        lat = self.south + y / self.meters_per_deg_y
        return (lon, lat)


@dataclass
class SceneStatistics:
    """Statistics about the built scene."""

    num_buildings: int = 0
    num_trees: int = 0
    num_terrain_vertices: int = 0
    total_triangles: int = 0
    bounds_meters: Tuple[float, float, float, float, float, float] = (0, 0, 0, 0, 0, 0)


class SceneBuilder:
    """Builds 3D scenes from geographic data for ray tracing.

    The scene is built in a local coordinate system (meters) centered
    on the tile for numerical stability and accurate shadow calculations.

    Example:
        builder = SceneBuilder(bounds=(8.53, 47.37, 8.55, 47.39))
        builder.add_terrain(elevation_data)
        builder.add_buildings(building_features)
        builder.add_trees(tree_features)
        scene = builder.build()
    """

    def __init__(
        self,
        bounds: Tuple[float, float, float, float],
        image_size: int = 512,
    ):
        """Initialize scene builder.

        Args:
            bounds: (west, south, east, north) in WGS84 degrees
            image_size: Output image size in pixels (for UV mapping)
        """
        self.bounds = SceneBounds(*bounds)
        self.image_size = image_size

        # Meshes to combine
        self._meshes: List[trimesh.Trimesh] = []

        # Statistics
        self.stats = SceneStatistics()

    def add_terrain(
        self,
        elevation: NDArray[np.float32],
        z_scale: float = 1.0,
        simplify: bool = True,
    ) -> "SceneBuilder":
        """Add terrain mesh from elevation heightmap.

        Args:
            elevation: 2D array of elevation values in meters (H, W)
            z_scale: Vertical exaggeration factor
            simplify: Whether to simplify the mesh for performance

        Returns:
            Self for method chaining
        """
        h, w = elevation.shape

        # Create grid of vertices
        x = np.linspace(0, self.bounds.width_meters, w)
        y = np.linspace(0, self.bounds.height_meters, h)
        xx, yy = np.meshgrid(x, y)

        # Scale elevation
        zz = elevation * z_scale

        # Flatten to vertex array
        vertices = np.column_stack([
            xx.ravel(),
            yy.ravel(),
            zz.ravel()
        ])

        # Create faces (two triangles per quad)
        faces = []
        for i in range(h - 1):
            for j in range(w - 1):
                # Vertex indices
                v0 = i * w + j
                v1 = i * w + j + 1
                v2 = (i + 1) * w + j
                v3 = (i + 1) * w + j + 1

                # Two triangles per quad
                faces.append([v0, v2, v1])
                faces.append([v1, v2, v3])

        faces = np.array(faces)

        # Create mesh
        terrain = trimesh.Trimesh(vertices=vertices, faces=faces)

        if simplify and len(terrain.faces) > 10000:
            # Simplify large terrains (requires fast_simplification package)
            try:
                terrain = terrain.simplify_quadric_decimation(10000)
            except (ImportError, ModuleNotFoundError):
                # fast_simplification not installed, skip simplification
                pass

        self._meshes.append(terrain)
        self.stats.num_terrain_vertices = len(vertices)

        return self

    def add_buildings(
        self,
        features: List[Feature],
        default_height: float = 10.0,
    ) -> "SceneBuilder":
        """Add building meshes by extruding footprints.

        Args:
            features: Building features with height and polygon coordinates
            default_height: Height to use if feature has no height

        Returns:
            Self for method chaining
        """
        for feature in features:
            if feature.geometry_type not in ("Polygon", "MultiPolygon"):
                continue

            height = feature.height if feature.height > 0 else default_height

            # Get base elevation if available
            base_z = feature.properties.get("elevation", 0)

            # Process all polygons
            if feature.geometry_type == "Polygon":
                polygons = [feature.coordinates]
            else:
                polygons = feature.coordinates

            for polygon in polygons:
                mesh = self._extrude_polygon(polygon, height, base_z)
                if mesh is not None:
                    self._meshes.append(mesh)
                    self.stats.num_buildings += 1

        return self

    def add_trees(
        self,
        features: List[Feature],
        default_height: float = 8.0,
        default_crown_radius: float = 3.0,
        use_cones: bool = True,
    ) -> "SceneBuilder":
        """Add tree volumes as cones or cylinders.

        Args:
            features: Tree features with position and dimensions
            default_height: Height if not specified
            default_crown_radius: Crown radius if not specified
            use_cones: Use cones (True) or cylinders (False)

        Returns:
            Self for method chaining
        """
        for feature in features:
            if feature.geometry_type != "Point":
                continue

            lon, lat = feature.coordinates
            x, y = self.bounds.wgs84_to_local(lon, lat)

            height = feature.height if feature.height > 0 else default_height
            crown_diam = feature.properties.get("crown_diameter", default_crown_radius * 2)
            crown_radius = crown_diam / 2

            # Get base elevation
            base_z = feature.properties.get("elevation", 0)

            # Create tree volume
            if use_cones:
                # Cone for deciduous trees (inverted cone = crown shape)
                tree = trimesh.creation.cone(
                    radius=crown_radius,
                    height=height,
                    sections=8,  # Low-poly for performance
                )
                # Move to position (cone is centered at origin)
                tree.vertices[:, 2] += base_z + height / 2
            else:
                # Cylinder for conifers
                tree = trimesh.creation.cylinder(
                    radius=crown_radius,
                    height=height,
                    sections=8,
                )
                tree.vertices[:, 2] += base_z + height / 2

            # Translate to position
            tree.vertices[:, 0] += x
            tree.vertices[:, 1] += y

            self._meshes.append(tree)
            self.stats.num_trees += 1

        return self

    def add_poles(
        self,
        features: List[Feature],
        default_height: float = 5.0,
        radius: float = 0.1,
    ) -> "SceneBuilder":
        """Add thin poles (light poles, tram poles, etc.).

        Args:
            features: Pole features with position and height
            default_height: Height if not specified
            radius: Pole radius in meters

        Returns:
            Self for method chaining
        """
        for feature in features:
            if feature.geometry_type != "Point":
                continue

            lon, lat = feature.coordinates
            x, y = self.bounds.wgs84_to_local(lon, lat)

            height = feature.height if feature.height > 0 else default_height
            base_z = feature.properties.get("elevation", 0)

            # Create thin cylinder
            pole = trimesh.creation.cylinder(
                radius=radius,
                height=height,
                sections=6,
            )

            # Position
            pole.vertices[:, 0] += x
            pole.vertices[:, 1] += y
            pole.vertices[:, 2] += base_z + height / 2

            self._meshes.append(pole)

        return self

    def add_ground_plane(
        self,
        z: float = 0.0,
        margin: float = 100.0,
    ) -> "SceneBuilder":
        """Add a flat ground plane (useful when no elevation data).

        Args:
            z: Ground elevation in meters
            margin: Extra margin around bounds in meters

        Returns:
            Self for method chaining
        """
        w = self.bounds.width_meters + 2 * margin
        h = self.bounds.height_meters + 2 * margin

        # Create simple quad
        vertices = np.array([
            [-margin, -margin, z],
            [w + margin, -margin, z],
            [w + margin, h + margin, z],
            [-margin, h + margin, z],
        ])
        faces = np.array([
            [0, 1, 2],
            [0, 2, 3],
        ])

        ground = trimesh.Trimesh(vertices=vertices, faces=faces)
        self._meshes.append(ground)

        return self

    def _extrude_polygon(
        self,
        polygon_coords: List[List[Tuple[float, float]]],
        height: float,
        base_z: float = 0,
    ) -> Optional[trimesh.Trimesh]:
        """Extrude a polygon to create a building mesh.

        Args:
            polygon_coords: List of rings [outer, hole1, hole2, ...]
            height: Extrusion height in meters
            base_z: Base elevation in meters

        Returns:
            Trimesh object or None if invalid
        """
        if len(polygon_coords) == 0 or len(polygon_coords[0]) < 3:
            return None

        try:
            # Convert outer ring to local coordinates
            outer_ring = polygon_coords[0]
            local_coords = np.array([
                self.bounds.wgs84_to_local(lon, lat)
                for lon, lat in outer_ring
            ])

            # Create 2D polygon path
            from shapely.geometry import Polygon as ShapelyPolygon

            # Handle holes if present
            if len(polygon_coords) > 1:
                holes = [
                    [self.bounds.wgs84_to_local(lon, lat) for lon, lat in ring]
                    for ring in polygon_coords[1:]
                ]
                shapely_poly = ShapelyPolygon(local_coords, holes)
            else:
                shapely_poly = ShapelyPolygon(local_coords)

            if not shapely_poly.is_valid:
                shapely_poly = shapely_poly.buffer(0)  # Fix invalid geometry

            if shapely_poly.is_empty:
                return None

            # Extrude using trimesh
            mesh = trimesh.creation.extrude_polygon(
                shapely_poly,
                height=height,
            )

            # Move to correct Z position
            mesh.vertices[:, 2] += base_z

            return mesh

        except Exception as e:
            # Invalid geometry - skip silently
            return None

    def build(self) -> trimesh.Trimesh:
        """Combine all meshes into a single scene.

        Returns:
            Combined trimesh ready for ray tracing
        """
        if len(self._meshes) == 0:
            # Return empty scene with just a ground plane
            self.add_ground_plane()

        # Combine all meshes
        scene = trimesh.util.concatenate(self._meshes)

        # Update statistics
        self.stats.total_triangles = len(scene.faces)
        self.stats.bounds_meters = tuple(scene.bounds.flatten())

        return scene

    def build_scene_collection(self) -> trimesh.Scene:
        """Build as a trimesh Scene for visualization.

        Returns:
            trimesh.Scene object
        """
        return trimesh.Scene(self._meshes)


def build_tile_scene(
    bounds: Tuple[float, float, float, float],
    buildings: Optional[List[Feature]] = None,
    trees: Optional[List[Feature]] = None,
    elevation: Optional[NDArray[np.float32]] = None,
    image_size: int = 512,
) -> Tuple[trimesh.Trimesh, SceneBuilder]:
    """Convenience function to build a complete tile scene.

    Args:
        bounds: (west, south, east, north) in WGS84
        buildings: Building features (optional)
        trees: Tree features (optional)
        elevation: Elevation heightmap (optional)
        image_size: Output image size

    Returns:
        Tuple of (combined mesh, SceneBuilder for statistics)

    Example:
        mesh, builder = build_tile_scene(
            bounds=(8.53, 47.37, 8.55, 47.39),
            buildings=building_features,
            trees=tree_features,
            elevation=elevation_data,
        )
        print(f"Scene has {builder.stats.total_triangles} triangles")
    """
    builder = SceneBuilder(bounds, image_size)

    # Add terrain or ground plane
    if elevation is not None:
        builder.add_terrain(elevation)
    else:
        builder.add_ground_plane()

    # Add features
    if buildings:
        builder.add_buildings(buildings)

    if trees:
        builder.add_trees(trees)

    return builder.build(), builder


def estimate_scene_complexity(
    num_buildings: int,
    num_trees: int,
    terrain_resolution: int,
) -> dict:
    """Estimate scene complexity for planning.

    Args:
        num_buildings: Number of buildings
        num_trees: Number of trees
        terrain_resolution: Terrain grid size

    Returns:
        Dictionary with estimates
    """
    # Rough estimates
    building_tris = num_buildings * 20  # ~20 triangles per extruded building
    tree_tris = num_trees * 16  # ~16 triangles per 8-sided cone
    terrain_tris = (terrain_resolution - 1) ** 2 * 2

    total = building_tris + tree_tris + terrain_tris

    return {
        "estimated_triangles": total,
        "estimated_memory_mb": total * 0.0001,  # ~100 bytes per triangle
        "ray_trace_time_factor": total / 100000,  # Relative to 100k base
        "recommendation": (
            "fast" if total < 50000 else
            "medium" if total < 200000 else
            "consider_simplification"
        ),
    }
