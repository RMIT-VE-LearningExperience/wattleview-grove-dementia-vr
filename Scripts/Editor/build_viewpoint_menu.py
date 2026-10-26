"""Add viewpoint buttons to the XRFramework VR menu (WBP_Menu) and fix Restart.

The template menu opens with the controller menu button and is driven by the laser
pointer. This adds:
  * Support worker view -> OpenLevel L_ResidentRoom ?view=David
  * Resident view       -> OpenLevel L_ResidentRoom ?view=Maria
  * Observer view       -> OpenLevel L_ResidentRoom ?view=Corner
and repoints Restart (which opened the template's missing VRTemplateMap) to
L_ResidentRoom with the current options, so it restarts in the same viewpoint.

BP_StoryDirector reads the "view" option on BeginPlay (default: David).
Requires the UnrealMCPython plugin. Re-runnable.
"""
import json

import unreal
from UnrealMCPython import blueprint_actions as bpa
from UnrealMCPython import umg_actions as umg

WBP = "/Game/XRFramework/Blueprints/WBP_Menu"
MAP_NAME = "/Game/Wattleview/Maps/L_ResidentRoom"
BUTTONS = [
    ("ViewDavidButton", "Support worker view", "view=David"),
    ("ViewMariaButton", "Resident view", "view=Maria"),
    ("ViewCornerButton", "Observer view", "view=Corner"),
]


def log(msg):
    unreal.log("[Menu] " + msg)


def call(fn, **kw):
    r = json.loads(fn(**kw))
    if not r.get("success", False):
        raise RuntimeError(f"{fn.__name__} failed: {r}")
    return r


def graph_nodes():
    bp = unreal.load_asset(WBP)
    return json.loads(unreal.MCPythonHelper.get_blueprint_graph_info(bp, "EventGraph"))["nodes"]


def remove_nodes_where(pred):
    for n in graph_nodes():
        if pred(n):
            call(bpa.ue_remove_blueprint_node, asset_path=WBP, graph_name="EventGraph", node_name=n["node_name"])


def add_node(**node):
    return call(bpa.ue_add_blueprint_node, asset_path=WBP, graph_name="EventGraph", node_json=node)["node_name"]


def connect(a, ap, b, bp):
    call(bpa.ue_connect_blueprint_pins, asset_path=WBP, graph_name="EventGraph",
         source_node=a, source_pin=ap, target_node=b, target_pin=bp)


def build():
    info = call(umg.ue_get_widget_blueprint_info, asset_path=WBP)
    existing = {w["name"] for w in info["widgets"]}
    style = call(umg.ue_get_widget_property, asset_path=WBP, widget_name="RestartButton",
                 property_name="WidgetStyle")["value"]

    # Clean previous runs: bound events + their OpenLevel nodes, then the widgets.
    names = {b[0] for b in BUTTONS}
    remove_nodes_where(lambda n: any(f"({b})" in n["node_title"] for b in names))
    remove_nodes_where(lambda n: n["node_title"].startswith("Open Level") and
                       not any(l for p in n["pins"] for l in p.get("linked_to", [])))
    for button, _, _ in BUTTONS:
        if button in existing:
            call(umg.ue_remove_widget, asset_path=WBP, widget_name=button)

    for button, label, option in BUTTONS:
        call(umg.ue_add_widget, asset_path=WBP, widget_type="Button", widget_name=button, parent_name="VerticalBox_48")
        call(umg.ue_set_widget_property, asset_path=WBP, widget_name=button, property_name="WidgetStyle", value=style)
        text = f"Text_{button}"
        call(umg.ue_add_widget, asset_path=WBP, widget_type="TextBlock", widget_name=text, parent_name=button)
        call(umg.ue_set_widget_property, asset_path=WBP, widget_name=text, property_name="Text", value=label)
        call(umg.ue_set_text_style, asset_path=WBP, widget_name=text, font_size=24)
        call(umg.ue_compile_widget_blueprint, asset_path=WBP)

        event = call(umg.ue_bind_widget_event, asset_path=WBP, widget_name=button, event_name="OnClicked")
        event_node = event["node"]
        open_node = add_node(type="CallFunction", target="GameplayStatics", function_name="OpenLevel",
                             pin_defaults={"LevelName": MAP_NAME, "bAbsolute": "true", "Options": option})
        connect(event_node, "then", open_node, "execute")
        log(f"{button}: {label} -> {option}")

    # Restart: replace the OpenLevel(VRTemplateMap) with L_ResidentRoom + current options.
    nodes = graph_nodes()
    stale = [n for n in nodes if n["node_title"].startswith("Open Level")
             and any(p.get("default_value") == "VRTemplateMap" for p in n["pins"])]
    delay = [n for n in nodes if n["node_title"] == "Delay"]
    if stale and delay:
        call(bpa.ue_remove_blueprint_node, asset_path=WBP, graph_name="EventGraph", node_name=stale[0]["node_name"])
        restart_open = add_node(type="CallFunction", target="GameplayStatics", function_name="OpenLevel",
                                pin_defaults={"LevelName": MAP_NAME, "bAbsolute": "true"})
        game_mode = add_node(type="CallFunction", target="GameplayStatics", function_name="GetGameMode")
        options = add_node(type="VariableGet", variable_name="OptionsString", variable_class="GameModeBase")
        connect(delay[0]["node_name"], "then", restart_open, "execute")
        connect(game_mode, "ReturnValue", options, "self")
        connect(options, "OptionsString", restart_open, "Options")
        log("Restart now reopens L_ResidentRoom with the current viewpoint")

    result = call(bpa.ue_compile_blueprint, asset_path=WBP)
    unreal.EditorAssetLibrary.save_asset(WBP, only_if_is_dirty=False)
    log(f"compiled: {result.get('status')}")


build()
