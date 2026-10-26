"""Replace the greybox room in L_ResidentRoom with the imported Blender assets.

Reads SourceArt/Room/placement.json (the same table the Blender overlap check uses) and, when
present, SourceArt/Room/Previews/Assembly/report.json for the exact resting heights that
Tools/assemble_room.py computed (props on the table, TV on its cabinet, chairs on the rug...).

  * Removes greybox StaticMeshActors (outliner folders Room* and Garden) and any previous
    dressing (folder Env*). Cameras, characters, lights and Story actors are untouched.
  * Spawns one StaticMeshActor per placement entry, labelled with the entry's label so the
    story scripts find them (Hairbrush, Glass, Chair_Second, TV_Screen, CeilingFan ...).
  * Overlay entries (Memory_*) are left to build_perception_layer.py.

Order after a fresh build_resident_room.py:
  import_room_assets.py -> build_room_dressing.py -> build_story_sequence.py ->
  build_perception_layer.py -> build_story_director.py -> build_gaze_start.py -> build_lighting.py
"""
import json
import os

import unreal

PROJECT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ROOM = os.path.join(PROJECT, "SourceArt", "Room")
MAP_PATH = "/Game/Wattleview/Maps/L_ResidentRoom"
MESH_DIR = "/Game/Wattleview/Environment/Meshes"
GARDEN = {"SM_Lawn", "SM_FlowerBed", "SM_GardenTree_A", "SM_GardenTree_B", "SM_Shrub", "SM_Fence", "SM_GardenBench"}
MEMORY = {"SM_TomatoPlant", "SM_BasilPot", "SM_FigTree", "SM_GardenHose"}
MOVABLE = {"Hairbrush", "Glass", "Chair_Second", "CeilingFan"}   # keyed on the story timeline
SILL_TOP = 80.0

acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.EditorAssetLibrary


def log(msg):
    unreal.log("[Dressing] " + msg)


def mesh_path(name):
    sub = "Garden" if name in GARDEN else "Memory" if name in MEMORY else "Sky" if name == "SM_SkyDome" else "Room"
    return f"{MESH_DIR}/{sub}/{name}"


def ensure_level():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None or world.get_path_name().split(".")[0] != MAP_PATH:
        les.load_level(MAP_PATH)


def clear_old():
    n = 0
    for a in acts.get_all_level_actors():
        folder = str(a.get_folder_path())
        if not isinstance(a, unreal.StaticMeshActor):
            continue
        if folder.startswith("Room") or folder.startswith("Garden") or folder.startswith("Env"):
            acts.destroy_actor(a)
            n += 1
    log(f"removed {n} greybox/old dressing actors")


def folder_for(kind):
    return {"shell": "Env/Shell", "furniture": "Env/Furniture", "soft": "Env/Furniture",
            "prop": "Env/Props", "wall": "Env/Wall", "exterior": "Env/Garden", "sky": "Env/Sky"}.get(kind, "Env/Other")


def support_top(label, placed):
    if label == "WindowFrame":
        return SILL_TOP
    a = placed.get(label)
    if a is None:
        return None
    origin, extent = a.get_actor_bounds(False)
    return origin.z + extent.z


def build():
    ensure_level()
    cfg = json.load(open(os.path.join(ROOM, "placement.json")))
    gap = cfg.get("gap_cm", 0.2)
    rep_path = os.path.join(ROOM, "Previews", "Assembly", "report.json")
    rest_z = json.load(open(rep_path)).get("rest_on_z", {}) if os.path.exists(rep_path) else {}
    if not rest_z:
        log("no assembly report: resting heights computed from bounds (run Tools/assemble_room.py for exact values)")
    clear_old()

    placed, missing = {}, []
    pieces = [p for p in cfg["pieces"] if p.get("kind") != "overlay"]
    pending = list(pieces)
    for _ in range(6):
        for p in list(pending):
            sup, same = p.get("rest_on"), p.get("same_as")
            if same and same not in placed:
                continue
            if sup and sup not in placed and sup != "WindowFrame" and any(q["label"] == sup for q in pieces):
                continue
            pending.remove(p)
            path = mesh_path(p["mesh"])
            if not eas.does_asset_exist(path):
                missing.append(p["mesh"])
                continue
            mesh = unreal.load_asset(path)
            if same:
                ref = placed[same]
                loc, rot = ref.get_actor_location(), ref.get_actor_rotation()
            else:
                x, y, z = p["loc"]
                if sup:
                    if p["label"] in rest_z:
                        z = rest_z[p["label"]]
                    else:
                        top = support_top(sup, placed)
                        if top is not None:
                            z = top + gap - mesh.get_bounding_box().min.z
                loc = unreal.Vector(x, y, z)
                rot = unreal.Rotator(roll=0.0, pitch=0.0, yaw=float(p.get("yaw", 0.0)))
            a = acts.spawn_actor_from_object(mesh, loc, rot)
            a.set_actor_label(p["label"])
            a.set_folder_path(folder_for(p.get("kind")))
            c = a.static_mesh_component
            c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
            c.set_mobility(unreal.ComponentMobility.MOVABLE if p["label"] in MOVABLE else unreal.ComponentMobility.STATIC)
            if p.get("kind") == "sky":
                c.set_cast_shadow(False)
                c.set_editor_property("affect_distance_field_lighting", False)
            placed[p["label"]] = a
        if not pending:
            break
    for p in pending:
        log(f"could not place {p['label']} (support missing)")
    if missing:
        log("missing meshes (not imported yet): " + ", ".join(sorted(set(missing))))
    les.save_current_level()
    log(f"placed {len(placed)} pieces and saved")


build()
