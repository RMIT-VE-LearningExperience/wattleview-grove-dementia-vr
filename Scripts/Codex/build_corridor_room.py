import json
import traceback

import unreal


GENERATED_PREFIXES = (
    "WG_Corridor_",
    "WG_LargeRoom_",
    "WG_Sky_",
)

FLOOR_MESH = "/Game/HospitalPack/floor_tile_1"
CEILING_MESH = "/Game/HospitalPack/ceiling_tile"
WALL_MESH = "/Game/HospitalPack/tile_wall"
DOORWAY_MESH = "/Game/HospitalPack/tile_doorway_1"
WINDOW_MESH = "/Game/HospitalPack/tile_window"
CEILING_LIGHT_MESH = "/Game/HospitalPack/ceiling_light"
SPHERE_MESH = "/Engine/BasicShapes/Sphere"

SKY_MATERIAL_PATH = "/Game/HospitalPack/Materials/M_MorningSkyDome"
SUN_MATERIAL_PATH = "/Game/HospitalPack/Materials/M_MorningSunDisc"


def vec(x, y, z):
    return unreal.Vector(float(x), float(y), float(z))


def rot(pitch=0.0, yaw=0.0, roll=0.0):
    value = unreal.Rotator()
    value.pitch = float(pitch)
    value.yaw = float(yaw)
    value.roll = float(roll)
    return value


def get_actor_by_label(actor_subsystem, label):
    for actor in actor_subsystem.get_all_level_actors():
        if actor.get_actor_label() == label:
            return actor
    return None


def remove_previous_generated_actors(actor_subsystem):
    removed = []
    for actor in list(actor_subsystem.get_all_level_actors()):
        label = actor.get_actor_label()
        if any(label.startswith(prefix) for prefix in GENERATED_PREFIXES):
            if actor_subsystem.destroy_actor(actor):
                removed.append(label)
    return removed


def spawn_mesh(
    actor_subsystem,
    asset_cache,
    asset_path,
    label,
    location,
    rotation=None,
    scale=None,
    folder="WG Expansion",
    collision=True,
    cast_shadow=True,
    material=None,
):
    asset = asset_cache.get(asset_path)
    if asset is None:
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        if asset is None:
            raise RuntimeError("Unable to load mesh asset: {}".format(asset_path))
        asset_cache[asset_path] = asset

    actor = actor_subsystem.spawn_actor_from_object(
        asset,
        vec(*location),
        rotation or rot(),
    )
    if actor is None:
        raise RuntimeError("Unable to spawn actor: {}".format(label))

    actor.set_actor_label(label)
    actor.set_folder_path(folder)
    if scale is not None:
        actor.set_actor_scale3d(vec(*scale))

    component = actor.static_mesh_component
    component.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
    component.set_editor_property("cast_shadow", bool(cast_shadow))
    if not collision:
        component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    if material is not None:
        component.set_material(0, material)
    return actor


def create_unlit_material(asset_path, color, gradient=False):
    existing = unreal.EditorAssetLibrary.load_asset(asset_path)
    if existing is not None:
        return existing, False

    package_path, asset_name = asset_path.rsplit("/", 1)
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name,
        package_path,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if material is None:
        raise RuntimeError("Unable to create material: {}".format(asset_path))

    material.set_editor_property("two_sided", True)
    material.set_editor_property(
        "shading_model",
        unreal.MaterialShadingModel.MSM_UNLIT,
    )

    if gradient:
        world_position = unreal.MaterialEditingLibrary.create_material_expression(
            material,
            unreal.MaterialExpressionWorldPosition,
            -900,
            0,
        )
        component_mask = unreal.MaterialEditingLibrary.create_material_expression(
            material,
            unreal.MaterialExpressionComponentMask,
            -700,
            0,
        )
        component_mask.set_editor_property("r", False)
        component_mask.set_editor_property("g", False)
        component_mask.set_editor_property("b", True)
        component_mask.set_editor_property("a", False)

        height_scale = unreal.MaterialEditingLibrary.create_material_expression(
            material,
            unreal.MaterialExpressionMultiply,
            -500,
            0,
        )
        height_scale.set_editor_property("const_b", 0.000285)

        height_bias = unreal.MaterialEditingLibrary.create_material_expression(
            material,
            unreal.MaterialExpressionAdd,
            -300,
            0,
        )
        height_bias.set_editor_property("const_b", 0.08)

        saturate = unreal.MaterialEditingLibrary.create_material_expression(
            material,
            unreal.MaterialExpressionSaturate,
            -100,
            0,
        )

        horizon = unreal.MaterialEditingLibrary.create_material_expression(
            material,
            unreal.MaterialExpressionConstant3Vector,
            -100,
            180,
        )
        horizon.set_editor_property(
            "constant",
            unreal.LinearColor(0.55, 0.72, 0.95, 1.0),
        )

        zenith = unreal.MaterialEditingLibrary.create_material_expression(
            material,
            unreal.MaterialExpressionConstant3Vector,
            -100,
            300,
        )
        zenith.set_editor_property(
            "constant",
            unreal.LinearColor(0.06, 0.18, 0.50, 1.0),
        )

        lerp = unreal.MaterialEditingLibrary.create_material_expression(
            material,
            unreal.MaterialExpressionLinearInterpolate,
            170,
            120,
        )

        unreal.MaterialEditingLibrary.connect_material_expressions(
            world_position,
            "",
            component_mask,
            "Input",
        )
        unreal.MaterialEditingLibrary.connect_material_expressions(
            component_mask,
            "",
            height_scale,
            "A",
        )
        unreal.MaterialEditingLibrary.connect_material_expressions(
            height_scale,
            "",
            height_bias,
            "A",
        )
        unreal.MaterialEditingLibrary.connect_material_expressions(
            height_bias,
            "",
            saturate,
            "Input",
        )
        unreal.MaterialEditingLibrary.connect_material_expressions(
            horizon,
            "",
            lerp,
            "A",
        )
        unreal.MaterialEditingLibrary.connect_material_expressions(
            zenith,
            "",
            lerp,
            "B",
        )
        unreal.MaterialEditingLibrary.connect_material_expressions(
            saturate,
            "",
            lerp,
            "Alpha",
        )
        unreal.MaterialEditingLibrary.connect_material_property(
            lerp,
            "",
            unreal.MaterialProperty.MP_EMISSIVE_COLOR,
        )
    else:
        emissive = unreal.MaterialEditingLibrary.create_material_expression(
            material,
            unreal.MaterialExpressionConstant3Vector,
            -200,
            0,
        )
        emissive.set_editor_property(
            "constant",
            unreal.LinearColor(float(color[0]), float(color[1]), float(color[2]), 1.0),
        )
        unreal.MaterialEditingLibrary.connect_material_property(
            emissive,
            "",
            unreal.MaterialProperty.MP_EMISSIVE_COLOR,
        )

    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    return material, True


def spawn_point_light(actor_subsystem, label, location, intensity, radius, folder):
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.PointLight,
        vec(*location),
        rot(),
    )
    if actor is None:
        raise RuntimeError("Unable to spawn point light: {}".format(label))
    actor.set_actor_label(label)
    actor.set_folder_path(folder)

    component = actor.point_light_component
    component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    component.set_editor_property("intensity_units", unreal.LightUnits.LUMENS)
    component.set_editor_property("intensity", float(intensity))
    component.set_editor_property("attenuation_radius", float(radius))
    component.set_editor_property("use_temperature", True)
    component.set_editor_property("temperature", 6300.0)
    component.set_editor_property("cast_shadows", False)
    component.set_editor_property("indirect_lighting_intensity", 0.0)
    component.set_editor_property("volumetric_scattering_intensity", 0.0)
    return actor


def spawn_window_fill(actor_subsystem):
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.SpotLight,
        vec(850.0, -1000.0, 175.0),
        rot(-12.0, 180.0, 0.0),
    )
    if actor is None:
        raise RuntimeError("Unable to spawn large-room window fill")
    actor.set_actor_label("WG_LargeRoom_WindowFill")
    actor.set_folder_path("WG Expansion/Large Room/Lights")

    component = actor.spot_light_component
    component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    component.set_editor_property("intensity_units", unreal.LightUnits.LUMENS)
    component.set_editor_property("intensity", 800.0)
    component.set_editor_property("attenuation_radius", 1000.0)
    component.set_editor_property("inner_cone_angle", 30.0)
    component.set_editor_property("outer_cone_angle", 60.0)
    component.set_editor_property("use_temperature", True)
    component.set_editor_property("temperature", 5900.0)
    component.set_editor_property("cast_shadows", False)
    component.set_editor_property("indirect_lighting_intensity", 0.0)
    component.set_editor_property("volumetric_scattering_intensity", 0.0)
    return actor


def configure_navigation(actor_subsystem):
    nav_bounds = get_actor_by_label(actor_subsystem, "NavBounds")
    if nav_bounds is None:
        return False
    nav_bounds.set_actor_location(vec(300.0, -400.0, 125.0), False, False)
    nav_bounds.set_actor_scale3d(vec(5.5, 10.0, 1.6))
    return True


def build():
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    editor_subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor_subsystem.get_editor_world()
    if world is None:
        raise RuntimeError("No editor world is open")
    if world.get_name() != "HospitalRoom":
        raise RuntimeError(
            "Expected HospitalRoom, but current world is {}".format(world.get_name())
        )

    asset_cache = {}
    created = []
    with unreal.ScopedEditorTransaction("Codex: Build corridor, large room, and morning sky"):
        removed = remove_previous_generated_actors(actor_subsystem)

        sky_material, sky_material_created = create_unlit_material(
            SKY_MATERIAL_PATH,
            (0.16, 0.42, 0.92),
            gradient=False,
        )
        sun_material, sun_material_created = create_unlit_material(
            SUN_MATERIAL_PATH,
            (4.0, 2.4, 0.8),
            gradient=False,
        )

        # Corridor: 2 m wide, 6 m long, aligned to the existing south doorway.
        for y in (-100, -300, -500):
            created.append(
                spawn_mesh(
                    actor_subsystem,
                    asset_cache,
                    FLOOR_MESH,
                    "WG_Corridor_Floor_X300_Y{}".format(y),
                    (300, y, -10),
                    folder="WG Expansion/Corridor/Floor",
                )
            )
            created.append(
                spawn_mesh(
                    actor_subsystem,
                    asset_cache,
                    CEILING_MESH,
                    "WG_Corridor_Ceiling_X300_Y{}".format(y),
                    (300, y, 250),
                    folder="WG Expansion/Corridor/Ceiling",
                )
            )
            for x, side in ((200, "West"), (400, "East")):
                created.append(
                    spawn_mesh(
                        actor_subsystem,
                        asset_cache,
                        WALL_MESH,
                        "WG_Corridor_Wall_{}_Y{}".format(side, y),
                        (x, y, 0),
                        rotation=rot(0, 90, 0),
                        folder="WG Expansion/Corridor/Walls",
                    )
                )

        created.append(
            spawn_mesh(
                actor_subsystem,
                asset_cache,
                DOORWAY_MESH,
                "WG_Corridor_LargeRoomDoorway",
                (300, -600, 0),
                rotation=rot(0, 180, 0),
                folder="WG Expansion/Corridor/Walls",
            )
        )

        for y in (-200, -400):
            created.append(
                spawn_mesh(
                    actor_subsystem,
                    asset_cache,
                    CEILING_LIGHT_MESH,
                    "WG_Corridor_CeilingLight_Y{}".format(y),
                    (300, y, 250),
                    folder="WG Expansion/Corridor/Lights",
                    collision=False,
                )
            )
        created.append(
            spawn_point_light(
                actor_subsystem,
                "WG_Corridor_Fill",
                (300, -300, 210),
                550,
                420,
                "WG Expansion/Corridor/Lights",
            )
        )

        # Large room: 10 m wide by 8 m deep.
        room_x = (-100, 100, 300, 500, 700)
        room_y = (-700, -900, -1100, -1300)
        for x in room_x:
            for y in room_y:
                created.append(
                    spawn_mesh(
                        actor_subsystem,
                        asset_cache,
                        FLOOR_MESH,
                        "WG_LargeRoom_Floor_X{}_Y{}".format(x, y),
                        (x, y, -10),
                        folder="WG Expansion/Large Room/Floor",
                    )
                )
                created.append(
                    spawn_mesh(
                        actor_subsystem,
                        asset_cache,
                        CEILING_MESH,
                        "WG_LargeRoom_Ceiling_X{}_Y{}".format(x, y),
                        (x, y, 250),
                        folder="WG Expansion/Large Room/Ceiling",
                    )
                )

        # North wall, leaving the corridor doorway open at X=300.
        for x in (-100, 100, 500, 700):
            created.append(
                spawn_mesh(
                    actor_subsystem,
                    asset_cache,
                    WALL_MESH,
                    "WG_LargeRoom_Wall_North_X{}".format(x),
                    (x, -600, 0),
                    rotation=rot(0, 180, 0),
                    folder="WG Expansion/Large Room/Walls",
                )
            )

        # South wall.
        for x in room_x:
            created.append(
                spawn_mesh(
                    actor_subsystem,
                    asset_cache,
                    WALL_MESH,
                    "WG_LargeRoom_Wall_South_X{}".format(x),
                    (x, -1400, 0),
                    folder="WG Expansion/Large Room/Walls",
                )
            )

        # West wall.
        for y in room_y:
            created.append(
                spawn_mesh(
                    actor_subsystem,
                    asset_cache,
                    WALL_MESH,
                    "WG_LargeRoom_Wall_West_Y{}".format(y),
                    (-200, y, 0),
                    rotation=rot(0, 90, 0),
                    folder="WG Expansion/Large Room/Walls",
                )
            )

        # East wall, with a full-height hospital window in the middle.
        for y in (-700, -900, -1100, -1300):
            mesh = WINDOW_MESH if y == -1100 else WALL_MESH
            label_part = "Window" if y == -1100 else "Wall"
            created.append(
                spawn_mesh(
                    actor_subsystem,
                    asset_cache,
                    mesh,
                    "WG_LargeRoom_{}_East_Y{}".format(label_part, y),
                    (800, y, 0),
                    rotation=rot(0, 90, 0),
                    folder="WG Expansion/Large Room/Walls",
                )
            )

        for x in (100, 500):
            for y in (-800, -1200):
                created.append(
                    spawn_mesh(
                        actor_subsystem,
                        asset_cache,
                        CEILING_LIGHT_MESH,
                        "WG_LargeRoom_CeilingLight_X{}_Y{}".format(x, y),
                        (x, y, 250),
                        folder="WG Expansion/Large Room/Lights",
                        collision=False,
                    )
                )

        created.append(
            spawn_point_light(
                actor_subsystem,
                "WG_LargeRoom_Fill_West",
                (100, -1000, 210),
                900,
                620,
                "WG Expansion/Large Room/Lights",
            )
        )
        created.append(
            spawn_point_light(
                actor_subsystem,
                "WG_LargeRoom_Fill_East",
                (500, -1000, 210),
                900,
                620,
                "WG Expansion/Large Room/Lights",
            )
        )
        created.append(spawn_window_fill(actor_subsystem))

        # Cheap, reliable mobile sky: an unlit two-sided gradient dome plus a
        # visible warm sun disc. The existing real DirectionalLight still casts
        # the room shadows.
        created.append(
            spawn_mesh(
                actor_subsystem,
                asset_cache,
                SPHERE_MESH,
                "WG_Sky_Dome",
                (300, -400, 0),
                scale=(100, 100, 100),
                folder="WG Expansion/Sky",
                collision=False,
                cast_shadow=False,
                material=sky_material,
            )
        )
        created.append(
            spawn_mesh(
                actor_subsystem,
                asset_cache,
                SPHERE_MESH,
                "WG_Sky_SunDisc",
                (4200, -1000, 3000),
                scale=(2.5, 2.5, 2.5),
                folder="WG Expansion/Sky",
                collision=False,
                cast_shadow=False,
                material=sun_material,
            )
        )

        # Keep the existing window backdrop, but give it the same brighter sky
        # material so there is no mismatch while the sky dome streams in.
        old_backdrop = get_actor_by_label(actor_subsystem, "ExteriorMorningBackdrop")
        if old_backdrop is not None:
            old_backdrop.static_mesh_component.set_material(0, sky_material)

        nav_updated = configure_navigation(actor_subsystem)

    try:
        unreal.SystemLibrary.execute_console_command(world, "RebuildNavigation")
    except Exception:
        pass

    unreal.EditorLevelLibrary.save_current_level()
    unreal.EditorAssetLibrary.save_asset(SKY_MATERIAL_PATH, only_if_is_dirty=False)
    unreal.EditorAssetLibrary.save_asset(SUN_MATERIAL_PATH, only_if_is_dirty=False)

    return {
        "success": True,
        "world": world.get_name(),
        "removed_previous": len(removed),
        "created_actors": len(created),
        "nav_bounds_updated": nav_updated,
        "sky_material_created": sky_material_created,
        "sun_material_created": sun_material_created,
        "corridor_size_cm": [200, 600, 250],
        "large_room_size_cm": [1000, 800, 250],
    }


try:
    print(json.dumps(build()))
except Exception as exc:
    print(
        json.dumps(
            {
                "success": False,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
    )
