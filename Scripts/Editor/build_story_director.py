"""Create BP_StoryDirector, place it in L_ResidentRoom, and wire the viewpoints.

On BeginPlay the director:
  1. Sets an eye-level tracking origin (a seated student gets the character's eye height).
  2. Reads the "view" travel option (WBP_Menu buttons reopen the map with ?view=David,
     ?view=Maria or ?view=Corner). No option means David: the script requires students
     to see the support worker's view first.
  3. Picks that viewpoint's anchor, hidden body and MariaView:
       David  -> Anchor_David,  David_StandIn, 0
       Maria  -> Anchor_Maria,  Maria_StandIn, 1
       Corner -> Anchor_Corner, (none),        0
  4. Sets MPC_Perception.MariaView, so Maria's perception layer only shows in her view.
  5. Attaches the player pawn to the anchor and recentres the headset; LS_Story moving
     the anchor then carries the viewer through the viewpoint cuts.
  6. Hides the body the viewer is "inside", then creates a player for LS_Story and plays.

The per-view actor references are set on the placed instance. Direct references avoid
array/for-each nodes, whose wildcard pins the scripted graph builder cannot resolve.

Requires the UnrealMCPython plugin (graph builder). Run in the open editor:
  exec(open(r"<this file>").read())
Re-runnable. Order matters: the placed instance is destroyed BEFORE the Blueprint asset
is deleted; deleting a Blueprint with a live instance in the level crashes the editor
(TickTaskManager assertion).
"""
import json

import unreal

BP_DIR = "/Game/Wattleview/Blueprints"
BP_NAME = "BP_StoryDirector"
BP_PATH = f"{BP_DIR}/{BP_NAME}"
SEQ = "/Game/Wattleview/Cinematics/LS_Story.LS_Story"
MPC = "/Game/Wattleview/Materials/MPC_Perception.MPC_Perception"
MAP_PATH = "/Game/Wattleview/Maps/L_ResidentRoom"
SNAP_CM = 40.0   # camera further than this from the anchor gets snapped back onto it

bel = unreal.BlueprintEditorLibrary
eas = unreal.EditorAssetLibrary
acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)


def log(msg):
    unreal.log("[Director] " + msg)


def ensure_level():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None or world.get_path_name().split(".")[0] != MAP_PATH:
        les.load_level(MAP_PATH)


def remove_placed_directors():
    removed = 0
    for a in acts.get_all_level_actors():
        if a.get_actor_label().startswith("StoryDirector"):
            acts.destroy_actor(a)
            removed += 1
    if removed:
        les.save_current_level()
    unreal.SystemLibrary.collect_garbage()


def recreate_blueprint():
    if eas.does_asset_exist(BP_PATH):
        eas.delete_asset(BP_PATH)
    return bel.create_blueprint_asset_with_parent(BP_PATH, unreal.Actor)


def add_var(bp, name, pin_type, editable):
    bel.add_member_variable(bp, name, pin_type)
    bel.set_blueprint_variable_instance_editable(bp, name, editable)
    bel.set_blueprint_variable_category(bp, name, unreal.Text("Story"))


def build_graph(bp):
    def N(**kw):
        return kw

    def C(a, ap, b, bp_):
        return {"source_node": a, "source_pin": ap, "target_node": b, "target_pin": bp_}

    nodes = [
        N(id="begin", type="Event", event_name="ReceiveBeginPlay"),
        N(id="origin", type="CallFunction", target="HeadMountedDisplayFunctionLibrary",
          function_name="SetTrackingOrigin", pin_defaults={"Origin": "Eye"}),
        # "view" travel option
        N(id="gameMode", type="CallFunction", target="GameplayStatics", function_name="GetGameMode"),
        N(id="options", type="VariableGet", variable_name="OptionsString", variable_class="GameModeBase"),
        N(id="parse", type="CallFunction", target="GameplayStatics", function_name="ParseOption",
          pin_defaults={"Key": "view"}),
        N(id="isMaria", type="CallFunction", target="KismetStringLibrary", function_name="EqualEqual_StriStri",
          pin_defaults={"B": "Maria"}),
        N(id="isCorner", type="CallFunction", target="KismetStringLibrary", function_name="EqualEqual_StriStri",
          pin_defaults={"B": "Corner"}),
        N(id="branchMaria", type="Branch"),
        N(id="branchCorner", type="Branch"),
        # Maria
        N(id="getAnchorMaria", type="VariableGet", variable_name="AnchorMaria"),
        N(id="getBodyMaria", type="VariableGet", variable_name="BodyMaria"),
        N(id="setAnchorM", type="VariableSet", variable_name="Anchor"),
        N(id="setBodyM", type="VariableSet", variable_name="HiddenBody"),
        N(id="setViewM", type="VariableSet", variable_name="MariaView", pin_defaults={"MariaView": "1.0"}),
        # Corner (no hidden body)
        N(id="getAnchorCorner", type="VariableGet", variable_name="AnchorCorner"),
        N(id="setAnchorC", type="VariableSet", variable_name="Anchor"),
        N(id="setBodyC", type="VariableSet", variable_name="HiddenBody"),
        N(id="setViewC", type="VariableSet", variable_name="MariaView", pin_defaults={"MariaView": "0.0"}),
        # David (default)
        N(id="getAnchorDavid", type="VariableGet", variable_name="AnchorDavid"),
        N(id="getBodyDavid", type="VariableGet", variable_name="BodyDavid"),
        N(id="setAnchorD", type="VariableSet", variable_name="Anchor"),
        N(id="setBodyD", type="VariableSet", variable_name="HiddenBody"),
        N(id="setViewD", type="VariableSet", variable_name="MariaView", pin_defaults={"MariaView": "0.0"}),
        # start
        N(id="getMPC", type="VariableGet", variable_name="Perception"),
        N(id="getMariaView", type="VariableGet", variable_name="MariaView"),
        N(id="setMariaView", type="CallFunction", target="KismetMaterialLibrary",
          function_name="SetScalarParameterValue", pin_defaults={"ParameterName": "MariaView"}),
        N(id="pawn", type="CallFunction", target="GameplayStatics", function_name="GetPlayerPawn",
          pin_defaults={"PlayerIndex": "0"}),
        N(id="getAnchor", type="VariableGet", variable_name="Anchor"),
        N(id="attach", type="CallFunction", target="Actor", function_name="K2_AttachToActor",
          pin_defaults={"LocationRule": "SnapToTarget", "RotationRule": "SnapToTarget",
                        "ScaleRule": "KeepWorld"}),
        N(id="recentre", type="CallFunction", target="HeadMountedDisplayFunctionLibrary",
          function_name="ResetOrientationAndPosition", pin_defaults={"Yaw": "0.0"}),
        N(id="getBody", type="VariableGet", variable_name="HiddenBody"),
        N(id="bodyValid", type="MacroInstance", macro_name="IsValid"),
        N(id="hide", type="CallFunction", target="Actor", function_name="SetActorHiddenInGame",
          pin_defaults={"bNewHidden": "true"}),
        N(id="getStory", type="VariableGet", variable_name="Story"),
        N(id="makePlayer", type="CallFunction", target="LevelSequencePlayer",
          function_name="CreateLevelSequencePlayer"),
        N(id="play", type="CallFunction", target="MovieSceneSequencePlayer", function_name="Play"),
        # ---- Tick: keep the viewer's eyes on the anchor -------------------------------
        # The tracking origin is not guaranteed (PICO may stay on a floor/stage origin, and a
        # system recenter resets it). Each frame, if the camera is more than SNAP_CM from the
        # anchor, move the pawn so the camera sits exactly on the anchor. Head movement within
        # that radius is untouched, so parallax stays natural.
        N(id="tick", type="Event", event_name="ReceiveTick"),
        N(id="tickAnchor", type="VariableGet", variable_name="Anchor"),
        N(id="tickValid", type="MacroInstance", macro_name="IsValid"),
        N(id="camMgr", type="CallFunction", target="GameplayStatics", function_name="GetPlayerCameraManager",
          pin_defaults={"PlayerIndex": "0"}),
        N(id="camLoc", type="CallFunction", target="PlayerCameraManager", function_name="GetCameraLocation"),
        N(id="anchorLoc", type="CallFunction", target="Actor", function_name="K2_GetActorLocation"),
        N(id="diff", type="CallFunction", target="KismetMathLibrary", function_name="Subtract_VectorVector"),
        N(id="dist", type="CallFunction", target="KismetMathLibrary", function_name="VSize"),
        N(id="far", type="CallFunction", target="KismetMathLibrary", function_name="Greater_DoubleDouble",
          pin_defaults={"B": str(SNAP_CM)}),
        N(id="branchFar", type="Branch"),
        N(id="negate", type="CallFunction", target="KismetMathLibrary", function_name="NegateVector"),
        N(id="tickPawn", type="CallFunction", target="GameplayStatics", function_name="GetPlayerPawn",
          pin_defaults={"PlayerIndex": "0"}),
        N(id="snap", type="CallFunction", target="Actor", function_name="K2_AddActorWorldOffset",
          pin_defaults={"bSweep": "false", "bTeleport": "true"}),
    ]
    connections = [
        C("begin", "then", "origin", "execute"),
        C("origin", "then", "branchMaria", "execute"),
        C("gameMode", "ReturnValue", "options", "self"),
        C("options", "OptionsString", "parse", "Options"),
        C("parse", "ReturnValue", "isMaria", "A"),
        C("parse", "ReturnValue", "isCorner", "A"),
        C("isMaria", "ReturnValue", "branchMaria", "Condition"),
        C("isCorner", "ReturnValue", "branchCorner", "Condition"),
        # Maria
        C("branchMaria", "then", "setAnchorM", "execute"),
        C("getAnchorMaria", "AnchorMaria", "setAnchorM", "Anchor"),
        C("setAnchorM", "then", "setBodyM", "execute"),
        C("getBodyMaria", "BodyMaria", "setBodyM", "HiddenBody"),
        C("setBodyM", "then", "setViewM", "execute"),
        C("setViewM", "then", "setMariaView", "execute"),
        # not Maria -> Corner?
        C("branchMaria", "else", "branchCorner", "execute"),
        C("branchCorner", "then", "setAnchorC", "execute"),
        C("getAnchorCorner", "AnchorCorner", "setAnchorC", "Anchor"),
        C("setAnchorC", "then", "setBodyC", "execute"),
        C("setBodyC", "then", "setViewC", "execute"),
        C("setViewC", "then", "setMariaView", "execute"),
        # otherwise David
        C("branchCorner", "else", "setAnchorD", "execute"),
        C("getAnchorDavid", "AnchorDavid", "setAnchorD", "Anchor"),
        C("setAnchorD", "then", "setBodyD", "execute"),
        C("getBodyDavid", "BodyDavid", "setBodyD", "HiddenBody"),
        C("setBodyD", "then", "setViewD", "execute"),
        C("setViewD", "then", "setMariaView", "execute"),
        # start
        C("getMPC", "Perception", "setMariaView", "Collection"),
        C("getMariaView", "MariaView", "setMariaView", "ParameterValue"),
        C("setMariaView", "then", "attach", "execute"),
        C("pawn", "ReturnValue", "attach", "self"),
        C("getAnchor", "Anchor", "attach", "ParentActor"),
        C("attach", "then", "recentre", "execute"),
        C("recentre", "then", "bodyValid", "exec"),
        C("getBody", "HiddenBody", "bodyValid", "InputObject"),
        C("bodyValid", "Is Valid", "hide", "execute"),
        C("getBody", "HiddenBody", "hide", "self"),
        C("bodyValid", "Is Not Valid", "makePlayer", "execute"),
        C("hide", "then", "makePlayer", "execute"),
        C("getStory", "Story", "makePlayer", "LevelSequence"),
        C("makePlayer", "then", "play", "execute"),
        C("makePlayer", "ReturnValue", "play", "self"),
        # tick snap
        C("tick", "then", "tickValid", "exec"),
        C("tickAnchor", "Anchor", "tickValid", "InputObject"),
        C("tickValid", "Is Valid", "branchFar", "execute"),
        C("camMgr", "ReturnValue", "camLoc", "self"),
        C("tickAnchor", "Anchor", "anchorLoc", "self"),
        C("camLoc", "ReturnValue", "diff", "A"),
        C("anchorLoc", "ReturnValue", "diff", "B"),
        C("diff", "ReturnValue", "dist", "A"),
        C("dist", "ReturnValue", "far", "A"),
        C("far", "ReturnValue", "branchFar", "Condition"),
        C("branchFar", "then", "snap", "execute"),
        C("diff", "ReturnValue", "negate", "A"),
        C("negate", "ReturnValue", "snap", "DeltaLocation"),
        C("tickPawn", "ReturnValue", "snap", "self"),
    ]
    return json.loads(unreal.MCPythonHelper.build_blueprint_graph(
        bp, "EventGraph", json.dumps({"nodes": nodes, "connections": connections})))


def place_director(bp):
    by_label = {a.get_actor_label(): a for a in acts.get_all_level_actors()}
    d = acts.spawn_actor_from_class(bel.generated_class(bp), unreal.Vector(250, 225, 300), unreal.Rotator(0, 0, 0))
    d.set_actor_label("StoryDirector")
    d.set_folder_path("Story")
    for var, label in [("AnchorDavid", "Anchor_David"), ("AnchorMaria", "Anchor_Maria"),
                       ("AnchorCorner", "Anchor_Corner"), ("BodyDavid", "David_StandIn"),
                       ("BodyMaria", "Maria_StandIn")]:
        d.set_editor_property(var, by_label[label])
    les.save_current_level()
    log("placed StoryDirector in " + MAP_PATH)


def build():
    ensure_level()
    remove_placed_directors()
    bp = recreate_blueprint()

    actor_ref = bel.get_object_reference_type(unreal.Actor)
    for name in ("AnchorDavid", "AnchorMaria", "AnchorCorner", "BodyDavid", "BodyMaria"):
        add_var(bp, name, actor_ref, True)
    add_var(bp, "Anchor", actor_ref, False)
    add_var(bp, "HiddenBody", actor_ref, False)
    add_var(bp, "MariaView", bel.get_basic_type_by_name("real"), False)
    add_var(bp, "Story", bel.get_object_reference_type(unreal.LevelSequence), False)
    add_var(bp, "Perception", bel.get_object_reference_type(unreal.MaterialParameterCollection), False)
    bel.compile_blueprint(bp)

    cdo = unreal.get_default_object(bel.generated_class(bp))
    cdo.set_editor_property("Story", unreal.load_asset(SEQ))
    cdo.set_editor_property("Perception", unreal.load_asset(MPC))

    result = build_graph(bp)
    log("graph: " + json.dumps({k: v for k, v in result.items() if k not in ("nodes", "node_id_to_name")}))
    bel.compile_blueprint(bp)
    eas.save_loaded_asset(bp)
    place_director(bp)
    return bp


bp = build()
