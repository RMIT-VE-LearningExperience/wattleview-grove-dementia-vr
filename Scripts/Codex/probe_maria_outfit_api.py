"""Log the live skeletal-mesh API needed for a non-destructive reference-pose capture."""

import json
import unreal


unreal.EditorLoadingAndSavingUtils.load_map("/Game/Wattleview/Maps/L_ResidentRoom")
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
maria = next(a for a in actors if a.get_actor_label() == "Maria_StandIn")
outfit = next(c for c in maria.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == "SkeletalMesh")
body = next(c for c in maria.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == "Body")

names = [name for name in dir(outfit) if any(token in name.lower() for token in ("leader", "master", "pose", "animation", "visibility"))]
unreal.log_warning("[MariaOutfitAPI] " + json.dumps({
    "methods": names,
    "outfit_visible": outfit.is_visible(),
    "outfit_hidden_in_game": outfit.get_editor_property("hidden_in_game"),
    "outfit_component_scale": str(outfit.get_world_scale()),
    "outfit_relative_transform": str(outfit.get_relative_transform()),
    "outfit_bounds": [str(v) for v in unreal.SystemLibrary.get_component_bounds(outfit)],
    "body_bounds": [str(v) for v in unreal.SystemLibrary.get_component_bounds(body)],
}, indent=2))
