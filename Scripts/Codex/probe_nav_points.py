import json

import unreal


MAP_PATH = "/Game/Maps/HospitalRoom"


def project(world, x, y, z, extent):
    result = unreal.NavigationSystemV1.project_point_to_navigation(
        world,
        unreal.Vector(float(x), float(y), float(z)),
        None,
        None,
        unreal.Vector(*extent),
    )
    if isinstance(result, (tuple, list)) and len(result) == 2:
        result = result[1] if bool(result[0]) else None
    if result is None:
        return None
    return [
        round(float(result.x), 3),
        round(float(result.y), 3),
        round(float(result.z), 3),
    ]


world = unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
unreal.SystemLibrary.execute_console_command(world, "RebuildNavigation")

points = []
for x in (100.0, 200.0, 300.0, 400.0, 500.0):
    for y in (100.0, 200.0, 300.0, 400.0, 500.0):
        points.append(
            {
                "input": [x, y, 0.0],
                "floor": project(world, x, y, 0.0, (25.0, 25.0, 20.0)),
                "roof": project(world, x, y, 255.0, (25.0, 25.0, 20.0)),
                "high": project(world, x, y, 200.0, (50.0, 50.0, 75.0)),
            }
        )

print("CODEX_NAV_PROBE=" + json.dumps(points, sort_keys=True))
