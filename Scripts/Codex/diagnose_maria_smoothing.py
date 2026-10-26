import json
import traceback

import unreal


ASSET_PATHS = (
    "/Game/MetaHumans/Maria/BP_Maria",
    "/Game/MetaHumans/Maria/Animations/ABP_Maria_NaturalLook",
)

PROPERTY_CANDIDATES = (
    "ubergraph_pages",
    "function_graphs",
    "macro_graphs",
    "event_graph",
    "anim_graph",
    "nodes",
    "pins",
    "node",
    "function_reference",
    "variable_reference",
    "member_reference",
    "custom_function_name",
    "event_reference",
    "bone_to_modify",
    "look_at_bone",
    "look_at_location",
    "look_at_target",
    "look_at_axis",
    "look_up_axis",
    "look_at_clamp",
    "interpolation_time",
    "interpolation_trigger_threshold",
    "interp_speed",
    "b_interp_result",
    "alpha",
    "lod_threshold",
)


def serialise(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [serialise(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serialise(item) for key, item in value.items()}
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def get_property(obj, name):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return None


def pin_report(pin):
    report = {}
    for name in (
        "pin_name",
        "pin_friendly_name",
        "direction",
        "default_value",
        "default_object",
        "default_text_value",
        "linked_to",
        "pin_type",
    ):
        value = get_property(pin, name)
        if value not in (None, "", [], ()):
            report[name] = serialise(value)
    return report


def node_report(node):
    report = {
        "name": node.get_name(),
        "class": node.get_class().get_name(),
    }
    for name in PROPERTY_CANDIDATES:
        value = get_property(node, name)
        if value not in (None, "", [], ()):
            report[name] = serialise(value)
    pins = get_property(node, "pins")
    if pins:
        report["pins"] = [pin_report(pin) for pin in pins]
    return report


def graph_report(graph):
    report = {
        "name": graph.get_name(),
        "class": graph.get_class().get_name(),
    }
    nodes = get_property(graph, "nodes")
    if nodes:
        report["nodes"] = [node_report(node) for node in nodes]
    return report


def asset_report(asset_path):
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if asset is None:
        return {"path": asset_path, "error": "load failed"}

    report = {
        "path": asset_path,
        "class": asset.get_class().get_name(),
        "available_attributes": [
            name
            for name in dir(asset)
            if any(
                term in name.lower()
                for term in ("graph", "variable", "generated", "skeleton")
            )
        ],
    }

    for graph_property in ("ubergraph_pages", "function_graphs", "macro_graphs"):
        graphs = get_property(asset, graph_property)
        if graphs:
            report[graph_property] = [graph_report(graph) for graph in graphs]

    if hasattr(asset, "get_animation_graphs"):
        try:
            report["animation_graphs"] = [
                graph_report(graph) for graph in asset.get_animation_graphs()
            ]
        except Exception as exc:
            report["animation_graphs_error"] = str(exc)

    generated_class = None
    generated_class_accessor = getattr(asset, "generated_class", None)
    if callable(generated_class_accessor):
        try:
            generated_class = generated_class_accessor()
        except Exception:
            pass
    if generated_class is None:
        generated_class = get_property(asset, "generated_class")
    if generated_class is not None:
        report["generated_class"] = serialise(generated_class)
        cdo = unreal.get_default_object(generated_class)
        report["cdo_available_attributes"] = [
            name
            for name in dir(cdo)
            if any(
                term in name.lower()
                for term in (
                    "interp",
                    "smooth",
                    "look",
                    "track",
                    "yaw",
                    "pitch",
                    "body",
                    "head",
                    "rotation",
                )
            )
        ]
        for name in report["cdo_available_attributes"]:
            value = get_property(cdo, name)
            if value is not None:
                report.setdefault("cdo_values", {})[name] = serialise(value)

    # Graph collections are not exposed as editable Blueprint properties in
    # every UE build. Loaded graph nodes are still visible through the object
    # iterator, so collect any whose package belongs to this asset.
    try:
        package_prefix = asset.get_outermost().get_path_name()
        loaded_nodes = []
        for node in unreal.ObjectIterator(unreal.EdGraphNode):
            try:
                if node.get_outermost().get_path_name() == package_prefix:
                    loaded_nodes.append(node_report(node))
            except Exception:
                pass
        report["loaded_nodes"] = loaded_nodes
    except Exception as exc:
        report["loaded_nodes_error"] = str(exc)

    return report


try:
    result = {"success": True, "assets": [asset_report(path) for path in ASSET_PATHS]}
    print("CODEX_MARIA_DIAG=" + json.dumps(result, sort_keys=True))
except Exception as exc:
    print(
        "CODEX_MARIA_DIAG="
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
