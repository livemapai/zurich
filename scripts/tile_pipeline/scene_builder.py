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


# WGS84 semi-major axis (meters) - used for Web Mercator projection
EARTH_RADIUS = 6378137.0


@dataclass
class SceneBounds:
    """Geographic bounds with Web Mercator coordinate conversion.

    Web Mercator (EPSG:3857) is used because map tiles are SQUARE in this
    projection. Using local meters (equirectangular approximation) produces
    non-square scenes that cause tile misalignment when rendered to 512x512.

    At Zurich (47°N), a zoom-16 tile is ~583m × ~583m in Web Mercator,
    but ~414m × ~611m in local meters. This class ensures proper alignment.
    """

    # WGS84 bounds
    west: float
    south: float
    east: float
    north: float

    # Derived values (computed in __post_init__)
    lat_center: float = field(init=False)
    sw_mercator: Tuple[float, float] = field(init=False)
    ne_mercator: Tuple[float, float] = field(init=False)
    width_meters: float = field(init=False)
    height_meters: float = field(init=False)

    def __post_init__(self):
        """Compute derived values using Web Mercator projection."""
        self.lat_center = (self.south + self.north) / 2

        # Convert corners to Web Mercator
        self.sw_mercator = self._wgs84_to_mercator(self.west, self.south)
        self.ne_mercator = self._wgs84_to_mercator(self.east, self.north)

        # Scene dimensions in Web Mercator meters (will be ~square for tiles!)
        self.width_meters = self.ne_mercator[0] - self.sw_mercator[0]
        self.height_meters = self.ne_mercator[1] - self.sw_mercator[1]

    @staticmethod
    def _wgs84_to_mercator(lon: float, lat: float) -> Tuple[float, float]:
        """Convert WGS84 to Web Mercator (EPSG:3857).

        Formula: x = R * lon_rad, y = R * ln(tan(π/4 + lat_rad/2))
        """
        x = math.radians(lon) * EARTH_RADIUS
        y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * EARTH_RADIUS
        return (x, y)

    @staticmethod
    def _mercator_to_wgs84(x: float, y: float) -> Tuple[float, float]:
        """Convert Web Mercator to WGS84."""
        lon = math.degrees(x / EARTH_RADIUS)
        lat = math.degrees(2 * math.atan(math.exp(y / EARTH_RADIUS)) - math.pi / 2)
        return (lon, lat)

    def wgs84_to_local(self, lon: float, lat: float) -> Tuple[float, float]:
        """Convert WGS84 to local scene coordinates (Web Mercator offset from SW)."""
        mx, my = self._wgs84_to_mercator(lon, lat)
        x = mx - self.sw_mercator[0]
        y = my - self.sw_mercator[1]
        return (x, y)

    def local_to_wgs84(self, x: float, y: float) -> Tuple[float, float]:
        """Convert local scene coordinates back to WGS84."""
        mx = x + self.sw_mercator[0]
        my = y + self.sw_mercator[1]
        return self._mercator_to_wgs84(mx, my)

    def lv95_to_local(self, e: float, n: float) -> Tuple[float, float]:
        """Convert Swiss LV95 (EPSG:2056) to local scene coordinates.

        Uses pyproj for accurate transformation: LV95 → WGS84 → Web Mercator → local.
        Falls back to approximate formula if pyproj unavailable.

        Args:
            e: Easting in LV95 meters
            n: Northing in LV95 meters

        Returns:
            (x, y) in local scene coordinates
        """
        try:
            from pyproj import Transformer
            transformer = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)
            lon, lat = transformer.transform(e, n)
        except ImportError:
            # Approximate conversion (good to ~10m for Zurich area)
            # LV95 origin: E=2600000, N=1200000 at ~7.44°E, ~46.95°N
            lon = (e - 2600000) / 75500 + 7.44
            lat = (n - 1200000) / 111320 + 46.95

        return self.wgs84_to_local(lon, lat)

    def is_in_bounds_lv95(self, e: float, n: float, margin: float = 50.0) -> bool:
        """Check if LV95 coordinate is within tile bounds (with margin).

        Args:
            e: Easting in LV95 meters
            n: Northing in LV95 meters
            margin: Extra margin in meters

        Returns:
            True if coordinate is within bounds
        """
        x, y = self.lv95_to_local(e, n)
        return (
            -margin < x < self.width_meters + margin and
            -margin < y < self.height_meters + margin
        )


@dataclass
class SceneStatistics:
    """Statistics about the built scene."""

    num_buildings: int = 0
    num_lod2_buildings: int = 0  # LOD2 buildings loaded from OBJ
    num_roof_faces: int = 0  # Individual roof faces from LOD2
    num_trees: int = 0
    num_streets: int = 0
    num_water_bodies: int = 0
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

    def add_lod2_buildings(
        self,
        obj_dir: str,
        metadata_path: Optional[str] = None,
        classify_faces: bool = True,
    ) -> "SceneBuilder":
        """Add LOD2 building meshes from OBJ files.

        LOD2 buildings have actual roof geometry (gabled, hipped, flat) instead
        of simple box extrusions. This method loads OBJ files in LV95 coordinates
        and converts them to the local scene coordinate system.

        Args:
            obj_dir: Directory containing OBJ files (in LV95 coordinates)
            metadata_path: Optional path to metadata.json with building bounds
            classify_faces: If True, separate roof and wall meshes for texturing

        Returns:
            Self for method chaining
        """
        from pathlib import Path
        import json

        obj_path = Path(obj_dir)
        if not obj_path.exists():
            print(f"[LOD2] Warning: OBJ directory not found: {obj_dir}")
            return self

        # Load metadata if available (for faster bounds checking)
        building_metadata = {}
        if metadata_path:
            meta_path = Path(metadata_path)
            if meta_path.exists():
                with open(meta_path) as f:
                    data = json.load(f)
                    for bldg in data.get("buildings", []):
                        building_metadata[bldg["id"]] = bldg

        # Find OBJ files
        obj_files = list(obj_path.glob("*.obj"))
        if not obj_files:
            print(f"[LOD2] No OBJ files found in {obj_dir}")
            return self

        print(f"[LOD2] Processing {len(obj_files)} OBJ files...")
        loaded_count = 0
        skipped_count = 0

        for obj_file in obj_files:
            building_id = obj_file.stem

            # Check if building is in tile bounds using metadata
            if building_id in building_metadata:
                bounds = building_metadata[building_id].get("bounds", {})
                center_e = (bounds.get("min_e", 0) + bounds.get("max_e", 0)) / 2
                center_n = (bounds.get("min_n", 0) + bounds.get("max_n", 0)) / 2

                if not self.bounds.is_in_bounds_lv95(center_e, center_n):
                    skipped_count += 1
                    continue

            # Load and transform OBJ mesh
            mesh = self._load_lod2_obj(obj_file, classify_faces)
            if mesh is not None:
                if isinstance(mesh, tuple):
                    # Separate roof and wall meshes
                    roof_mesh, wall_mesh = mesh
                    if roof_mesh is not None:
                        self._meshes.append(roof_mesh)
                        # Count faces for statistics
                        self.stats.num_roof_faces += len(roof_mesh.faces)
                    if wall_mesh is not None:
                        self._meshes.append(wall_mesh)
                else:
                    self._meshes.append(mesh)
                loaded_count += 1
                self.stats.num_lod2_buildings += 1

        print(f"[LOD2] Loaded {loaded_count} buildings, skipped {skipped_count} out of bounds")
        return self

    def _load_lod2_obj(
        self,
        obj_path,
        classify_faces: bool = True,
        roof_threshold: float = 0.3,
    ) -> Optional[trimesh.Trimesh]:
        """Load an OBJ file and convert from LV95 to local coordinates.

        Args:
            obj_path: Path to OBJ file
            classify_faces: If True, separate roof from wall faces
            roof_threshold: Normal.z threshold for roof classification

        Returns:
            Trimesh or tuple of (roof_mesh, wall_mesh) if classify_faces=True
        """
        try:
            # Parse OBJ manually for coordinate control
            vertices = []
            faces = []

            with open(obj_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    parts = line.split()
                    if not parts:
                        continue

                    if parts[0] == 'v':
                        # Vertex: v X Y Z where X=Easting, Y=Elevation, Z=-Northing
                        # (Stadt Zürich LOD2 uses rotated coordinate system)
                        obj_x, obj_y, obj_z = float(parts[1]), float(parts[2]), float(parts[3])
                        # Convert to LV95: E=X, N=-Z, Elevation=Y
                        e = obj_x
                        n = -obj_z  # Invert Z to get Northing
                        elev = obj_y
                        # Convert to local scene coordinates
                        x, y = self.bounds.lv95_to_local(e, n)
                        vertices.append([x, y, elev])

                    elif parts[0] == 'f':
                        # Face: f v1 v2 v3 ... (1-indexed)
                        face_verts = []
                        for p in parts[1:]:
                            v_idx = int(p.split('/')[0]) - 1
                            face_verts.append(v_idx)
                        if len(face_verts) >= 3:
                            faces.append(face_verts)

            if not vertices or not faces:
                return None

            vertices = np.array(vertices)
            faces = np.array(faces) if all(len(f) == 3 for f in faces) else faces

            # Create mesh
            mesh = trimesh.Trimesh(vertices=vertices, faces=faces)

            if not classify_faces:
                return mesh

            # Classify faces into roof and wall based on normal direction
            mesh.fix_normals()
            face_normals = mesh.face_normals

            roof_faces = []
            wall_faces = []

            for i, normal in enumerate(face_normals):
                if normal[2] > roof_threshold:
                    roof_faces.append(i)
                else:
                    wall_faces.append(i)

            # Create separate meshes
            roof_mesh = None
            wall_mesh = None

            if roof_faces:
                roof_mesh = mesh.submesh([roof_faces], append=True)
            if wall_faces:
                wall_mesh = mesh.submesh([wall_faces], append=True)

            return (roof_mesh, wall_mesh)

        except Exception as e:
            # Skip invalid OBJ files silently
            return None

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

    def add_streets(
        self,
        features: List[Feature],
        default_width: float = 6.0,
        elevation_offset: float = 0.05,
    ) -> "SceneBuilder":
        """Add street surfaces as flat polygons.

        Streets are buffered from centerlines to create road polygons.
        They are placed slightly above terrain to prevent z-fighting.

        Args:
            features: Street features with LineString geometry and width property
            default_width: Default road width in meters if not specified
            elevation_offset: Height above terrain in meters (0.05m = 5cm)

        Returns:
            Self for method chaining
        """
        from .geometry import buffer_line_to_polygon

        for feature in features:
            if feature.geometry_type not in ("LineString", "MultiLineString"):
                continue

            width = feature.height if feature.height > 0 else default_width
            base_z = feature.properties.get("elevation", 0) + elevation_offset

            # Handle LineString and MultiLineString
            if feature.geometry_type == "LineString":
                lines = [feature.coordinates]
            else:
                lines = feature.coordinates

            for line_coords in lines:
                # Convert to WGS84 tuples for buffering
                wgs84_coords = [(c[0], c[1]) for c in line_coords]

                # Buffer line to polygon
                poly_coords = buffer_line_to_polygon(
                    wgs84_coords,
                    width_meters=width,
                    cap_style="flat",
                    latitude=self.bounds.lat_center,
                )

                if poly_coords and len(poly_coords) >= 3:
                    mesh = self._create_flat_polygon(poly_coords, base_z)
                    if mesh is not None:
                        self._meshes.append(mesh)
                        self.stats.num_streets += 1

        return self

    def add_water_bodies(
        self,
        features: List[Feature],
        default_river_width: float = 5.0,
        elevation_offset: float = -0.1,
    ) -> "SceneBuilder":
        """Add water body surfaces as flat polygons.

        Lakes/ponds: Use polygon directly
        Rivers/streams: Buffer from centerline using width property

        Water is placed slightly below terrain level.

        Args:
            features: Water features (Polygon for lakes, LineString for rivers)
            default_river_width: Default width for rivers in meters
            elevation_offset: Height relative to terrain (-0.1m = 10cm below)

        Returns:
            Self for method chaining
        """
        from .geometry import buffer_line_to_polygon

        for feature in features:
            base_z = feature.properties.get("elevation", 0) + elevation_offset

            if feature.geometry_type == "Polygon":
                # Lakes/ponds - use polygon directly
                if len(feature.coordinates) > 0 and len(feature.coordinates[0]) >= 3:
                    poly_coords = [(c[0], c[1]) for c in feature.coordinates[0]]
                    mesh = self._create_flat_polygon(poly_coords, base_z)
                    if mesh is not None:
                        self._meshes.append(mesh)
                        self.stats.num_water_bodies += 1

            elif feature.geometry_type == "MultiPolygon":
                # Multiple lake polygons
                for polygon in feature.coordinates:
                    if len(polygon) > 0 and len(polygon[0]) >= 3:
                        poly_coords = [(c[0], c[1]) for c in polygon[0]]
                        mesh = self._create_flat_polygon(poly_coords, base_z)
                        if mesh is not None:
                            self._meshes.append(mesh)
                            self.stats.num_water_bodies += 1

            elif feature.geometry_type == "LineString":
                # Rivers/streams - buffer to polygon
                width = feature.height if feature.height > 0 else default_river_width
                wgs84_coords = [(c[0], c[1]) for c in feature.coordinates]

                poly_coords = buffer_line_to_polygon(
                    wgs84_coords,
                    width_meters=width,
                    cap_style="round",  # Round ends for natural river look
                    latitude=self.bounds.lat_center,
                )

                if poly_coords and len(poly_coords) >= 3:
                    mesh = self._create_flat_polygon(poly_coords, base_z)
                    if mesh is not None:
                        self._meshes.append(mesh)
                        self.stats.num_water_bodies += 1

            elif feature.geometry_type == "MultiLineString":
                # Multiple river segments
                width = feature.height if feature.height > 0 else default_river_width
                for line_coords in feature.coordinates:
                    wgs84_coords = [(c[0], c[1]) for c in line_coords]

                    poly_coords = buffer_line_to_polygon(
                        wgs84_coords,
                        width_meters=width,
                        cap_style="round",
                        latitude=self.bounds.lat_center,
                    )

                    if poly_coords and len(poly_coords) >= 3:
                        mesh = self._create_flat_polygon(poly_coords, base_z)
                        if mesh is not None:
                            self._meshes.append(mesh)
                            self.stats.num_water_bodies += 1

        return self

    def _create_flat_polygon(
        self,
        wgs84_coords: List[Tuple[float, float]],
        z: float = 0,
    ) -> Optional[trimesh.Trimesh]:
        """Create a flat polygon mesh from WGS84 coordinates.

        Args:
            wgs84_coords: List of (lon, lat) coordinates forming polygon
            z: Z elevation in meters

        Returns:
            Trimesh object or None if invalid
        """
        if len(wgs84_coords) < 3:
            return None

        try:
            from shapely.geometry import Polygon as ShapelyPolygon

            # Convert to local coordinates
            local_coords = np.array([
                self.bounds.wgs84_to_local(lon, lat)
                for lon, lat in wgs84_coords
            ])

            # Create Shapely polygon for triangulation
            shapely_poly = ShapelyPolygon(local_coords)

            if not shapely_poly.is_valid:
                shapely_poly = shapely_poly.buffer(0)

            if shapely_poly.is_empty:
                return None

            # Triangulate using trimesh
            from shapely import get_coordinates
            import triangle

            # Get exterior coordinates
            exterior = np.array(shapely_poly.exterior.coords[:-1])  # Remove closing point

            if len(exterior) < 3:
                return None

            # Create simple triangulation
            vertices = np.column_stack([exterior, np.full(len(exterior), z)])

            # Use ear clipping for simple convex-ish polygons
            # For complex polygons, use triangle library
            try:
                # Simple fan triangulation from centroid
                centroid = exterior.mean(axis=0)
                center_vertex = np.array([[centroid[0], centroid[1], z]])
                vertices = np.vstack([vertices, center_vertex])
                center_idx = len(vertices) - 1

                faces = []
                n = len(exterior)
                for i in range(n):
                    faces.append([i, (i + 1) % n, center_idx])
                faces = np.array(faces)

                mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
                return mesh

            except Exception:
                return None

        except Exception:
            return None

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
