import json
import traceback

import unreal


SKY_MATERIAL_PATH = "/Game/HospitalPack/Materials/M_MorningSkyDome"
SUN_MATERIAL_PATH = "/Game/HospitalPack/Materials/M_MorningSunDisc"


def find_named_constant(material, description):
    material_object_path = material.get_path_name()
    for obj in unreal.ObjectIterator():
        if not isinstance(obj, unreal.MaterialExpressionConstant3Vector):
            continue
        if not obj.get_path_name().startswith(material_object_path):
            continue
        if obj.get_editor_property("desc") == description:
            return obj
    return None


def force_simple_emissive(material_path, description, color):
    material = unreal.EditorAssetLibrary.load_asset(material_path)
    if material is None:
        raise RuntimeError("Material not found: {}".format(material_path))

    material.set_editor_property("two_sided", True)
    material.set_editor_property(
        "shading_model",
        unreal.MaterialShadingModel.MSM_UNLIT,
    )
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)

    expression = find_named_constant(material, description)
    created = expression is None
    if expression is None:
        expression = unreal.MaterialEditingLibrary.create_material_expression(
            material,
            unreal.MaterialExpressionConstant3Vector,
            430,
            0,
        )
        expression.set_editor_property("desc", description)

    expression.set_editor_property(
        "constant",
        unreal.LinearColor(
            float(color[0]),
            float(color[1]),
            float(color[2]),
            1.0,
        ),
    )
    connected = unreal.MaterialEditingLibrary.connect_material_property(
        expression,
        "",
        unreal.MaterialProperty.MP_EMISSIVE_COLOR,
    )
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)

    return {
        "path": material_path,
        "created_output": created,
        "connected": bool(connected),
        "two_sided": bool(material.get_editor_property("two_sided")),
        "shading_model": str(material.get_editor_property("shading_model")),
        "blend_mode": str(material.get_editor_property("blend_mode")),
        "output_expression": expression.get_name(),
    }


try:
    sky = force_simple_emissive(
        SKY_MATERIAL_PATH,
        "CodexSkyOutput",
        (0.16, 0.42, 0.92),
    )
    sun = force_simple_emissive(
        SUN_MATERIAL_PATH,
        "CodexSunOutput",
        (4.0, 2.2, 0.65),
    )
    print(json.dumps({"success": True, "sky": sky, "sun": sun}))
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
