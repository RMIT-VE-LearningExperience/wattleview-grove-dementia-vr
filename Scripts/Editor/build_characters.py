"""Put the assembled MetaHumans into L_ResidentRoom in place of the mannequin stand-ins.

1. Retarget the placeholder animations (idle, in-place walk, sit; UE5 mannequin skeleton) onto
   each MetaHuman body with an IK Retargeter (auto-generated IK rigs, fuzzy chain mapping).
   Each approved reference has its own set so its reviewed proportions are preserved.
   Output: /Game/Wattleview/Animations/MH/<Body>/<Anim>_<Body>
2. Replace Maria_StandIn, David_StandIn and Gardener_StandIn with the approved reference
   MetaHumans at the same transform.
   The actors KEEP the *_StandIn labels so the sequence, director and perception scripts keep
   finding them; they carry the actor tag "MetaHuman". The gardener stays a mannequin (far away,
   BP_EnzoReference is placed on David (label Enzo_Overlay), hidden until the cross-fade is built.
3. build_story_sequence.py detects MetaHuman actors and puts their animation on the Body
   component using the retargeted clips.

Run after build_resident_room.py / build_room_dressing.py and before build_story_sequence.py.
Needs the assembled characters from assemble_metahumans.py.
"""
import unreal

SRC_MESH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
RIG_DIR = "/Game/Wattleview/Animations/Retarget"
OUT_DIR = "/Game/Wattleview/Animations/MH"
ANIMS = ["/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle",
         "/Game/Wattleview/Animations/AS_Placeholder_Walk",
         "/Game/Wattleview/Animations/AS_Placeholder_Sit"]
BODIES = {
    "MariaReference": "/Game/MetaHumans/MariaReference/Body/SKM_MariaReference_BodyMesh",
    "DavidReference": "/Game/MetaHumans/DavidReference/Body/SKM_DavidReference_BodyMesh",
    "EnzoReference": "/Game/MetaHumans/EnzoReference/Body/SKM_EnzoReference_BodyMesh",
    "GardenerReference": "/Game/MetaHumans/GardenerReference/Body/SKM_GardenerReference_BodyMesh",
}
CHARACTERS = [
    ("Maria_StandIn", "/Game/MetaHumans/MariaReference/BP_MariaReference"),
    ("David_StandIn", "/Game/MetaHumans/DavidReference/BP_DavidReference"),
    ("Gardener_StandIn", "/Game/MetaHumans/GardenerReference/BP_GardenerReference"),
]
ENZO_BP = "/Game/MetaHumans/EnzoReference/BP_EnzoReference"
MAP_PATH = "/Game/Wattleview/Maps/L_ResidentRoom"
GENERATED_OUTFITS = {
    "Maria_StandIn": "/Game/MetaHumans/MariaReference/Clothing/MariaReference_Outfits",
    "David_StandIn": "/Game/MetaHumans/DavidReference/Clothing/DavidReference_Outfits",
    "Gardener_StandIn": "/Game/MetaHumans/GardenerReference/Clothing/GardenerReference_Outfits",
    "Enzo_Overlay": "/Game/MetaHumans/EnzoReference/Clothing/EnzoReference_Outfits",
}
FORCE_RETARGET = globals().get("FORCE_RETARGET", False)

eas = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
SRC, TGT = unreal.RetargetSourceOrTarget.SOURCE, unreal.RetargetSourceOrTarget.TARGET


def log(msg):
    unreal.log("[Characters] " + str(msg))


def get_or_create(name, path, cls, factory):
    """Reuse an existing asset: deleting one that others reference opens a blocking modal."""
    full = f"{path}/{name}"
    if eas.does_asset_exist(full):
        return unreal.load_asset(full), False
    return tools.create_asset(name, path, cls, factory), True


def make_rig(name, mesh):
    rig, created = get_or_create(name, RIG_DIR, unreal.IKRigDefinition, unreal.IKRigDefinitionFactory())
    c = unreal.IKRigController.get_controller(rig)
    if created or not c.get_retarget_chains():
        c.set_skeletal_mesh(mesh)
        c.apply_auto_generated_retarget_definition()
    eas.save_loaded_asset(rig, False)
    log(f"{name}: {len(c.get_retarget_chains())} retarget chains")
    return rig


def make_retargeter(name, src_rig, tgt_rig, src_mesh, tgt_mesh):
    rtg, created = get_or_create(name, RIG_DIR, unreal.IKRetargeter, unreal.IKRetargetFactory())
    rc = unreal.IKRetargeterController.get_controller(rtg)
    if not created:
        return rtg
    rc.set_ik_rig(SRC, src_rig)
    rc.set_ik_rig(TGT, tgt_rig)
    rc.set_preview_mesh(SRC, src_mesh)
    rc.set_preview_mesh(TGT, tgt_mesh)
    try:
        rc.add_default_ops()
        rc.assign_ik_rig_to_all_ops(TGT, tgt_rig)
    except Exception as exc:
        log(f"{name}: default ops not added ({exc})")
    rc.auto_map_chains(unreal.AutoMapChainType.FUZZY, True)
    try:
        rc.auto_align_all_bones(TGT)
    except Exception as exc:
        log(f"{name}: auto align skipped ({exc})")
    eas.save_loaded_asset(rtg, False)
    return rtg


def retarget_for(body, mesh_path):
    src_mesh = unreal.load_asset(SRC_MESH)
    tgt_mesh = unreal.load_asset(mesh_path)
    src_rig = make_rig("IK_Mannequin_Auto", src_mesh) if not eas.does_asset_exist(f"{RIG_DIR}/IK_Mannequin_Auto") \
        else unreal.load_asset(f"{RIG_DIR}/IK_Mannequin_Auto")
    tgt_rig = make_rig(f"IK_MH_{body}", tgt_mesh)
    rtg = make_retargeter(f"RTG_Mannequin_To_{body}", src_rig, tgt_rig, src_mesh, tgt_mesh)
    sources = [eas.find_asset_data(p) for p in ANIMS]       # the batch API takes AssetData
    eas.make_directory(f"{OUT_DIR}/{body}")
    out = unreal.IKRetargetBatchOperation.duplicate_and_retarget(
        sources, src_mesh, tgt_mesh, rtg, search="", replace="", prefix="", suffix=f"_{body}",
        target_path=f"{OUT_DIR}/{body}", use_source_path=False, include_referenced_assets=False,
        overwrite_existing_files=True)            # overwrite in place: no delete, no modal
    moved = [str(ad.package_name) for ad in out if str(ad.asset_class_path.asset_name) == "AnimSequence"]
    log(f"{body}: retargeted {moved}")
    return moved


def find(label):
    return next((a for a in acts.get_all_level_actors() if a.get_actor_label() == label), None)


def configure_cinematic_mobile_character(actor):
    """Keep the assembled body and wardrobe on one proven Pico deformation tier."""
    comps = actor.get_components_by_class(unreal.ActorComponent)
    lod_sync = next((c for c in comps if c.get_name() == "LODSync"), None)
    body = next((c for c in comps if c.get_name() == "Body"), None)
    outfit = next((c for c in comps if c.get_name() == "SkeletalMesh"), None)
    if lod_sync is None or body is None or outfit is None:
        log(f"{actor.get_actor_label()}: cinematic mobile settings skipped; components missing")
        return
    generated_path = GENERATED_OUTFITS.get(actor.get_actor_label())
    if generated_path and eas.does_asset_exist(generated_path):
        generated_outfit = unreal.load_asset(generated_path)
        outfit.set_skinned_asset_and_update(generated_outfit)
        # Android Leader Pose can corrupt generated MetaHuman clothes.  The story
        # sequence drives Body and wardrobe with matching baked animation tracks.
        outfit.set_leader_pose_component(None, True, True)
        log(f"{actor.get_actor_label()}: assigned generated outfit with independent pose")
    lod_sync.set_editor_property("forced_lod", 0)
    lod_sync.set_editor_property("min_lod", 0)
    outfit.set_editor_property("disable_cloth_simulation", True)
    outfit.set_editor_property("allow_cloth_actors", False)
    outfit.set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    outfit.set_editor_property("enable_update_rate_optimizations", False)
    body.set_editor_property("enable_update_rate_optimizations", False)


def place():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None or world.get_path_name().split(".")[0] != MAP_PATH:
        les.load_level(MAP_PATH)
    placed = {}
    for label, bp in CHARACTERS:
        old = find(label)
        if old is None:
            log(f"{label}: not found, skipped")
            continue
        loc, rot, folder = old.get_actor_location(), old.get_actor_rotation(), old.get_folder_path()
        if "MetaHuman" in [str(t) for t in old.tags]:
            log(f"{label}: already a MetaHuman, replacing")
        acts.destroy_actor(old)
        a = acts.spawn_actor_from_class(unreal.EditorAssetLibrary.load_blueprint_class(bp), loc, rot)
        a.set_actor_label(label)
        a.set_folder_path(folder)
        a.set_editor_property("tags", [unreal.Name("MetaHuman")])
        configure_cinematic_mobile_character(a)
        placed[label] = a
    old = find("Enzo_Overlay")
    if old:
        acts.destroy_actor(old)
    david = placed.get("David_StandIn")
    if david and eas.does_asset_exist(ENZO_BP):
        e = acts.spawn_actor_from_class(unreal.EditorAssetLibrary.load_blueprint_class(ENZO_BP),
                                        david.get_actor_location(), david.get_actor_rotation())
        e.set_actor_label("Enzo_Overlay")
        e.set_folder_path("Characters")
        e.set_editor_property("tags", [unreal.Name("MetaHuman")])
        configure_cinematic_mobile_character(e)
        e.set_actor_hidden_in_game(True)
        e.attach_to_actor(david, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                          unreal.AttachmentRule.KEEP_WORLD, False)
    les.save_current_level()
    log(f"placed {sorted(placed)} and saved")


def main():
    eas.make_directory(RIG_DIR)
    for body, mesh in BODIES.items():
        try:
            retarget_for(body, mesh)
        except Exception:
            import traceback
            log(f"{body}: retarget FAILED\n" + traceback.format_exc())
    place()


main()
