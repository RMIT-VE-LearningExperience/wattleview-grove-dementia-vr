import json
import traceback

import unreal


ANIM_BLUEPRINT_PATH = (
    "/Game/MetaHumans/Maria/Animations/ABP_Maria_NaturalLook"
)
OLD_INTERP_SPEED = 3.0
NEW_INTERP_SPEED = 2.0


def get_event_graph_info(asset):
    raw = unreal.MCPythonHelper.get_blueprint_graph_info(
        asset,
        "EventGraph",
    )
    info = json.loads(raw)
    if not info.get("success"):
        raise RuntimeError(
            "Unable to inspect Maria EventGraph: {}".format(raw)
        )
    return info


def find_vinterp_node(asset):
    candidates = []

    # UEdGraph::Nodes is protected from Python in UE 5.7. The project's
    # MCPython C++ helper safely exposes graph and pin metadata as JSON.
    for node in get_event_graph_info(asset).get("nodes", []):
        if node.get("node_class") != "K2Node_CallFunction":
            continue

        title_key = "".join(
            character
            for character in node.get("node_title", "").lower()
            if character.isalnum()
        )
        if "vinterpto" not in title_key:
            continue

        pins_by_name = {
            pin.get("pin_name"): pin
            for pin in node.get("pins", [])
        }
        if "InterpSpeed" not in pins_by_name:
            continue

        current_default = str(
            pins_by_name["InterpSpeed"].get("default_value", "")
        )
        if abs(float(current_default) - OLD_INTERP_SPEED) > 0.001:
            continue
        candidates.append(node)

    if len(candidates) != 1:
        raise RuntimeError(
            "Expected one VInterpTo node with speed {}, found {}".format(
                OLD_INTERP_SPEED,
                len(candidates),
            )
        )
    return candidates[0]


def smooth():
    asset = unreal.EditorAssetLibrary.load_asset(ANIM_BLUEPRINT_PATH)
    if asset is None:
        raise RuntimeError("Unable to load {}".format(ANIM_BLUEPRINT_PATH))

    node = find_vinterp_node(asset)
    speed_pin = next(
        pin
        for pin in node.get("pins", [])
        if pin.get("pin_name") == "InterpSpeed"
    )
    old_value = str(speed_pin.get("default_value", ""))
    if abs(float(old_value) - OLD_INTERP_SPEED) > 0.001:
        raise RuntimeError(
            "VInterpTo speed changed unexpectedly: {}".format(old_value)
        )

    set_result_raw = unreal.MCPythonHelper.set_blueprint_node_pin_default(
        asset,
        "EventGraph",
        node["node_name"],
        "InterpSpeed",
        str(NEW_INTERP_SPEED),
    )
    set_result = json.loads(set_result_raw)
    if not set_result.get("success"):
        raise RuntimeError(
            "Unable to set VInterpTo speed: {}".format(set_result_raw)
        )

    unreal.BlueprintEditorLibrary.compile_blueprint(asset)

    verified_node = next(
        graph_node
        for graph_node in get_event_graph_info(asset).get("nodes", [])
        if graph_node.get("node_name") == node["node_name"]
    )
    verified_pin = next(
        pin
        for pin in verified_node.get("pins", [])
        if pin.get("pin_name") == "InterpSpeed"
    )
    new_value = str(verified_pin.get("default_value", ""))
    if abs(float(new_value) - NEW_INTERP_SPEED) > 0.001:
        raise RuntimeError(
            "VInterpTo speed did not update: {}".format(new_value)
        )

    if not unreal.EditorAssetLibrary.save_asset(
        ANIM_BLUEPRINT_PATH,
        only_if_is_dirty=False,
    ):
        raise RuntimeError("Unable to save {}".format(ANIM_BLUEPRINT_PATH))

    result = {
        "success": True,
        "asset": ANIM_BLUEPRINT_PATH,
        "node": node["node_name"],
        "old_interp_speed": float(old_value),
        "new_interp_speed": float(new_value),
    }
    print("CODEX_MARIA_SMOOTH=" + json.dumps(result, sort_keys=True))


try:
    smooth()
except Exception as exc:
    print(
        "CODEX_MARIA_SMOOTH="
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
