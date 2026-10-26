"""Import the Blender room assets and their materials into the project.

Inputs (all produced outside Unreal):
  SourceArt/Room/Export/SM_*.fbx         meshes (UV0 'UVMap' texture, UV1 'Lightmap')
  SourceArt/Room/Export/T_SkyDome.jpg    LDR equirectangular sky
  SourceArt/Textures/<id>/<id>_{Diffuse,nor_dx,arm}_1k.jpg   Poly Haven CC0 PBR sets
  SourceArt/Textures/texture_stats.json  mean linear luminance per diffuse (keeps palette exact)

Outputs:
  /Game/Wattleview/Environment/Textures/<id>/T_<id>_{D,N,ARM}
  /Game/Wattleview/Environment/Materials/M_RoomMaster   one lit master for every slot
  /Game/Wattleview/Environment/Materials/M_SkyDome      unlit sky
  /Game/Wattleview/Environment/Materials/MI_<slot>      one instance per CONVENTIONS slot name
  /Game/Wattleview/Environment/Meshes/{Room,Garden,Memory,Sky}/SM_*

Mesh settings: lightmap UVs from the FBX (channel 1, no generated lightmap UVs), lightmap
resolution per mesh, no collision, Nanite off, material slots filled by slot name.

Run headless or in the editor:
  UnrealEditor-Cmd <project> -ExecutePythonScript="<this file>"
Re-running replaces assets in place (references from the level survive).
"""
import json
import os

import unreal

PROJECT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SRC_ROOM = os.path.join(PROJECT, "SourceArt", "Room", "Export")
SRC_TEX = os.path.join(PROJECT, "SourceArt", "Textures")
SRC_PHOTOS = os.path.join(PROJECT, "SourceArt", "Photos")
ENV = "/Game/Wattleview/Environment"
TEX_DIR = ENV + "/Textures"
MAT_DIR = ENV + "/Materials"
MESH_DIR = ENV + "/Meshes"

eas = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
smes = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)


def log(msg):
    unreal.log("[RoomImport] " + msg)


# ------------------------------------------------------------------ slot -> material settings
# mode "detail": BaseColor = Tint * lerp(1, luminance/mean, Strength)  (palette colour kept)
# mode "colour": BaseColor = lerp(texture, 1, Lift) * Tint             (texture's own colours)
# tex None: plain Tint, no texture samplers (static switch off).
# Glossy slots are kept at roughness >= 0.15: on the headset (no exposure, LDR) reflections of
# the sunlit room read as harsh highlights.
SLOTS = {
    "M_WallPaint":       dict(tex="beige_wall_001", mode="detail", tint=(0.74, 0.71, 0.66), strength=0.35, tiling=0.5, rough=0.85, normal=0.35),
    "M_Ceiling":         dict(tex="beige_wall_002", mode="detail", tint=(0.80, 0.79, 0.76), strength=0.2, tiling=0.5, rough=0.9, normal=0.2),
    "M_Carpet":          dict(tex="dirty_carpet", mode="detail", tint=(0.52, 0.48, 0.43), strength=0.55, tiling=1.0, rough=0.95, normal=0.6),
    "M_Timber":          dict(tex="ash_veneer", mode="colour", tint=(1.25, 1.2, 1.15), lift=0.0, tiling=1.5, rough=0.55, normal=0.4),
    "M_TimberDark":      dict(tex="ash_veneer", mode="colour", tint=(0.55, 0.40, 0.30), lift=0.0, tiling=1.5, rough=0.5, normal=0.4),
    "M_DoorTimber":      dict(tex="ash_veneer", mode="colour", tint=(1.05, 0.88, 0.70), lift=0.0, tiling=1.0, rough=0.5, normal=0.4),
    "M_PaintedTimber":   dict(tex=None, tint=(0.86, 0.85, 0.82), rough=0.4),
    "M_UpholsteryPink":  dict(tex="caban", mode="detail", tint=(0.70, 0.42, 0.42), strength=0.6, tiling=3.0, rough=0.9, normal=0.7),
    "M_UpholsteryCream": dict(tex="caban", mode="detail", tint=(0.76, 0.68, 0.56), strength=0.6, tiling=3.0, rough=0.9, normal=0.7),
    "M_Linen":           dict(tex="rough_linen", mode="detail", tint=(0.90, 0.89, 0.86), strength=0.35, tiling=2.0, rough=0.9, normal=0.5),
    "M_FloralCover":     dict(tex="floral_jacquard", mode="detail", tint=(0.78, 0.56, 0.62), strength=0.85, tiling=2.0, rough=0.85, normal=0.6),
    "M_Crochet":         dict(tex="wool_boucle", mode="colour", tint=(1.6, 1.45, 1.4), lift=0.1, tiling=3.0, rough=0.95, normal=0.8),
    "M_Curtain":         dict(tex="rough_linen", mode="detail", tint=(0.88, 0.85, 0.78), strength=0.3, tiling=1.5, rough=0.9, normal=0.4),
    "M_Rug":             dict(tex="hessian_380", mode="colour", tint=(1.0, 1.0, 1.0), lift=0.0, tiling=2.0, rough=0.95, normal=0.7),
    "M_Metal":           dict(tex=None, tint=(0.62, 0.62, 0.64), rough=0.45, metallic=1.0),
    "M_Brass":           dict(tex=None, tint=(0.78, 0.58, 0.26), rough=0.4, metallic=1.0),
    "M_Gold":            dict(tex=None, tint=(0.85, 0.65, 0.25), rough=0.4, metallic=1.0),
    "M_PlasticBlack":    dict(tex=None, tint=(0.03, 0.03, 0.03), rough=0.4),
    "M_PlasticWhite":    dict(tex=None, tint=(0.85, 0.85, 0.83), rough=0.45),
    "M_Screen":          dict(tex=None, tint=(0.01, 0.01, 0.012), rough=0.25),
    "M_Ceramic":         dict(tex=None, tint=(0.88, 0.86, 0.80), rough=0.35),
    "M_Glass":           dict(tex=None, tint=(0.70, 0.80, 0.82), rough=0.15),
    "M_Plant":           dict(tex=None, tint=(0.16, 0.38, 0.12), rough=0.6),
    "M_PlantDark":       dict(tex=None, tint=(0.07, 0.22, 0.06), rough=0.6),
    "M_Flower":          dict(tex=None, tint=(0.95, 0.80, 0.15), rough=0.6),
    "M_FlowerRed":       dict(tex=None, tint=(0.80, 0.10, 0.10), rough=0.5),
    "M_Paper":           dict(tex=None, tint=(0.92, 0.91, 0.86), rough=0.9),
    "M_Photo":           dict(tex=None, tint=(0.45, 0.52, 0.38), rough=0.6),
    "M_LampShade":       dict(tex="rough_linen", mode="detail", tint=(0.92, 0.86, 0.72), strength=0.25, tiling=2.0, rough=0.9, normal=0.3),
    "M_Bark":            dict(tex="bark_bluegum", mode="colour", tint=(1.6, 1.5, 1.4), lift=0.0, tiling=1.0, rough=0.9, normal=0.8),
    "M_Soil":            dict(tex="farm_soil", mode="colour", tint=(1.2, 1.15, 1.1), lift=0.0, tiling=1.0, rough=0.95, normal=0.7),
    "M_Grass":           dict(tex="leafy_grass", mode="colour", tint=(0.95, 1.15, 0.80), lift=0.0, tiling=0.5, rough=0.95, normal=0.5),
    "M_Terracotta":      dict(tex=None, tint=(0.65, 0.32, 0.18), rough=0.85),
    "M_Rubber":          dict(tex=None, tint=(0.10, 0.10, 0.10), rough=0.8),
}

GARDEN = {"SM_Lawn", "SM_FlowerBed", "SM_GardenTree_A", "SM_GardenTree_B", "SM_Shrub", "SM_Fence", "SM_GardenBench"}
MEMORY = {"SM_TomatoPlant", "SM_BasilPot", "SM_FigTree", "SM_GardenHose"}
SKY = {"SM_SkyDome"}
# Mesh-specific slot materials: the wall photograph is a real picture (graded by
# Scripts/Tools/grade_wall_photo.py); the gallery frames keep the plain M_Photo tint.
# mesh -> {slot: (instance name, image in SourceArt/Photos)}
PHOTOS = {"SM_PhotoFrame_MariaEnzo": {"M_Photo": ("MI_Photo_MariaEnzo", "T_Photo_MariaEnzo.jpg")}}

LIGHTMAP_RES = {
    "SM_Floor": 1024, "SM_Ceiling": 512, "SM_Wall_North": 512, "SM_Wall_South": 512,
    "SM_Wall_East": 512, "SM_Wall_West": 512, "SM_Skirting": 256, "SM_Cornice": 256,
    "SM_WindowFrame": 256, "SM_Door": 256, "SM_DoorFrame": 128, "SM_DoorHandle": 32,
    "SM_Bed": 256, "SM_BedLinen": 256, "SM_Wardrobe": 256, "SM_Recliner": 256,
    "SM_Armchair": 128, "SM_RoundTable": 128, "SM_Rug": 256, "SM_Bedside": 128,
    "SM_TVCabinet": 128, "SM_TV": 64, "SM_TVScreen": 16, "SM_Curtains": 256,
    "SM_CurtainRod": 64, "SM_FloorLamp": 64, "SM_CeilingFan": 32, "SM_Shelf": 64,
    "SM_PhotoFrame_MariaEnzo": 64, "SM_Calendar": 64, "SM_Lawn": 512, "SM_SkyDome": 4,
    "SM_GardenTree_A": 128, "SM_GardenTree_B": 128, "SM_Fence": 128, "SM_FlowerBed": 128,
}


# ------------------------------------------------------------------ textures
def import_file(path, dest_dir, name):
    t = unreal.AssetImportTask()
    t.filename = path
    t.destination_path = dest_dir
    t.destination_name = name
    t.automated = True
    t.replace_existing = True
    t.save = False
    tools.import_asset_tasks([t])
    return unreal.load_asset(f"{dest_dir}/{name}")


def import_textures():
    stats = json.load(open(os.path.join(SRC_TEX, "texture_stats.json")))
    out = {}
    needed = sorted({s["tex"] for s in SLOTS.values() if s.get("tex")})
    for tid in needed:
        d = os.path.join(SRC_TEX, tid)
        dest = f"{TEX_DIR}/{tid}"
        maps = {}
        for key, suffix in (("Diffuse", "D"), ("nor_dx", "N"), ("arm", "ARM")):
            f = os.path.join(d, f"{tid}_{key}_1k.jpg")
            if not os.path.exists(f):
                continue
            tex = import_file(f, dest, f"T_{tid}_{suffix}")
            if suffix == "N":
                tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
                tex.set_editor_property("srgb", False)
                tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD_NORMAL_MAP)
            elif suffix == "ARM":
                tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
                tex.set_editor_property("srgb", False)
                tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD_SPECULAR)
            else:
                tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD)
            tex.set_editor_property("max_texture_size", 1024)
            eas.save_loaded_asset(tex, False)
            maps[suffix] = tex
        maps["mean"] = (stats.get(tid) or {}).get("mean_lum_linear", 0.5)
        out[tid] = maps
        log(f"textures {tid}: {sorted(k for k in maps if k != 'mean')}")
    sky = os.path.join(SRC_ROOM, "T_SkyDome.jpg")
    if os.path.exists(sky):
        st = import_file(sky, TEX_DIR + "/Sky", "T_SkyDome")
        st.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_SKYBOX)
        st.set_editor_property("max_texture_size", 2048)
        st.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
        st.set_editor_property("address_x", unreal.TextureAddress.TA_WRAP)
        st.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
        eas.save_loaded_asset(st, False)
        out["__sky__"] = st
        log("sky texture imported")
    return out


# ------------------------------------------------------------------ materials
def fresh_material(name, path=MAT_DIR):
    full = f"{path}/{name}"
    if eas.does_asset_exist(full):
        mat = unreal.load_asset(full)
        mel.delete_all_material_expressions(mat)
        return mat
    return tools.create_asset(name, path, unreal.Material, unreal.MaterialFactoryNew())


def expr(mat, cls, x, y, **props):
    e = mel.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        e.set_editor_property(k, v)
    return e


def link(a, a_out, b, b_in):
    mel.connect_material_expressions(a, a_out, b, b_in)


def build_master(textures):
    """Lit master: detail or colour texturing, ARM roughness, normal strength, static switch."""
    any_set = next(v for k, v in textures.items() if k != "__sky__" and "D" in v and "N" in v and "ARM" in v)
    mat = fresh_material("M_RoomMaster")
    s = unreal.MaterialExpressionScalarParameter
    v = unreal.MaterialExpressionVectorParameter
    tint = expr(mat, v, -400, -300, parameter_name="Tint", default_value=unreal.LinearColor(0.8, 0.8, 0.8, 1))
    tiling = expr(mat, s, -1700, 0, parameter_name="Tiling", default_value=1.0)
    uv = expr(mat, unreal.MaterialExpressionTextureCoordinate, -1700, -120)
    uvm = expr(mat, unreal.MaterialExpressionMultiply, -1550, -60)
    link(uv, "", uvm, "A"); link(tiling, "", uvm, "B")
    tp = unreal.MaterialExpressionTextureSampleParameter2D
    base = expr(mat, tp, -1350, -400, parameter_name="BaseTex", texture=any_set["D"],
                sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
    nrm = expr(mat, tp, -1350, 100, parameter_name="NormalTex", texture=any_set["N"],
               sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    arm = expr(mat, tp, -1350, 450, parameter_name="ARMTex", texture=any_set["ARM"],
               sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    for t in (base, nrm, arm):
        link(uvm, "", t, "UVs")
    # detail mode
    desat = expr(mat, unreal.MaterialExpressionDesaturation, -1100, -500)
    one = expr(mat, unreal.MaterialExpressionConstant, -1250, -560, r=1.0)
    link(base, "RGB", desat, ""); link(one, "", desat, "Fraction")
    mean = expr(mat, s, -1100, -380, parameter_name="TexMean", default_value=0.5)
    ratio = expr(mat, unreal.MaterialExpressionDivide, -950, -480)
    link(desat, "", ratio, "A"); link(mean, "", ratio, "B")
    strength = expr(mat, s, -950, -360, parameter_name="TexStrength", default_value=0.5)
    det_l = expr(mat, unreal.MaterialExpressionLinearInterpolate, -800, -460)
    link(one, "", det_l, "A"); link(ratio, "", det_l, "B"); link(strength, "", det_l, "Alpha")
    det_c = expr(mat, unreal.MaterialExpressionMultiply, -650, -440)
    link(det_l, "", det_c, "A"); link(tint, "", det_c, "B")
    # colour mode
    lift = expr(mat, s, -1100, -220, parameter_name="Lift", default_value=0.0)
    col_l = expr(mat, unreal.MaterialExpressionLinearInterpolate, -950, -260)
    link(base, "RGB", col_l, "A"); link(one, "", col_l, "B"); link(lift, "", col_l, "Alpha")
    col_c = expr(mat, unreal.MaterialExpressionMultiply, -800, -260)
    link(col_l, "", col_c, "A"); link(tint, "", col_c, "B")
    cmode = expr(mat, s, -800, -150, parameter_name="ColourMode", default_value=0.0)
    tex_col = expr(mat, unreal.MaterialExpressionLinearInterpolate, -500, -380)
    link(det_c, "", tex_col, "A"); link(col_c, "", tex_col, "B"); link(cmode, "", tex_col, "Alpha")
    # roughness
    rough = expr(mat, s, -1000, 600, parameter_name="Roughness", default_value=0.7)
    rough_w = expr(mat, s, -1000, 700, parameter_name="ARMRoughnessWeight", default_value=0.5)
    tex_rough = expr(mat, unreal.MaterialExpressionLinearInterpolate, -800, 560)
    link(rough, "", tex_rough, "A"); link(arm, "G", tex_rough, "B"); link(rough_w, "", tex_rough, "Alpha")
    # normal
    flat = expr(mat, unreal.MaterialExpressionConstant3Vector, -1000, 250, constant=unreal.LinearColor(0, 0, 1, 1))
    nstr = expr(mat, s, -1000, 350, parameter_name="NormalStrength", default_value=0.5)
    tex_n = expr(mat, unreal.MaterialExpressionLinearInterpolate, -800, 200)
    link(flat, "", tex_n, "A"); link(nrm, "RGB", tex_n, "B"); link(nstr, "", tex_n, "Alpha")
    # static switches: plain slots skip all three texture samplers
    sw = unreal.MaterialExpressionStaticSwitchParameter
    sw_c = expr(mat, sw, -250, -300, parameter_name="UseTextures", default_value=True)
    link(tex_col, "", sw_c, "True"); link(tint, "", sw_c, "False")
    sw_r = expr(mat, sw, -250, 500, parameter_name="UseTextures", default_value=True)
    link(tex_rough, "", sw_r, "True"); link(rough, "", sw_r, "False")
    sw_n = expr(mat, sw, -250, 200, parameter_name="UseTextures", default_value=True)
    link(tex_n, "", sw_n, "True"); link(flat, "", sw_n, "False")
    metal = expr(mat, s, -250, 380, parameter_name="Metallic", default_value=0.0)
    mel.connect_material_property(sw_c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(sw_r, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(sw_n, "", unreal.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
    mel.recompile_material(mat)
    eas.save_loaded_asset(mat, False)
    log("M_RoomMaster built")
    return mat


def build_sky_material(sky_tex):
    mat = fresh_material("M_SkyDome")
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    t = expr(mat, unreal.MaterialExpressionTextureSampleParameter2D, -600, 0, parameter_name="SkyTex",
             texture=sky_tex, sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
    b = expr(mat, unreal.MaterialExpressionScalarParameter, -600, 250, parameter_name="SkyBrightness", default_value=0.8)
    m = expr(mat, unreal.MaterialExpressionMultiply, -300, 50)
    link(t, "RGB", m, "A"); link(b, "", m, "B")
    mel.connect_material_property(m, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(mat)
    eas.save_loaded_asset(mat, False)
    log("M_SkyDome built")
    return mat


def build_instances(master, textures):
    mis = {}
    for slot, cfg in SLOTS.items():
        name = "MI_" + slot[2:]
        full = f"{MAT_DIR}/{name}"
        mi = unreal.load_asset(full) if eas.does_asset_exist(full) else tools.create_asset(
            name, MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mi.set_editor_property("parent", master)
        mel.clear_all_material_instance_parameters(mi)
        tint = cfg["tint"]
        mel.set_material_instance_vector_parameter_value(mi, "Tint", unreal.LinearColor(tint[0], tint[1], tint[2], 1.0))
        mel.set_material_instance_scalar_parameter_value(mi, "Roughness", cfg.get("rough", 0.7))
        mel.set_material_instance_scalar_parameter_value(mi, "Metallic", cfg.get("metallic", 0.0))
        tid = cfg.get("tex")
        use = bool(tid and tid in textures)
        mel.set_material_instance_static_switch_parameter_value(mi, "UseTextures", use)
        if use:
            t = textures[tid]
            if "D" in t:
                mel.set_material_instance_texture_parameter_value(mi, "BaseTex", t["D"])
            if "N" in t:
                mel.set_material_instance_texture_parameter_value(mi, "NormalTex", t["N"])
            if "ARM" in t:
                mel.set_material_instance_texture_parameter_value(mi, "ARMTex", t["ARM"])
            mel.set_material_instance_scalar_parameter_value(mi, "Tiling", cfg.get("tiling", 1.0))
            mel.set_material_instance_scalar_parameter_value(mi, "NormalStrength", cfg.get("normal", 0.5) if "N" in t else 0.0)
            mel.set_material_instance_scalar_parameter_value(mi, "ARMRoughnessWeight", 0.5 if "ARM" in t else 0.0)
            if cfg.get("mode") == "colour":
                mel.set_material_instance_scalar_parameter_value(mi, "ColourMode", 1.0)
                mel.set_material_instance_scalar_parameter_value(mi, "Lift", cfg.get("lift", 0.0))
            else:
                mel.set_material_instance_scalar_parameter_value(mi, "ColourMode", 0.0)
                mel.set_material_instance_scalar_parameter_value(mi, "TexMean", max(0.02, t["mean"]))
                mel.set_material_instance_scalar_parameter_value(mi, "TexStrength", cfg.get("strength", 0.5))
        mel.update_material_instance(mi)
        eas.save_loaded_asset(mi, False)
        mis[slot] = mi
    log(f"{len(mis)} material instances")
    return mis


def build_photo_instances(master):
    """Colour-mode instances showing a photograph 1:1 on a picture slot's own 0..1 UV map."""
    out = {}
    for mesh, slots in PHOTOS.items():
        for slot, (mi_name, image) in slots.items():
            f = os.path.join(SRC_PHOTOS, image)
            if not os.path.exists(f):
                log(f"photo {image} missing, {mesh} keeps {slot}")
                continue
            tex = import_file(f, TEX_DIR + "/Photos", os.path.splitext(image)[0])
            tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD)
            tex.set_editor_property("max_texture_size", 1024)
            tex.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
            tex.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
            eas.save_loaded_asset(tex, False)
            full = f"{MAT_DIR}/{mi_name}"
            mi = unreal.load_asset(full) if eas.does_asset_exist(full) else tools.create_asset(
                mi_name, MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
            mi.set_editor_property("parent", master)
            mel.clear_all_material_instance_parameters(mi)
            mel.set_material_instance_static_switch_parameter_value(mi, "UseTextures", True)
            mel.set_material_instance_texture_parameter_value(mi, "BaseTex", tex)
            mel.set_material_instance_vector_parameter_value(mi, "Tint", unreal.LinearColor(1, 1, 1, 1))
            for name, val in (("ColourMode", 1.0), ("Lift", 0.0), ("Tiling", 1.0), ("Roughness", 0.5),
                              ("NormalStrength", 0.0), ("ARMRoughnessWeight", 0.0)):
                mel.set_material_instance_scalar_parameter_value(mi, name, val)
            mel.update_material_instance(mi)
            eas.save_loaded_asset(mi, False)
            out.setdefault(mesh, {})[slot] = mi
            log(f"photo {image} -> {mi_name} on {mesh}.{slot}")
    return out


# ------------------------------------------------------------------ meshes
def mesh_folder(name):
    if name in GARDEN:
        return MESH_DIR + "/Garden"
    if name in MEMORY:
        return MESH_DIR + "/Memory"
    if name in SKY:
        return MESH_DIR + "/Sky"
    return MESH_DIR + "/Room"


def default_lightmap_res(mesh):
    b = mesh.get_bounding_box()
    size = max(b.max.x - b.min.x, b.max.y - b.min.y, b.max.z - b.min.z)
    if size > 150:
        return 256
    if size > 60:
        return 128
    if size > 25:
        return 64
    return 32


def assign_slot_materials(mesh, mis, override=None):
    """Assign MI_<slot> by material slot name. Struct copies from static_materials cannot be
    edited in place from Python, so use StaticMesh.set_material per index."""
    unknown = []
    for i, sm in enumerate(mesh.get_editor_property("static_materials")):
        slot = str(sm.get_editor_property("material_slot_name")).split(".")[0]
        mat = override or mis.get(slot)
        if mat is None:
            unknown.append(slot)
            continue
        mesh.set_material(i, mat)
    return unknown


def import_meshes(mis, sky_mat, photo_mis=None):
    files = sorted(f for f in os.listdir(SRC_ROOM) if f.startswith("SM_") and f.lower().endswith(".fbx"))
    report = []
    for f in files:
        name = os.path.splitext(f)[0]
        dest = mesh_folder(name)
        t = unreal.AssetImportTask()
        t.filename = os.path.join(SRC_ROOM, f)
        t.destination_path = dest
        t.destination_name = name
        t.automated = True
        t.replace_existing = True
        t.save = False
        ui = unreal.FbxImportUI()
        ui.import_mesh = True
        ui.import_as_skeletal = False
        ui.import_materials = False
        ui.import_textures = False
        ui.import_animations = False
        smd = ui.static_mesh_import_data
        smd.combine_meshes = True
        smd.generate_lightmap_u_vs = False
        smd.auto_generate_collision = False
        smd.remove_degenerates = True
        smd.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
        for prop, val in (("build_nanite", False), ("one_convex_hull_per_ucx", False)):
            try:
                smd.set_editor_property(prop, val)
            except Exception:
                pass
        t.options = ui
        tools.import_asset_tasks([t])
        mesh = unreal.load_asset(f"{dest}/{name}")
        if not isinstance(mesh, unreal.StaticMesh):
            report.append(f"{name}: IMPORT FAILED")
            continue
        uv_channels = smes.get_num_uv_channels(mesh, 0)
        mesh.set_editor_property("light_map_coordinate_index", 1 if uv_channels > 1 else 0)
        mesh.set_editor_property("light_map_resolution", LIGHTMAP_RES.get(name, default_lightmap_res(mesh)))
        try:
            ns = mesh.get_editor_property("nanite_settings")
            ns.set_editor_property("enabled", False)
            mesh.set_editor_property("nanite_settings", ns)
        except Exception:
            pass
        slot_mis = {**mis, **(photo_mis or {}).get(name, {})}
        unknown = assign_slot_materials(mesh, slot_mis, sky_mat if name in SKY else None)
        if name in SKY:
            mesh.set_editor_property("light_map_resolution", 4)
        eas.save_loaded_asset(mesh, False)
        b = mesh.get_bounding_box()
        report.append(f"{name}: uv={uv_channels} lm={mesh.get_editor_property('light_map_resolution')} "
                      f"size=({b.max.x - b.min.x:.0f},{b.max.y - b.min.y:.0f},{b.max.z - b.min.z:.0f})"
                      + (f" UNKNOWN SLOTS {unknown}" if unknown else ""))
    for line in report:
        log(line)
    return report


def main():
    for d in (TEX_DIR, MAT_DIR, MESH_DIR):
        eas.make_directory(d)
    textures = import_textures()
    master = build_master(textures)
    sky_mat = build_sky_material(textures["__sky__"]) if "__sky__" in textures else None
    mis = build_instances(master, textures)
    import_meshes(mis, sky_mat, build_photo_instances(master))
    log("done")


main()
