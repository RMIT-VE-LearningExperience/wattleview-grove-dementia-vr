"""Natural daylight for L_ResidentRoom: baked, mobile-friendly, high-key.

Target look (reference from Lawrence, 2026-10-26): bright airy room, sun streaming through the
window onto the floor, soft bounce fill everywhere, warm-white walls, gentle shadows.

  * Static sun (morning, from the north-east through the north window) -> crisp sun patch.
  * Static sky light from a daylight cubemap + a Lightmass portal on the window -> soft fill.
  * Lightmass importance volume around the room and near garden; 4 indirect bounces.
  * Per-surface lightmap resolution so the sun patch has clean edges.
  * Sphere reflection capture for mobile reflections.
  * Clear blue gradient sky (pale horizon, deeper zenith), unlit.
  * Palette shifted toward the reference (near-white walls, light carpet, jute rug).
  * Production bake (build_light_maps) unless BAKE = False.

Mobile LDR has no exposure: final pixel values clamp at 1. Values here aim for walls ~0.7-0.85
and a near-white sun patch; confirm on the headset, the desktop preview is not truthful.

Run in the open editor AFTER build_resident_room.py (and before or after the story scripts):
  exec(open(r"<this file>").read())
"""
import unreal

MAP_PATH = "/Game/Wattleview/Maps/L_ResidentRoom"
MAT_DIR = "/Game/Wattleview/Materials/Blockout"
BAKE = globals().get("BAKE", True)

acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary

ROOM_X, ROOM_Y, ROOM_H = 500.0, 450.0, 270.0

# Palette toward the reference: warm whites, light timber, jute; Maria's pinks kept.
PALETTE = {
    "Wall": (0.86, 0.83, 0.77),
    "Ceiling": (0.90, 0.89, 0.86),
    "Carpet": (0.52, 0.48, 0.43),
    "Rug": (0.58, 0.44, 0.28),
    "Linen": (0.92, 0.91, 0.88),
    "White": (0.92, 0.92, 0.90),
    "Timber": (0.66, 0.50, 0.33),
    "Curtain": (0.90, 0.88, 0.84),
}

# Lightmap resolution by actor label prefix (first match wins); everything else 32.
LIGHTMAP_RES = [
    ("Floor", 512), ("Ceiling", 256), ("Wall_", 256), ("Rug", 128), ("Bed_", 128),
    ("Wardrobe", 128), ("Table_Top", 64), ("Recliner", 64), ("Curtain", 64),
    ("Garden_Ground", 128),
]


def log(msg):
    unreal.log("[Lighting] " + msg)


def ensure_level():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None or world.get_path_name().split(".")[0] != MAP_PATH:
        les.load_level(MAP_PATH)
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def remove(labels_or_classes):
    for a in acts.get_all_level_actors():
        if a.get_actor_label() in labels_or_classes or type(a) in labels_or_classes:
            acts.destroy_actor(a)


def recolour():
    for key, rgb in PALETTE.items():
        path = f"{MAT_DIR}/MI_BO_{key}"
        if eas.does_asset_exist(path):
            mi = unreal.load_asset(path)
            mel.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(*rgb, 1.0))
            eas.save_loaded_asset(mi)
    log("palette updated")


def set_lightmaps():
    n = 0
    for a in acts.get_all_level_actors():
        if not isinstance(a, unreal.StaticMeshActor):
            continue
        comp = a.static_mesh_component
        if comp.mobility != unreal.ComponentMobility.STATIC:
            continue
        label = a.get_actor_label()
        res = next((r for prefix, r in LIGHTMAP_RES if label.startswith(prefix)), 32)
        comp.set_editor_property("override_light_map_res", True)
        comp.set_editor_property("overridden_light_map_res", res)
        n += 1
    log(f"lightmap resolution set on {n} static meshes")


def sky_gradient():
    """Clear blue sky: pale near the horizon, deeper blue overhead (unlit, mobile-safe)."""
    path = "/Game/Wattleview/Materials/M_SkyGradient"
    if eas.does_asset_exist(path):
        mat = unreal.load_asset(path)
        mel.delete_all_material_expressions(mat)
    else:
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "M_SkyGradient", "/Game/Wattleview/Materials", unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    wp = mel.create_material_expression(mat, unreal.MaterialExpressionWorldPosition, -900, 0)
    mask = mel.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -750, 0)
    mask.set_editor_property("r", False)
    mask.set_editor_property("g", False)
    mask.set_editor_property("b", True)
    mel.connect_material_expressions(wp, "", mask, "")
    div = mel.create_material_expression(mat, unreal.MaterialExpressionDivide, -600, 0)
    mel.connect_material_expressions(mask, "", div, "A")
    height = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -750, 120)
    height.set_editor_property("r", 1800.0)
    mel.connect_material_expressions(height, "", div, "B")
    sat = mel.create_material_expression(mat, unreal.MaterialExpressionSaturate, -450, 0)
    mel.connect_material_expressions(div, "", sat, "")
    horizon = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -450, 150)
    horizon.set_editor_property("constant", unreal.LinearColor(0.62, 0.78, 0.95, 1))
    zenith = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -450, 280)
    zenith.set_editor_property("constant", unreal.LinearColor(0.16, 0.42, 0.88, 1))
    lerp = mel.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -250, 100)
    mel.connect_material_expressions(horizon, "", lerp, "A")
    mel.connect_material_expressions(zenith, "", lerp, "B")
    mel.connect_material_expressions(sat, "", lerp, "Alpha")
    mel.connect_material_property(lerp, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(mat)
    eas.save_loaded_asset(mat)
    n = 0
    for a in acts.get_all_level_actors():
        if a.get_actor_label().startswith("Sky_"):
            a.static_mesh_component.set_material(0, mat)
            n += 1
    log(f"sky gradient applied to {n} sky panels")


def spawn(cls, label, loc, rot=(0.0, 0.0, 0.0), folder="Lighting"):
    a = acts.spawn_actor_from_class(cls, unreal.Vector(*loc), unreal.Rotator(*rot))
    a.set_actor_label(label)
    a.set_folder_path(folder)
    return a


def build():
    world = ensure_level()
    recolour()
    sky_gradient()

    remove({"Sun_Morning", "SkyLight", "RoomFill", "WindowPortal", "LightmassVolume",
            "RoomReflection", "PendantWarm"})

    # Sun: morning light from the north-east, through the north window, down onto the floor.
    sun = spawn(unreal.DirectionalLight, "Sun_Morning", (ROOM_X + 200, 225, 400), (0.0, -38.0, 215.0))
    lc = sun.light_component
    lc.set_mobility(unreal.ComponentMobility.STATIC)
    lc.set_intensity(2.3)
    lc.set_light_color(unreal.LinearColor(1.0, 0.92, 0.80, 1.0))
    lc.set_editor_property("light_source_angle", 0.7)          # defined but soft sun-patch edges
    lms = lc.get_editor_property("lightmass_settings")
    lms.set_editor_property("light_source_angle", 0.7)
    lms.set_editor_property("indirect_lighting_saturation", 1.0)
    lc.set_editor_property("lightmass_settings", lms)

    # Sky: daylight cubemap, static so it is baked with bounce.
    sky = spawn(unreal.SkyLight, "SkyLight", (250, 225, 200))
    slc = sky.light_component
    slc.set_mobility(unreal.ComponentMobility.STATIC)
    slc.set_editor_property("source_type", unreal.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
    slc.set_editor_property("cubemap", unreal.load_asset(
        "/Engine/MapTemplates/Sky/DaylightAmbientCubemap.DaylightAmbientCubemap"))
    slc.set_intensity(1.1)

    # Portal over the window opening (Y 100..350, Z 80..220) focuses sky light into the room.
    portal = spawn(unreal.LightmassPortal, "WindowPortal", (ROOM_X + 7, 225, 150))
    portal.set_actor_scale3d(unreal.Vector(0.1, 2.5, 1.4))

    # Soft warm pendant (the reference's woven shade), low, static, adds gentle fill.
    pend = spawn(unreal.PointLight, "PendantWarm", (250, 225, 235))
    plc = pend.light_component
    plc.set_mobility(unreal.ComponentMobility.STATIC)
    plc.set_intensity(8.0)
    plc.set_attenuation_radius(450.0)
    plc.set_light_color(unreal.LinearColor(1.0, 0.85, 0.65, 1.0))
    plc.set_editor_property("source_radius", 20.0)

    # Importance volume: room plus the garden strip seen through the window.
    vol = spawn(unreal.LightmassImportanceVolume, "LightmassVolume", (ROOM_X / 2 + 150, ROOM_Y / 2, 140))
    vol.set_actor_scale3d(unreal.Vector(5.5, 4.0, 1.8))   # default brush is 200 cm

    # Reflection capture for the room.
    refl = spawn(unreal.SphereReflectionCapture, "RoomReflection", (250, 225, 140))
    refl.capture_component.set_editor_property("influence_radius", 450.0)

    # World Lightmass settings: more bounces, finer static lighting for a soft high-key look.
    ws = world.get_world_settings()
    lm = ws.get_editor_property("lightmass_settings")
    lm.set_editor_property("num_indirect_lighting_bounces", 4)
    lm.set_editor_property("num_sky_lighting_bounces", 2)
    lm.set_editor_property("static_lighting_level_scale", 0.5)
    lm.set_editor_property("indirect_lighting_quality", 2.0)
    lm.set_editor_property("indirect_lighting_smoothness", 1.2)
    lm.set_editor_property("environment_color", unreal.Color(0, 0, 0, 255))
    ws.set_editor_property("lightmass_settings", lm)

    set_lightmaps()
    les.save_current_level()
    log("lights placed and saved")

    if BAKE:
        log("starting Production light bake")
        les.build_light_maps(unreal.LightingBuildQuality.QUALITY_PRODUCTION, True)
        les.save_current_level()
        log("bake finished and saved")


build()
