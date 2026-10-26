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
# Seated eye positions sit above the seated stand-in's hips (AS_Placeholder_Sit puts the
# hips 13 cm behind the actor root, eyes ~64 cm above the hips).
MARIA_SEATED_EYE = (333, 200, 117)
VIEWPOINTS = {
    "Anchor_David": [
        (0.0,   (105, 40, 165), (300, 150, 130)),     # 0:00 enters at the door with the clipboard
        (14.0,  (332, 112, 165), (355, 60, 150)),     # 0:14 beside Maria at the photograph
        (34.0,  (372, 145, 165), MARIA_SEATED_EYE),   # 0:34 standing at her chair, table
        (240.0, (368, 268, 118), MARIA_SEATED_EYE),   # 4:00 pulled a chair in, sits close
        (288.0, (120, 70, 165), (340, 200, 110)),     # 4:48 at the door, leaving
    ],
    "Anchor_Maria": [
        (0.0,   (355, 60, 155), (355, 0, 147)),       # 0:00 standing at the photograph
        (35.0,  MARIA_SEATED_EYE, (700, 200, 90)),    # 0:35 seated, facing the garden window
    ],
    "Anchor_Corner": [
        (0.0,   (480, 25, 225), (300, 230, 90)),      # fixed overview from the window corner
    ],
}

# Stand-in blocking: (time_s, (x, y, z), facing_deg, interp). Floor-level root positions.
# facing_deg is the direction the character faces (0 = +X, toward the window). The UE5
# mannequin mesh faces +Y, so MESH_YAW_OFFSET is added to get the actor yaw.
MESH_YAW_OFFSET = -90.0
BLOCKING = {
    "David_StandIn": [
        (0.0,   (105, 45, 0), 45, CONST),
        (6.0,   (105, 45, 0), 45, LINEAR),            # reads the handover, then walks in
        (14.0,  (330, 112, 0), -62, CONST),           # greets Maria at the photograph
        (24.0,  (330, 112, 0), -62, LINEAR),          # guides her to the table
        (34.0,  (372, 145, 0), 115, CONST),           # stands at her chair
        (240.0, (365, 260, 0), -113, CONST),          # sits in the pulled-in chair (4:00)
        (282.0, (365, 260, 0), -113, LINEAR),         # stands to leave
        (292.0, (110, 55, 0), 200, LINEAR),           # leaves (4:42-4:52)
        (298.0, (105, -60, 0), 270, CONST),           # out through the door
    ],
    "Maria_StandIn": [
        (0.0,   (355, 68, 0), -90, CONST),            # at the photograph, facing it
        (24.0,  (355, 68, 0), -90, LINEAR),
        (34.0,  (346, 200, 0), 0, CONST),             # seated at the table, facing the window
    ],
    "Gardener_StandIn": [
        (0.0,   (745, 300, -20), 180, LINEAR),        # faces the house while working
        (120.0, (745, 330, -20), 160, LINEAR),
        (300.0, (745, 280, -20), 190, LINEAR),
    ],
}

# Animation sections per stand-in: (start_s, end_s, anim). Sections loop to fill.
IDLE = "/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle.MM_Idle"
WALK = "/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd.MF_Unarmed_Walk_Fwd"
SIT = "/Game/Wattleview/Animations/AS_Placeholder_Sit.AS_Placeholder_Sit"
ANIMS = {
    "David_StandIn": [(0, 6, IDLE), (6, 14, WALK), (14, 24, IDLE), (24, 34, WALK), (34, 240, IDLE),
                      (240, 282, SIT), (282, 298, WALK), (298, 300, IDLE)],
    "Maria_StandIn": [(0, 24, IDLE), (24, 34, WALK), (34, 300, SIT)],
    "Gardener_StandIn": [(0, 300, IDLE)],
}

# Props that move: label of the root actor, the label prefix of parts to attach to it, and
# keys (time_s, (x, y, z), yaw, interp) for the root. David pulls this chair in at 4:00.
PROP_MOVES = {
    "Chair_Second_Seat": ("Chair_Second_", [
        (0.0,   (400, 268, 46), -90, CONST),
        (236.0, (400, 268, 46), -90, LINEAR),
        (240.0, (370, 272, 46), -113, CONST),
    ]),
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
    # TV (both views, not gated by MariaView): David turns it down, then off (~1:10).
    "TVOn":     [(0, 1.0), (68, 1.0), (71, 0.4), (74, 0.4), (75, 0.0), (300, 0.0)],
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
    # Keep existing parameters (materials reference them by internal ID); only add missing.
    params = list(mpc.get_editor_property("scalar_parameters"))
    have = {str(p.get_editor_property("parameter_name")) for p in params}
    added = False
    for name in ["MariaView"] + list(PERCEPTION.keys()):
        if name not in have:
            p = unreal.CollectionScalarParameter()
            p.set_editor_property("parameter_name", name)
            p.set_editor_property("default_value", 0.0)
            params.append(p)
            added = True
    if added:
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


def key_transform(chs, t, loc, yaw, interp, scale=(1.0, 1.0, 1.0)):
    for i, v in enumerate(loc):
        key(chs[i], t, v, interp)
    key(chs[3], t, 0.0, interp)   # roll
    key(chs[4], t, 0.0, interp)   # pitch
    key(chs[5], t, yaw, interp)   # yaw
    for i, v in zip((6, 7, 8), scale):
        key(chs[i], t, v, interp)


def add_anim_sections(binding, sections):
    if not sections:
        return 0
    track = binding.add_track(unreal.MovieSceneSkeletalAnimationTrack)
    for start, end, path in sections:
        anim = unreal.load_asset(path)
        if anim is None:
            log(f"missing animation {path}")
            continue
        sec = track.add_section()
        sec.set_range_seconds(float(start), float(end))
        params = sec.get_editor_property("params")
        params.set_editor_property("animation", anim)
        sec.set_editor_property("params", params)
    return len(sections)


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
        binding = seq.add_possessable(actor)
        chs = transform_channels(binding)
        for t, loc, facing, interp in keys:
            key_transform(chs, t, loc, facing + MESH_YAW_OFFSET, interp)
        n_anim = add_anim_sections(binding, ANIMS.get(label, []))
        log(f"{label}: {len(keys)} blocking keys, {n_anim} anim sections")

    # Moving props (parts attached to a root so the whole chair moves).
    for root_label, (prefix, keys) in PROP_MOVES.items():
        root = find_actor(root_label)
        if root is None:
            log(f"missing {root_label}; skipped")
            continue
        root.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        for part in actors.get_all_level_actors():
            lbl = part.get_actor_label()
            if lbl.startswith(prefix) and lbl != root_label:
                part.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)
                if part.get_attach_parent_actor() != root:
                    part.attach_to_actor(root, "", unreal.AttachmentRule.KEEP_WORLD,
                                         unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
        chs = transform_channels(seq.add_possessable(root))
        scale = root.get_actor_scale3d()
        for t, loc, yaw, interp in keys:
            key_transform(chs, t, loc, yaw, interp, (scale.x, scale.y, scale.z))
        log(f"{root_label}: {len(keys)} prop keys")

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
