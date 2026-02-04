"""
Blender scene builder - runs INSIDE Blender.

This script is executed by Blender headlessly to render tiles.
It builds a 3D scene from exported tile data and renders using Cycles.

Supports three rendering modes:
- Shadow mode (default): Renders shadow-only pass for compositing
- Color mode: Renders full-color tiles with styled materials
- Depth mode: Renders Z-buffer depth pass for AI style transfer (ControlNet)

Usage (called by BlenderShadowRenderer or BlenderTileRenderer):
    blender --background --python blender_scene.py -- \\
        --data-dir /path/to/data --output /path/to/output.png

The data directory should contain:
    - scene.json: Scene configuration, geometry data, and render mode
    - elevation.npy: Elevation heightmap (optional)

Output:
    - Shadow mode: Grayscale PNG where black=shadow, white=lit
    - Color mode: Full RGB PNG with colored buildings/terrain
    - Depth mode: Grayscale PNG where white=far, black=near (normalized Z-buffer)
"""

# This script runs inside Blender, so bpy is available
try:
    import bpy
    import bmesh
except ImportError:
    # When type-checking outside Blender, skip bpy imports
    bpy = None
    bmesh = None

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np


def clear_scene():
    """Remove all objects from the Blender scene."""
    if bpy is None:
        return

    # Select all objects
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    # Clear orphan data blocks
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)

    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)


def create_terrain_mesh(
    elevation: np.ndarray,
    width_meters: float,
    height_meters: float,
) -> object:
    """Create terrain mesh from elevation heightmap.

    Args:
        elevation: 2D array of heights in meters
        width_meters: Scene width in meters
        height_meters: Scene height in meters

    Returns:
        Blender mesh object
    """
    if bpy is None:
        return None

    h, w = elevation.shape

    # Create bmesh for building geometry
    bm = bmesh.new()

    # Create vertex grid
    for y in range(h):
        for x in range(w):
            # Map to world coordinates
            px = (x / (w - 1)) * width_meters
            py = (y / (h - 1)) * height_meters
            pz = elevation[y, x]
            bm.verts.new((px, py, pz))

    bm.verts.ensure_lookup_table()

    # Create faces (quads)
    for y in range(h - 1):
        for x in range(w - 1):
            i = y * w + x
            v1 = bm.verts[i]
            v2 = bm.verts[i + 1]
            v3 = bm.verts[i + w + 1]
            v4 = bm.verts[i + w]
            try:
                bm.faces.new((v1, v2, v3, v4))
            except ValueError:
                # Face already exists or invalid
                pass

    # Create mesh object
    mesh = bpy.data.meshes.new("Terrain")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("Terrain", mesh)
    bpy.context.collection.objects.link(obj)

    return obj


def create_building(
    footprint: list,
    height: float,
    base_elevation: float = 0,
    name: str = "Building",
) -> object:
    """Create extruded building from footprint.

    Args:
        footprint: List of [x, y] coordinates (in meters)
        height: Building height in meters
        base_elevation: Ground elevation at building location
        name: Object name

    Returns:
        Blender mesh object
    """
    if bpy is None or len(footprint) < 3:
        return None

    bm = bmesh.new()

    # Create base vertices
    base_verts = []
    for x, y in footprint:
        v = bm.verts.new((x, y, base_elevation))
        base_verts.append(v)

    # Create base face
    if len(base_verts) >= 3:
        try:
            base_face = bm.faces.new(base_verts)

            # Extrude upward
            result = bmesh.ops.extrude_face_region(bm, geom=[base_face])
            verts = [v for v in result["geom"] if isinstance(v, bmesh.types.BMVert)]
            bmesh.ops.translate(bm, verts=verts, vec=(0, 0, height))
        except ValueError:
            # Invalid geometry
            pass

    # Create mesh
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    # Recalculate normals
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    return obj


def create_tree(
    position: list,
    height: float,
    crown_radius: float,
    name: str = "Tree",
) -> tuple:
    """Create tree as cone (crown) on cylinder (trunk).

    Args:
        position: [x, y, z] position in meters
        height: Total tree height in meters
        crown_radius: Crown radius in meters
        name: Object name prefix

    Returns:
        Tuple of (crown_object, trunk_object)
    """
    if bpy is None:
        return None, None

    x, y, z = position

    # Crown (cone pointing up)
    crown_height = height * 0.7
    bpy.ops.mesh.primitive_cone_add(
        radius1=crown_radius,
        radius2=0.1,  # Small top for better shadow shape
        depth=crown_height,
        vertices=8,  # Low poly for performance
        location=(x, y, z + height * 0.3 + crown_height / 2),
    )
    crown = bpy.context.active_object
    crown.name = f"{name}_Crown"

    # Trunk (cylinder)
    trunk_height = height * 0.35
    trunk_radius = crown_radius * 0.1
    bpy.ops.mesh.primitive_cylinder_add(
        radius=trunk_radius,
        depth=trunk_height,
        vertices=6,
        location=(x, y, z + trunk_height / 2),
    )
    trunk = bpy.context.active_object
    trunk.name = f"{name}_Trunk"

    return crown, trunk


def setup_sun(
    azimuth: float,
    altitude: float,
    angular_size: float = 0.533,
    strength: float = 5.0,
) -> object:
    """Create sun lamp at specified position.

    Args:
        azimuth: Degrees from north, clockwise (0=N, 90=E, 180=S, 270=W)
        altitude: Degrees above horizon (0=horizon, 90=zenith)
        angular_size: Sun's apparent angular size in degrees
        strength: Light intensity

    Returns:
        Blender sun lamp object
    """
    if bpy is None:
        return None

    # Create sun light
    sun_data = bpy.data.lights.new(name="Sun", type="SUN")
    sun_data.energy = strength
    sun_data.angle = math.radians(angular_size)  # Angular diameter for soft shadows

    sun_obj = bpy.data.objects.new("Sun", sun_data)
    bpy.context.collection.objects.link(sun_obj)

    # Calculate rotation from azimuth/altitude
    # Blender sun points in -Z direction by default
    # We need to rotate it to point FROM the sun position

    # Convert meteorological convention to Blender rotation
    # Azimuth: 0=N=+Y, 90=E=+X, 180=S=-Y, 270=W=-X
    az_rad = math.radians(azimuth)
    alt_rad = math.radians(altitude)

    # Sun lamp should point FROM sun TO scene (down)
    # Rotation: first around Z (azimuth), then tilt down (altitude)
    # Blender uses XYZ Euler by default

    # The sun direction in world space FROM the sun:
    # At azimuth=180 (south), altitude=45: light comes from south
    # Rotation X = 90 - altitude (tilt from vertical)
    # Rotation Z = azimuth + 180 (point toward scene)

    rot_x = math.radians(90 - altitude)
    rot_z = math.radians(azimuth + 180)

    sun_obj.rotation_euler = (rot_x, 0, rot_z)

    return sun_obj


def setup_shadow_catcher(
    width: float,
    height: float,
    margin: float = 50.0,
) -> object:
    """Create shadow catcher ground plane.

    The shadow catcher is invisible in the render but catches shadows,
    producing a shadow-only output.

    Args:
        width: Scene width in meters
        height: Scene height in meters
        margin: Extra margin around scene

    Returns:
        Blender plane object
    """
    if bpy is None:
        return None

    # Create plane larger than scene
    size = max(width, height) + 2 * margin
    bpy.ops.mesh.primitive_plane_add(
        size=size,
        location=(width / 2, height / 2, 0),
    )
    plane = bpy.context.active_object
    plane.name = "ShadowCatcher"

    # Enable shadow catcher in Cycles
    plane.is_shadow_catcher = True

    # Create diffuse material (required for shadow catcher to work)
    mat = bpy.data.materials.new(name="ShadowCatcherMat")

    # In Blender 5.0+, materials use nodes by default
    # Only set use_nodes if the attribute exists and is False
    if hasattr(mat, "use_nodes") and not mat.use_nodes:
        mat.use_nodes = True

    nodes = mat.node_tree.nodes

    # Clear default nodes
    nodes.clear()

    # Create simple diffuse shader
    diffuse = nodes.new("ShaderNodeBsdfDiffuse")
    diffuse.inputs["Color"].default_value = (1, 1, 1, 1)  # White

    output = nodes.new("ShaderNodeOutputMaterial")
    mat.node_tree.links.new(diffuse.outputs["BSDF"], output.inputs["Surface"])

    plane.data.materials.append(mat)

    return plane


def setup_building_material() -> object:
    """Create material for buildings (white diffuse).

    Returns:
        Blender material
    """
    if bpy is None:
        return None

    mat = bpy.data.materials.new(name="BuildingMat")

    # In Blender 5.0+, materials use nodes by default
    if hasattr(mat, "use_nodes") and not mat.use_nodes:
        mat.use_nodes = True

    nodes = mat.node_tree.nodes
    nodes.clear()

    diffuse = nodes.new("ShaderNodeBsdfDiffuse")
    diffuse.inputs["Color"].default_value = (0.8, 0.8, 0.8, 1)  # Light gray

    output = nodes.new("ShaderNodeOutputMaterial")
    mat.node_tree.links.new(diffuse.outputs["BSDF"], output.inputs["Surface"])

    return mat


def create_principled_material(
    name: str,
    color: tuple,
    roughness: float = 0.8,
) -> object:
    """Create a Principled BSDF material with specified color.

    Args:
        name: Material name
        color: RGB tuple (0.0-1.0 range)
        roughness: Surface roughness (0=shiny, 1=matte)

    Returns:
        Blender material
    """
    if bpy is None:
        return None

    mat = bpy.data.materials.new(name=name)

    if hasattr(mat, "use_nodes") and not mat.use_nodes:
        mat.use_nodes = True

    nodes = mat.node_tree.nodes
    nodes.clear()

    # Principled BSDF for physically-based shading
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.inputs["Base Color"].default_value = (*color, 1.0)
    principled.inputs["Roughness"].default_value = roughness
    # Reduce specular for more matte look
    principled.inputs["Specular IOR Level"].default_value = 0.3

    output = nodes.new("ShaderNodeOutputMaterial")
    mat.node_tree.links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    return mat


def setup_color_materials(style_data: dict) -> dict:
    """Create colored materials from style definition.

    Args:
        style_data: Style dictionary with color definitions

    Returns:
        Dict mapping material names to Blender materials
    """
    if bpy is None:
        return {}

    materials = {}

    # Building wall material
    wall_color = tuple(style_data.get("building_wall", [0.85, 0.82, 0.78]))
    wall_roughness = style_data.get("building_roughness", 0.8)
    materials["wall"] = create_principled_material(
        "BuildingWall", wall_color, wall_roughness
    )

    # Building roof material
    roof_color = tuple(style_data.get("building_roof", [0.45, 0.35, 0.30]))
    materials["roof"] = create_principled_material(
        "BuildingRoof", roof_color, 0.9
    )

    # Tree foliage
    foliage_color = tuple(style_data.get("tree_foliage", [0.25, 0.45, 0.20]))
    materials["foliage"] = create_principled_material(
        "TreeFoliage", foliage_color, 0.95
    )

    # Tree trunk
    trunk_color = tuple(style_data.get("tree_trunk", [0.35, 0.25, 0.18]))
    materials["trunk"] = create_principled_material(
        "TreeTrunk", trunk_color, 0.9
    )

    # Ground/terrain
    terrain_color = tuple(style_data.get("terrain", [0.45, 0.42, 0.38]))
    terrain_roughness = style_data.get("terrain_roughness", 0.95)
    materials["terrain"] = create_principled_material(
        "Terrain", terrain_color, terrain_roughness
    )

    # Grass (for ground plane if no terrain)
    grass_color = tuple(style_data.get("grass", [0.35, 0.50, 0.25]))
    materials["grass"] = create_principled_material(
        "Grass", grass_color, 0.95
    )

    return materials


def setup_ground_plane(
    width: float,
    height: float,
    material: object,
    margin: float = 50.0,
) -> object:
    """Create visible ground plane with material.

    Unlike shadow catcher, this is a visible ground that renders
    with the specified material color.

    Args:
        width: Scene width in meters
        height: Scene height in meters
        material: Blender material to apply
        margin: Extra margin around scene

    Returns:
        Blender plane object
    """
    if bpy is None:
        return None

    size = max(width, height) + 2 * margin
    bpy.ops.mesh.primitive_plane_add(
        size=size,
        location=(width / 2, height / 2, -0.1),  # Slightly below terrain
    )
    plane = bpy.context.active_object
    plane.name = "Ground"

    # NOT a shadow catcher - visible ground
    plane.is_shadow_catcher = False

    if material:
        plane.data.materials.append(material)

    return plane


def setup_depth_render(
    config: dict,
    scene_width: float,
    scene_height: float,
) -> None:
    """Configure Cycles renderer for depth pass output.

    Renders a normalized Z-buffer where:
    - 0 (black) = near plane
    - 1 (white) = far plane

    This is used for ControlNet Depth conditioning in AI style transfer.

    Args:
        config: Render configuration dictionary
        scene_width: Scene width in meters (for camera)
        scene_height: Scene height in meters (for camera)
    """
    if bpy is None:
        return

    scene = bpy.context.scene

    # Use Cycles renderer
    scene.render.engine = "CYCLES"

    # Configure GPU if requested
    prefs = bpy.context.preferences.addons["cycles"].preferences

    if config.get("use_gpu", True):
        device = config.get("device", "METAL")
        prefs.compute_device_type = device
        scene.cycles.device = "GPU"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
    else:
        scene.cycles.device = "CPU"

    # Minimal samples for depth (no AA/shading needed)
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False

    # Output resolution
    size = config.get("image_size", 512)
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100

    # Transparent background (depth pass will be composited)
    scene.render.film_transparent = True

    # Setup orthographic camera (top-down) - CRITICAL for depth consistency
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = scene_width

    # Set clip planes for consistent depth range
    cam_data.clip_start = 1.0     # Near plane: 1m
    cam_data.clip_end = 600.0     # Far plane: 600m (covers all buildings + camera height)

    cam_obj = bpy.data.objects.new("Camera", cam_data)
    cam_obj.location = (scene_width / 2, scene_height / 2, 500)
    cam_obj.rotation_euler = (0, 0, 0)

    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    # Enable Z pass in view layers
    scene.view_layers["ViewLayer"].use_pass_z = True

    # Setup compositor nodes for depth output
    scene.use_nodes = True
    tree = scene.node_tree
    nodes = tree.nodes
    links = tree.links

    # Clear existing nodes
    nodes.clear()

    # Create render layers node
    render_layers = nodes.new("CompositorNodeRLayers")
    render_layers.location = (0, 0)

    # Create normalize node to map depth to 0-1 range
    normalize = nodes.new("CompositorNodeNormalize")
    normalize.location = (200, 0)

    # Create invert node (so near=black, far=white - ControlNet convention)
    invert = nodes.new("CompositorNodeInvert")
    invert.location = (400, 0)

    # Create composite output
    composite = nodes.new("CompositorNodeComposite")
    composite.location = (600, 0)

    # Connect nodes: RenderLayers.Depth -> Normalize -> Invert -> Composite
    links.new(render_layers.outputs["Depth"], normalize.inputs[0])
    links.new(normalize.outputs[0], invert.inputs["Color"])
    links.new(invert.outputs["Color"], composite.inputs["Image"])

    # Configure output
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "BW"  # Grayscale depth
    scene.render.image_settings.color_depth = "16"  # 16-bit for precision


def setup_color_render(
    config: dict,
    style_data: dict,
    scene_width: float,
    scene_height: float,
) -> None:
    """Configure Cycles renderer for full color output.

    Args:
        config: Render configuration dictionary
        style_data: Style dictionary with lighting settings
        scene_width: Scene width in meters
        scene_height: Scene height in meters
    """
    if bpy is None:
        return

    scene = bpy.context.scene

    # Use Cycles renderer
    scene.render.engine = "CYCLES"

    # Configure GPU
    prefs = bpy.context.preferences.addons["cycles"].preferences

    if config.get("use_gpu", True):
        device = config.get("device", "METAL")
        prefs.compute_device_type = device
        scene.cycles.device = "GPU"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
    else:
        scene.cycles.device = "CPU"

    # Render settings - higher samples for color
    scene.cycles.samples = config.get("samples", 64)
    scene.cycles.use_denoising = True
    scene.cycles.tile_size = config.get("tile_size", 256)

    # Output resolution
    size = config.get("image_size", 512)
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100

    # IMPORTANT: Opaque background (not transparent like shadow mode)
    scene.render.film_transparent = False

    # Setup world background (sky color)
    if config.get("render_sky", True):
        world = bpy.data.worlds.get("World")
        if world is None:
            world = bpy.data.worlds.new("World")
        scene.world = world

        world.use_nodes = True
        nodes = world.node_tree.nodes
        nodes.clear()

        # Background node with sky color
        background = nodes.new("ShaderNodeBackground")
        sky_color = style_data.get("sky_color", [0.7, 0.8, 1.0])
        # Mix sky color with ambient strength for brightness
        ambient = style_data.get("ambient_strength", 0.3)
        background.inputs["Color"].default_value = (*sky_color, 1.0)
        background.inputs["Strength"].default_value = ambient * 2.0

        output = nodes.new("ShaderNodeOutputWorld")
        world.node_tree.links.new(
            background.outputs["Background"], output.inputs["Surface"]
        )

    # Setup camera - orthographic with optional isometric tilt for 3D depth
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = scene_width

    cam_obj = bpy.data.objects.new("Camera", cam_data)

    # Check if isometric view is requested (shows building facades)
    import math
    isometric = style_data.get("isometric", False)
    isometric_angle = style_data.get("isometric_angle", 30)  # degrees from vertical

    if isometric:
        # Isometric camera: tilted to show building walls
        # Angle from vertical (0 = top-down, 45 = classic isometric)
        tilt_rad = math.radians(isometric_angle)

        # Position camera: move back and up to compensate for tilt
        cam_height = 500
        cam_offset = cam_height * math.tan(tilt_rad)

        # Camera looks from south (positive Y offset means camera is south of center)
        cam_obj.location = (
            scene_width / 2,
            scene_height / 2 - cam_offset,
            cam_height
        )
        # Tilt camera to look at scene center
        cam_obj.rotation_euler = (tilt_rad, 0, 0)

        # Increase ortho scale to fit tilted view
        cam_data.ortho_scale = scene_width * (1 + math.sin(tilt_rad) * 0.5)
    else:
        # Standard top-down view (for map tiles)
        cam_obj.location = (scene_width / 2, scene_height / 2, 500)
        cam_obj.rotation_euler = (0, 0, 0)

    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    # Configure output
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"  # Full color, not RGBA
    scene.render.image_settings.color_depth = "8"


def setup_render(config: dict, scene_width: float, scene_height: float) -> None:
    """Configure Cycles renderer for shadow pass.

    Args:
        config: Render configuration dictionary
        scene_width: Scene width in meters (for camera)
        scene_height: Scene height in meters (for camera)
    """
    if bpy is None:
        return

    scene = bpy.context.scene

    # Use Cycles renderer
    scene.render.engine = "CYCLES"

    # Configure GPU if requested
    prefs = bpy.context.preferences.addons["cycles"].preferences

    if config.get("use_gpu", True):
        device = config.get("device", "METAL")

        # Set compute device type
        prefs.compute_device_type = device
        scene.cycles.device = "GPU"

        # Enable all available devices
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
    else:
        scene.cycles.device = "CPU"

    # Render settings
    scene.cycles.samples = config.get("samples", 16)
    scene.cycles.use_denoising = True

    # Tile size (performance)
    scene.cycles.tile_size = config.get("tile_size", 256)

    # Output resolution
    size = config.get("image_size", 512)
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100

    # Transparent background (important for shadow catcher)
    scene.render.film_transparent = True

    # Setup orthographic camera (top-down)
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.type = "ORTHO"
    # Scene is now square in Web Mercator, so width ≈ height
    cam_data.ortho_scale = scene_width

    cam_obj = bpy.data.objects.new("Camera", cam_data)
    # Position camera centered over scene
    cam_obj.location = (scene_width / 2, scene_height / 2, 500)
    cam_obj.rotation_euler = (0, 0, 0)  # Looking straight down

    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    # Configure output
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"


def apply_material_to_all_objects(mat, exclude_names: list = None) -> None:
    """Apply material to all mesh objects except excluded ones.

    Args:
        mat: Blender material to apply
        exclude_names: List of object names to skip
    """
    if bpy is None:
        return

    exclude = exclude_names or ["ShadowCatcher", "Camera", "Sun"]

    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj.name not in exclude:
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)


def main():
    """Main entry point when run inside Blender."""
    if bpy is None:
        print("Error: This script must be run inside Blender")
        sys.exit(1)

    # Parse arguments after "--"
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Blender tile renderer")
    parser.add_argument("--data-dir", required=True, help="Directory with scene data")
    parser.add_argument("--output", required=True, help="Output image path")

    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    output_path = Path(args.output)

    # Load scene data
    with open(data_dir / "scene.json") as f:
        scene_data = json.load(f)

    # Load elevation if available
    elevation_path = data_dir / "elevation.npy"
    if elevation_path.exists():
        elevation = np.load(elevation_path)
    else:
        elevation = None

    config = scene_data.get("config", {})
    bounds_meters = scene_data.get("bounds_meters", {})
    width_m = bounds_meters.get("width", 500)
    height_m = bounds_meters.get("height", 500)

    # Determine render mode
    render_mode = scene_data.get("mode", "shadow")
    style_data = scene_data.get("style", {})

    print(f"Building scene: {width_m:.0f}x{height_m:.0f}m")
    print(f"  Mode: {render_mode}")
    print(f"  Buildings: {len(scene_data.get('buildings', []))}")
    print(f"  Trees: {len(scene_data.get('trees', []))}")

    # Clear existing scene
    clear_scene()

    # Branch based on render mode
    if render_mode == "color":
        _render_color_mode(
            scene_data, config, style_data, elevation, width_m, height_m, output_path
        )
    elif render_mode == "depth":
        _render_depth_mode(
            scene_data, config, elevation, width_m, height_m, output_path
        )
    else:
        _render_shadow_mode(
            scene_data, config, elevation, width_m, height_m, output_path
        )


def _render_shadow_mode(
    scene_data: dict,
    config: dict,
    elevation,
    width_m: float,
    height_m: float,
    output_path: Path,
) -> None:
    """Render shadow-only pass (original behavior)."""
    # Create terrain
    if elevation is not None and elevation.size > 0:
        print("  Creating terrain mesh...")
        create_terrain_mesh(elevation, width_m, height_m)
    else:
        print("  Using flat ground plane")

    # Create shadow catcher (invisible ground that catches shadows)
    print("  Setting up shadow catcher...")
    setup_shadow_catcher(width_m, height_m)

    # Create building material
    building_mat = setup_building_material()

    # Create buildings
    buildings = scene_data.get("buildings", [])
    print(f"  Creating {len(buildings)} buildings...")
    for i, b in enumerate(buildings):
        building = create_building(
            b["footprint"],
            b["height"],
            b.get("elevation", 0),
            f"Building_{i}",
        )
        if building and building_mat:
            if building.data.materials:
                building.data.materials[0] = building_mat
            else:
                building.data.materials.append(building_mat)

    # Create trees
    trees = scene_data.get("trees", [])
    print(f"  Creating {len(trees)} trees...")
    for i, t in enumerate(trees):
        crown, trunk = create_tree(
            t["position"],
            t["height"],
            t.get("crown_radius", 3),
            f"Tree_{i}",
        )
        if crown and building_mat:
            crown.data.materials.append(building_mat)
        if trunk and building_mat:
            trunk.data.materials.append(building_mat)

    # Setup sun
    sun_data = scene_data.get("sun", {})
    print(
        f"  Setting up sun: azimuth={sun_data.get('azimuth', 225)}°, "
        f"altitude={sun_data.get('altitude', 35)}°"
    )
    setup_sun(
        azimuth=sun_data.get("azimuth", 225),
        altitude=sun_data.get("altitude", 35),
        angular_size=sun_data.get("angular_size", 0.533)
        if config.get("soft_shadows", True)
        else 0.01,
    )

    # Setup render
    print("  Configuring renderer (shadow mode)...")
    setup_render(config, width_m, height_m)

    # Render
    print(f"  Rendering to {output_path}...")
    bpy.context.scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)

    print("  Done!")


def create_data_driven_material(
    name: str,
    color: tuple,
    roughness: float = 0.8,
    emission: float = 0.0,
    emission_color: tuple = None,
) -> object:
    """Create material with optional emission (for night scenes, neon, etc.).

    Args:
        name: Material name
        color: RGB tuple (0.0-1.0)
        roughness: Surface roughness
        emission: Emission strength (0=none, 1+=glowing)
        emission_color: RGB tuple for emission (defaults to color)

    Returns:
        Blender material
    """
    if bpy is None:
        return None

    mat = bpy.data.materials.new(name=name)

    if hasattr(mat, "use_nodes") and not mat.use_nodes:
        mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Principled BSDF
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.inputs["Base Color"].default_value = (*color, 1.0)
    principled.inputs["Roughness"].default_value = roughness
    principled.inputs["Specular IOR Level"].default_value = 0.3

    # Add emission if specified
    if emission > 0:
        em_color = emission_color or color
        principled.inputs["Emission Color"].default_value = (*em_color, 1.0)
        principled.inputs["Emission Strength"].default_value = emission

    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    return mat


def _render_color_mode(
    scene_data: dict,
    config: dict,
    style_data: dict,
    elevation,
    width_m: float,
    height_m: float,
    output_path: Path,
) -> None:
    """Render full-color tile with styled materials.

    Supports two modes:
    1. Simple mode: All buildings/trees use same colors from style_data
    2. Data-driven mode: Per-building types and per-tree species colors

    Data-driven mode is activated when:
    - style_data contains "use_building_types": true
    - style_data contains "use_tree_species": true
    - buildings have "type" field
    - trees have "species" field
    """
    print(f"  Style: {style_data.get('name', 'default')}")

    # Check if data-driven mode
    use_building_types = style_data.get("use_building_types", False)
    use_tree_species = style_data.get("use_tree_species", False)
    season = style_data.get("season", "summer")
    llm_style = style_data.get("llm_style", {})  # LLM-generated parameters

    if use_building_types or use_tree_species or llm_style:
        print(f"  Data-driven mode: buildings={use_building_types}, trees={use_tree_species}, season={season}")

    # Create colored materials from style
    print("  Creating colored materials...")
    materials = setup_color_materials(style_data)

    # If LLM style provided, override base colors
    if llm_style:
        print("  Applying LLM-generated style parameters...")
        # Override materials with LLM colors
        if llm_style.get("building_wall_color"):
            materials["wall"] = create_data_driven_material(
                "LLMWall",
                tuple(llm_style["building_wall_color"]),
                llm_style.get("building_roughness", 0.8),
                llm_style.get("building_emission", 0.0),
                tuple(llm_style["window_emission_color"]) if llm_style.get("window_emission_color") else None,
            )
        if llm_style.get("tree_foliage_color"):
            materials["foliage"] = create_data_driven_material(
                "LLMFoliage",
                tuple(llm_style["tree_foliage_color"]),
                0.95,
            )
        if llm_style.get("ground_color"):
            materials["grass"] = create_data_driven_material(
                "LLMGround",
                tuple(llm_style["ground_color"]),
                0.95,
            )
        if llm_style.get("terrain_color"):
            materials["terrain"] = create_data_driven_material(
                "LLMTerrain",
                tuple(llm_style["terrain_color"]),
                style_data.get("terrain_roughness", 0.95),
            )

    # Create terrain mesh or ground plane
    if elevation is not None and elevation.size > 0:
        print("  Creating terrain mesh...")
        terrain = create_terrain_mesh(elevation, width_m, height_m)
        if terrain and materials.get("terrain"):
            terrain.data.materials.append(materials["terrain"])
    else:
        print("  Creating ground plane...")

    # Always create ground plane for color mode (visible base)
    setup_ground_plane(width_m, height_m, materials.get("grass"))

    # Create buildings
    buildings = scene_data.get("buildings", [])
    print(f"  Creating {len(buildings)} buildings...")

    # Cache for building type materials (data-driven mode)
    building_type_mats = {}

    for i, b in enumerate(buildings):
        building = create_building(
            b["footprint"],
            b["height"],
            b.get("elevation", 0),
            f"Building_{i}",
        )
        if not building:
            continue

        # Determine material to use
        if use_building_types and b.get("type"):
            building_type = b["type"]
            # Get or create material for this type
            if building_type not in building_type_mats:
                # Get colors from building type mapping
                type_colors = style_data.get("building_type_colors", {}).get(building_type)
                if type_colors:
                    wall_color = tuple(type_colors.get("wall", [0.85, 0.82, 0.78]))
                    roof_color = tuple(type_colors.get("roof", [0.45, 0.38, 0.32]))
                    roughness = type_colors.get("roughness", 0.8)
                else:
                    # Fallback to default
                    wall_color = tuple(style_data.get("building_wall", [0.85, 0.82, 0.78]))
                    roof_color = tuple(style_data.get("building_roof", [0.45, 0.38, 0.32]))
                    roughness = style_data.get("building_roughness", 0.8)

                building_type_mats[building_type] = create_data_driven_material(
                    f"Building_{building_type}",
                    wall_color,
                    roughness,
                )

            mat = building_type_mats[building_type]
        else:
            # Use default wall material
            mat = materials.get("wall")

        # Apply material
        if mat:
            if building.data.materials:
                building.data.materials[0] = mat
            else:
                building.data.materials.append(mat)

    # Create trees
    trees = scene_data.get("trees", [])
    print(f"  Creating {len(trees)} trees...")

    # Cache for tree species materials (data-driven mode)
    tree_species_mats = {}
    default_foliage_mat = materials.get("foliage")
    trunk_mat = materials.get("trunk")

    for i, t in enumerate(trees):
        crown, trunk = create_tree(
            t["position"],
            t["height"],
            t.get("crown_radius", 3),
            f"Tree_{i}",
        )

        # Determine foliage material
        if use_tree_species and t.get("species"):
            species = t["species"]
            # Get genus (first word)
            genus = species.split()[0] if species else "default"
            cache_key = f"{genus}_{season}"

            if cache_key not in tree_species_mats:
                # Get color from species mapping
                species_colors = style_data.get("tree_species_colors", {})
                season_colors = species_colors.get(genus, {})
                foliage_color = season_colors.get(season)

                if foliage_color:
                    tree_species_mats[cache_key] = create_data_driven_material(
                        f"Foliage_{cache_key}",
                        tuple(foliage_color),
                        0.95,
                    )
                else:
                    # Use default
                    tree_species_mats[cache_key] = default_foliage_mat

            foliage_mat = tree_species_mats[cache_key]
        else:
            foliage_mat = default_foliage_mat

        # Apply materials
        if crown and foliage_mat:
            crown.data.materials.append(foliage_mat)
        if trunk and trunk_mat:
            trunk.data.materials.append(trunk_mat)

    # Setup sun with style-specific strength
    sun_data = scene_data.get("sun", {})
    sun_strength = style_data.get("sun_strength", 3.0)
    sun_color = style_data.get("sun_color", [1.0, 0.98, 0.95])

    print(
        f"  Setting up sun: azimuth={sun_data.get('azimuth', 225)}°, "
        f"altitude={sun_data.get('altitude', 35)}°, strength={sun_strength}"
    )
    sun_obj = setup_sun(
        azimuth=sun_data.get("azimuth", 225),
        altitude=sun_data.get("altitude", 35),
        angular_size=sun_data.get("angular_size", 0.533)
        if config.get("soft_shadows", True)
        else 0.01,
        strength=sun_strength,
    )
    # Set sun color if we have access to the light data
    if sun_obj and hasattr(sun_obj, "data") and sun_obj.data:
        sun_obj.data.color = tuple(sun_color)

    # Setup color render settings
    print("  Configuring renderer (color mode)...")
    setup_color_render(config, style_data, width_m, height_m)

    # Render
    print(f"  Rendering to {output_path}...")
    bpy.context.scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)

    print("  Done!")


def _render_depth_mode(
    scene_data: dict,
    config: dict,
    elevation,
    width_m: float,
    height_m: float,
    output_path: Path,
) -> None:
    """Render depth pass (Z-buffer) for ControlNet conditioning.

    The depth pass provides geometric structure information that can be used
    with Stable Diffusion ControlNet to generate stylized tiles while
    preserving building positions, heights, and street layouts.
    """
    # Create terrain
    if elevation is not None and elevation.size > 0:
        print("  Creating terrain mesh...")
        terrain = create_terrain_mesh(elevation, width_m, height_m)
        # Apply simple gray material to terrain
        if terrain and bpy is not None:
            mat = bpy.data.materials.new(name="DepthTerrainMat")
            if hasattr(mat, "use_nodes") and not mat.use_nodes:
                mat.use_nodes = True
            nodes = mat.node_tree.nodes
            nodes.clear()
            diffuse = nodes.new("ShaderNodeBsdfDiffuse")
            diffuse.inputs["Color"].default_value = (0.5, 0.5, 0.5, 1)
            output = nodes.new("ShaderNodeOutputMaterial")
            mat.node_tree.links.new(diffuse.outputs["BSDF"], output.inputs["Surface"])
            terrain.data.materials.append(mat)
    else:
        print("  Using flat ground plane")
        # Create a simple ground plane
        if bpy is not None:
            bpy.ops.mesh.primitive_plane_add(
                size=max(width_m, height_m) + 100,
                location=(width_m / 2, height_m / 2, 0),
            )
            ground = bpy.context.active_object
            ground.name = "Ground"

    # Create buildings with depth-neutral material (gray)
    buildings = scene_data.get("buildings", [])
    print(f"  Creating {len(buildings)} buildings...")

    depth_mat = None
    if bpy is not None:
        depth_mat = bpy.data.materials.new(name="DepthBuildingMat")
        if hasattr(depth_mat, "use_nodes") and not depth_mat.use_nodes:
            depth_mat.use_nodes = True
        nodes = depth_mat.node_tree.nodes
        nodes.clear()
        diffuse = nodes.new("ShaderNodeBsdfDiffuse")
        diffuse.inputs["Color"].default_value = (0.7, 0.7, 0.7, 1)
        output = nodes.new("ShaderNodeOutputMaterial")
        depth_mat.node_tree.links.new(diffuse.outputs["BSDF"], output.inputs["Surface"])

    for i, b in enumerate(buildings):
        building = create_building(
            b["footprint"],
            b["height"],
            b.get("elevation", 0),
            f"Building_{i}",
        )
        if building and depth_mat:
            if building.data.materials:
                building.data.materials[0] = depth_mat
            else:
                building.data.materials.append(depth_mat)

    # Create trees (simplified for depth)
    trees = scene_data.get("trees", [])
    print(f"  Creating {len(trees)} trees...")
    for i, t in enumerate(trees):
        crown, trunk = create_tree(
            t["position"],
            t["height"],
            t.get("crown_radius", 3),
            f"Tree_{i}",
        )
        if crown and depth_mat:
            crown.data.materials.append(depth_mat)
        if trunk and depth_mat:
            trunk.data.materials.append(depth_mat)

    # No sun needed for depth pass (we use Z-buffer, not shading)
    # But we need some light to avoid completely black renders
    if bpy is not None:
        light_data = bpy.data.lights.new(name="DepthLight", type="SUN")
        light_data.energy = 1.0
        light_obj = bpy.data.objects.new("DepthLight", light_data)
        light_obj.rotation_euler = (0, 0, 0)  # Straight down
        bpy.context.collection.objects.link(light_obj)

    # Setup depth render
    print("  Configuring renderer (depth mode)...")
    setup_depth_render(config, width_m, height_m)

    # Render
    print(f"  Rendering depth pass to {output_path}...")
    bpy.context.scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)

    print("  Done!")


if __name__ == "__main__":
    main()
