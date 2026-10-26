import json
import traceback

import unreal


MASTER_PATHS = (
    "/Game/HospitalMaterials/M_Hospital_ORM",
    "/Game/HospitalMaterials/M_Hospital_RM",
)
INSTANCE_PATHS = (
    "/Game/HospitalMaterials/MI_Walls_1",
    "/Game/HospitalMaterials/MI_Floors_1",
)
CANDIDATE_DEFAULTS = (
    "/Engine/EngineMaterials/DefaultNormal",
    "/Engine/EngineMaterials/DefaultDiffuse_TC_Masks",
    "/Engine/EngineResources/Gray",
    "/Engine/EngineResources/WhiteSquareTexture",
)


def serialise_texture(texture):
    if texture is None:
        return None
    result = {"path": texture.get_path_name()}
    for property_name in ("srgb", "compression_settings", "lod_group"):
        try:
            result[property_name] = str(
                texture.get_editor_property(property_name)
            )
        except Exception:
            pass
    return result


def report_expression(expression):
    result = {
        "name": expression.get_name(),
        "class": expression.get_class().get_name(),
    }
    for property_name in (
        "parameter_name",
        "sampler_type",
        "texture",
    ):
        try:
            value = expression.get_editor_property(property_name)
        except Exception:
            continue
        if property_name == "texture":
            result[property_name] = serialise_texture(value)
        else:
            result[property_name] = str(value)
    return result


def run():
    materials = []
    for master_path in MASTER_PATHS:
        master = unreal.EditorAssetLibrary.load_asset(master_path)
        if master is None:
            raise RuntimeError("Unable to load {}".format(master_path))

        expressions = []
        master_prefix = master.get_path_name()
        for expression in unreal.ObjectIterator(unreal.MaterialExpression):
            if expression.get_path_name().startswith(master_prefix):
                expressions.append(report_expression(expression))
        materials.append(
            {
                "path": master_path,
                "expressions": expressions,
            }
        )

    instances = []
    for path in INSTANCE_PATHS:
        instance = unreal.EditorAssetLibrary.load_asset(path)
        if instance is None:
            continue
        textures = {}
        for parameter_name in unreal.MaterialEditingLibrary.get_texture_parameter_names(
            instance
        ):
            value = unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(
                instance,
                parameter_name,
            )
            textures[str(parameter_name)] = serialise_texture(value)
        instances.append({"path": path, "textures": textures})

    defaults = {}
    for path in CANDIDATE_DEFAULTS:
        defaults[path] = serialise_texture(
            unreal.EditorAssetLibrary.load_asset(path)
        )

    print(
        "CODEX_HOSPITAL_MATERIAL_DIAG="
        + json.dumps(
            {
                "success": True,
                "materials": materials,
                "instances": instances,
                "candidate_defaults": defaults,
            },
            sort_keys=True,
        )
    )


try:
    run()
except Exception as exc:
    print(
        "CODEX_HOSPITAL_MATERIAL_DIAG="
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
