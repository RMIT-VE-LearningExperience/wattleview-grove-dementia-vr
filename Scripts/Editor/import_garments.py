"""Import the Blender garments for the MetaHumans and dress the characters in the level.

Inputs: SourceArt/Characters/Garments/<Name>/SKM_<Name>_Outfit.fbx (skinned to metahuman_base_skel).
Outputs: /Game/Wattleview/Characters/Garments/<Name>/SKM_<Name>_Outfit and MI_Garment_<slot>.

Dressing: each MetaHuman Blueprint already has an outfit skeletal mesh component (Epic's default
T-shirt and shorts, mesh "<Name>_Outfits") that follows the body. The level instance's component
gets the garment instead, so re-assembling a character in MetaHuman Creator does not lose it
(rerun this script after build_characters.py).

Run headless or in the editor after build_characters.py.
"""
import os

import unreal

PROJECT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SRC = os.path.join(PROJECT, "SourceArt", "Characters", "Garments")
DST = "/Game/Wattleview/Characters/Garments"
MAT_DIR = "/Game/Wattleview/Characters/Garments/Materials"
SKELETON = "/Game/MetaHumans/Common/Female/Medium/NormalWeight/Body/metahuman_base_skel"
TEX = "/Game/Wattleview/Environment/Textures"
MASTER = "/Game/Wattleview/Environment/Materials/M_RoomMaster"
TWO_SIDED = {"M_Skirt", "M_Cardigan"}
# Per-character remaps: the FBX slot names are shared; these pick a different instance.
REMAP = {"David": {"M_Shoes": "M_ShoesBlack"}, "Enzo": {"M_Trousers": "M_TrousersBrown"}}
# label of the actor in L_ResidentRoom -> garment name
WEARERS = {"David_StandIn": "David", "Maria_StandIn": "Maria", "Enzo_Overlay": "Enzo"}

# slot -> (texture id or None, mode, tint, strength/lift, tiling, roughness)
SLOTS = {
    "M_PoloShirt":    ("cotton_jersey", "detail", (0.035, 0.06, 0.14), 0.25, 6.0, 0.85),
    "M_Trousers":     (None, None, (0.07, 0.07, 0.075), 0.0, 1.0, 0.8),
    "M_TrousersBrown": (None, None, (0.16, 0.10, 0.06), 0.0, 1.0, 0.85),
    "M_Belt":         ("brown_leather", "colour", (1.2, 1.1, 1.0), 0.0, 3.0, 0.5),
    "M_Shoes":        ("brown_leather", "colour", (0.45, 0.42, 0.40), 0.0, 3.0, 0.45),
    "M_ShoesBlack":   (None, None, (0.02, 0.02, 0.02), 0.0, 1.0, 0.35),
    "M_Badge":        (None, None, (0.88, 0.88, 0.86), 0.0, 1.0, 0.4),
    "M_Cardigan":     ("wool_boucle", "detail", (0.80, 0.74, 0.62), 0.6, 4.0, 0.95),
    "M_Blouse":       ("floral_jacquard", "detail", (0.85, 0.70, 0.75), 0.8, 5.0, 0.8),
    "M_Skirt":        (None, None, (0.05, 0.06, 0.13), 0.0, 1.0, 0.85),
    "M_FlannelShirt": ("wool_boucle", "colour", (1.0, 0.75, 0.70), 0.0, 3.0, 0.9),
}

eas = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def log(msg):
    unreal.log("[Garments] " + str(msg))


def tex(tid, suffix):
    path = f"{TEX}/{tid}/T_{tid}_{suffix}"
    return unreal.load_asset(path) if eas.does_asset_exist(path) else None


def ensure_texture(tid):
    """Import a Poly Haven set that the room import did not need (e.g. brown_leather)."""
    if tex(tid, "D"):
        return
    folder = os.path.join(PROJECT, "SourceArt", "Textures", tid)
    for key, suffix in (("Diffuse", "D"), ("nor_dx", "N"), ("arm", "ARM")):
        f = os.path.join(folder, f"{tid}_{key}_1k.jpg")
        if not os.path.exists(f):
            continue
        t = unreal.AssetImportTask()
        t.filename, t.destination_path, t.destination_name = f, f"{TEX}/{tid}", f"T_{tid}_{suffix}"
        t.automated, t.replace_existing, t.save = True, True, False
        tools.import_asset_tasks([t])
        a = unreal.load_asset(f"{TEX}/{tid}/T_{tid}_{suffix}")
        if suffix == "N":
            a.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
            a.set_editor_property("srgb", False)
        elif suffix == "ARM":
            a.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
            a.set_editor_property("srgb", False)
        a.set_editor_property("max_texture_size", 1024)
        eas.save_loaded_asset(a, False)


def build_materials():
    master = unreal.load_asset(MASTER)
    if not master.get_editor_property("used_with_skeletal_mesh"):
        master.set_editor_property("used_with_skeletal_mesh", True)
        mel.recompile_material(master)
        eas.save_loaded_asset(master, False)
    import json
    stats = json.load(open(os.path.join(PROJECT, "SourceArt", "Textures", "texture_stats.json")))
    mis = {}
    for slot, (tid, mode, tint, s, tiling, rough) in SLOTS.items():
        name = "MI_Garment_" + slot[2:]
        full = f"{MAT_DIR}/{name}"
        mi = unreal.load_asset(full) if eas.does_asset_exist(full) else tools.create_asset(
            name, MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mi.set_editor_property("parent", master)
        mel.clear_all_material_instance_parameters(mi)
        mel.set_material_instance_vector_parameter_value(mi, "Tint", unreal.LinearColor(*tint, 1.0))
        mel.set_material_instance_scalar_parameter_value(mi, "Roughness", rough)
        use = bool(tid)
        if use:
            ensure_texture(tid)
            use = tex(tid, "D") is not None
        mel.set_material_instance_static_switch_parameter_value(mi, "UseTextures", use)
        if use:
            mel.set_material_instance_texture_parameter_value(mi, "BaseTex", tex(tid, "D"))
            if tex(tid, "N"):
                mel.set_material_instance_texture_parameter_value(mi, "NormalTex", tex(tid, "N"))
                mel.set_material_instance_scalar_parameter_value(mi, "NormalStrength", 0.6)
            if tex(tid, "ARM"):
                mel.set_material_instance_texture_parameter_value(mi, "ARMTex", tex(tid, "ARM"))
                mel.set_material_instance_scalar_parameter_value(mi, "ARMRoughnessWeight", 0.5)
            mel.set_material_instance_scalar_parameter_value(mi, "Tiling", tiling)
            if mode == "colour":
                mel.set_material_instance_scalar_parameter_value(mi, "ColourMode", 1.0)
                mel.set_material_instance_scalar_parameter_value(mi, "Lift", s)
            else:
                mel.set_material_instance_scalar_parameter_value(mi, "TexMean", max(0.02, (stats.get(tid) or {}).get("mean_lum_linear", 0.3)))
                mel.set_material_instance_scalar_parameter_value(mi, "TexStrength", s)
        if slot in TWO_SIDED:
            # skirt hem and cardigan opening show their inside from a seated viewer
            bpo = mi.get_editor_property("base_property_overrides")
            bpo.set_editor_property("override_two_sided", True)
            bpo.set_editor_property("two_sided", True)
            mi.set_editor_property("base_property_overrides", bpo)
        mel.update_material_instance(mi)
        eas.save_loaded_asset(mi, False)
        mis[slot] = mi
    return mis


def import_garment(name, mis):
    fbx = os.path.join(SRC, name, f"SKM_{name}_Outfit.fbx")
    if not os.path.exists(fbx):
        log(f"{name}: no FBX yet ({fbx})")
        return None
    dest = f"{DST}/{name}"
    t = unreal.AssetImportTask()
    t.filename, t.destination_path, t.destination_name = fbx, dest, f"SKM_{name}_Outfit"
    t.automated, t.replace_existing, t.save = True, True, False
    ui = unreal.FbxImportUI()
    ui.import_mesh = True
    ui.import_as_skeletal = True
    ui.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH
    ui.import_materials = False
    ui.import_textures = False
    ui.import_animations = False
    ui.create_physics_asset = False
    ui.skeleton = unreal.load_asset(SKELETON)
    sk = ui.skeletal_mesh_import_data
    for prop, val in (("import_morph_targets", False), ("update_skeleton_reference_pose", False),
                      ("use_t0_as_ref_pose", False), ("import_meshes_in_bone_hierarchy", True)):
        try:   # property names differ between engine versions; skip what is not exposed
            sk.set_editor_property(prop, val)
        except Exception:
            pass
    t.options = ui
    tools.import_asset_tasks([t])
    mesh = unreal.load_asset(f"{dest}/SKM_{name}_Outfit")
    if not isinstance(mesh, unreal.SkeletalMesh):
        log(f"{name}: import FAILED")
        return None
    mats = list(mesh.get_editor_property("materials"))
    unknown = []
    for i, m in enumerate(mats):
        slot = str(m.get_editor_property("material_slot_name")).split(".")[0]
        slot = REMAP.get(name, {}).get(slot, slot)
        if slot in mis:
            m.set_editor_property("material_interface", mis[slot])
            mats[i] = m
        else:
            unknown.append(slot)
    mesh.set_editor_property("materials", mats)
    eas.save_loaded_asset(mesh, False)
    log(f"{name}: imported, skeleton {mesh.skeleton.get_name()}, slots {len(mats)}" + (f", UNKNOWN {unknown}" if unknown else ""))
    return mesh


def dress(garments):
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    n = 0
    for a in acts.get_all_level_actors():
        name = WEARERS.get(a.get_actor_label())
        if not name or garments.get(name) is None:
            continue
        outfit = next((c for c in a.get_components_by_class(unreal.SkeletalMeshComponent)
                       if c.get_skinned_asset() and str(c.get_skinned_asset().get_name()).endswith("_Outfits")), None)
        if outfit is None:
            outfit = next((c for c in a.get_components_by_class(unreal.SkeletalMeshComponent)
                           if c.get_skinned_asset() and "Outfit" in c.get_skinned_asset().get_name()), None)
        if outfit is None:
            log(f"{a.get_actor_label()}: no outfit component")
            continue
        outfit.set_skinned_asset_and_update(garments[name])
        # The MetaHuman Blueprint sets material overrides for Epic's default garment on this
        # component; left in place they cover our slots 0/1 (shirt, trousers) with the T-shirt
        # material. Clear them so the garment's own MI_Garment_* materials show.
        try:
            outfit.empty_override_materials()
        except Exception:
            for i, m in enumerate(garments[name].get_editor_property("materials")):
                outfit.set_material(i, m.get_editor_property("material_interface"))
        n += 1
    les.save_current_level()
    log(f"dressed {n} characters and saved the level")


def main():
    mis = build_materials()
    garments = {n: import_garment(n, mis) for n in ("David", "Maria", "Enzo")}
    dress(garments)


main()
