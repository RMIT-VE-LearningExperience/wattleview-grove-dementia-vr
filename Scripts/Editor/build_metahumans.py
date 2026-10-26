"""Author the Wattleview Grove MetaHuman characters (UE 5.8 MetaHuman Creator, Python only).

Characters (MetaHumanCharacter source assets in /Game/MetaHumans/Src):
  Maria      82, Italian, Alzheimer's (moderate). Elderly face, olive skin, short grey curls.
  David      support worker, early 30s. Short dark hair, light stubble.
  Enzo       Maria's late husband as she sees him: elderly, grey hair, moustache. Shares
             David's body measurements so the two can cross-fade on the same animation.
  EnzoYoung  Enzo in the wall photograph (younger, dark hair). Desktop-only, rendered to a
             texture, never shipped as a character.

What runs locally (no sign-in): preset blending via face-model coefficients, body
measurements, skin tone and aged face texture (texture synthesis), teeth/eyelash/eye settings,
grooms and their colours, preview portraits.
What needs Lawrence's Epic sign-in (MetaHuman cloud): face auto-rigging, texture-source
download and assembly. Run Scripts/Editor/assemble_metahumans.py after signing in.

Run headless:  UnrealEditor-Cmd <project> -ExecutePythonScript="<this file>"
Environment:   WG_MH_ONLY=Maria,David  (subset)   WG_MH_RECREATE=1 (start again from presets)
               WG_MH_CAPTURE=0 (skip portraits)   WG_MH_AUTHOR=0 (portraits of existing characters)
Portraits:     Saved/MetaHumans/<Name>_front.png and <Name>_three_quarter.png
"""
import json
import os
import time
import traceback

import unreal

SRC = "/Game/MetaHumans/Src"
PRESETS = "/MetaHumanCharacter/Optional/Presets"
GROOMS = "/MetaHumanCharacter/Optional/Grooms/Bindings"
OUT = os.path.join(unreal.Paths.project_saved_dir(), "MetaHumans")

# David and Enzo share one body so Enzo can cross-fade over David on the same animation.
SHARED_MALE_BODY = {"Height": 177.0, "Fat": 0.2, "Muscularity": -0.6, "Masculine/Feminine": -1.2}

CHARACTERS = {
    "Maria": dict(
        blend={"Grace": 0.45, "Vivian": 0.33, "Jelena": 0.22},   # chosen from five trial blends (Maria_A)
        skin=dict(u=0.46, v=0.60, face_texture_index=121, roughness=1.08),
        body={"Height": 155.0, "Fat": 0.9, "Muscularity": -1.4, "Masculine/Feminine": 1.3},
        teeth=dict(worn_down=0.55, plaque_amount=0.3, receding_gums=0.5, variation=0.4),
        sclera_tint=(1.0, 0.96, 0.90),
        iris_from="Mateo",
        grooms={"Hair": "Hair/WI_Hair_M_BobCurly", "Eyebrows": "Eyebrows/WI_Eyebrows_M_Thin",
                "Eyelashes": "Eyelashes/WI_Eyelashes_S_Fine", "Peachfuzz": "Peachfuzz/WI_Peachfuzz_M_Thin"},
        hair_colour={"Melanin": 0.35, "Whiteness": 0.8, "Lightness": 0.55},
    ),
    "David": dict(
        blend={"Orlando": 0.6, "Mateo": 0.4},
        skin=dict(u=0.52, v=0.60, face_texture_index=72, roughness=1.0),
        body=SHARED_MALE_BODY,
        teeth=dict(variation=0.2),
        sclera_tint=None,
        grooms={"Hair": "Hair/WI_Hair_S_Clean", "Eyebrows": "Eyebrows/WI_Eyebrows_M_Natural",
                "Beard": "Beards/WI_Beard_S_Stubble", "Eyelashes": "Eyelashes/WI_Eyelashes_S_Fine",
                "Peachfuzz": "Peachfuzz/WI_Peachfuzz_M_Thin"},
        hair_colour={"Melanin": 0.85, "Whiteness": 0.0},
    ),
    "Enzo": dict(
        blend={"Lorenzo": 0.7, "Walter": 0.3},
        skin=dict(u=0.48, v=0.52, face_texture_index=11, roughness=1.08),
        body=SHARED_MALE_BODY,
        teeth=dict(worn_down=0.6, plaque_amount=0.35, receding_gums=0.45, variation=0.5),
        sclera_tint=(1.0, 0.96, 0.90),
        iris_from="Mateo",
        grooms={"Hair": "Hair/WI_Hair_S_RecedeMessy", "Mustache": "Mustaches/WI_Mustache_S_Full",
                "Eyebrows": "Eyebrows/WI_Eyebrows_L_Scraggly", "Eyelashes": "Eyelashes/WI_Eyelashes_S_Fine",
                "Peachfuzz": "Peachfuzz/WI_Peachfuzz_M_Thin"},
        hair_colour={"Melanin": 0.3, "Whiteness": 0.85, "Lightness": 0.55},
        body_from="David",
    ),
    "EnzoYoung": dict(
        blend={"Lorenzo": 0.35, "Mateo": 0.4, "Jorge": 0.25},
        skin=dict(u=0.50, v=0.55, face_texture_index=36, roughness=1.0),
        body=SHARED_MALE_BODY,
        teeth=dict(variation=0.3),
        sclera_tint=None,
        iris_from="Mateo",
        grooms={"Hair": "Hair/WI_Hair_S_SlickBack", "Mustache": "Mustaches/WI_Mustache_S_Full",
                "Eyebrows": "Eyebrows/WI_Eyebrows_M_Thick", "Eyelashes": "Eyelashes/WI_Eyelashes_S_Fine",
                "Peachfuzz": "Peachfuzz/WI_Peachfuzz_M_Thin"},
        hair_colour={"Melanin": 0.9, "Whiteness": 0.0},
        body_from="David",
    ),
}

eas = unreal.EditorAssetLibrary
sub = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def log(msg):
    unreal.log("[MetaHumans] " + str(msg))


def edit(ch):
    if not sub.is_object_added_for_editing(ch):
        if not sub.try_add_object_to_edit(ch):
            raise RuntimeError(f"cannot open {ch.get_name()} for editing")


def done(ch):
    if sub.is_object_added_for_editing(ch):
        sub.remove_object_to_edit(ch)


def save(ch):
    eas.save_loaded_asset(ch, False)


def preset_coefficients(name):
    tmp = f"{SRC}/_Tmp/{name.replace('-', '_')}"
    if not eas.does_asset_exist(tmp):
        eas.duplicate_asset(f"{PRESETS}/{name}", tmp)
    ch = unreal.load_asset(tmp)
    edit(ch)
    try:
        return list(sub.get_face_model_coefficients(ch))
    finally:
        done(ch)


def create(name, spec, recreate):
    path = f"{SRC}/{name}"
    base = max(spec["blend"].items(), key=lambda kv: kv[1])[0]
    if eas.does_asset_exist(path) and recreate:
        eas.delete_asset(path)
    if not eas.does_asset_exist(path):
        eas.duplicate_asset(f"{PRESETS}/{base}", path)
        log(f"{name}: created from preset {base}")
    return unreal.load_asset(path)


def apply_face(ch, spec, cache):
    mix = None
    for preset, w in spec["blend"].items():
        if preset not in cache:
            cache[preset] = preset_coefficients(preset)
        c = cache[preset]
        mix = [w * x for x in c] if mix is None else [m + w * x for m, x in zip(mix, c)]
    total = sum(spec["blend"].values())
    mix = [m / total for m in mix]
    sub.set_face_model_coefficients(ch, mix)
    sub.commit_face_state(ch)


BODY_CACHE = {}


def apply_body(ch, spec):
    cons = list(sub.get_body_constraints(ch))
    src = spec.get("body_from")
    if src and src in BODY_CACHE:
        # Copy every measurement so the two bodies match (cross-fade on one animation).
        values = BODY_CACHE[src]
        for c in cons:
            n = str(c.get_editor_property("name"))
            if n in values:
                c.set_editor_property("is_active", True)
                c.set_editor_property("target_measurement", values[n])
    else:
        if src:
            log(f"body_from {src} not authored in this run; using its spec values")
        for c in cons:
            n = str(c.get_editor_property("name"))
            if n in spec["body"]:
                c.set_editor_property("is_active", True)
                c.set_editor_property("target_measurement", float(spec["body"][n]))
    sub.set_body_constraints(ch, cons)
    sub.commit_body_state(ch)
    BODY_CACHE[ch.get_name()] = {str(c.get_editor_property("name")): float(c.get_editor_property("target_measurement"))
                                 for c in sub.get_body_constraints(ch)}


def apply_skin(ch, spec):
    ss = ch.get_editor_property("skin_settings")
    sk = ss.get_editor_property("skin")
    for k, v in spec["skin"].items():
        sk.set_editor_property(k, v)
    ss.set_editor_property("skin", sk)
    sub.commit_skin_settings(ch, ss)


def apply_head_and_eyes(ch, spec):
    hm = ch.get_editor_property("head_model_settings")
    teeth = hm.get_editor_property("teeth")
    for k, v in spec["teeth"].items():
        teeth.set_editor_property(k, v)
    hm.set_editor_property("teeth", teeth)
    sub.commit_head_model_settings(ch, hm)
    if spec.get("iris_from"):
        src = unreal.load_asset(f"{PRESETS}/{spec['iris_from']}")
        src_es = src.get_editor_property("eyes_settings")
        es = ch.get_editor_property("eyes_settings")
        for side in ("eye_left", "eye_right"):
            eye = es.get_editor_property(side)
            eye.set_editor_property("iris", src_es.get_editor_property(side).get_editor_property("iris"))
            es.set_editor_property(side, eye)
        sub.commit_eyes_settings(ch, es)
    if spec.get("sclera_tint"):
        es = ch.get_editor_property("eyes_settings")
        for side in ("eye_left", "eye_right"):
            eye = es.get_editor_property(side)
            sc = eye.get_editor_property("sclera")
            sc.set_editor_property("use_custom_tint", True)
            r, g, b = spec["sclera_tint"]
            sc.set_editor_property("tint", unreal.LinearColor(r, g, b, 1.0))
            eye.set_editor_property("sclera", sc)
            es.set_editor_property(side, eye)
        sub.commit_eyes_settings(ch, es)


GROOM_SLOTS = ("Hair", "Eyebrows", "Beard", "Mustache", "Eyelashes", "Peachfuzz")


def apply_grooms(ch, spec):
    """Select grooms and colour them through the PREVIEW collection, then propagate to the asset.

    While a character is open for editing, the subsystem assembles a transient preview
    collection; edits must go there and be pushed back with on_edit_preview_collection
    (MetaHumanCharacterEditorSubsystem.h). One hair colour per character is applied to every
    groom (hair, brows, beard/moustache, lashes).
    """
    edit(ch)
    pc = sub.get_preview_collection(ch)
    inst = pc.get_editor_property("default_instance")
    chosen = {}
    for slot, rel in spec["grooms"].items():
        wi = unreal.load_asset(f"{GROOMS}/{rel}")
        if wi is None:
            log(f"missing groom {rel}")
            continue
        existing = list(pc.get_item_keys_for_wardrobe_item(wi))
        key = existing[0] if existing else pc.try_add_item_from_wardrobe_item(slot, wi)
        inst.set_single_slot_selection(slot, key)
        chosen[slot] = rel.split("/")[-1]
    for slot in GROOM_SLOTS:
        if slot not in spec["grooms"]:
            inst.set_single_slot_selection(slot, unreal.MetaHumanPaletteItemKey())   # no item
    sub.on_edit_preview_collection(ch)
    sub.assemble_for_preview(ch)
    colour = spec.get("hair_colour", {})
    n = 0
    for path in inst.get_instance_parameter_item_paths():
        names = {str(prm.name): prm for prm in inst.get_instance_parameters(item_path=path)}
        if "Melanin" not in names:
            continue                         # outfit and other non-groom items
        for pname, val in colour.items():
            if pname in names:
                names[pname].set_float(value=float(val))
        n += 1
    sub.on_edit_preview_collection(ch)
    sub.assemble_for_preview(ch)
    log(f"grooms {chosen}; colour {colour} on {n} groom items")


def author(names, recreate):
    cache, made = {}, []
    for name in names:
        spec = CHARACTERS[name]
        try:
            ch = create(name, spec, recreate)
            edit(ch)
            try:
                apply_face(ch, spec, cache)
                apply_body(ch, spec)
                apply_skin(ch, spec)
                apply_head_and_eyes(ch, spec)
                apply_grooms(ch, spec)
            finally:
                done(ch)
            save(ch)
            made.append(name)
            log(f"{name}: authored and saved")
        except Exception:
            log(f"{name}: FAILED\n" + traceback.format_exc())
    for a in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path(f"{SRC}/_Tmp", recursive=True):
        eas.delete_asset(str(a.package_name))
    return made


# ------------------------------------------------------------------ portraits (tick-driven)
ST = {"queue": [], "i": -1, "t": 0.0, "ch": None, "actor": None, "rt": None, "busy": False, "handle": None,
      "ticks": 0, "staged": False}


def stage():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    les.new_level("/Temp/L_MHPortrait_%d" % int(time.time()))
    sun = actors.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 400), unreal.Rotator(roll=0, pitch=-30, yaw=-115))
    sun.light_component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    sun.light_component.set_editor_property("intensity", 4.0)
    fill = actors.spawn_actor_from_class(unreal.PointLight, unreal.Vector(-120, 160, 175), unreal.Rotator())
    fill.point_light_component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    fill.point_light_component.set_editor_property("intensity", 300.0)
    sky = actors.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 300), unreal.Rotator())
    sc = sky.light_component
    sc.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    sc.set_editor_property("source_type", unreal.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
    sc.set_editor_property("cubemap", unreal.load_asset("/Engine/MapTemplates/Sky/DaylightAmbientCubemap.DaylightAmbientCubemap"))
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    ST["rt"] = unreal.RenderingLibrary.create_render_target2d(world, 768, 960, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)


def head_point(a):
    comps = list(a.get_components_by_class(unreal.SkeletalMeshComponent))
    body = next((c for c in comps if "body" in c.get_name().lower()), comps[0])
    face = next((c for c in comps if "face" in c.get_name().lower()), body)
    for comp in (face, body):
        if comp.does_socket_exist("head"):
            p = comp.get_socket_location("head")
            return unreal.Vector(p.x, p.y, p.z + 9.0)
    o, e, r = unreal.SystemLibrary.get_component_bounds(face)
    return unreal.Vector(o.x, o.y, o.z + e.z * 0.6)


def capture(name):
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    h = head_point(ST["actor"])
    shots = (("front", unreal.Vector(0, 1, 0), 85.0, 28.0, -4.0),
             ("three_quarter", unreal.Vector(0.6, 0.8, 0), 85.0, 28.0, -4.0),
             ("full", unreal.Vector(0.35, 0.94, 0), 380.0, 32.0, -75.0))
    for tag, d, dist, fov, dz in shots:
        tgt = unreal.Vector(h.x, h.y, h.z + dz)
        loc = tgt + d * dist
        cap = actors.spawn_actor_from_class(unreal.SceneCapture2D, loc, unreal.MathLibrary.find_look_at_rotation(loc, tgt))
        cc = cap.capture_component2d
        cc.set_editor_property("texture_target", ST["rt"])
        cc.set_editor_property("fov_angle", fov)
        cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        pp = cc.get_editor_property("post_process_settings")
        pp.set_editor_property("override_auto_exposure_method", True)
        pp.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
        pp.set_editor_property("override_auto_exposure_apply_physical_camera_exposure", True)
        pp.set_editor_property("auto_exposure_apply_physical_camera_exposure", False)
        pp.set_editor_property("override_auto_exposure_bias", True)
        pp.set_editor_property("auto_exposure_bias", -1.3)
        cc.set_editor_property("post_process_settings", pp)
        flush_rendering()
        cc.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, ST["rt"], OUT, f"{name}_{tag}.png")
        actors.destroy_actor(cap)
    log(f"portraits for {name}")


def flush_rendering():
    """Block until shaders are compiled and textures streamed (FunctionalTesting helper)."""
    try:
        unreal.AutomationLibrary.finish_loading_before_screenshot()
    except Exception as exc:
        log(f"finish_loading_before_screenshot unavailable: {exc}")


def start(i):
    name = ST["queue"][i]
    ch = unreal.load_asset(f"{SRC}/{name}")
    edit(ch)
    sub.assemble_for_preview(ch)     # rebuild the preview (grooms, outfit) from the saved asset
    ST["ch"], ST["actor"] = ch, sub.spawn_meta_human_actor(ch)
    # Read-back check after save and reopen: which grooms does the preview actually show?
    try:
        shown = {}
        for c in ST["actor"].get_components_by_class(unreal.GroomComponent):
            g = c.get_editor_property("groom_asset")
            shown[c.get_name()] = g.get_name() if g else None
        log(f"{name} grooms after reopen: {shown}")
    except Exception as exc:
        log(f"{name} read-back failed: {exc}")


def finish():
    unreal.unregister_slate_post_tick_callback(ST["handle"])
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def tick(dt):
    if ST["busy"]:
        return
    ST["busy"] = True
    ST["ticks"] += 1
    try:
        if not ST["staged"]:
            if ST["ticks"] > 3:
                stage()
                ST["staged"] = True
            return
        if ST["i"] < 0:
            ST["i"] = 0
            ST["t"] = time.time()
            start(0)
            ST["t"] = time.time()
            return
        wait = float(os.environ.get("WG_MH_FIRST_WAIT", "240")) if ST["i"] == 0 else float(os.environ.get("WG_MH_NEXT_WAIT", "90"))
        if time.time() - ST["t"] < wait:
            return
        capture(ST["queue"][ST["i"]])
        done(ST["ch"])
        ST["i"] += 1
        if ST["i"] >= len(ST["queue"]):
            finish()
            return
        ST["t"] = time.time()
        start(ST["i"])
        ST["t"] = time.time()
    except Exception:
        log("portrait FAILED\n" + traceback.format_exc())
        finish()
    finally:
        ST["busy"] = False


def main():
    os.makedirs(OUT, exist_ok=True)
    vpath = os.environ.get("WG_MH_VARIANTS", "")
    if vpath and os.path.exists(vpath):
        for vname, over in json.load(open(vpath)).items():
            spec = dict(CHARACTERS[over.pop("base")])
            spec.update(over)
            CHARACTERS[vname] = spec
    only = [n for n in os.environ.get("WG_MH_ONLY", "").split(",") if n]
    names = only or list(CHARACTERS)
    if os.environ.get("WG_MH_AUTHOR", "1") == "0":      # portraits only
        made = [n for n in names if eas.does_asset_exist(f"{SRC}/{n}")]
    else:
        made = author(names, os.environ.get("WG_MH_RECREATE", "0") == "1")
    with open(os.path.join(OUT, "authored.json"), "w") as fh:
        json.dump({"authored": made, "specs": {n: CHARACTERS[n] for n in made}}, fh, indent=1, default=str)
    if os.environ.get("WG_MH_CAPTURE", "1") == "1" and made:
        ST["queue"] = made
        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
        ST["handle"] = unreal.register_slate_post_tick_callback(tick)


main()
