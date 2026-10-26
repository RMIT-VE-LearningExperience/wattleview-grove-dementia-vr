import json
import traceback

import unreal


MAP_PATH = "/Game/Maps/HospitalRoom"
MASTER_PATH = "/Game/HospitalMaterials/M_Hospital_ORM"
WALLS_INSTANCE_PATH = "/Game/HospitalMaterials/MI_Walls_1"
FLOOR_MASTER_PATH = "/Game/HospitalMaterials/M_Hospital_RM"
FLOOR_INSTANCE_PATH = "/Game/HospitalMaterials/MI_Floors_1"
NORMAL_TEXTURE_PATH = (
    "/Game/Fab/Modular_3D_hospital_environment/Walls/"
    "hospital_Walls_1_Normal"
)
ORM_TEXTURE_PATH = (
    "/Game/Fab/Modular_3D_hospital_environment/Walls/"
    "hospital_Walls_1_OcclusionRoughnessMetallic"
)

EXPANSION_LIGHT_LABELS = (
    "WG_Corridor_Fill",
    "WG_LargeRoom_Fill_West",
    "WG_LargeRoom_Fill_East",
    "WG_LargeRoom_WindowFill",
)


def vec(x, y, z):
    return unreal.Vector(float(x), float(y), float(z))


def rot(pitch=0.0, yaw=0.0, roll=0.0):
    value = unreal.Rotator()
    value.pitch = float(pitch)
    value.yaw = float(yaw)
    value.roll = float(roll)
    return value


def load_required(path):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None:
        raise RuntimeError("Unable to load {}".format(path))
    return asset


def material_parameter_expressions(material):
    prefix = material.get_path_name()
    result = {}
    for expression in unreal.ObjectIterator(
        unreal.MaterialExpressionTextureSampleParameter2D
    ):
        if not expression.get_path_name().startswith(prefix):
            continue
        parameter_name = str(
            expression.get_editor_property("parameter_name")
        )
        result.setdefault(parameter_name, []).append(expression)
    return result


def fix_hospital_material():
    master = load_required(MASTER_PATH)
    walls_instance = load_required(WALLS_INSTANCE_PATH)
    normal_texture = load_required(NORMAL_TEXTURE_PATH)
    orm_texture = load_required(ORM_TEXTURE_PATH)

    expressions = material_parameter_expressions(master)
    for parameter_name in ("Normal", "ORM"):
        count = len(expressions.get(parameter_name, []))
        if count != 1:
            raise RuntimeError(
                "Expected one {} parameter expression, found {}".format(
                    parameter_name,
                    count,
                )
            )

    normal_expression = expressions["Normal"][0]
    orm_expression = expressions["ORM"][0]

    old_defaults = {
        "Normal": normal_expression.get_editor_property(
            "texture"
        ).get_path_name(),
        "ORM": orm_expression.get_editor_property("texture").get_path_name(),
    }

    master.modify()
    normal_expression.modify()
    orm_expression.modify()
    orm_texture.modify()

    # Match each parameter's default texture to its sampler. The previous
    # generic sRGB DefaultTexture made the master fail shader compilation.
    normal_expression.set_editor_property("texture", normal_texture)
    orm_texture.set_editor_property("srgb", False)
    orm_texture.set_editor_property(
        "compression_settings",
        unreal.TextureCompressionSettings.TC_MASKS,
    )
    orm_expression.set_editor_property(
        "sampler_type",
        unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,
    )
    orm_expression.set_editor_property("texture", orm_texture)

    unreal.MaterialEditingLibrary.recompile_material(master)
    unreal.MaterialEditingLibrary.update_material_instance(walls_instance)

    for asset in (orm_texture, master, walls_instance):
        if not unreal.EditorAssetLibrary.save_loaded_asset(
            asset,
            only_if_is_dirty=False,
        ):
            raise RuntimeError("Unable to save {}".format(asset.get_path_name()))

    return {
        "master": MASTER_PATH,
        "old_defaults": old_defaults,
        "normal_default": normal_texture.get_path_name(),
        "orm_default": orm_texture.get_path_name(),
        "orm_srgb": bool(orm_texture.get_editor_property("srgb")),
        "orm_compression": str(
            orm_texture.get_editor_property("compression_settings")
        ),
        "orm_sampler": str(
            orm_expression.get_editor_property("sampler_type")
        ),
    }


def fix_floor_material():
    master = load_required(FLOOR_MASTER_PATH)
    floor_instance = load_required(FLOOR_INSTANCE_PATH)
    expressions = material_parameter_expressions(master)
    parameter_names = ("BaseColor", "Normal", "Roughness", "Metallic")

    for parameter_name in parameter_names:
        count = len(expressions.get(parameter_name, []))
        if count != 1:
            raise RuntimeError(
                "Expected one floor {} parameter expression, found {}".format(
                    parameter_name,
                    count,
                )
            )

    textures = {}
    for parameter_name in parameter_names:
        texture = (
            unreal.MaterialEditingLibrary
            .get_material_instance_texture_parameter_value(
                floor_instance,
                parameter_name,
            )
        )
        if texture is None:
            raise RuntimeError(
                "MI_Floors_1 has no {} texture".format(parameter_name)
            )
        textures[parameter_name] = texture

    old_defaults = {
        parameter_name: expressions[parameter_name][0]
        .get_editor_property("texture")
        .get_path_name()
        for parameter_name in parameter_names
    }

    master.modify()
    floor_instance.modify()
    for parameter_name in parameter_names:
        expressions[parameter_name][0].modify()

    # The RM master was authored with a Color default texture on Normal,
    # Roughness, and Metallic samplers. Give every parameter a compatible
    # real default and import scalar maps as linear grayscale data.
    textures["Roughness"].modify()
    textures["Metallic"].modify()
    for parameter_name in ("Roughness", "Metallic"):
        texture = textures[parameter_name]
        texture.set_editor_property("srgb", False)
        texture.set_editor_property(
            "compression_settings",
            unreal.TextureCompressionSettings.TC_GRAYSCALE,
        )

    sampler_types = {
        "BaseColor": unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
        "Normal": unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
        "Roughness": (
            unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE
        ),
        "Metallic": (
            unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE
        ),
    }
    for parameter_name in parameter_names:
        expression = expressions[parameter_name][0]
        expression.set_editor_property(
            "sampler_type",
            sampler_types[parameter_name],
        )
        expression.set_editor_property(
            "texture",
            textures[parameter_name],
        )

    unreal.MaterialEditingLibrary.recompile_material(master)
    unreal.MaterialEditingLibrary.update_material_instance(floor_instance)

    assets_to_save = [
        textures["Roughness"],
        textures["Metallic"],
        master,
        floor_instance,
    ]
    for asset in assets_to_save:
        if not unreal.EditorAssetLibrary.save_loaded_asset(
            asset,
            only_if_is_dirty=False,
        ):
            raise RuntimeError("Unable to save {}".format(asset.get_path_name()))

    return {
        "master": FLOOR_MASTER_PATH,
        "old_defaults": old_defaults,
        "defaults": {
            parameter_name: textures[parameter_name].get_path_name()
            for parameter_name in parameter_names
        },
        "roughness_srgb": bool(
            textures["Roughness"].get_editor_property("srgb")
        ),
        "metallic_srgb": bool(
            textures["Metallic"].get_editor_property("srgb")
        ),
        "roughness_compression": str(
            textures["Roughness"].get_editor_property(
                "compression_settings"
            )
        ),
        "metallic_compression": str(
            textures["Metallic"].get_editor_property(
                "compression_settings"
            )
        ),
    }


def configure_static_light(component, intensity, radius, temperature):
    component.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
    component.set_editor_property("intensity_units", unreal.LightUnits.LUMENS)
    component.set_editor_property("intensity", float(intensity))
    component.set_editor_property("attenuation_radius", float(radius))
    component.set_editor_property("use_temperature", True)
    component.set_editor_property("temperature", float(temperature))
    component.set_editor_property("cast_shadows", True)
    component.set_editor_property("cast_static_shadows", True)
    component.set_editor_property("cast_dynamic_shadows", False)
    component.set_editor_property("volumetric_scattering_intensity", 0.0)


def spawn_rect_light(
    actor_subsystem,
    label,
    location,
    intensity,
    indirect_intensity,
    radius,
    source_width,
    source_height,
    folder,
):
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.RectLight,
        vec(*location),
        rot(-90.0, 0.0, 0.0),
    )
    if actor is None:
        raise RuntimeError("Unable to spawn {}".format(label))

    actor.set_actor_label(label)
    actor.set_folder_path(folder)
    component = actor.rect_light_component
    configure_static_light(component, intensity, radius, 6200.0)
    component.set_editor_property("source_width", float(source_width))
    component.set_editor_property("source_height", float(source_height))
    component.set_editor_property(
        "indirect_lighting_intensity",
        float(indirect_intensity),
    )
    return actor


def spawn_window_fill(actor_subsystem):
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.SpotLight,
        vec(850.0, -1000.0, 175.0),
        rot(-12.0, 180.0, 0.0),
    )
    if actor is None:
        raise RuntimeError("Unable to spawn WG_LargeRoom_WindowFill")

    actor.set_actor_label("WG_LargeRoom_WindowFill")
    actor.set_folder_path("WG Expansion/Large Room/Lights")
    component = actor.spot_light_component
    configure_static_light(component, 400.0, 1000.0, 5700.0)
    component.set_editor_property("inner_cone_angle", 25.0)
    component.set_editor_property("outer_cone_angle", 65.0)
    component.set_editor_property("source_radius", 90.0)
    component.set_editor_property("soft_source_radius", 150.0)
    component.set_editor_property("indirect_lighting_intensity", 0.7)
    return actor


def replace_expansion_lights(actor_subsystem):
    existing = {}
    for actor in actor_subsystem.get_all_level_actors():
        label = actor.get_actor_label()
        if label in EXPANSION_LIGHT_LABELS:
            existing.setdefault(label, []).append(actor)

    bad_counts = {
        label: len(existing.get(label, []))
        for label in EXPANSION_LIGHT_LABELS
        if len(existing.get(label, [])) != 1
    }
    if bad_counts:
        raise RuntimeError(
            "Unexpected expansion light counts: {}".format(bad_counts)
        )

    for label in EXPANSION_LIGHT_LABELS:
        if not actor_subsystem.destroy_actor(existing[label][0]):
            raise RuntimeError("Unable to remove {}".format(label))

    created = [
        spawn_rect_light(
            actor_subsystem,
            "WG_Corridor_Fill",
            (300.0, -300.0, 235.0),
            350.0,
            0.6,
            450.0,
            180.0,
            80.0,
            "WG Expansion/Corridor/Lights",
        ),
        spawn_rect_light(
            actor_subsystem,
            "WG_LargeRoom_Fill_West",
            (100.0, -1000.0, 235.0),
            450.0,
            0.6,
            650.0,
            260.0,
            120.0,
            "WG Expansion/Large Room/Lights",
        ),
        spawn_rect_light(
            actor_subsystem,
            "WG_LargeRoom_Fill_East",
            (500.0, -1000.0, 235.0),
            450.0,
            0.6,
            650.0,
            260.0,
            120.0,
            "WG Expansion/Large Room/Lights",
        ),
        spawn_window_fill(actor_subsystem),
    ]

    return [
        {
            "label": actor.get_actor_label(),
            "class": actor.get_class().get_name(),
            "location": [
                round(float(actor.get_actor_location().x), 3),
                round(float(actor.get_actor_location().y), 3),
                round(float(actor.get_actor_location().z), 3),
            ],
        }
        for actor in created
    ]


def run():
    world = unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
    if world is None:
        raise RuntimeError("Unable to load {}".format(MAP_PATH))

    actor_subsystem = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    )
    with unreal.ScopedEditorTransaction(
        "Codex: Soften expansion lights and fix hospital material"
    ):
        material_result = {
            "walls": fix_hospital_material(),
            "floor": fix_floor_material(),
        }
        light_result = replace_expansion_lights(actor_subsystem)

    if not unreal.EditorLevelLibrary.save_current_level():
        raise RuntimeError("Unable to save {}".format(MAP_PATH))

    print(
        "CODEX_EXPANSION_REFINEMENT="
        + json.dumps(
            {
                "success": True,
                "map": world.get_path_name(),
                "material": material_result,
                "lights": light_result,
                "lighting_rebuild_required": True,
            },
            sort_keys=True,
        )
    )


try:
    run()
except Exception as exc:
    print(
        "CODEX_EXPANSION_REFINEMENT="
        + json.dumps(
            {
                "success": False,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
            sort_keys=True,
        )
    )
    raise
