"""Soft contact ("blob") shadows under the characters, instead of dynamic shadows.

On the PICO 4 Ultra the sun's one movable-shadow cascade cost about 7 ms of GPU per frame
(measured with ShowFlag.DynamicShadows on the device, story paused): every MetaHuman component
re-renders into the shadow map and every room pixel samples it. build_lighting.py now sets the
cascade distance to 0, so the baked room keeps its static shadows and the characters get a soft
dark disc at their feet instead (unlit, modulate blend, a few hundred pixels).

  M_BlobShadow       unlit, BLEND_MODULATE: 1 at the rim falling to Darkness at the centre.
  BlobShadow_<label> Engine plane attached to each character actor, 1 cm above its root (the
                     floor point between the feet), so it follows the blocking in LS_Story.

Run after build_characters.py (it respawns the characters) and before build_story_sequence.py:
  exec(open(r"<this file>").read())
"""
import unreal

MAT_PATH = "/Game/Wattleview/Materials/M_BlobShadow"
PLANE = "/Engine/BasicShapes/Plane.Plane"
# label -> disc diameter (cm). Enzo shares David's blocking and is attached to him, so David's
# disc serves both.
CHARACTERS = {"Maria_StandIn": 60.0, "David_StandIn": 70.0, "Gardener_StandIn": 70.0}
DARKNESS = 0.45       # multiplier at the centre of the disc (1 = no darkening)
LIFT_CM = 1.0         # above the root: clears the 0.6 cm rug and avoids z-fighting with the floor

eas = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)


def log(msg):
    unreal.log("[BlobShadow] " + msg)


def build_material():
    if eas.does_asset_exist(MAT_PATH):
        mat = unreal.load_asset(MAT_PATH)
        mel.delete_all_material_expressions(mat)
    else:
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "M_BlobShadow", "/Game/Wattleview/Materials", unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MODULATE)
    uv = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -800, 0)
    centre = mel.create_material_expression(mat, unreal.MaterialExpressionConstant2Vector, -800, 120)
    centre.set_editor_property("r", 0.5)
    centre.set_editor_property("g", 0.5)
    dist = mel.create_material_expression(mat, unreal.MaterialExpressionDistance, -600, 60)
    mel.connect_material_expressions(uv, "", dist, "A")
    mel.connect_material_expressions(centre, "", dist, "B")
    # 0 at the centre -> 1 at the rim (radius 0.5), eased so the edge has no visible ring
    two = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -600, 180)
    two.set_editor_property("r", 2.0)
    rim = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -450, 100)
    mel.connect_material_expressions(dist, "", rim, "A")
    mel.connect_material_expressions(two, "", rim, "B")
    sat = mel.create_material_expression(mat, unreal.MaterialExpressionSaturate, -320, 100)
    mel.connect_material_expressions(rim, "", sat, "")
    ease = mel.create_material_expression(mat, unreal.MaterialExpressionSmoothStep, -200, 100)
    mel.connect_material_expressions(sat, "", ease, "Value")
    ease.set_editor_property("const_min", 0.0)
    ease.set_editor_property("const_max", 1.0)
    dark = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -200, 220)
    dark.set_editor_property("r", DARKNESS)
    one = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -200, 300)
    one.set_editor_property("r", 1.0)
    lerp = mel.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -50, 180)
    mel.connect_material_expressions(dark, "", lerp, "A")
    mel.connect_material_expressions(one, "", lerp, "B")
    mel.connect_material_expressions(ease, "", lerp, "Alpha")
    mel.connect_material_property(lerp, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(mat)
    eas.save_loaded_asset(mat)
    return mat


def place(mat):
    by_label = {a.get_actor_label(): a for a in acts.get_all_level_actors()}
    for a in list(by_label.values()):
        if a.get_actor_label().startswith("BlobShadow_"):
            acts.destroy_actor(a)
    n = 0
    for label, diameter in CHARACTERS.items():
        owner = by_label.get(label)
        if owner is None:
            log(f"{label} missing; no blob")
            continue
        loc = owner.get_actor_location()
        blob = acts.spawn_actor_from_object(unreal.load_asset(PLANE), unreal.Vector(loc.x, loc.y, loc.z + LIFT_CM),
                                            unreal.Rotator(0, 0, 0))
        blob.set_actor_label("BlobShadow_" + label.split("_")[0])
        blob.set_folder_path("Characters")
        c = blob.static_mesh_component
        c.set_mobility(unreal.ComponentMobility.MOVABLE)
        c.set_material(0, mat)
        c.set_cast_shadow(False)
        c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        s = diameter / 100.0                       # the engine plane is 100 cm across
        blob.set_actor_scale3d(unreal.Vector(s, s, 1.0))
        blob.attach_to_actor(owner, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                             unreal.AttachmentRule.KEEP_WORLD, False)
        n += 1
    les.save_current_level()
    log(f"{n} blob shadows placed and saved")


place(build_material())
