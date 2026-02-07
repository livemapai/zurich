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


def shear_footprint_for_isometric(
    footprint: list,
    height: float,
    base_elevation: float,
    isometric_angle: float,
) -> list:
    """Pre-shear footprint so buildings appear at correct position in isometric view.

    When rendering with a tilted camera, taller objects appear displaced from their
    true map position. This function shifts vertices toward the camera to compensate,
    so when rendered through the tilted camera, buildings appear at correct positions.

    Args:
        footprint: List of [x, y] coordinates (in meters)
        height: Building height in meters
        base_elevation: Ground elevation at building location
        isometric_angle: Camera tilt angle in degrees from vertical

    Returns:
        List of [x, y] coordinates shifted for isometric alignment
    """
    total_height = height + base_elevation
    shift = total_height * math.tan(math.radians(isometric_angle))
    # Shift toward camera (south = negative Y) to compensate for tilt
    return [[x, y - shift] for x, y in footprint]


def shear_point_for_isometric(
    x: float,
    y: float,
    z: float,
    total_height: float,
    isometric_angle: float,
) -> tuple:
    """Pre-shear point position for isometric alignment.

    Args:
        x, y, z: Original point position in meters
        total_height: Total height of object (z + object height)
        isometric_angle: Camera tilt angle in degrees from vertical

    Returns:
        Tuple of (x, y_shifted, z) with Y shifted for isometric view
    """
    shift = total_height * math.tan(math.radians(isometric_angle))
    return (x, y - shift, z)


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


# Z-offset constants to prevent z-fighting between coplanar surfaces
# These small offsets ensure proper layering in the depth buffer
STREET_Z_OFFSET = 0.05  # Streets slightly above ground (5cm)
WATER_Z_OFFSET = -0.1   # Water slightly below ground (-10cm)


def create_street(
    footprint: list,
    base_elevation: float = 0,
    name: str = "Street",
) -> object:
    """Create flat street polygon mesh.

    Streets are rendered as flat polygons slightly above terrain
    to prevent z-fighting.

    Args:
        footprint: List of [x, y] coordinates (in meters, already buffered)
        base_elevation: Ground elevation at street location
        name: Object name

    Returns:
        Blender mesh object
    """
    if bpy is None or len(footprint) < 3:
        return None

    bm = bmesh.new()

    # Create vertices for flat polygon with Z-offset to prevent z-fighting
    z = base_elevation + STREET_Z_OFFSET
    verts = []
    for x, y in footprint:
        v = bm.verts.new((x, y, z))
        verts.append(v)

    # Create face
    if len(verts) >= 3:
        try:
            bm.faces.new(verts)
        except ValueError:
            # Invalid geometry
            pass

    # Create mesh
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    return obj


def create_water_body(
    footprint: list,
    base_elevation: float = 0,
    name: str = "Water",
) -> object:
    """Create flat water body polygon mesh.

    Water bodies are rendered as flat polygons slightly below terrain
    to give depth impression.

    Args:
        footprint: List of [x, y] coordinates (in meters)
        base_elevation: Water surface elevation
        name: Object name

    Returns:
        Blender mesh object
    """
    if bpy is None or len(footprint) < 3:
        return None

    bm = bmesh.new()

    # Create vertices for flat polygon with Z-offset to prevent z-fighting
    z = base_elevation + WATER_Z_OFFSET
    verts = []
    for x, y in footprint:
        v = bm.verts.new((x, y, z))
        verts.append(v)

    # Create face
    if len(verts) >= 3:
        try:
            bm.faces.new(verts)
        except ValueError:
            pass

    # Create mesh
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    return obj


def create_water_material(
    name: str,
    color: tuple,
    roughness: float = 0.1,
    transmission: float = 0.3,
) -> object:
    """Create reflective water material with optional transparency.

    Water materials use low roughness for reflections and
    slight transmission for a realistic water appearance.

    Args:
        name: Material name
        color: RGB tuple (0.0-1.0 range)
        roughness: Surface roughness (lower = more reflective)
        transmission: Transparency amount (0=opaque, 1=fully transparent)

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

    # Principled BSDF for water
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.inputs["Base Color"].default_value = (*color, 1.0)
    principled.inputs["Roughness"].default_value = roughness
    principled.inputs["Specular IOR Level"].default_value = 0.5  # Water-like
    principled.inputs["IOR"].default_value = 1.33  # Water IOR

    # Add transmission for transparency effect
    if transmission > 0:
        principled.inputs["Transmission Weight"].default_value = transmission

    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    return mat


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

    # Street surface
    street_color = tuple(style_data.get("street", [0.30, 0.30, 0.32]))
    street_roughness = style_data.get("street_roughness", 0.85)
    materials["street"] = create_principled_material(
        "Street", street_color, street_roughness
    )

    # Sidewalk (lighter than street)
    sidewalk_color = tuple(style_data.get("sidewalk", [0.65, 0.62, 0.58]))
    materials["sidewalk"] = create_principled_material(
        "Sidewalk", sidewalk_color, 0.88
    )

    # Water (uses special water material)
    water_color = tuple(style_data.get("water", [0.20, 0.35, 0.50]))
    water_roughness = style_data.get("water_roughness", 0.12)
    water_transmission = style_data.get("water_transmission", 0.3)
    materials["water"] = create_water_material(
        "Water", water_color, water_roughness, water_transmission
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

    Uses a material-based approach for Blender 5.x compatibility.
    Depth is encoded as grayscale where:
    - 0 (black) = near plane (high objects like rooftops)
    - 1 (white) = far plane (ground level)

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

    # Minimal samples for depth
    scene.cycles.samples = 4
    scene.cycles.use_denoising = False

    # Output resolution
    size = config.get("image_size", 512)
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100

    # Solid white background (far depth)
    scene.render.film_transparent = False

    # Setup world with white background (represents far depth)
    world = bpy.data.worlds.get("World")
    if world is None:
        world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    w_nodes = world.node_tree.nodes
    w_nodes.clear()
    bg = w_nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)  # White = far
    bg.inputs["Strength"].default_value = 1.0
    w_output = w_nodes.new("ShaderNodeOutputWorld")
    world.node_tree.links.new(bg.outputs["Background"], w_output.inputs["Surface"])

    # Setup orthographic camera (top-down)
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = scene_width
    cam_data.clip_start = 1.0
    cam_data.clip_end = 600.0

    cam_obj = bpy.data.objects.new("Camera", cam_data)
    cam_obj.location = (scene_width / 2, scene_height / 2, 500)
    cam_obj.rotation_euler = (0, 0, 0)

    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    # Configure output
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"


def create_depth_material(camera_z: float = 500.0, max_depth: float = 150.0) -> "bpy.types.Material":
    """Create a material that outputs camera-space depth as grayscale.

    Objects closer to camera appear darker, farther objects appear lighter.
    This matches ControlNet depth conventions.

    Args:
        camera_z: Camera Z position in scene
        max_depth: Maximum depth range to map (buildings up to this height)

    Returns:
        Material that visualizes depth as grayscale
    """
    if bpy is None:
        return None

    mat = bpy.data.materials.new(name="DepthVisualize")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Get world-space position
    geometry = nodes.new("ShaderNodeNewGeometry")
    geometry.location = (0, 0)

    # Separate Z component
    separate = nodes.new("ShaderNodeSeparateXYZ")
    separate.location = (200, 0)

    # Map Z to 0..1 range: (camera_z - z) / max_depth
    # Higher Z (closer to camera) = darker (0)
    # Lower Z (ground) = lighter (1)
    subtract = nodes.new("ShaderNodeMath")
    subtract.operation = "SUBTRACT"
    subtract.location = (400, 0)
    subtract.inputs[0].default_value = camera_z
    subtract.use_clamp = True  # Use built-in clamping

    divide = nodes.new("ShaderNodeMath")
    divide.operation = "DIVIDE"
    divide.location = (600, 0)
    divide.inputs[1].default_value = max_depth
    divide.use_clamp = True  # Clamp to 0-1

    # Convert grayscale to color with CombineColor
    combine = nodes.new("ShaderNodeCombineColor")
    combine.location = (800, 0)

    # Emission shader
    emission = nodes.new("ShaderNodeEmission")
    emission.location = (1000, 0)
    emission.inputs["Strength"].default_value = 1.0

    # Output
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (1200, 0)

    # Connect: Geometry.Position -> Separate.Z -> (camera_z - Z) / max_depth -> CombineRGB -> Emission
    links.new(geometry.outputs["Position"], separate.inputs["Vector"])
    links.new(separate.outputs["Z"], subtract.inputs[1])
    links.new(subtract.outputs["Value"], divide.inputs[0])
    # Connect grayscale value to R, G, B channels
    links.new(divide.outputs["Value"], combine.inputs["Red"])
    links.new(divide.outputs["Value"], combine.inputs["Green"])
    links.new(divide.outputs["Value"], combine.inputs["Blue"])
    links.new(combine.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])

    return mat


def setup_normal_render(
    config: dict,
    scene_width: float,
    scene_height: float,
) -> None:
    """Configure Cycles renderer for world-space normal pass output.

    Uses a simple material-based approach that works reliably across Blender versions.
    Surface normals are visualized as colors via a custom shader.

    This is used for ControlNet Normal conditioning to preserve surface
    orientations during AI style transfer.

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

    # Minimal samples for normal pass
    scene.cycles.samples = 4
    scene.cycles.use_denoising = False

    # Output resolution
    size = config.get("image_size", 512)
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100

    # Solid background (neutral normal)
    scene.render.film_transparent = False

    # Setup neutral background world (represents flat up-facing normal)
    world = bpy.data.worlds.get("World")
    if world is None:
        world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    w_nodes = world.node_tree.nodes
    w_nodes.clear()
    bg = w_nodes.new("ShaderNodeBackground")
    # Neutral normal color: (0.5, 0.5, 1.0) = flat surface facing up
    bg.inputs["Color"].default_value = (0.5, 0.5, 1.0, 1.0)
    bg.inputs["Strength"].default_value = 1.0
    w_output = w_nodes.new("ShaderNodeOutputWorld")
    world.node_tree.links.new(bg.outputs["Background"], w_output.inputs["Surface"])

    # Setup orthographic camera (top-down)
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = scene_width
    cam_data.clip_start = 1.0
    cam_data.clip_end = 600.0

    cam_obj = bpy.data.objects.new("Camera", cam_data)
    cam_obj.location = (scene_width / 2, scene_height / 2, 500)
    cam_obj.rotation_euler = (0, 0, 0)

    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    # Configure output
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"


def create_normal_material() -> "bpy.types.Material":
    """Create a material that outputs world-space normals as RGB.

    The normal vector is mapped from [-1, 1] to [0, 1] for each component:
    - R = (X + 1) / 2
    - G = (Y + 1) / 2
    - B = (Z + 1) / 2

    Returns:
        Material that visualizes surface normals
    """
    if bpy is None:
        return None

    mat = bpy.data.materials.new(name="NormalVisualize")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Get geometry normal
    geometry = nodes.new("ShaderNodeNewGeometry")
    geometry.location = (0, 0)

    # Vector math to map -1..1 to 0..1: (normal + 1) * 0.5
    add_one = nodes.new("ShaderNodeVectorMath")
    add_one.operation = "ADD"
    add_one.location = (200, 0)
    add_one.inputs[1].default_value = (1.0, 1.0, 1.0)

    scale_half = nodes.new("ShaderNodeVectorMath")
    scale_half.operation = "SCALE"
    scale_half.location = (400, 0)
    scale_half.inputs["Scale"].default_value = 0.5

    # Emission shader (no lighting influence)
    emission = nodes.new("ShaderNodeEmission")
    emission.location = (600, 0)
    emission.inputs["Strength"].default_value = 1.0

    # Output
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (800, 0)

    # Connect: Geometry.Normal -> Add(1) -> Scale(0.5) -> Emission -> Output
    links.new(geometry.outputs["Normal"], add_one.inputs[0])
    links.new(add_one.outputs["Vector"], scale_half.inputs[0])
    links.new(scale_half.outputs["Vector"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])

    return mat


def setup_edge_render(
    config: dict,
    scene_width: float,
    scene_height: float,
) -> None:
    """Configure Cycles renderer for edge/line pass output.

    Uses Freestyle renderer to generate clean edge lines from 3D geometry.
    Output is black lines on white background, suitable for ControlNet
    Canny/HED conditioning.

    Args:
        config: Render configuration dictionary
        scene_width: Scene width in meters (for camera)
        scene_height: Scene height in meters (for camera)
    """
    if bpy is None:
        return

    scene = bpy.context.scene

    # Use Cycles renderer with Freestyle
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

    # Minimal samples (edges are geometric, not shaded)
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False

    # Output resolution
    size = config.get("image_size", 512)
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100

    # White background (edges will be black lines)
    scene.render.film_transparent = False

    # Setup world with pure white background
    world = bpy.data.worlds.get("World")
    if world is None:
        world = bpy.data.worlds.new("World")
    scene.world = world

    world.use_nodes = True
    w_nodes = world.node_tree.nodes
    w_nodes.clear()

    background = w_nodes.new("ShaderNodeBackground")
    background.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    background.inputs["Strength"].default_value = 1.0

    w_output = w_nodes.new("ShaderNodeOutputWorld")
    world.node_tree.links.new(background.outputs["Background"], w_output.inputs["Surface"])

    # Setup orthographic camera (top-down)
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = scene_width
    cam_data.clip_start = 1.0
    cam_data.clip_end = 600.0

    cam_obj = bpy.data.objects.new("Camera", cam_data)
    cam_obj.location = (scene_width / 2, scene_height / 2, 500)
    cam_obj.rotation_euler = (0, 0, 0)

    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    # Enable Freestyle for edge rendering
    scene.render.use_freestyle = True
    scene.view_layers["ViewLayer"].use_freestyle = True

    # Configure Freestyle line settings
    freestyle = scene.view_layers["ViewLayer"].freestyle_settings
    freestyle.crease_angle = 2.35619  # ~135 degrees - detect sharp edges

    # Configure line set for clean architectural lines
    if freestyle.linesets:
        lineset = freestyle.linesets[0]
    else:
        lineset = freestyle.linesets.new("EdgeLines")

    # Select edge types to render
    lineset.select_silhouette = True      # Outer silhouettes
    lineset.select_border = True          # Mesh borders
    lineset.select_crease = True          # Sharp edges (based on crease_angle)
    lineset.select_edge_mark = False      # Manual edge marks
    lineset.select_external_contour = True  # External contours
    lineset.select_material_boundary = True  # Material boundaries
    lineset.select_contour = True         # Contour lines
    lineset.select_suggestive_contour = False  # Skip suggestive (too noisy)
    lineset.select_ridge_valley = False   # Skip ridge/valley (too noisy)

    # Line style - clean black lines
    linestyle = lineset.linestyle
    linestyle.color = (0.0, 0.0, 0.0)  # Black lines
    linestyle.thickness = 1.5  # Slightly thick for visibility
    linestyle.alpha = 1.0

    # Configure output
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"


def setup_color_render(
    config: dict,
    style_data: dict,
    scene_width: float,
    scene_height: float,
) -> dict:
    """Configure Cycles renderer for full color output.

    For isometric renders, uses the "render-larger-crop-exact" technique:
    renders at 2× resolution and crops center to ensure pixel-perfect alignment.

    Args:
        config: Render configuration dictionary
        style_data: Style dictionary with lighting settings
        scene_width: Scene width in meters
        scene_height: Scene height in meters

    Returns:
        Dict with render metadata (render_scale for post-processing)
    """
    if bpy is None:
        return {"render_scale": 1.0}

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

    # Check if isometric view is requested (shows building facades)
    import math
    isometric = style_data.get("isometric", False)
    isometric_angle = style_data.get("isometric_angle", 12)  # Low angle (Factorio-like)

    # Base output resolution
    base_size = config.get("image_size", 512)

    # For isometric renders, use render-larger-crop-exact technique:
    # With geometry shearing, we only need small margin for building facades
    # extending past tile edge (reduced from 2.0 to 1.3 for faster renders)
    if isometric:
        render_scale = 1.3
    else:
        render_scale = 1.0

    actual_size = int(base_size * render_scale)
    scene.render.resolution_x = actual_size
    scene.render.resolution_y = actual_size
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

    cam_obj = bpy.data.objects.new("Camera", cam_data)

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

        # CRITICAL FIX: Scale ortho_scale by render_scale for larger capture area
        # This ensures all geometry is visible for the subsequent center crop
        cam_data.ortho_scale = scene_width * render_scale
    else:
        # Standard top-down view (for map tiles)
        cam_obj.location = (scene_width / 2, scene_height / 2, 500)
        cam_obj.rotation_euler = (0, 0, 0)
        cam_data.ortho_scale = scene_width

    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    # Configure output
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"  # Full color, not RGBA
    scene.render.image_settings.color_depth = "8"

    # Return metadata for post-processing
    return {"render_scale": render_scale, "target_size": base_size}


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
    parser.add_argument("--save-blend", help="Save .blend file to this path (optional)")

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
    elif render_mode == "normal":
        _render_normal_mode(
            scene_data, config, elevation, width_m, height_m, output_path
        )
    elif render_mode == "edge":
        _render_edge_mode(
            scene_data, config, elevation, width_m, height_m, output_path
        )
    elif render_mode == "semantic":
        _render_semantic_mode(
            scene_data, config, style_data, elevation, width_m, height_m, output_path
        )
    else:
        _render_shadow_mode(
            scene_data, config, elevation, width_m, height_m, output_path
        )

    # Save .blend file if requested
    if args.save_blend:
        blend_path = Path(args.save_blend)
        blend_path.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
        print(f"Saved Blender file: {blend_path}")


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


def create_textured_material(
    name: str,
    texture_path: str,
    fallback_color: tuple = (0.85, 0.82, 0.78),
    roughness: float = 0.8,
    texture_scale: float = 0.1,
    use_box_mapping: bool = True,
) -> object:
    """Create a Principled BSDF material with an image texture.

    Uses box projection mapping which works well for buildings without
    requiring explicit UV unwrapping. The texture is automatically
    projected onto all faces.

    Args:
        name: Material name
        texture_path: Path to albedo texture PNG file
        fallback_color: RGB tuple to use if texture loading fails
        roughness: Surface roughness (0=shiny, 1=matte)
        texture_scale: Meters per texture repeat (smaller = more repetition)
        use_box_mapping: Use box projection (True) or UV coords (False)

    Returns:
        Blender material, or None if bpy unavailable
    """
    if bpy is None:
        return None

    mat = bpy.data.materials.new(name=name)

    if hasattr(mat, "use_nodes") and not mat.use_nodes:
        mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Create Principled BSDF
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (300, 0)
    principled.inputs["Roughness"].default_value = roughness
    principled.inputs["Specular IOR Level"].default_value = 0.3

    # Create output
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (600, 0)
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    # Try to load the texture
    texture_loaded = False
    try:
        import os
        if os.path.exists(texture_path):
            # Load image texture
            img_texture = nodes.new("ShaderNodeTexImage")
            img_texture.location = (-200, 0)

            # Load the image
            img = bpy.data.images.load(texture_path)
            img_texture.image = img
            img_texture.interpolation = "Smart"

            if use_box_mapping:
                # Use Generated coordinates with box projection
                # This avoids UV seams on box-like buildings

                # Texture Coordinate node
                tex_coord = nodes.new("ShaderNodeTexCoord")
                tex_coord.location = (-800, 0)

                # Mapping node for scale control
                mapping = nodes.new("ShaderNodeMapping")
                mapping.location = (-600, 0)
                mapping.vector_type = "POINT"

                # Set scale (inverse of texture_scale for correct mapping)
                # texture_scale is meters per repeat, so scale = 1/texture_scale
                scale_factor = 1.0 / texture_scale if texture_scale > 0 else 10.0
                mapping.inputs["Scale"].default_value = (scale_factor, scale_factor, scale_factor)

                # Connect: Generated -> Mapping -> Image
                links.new(tex_coord.outputs["Generated"], mapping.inputs["Vector"])
                links.new(mapping.outputs["Vector"], img_texture.inputs["Vector"])
            else:
                # Use UV coordinates (requires UV unwrapping on mesh)
                tex_coord = nodes.new("ShaderNodeTexCoord")
                tex_coord.location = (-600, 0)
                links.new(tex_coord.outputs["UV"], img_texture.inputs["Vector"])

            # Connect texture to principled BSDF
            links.new(img_texture.outputs["Color"], principled.inputs["Base Color"])
            texture_loaded = True

    except Exception as e:
        print(f"Warning: Could not load texture {texture_path}: {e}")

    # Fallback to solid color if texture didn't load
    if not texture_loaded:
        principled.inputs["Base Color"].default_value = (*fallback_color, 1.0)

    return mat


def get_texture_path(texture_type: str) -> str:
    """Get the full path to a texture file.

    Looks in the assets/textures directory for the texture type.

    Args:
        texture_type: Texture type name (e.g., "residential_plaster")

    Returns:
        Path string to the albedo.png file
    """
    # Import Path here to avoid circular imports at module level
    from pathlib import Path

    # Try multiple locations for flexibility
    search_paths = [
        Path("scripts/tile_pipeline/assets/textures") / texture_type / "albedo.png",
        Path(".texture_cache") / f"{texture_type}_*.png",
        Path(__file__).parent / "assets" / "textures" / texture_type / "albedo.png",
    ]

    for path in search_paths:
        if "*" in str(path):
            # Glob pattern - find first matching file
            matches = list(path.parent.glob(path.name))
            if matches:
                return str(matches[0])
        elif path.exists():
            return str(path)

    # Return the expected location even if file doesn't exist yet
    return str(search_paths[0])


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
    use_textures = style_data.get("use_textures", False)
    texture_scale = style_data.get("texture_scale", 0.1)
    season = style_data.get("season", "summer")
    llm_style = style_data.get("llm_style", {})  # LLM-generated parameters

    if use_building_types or use_tree_species or llm_style or use_textures:
        print(f"  Data-driven mode: buildings={use_building_types}, trees={use_tree_species}, textures={use_textures}, season={season}")

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

    # Get isometric settings for geometry shearing
    isometric = style_data.get("isometric", False)
    isometric_angle = style_data.get("isometric_angle", 12)  # Default 12° for Factorio-like view

    if isometric and isometric_angle > 0:
        print(f"  Isometric mode: angle={isometric_angle}°, applying geometry shear")

    # Cache for building type materials (data-driven mode)
    building_type_mats = {}

    for i, b in enumerate(buildings):
        footprint = b["footprint"]
        height = b["height"]
        elevation = b.get("elevation", 0)

        # Apply shearing for geographic accuracy in isometric mode
        if isometric and isometric_angle > 0:
            footprint = shear_footprint_for_isometric(
                footprint, height, elevation, isometric_angle
            )

        building = create_building(
            footprint,
            height,
            elevation,
            f"Building_{i}",
        )
        if not building:
            continue

        # Determine material to use
        if use_building_types and b.get("type"):
            building_type = b["type"]
            # Get or create material for this type
            if building_type not in building_type_mats:
                # Get colors and texture from building type mapping
                type_colors = style_data.get("building_type_colors", {}).get(building_type)
                if type_colors:
                    wall_color = tuple(type_colors.get("wall", [0.85, 0.82, 0.78]))
                    roof_color = tuple(type_colors.get("roof", [0.45, 0.38, 0.32]))
                    roughness = type_colors.get("roughness", 0.8)
                    wall_texture = type_colors.get("wall_texture")
                else:
                    # Fallback to default
                    wall_color = tuple(style_data.get("building_wall", [0.85, 0.82, 0.78]))
                    roof_color = tuple(style_data.get("building_roof", [0.45, 0.38, 0.32]))
                    roughness = style_data.get("building_roughness", 0.8)
                    wall_texture = style_data.get("default_wall_texture", "residential_plaster")

                # Use textured material if textures are enabled
                if use_textures and wall_texture:
                    texture_path = get_texture_path(wall_texture)
                    building_type_mats[building_type] = create_textured_material(
                        f"Building_{building_type}_Textured",
                        texture_path,
                        fallback_color=wall_color,
                        roughness=roughness,
                        texture_scale=texture_scale,
                    )
                else:
                    building_type_mats[building_type] = create_data_driven_material(
                        f"Building_{building_type}",
                        wall_color,
                        roughness,
                    )

            mat = building_type_mats[building_type]
        else:
            # Use default wall material (with texture if enabled)
            if use_textures:
                default_texture = style_data.get("default_wall_texture", "residential_plaster")
                texture_path = get_texture_path(default_texture)
                mat = create_textured_material(
                    "DefaultWall_Textured",
                    texture_path,
                    fallback_color=tuple(style_data.get("building_wall", [0.85, 0.82, 0.78])),
                    roughness=style_data.get("building_roughness", 0.8),
                    texture_scale=texture_scale,
                )
            else:
                mat = materials.get("wall")

        # Apply material
        if mat:
            if building.data.materials:
                building.data.materials[0] = mat
            else:
                building.data.materials.append(mat)

    # Create LOD2 roof faces (if present)
    # Roof faces are pre-extracted 3D polygons with material assignments
    roof_faces = scene_data.get("roof_faces", [])
    if roof_faces:
        print(f"  Creating {len(roof_faces)} LOD2 roof faces...")

        # Cache for roof materials
        roof_mats = {}

        for i, rf in enumerate(roof_faces):
            vertices = rf.get("vertices", [])
            material = rf.get("material", "roof_terracotta")

            if len(vertices) < 3:
                continue

            # Create mesh from vertices
            mesh = bpy.data.meshes.new(f"Roof_{i}")
            obj = bpy.data.objects.new(f"Roof_{i}", mesh)
            bpy.context.collection.objects.link(obj)

            # Create BMesh from vertices
            bm = bmesh.new()

            # Add vertices
            bm_verts = []
            for v in vertices:
                x, y, z = v[0], v[1], v[2]
                # Apply shearing for isometric mode if needed
                if isometric and isometric_angle > 0:
                    x, y, z = shear_point_for_isometric(x, y, z, z, isometric_angle)
                bm_verts.append(bm.verts.new((x, y, z)))

            bm.verts.ensure_lookup_table()

            # Create face from all vertices
            try:
                bm.faces.new(bm_verts)
            except ValueError:
                # Face creation failed (e.g., collinear vertices)
                bm.free()
                continue

            bm.to_mesh(mesh)
            bm.free()

            # Get or create material for this roof type
            if material not in roof_mats:
                roof_colors = style_data.get("roof_material_colors", {})
                roof_color = roof_colors.get(material, [0.55, 0.35, 0.28])  # Default terracotta

                if use_textures:
                    texture_path = get_texture_path(material)
                    roof_mats[material] = create_textured_material(
                        f"Roof_{material}_Textured",
                        texture_path,
                        fallback_color=tuple(roof_color),
                        roughness=0.85,
                        texture_scale=texture_scale,
                    )
                else:
                    roof_mats[material] = create_data_driven_material(
                        f"Roof_{material}",
                        tuple(roof_color),
                        roughness=0.85,
                    )

            # Apply material
            roof_mat = roof_mats[material]
            if roof_mat:
                obj.data.materials.append(roof_mat)

    # Create trees
    trees = scene_data.get("trees", [])
    print(f"  Creating {len(trees)} trees...")

    # Cache for tree species materials (data-driven mode)
    tree_species_mats = {}
    default_foliage_mat = materials.get("foliage")
    trunk_mat = materials.get("trunk")

    for i, t in enumerate(trees):
        position = t["position"]
        height = t["height"]

        # Apply shearing for isometric mode
        if isometric and isometric_angle > 0:
            x, y, z = position
            total_height = height + z
            position = list(shear_point_for_isometric(
                x, y, z, total_height, isometric_angle
            ))

        crown, trunk = create_tree(
            position,
            height,
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

    # Create streets
    streets = scene_data.get("streets", [])
    if streets:
        print(f"  Creating {len(streets)} streets...")
        street_mat = materials.get("street")

        for i, s in enumerate(streets):
            footprint = s["footprint"]
            elevation = s.get("elevation", 0)

            # Apply shearing for isometric mode
            if isometric and isometric_angle > 0:
                footprint = [[x, y - elevation * math.tan(math.radians(isometric_angle))]
                             for x, y in footprint]

            street = create_street(
                footprint,
                elevation,
                f"Street_{i}",
            )
            if street and street_mat:
                street.data.materials.append(street_mat)

    # Create water bodies
    water_bodies = scene_data.get("water_bodies", [])
    if water_bodies:
        print(f"  Creating {len(water_bodies)} water bodies...")
        water_mat = materials.get("water")

        for i, w in enumerate(water_bodies):
            footprint = w["footprint"]
            elevation = w.get("elevation", 0)
            water_type = w.get("water_type", "default")

            # Apply shearing for isometric mode
            if isometric and isometric_angle > 0:
                footprint = [[x, y - elevation * math.tan(math.radians(isometric_angle))]
                             for x, y in footprint]

            water = create_water_body(
                footprint,
                elevation,
                f"Water_{i}",
            )
            if water and water_mat:
                water.data.materials.append(water_mat)

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
    render_meta = setup_color_render(config, style_data, width_m, height_m)

    # Save render metadata for post-processing (e.g., isometric crop)
    import json
    meta_path = output_path.parent / "render_meta.json"
    with open(meta_path, "w") as f:
        json.dump(render_meta, f)

    # Render
    print(f"  Rendering to {output_path}...")
    if render_meta.get("render_scale", 1.0) > 1.0:
        print(f"  Using render-larger-crop-exact: scale={render_meta['render_scale']}")
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
    """Render depth pass for ControlNet conditioning.

    Uses emission shaders that encode world-space Z position as grayscale,
    bypassing compositor nodes for Blender 5.x compatibility.

    The depth pass provides geometric structure information that can be used
    with Stable Diffusion ControlNet to generate stylized tiles while
    preserving building positions, heights, and street layouts.
    """
    # Create shared depth visualization material
    # Camera is at Z=500, buildings up to ~150m tall
    print("  Creating depth visualization material...")
    depth_mat = create_depth_material(camera_z=500.0, max_depth=150.0)

    # Create white ground material (so streets are visible)
    white_ground_mat = None
    if bpy is not None:
        white_ground_mat = bpy.data.materials.new(name="WhiteGroundMat")
        white_ground_mat.use_nodes = True
        nodes = white_ground_mat.node_tree.nodes
        nodes.clear()
        emission = nodes.new("ShaderNodeEmission")
        emission.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1)
        emission.inputs["Strength"].default_value = 1.0
        output = nodes.new("ShaderNodeOutputMaterial")
        white_ground_mat.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])

    # Create terrain with WHITE background
    if elevation is not None and elevation.size > 0:
        print("  Creating terrain mesh...")
        terrain = create_terrain_mesh(elevation, width_m, height_m)
        if terrain and white_ground_mat:
            terrain.data.materials.append(white_ground_mat)
    else:
        print("  Using flat ground plane")
        if bpy is not None:
            bpy.ops.mesh.primitive_plane_add(
                size=max(width_m, height_m) + 100,
                location=(width_m / 2, height_m / 2, 0),
            )
            ground = bpy.context.active_object
            ground.name = "Ground"
            if white_ground_mat:
                ground.data.materials.append(white_ground_mat)

    # Create buildings with depth material
    buildings = scene_data.get("buildings", [])
    print(f"  Creating {len(buildings)} buildings...")

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

    # Create trees with depth material
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

    # Create streets with depth material
    streets = scene_data.get("streets", [])
    if streets:
        print(f"  Creating {len(streets)} streets...")
        for i, s in enumerate(streets):
            street = create_street(
                s["footprint"],
                s.get("elevation", 0),
                f"Street_{i}",
            )
            if street and depth_mat:
                street.data.materials.append(depth_mat)

    # Create water bodies with depth material
    water_bodies = scene_data.get("water_bodies", [])
    if water_bodies:
        print(f"  Creating {len(water_bodies)} water bodies...")
        for i, w in enumerate(water_bodies):
            water = create_water_body(
                w["footprint"],
                w.get("elevation", 0),
                f"Water_{i}",
            )
            if water and depth_mat:
                water.data.materials.append(depth_mat)

    # No lighting needed - using emission shaders

    # Setup depth render
    print("  Configuring renderer (depth mode)...")
    setup_depth_render(config, width_m, height_m)

    # Render
    print(f"  Rendering depth pass to {output_path}...")
    bpy.context.scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)

    print("  Done!")


def _render_normal_mode(
    scene_data: dict,
    config: dict,
    elevation,
    width_m: float,
    height_m: float,
    output_path: Path,
) -> None:
    """Render world-space normal pass for ControlNet conditioning.

    The normal pass encodes surface orientation as RGB colors, which can be
    used with ControlNet Normal to preserve building facades and roof angles
    during AI style transfer.

    Uses emission shaders to directly output normals as colors, bypassing
    compositor nodes for better Blender 5.x compatibility.
    """
    # Create shared normal visualization material
    print("  Creating normal visualization material...")
    normal_mat = create_normal_material()

    # Create white ground material (so streets are visible)
    white_ground_mat = None
    if bpy is not None:
        white_ground_mat = bpy.data.materials.new(name="WhiteGroundMat")
        white_ground_mat.use_nodes = True
        nodes = white_ground_mat.node_tree.nodes
        nodes.clear()
        emission = nodes.new("ShaderNodeEmission")
        emission.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1)
        emission.inputs["Strength"].default_value = 1.0
        output = nodes.new("ShaderNodeOutputMaterial")
        white_ground_mat.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])

    # Create terrain with WHITE background
    if elevation is not None and elevation.size > 0:
        print("  Creating terrain mesh...")
        terrain = create_terrain_mesh(elevation, width_m, height_m)
        if terrain and white_ground_mat:
            terrain.data.materials.append(white_ground_mat)
    else:
        print("  Using flat ground plane")
        if bpy is not None:
            bpy.ops.mesh.primitive_plane_add(
                size=max(width_m, height_m) + 100,
                location=(width_m / 2, height_m / 2, 0),
            )
            ground = bpy.context.active_object
            ground.name = "Ground"
            if white_ground_mat:
                ground.data.materials.append(white_ground_mat)

    # Create buildings with normal material
    buildings = scene_data.get("buildings", [])
    print(f"  Creating {len(buildings)} buildings...")

    for i, b in enumerate(buildings):
        building = create_building(
            b["footprint"],
            b["height"],
            b.get("elevation", 0),
            f"Building_{i}",
        )
        if building and normal_mat:
            if building.data.materials:
                building.data.materials[0] = normal_mat
            else:
                building.data.materials.append(normal_mat)

    # Create trees with normal material
    trees = scene_data.get("trees", [])
    print(f"  Creating {len(trees)} trees...")
    for i, t in enumerate(trees):
        crown, trunk = create_tree(
            t["position"],
            t["height"],
            t.get("crown_radius", 3),
            f"Tree_{i}",
        )
        if crown and normal_mat:
            crown.data.materials.append(normal_mat)
        if trunk and normal_mat:
            trunk.data.materials.append(normal_mat)

    # Create streets with normal material
    streets = scene_data.get("streets", [])
    if streets:
        print(f"  Creating {len(streets)} streets...")
        for i, s in enumerate(streets):
            street = create_street(
                s["footprint"],
                s.get("elevation", 0),
                f"Street_{i}",
            )
            if street and normal_mat:
                street.data.materials.append(normal_mat)

    # Create water bodies with normal material
    water_bodies = scene_data.get("water_bodies", [])
    if water_bodies:
        print(f"  Creating {len(water_bodies)} water bodies...")
        for i, w in enumerate(water_bodies):
            water = create_water_body(
                w["footprint"],
                w.get("elevation", 0),
                f"Water_{i}",
            )
            if water and normal_mat:
                water.data.materials.append(normal_mat)

    # No lighting needed - using emission shaders

    # Setup normal render
    print("  Configuring renderer (normal mode)...")
    setup_normal_render(config, width_m, height_m)

    # Render
    print(f"  Rendering normal pass to {output_path}...")
    bpy.context.scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)

    print("  Done!")


def _render_edge_mode(
    scene_data: dict,
    config: dict,
    elevation,
    width_m: float,
    height_m: float,
    output_path: Path,
) -> None:
    """Render edge/line pass for ControlNet Canny/HED conditioning.

    Uses Blender's Freestyle renderer to extract clean architectural edge
    lines from the 3D scene. Output is black lines on white background.
    """
    # Create terrain (needed for proper edge detection context)
    if elevation is not None and elevation.size > 0:
        print("  Creating terrain mesh...")
        terrain = create_terrain_mesh(elevation, width_m, height_m)
        if terrain and bpy is not None:
            # White material so it blends with background
            mat = bpy.data.materials.new(name="EdgeTerrainMat")
            if hasattr(mat, "use_nodes") and not mat.use_nodes:
                mat.use_nodes = True
            nodes = mat.node_tree.nodes
            nodes.clear()
            emission = nodes.new("ShaderNodeEmission")
            emission.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1)
            emission.inputs["Strength"].default_value = 1.0
            output = nodes.new("ShaderNodeOutputMaterial")
            mat.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
            terrain.data.materials.append(mat)
    else:
        print("  Using flat ground plane")
        if bpy is not None:
            bpy.ops.mesh.primitive_plane_add(
                size=max(width_m, height_m) + 100,
                location=(width_m / 2, height_m / 2, 0),
            )
            ground = bpy.context.active_object
            ground.name = "Ground"
            # White emission material
            mat = bpy.data.materials.new(name="EdgeGroundMat")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            nodes.clear()
            emission = nodes.new("ShaderNodeEmission")
            emission.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1)
            output = nodes.new("ShaderNodeOutputMaterial")
            mat.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
            ground.data.materials.append(mat)

    # Create buildings with white emission material (Freestyle draws edges)
    buildings = scene_data.get("buildings", [])
    print(f"  Creating {len(buildings)} buildings...")

    edge_mat = None
    if bpy is not None:
        edge_mat = bpy.data.materials.new(name="EdgeBuildingMat")
        if hasattr(edge_mat, "use_nodes") and not edge_mat.use_nodes:
            edge_mat.use_nodes = True
        nodes = edge_mat.node_tree.nodes
        nodes.clear()
        emission = nodes.new("ShaderNodeEmission")
        emission.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1)
        emission.inputs["Strength"].default_value = 1.0
        output = nodes.new("ShaderNodeOutputMaterial")
        edge_mat.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])

    for i, b in enumerate(buildings):
        building = create_building(
            b["footprint"],
            b["height"],
            b.get("elevation", 0),
            f"Building_{i}",
        )
        if building and edge_mat:
            if building.data.materials:
                building.data.materials[0] = edge_mat
            else:
                building.data.materials.append(edge_mat)

    # Create trees with white material
    trees = scene_data.get("trees", [])
    print(f"  Creating {len(trees)} trees...")
    for i, t in enumerate(trees):
        crown, trunk = create_tree(
            t["position"],
            t["height"],
            t.get("crown_radius", 3),
            f"Tree_{i}",
        )
        if crown and edge_mat:
            crown.data.materials.append(edge_mat)
        if trunk and edge_mat:
            trunk.data.materials.append(edge_mat)

    # Create streets with edge material (will show street edges in Freestyle)
    streets = scene_data.get("streets", [])
    if streets:
        print(f"  Creating {len(streets)} streets...")
        for i, s in enumerate(streets):
            street = create_street(
                s["footprint"],
                s.get("elevation", 0),
                f"Street_{i}",
            )
            if street and edge_mat:
                street.data.materials.append(edge_mat)

    # Create water bodies with edge material
    water_bodies = scene_data.get("water_bodies", [])
    if water_bodies:
        print(f"  Creating {len(water_bodies)} water bodies...")
        for i, w in enumerate(water_bodies):
            water = create_water_body(
                w["footprint"],
                w.get("elevation", 0),
                f"Water_{i}",
            )
            if water and edge_mat:
                water.data.materials.append(edge_mat)

    # No sun needed - using emission materials and Freestyle

    # Setup edge render
    print("  Configuring renderer (edge mode)...")
    setup_edge_render(config, width_m, height_m)

    # Render
    print(f"  Rendering edge pass to {output_path}...")
    bpy.context.scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)

    print("  Done!")


def setup_semantic_render(
    config: dict,
    scene_width: float,
    scene_height: float,
) -> None:
    """Configure renderer for semantic conditioning output.

    Uses orthographic top-down camera with soft ambient lighting
    to produce clean class-colored tiles for LLM conditioning.

    Args:
        config: Render configuration dictionary
        scene_width: Scene width in meters
        scene_height: Scene height in meters
    """
    if bpy is None:
        return

    scene = bpy.context.scene

    # Use Cycles for consistent output
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

    # Low samples - semantic tiles don't need anti-aliasing or complex shading
    scene.cycles.samples = config.get("samples", 16)
    scene.cycles.use_denoising = True

    # Output resolution
    size = config.get("image_size", 512)
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100

    # Opaque background
    scene.render.film_transparent = False

    # Setup world with neutral ambient light
    world = bpy.data.worlds.get("World")
    if world is None:
        world = bpy.data.worlds.new("World")
    scene.world = world

    world.use_nodes = True
    nodes = world.node_tree.nodes
    nodes.clear()

    background = nodes.new("ShaderNodeBackground")
    # Pure white background for flat, shadow-free semantic rendering
    background.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    background.inputs["Strength"].default_value = 2.0  # Strong ambient - no shadows

    output = nodes.new("ShaderNodeOutputWorld")
    world.node_tree.links.new(background.outputs["Background"], output.inputs["Surface"])

    # Orthographic top-down camera (no perspective distortion)
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = scene_width

    cam_obj = bpy.data.objects.new("Camera", cam_data)
    cam_obj.location = (scene_width / 2, scene_height / 2, 500)
    cam_obj.rotation_euler = (0, 0, 0)  # Looking straight down

    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    # Output format
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"


def _render_semantic_mode(
    scene_data: dict,
    config: dict,
    style_data: dict,
    elevation,
    width_m: float,
    height_m: float,
    output_path: Path,
) -> None:
    """Render semantic conditioning tile with class-colored features.

    Produces a top-down orthographic view where:
    - Roofs are colored by type (terracotta, slate, flat)
    - Water is blue
    - Trees are green
    - Streets are dark gray
    - Ground is light green

    This semantic map helps LLMs understand scene structure for
    better style transfer results.
    """
    print("  Rendering semantic conditioning tile...")

    # Get semantic colors from style or use defaults
    semantic_colors = style_data.get("semantic_colors", {})

    # Default semantic palette - VIBRANT colors for clear class separation
    roof_colors = semantic_colors.get("roof", {
        "roof_terracotta": [0.55, 0.35, 0.28],
        "roof_slate": [0.35, 0.32, 0.30],
        "roof_flat": [0.45, 0.45, 0.48],
    })
    water_colors = semantic_colors.get("water", {
        # BRIGHT BLUE water - clearly visible
        "lake": [0.10, 0.45, 0.85],
        "river": [0.15, 0.55, 0.90],
        "stream": [0.20, 0.60, 0.95],
        "default": [0.15, 0.55, 0.90],
    })
    tree_color = tuple(semantic_colors.get("trees", [0.20, 0.65, 0.25]))  # Bright green
    street_color = tuple(semantic_colors.get("streets", [0.50, 0.50, 0.52]))  # Medium gray
    ground_color = tuple(semantic_colors.get("ground", [0.70, 0.82, 0.55]))  # Light green
    wall_color = tuple(semantic_colors.get("building_wall", [0.95, 0.92, 0.88]))  # Light cream

    # Create materials with flat shading (no specular/roughness effects)
    def create_flat_material(name: str, color: tuple) -> object:
        """Create simple diffuse material for semantic rendering."""
        if bpy is None:
            return None
        mat = bpy.data.materials.new(name=name)
        if hasattr(mat, "use_nodes") and not mat.use_nodes:
            mat.use_nodes = True
        nodes = mat.node_tree.nodes
        nodes.clear()
        diffuse = nodes.new("ShaderNodeBsdfDiffuse")
        diffuse.inputs["Color"].default_value = (*color, 1.0)
        output = nodes.new("ShaderNodeOutputMaterial")
        mat.node_tree.links.new(diffuse.outputs["BSDF"], output.inputs["Surface"])
        return mat

    # Create roof materials (by type)
    roof_mats = {}
    for roof_type, color in roof_colors.items():
        roof_mats[roof_type] = create_flat_material(f"Semantic_{roof_type}", tuple(color))

    # Create other materials
    tree_mat = create_flat_material("Semantic_Trees", tree_color)
    trunk_mat = create_flat_material("Semantic_Trunk", tree_color)  # Same as tree - no black dots
    street_mat = create_flat_material("Semantic_Streets", street_color)
    ground_mat = create_flat_material("Semantic_Ground", ground_color)
    wall_mat = create_flat_material("Semantic_Wall", wall_color)

    # Water materials (by type)
    water_mats = {}
    for water_type, color in water_colors.items():
        water_mats[water_type] = create_flat_material(f"Semantic_Water_{water_type}", tuple(color))

    # Create terrain/ground
    if elevation is not None and elevation.size > 0:
        print("  Creating terrain mesh...")
        terrain = create_terrain_mesh(elevation, width_m, height_m)
        if terrain and ground_mat:
            terrain.data.materials.append(ground_mat)
    else:
        print("  Creating ground plane...")

    # Ground plane
    setup_ground_plane(width_m, height_m, ground_mat)

    # Create buildings with semantic roof colors
    buildings = scene_data.get("buildings", [])
    print(f"  Creating {len(buildings)} buildings with semantic roof colors...")

    for i, b in enumerate(buildings):
        building = create_building(
            b["footprint"],
            b["height"],
            b.get("elevation", 0),
            f"Building_{i}",
        )
        if not building:
            continue

        # Determine roof type from building type
        building_type = b.get("type", "default")
        roof_material = b.get("roof_material")

        # Infer roof type if not specified
        if not roof_material:
            # Map building types to roof materials
            type_to_roof = {
                "Gebaeude_Wohngebaeude": "roof_terracotta",
                "Gebaeude_Wohngebaeude_mit_Gewerbe": "roof_terracotta",
                "Gebaeude_Handel": "roof_flat",
                "Gebaeude_Buerohaus": "roof_flat",
                "Gebaeude_Industrie": "roof_flat",
                "Gebaeude_Gewerbe": "roof_flat",
                "Gebaeude_Verwaltung": "roof_slate",
                "Gebaeude_Schule": "roof_terracotta",
                "Gebaeude_Kirche": "roof_slate",
                "Gebaeude_Spital": "roof_flat",
                "Gebaeude_Museum": "roof_slate",
                "Gebaeude_Theater": "roof_slate",
                "Gebaeude_Nebengebaeude": "roof_flat",
                "Gebaeude_Garage": "roof_flat",
            }
            roof_material = type_to_roof.get(building_type, "roof_terracotta")

        # Apply roof material (for semantic mode, we color the whole building by roof type)
        roof_mat = roof_mats.get(roof_material, roof_mats.get("roof_terracotta"))
        if roof_mat:
            if building.data.materials:
                building.data.materials[0] = roof_mat
            else:
                building.data.materials.append(roof_mat)

    # Create LOD2 roof faces if present
    roof_faces = scene_data.get("roof_faces", [])
    if roof_faces:
        print(f"  Creating {len(roof_faces)} LOD2 roof faces...")
        for i, rf in enumerate(roof_faces):
            vertices = rf.get("vertices", [])
            material = rf.get("material", "roof_terracotta")

            if len(vertices) < 3:
                continue

            mesh = bpy.data.meshes.new(f"Roof_{i}")
            obj = bpy.data.objects.new(f"Roof_{i}", mesh)
            bpy.context.collection.objects.link(obj)

            bm = bmesh.new()
            bm_verts = []
            for v in vertices:
                bm_verts.append(bm.verts.new((v[0], v[1], v[2])))
            bm.verts.ensure_lookup_table()

            try:
                bm.faces.new(bm_verts)
            except ValueError:
                bm.free()
                continue

            bm.to_mesh(mesh)
            bm.free()

            roof_mat = roof_mats.get(material, roof_mats.get("roof_terracotta"))
            if roof_mat:
                obj.data.materials.append(roof_mat)

    # Create trees - NO TRUNKS for semantic mode (causes black dots from top-down view)
    trees = scene_data.get("trees", [])
    print(f"  Creating {len(trees)} trees (no trunks)...")
    for i, t in enumerate(trees):
        crown, trunk = create_tree(
            t["position"],
            t["height"],
            t.get("crown_radius", 3),
            f"Tree_{i}",
        )
        if crown and tree_mat:
            crown.data.materials.append(tree_mat)
        # DELETE trunk - it shows through cone in top-down view causing black dots
        if trunk and bpy is not None:
            bpy.data.objects.remove(trunk, do_unlink=True)

    # Create streets
    streets = scene_data.get("streets", [])
    if streets:
        print(f"  Creating {len(streets)} streets...")
        for i, s in enumerate(streets):
            street = create_street(
                s["footprint"],
                s.get("elevation", 0),
                f"Street_{i}",
            )
            if street and street_mat:
                street.data.materials.append(street_mat)

    # Create water bodies
    water_bodies = scene_data.get("water_bodies", [])
    if water_bodies:
        print(f"  Creating {len(water_bodies)} water bodies...")
        for i, w in enumerate(water_bodies):
            water_type = w.get("water_type", "default")
            water = create_water_body(
                w["footprint"],
                w.get("elevation", 0),
                f"Water_{i}",
            )
            water_mat = water_mats.get(water_type, water_mats.get("default"))
            if water and water_mat:
                water.data.materials.append(water_mat)

    # NO SUN for semantic mode - pure ambient lighting, NO shadows
    print("  Setting up shadow-free ambient lighting...")
    # Don't call setup_sun() - we want completely flat, shadow-free rendering
    # The world background provides all the lighting

    # Setup semantic render settings
    print("  Configuring renderer (semantic mode)...")
    setup_semantic_render(config, width_m, height_m)

    # Render
    print(f"  Rendering to {output_path}...")
    bpy.context.scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)

    print("  Done!")


if __name__ == "__main__":
    main()
