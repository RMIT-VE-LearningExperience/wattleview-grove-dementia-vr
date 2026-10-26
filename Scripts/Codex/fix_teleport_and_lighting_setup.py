import json
import traceback

import unreal


MAP_PATH = "/Game/Maps/HospitalRoom"
LIGHTMASS_VOLUME_LABEL = "WG_Lighting_ImportanceVolume"
XR_PAWN_PATH = "/Game/XRFramework/Blueprints/BP_XRPawn"


def vec(x, y, z):
    return unreal.Vector(float(x), float(y), float(z))


def rot(pitch=0.0, yaw=0.0, roll=0.0):
    value = unreal.Rotator()
    value.pitch = float(pitch)
    value.yaw = float(yaw)
    value.roll = float(roll)
    return value


def get_actor_by_label(actor_subsystem, label):
    for actor in actor_subsystem.get_all_level_actors():
        if actor.get_actor_label() == label:
            return actor
    return None


def fix():
    world = unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
    if world is None:
        raise RuntimeError("Unable to load {}".format(MAP_PATH))

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    fixed_ceilings = []
    fixed_sky = []

    with unreal.ScopedEditorTransaction(
        "Codex: Restrict teleport navigation and prepare baked lighting"
    ):
        for actor in actor_subsystem.get_all_level_actors():
            if not isinstance(actor, unreal.StaticMeshActor):
                continue

            component = actor.static_mesh_component
            mesh = component.static_mesh
            mesh_path = mesh.get_path_name().lower() if mesh is not None else ""
            label = actor.get_actor_label()

            if "ceiling_tile" in mesh_path or "ceiling_light" in mesh_path:
                actor.modify()
                component.modify()
                component.set_editor_property("can_ever_affect_navigation", False)
                component.set_collision_profile_name("NoCollision")
                component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
                fixed_ceilings.append(label)

            if label in ("WG_Sky_Dome", "WG_Sky_SunDisc"):
                actor.modify()
                component.modify()
                component.set_editor_property("can_ever_affect_navigation", False)
                component.set_collision_profile_name("NoCollision")
                component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
                component.set_editor_property(
                    "mobility",
                    unreal.ComponentMobility.MOVABLE,
                )
                fixed_sky.append(label)

        nav_bounds = get_actor_by_label(actor_subsystem, "NavBounds")
        if nav_bounds is None:
            raise RuntimeError("NavBounds was not found")

        # The volume now covers only the floor navigation layer. Its previous
        # top was Z=285 cm, which included the ceiling at Z=250 and generated a
        # second walkable navmesh layer on the roof.
        nav_bounds.modify()
        nav_bounds.set_actor_location(vec(300.0, -400.0, 80.0), False, False)
        nav_bounds.set_actor_scale3d(vec(5.5, 10.0, 1.2))

        importance_volume = get_actor_by_label(
            actor_subsystem,
            LIGHTMASS_VOLUME_LABEL,
        )
        if importance_volume is None:
            importance_volume = actor_subsystem.spawn_actor_from_class(
                unreal.LightmassImportanceVolume,
                vec(300.0, -400.0, 125.0),
                rot(),
            )
            if importance_volume is None:
                raise RuntimeError("Unable to create Lightmass Importance Volume")
            importance_volume.set_actor_label(LIGHTMASS_VOLUME_LABEL)
            importance_volume.set_folder_path("WG Expansion/Lighting")

        # Covers the original room, corridor, large room, and a small margin.
        importance_volume.set_actor_location(
            vec(300.0, -400.0, 125.0),
            False,
            False,
        )
        importance_volume.set_actor_scale3d(vec(6.5, 11.0, 2.25))

    xr_pawn_class = unreal.EditorAssetLibrary.load_blueprint_class(XR_PAWN_PATH)
    if xr_pawn_class is None:
        raise RuntimeError("Unable to load {}".format(XR_PAWN_PATH))
    xr_pawn_cdo = unreal.get_default_object(xr_pawn_class)
    xr_pawn_cdo.modify()
    teleport_query_extent = vec(50.0, 50.0, 75.0)
    xr_pawn_cdo.set_editor_property(
        "TeleportProjectPointToNavigationQueryExtent",
        teleport_query_extent,
    )
    if not unreal.EditorAssetLibrary.save_asset(
        XR_PAWN_PATH,
        only_if_is_dirty=False,
    ):
        raise RuntimeError("Unable to save {}".format(XR_PAWN_PATH))

    unreal.SystemLibrary.execute_console_command(world, "RebuildNavigation")
    if not unreal.EditorLevelLibrary.save_current_level():
        raise RuntimeError("Unable to save {}".format(MAP_PATH))

    nav_origin, nav_extent = nav_bounds.get_actor_bounds(False)
    importance_origin, importance_extent = importance_volume.get_actor_bounds(False)
    result = {
        "success": True,
        "map": world.get_path_name(),
        "ceilings_excluded_from_navigation": len(fixed_ceilings),
        "sky_excluded_from_lightmass": fixed_sky,
        "teleport_query_extent": [
            teleport_query_extent.x,
            teleport_query_extent.y,
            teleport_query_extent.z,
        ],
        "nav_bounds_origin": [
            nav_origin.x,
            nav_origin.y,
            nav_origin.z,
        ],
        "nav_bounds_extent": [
            nav_extent.x,
            nav_extent.y,
            nav_extent.z,
        ],
        "lightmass_volume_origin": [
            importance_origin.x,
            importance_origin.y,
            importance_origin.z,
        ],
        "lightmass_volume_extent": [
            importance_extent.x,
            importance_extent.y,
            importance_extent.z,
        ],
    }
    print("CODEX_FIX=" + json.dumps(result, sort_keys=True))


try:
    fix()
except Exception as exc:
    print(
        "CODEX_FIX="
        + json.dumps(
            {
                "success": False,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
            sort_keys=True,
        )
    )
    raise
