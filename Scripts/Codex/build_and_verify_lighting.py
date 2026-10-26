import json
import math
import traceback

import unreal


MAP_PATH = "/Game/Maps/HospitalRoom"
BUILT_DATA_PATH = "/Game/Maps/HospitalRoom_BuiltData"
XR_PAWN_PATH = "/Game/XRFramework/Blueprints/BP_XRPawn"

EXPECTED_TELEPORT_QUERY_EXTENT = (50.0, 50.0, 75.0)
FLOOR_QUERY_EXTENT = (50.0, 50.0, 20.0)
HIGH_QUERY_EXTENT = EXPECTED_TELEPORT_QUERY_EXTENT

# These points are deliberately in clear, representative parts of each space.
NAV_TEST_AREAS = {
    "large_room": (300.0, -1000.0),
    "corridor": (300.0, -300.0),
    # (100,100) is occupied by furniture and correctly has no walkable nav.
    # This point is the known-clear player-start area in the original room.
    "original_room": (300.0, 200.0),
}

REPORT = {
    "success": False,
    "map": MAP_PATH,
    "navigation_rebuilt": False,
    "navigation_assertions_passed": False,
    "navigation_checks": {},
    "lighting": {
        "quality": "Production",
        "with_reflection_captures": False,
        "build_light_maps_returned": None,
        "unbuilt_dump_requested": False,
    },
    "saves": {
        "map": False,
        "built_data": False,
        "dirty_packages": False,
    },
}


def vec(x, y, z):
    return unreal.Vector(float(x), float(y), float(z))


def vector_to_list(value):
    if value is None:
        return None
    return [
        round(float(value.x), 3),
        round(float(value.y), 3),
        round(float(value.z), 3),
    ]


def vectors_close(actual, expected, tolerance=0.01):
    return all(
        math.isclose(float(component), float(target), abs_tol=tolerance)
        for component, target in (
            (actual.x, expected[0]),
            (actual.y, expected[1]),
            (actual.z, expected[2]),
        )
    )


def coerce_projection(value):
    """Normalize Vector/None and older (success, Vector) wrapper forms."""
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return value[1] if bool(value[0]) else None
    return value


def project_to_navigation(world, point, query_extent):
    return coerce_projection(
        unreal.NavigationSystemV1.project_point_to_navigation(
            world,
            vec(*point),
            None,
            None,
            vec(*query_extent),
        )
    )


def verify_teleport_query_extent():
    xr_pawn_class = unreal.EditorAssetLibrary.load_blueprint_class(XR_PAWN_PATH)
    if xr_pawn_class is None:
        raise RuntimeError("Unable to load Blueprint class {}".format(XR_PAWN_PATH))

    xr_pawn_cdo = unreal.get_default_object(xr_pawn_class)
    if xr_pawn_cdo is None:
        raise RuntimeError("Unable to get the BP_XRPawn class default object")

    actual = xr_pawn_cdo.get_editor_property(
        "TeleportProjectPointToNavigationQueryExtent"
    )
    REPORT["teleport_query_extent"] = vector_to_list(actual)
    REPORT["expected_teleport_query_extent"] = list(
        EXPECTED_TELEPORT_QUERY_EXTENT
    )

    if not vectors_close(actual, EXPECTED_TELEPORT_QUERY_EXTENT):
        raise RuntimeError(
            "BP_XRPawn teleport query extent is {}, expected {}".format(
                vector_to_list(actual),
                list(EXPECTED_TELEPORT_QUERY_EXTENT),
            )
        )


def verify_navigation(world):
    failures = []

    for area_name, (x, y) in NAV_TEST_AREAS.items():
        floor_input = (x, y, 0.0)
        roof_input = (x, y, 255.0)
        high_input = (x, y, 200.0)

        floor_result = project_to_navigation(
            world,
            floor_input,
            FLOOR_QUERY_EXTENT,
        )
        roof_result = project_to_navigation(
            world,
            roof_input,
            FLOOR_QUERY_EXTENT,
        )
        high_result = project_to_navigation(
            world,
            high_input,
            HIGH_QUERY_EXTENT,
        )

        area_report = {
            "floor": {
                "input": list(floor_input),
                "query_extent": list(FLOOR_QUERY_EXTENT),
                "projected": vector_to_list(floor_result),
            },
            "roof": {
                "input": list(roof_input),
                "query_extent": list(FLOOR_QUERY_EXTENT),
                "projected": vector_to_list(roof_result),
            },
            "high": {
                "input": list(high_input),
                "query_extent": list(HIGH_QUERY_EXTENT),
                "projected": vector_to_list(high_result),
            },
        }
        REPORT["navigation_checks"][area_name] = area_report

        if floor_result is None:
            failures.append("{}: floor did not project to navigation".format(area_name))
        else:
            # The floor navmesh is expected near Z=5 cm. Keep a little tolerance
            # for Recast cell quantization while still rejecting a roof result.
            if not (-25.0 <= float(floor_result.z) <= 35.0):
                failures.append(
                    "{}: floor projected to unexpected Z={:.3f}".format(
                        area_name,
                        float(floor_result.z),
                    )
                )
            if abs(float(floor_result.x) - x) > FLOOR_QUERY_EXTENT[0] + 1.0:
                failures.append(
                    "{}: floor projection exceeded X query extent".format(area_name)
                )
            if abs(float(floor_result.y) - y) > FLOOR_QUERY_EXTENT[1] + 1.0:
                failures.append(
                    "{}: floor projection exceeded Y query extent".format(area_name)
                )

        if roof_result is not None:
            failures.append(
                "{}: roof still projects to navigation at {}".format(
                    area_name,
                    vector_to_list(roof_result),
                )
            )

        if high_result is not None:
            failures.append(
                "{}: high teleport query still reaches navigation at {}".format(
                    area_name,
                    vector_to_list(high_result),
                )
            )

    REPORT["navigation_failures"] = failures
    if failures:
        raise RuntimeError(
            "Navigation verification failed: {}".format("; ".join(failures))
        )

    REPORT["navigation_assertions_passed"] = True


def save_built_lighting():
    map_saved = bool(unreal.EditorLevelLibrary.save_current_level())
    REPORT["saves"]["map"] = map_saved
    if not map_saved:
        raise RuntimeError("Unable to save current level {}".format(MAP_PATH))

    built_data = unreal.EditorAssetLibrary.load_asset(BUILT_DATA_PATH)
    if built_data is None:
        raise RuntimeError(
            "Lighting build did not produce/load {}".format(BUILT_DATA_PATH)
        )

    built_data_saved = bool(
        unreal.EditorAssetLibrary.save_loaded_asset(
            built_data,
            only_if_is_dirty=False,
        )
    )
    REPORT["saves"]["built_data"] = built_data_saved
    if not built_data_saved:
        raise RuntimeError("Unable to save {}".format(BUILT_DATA_PATH))

    dirty_packages_saved = bool(
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(
            True,
            True,
        )
    )
    REPORT["saves"]["dirty_packages"] = dirty_packages_saved
    if not dirty_packages_saved:
        raise RuntimeError("Unable to save all dirty map/content packages")


def build_and_verify():
    world = unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
    if world is None:
        raise RuntimeError("Unable to load {}".format(MAP_PATH))

    REPORT["loaded_world"] = world.get_path_name()
    if world.get_path_name().split(".", 1)[0] != MAP_PATH:
        raise RuntimeError(
            "Loaded unexpected world {}".format(world.get_path_name())
        )

    unreal.SystemLibrary.execute_console_command(world, "RebuildNavigation")
    REPORT["navigation_rebuilt"] = True

    verify_teleport_query_extent()
    verify_navigation(world)

    level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level_editor is None:
        raise RuntimeError("LevelEditorSubsystem is unavailable")

    lighting_ok = bool(
        level_editor.build_light_maps(
            unreal.LightingBuildQuality.QUALITY_PRODUCTION,
            False,
        )
    )
    REPORT["lighting"]["build_light_maps_returned"] = lighting_ok
    if not lighting_ok:
        raise RuntimeError("Production lightmap build returned False")

    # The detailed zero/nonzero interaction counts are emitted by Unreal's
    # renderer to the process log, so delimit the explicit dump for automation.
    print("CODEX_UNBUILT_DUMP_BEGIN")
    unreal.SystemLibrary.execute_console_command(
        world,
        "DumpUnbuiltLightInteractions",
    )
    print("CODEX_UNBUILT_DUMP_END")
    REPORT["lighting"]["unbuilt_dump_requested"] = True

    save_built_lighting()

    REPORT["success"] = True
    return REPORT


try:
    build_and_verify()
except Exception as exc:
    REPORT["success"] = False
    REPORT["error"] = str(exc)
    REPORT["traceback"] = traceback.format_exc()
    print("CODEX_BUILD_VERIFY=" + json.dumps(REPORT, sort_keys=True))
    raise
else:
    print("CODEX_BUILD_VERIFY=" + json.dumps(REPORT, sort_keys=True))
