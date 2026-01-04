"""Create a serene forest glade scene completely from Blender Python API.

Run with:
    blender -b -P scripts/serene_grove.py -- --output //serene.png
"""

import argparse
import math
import random

import bpy
from mathutils import Vector, noise as mnoise


def clear_scene() -> None:
    """Remove all existing data so the script is fully repeatable."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    for datablock_collection in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.lights,
        bpy.data.images,
        bpy.data.textures,
    ):
        for block in datablock_collection:
            datablock_collection.remove(block)


def configure_render() -> None:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.film_transparent = False
    scene.cycles.samples = 128
    scene.cycles.use_adaptive_sampling = True
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "High Contrast"

    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()

    background = nodes.new(type="ShaderNodeBackground")
    background.inputs[0].default_value = (0.0705, 0.1059, 0.1411, 1.0)
    background.inputs[1].default_value = 1.0

    sky_tex = nodes.new(type="ShaderNodeTexSky")
    sky_tex.sun_elevation = math.radians(18)
    sky_tex.air_density = 1.05
    sky_tex.dust_density = 2.2

    output = nodes.new(type="ShaderNodeOutputWorld")

    links.new(sky_tex.outputs[0], background.inputs[0])
    links.new(background.outputs[0], output.inputs[0])


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    rot_quat = direction.to_track_quat("-Z", "Y")
    obj.rotation_euler = rot_quat.to_euler()


def create_camera() -> bpy.types.Object:
    camera_data = bpy.data.cameras.new(name="Camera")
    camera_data.lens = 35
    camera_object = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera_object)

    camera_object.location = Vector((14.0, -12.0, 8.0))
    look_at(camera_object, Vector((0.0, 0.0, 2.0)))
    bpy.context.scene.camera = camera_object
    return camera_object


def create_sun_light() -> bpy.types.Object:
    sun_data = bpy.data.lights.new(name="Sun", type="SUN")
    sun_data.energy = 8.0
    sun_data.angle = math.radians(1.5)
    sun_object = bpy.data.objects.new(name="Sun", object_data=sun_data)
    bpy.context.collection.objects.link(sun_object)
    sun_object.location = Vector((12.0, -6.0, 14.0))
    look_at(sun_object, Vector((0.0, 0.0, 0.0)))
    return sun_object


def create_fill_light() -> bpy.types.Object:
    area_data = bpy.data.lights.new(name="Fill", type="AREA")
    area_data.energy = 800.0
    area_data.size = 8.0
    area_object = bpy.data.objects.new(name="Fill", object_data=area_data)
    bpy.context.collection.objects.link(area_object)
    area_object.location = Vector((-10.0, 6.0, 6.0))
    look_at(area_object, Vector((0.0, 0.0, 1.0)))
    return area_object


def create_ground() -> bpy.types.Object:
    bpy.ops.mesh.primitive_grid_add(
        size=60.0, x_subdivisions=140, y_subdivisions=140, location=(0.0, 0.0, 0.0)
    )
    ground = bpy.context.active_object
    ground.name = "Ground"

    for vert in ground.data.vertices:
        sample_coord = Vector((vert.co.x * 0.08, vert.co.y * 0.08, 0.0))
        height = mnoise.multi_fractal(sample_coord, 1.6, 1.0, 4) * 2.4
        slope = mnoise.noise(sample_coord + Vector((0.0, 0.0, 0.5))) * 0.6
        vert.co.z = height + slope

    ground.data.update()

    bpy.ops.object.shade_smooth()

    ground_material = bpy.data.materials.new(name="GroundMaterial")
    ground_material.use_nodes = True
    nodes = ground_material.node_tree.nodes
    links = ground_material.node_tree.links

    principled = nodes.get("Principled BSDF")
    tex_coord = nodes.new(type="ShaderNodeTexCoord")
    noise = nodes.new(type="ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 4.5
    noise.inputs["Detail"].default_value = 2.2

    color_ramp = nodes.new(type="ShaderNodeValToRGB")
    color_ramp.color_ramp.elements[0].position = 0.22
    color_ramp.color_ramp.elements[0].color = (0.1, 0.22, 0.09, 1.0)
    color_ramp.color_ramp.elements[1].position = 0.78
    color_ramp.color_ramp.elements[1].color = (0.24, 0.34, 0.15, 1.0)

    bump = nodes.new(type="ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.2

    links.new(tex_coord.outputs["Object"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], color_ramp.inputs["Fac"])
    links.new(color_ramp.outputs["Color"], principled.inputs["Base Color"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], principled.inputs["Normal"])
    principled.inputs["Roughness"].default_value = 0.85
    principled.inputs["Sheen Tint"].default_value = 0.35

    ground.data.materials.append(ground_material)
    return ground


def create_water() -> bpy.types.Object:
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, 0.0, 0.65))
    water = bpy.context.active_object
    water.name = "Water"
    water.scale = (18.0, 12.0, 1.0)

    water_material = bpy.data.materials.new(name="WaterMaterial")
    water_material.use_nodes = True
    nodes = water_material.node_tree.nodes
    links = water_material.node_tree.links

    principled = nodes.get("Principled BSDF")
    principled.inputs["Transmission"].default_value = 1.0
    principled.inputs["Roughness"].default_value = 0.04
    principled.inputs["IOR"].default_value = 1.333
    principled.inputs["Base Color"].default_value = (0.16, 0.25, 0.28, 1.0)

    tex_coord = nodes.new(type="ShaderNodeTexCoord")
    musgrave = nodes.new(type="ShaderNodeTexMusgrave")
    musgrave.inputs[1].default_value = 3.5
    musgrave.inputs[2].default_value = 2.5
    musgrave.inputs[3].default_value = 2.0

    bump = nodes.new(type="ShaderNodeBump")
    bump.inputs[0].default_value = 0.1

    links.new(tex_coord.outputs["Generated"], musgrave.inputs["Vector"])
    links.new(musgrave.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], principled.inputs["Normal"])

    water.data.materials.append(water_material)
    return water


def create_tree_materials() -> tuple[bpy.types.Material, bpy.types.Material]:
    trunk_mat = bpy.data.materials.new(name="Trunk")
    trunk_mat.use_nodes = True
    trunk_nodes = trunk_mat.node_tree.nodes
    trunk_nodes["Principled BSDF"].inputs["Base Color"].default_value = (
        0.24,
        0.13,
        0.08,
        1.0,
    )
    trunk_nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9

    leaf_mat = bpy.data.materials.new(name="Foliage")
    leaf_mat.use_nodes = True
    leaf_nodes = leaf_mat.node_tree.nodes
    leaf_nodes["Principled BSDF"].inputs["Base Color"].default_value = (
        0.08,
        0.25,
        0.12,
        1.0,
    )
    leaf_nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.4
    leaf_nodes["Principled BSDF"].inputs["Sheen"].default_value = 0.35
    return trunk_mat, leaf_mat


def add_tree(location: Vector, trunk_mat: bpy.types.Material, leaf_mat: bpy.types.Material) -> None:
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.12, depth=1.5, location=location)
    trunk = bpy.context.active_object
    trunk.name = "Trunk"
    trunk.data.materials.append(trunk_mat)

    canopy_height = random.uniform(1.8, 2.4)
    bpy.ops.mesh.primitive_cone_add(
        vertices=10,
        radius1=1.2,
        radius2=0.05,
        depth=canopy_height,
        location=location + Vector((0.0, 0.0, 1.0)),
    )
    canopy = bpy.context.active_object
    canopy.name = "Canopy"
    canopy.scale = (random.uniform(0.8, 1.2),) * 2 + (1.0,)
    canopy.data.materials.append(leaf_mat)

    canopy.parent = trunk


def scatter_trees(ground: bpy.types.Object) -> None:
    random.seed(4)
    trunk_mat, leaf_mat = create_tree_materials()
    for _ in range(26):
        angle = random.uniform(0, 2 * math.pi)
        radius = random.uniform(5.0, 13.0)
        x = math.cos(angle) * radius
        y = math.sin(angle) * radius
        z = 0.05
        scale = random.uniform(0.85, 1.35)
        location = Vector((x, y, z))
        add_tree(location, trunk_mat, leaf_mat)
        bpy.context.active_object.scale *= scale


def add_fog_volume() -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=60.0, location=(0.0, 0.0, 6.0))
    volume = bpy.context.active_object
    volume.name = "Fog"

    fog_mat = bpy.data.materials.new(name="FogVolume")
    fog_mat.use_nodes = True
    nodes = fog_mat.node_tree.nodes
    links = fog_mat.node_tree.links
    nodes.clear()

    principled = nodes.new(type="ShaderNodeVolumePrincipled")
    principled.inputs["Color"].default_value = (0.55, 0.62, 0.7, 1.0)
    principled.inputs["Density"].default_value = 0.03
    principled.inputs["Anisotropy"].default_value = 0.1

    output = nodes.new(type="ShaderNodeOutputMaterial")
    links.new(principled.outputs["Volume"], output.inputs["Volume"])

    volume.data.materials.append(fog_mat)
    volume.display_type = "WIRE"
    return volume


def animate_camera(camera: bpy.types.Object) -> None:
    """Add a slow orbit for extra life when previewing interactively."""
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 120
    camera.location = Vector((14.0, -12.0, 8.0))
    camera.keyframe_insert(data_path="location", frame=1)
    camera.keyframe_insert(data_path="rotation_euler", frame=1)

    camera.location = Vector((-10.0, 12.0, 7.0))
    look_at(camera, Vector((0.0, 0.0, 2.0)))
    camera.keyframe_insert(data_path="location", frame=120)
    camera.keyframe_insert(data_path="rotation_euler", frame=120)

    for fcurve in camera.animation_data.action.fcurves:
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = "SINE"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="//serene_grove.png",
        help="Output path for the render. Uses Blender's // prefix for the blend file directory by default.",
    )
    driver_namespace = getattr(bpy.app, "driver_namespace", {})
    return parser.parse_args(args=driver_namespace.get("script_args", []))


def main() -> None:
    args = parse_args()
    clear_scene()
    configure_render()
    camera = create_camera()
    create_sun_light()
    create_fill_light()
    ground = create_ground()
    create_water()
    scatter_trees(ground)
    add_fog_volume()
    animate_camera(camera)

    bpy.context.scene.render.filepath = args.output
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
