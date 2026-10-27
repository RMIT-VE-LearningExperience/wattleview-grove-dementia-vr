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
DURATION = 300.0   # cinematic length; build() replaces it with the paced length

# ------------------------------------------------------------------ pacing
# All times in the tables below are CINEMATIC times (the Story V2 script, 5:00). The VR
# experience is much slower and seen from the characters' eyes, so build() maps every time
# through a piecewise-linear beat map. Fades and pose blends keep fixed real-time lengths;
# walk play rates are rescaled so the feet stay matched to the distance covered.
# PACING = "cinematic" reproduces the 5:00 cut from the same data.
PACING = globals().get("PACING", "vr")
BEATS_CINEMATIC = [0, 45, 100, 150, 195, 240, 270, 300]
BEATS_VR = [0, 90, 170, 235, 295, 360, 410, 470]   # ~7:50. 0:00-0:45 gets the most room:
#                                                   reading the handover, looking around,
#                                                   noticing the bruise.


def paced(t):
    """Map a cinematic time (s) to the active pacing."""
    if PACING != "vr":
        return float(t)
    b0, b1 = BEATS_CINEMATIC, BEATS_VR
    if t <= b0[0]:
        return float(b1[0])
    for i in range(1, len(b0)):
        if t <= b0[i]:
            f = (t - b0[i - 1]) / (b0[i] - b0[i - 1])
            return b1[i - 1] + f * (b1[i] - b1[i - 1])
    return b1[-1] + (t - b0[-1])

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
# Every key after t=0 is a cut; build() wraps each cut in a fade to black (FADE_*), the VR
# comfort convention for teleports. Keep cuts few: Lawrence found them uncomfortable.
# Seated eye positions sit above the seated stand-in's hips (AS_Placeholder_Sit puts the
# hips 13 cm behind the actor root, eyes ~64 cm above the hips).
MARIA_SEATED_EYE = (333, 200, 117)
VIEWPOINTS = {
    "Anchor_David": [
        (0.0,   (105, 40, 165), (300, 150, 130)),     # 0:00 enters at the door with the clipboard
        (9.5,   (332, 112, 165), (355, 60, 150)),     # 0:09 beside Maria at the photograph; from
                                                      #      here he also sees her at the table
        (240.0, (368, 268, 118), MARIA_SEATED_EYE),   # 4:00 pulled a chair in, sits close
        (288.0, (120, 70, 165), (340, 200, 110)),     # 4:48 at the door, leaving
    ],
    "Anchor_Maria": [
        (0.0,   (355, 60, 155), (355, 0, 147)),       # 0:00 standing at the photograph
        (31.0,  MARIA_SEATED_EYE, (700, 200, 90)),    # 0:31 seated, facing the garden window
    ],
    "Anchor_Corner": [
        (0.0,   (80, 330, 225), (300, 140, 100)),     # south-east corner: door, table, window
    ],
}
FADE_PARAM = {"Anchor_David": "FadeDavid", "Anchor_Maria": "FadeMaria", "Anchor_Corner": "FadeCorner"}
FADE_OUT, FADE_HOLD, FADE_IN = 0.4, 0.15, 0.45   # seconds: to black, held black, back
INTRO_FADE, OUTRO_FADE = 1.5, 2.0

# Stand-in blocking: (time_s, (x, y, z), facing_deg, interp). Floor-level root positions.
# facing_deg is the direction the character faces (0 = +X, toward the window). The UE5
# mannequin mesh faces +Y, so MESH_YAW_OFFSET is added to get the actor yaw.
MESH_YAW_OFFSET = -90.0
# Ceiling fan speed: a gentle low setting (about 30 rpm); fast blades flicker in VR.
FAN_DEG_PER_SECOND = 180.0
BLOCKING = {
    "David_StandIn": [
        (0.0,   (105, 45, 0), 45, CONST),
        (6.0,   (105, 45, 0), 45, LINEAR),            # reads the handover, then walks in
        (9.0,   (330, 112, 0), -62, CONST),           # greets Maria at the photograph
        (26.0,  (330, 112, 0), -62, LINEAR),          # follows as she walks to the table
        (28.5,  (372, 145, 0), 115, CONST),           # stands at her chair
        (238.0, (372, 145, 0), 115, LINEAR),
        (240.0, (365, 260, 0), -113, CONST),          # sits in the pulled-in chair (4:00)
        (284.0, (365, 260, 0), -113, LINEAR),         # stands to leave
        (286.0, (285, 265, 0), 180, LINEAR),          # steps behind Maria's chair, not through it
        (288.5, (110, 55, 0), 230, LINEAR),           # walks to the door
        (290.5, (105, -60, 0), 270, CONST),           # out through the door
    ],
    "Maria_StandIn": [
        (0.0,   (355, 68, 0), -90, CONST),            # at the photograph, facing it
        (24.0,  (355, 68, 0), -90, LINEAR),           # led to the table, slowly
        (26.3,  (378, 115, 0), 30, LINEAR),           # curves away from David (keeps >40 cm)
        (28.5,  (346, 200, 0), 0, CONST),             # at her chair; sits from 28.5
    ],
    "Gardener_StandIn": [
        (0.0,   (745, 460, -20), 190, LINEAR),        # east end of the bed, faces the house;
        (120.0, (745, 480, -20), 170, LINEAR),        # ~30 deg from the TV as Maria sees them
        (300.0, (745, 455, -20), 195, LINEAR),
    ],
}

# Animation sections per stand-in: (start_s, end_s, anim, play_rate). Sections loop to fill
# and overlap by ANIM_BLEND seconds with eased weights, so poses blend instead of snapping.
# Walk rates: AS_Placeholder_Walk covers ~300 cm/s at rate 1; rate = cm_per_s / 300.
IDLE = "/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle.MM_Idle"
WALK = "/Game/Wattleview/Animations/AS_Placeholder_Walk.AS_Placeholder_Walk"
SIT = "/Game/Wattleview/Animations/AS_Placeholder_Sit.AS_Placeholder_Sit"
ANIM_BLEND = 0.6
ANIMS = {
    "David_StandIn": [(0, 6, IDLE, 1.0), (6, 9, WALK, 0.26), (9, 26, IDLE, 1.0), (26, 28.5, WALK, 0.12),
                      (28.5, 238, IDLE, 1.0), (238, 240, WALK, 0.2), (240, 284, SIT, 1.0),
                      (284, 290.5, WALK, 0.26), (290.5, 300, IDLE, 1.0)],
    "Maria_StandIn": [(0, 24, IDLE, 1.0), (24, 28.5, WALK, 0.12), (28.5, 300, SIT, 1.0)],
    "Gardener_StandIn": [(0, 300, IDLE, 1.0)],
}

# Props that move: label of the root actor, the label prefix of parts to attach to it, and
# keys (time_s, (x, y, z), yaw, interp) for the root. David pulls this chair in at 4:00.
PROP_MOVES = {
    # Dressed room: one Chair_Second actor (pivot on the rug). Greybox fallback: the
    # Chair_Second_Seat root with its parts. Key heights are shifted to the actor's real
    # resting height at build time, so only relative z matters here.
    "Chair_Second": ("__none__", [
        (0.0,   (400, 268, 0), -90, CONST),
        (236.0, (400, 268, 0), -90, LINEAR),
        (240.0, (370, 272, 0), -113, CONST),
    ]),
    "Hairbrush": ("__none__", [
        (0.0,   (372, 182, 76.5), 20, CONST),
        (100.0, (372, 182, 76.5), 20, LINEAR),
        (106.0, (350, 196, 112), 70, LINEAR),     # 1:46 brought toward her head
        (110.0, (352, 194, 108), 70, LINEAR),     # 1:50 she blocks it with her sore hand
        (113.0, (368, 178, 92), 40, LINEAR),      # pulled back
        (200.0, (368, 178, 92), 40, LINEAR),
        (207.0, (350, 196, 112), 70, LINEAR),     # 3:27 back to brushing her hair
        (232.0, (350, 196, 112), 70, LINEAR),
        (238.0, (382, 186, 76.5), 20, CONST),     # 3:58 set aside on the table
    ]),
    "Glass": ("__none__", [
        (0.0,   (378, 225, 80.5), 0, CONST),
        (158.0, (378, 225, 80.5), 0, LINEAR),
        (161.0, (359, 208, 80.5), 0, CONST),      # 2:41 slid toward her (stays on the 47.5 cm top)
        (170.0, (352, 210, 80.5), 0, LINEAR),
        (171.0, (380, 236, 80.5), 0, CONST),      # 2:51 pushed away
    ]),
}

# Perception layer (Maria's view). Values 0..1; keyed AUTO for smooth ramps.
PERCEPTION = {
    # Whole-room softness; photo stays sharp (rendered separately).
    # (the 275-277.6 pulse hides the moment David becomes Enzo in her view; see build_story_director)
    "Softness": [(0, 0.8), (45, 0.8), (100, 0.6), (210, 0.7), (240, 0.4), (274.8, 0.0), (275.6, 0.55),
                 (276.6, 0.55), (277.6, 0.0), (300, 0.0)],
    # Warmth: +1 warm, 0 neutral, negative = cool (3:15-4:00 corridor overload).
    "Warmth":   [(0, 0.3), (195, 0.3), (205, -0.6), (238, -0.6), (255, 0.4), (275, 0.8), (300, 0.8)],
    # Darkened vision edges, peaks with the corridor noise.
    "EdgeDark": [(0, 0.15), (28.8, 0.15), (29.2, 0.9), (30.8, 0.15),       # pain as she sits
                 (109.6, 0.15), (110.0, 0.9), (111.5, 0.15),                # pain blocking the brush
                 (195, 0.15), (205, 0.8), (238, 0.8), (255, 0.2), (275, 0.0), (300, 0.0)],
    # Enzo over David: colours from 0:45, firms up from 1:40, full face at 4:30.
    "EnzoBlend": [(0, 0.0), (60, 0.0), (90, 0.3), (100, 0.35), (140, 0.55), (165, 0.45), (180, 0.6),
                  (205, 0.4), (240, 0.7), (270, 0.85), (276, 1.0), (300, 1.0)],
    # Glow on the photograph (0:00-0:45) and halo on the gardener (0:45-1:40).
    "PhotoGlow":    [(0, 1.0), (40, 1.0), (50, 0.2), (300, 0.2)],
    "GardenerHalo": [(0, 0.0), (45, 0.0), (52, 1.0), (95, 1.0), (105, 0.0), (300, 0.0)],
    # Backyard memory overlay (2:30-3:15).
    "Memory":   [(0, 0.0), (152, 0.0), (158, 1.0), (169, 1.0), (172, 0.0), (300, 0.0)],
    # Brush looming (1:40-2:30): scale boost on the brush in her view.
    "BrushLoom": [(0, 0.0), (102, 0.0), (110, 1.0), (140, 1.0), (148, 0.0), (300, 0.0)],
    # TV (both views, not gated by MariaView): David turns it down, then off (~1:10).
    "TVOn":     [(0, 1.0), (68, 1.0), (71, 0.4), (74, 0.4), (75, 0.0), (300, 0.0)],
}


# ------------------------------------------------------------------ helpers
def mh_clip(path, label):
    """Retargeted clip for a MetaHuman body (build_characters.py), falling back to the original."""
    body = "Maria" if label.startswith("Maria") else "David"     # Enzo shares David's body
    name = path.split("/")[-1].split(".")[0]
    candidate = f"/Game/Wattleview/Animations/MH/{body}/{name}_{body}"
    return candidate if unreal.EditorAssetLibrary.does_asset_exist(candidate) else path


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
    for name in ["MariaView"] + list(PERCEPTION.keys()) + list(FADE_PARAM.values()):
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


def keep_state(section):
    """At the end of the sequence keep the final values instead of restoring the opening."""
    try:
        opts = section.get_editor_property("eval_options")
        opts.set_editor_property("completion_mode", unreal.MovieSceneCompletionMode.KEEP_STATE)
        section.set_editor_property("eval_options", opts)
    except Exception as exc:  # property names differ across engine versions
        log(f"keep_state not applied: {exc}")


def transform_channels(binding):
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    section = track.add_section()
    section.set_range_seconds(0.0, DURATION)
    keep_state(section)
    return section.get_all_channels()


def key(channel, t, v, interp):
    channel.add_key(unreal.FrameNumber(int(round(t * FPS))), float(v), 0.0,
                    unreal.MovieSceneTimeUnit.DISPLAY_RATE, interp)


def unwrap_yaws(keys, yaw_index):
    """Rewrite yaws so each is within 180 deg of the previous key (no long-way spins)."""
    out, prev = [], None
    for k in keys:
        k = list(k)
        y = k[yaw_index]
        if prev is not None:
            while y - prev > 180:
                y -= 360
            while y - prev < -180:
                y += 360
        k[yaw_index] = y
        prev = y
        out.append(tuple(k))
    return out


def key_transform(chs, t, loc, yaw, interp, scale=(1.0, 1.0, 1.0)):
    for i, v in enumerate(loc):
        key(chs[i], t, v, interp)
    key(chs[3], t, 0.0, interp)   # roll
    key(chs[4], t, 0.0, interp)   # pitch
    key(chs[5], t, yaw, interp)   # yaw
    for i, v in zip((6, 7, 8), scale):
        key(chs[i], t, v, interp)


def add_anim_sections(binding, sections, seq):
    """Anim sections that overlap their neighbours by ANIM_BLEND with eased weights.
    Alternating rows let overlapping sections blend."""
    if not sections:
        return 0
    track = binding.add_track(unreal.MovieSceneSkeletalAnimationTrack)
    tick = seq.get_tick_resolution()
    blend_ticks = int(ANIM_BLEND * tick.numerator / tick.denominator)
    last = len(sections) - 1
    for i, (start, end, path, rate) in enumerate(sections):
        anim = unreal.load_asset(path)
        if anim is None:
            log(f"missing animation {path}")
            continue
        sec = track.add_section()
        lo = max(0.0, start - (ANIM_BLEND / 2 if i > 0 else 0.0))
        hi = min(DURATION, end + (ANIM_BLEND / 2 if i < last else 0.0))
        sec.set_range_seconds(float(lo), float(hi))
        sec.set_row_index(i % 2)
        keep_state(sec)
        params = sec.get_editor_property("params")
        params.set_editor_property("animation", anim)
        # UE 5.8: PlayRate is a MovieSceneTimeWarpVariant, not a float.
        warp = unreal.MovieSceneTimeWarpVariant()
        warp.set_fixed_play_rate(float(rate))
        params.set_editor_property("play_rate", warp)
        sec.set_editor_property("params", params)
        # Easing fields are not Python-visible in 5.8; these setters enable the manual
        # override. Durations are in tick-resolution frames.
        if i > 0:
            sec.set_ease_in_duration(blend_ticks)
        if i < last:
            sec.set_ease_out_duration(blend_ticks)
    return len(sections)


def fade_keys(anchor_label):
    """Fade-to-black keys: in from black at the start, around every cut, out at the end."""
    keys = [(0.0, 1.0), (INTRO_FADE, 0.0)]
    for t, _loc, _look in VIEWPOINTS[anchor_label][1:]:
        keys += [(t - FADE_OUT - FADE_HOLD / 2, 0.0), (t - FADE_HOLD / 2, 1.0),
                 (t + FADE_HOLD / 2, 1.0), (t + FADE_HOLD / 2 + FADE_IN, 0.0)]
    keys += [(DURATION - OUTRO_FADE, 0.0), (DURATION, 1.0)]
    return keys


def ensure_fade_material(param):
    """Black, unlit, translucent, drawn over everything; opacity = MPC param."""
    path = f"/Game/Wattleview/Materials/M_ViewFade_{param}"
    mel = unreal.MaterialEditingLibrary
    if eas.does_asset_exist(path):
        mat = unreal.load_asset(path)
        mel.delete_all_material_expressions(mat)
    else:
        mat = tools.create_asset(f"M_ViewFade_{param}", "/Game/Wattleview/Materials", unreal.Material,
                                 unreal.MaterialFactoryNew())
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("disable_depth_test", True)
    black = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -400, 0)
    black.set_editor_property("constant", unreal.LinearColor(0, 0, 0, 1))
    mel.connect_material_property(black, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    p = mel.create_material_expression(mat, unreal.MaterialExpressionCollectionParameter, -400, 150)
    p.set_editor_property("collection", unreal.load_asset(MPC_PATH))
    p.set_editor_property("parameter_name", param)
    mel.connect_material_property(p, "", unreal.MaterialProperty.MP_OPACITY)
    mel.recompile_material(mat)
    eas.save_loaded_asset(mat)
    return mat


def ensure_fade_sphere(anchor, param):
    """Inside-out sphere around the anchor (negative X scale flips the winding, so it only
    renders from inside: no black ball visible to the other viewpoints)."""
    label = f"ViewFade_{anchor.get_actor_label()}"
    for a in actors.get_all_level_actors():
        if a.get_actor_label() == label:
            actors.destroy_actor(a)
    loc = anchor.get_actor_location()
    sphere = actors.spawn_actor_from_object(unreal.load_asset("/Engine/BasicShapes/Sphere.Sphere"), loc,
                                            unreal.Rotator(0, 0, 0))
    sphere.set_actor_label(label)
    sphere.set_folder_path("Story/Anchors")
    sphere.set_actor_scale3d(unreal.Vector(-0.9, 0.9, 0.9))   # 45 cm radius > 40 cm snap radius
    c = sphere.static_mesh_component
    c.set_mobility(unreal.ComponentMobility.MOVABLE)
    c.set_material(0, ensure_fade_material(param))
    c.set_cast_shadow(False)
    c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    c.set_editor_property("translucency_sort_priority", 200)
    sphere.attach_to_actor(anchor, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                           unreal.AttachmentRule.KEEP_WORLD, False)
    # Hidden except while a fade is running (key_visibility): even fully transparent it cost a
    # full-view translucent pass every frame on the PICO.
    sphere.set_actor_hidden_in_game(True)
    return sphere


def fade_visible_ranges(anchor_label):
    """(start, end) seconds in which the anchor's fade sphere is not fully transparent."""
    ranges = [(0.0, INTRO_FADE)]
    for t, _loc, _look in VIEWPOINTS[anchor_label][1:]:
        ranges.append((t - FADE_OUT - FADE_HOLD / 2, t + FADE_HOLD / 2 + FADE_IN))
    ranges.append((DURATION - OUTRO_FADE, DURATION))
    return ranges


def key_visibility(seq, actor, ranges):
    """Show the actor only inside the (start, end) ranges; hidden in game the rest of the time."""
    track = seq.add_possessable(actor).add_track(unreal.MovieSceneVisibilityTrack)
    track.set_property_name_and_path("bHiddenInGame", "bHiddenInGame")
    sec = track.add_section()
    sec.set_range_seconds(0.0, DURATION)
    keep_state(sec)
    keys = {0: True}                               # frame -> hidden; later keys win at a frame
    for start, end in sorted(ranges):
        keys[int(round(max(0.0, start) * FPS))] = False
        if end < DURATION:
            keys[int(round(end * FPS))] = True
    ch = sec.get_all_channels()[0]
    for frame in sorted(keys):
        ch.add_key(unreal.FrameNumber(frame), keys[frame], 0.0, unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    return len(keys)


# ------------------------------------------------------------------ build
def apply_pacing():
    """Rewrite the timeline tables from cinematic to paced times (in place, once)."""
    global DURATION, VIEWPOINTS, BLOCKING, ANIMS, PROP_MOVES, PERCEPTION
    DURATION = paced(300.0)
    VIEWPOINTS = {k: [(paced(t), loc, look) for t, loc, look in v] for k, v in VIEWPOINTS.items()}
    BLOCKING = {k: [(paced(t), loc, f, i) for t, loc, f, i in v] for k, v in BLOCKING.items()}
    PROP_MOVES = {k: (pre, [(paced(t), loc, yaw, i) for t, loc, yaw, i in keys])
                  for k, (pre, keys) in PROP_MOVES.items()}
    PERCEPTION = {k: [(paced(t), val) for t, val in v] for k, v in PERCEPTION.items()}
    new_anims = {}
    for k, secs in ANIMS.items():
        out = []
        for start, end, path, rate in secs:
            a, b = paced(start), paced(end)
            stretch = (b - a) / max(1e-3, (end - start))
            # Walks cover the same distance in more time: slow the cycle to match.
            out.append((a, b, path, rate / stretch if path == WALK else rate))
        new_anims[k] = out
    ANIMS = new_anims
    log(f"pacing '{PACING}': {DURATION:.0f} s ({int(DURATION // 60)}:{int(DURATION % 60):02d})")


def build():
    apply_pacing()
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
        sphere = ensure_fade_sphere(anchor, FADE_PARAM[label])
        key_visibility(seq, sphere, fade_visible_ranges(label))
        log(f"{label}: {len(keys)} viewpoint keys, fades around {len(keys) - 1} cuts")

    # Character blocking.
    for label, keys in BLOCKING.items():
        actor = find_actor(label)
        if actor is None:
            log(f"missing {label}; skipped")
            continue
        actor.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        is_mh = "MetaHuman" in [str(t) for t in actor.tags]
        tags = [unreal.Name("Body_" + label.split("_")[0])] + ([unreal.Name("MetaHuman")] if is_mh else [])
        actor.set_editor_property("tags", tags)
        binding = seq.add_possessable(actor)
        chs = transform_channels(binding)
        for t, loc, facing, interp in unwrap_yaws(keys, 2):
            key_transform(chs, t, loc, facing + MESH_YAW_OFFSET, interp)
        # The level placement is what students see until the gaze starts LS_Story (the director
        # creates the player but does not evaluate it), so pose each character at its t=0 key.
        _, loc0, facing0, _ = keys[0]
        actor.set_actor_location_and_rotation(unreal.Vector(*loc0),
                                              unreal.Rotator(0, 0, facing0 + MESH_YAW_OFFSET), False, True)
        anim_binding, sections = binding, ANIMS.get(label, [])
        if is_mh:
            # MetaHuman Blueprint (build_characters.py): the root is a scene component, so the
            # animation goes on the Body skeletal mesh, using the clips retargeted to that body.
            body = next((c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent)
                         if c.get_name().startswith("Body")), None)
            if body is not None:
                anim_binding = seq.add_possessable(body)
                sections = [(s0, s1, mh_clip(path, label), rate) for s0, s1, path, rate in sections]
                # Before the gaze start nothing animates the body: loop the idle so the student
                # doesn't see an A-pose (the mannequin stand-ins get theirs in build_resident_room).
                idle = unreal.load_asset(mh_clip(IDLE, label))
                if idle is not None:
                    body.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
                    body.set_editor_property("animation_data", unreal.SingleAnimationPlayData(anim_to_play=idle))
        n_anim = add_anim_sections(anim_binding, sections, seq)
        log(f"{label}: {len(keys)} blocking keys, {n_anim} anim sections{' (MetaHuman body)' if is_mh else ''}")

    # Enzo (MetaHuman, attached to David, hidden until the director swaps them in Maria's view)
    # plays David's animation on his own body so the swap lands on the same pose.
    enzo = find_actor("Enzo_Overlay")
    if enzo is not None:
        ebody = next((c for c in enzo.get_components_by_class(unreal.SkeletalMeshComponent)
                      if c.get_name().startswith("Body")), None)
        if ebody is not None:
            seq.add_possessable(enzo)
            esections = [(s0, s1, mh_clip(path, "David_StandIn"), rate)
                         for s0, s1, path, rate in ANIMS.get("David_StandIn", [])]
            log(f"Enzo_Overlay: {add_anim_sections(seq.add_possessable(ebody), esections, seq)} anim sections (David's)")

    # Moving props (parts attached to a root so the whole chair moves).
    for root_label, (prefix, keys) in PROP_MOVES.items():
        root = find_actor(root_label)
        if root is None and find_actor(root_label + "_Seat") is not None:
            # greybox room: the chair is a seat root plus loose parts
            root, prefix = find_actor(root_label + "_Seat"), root_label + "_"
            root_label = root_label + "_Seat"
        if root is None:
            log(f"missing {root_label}; skipped")
            continue
        # Key heights follow the actor's real resting height (dressed meshes sit on the rug or
        # the table top computed by the placement tools, not on the greybox heights).
        dz = root.get_actor_location().z - keys[0][1][2]
        keys = [(t, (l[0], l[1], l[2] + dz), yaw, i) for t, l, yaw, i in keys]
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
        for t, loc, yaw, interp in unwrap_yaws(keys, 2):
            key_transform(chs, t, loc, yaw, interp, (scale.x, scale.y, scale.z))
        log(f"{root_label}: {len(keys)} prop keys")

    # Ceiling fan turning slowly for the whole piece (movable in the dressed room).
    fan = find_actor("CeilingFan")
    if fan is not None:
        fan.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        chs = transform_channels(seq.add_possessable(fan))
        l = fan.get_actor_location()
        y0 = fan.get_actor_rotation().yaw
        key_transform(chs, 0.0, (l.x, l.y, l.z), y0, LINEAR)
        key_transform(chs, DURATION, (l.x, l.y, l.z), y0 + FAN_DEG_PER_SECOND * DURATION, LINEAR)
        log(f"CeilingFan: {FAN_DEG_PER_SECOND:.0f} deg/s")

    # Perception parameters.
    res = seq.get_tick_resolution()

    def ticks(t):
        # MovieSceneParameterSection keys are in tick resolution (24000/s), not display frames.
        return unreal.FrameNumber(int(round(t * res.numerator / res.denominator)))

    track = seq.add_track(unreal.MovieSceneMaterialParameterCollectionTrack)
    track.set_editor_property("mpc", mpc)
    section = track.add_section()
    section.set_range_seconds(0.0, DURATION)
    keep_state(section)
    for label, param in FADE_PARAM.items():
        for t, v in fade_keys(label):
            section.add_scalar_parameter_key(unreal.Name(param), ticks(t), float(v))
    for name, keys in PERCEPTION.items():
        for t, v in keys:
            section.add_scalar_parameter_key(unreal.Name(name), ticks(t), float(v))
    log(f"MPC track: {len(PERCEPTION)} parameters")

    eas.save_loaded_asset(seq)
    les.save_current_level()
    log(f"saved {seq_path} and {MAP_PATH}")


build()
