import json
import traceback

import unreal


ANIM_BLUEPRINT_PATH = (
    "/Game/MetaHumans/Maria/Animations/ABP_Maria_NaturalLook"
)
ALPHA_VARIABLE = "PersonalSpaceAlpha"
SPEC = {
    "builder": "personal_space_recoil",
    "xr_pawn_class": (
        "/Game/XRFramework/Blueprints/BP_XRPawn.BP_XRPawn_C"
    ),
    "alpha_variable": ALPHA_VARIABLE,
    "neck_bone": "neck_01",
    "head_bone": "head",
    "near_distance": 35.0,
    "far_distance": 80.0,
    "front_gate_start": 0.25,
    "front_gate_full": 0.55,
    "interp_speed": 4.5,
    "neck_pitch_degrees": -10.0,
    "upper_neck_pitch_degrees": -6.0,
    "head_back_translation": 1.5,
}


def helper_json(value):
    parsed = json.loads(value)
    if not parsed.get("success"):
        raise RuntimeError(value)
    return parsed


def ensure_alpha_variable(asset):
    variables = helper_json(
        unreal.MCPythonHelper.list_blueprint_variables(asset)
    ).get("variables", [])
    existing = {
        variable.get("name"): variable
        for variable in variables
    }
    if ALPHA_VARIABLE in existing:
        if existing[ALPHA_VARIABLE].get("type") != "real":
            raise RuntimeError(
                "{} exists with type {}, expected real".format(
                    ALPHA_VARIABLE,
                    existing[ALPHA_VARIABLE].get("type"),
                )
            )
        return False

    pin_type = unreal.BlueprintEditorLibrary.get_basic_type_by_name(
        unreal.Name("real")
    )
    if not unreal.BlueprintEditorLibrary.add_member_variable(
        asset,
        unreal.Name(ALPHA_VARIABLE),
        pin_type,
    ):
        raise RuntimeError(
            "Unable to add {}".format(ALPHA_VARIABLE)
        )
    unreal.BlueprintEditorLibrary.compile_blueprint(asset)
    return True


def find_nodes(graph_info, node_class):
    return [
        node
        for node in graph_info.get("nodes", [])
        if node.get("node_class") == node_class
    ]


def verify(asset):
    event_graph = helper_json(
        unreal.MCPythonHelper.get_blueprint_graph_info(
            asset,
            "EventGraph",
        )
    )
    anim_graph = helper_json(
        unreal.MCPythonHelper.get_blueprint_graph_info(
            asset,
            "AnimGraph",
        )
    )

    recoil_sets = [
        node
        for node in find_nodes(event_graph, "K2Node_VariableSet")
        if node.get("node_title") == "Set {}".format(ALPHA_VARIABLE)
    ]
    recoil_gets_event = [
        node
        for node in find_nodes(event_graph, "K2Node_VariableGet")
        if node.get("node_title") == "Get {}".format(ALPHA_VARIABLE)
    ]
    modify_nodes = find_nodes(
        anim_graph,
        "AnimGraphNode_ModifyBone",
    )
    recoil_gets_anim = [
        node
        for node in find_nodes(anim_graph, "K2Node_VariableGet")
        if node.get("node_title") == "Get {}".format(ALPHA_VARIABLE)
    ]

    modify_titles = sorted(
        node.get("node_title", "")
        for node in modify_nodes
    )
    if len(recoil_sets) != 1:
        raise RuntimeError(
            "Expected one recoil alpha setter, found {}".format(
                len(recoil_sets)
            )
        )
    if len(recoil_gets_event) != 1:
        raise RuntimeError(
            "Expected one EventGraph recoil getter, found {}".format(
                len(recoil_gets_event)
            )
        )
    if len(modify_nodes) != 3:
        raise RuntimeError(
            "Expected three recoil Modify Bone nodes, found {}: {}".format(
                len(modify_nodes),
                modify_titles,
            )
        )
    if len(recoil_gets_anim) != 3:
        raise RuntimeError(
            "Expected three AnimGraph recoil getters, found {}".format(
                len(recoil_gets_anim)
            )
        )

    output_nodes = find_nodes(anim_graph, "AnimGraphNode_Root")
    if len(output_nodes) != 1:
        raise RuntimeError(
            "Expected one AnimGraph output node, found {}".format(
                len(output_nodes)
            )
        )

    return {
        "event_node_count": event_graph.get("node_count"),
        "anim_node_count": anim_graph.get("node_count"),
        "modify_bone_titles": modify_titles,
        "recoil_event_setter": recoil_sets[0]["node_name"],
    }


def run():
    asset = unreal.EditorAssetLibrary.load_asset(
        ANIM_BLUEPRINT_PATH
    )
    if asset is None:
        raise RuntimeError(
            "Unable to load {}".format(ANIM_BLUEPRINT_PATH)
        )

    variable_added = ensure_alpha_variable(asset)
    build_result = helper_json(
        unreal.MCPythonHelper.build_blueprint_graph(
            asset,
            "EventGraph",
            json.dumps(SPEC),
        )
    )
    compile_result = helper_json(
        unreal.MCPythonHelper.compile_blueprint(asset)
    )
    verification = verify(asset)

    if not unreal.EditorAssetLibrary.save_asset(
        ANIM_BLUEPRINT_PATH,
        only_if_is_dirty=False,
    ):
        raise RuntimeError(
            "Unable to save {}".format(ANIM_BLUEPRINT_PATH)
        )

    unreal.MCPythonHelper.submit_result(
        json.dumps(
            {
                "success": True,
                "asset": ANIM_BLUEPRINT_PATH,
                "variable_added": variable_added,
                "build": build_result,
                "compile": compile_result,
                "verification": verification,
            },
            sort_keys=True,
        )
    )


try:
    run()
except Exception as exc:
    unreal.MCPythonHelper.submit_result(
        json.dumps(
            {
                "success": False,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
            sort_keys=True,
        )
    )
    raise
