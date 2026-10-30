"""Apply the stable cinematic character settings used by the Pico build.

UE 5.7/5.8's Android path can corrupt MetaHuman wardrobe meshes that use Leader
Pose, including Epic's generated default clothes.  The story is fully cinematic,
so each wardrobe evaluates the same baked animation as its body instead.  This
script restores the untouched generated outfit, disconnects Leader Pose, disables
cloth and keeps the body/wardrobe on one deterministic LOD tier.  The matching
Sequencer tracks are created by build_story_sequence.py.
"""
import unreal


MAP = "/Game/Wattleview/Maps/L_ResidentRoom"
CHARACTERS = ("Maria_StandIn", "David_StandIn", "Gardener_StandIn", "Enzo_Overlay")
GENERATED_OUTFITS = {
    "Maria_StandIn": "/Game/MetaHumans/MariaReference/Clothing/MariaReference_Outfits",
    "David_StandIn": "/Game/MetaHumans/DavidReference/Clothing/DavidReference_Outfits",
    "Gardener_StandIn": "/Game/MetaHumans/GardenerReference/Clothing/GardenerReference_Outfits",
    "Enzo_Overlay": "/Game/MetaHumans/EnzoReference/Clothing/EnzoReference_Outfits",
}

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)


def log(message):
    unreal.log("[CinematicMobileCharacters] " + str(message))


def find(label):
    return next((actor for actor in actors.get_all_level_actors()
                 if actor.get_actor_label() == label), None)


def named_component(actor, name):
    return next((component for component in actor.get_components_by_class(unreal.ActorComponent)
                 if component.get_name() == name), None)


def configure(actor):
    actor.modify()
    lod_sync = named_component(actor, "LODSync")
    body = named_component(actor, "Body")
    outfit = named_component(actor, "SkeletalMesh")
    if lod_sync is None or body is None or outfit is None:
        raise RuntimeError(f"{actor.get_actor_label()}: missing LODSync, Body, or wardrobe")

    generated_path = GENERATED_OUTFITS.get(actor.get_actor_label())
    if not generated_path or not unreal.EditorAssetLibrary.does_asset_exist(generated_path):
        raise RuntimeError(f"{actor.get_actor_label()}: generated wardrobe is missing")
    generated_outfit = unreal.load_asset(generated_path)
    if outfit.get_skinned_asset() != generated_outfit:
        outfit.set_skinned_asset_and_update(generated_outfit)

    # Deliberately avoid the Android Leader Pose path.  The follower must evaluate
    # its own pose; Sequencer gives it the exact same animation sections as Body.
    outfit.set_leader_pose_component(None, True, True)

    # Global MetaHuman LOD 0 maps this Optimized/Medium build to body LOD 0,
    # wardrobe LOD 1, and groom-card LOD 3.  These are the highest matching mobile
    # tiers in this assembly.  A fixed global LOD prevents lower-LOD bone reduction
    # from pulling pelvis/thigh-weighted shorts downward during a shot.
    lod_sync.modify()
    lod_sync.set_editor_property("forced_lod", 0)
    lod_sync.set_editor_property("min_lod", 0)

    outfit.modify()
    leader = outfit.get_editor_property("leader_pose_component")
    if leader is not None:
        raise RuntimeError(f"{actor.get_actor_label()}: wardrobe Leader Pose did not clear")
    outfit.set_editor_property("disable_cloth_simulation", True)
    outfit.set_editor_property("allow_cloth_actors", False)
    outfit.set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
    )
    outfit.set_editor_property("enable_update_rate_optimizations", False)
    body.set_editor_property("enable_update_rate_optimizations", False)

    log(
        f"{actor.get_actor_label()}: global LOD locked to 0; "
        "original generated wardrobe animates independently; cloth disabled"
    )


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None or world.get_path_name().split(".")[0] != MAP:
        if not levels.load_level(MAP):
            raise RuntimeError("Could not load " + MAP)
    configured = []
    for label in CHARACTERS:
        actor = find(label)
        if actor is None:
            log(label + ": not present; skipped")
            continue
        configure(actor)
        configured.append(label)
    levels.save_current_level()
    log("saved: " + ", ".join(configured))


main()
