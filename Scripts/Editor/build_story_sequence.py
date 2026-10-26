"""Build the Story V2 master timeline: LS_Story (5:00 @ 30 fps).

One timeline serves all three viewpoints. It drives:
  * Viewer anchors (Anchor_David / Anchor_Maria / Anchor_Corner): eye-height points the
    player pawn is attached to. Keys are CONSTANT, so a viewpoint change is a cut.
    Head rotation always comes from the headset; anchors carry position and yaw only.
  * Placeholder character blocking (Maria, David, gardener stand-ins).
  * MPC_Perception scalars for Maria's perception layer. The director multiplies them by
    MariaView (1 only in Maria's viewpoint), so the same keys are inert in the other two.

Beat times follow Docs/Production/Story_V2_VR_Breakdown.md (hairbrush version).

Run inside the open editor (MCP execute_python / Python console) or headless:
  UnrealEditor-Cmd.exe <project>.uproject -ExecutePythonScript="<this file>" -nosplash
Re-runnable: clears and refills the sequence; updates anchors and MPC in place.
"""
import math

import unreal

MAP_PATH = "/Game/Wattleview/Maps/L_ResidentRoom"
SEQ_DIR = "/Game/Wattleview/Cinematics"
SEQ_NAME = "LS_Story"
MPC_PATH = "/Game/Wattleview/Materials/MPC_Perception"
FPS = 30
DURATION = 300.0

eas = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
CONST = unreal.MovieSceneKeyInterpolation.CONSTANT
LINEAR = unreal.MovieSceneKeyInterpolation.LINEAR
AUTO = unreal.MovieSceneKeyInterpolation.AUTO


def log(msg):
    unreal.log("[Seq] " + msg)


def yaw_to(src, dst):
    return math.degrees(math.atan2(dst[1] - src[1], dst[0] - src[0]))


# ------------------------------------------------------------------ timeline data
# Viewer anchors: (time_s, (x, y, eye_z), look_at) -> yaw derived from look_at.
VIEWPOINTS = {
    "Anchor_David": [
        (0.0,   (105, 40, 165), (300, 150, 130)),   # 0:00 enters at the door with the clipboard
        (14.0,  (360, 150, 165), (335, 200, 100)),  # 0:14 arrives beside Maria at the table
        (240.0, (348, 262, 115), (335, 200, 110)),  # 4:00 pulls a chair in, sits close
        (288.0, (120, 70, 165), (330, 200, 110)),   # 4:48 at the door, leaving
    ],
    "Anchor_Maria": [
        (0.0,   (355, 60, 155), (355, 0, 147)),     # 0:00 standing at the photograph
        (35.0,  (340, 200, 115), (700, 200, 90)),   # 0:35 seated, facing the garden window
    ],
    "Anchor_Corner": [
        (0.0,   (480, 25, 225), (300, 230, 90)),    # fixed overview from the window corner
    ],
}

# Stand-in blocking: (time_s, (x, y, z), yaw, interp). Floor-level positions.
BLOCKING = {
    "David_StandIn": [
        (0.0,   (105, 40, 0), 45, CONST),
        (6.0,   (105, 40, 0), 45, LINEAR),          # reads the handover, then walks in
        (14.0,  (300, 105, 0), 30, LINEAR),
        (20.0,  (372, 140, 0), 130, CONST),         # guides Maria to the table
        (236.0, (372, 140, 0), 130, LINEAR),
        (240.0, (362, 265, 0), -105, CONST),        # sits close (4:00)
        (282.0, (362, 265, 0), -105, LINEAR),
        (292.0, (110, 50, 0), 200, LINEAR),         # leaves (4:42-4:52)
        (298.0, (105, -60, 0), 270, CONST),         # out through the door
    ],
    "Maria_StandIn": [
        (0.0,   (355, 60, 0), -90, CONST),          # at the photograph
        (24.0,  (355, 60, 0), -90, LINEAR),
        (34.0,  (335, 200, 0), 0, CONST),           # led to her table chair
    ],
    "Gardener_StandIn": [
        (0.0,   (745, 300, -20), 180, LINEAR),
        (120.0, (745, 330, -20), 200, LINEAR),      # drifts along the bed while working
        (300.0, (745, 280, -20), 170, LINEAR),
    ],
}

# Perception layer (Maria's view). Values 0..1; keyed AUTO for smooth ramps.
PERCEPTION = {
    # Whole-room softness; photo stays sharp (rendered separately).
    "Softness": [(0, 0.8), (45, 0.8), (100, 0.6), (210, 0.7), (240, 0.4), (275, 0.0), (300, 0.0)],
    # Warmth: +1 warm, 0 neutral, negative = cool (3:15-4:00 corridor overload).
    "Warmth":   [(0, 0.3), (195, 0.3), (205, -0.6), (238, -0.6), (255, 0.4), (275, 0.8), (300, 0.8)],
    # Darkened vision edges, peaks with the corridor noise.
    "EdgeDark": [(0, 0.15), (195, 0.15), (205, 0.8), (238, 0.8), (255, 0.2), (275, 0.0), (300, 0.0)],
    # Enzo over David: colours from 0:45, firms up from 1:40, full face at 4:30.
    "EnzoBlend": [(0, 0.0), (60, 0.0), (90, 0.3), (100, 0.35), (140, 0.55), (165, 0.45), (180, 0.6),
                  (205, 0.4), (240, 0.7), (270, 0.85), (276, 1.0), (300, 1.0)],
    # Glow on the photograph (0:00-0:45) and halo on the gardener (0:45-1:40).
    "PhotoGlow":    [(0, 1.0), (40, 1.0), (50, 0.2), (300, 0.2)],
    "GardenerHalo": [(0, 0.0), (45, 0.0), (52, 1.0), (95, 1.0), (105, 0.0), (300, 0.0)],
    # Backyard memory overlay (2:30-3:15).
    "Memory":   [(0, 0.0), (152, 0.0), (158, 1.0), (186, 1.0), (189, 0.0), (300, 0.0)],
    # Brush looming (1:40-2:30): scale boost on the brush in her view.
    "BrushLoom": [(0, 0.0), (102, 0.0), (110, 1.0), (140, 1.0), (148, 0.0), (300, 0.0)],
}


# ------------------------------------------------------------------ helpers
def find_actor(label):
    for a in actors.get_all_level_actors():
        if a.get_actor_label() == label:
            return a
    return None


def ensure_anchor(label, loc, yaw):
    a = find_actor(label)
    if a is None:
        a = actors.spawn_actor_from_class(unreal.TargetPoint, unreal.Vector(*loc), unreal.Rotator(0, 0, yaw))
        a.set_actor_label(label)
    a.set_actor_location_and_rotation(unreal.Vector(*loc), unreal.Rotator(0, 0, yaw), False, False)
    a.set_folder_path("Story/Anchors")
    a.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    tags = [unreal.Name(label)]
    a.set_editor_property("tags", tags)
    return a


def ensure_mpc():
    if eas.does_asset_exist(MPC_PATH):
        mpc = unreal.load_asset(MPC_PATH)
    else:
        mpc = tools.create_asset("MPC_Perception", MPC_PATH.rsplit("/", 1)[0],
                                 unreal.MaterialParameterCollection, unreal.MaterialParameterCollectionFactoryNew())
    params = []
    for name in ["MariaView"] + list(PERCEPTION.keys()):
        p = unreal.CollectionScalarParameter()
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", 0.0)
        params.append(p)
    mpc.set_editor_property("scalar_parameters", params)
    eas.save_loaded_asset(mpc)
    return mpc


def transform_channels(binding):
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    section = track.add_section()
    section.set_range_seconds(0.0, DURATION)
    return section.get_all_channels()


def key(channel, t, v, interp):
    channel.add_key(unreal.FrameNumber(int(round(t * FPS))), float(v), 0.0,
                    unreal.MovieSceneTimeUnit.DISPLAY_RATE, interp)


def key_transform(chs, t, loc, yaw, interp):
    for i, v in enumerate(loc):
        key(chs[i], t, v, interp)
    key(chs[3], t, 0.0, interp)   # roll
    key(chs[4], t, 0.0, interp)   # pitch
    key(chs[5], t, yaw, interp)   # yaw
    for i in (6, 7, 8):
        key(chs[i], t, 1.0, interp)


# ------------------------------------------------------------------ build
def build():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    current = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if current is None or current.get_path_name().split(".")[0] != MAP_PATH:
        les.load_level(MAP_PATH)

    mpc = ensure_mpc()

    # Reuse the asset if it exists (BP_StoryDirector references it); clear it out.
    seq_path = f"{SEQ_DIR}/{SEQ_NAME}"
    if eas.does_asset_exist(seq_path):
        seq = unreal.load_asset(seq_path)
        for binding in seq.get_bindings():
            binding.remove()
        for track in seq.get_tracks():
            seq.remove_track(track)
    else:
        seq = tools.create_asset(SEQ_NAME, SEQ_DIR, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    seq.set_display_rate(unreal.FrameRate(FPS, 1))
    seq.set_playback_start_seconds(0.0)
    seq.set_playback_end_seconds(DURATION)

    # Viewer anchors.
    for label, keys in VIEWPOINTS.items():
        t0, loc0, look0 = keys[0]
        anchor = ensure_anchor(label, loc0, yaw_to(loc0, look0))
        chs = transform_channels(seq.add_possessable(anchor))
        for t, loc, look in keys:
            key_transform(chs, t, loc, yaw_to(loc, look), CONST)
        log(f"{label}: {len(keys)} viewpoint keys")

    # Character blocking.
    for label, keys in BLOCKING.items():
        actor = find_actor(label)
        if actor is None:
            log(f"missing {label}; skipped")
            continue
        actor.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        tags = [unreal.Name("Body_" + label.split("_")[0])]
        actor.set_editor_property("tags", tags)
        chs = transform_channels(seq.add_possessable(actor))
        for t, loc, yaw, interp in keys:
            key_transform(chs, t, loc, yaw, interp)
        log(f"{label}: {len(keys)} blocking keys")

    # Perception parameters.
    track = seq.add_track(unreal.MovieSceneMaterialParameterCollectionTrack)
    track.set_editor_property("mpc", mpc)
    section = track.add_section()
    section.set_range_seconds(0.0, DURATION)
    for name, keys in PERCEPTION.items():
        for t, v in keys:
            section.add_scalar_parameter_key(unreal.Name(name), unreal.FrameNumber(int(t * FPS)), float(v))
    log(f"MPC track: {len(PERCEPTION)} parameters")

    eas.save_loaded_asset(seq)
    les.save_current_level()
    log(f"saved {seq_path} and {MAP_PATH}")


build()
