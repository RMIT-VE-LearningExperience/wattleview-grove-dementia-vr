"""Create placeholder pose animations for the UE5 mannequin stand-ins.

AS_Placeholder_Walk: MF_Unarmed_Walk_Fwd with its root motion removed (the root bone is
keyed at the origin), so LS_Story's transform keys alone move the character. The clip's
own root travels 450 cm per 1.5 s cycle (~300 cm/s); LS_Story sets each walk section's
play rate from the distance actually covered so the feet don't slide.

AS_Placeholder_Sit: MM_Idle with the legs posed for sitting on a 46 cm chair. The upper
body keeps the idle breathing; pelvis, thighs and calves are overwritten with a constant
seated pose. Built by editing the pose in component space (mesh forward is +Y, up +Z,
lateral X) and writing the resulting local transforms as bone track keys.

Placeholder until the MetaHuman performances exist.
Run in the open editor:  exec(open(r"<this file>").read())
"""
import unreal

SRC = "/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle"
DST_DIR = "/Game/Wattleview/Animations"
SIT = "AS_Placeholder_Sit"
WALK_SRC = "/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd"
WALK = "AS_Placeholder_Walk"

# Seated geometry (cm / degrees).
PELVIS_DROP = 40.0      # lower the hips onto the seat
PELVIS_BACK = 12.0      # sit back into the chair (mesh -Y)
THIGH_SWING = 78.0      # swing thighs forward so the knees sit just above hip height
CALF_RETURN = 82.0      # bring the shins back to vertical, feet on the floor

eas = unreal.EditorAssetLibrary
WORLD = unreal.AnimPoseSpaces.WORLD
LOCAL = unreal.AnimPoseSpaces.LOCAL


def log(msg):
    unreal.log("[Poses] " + msg)


def rotate_about_lateral(pose, bone, degrees):
    """Rotate a bone about the component lateral (X) axis, pivoting at the bone.

    AnimPose is a struct: set_bone_pose returns the modified copy, so return it."""
    t = unreal.AnimPoseExtensions.get_bone_pose(pose, bone, WORLD)
    delta = unreal.Quat()
    delta.set_from_euler(unreal.Vector(degrees, 0.0, 0.0))
    rot = unreal.MathLibrary.multiply_quat_quat(delta, t.rotation)
    t.rotation = rot
    return unreal.AnimPoseExtensions.set_bone_pose(pose, t, bone, WORLD)


def build_sit():
    path = f"{DST_DIR}/{SIT}"
    if eas.does_asset_exist(path):
        eas.delete_asset(path)
    seq = eas.duplicate_asset(SRC, path)

    eval_opts = unreal.AnimPoseEvaluationOptions()
    pose = unreal.AnimPoseExtensions.get_anim_pose_at_frame(seq, 0, eval_opts)

    pelvis = unreal.AnimPoseExtensions.get_bone_pose(pose, "pelvis", WORLD)
    pelvis.translation = unreal.Vector(pelvis.translation.x, pelvis.translation.y - PELVIS_BACK,
                                       pelvis.translation.z - PELVIS_DROP)
    pose = unreal.AnimPoseExtensions.set_bone_pose(pose, pelvis, "pelvis", WORLD)
    for side in ("l", "r"):
        pose = rotate_about_lateral(pose, f"thigh_{side}", -THIGH_SWING)
        pose = rotate_about_lateral(pose, f"calf_{side}", CALF_RETURN)

    controller = seq.controller
    try:
        n_keys = controller.get_model_interface().get_number_of_keys()
    except Exception:
        n_keys = unreal.AnimationLibrary.get_num_frames(seq) + 1
    controller.open_bracket(unreal.Text("Placeholder sit pose"))
    for bone in ("pelvis", "thigh_l", "thigh_r", "calf_l", "calf_r"):
        local = unreal.AnimPoseExtensions.get_bone_pose(pose, bone, LOCAL)
        controller.set_bone_track_keys(bone,
                                       [local.translation] * n_keys,
                                       [local.rotation] * n_keys,
                                       [local.scale3d] * n_keys)
    controller.close_bracket()
    eas.save_loaded_asset(seq)
    log(f"built {path} ({n_keys} keys)")
    return seq


def key_count(seq):
    try:
        return seq.controller.get_model_interface().get_number_of_keys()
    except Exception:
        return unreal.AnimationLibrary.get_num_frames(seq) + 1


def build_walk():
    """In-place walk: root keyed at the origin for every frame, other bones untouched."""
    path = f"{DST_DIR}/{WALK}"
    if eas.does_asset_exist(path):
        eas.delete_asset(path)
    seq = eas.duplicate_asset(WALK_SRC, path)
    n = key_count(seq)
    ident = unreal.Transform()
    c = seq.controller
    c.open_bracket(unreal.Text("In-place walk"))
    c.set_bone_track_keys("root", [ident.translation] * n, [ident.rotation] * n, [ident.scale3d] * n)
    c.close_bracket()
    seq.set_editor_property("enable_root_motion", False)
    eas.save_loaded_asset(seq)
    log(f"built {path} ({n} keys)")
    return seq


build_sit()
build_walk()
