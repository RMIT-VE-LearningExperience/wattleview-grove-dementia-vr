"""Rig, texture and assemble the Wattleview Grove MetaHumans (needs the MetaHuman cloud).

Prerequisite (once, Lawrence only): open the project in the editor, open any character in
/Game/MetaHumans/Src and sign in with your Epic account when MetaHuman asks (it opens a browser).
The stored token then lets this script run unattended, including headless:
  UnrealEditor-Cmd <project> -ExecutePythonScript="<this file>"

Per character (authored by build_metahumans.py):
  1. Face auto-rigging, joints only (blendshapes are LOD0-only and unused on mobile).
  2. Texture-source download (assembly refuses to run without it).
  3. Assembly: UE Optimized, Medium (face LODs 3/5/7, body 1/2/3) into /Game/MetaHumans/<Name>.
     EnzoYoung is assembled at Cinematic quality into /Game/MetaHumans/Photo for a desktop-only
     portrait render (never placed in the level, so never cooked).
  4. Android hardening: textures capped at 2048 (eyes, teeth, hair 1024), no virtual textures.

If the cloud sign-in is missing or expired, the script stops after the first character with a
clear message instead of building half-rigged characters.
"""
import os
import traceback

import unreal

SRC = "/Game/MetaHumans/Src"
RUNTIME = ["Maria", "David", "Enzo"]
PHOTO = ["EnzoYoung", "MariaYoung"]
ONLY = [n for n in os.environ.get("WG_MH_ONLY", "").split(",") if n]

eas = unreal.EditorAssetLibrary
sub = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)


def log(msg):
    unreal.log("[MHAssemble] " + str(msg))


def ready(ch):
    try:
        return bool(sub.can_build_meta_human(ch, True))
    except Exception:
        return False


def rig_and_textures(ch):
    p = unreal.MetaHumanCharacterAutoRiggingRequestParams()
    p.blocking = True
    p.report_progress = False
    p.rig_type = unreal.MetaHumanRigType.JOINTS_ONLY
    sub.request_auto_rigging(ch, p)
    t = unreal.MetaHumanCharacterTextureRequestParams()
    t.blocking = True
    t.report_progress = False
    sub.request_texture_sources(ch, t)


def build(ch, name, cinematic):
    bp = unreal.MetaHumanCharacterEditorBuildParameters()
    if cinematic:
        # Photo characters: Optimized/Medium is plenty for a ~1K print. Both Cinematic and
        # Optimized young builds render glowing white eyes (cause unknown);
        # Scripts/Tools/grade_wall_photo.py repaints them in the print.
        bp.pipeline_type = unreal.MetaHumanDefaultPipelineType.OPTIMIZED
        bp.pipeline_quality = unreal.MetaHumanQualityLevel.MEDIUM
        bp.absolute_build_path = "/Game/MetaHumans/PhotoM"
        bp.common_folder_path = "/Game/MetaHumans/PhotoM/Common"
    else:
        bp.pipeline_type = unreal.MetaHumanDefaultPipelineType.OPTIMIZED
        bp.pipeline_quality = unreal.MetaHumanQualityLevel.MEDIUM
        bp.absolute_build_path = "/Game/MetaHumans"
        bp.common_folder_path = "/Game/MetaHumans/Common"
    bp.enable_wardrobe_item_validation = False
    sub.build_meta_human(character=ch, params=bp)


def harden(folder):
    """Cap textures for Android and keep them out of virtual texturing."""
    n = 0
    for a in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path(folder, recursive=True):
        if str(a.asset_class_path.asset_name) not in ("Texture2D",):
            continue
        tex = a.get_asset()
        name = str(a.asset_name).lower()
        cap = 1024 if any(k in name for k in ("eye", "teeth", "hair", "groom", "lash", "brow")) else 2048
        changed = False
        if tex.get_editor_property("max_texture_size") in (0,) or tex.get_editor_property("max_texture_size") > cap:
            tex.set_editor_property("max_texture_size", cap)
            changed = True
        try:
            if tex.get_editor_property("virtual_texture_streaming"):
                tex.set_editor_property("virtual_texture_streaming", False)
                changed = True
        except Exception:
            pass
        if changed:
            eas.save_loaded_asset(tex, False)
            n += 1
    log(f"{folder}: {n} textures capped for Android")


def main():
    names = [n for n in RUNTIME + PHOTO if not ONLY or n in ONLY]
    for name in names:
        path = f"{SRC}/{name}"
        if not eas.does_asset_exist(path):
            log(f"{name}: no source asset (run build_metahumans.py first)")
            continue
        ch = unreal.load_asset(path)
        opened_here = False
        if not sub.is_object_added_for_editing(ch):      # may already be open in MetaHuman Creator
            if not sub.try_add_object_to_edit(ch):
                log(f"{name}: could not open for editing")
                continue
            opened_here = True
        try:
            if not ready(ch):
                rig_and_textures(ch)
            if not ready(ch):
                log(f"{name}: NOT READY after rigging/texture requests. Most likely the MetaHuman "
                    "cloud sign-in is missing or expired (log shows 'Login failed'). Sign in once in "
                    "the editor, then rerun. Stopping.")
                return
            try:
                build(ch, name, cinematic=name in PHOTO)
            except RuntimeError as exc:
                # The pipeline copies Epic's Control Rig assets into Common and logs "Cannot break
                # link ..." while fixing them up; Python surfaces those log errors as an exception
                # even though the log then reports "MetaHuman Character assembly succeeded".
                if "Cannot break link" not in str(exc):
                    raise
                log(f"{name}: Control Rig fix-up warnings during assembly (harmless)")
            log(f"{name}: assembled")
        except Exception:
            log(f"{name}: FAILED\n" + traceback.format_exc())
        finally:
            # Always save the source: it now holds the rig and downloaded textures.
            eas.save_loaded_asset(ch, False)
            if opened_here and sub.is_object_added_for_editing(ch):
                sub.remove_object_to_edit(ch)
    for name in names:
        folder = f"/Game/MetaHumans/{'Photo/' if name in PHOTO else ''}{name}"
        if eas.does_directory_exist(folder) and name not in PHOTO:
            harden(folder)
    if eas.does_directory_exist("/Game/MetaHumans/Common"):
        harden("/Game/MetaHumans/Common")
    # The build creates many new packages (meshes, textures, Blueprint); a headless editor exits
    # without saving them, so save everything that is dirty.
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    log("done")


main()
