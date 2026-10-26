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
  5. Attaches the player pawn to the anchor; LS_Story moving the anchor then carries the
     viewer through the viewpoint cuts. Each tick keeps the eyes on the anchor (see SNAP_CM),
     and 0.75 s after the story starts the headset yaw is recentred.
  6. Hides the body the viewer is "inside" and creates a player for LS_Story, but waits:
     the StartTarget marker is placed GAZE_DISTANCE in front of the viewpoint, and the story
     plays once the student has looked at it for GAZE_SECONDS (head gaze; the PICO 4 Ultra
     Enterprise has no eye tracking). No controller is needed. Without a StartTarget the
     story starts immediately.

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
# EnzoBlend value at which David becomes Enzo in Maria's view (keyed 1.0 at 4:36 cinematic).
ENZO_SWAP = 0.99
MPC = "/Game/Wattleview/Materials/MPC_Perception.MPC_Perception"
MAP_PATH = "/Game/Wattleview/Maps/L_ResidentRoom"
SNAP_CM = 40.0   # camera further than this from the anchor gets snapped back onto it
GAZE_SECONDS = 2.0      # look at the start marker this long to begin (head gaze; no eye tracking)
GAZE_COS = 0.993        # ~7 degree cone around the marker counts as looking at it
GAZE_DISTANCE = 160.0   # marker distance in front of the viewpoint (cm)

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
        N(id="delayRecentre", type="CallFunction", target="KismetSystemLibrary", function_name="Delay",
          pin_defaults={"Duration": "0.75"}),
        N(id="recentre", type="CallFunction", target="HeadMountedDisplayFunctionLibrary",
          function_name="ResetOrientationAndPosition",
          pin_defaults={"Yaw": "0.0", "Options": "Orientation"}),
        N(id="getBody", type="VariableGet", variable_name="HiddenBody"),
        N(id="bodyValid", type="MacroInstance", macro_name="IsValid"),
        N(id="hide", type="CallFunction", target="Actor", function_name="SetActorHiddenInGame",
          pin_defaults={"bNewHidden": "true"}),
        N(id="getStory", type="VariableGet", variable_name="Story"),
        N(id="makePlayer", type="CallFunction", target="LevelSequencePlayer",
          function_name="CreateLevelSequencePlayer"),
        N(id="setPlayer", type="VariableSet", variable_name="Player"),
        N(id="getStartTarget", type="VariableGet", variable_name="StartTarget"),
        N(id="tgtValid", type="MacroInstance", macro_name="IsValid"),
        N(id="anchorLoc2", type="CallFunction", target="Actor", function_name="K2_GetActorLocation"),
        N(id="anchorFwd", type="CallFunction", target="Actor", function_name="GetActorForwardVector"),
        N(id="fwdScaled", type="CallFunction", target="KismetMathLibrary", function_name="Multiply_VectorFloat",
          pin_defaults={"B": str(GAZE_DISTANCE)}),
        N(id="tgtLoc", type="CallFunction", target="KismetMathLibrary", function_name="Add_VectorVector"),
        N(id="tgtRot", type="CallFunction", target="KismetMathLibrary", function_name="FindLookAtRotation"),
        N(id="placeTgt", type="CallFunction", target="Actor", function_name="K2_SetActorLocationAndRotation",
          pin_defaults={"bSweep": "false", "bTeleport": "true"}),
        N(id="getPlayer", type="VariableGet", variable_name="Player"),
        N(id="setStartedNow", type="VariableSet", variable_name="Started", pin_defaults={"Started": "true"}),
        N(id="playNow", type="CallFunction", target="MovieSceneSequencePlayer", function_name="Play"),
        # ---- Tick: keep the viewer's eyes on the anchor -------------------------------
        # The tracking origin is not guaranteed (PICO may stay on a floor/stage origin, and a
        # system recenter resets it). Each frame, if the camera is more than SNAP_CM from the
        # anchor, move the pawn so the camera sits exactly on the anchor. Head movement within
        # that radius is untouched, so parallax stays natural.
        N(id="tick", type="Event", event_name="ReceiveTick"),
        N(id="tickSeq", type="Sequence"),
        N(id="getStarted", type="VariableGet", variable_name="Started"),
        N(id="branchStarted", type="Branch"),
        N(id="gCamMgr", type="CallFunction", target="GameplayStatics", function_name="GetPlayerCameraManager",
          pin_defaults={"PlayerIndex": "0"}),
        N(id="gCamLoc", type="CallFunction", target="PlayerCameraManager", function_name="GetCameraLocation"),
        N(id="gCamRot", type="CallFunction", target="PlayerCameraManager", function_name="GetCameraRotation"),
        N(id="gCamFwd", type="CallFunction", target="KismetMathLibrary", function_name="GetForwardVector"),
        N(id="gTgt", type="VariableGet", variable_name="StartTarget"),
        N(id="gTgtLoc", type="CallFunction", target="Actor", function_name="K2_GetActorLocation"),
        N(id="gToTgt", type="CallFunction", target="KismetMathLibrary", function_name="Subtract_VectorVector"),
        N(id="gDir", type="CallFunction", target="KismetMathLibrary", function_name="Normal"),
        N(id="gDot", type="CallFunction", target="KismetMathLibrary", function_name="Dot_VectorVector"),
        N(id="gLooking", type="CallFunction", target="KismetMathLibrary", function_name="Greater_DoubleDouble",
          pin_defaults={"B": str(GAZE_COS)}),
        N(id="branchLook", type="Branch"),
        N(id="getGP", type="VariableGet", variable_name="GazeProgress"),
        N(id="gStep", type="CallFunction", target="KismetMathLibrary", function_name="Divide_DoubleDouble",
          pin_defaults={"B": str(GAZE_SECONDS)}),
        N(id="gUp", type="CallFunction", target="KismetMathLibrary", function_name="Add_DoubleDouble"),
        N(id="gUpClamp", type="CallFunction", target="KismetMathLibrary", function_name="FMin",
          pin_defaults={"B": "1.0"}),
        N(id="gDown", type="CallFunction", target="KismetMathLibrary", function_name="Subtract_DoubleDouble"),
        N(id="gDownClamp", type="CallFunction", target="KismetMathLibrary", function_name="FMax",
          pin_defaults={"B": "0.0"}),
        N(id="setGPUp", type="VariableSet", variable_name="GazeProgress"),
        N(id="setGPDown", type="VariableSet", variable_name="GazeProgress"),
        N(id="gMPC", type="VariableGet", variable_name="Perception"),
        N(id="setGazeMPC", type="CallFunction", target="KismetMaterialLibrary",
          function_name="SetScalarParameterValue", pin_defaults={"ParameterName": "GazeProgress"}),
        N(id="gDone", type="CallFunction", target="KismetMathLibrary", function_name="GreaterEqual_DoubleDouble",
          pin_defaults={"B": "1.0"}),
        N(id="branchDone", type="Branch"),
        N(id="setStarted", type="VariableSet", variable_name="Started", pin_defaults={"Started": "true"}),
        N(id="hideTgt", type="CallFunction", target="Actor", function_name="K2_SetActorLocation",
          pin_defaults={"NewLocation": "0.0,0.0,-10000.0", "bSweep": "false", "bTeleport": "true"}),
        N(id="gPlayer", type="VariableGet", variable_name="Player"),
        N(id="playGaze", type="CallFunction", target="MovieSceneSequencePlayer", function_name="Play"),
        N(id="tickAnchor", type="VariableGet", variable_name="Anchor"),
        N(id="tickValid", type="MacroInstance", macro_name="IsValid"),
        N(id="hmd", type="CallFunction", target="HeadMountedDisplayFunctionLibrary",
          function_name="GetOrientationAndPosition"),
        N(id="tickPawn", type="CallFunction", target="GameplayStatics", function_name="GetPlayerPawn",
          pin_defaults={"PlayerIndex": "0"}),
        N(id="root", type="CallFunction", target="Actor", function_name="K2_GetRootComponent"),
        N(id="relT", type="CallFunction", target="SceneComponent", function_name="GetRelativeTransform"),
        N(id="breakT", type="CallFunction", target="KismetMathLibrary", function_name="BreakTransform"),
        N(id="sum", type="CallFunction", target="KismetMathLibrary", function_name="Add_VectorVector"),
        N(id="dist", type="CallFunction", target="KismetMathLibrary", function_name="VSize"),
        N(id="far", type="CallFunction", target="KismetMathLibrary", function_name="Greater_DoubleDouble",
          pin_defaults={"B": str(SNAP_CM)}),
        N(id="branchFar", type="Branch"),
        N(id="negate", type="CallFunction", target="KismetMathLibrary", function_name="NegateVector"),
        N(id="snap", type="CallFunction", target="Actor", function_name="K2_SetActorRelativeLocation",
          pin_defaults={"bSweep": "false", "bTeleport": "true"}),
        # ---- Enzo: in Maria's view only, David becomes Enzo once EnzoBlend reaches ENZO_SWAP
        # (4:30-4:36 cinematic, under a softness pulse keyed in the sequence). David's and
        # Corner views never swap: the sequence is shared, so this lives in the director.
        N(id="getEnzo", type="VariableGet", variable_name="EnzoOverlay"),
        N(id="enzoValid", type="MacroInstance", macro_name="IsValid"),
        N(id="getSwapped", type="VariableGet", variable_name="Swapped"),
        N(id="notSwapped", type="CallFunction", target="KismetMathLibrary", function_name="Not_PreBool"),
        N(id="getMV2", type="VariableGet", variable_name="MariaView"),
        N(id="isMariaView", type="CallFunction", target="KismetMathLibrary", function_name="Greater_DoubleDouble",
          pin_defaults={"B": "0.5"}),
        N(id="eMPC", type="VariableGet", variable_name="Perception"),
        N(id="getBlend", type="CallFunction", target="KismetMaterialLibrary",
          function_name="GetScalarParameterValue", pin_defaults={"ParameterName": "EnzoBlend"}),
        N(id="blendDone", type="CallFunction", target="KismetMathLibrary", function_name="GreaterEqual_DoubleDouble",
          pin_defaults={"B": str(ENZO_SWAP)}),
        N(id="and1", type="CallFunction", target="KismetMathLibrary", function_name="BooleanAND"),
        N(id="and2", type="CallFunction", target="KismetMathLibrary", function_name="BooleanAND"),
        N(id="branchSwap", type="Branch"),
        N(id="setSwapped", type="VariableSet", variable_name="Swapped", pin_defaults={"Swapped": "true"}),
        N(id="getBodyD2", type="VariableGet", variable_name="BodyDavid"),
        N(id="hideDavid", type="CallFunction", target="Actor", function_name="SetActorHiddenInGame",
          pin_defaults={"bNewHidden": "true"}),
        N(id="showEnzo", type="CallFunction", target="Actor", function_name="SetActorHiddenInGame",
          pin_defaults={"bNewHidden": "false"}),
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
        C("attach", "then", "bodyValid", "exec"),
        C("getBody", "HiddenBody", "bodyValid", "InputObject"),
        C("bodyValid", "Is Valid", "hide", "execute"),
        C("getBody", "HiddenBody", "hide", "self"),
        C("bodyValid", "Is Not Valid", "makePlayer", "execute"),
        C("hide", "then", "makePlayer", "execute"),
        C("getStory", "Story", "makePlayer", "LevelSequence"),
        C("makePlayer", "then", "setPlayer", "execute"),
        C("makePlayer", "ReturnValue", "setPlayer", "Player"),
        C("setPlayer", "then", "tgtValid", "exec"),
        C("getStartTarget", "StartTarget", "tgtValid", "InputObject"),
        # marker present: place it in front of the viewpoint, facing the viewer
        C("tgtValid", "Is Valid", "placeTgt", "execute"),
        C("getStartTarget", "StartTarget", "placeTgt", "self"),
        C("getAnchor", "Anchor", "anchorLoc2", "self"),
        C("getAnchor", "Anchor", "anchorFwd", "self"),
        C("anchorFwd", "ReturnValue", "fwdScaled", "A"),
        C("anchorLoc2", "ReturnValue", "tgtLoc", "A"),
        C("fwdScaled", "ReturnValue", "tgtLoc", "B"),
        C("tgtLoc", "ReturnValue", "tgtRot", "Start"),
        C("anchorLoc2", "ReturnValue", "tgtRot", "Target"),
        C("tgtLoc", "ReturnValue", "placeTgt", "NewLocation"),
        C("tgtRot", "ReturnValue", "placeTgt", "NewRotation"),
        C("placeTgt", "then", "delayRecentre", "execute"),
        # no marker: start straight away
        C("tgtValid", "Is Not Valid", "setStartedNow", "execute"),
        C("setStartedNow", "then", "playNow", "execute"),
        C("getPlayer", "Player", "playNow", "self"),
        C("playNow", "then", "delayRecentre", "execute"),
        C("delayRecentre", "then", "recentre", "execute"),
        # tick snap: eye offset from the anchor = pawn offset (anchor space) + HMD tracked position.
        # If it exceeds SNAP_CM (startup on a floor origin, a PICO recenter), set the pawn offset
        # to -HMD so the eyes land exactly on the anchor. Anchor cuts move pawn and anchor
        # together, so they never trigger a correction.
        C("tick", "then", "tickSeq", "execute"),
        C("tickSeq", "then_0", "tickValid", "exec"),
        # gaze to start (head gaze: the PICO 4 Ultra Enterprise has no eye tracking)
        C("tickSeq", "then_1", "branchStarted", "execute"),
        C("getStarted", "Started", "branchStarted", "Condition"),
        C("branchStarted", "else", "branchLook", "execute"),
        C("gCamMgr", "ReturnValue", "gCamLoc", "self"),
        C("gCamMgr", "ReturnValue", "gCamRot", "self"),
        C("gCamRot", "ReturnValue", "gCamFwd", "InRot"),
        C("gTgt", "StartTarget", "gTgtLoc", "self"),
        C("gTgtLoc", "ReturnValue", "gToTgt", "A"),
        C("gCamLoc", "ReturnValue", "gToTgt", "B"),
        C("gToTgt", "ReturnValue", "gDir", "A"),
        C("gCamFwd", "ReturnValue", "gDot", "A"),
        C("gDir", "ReturnValue", "gDot", "B"),
        C("gDot", "ReturnValue", "gLooking", "A"),
        C("gLooking", "ReturnValue", "branchLook", "Condition"),
        C("tick", "DeltaSeconds", "gStep", "A"),
        C("getGP", "GazeProgress", "gUp", "A"),
        C("gStep", "ReturnValue", "gUp", "B"),
        C("gUp", "ReturnValue", "gUpClamp", "A"),
        C("getGP", "GazeProgress", "gDown", "A"),
        C("tick", "DeltaSeconds", "gDown", "B"),
        C("gDown", "ReturnValue", "gDownClamp", "A"),
        C("branchLook", "then", "setGPUp", "execute"),
        C("gUpClamp", "ReturnValue", "setGPUp", "GazeProgress"),
        C("branchLook", "else", "setGPDown", "execute"),
        C("gDownClamp", "ReturnValue", "setGPDown", "GazeProgress"),
        C("setGPUp", "then", "setGazeMPC", "execute"),
        C("setGPDown", "then", "setGazeMPC", "execute"),
        C("gMPC", "Perception", "setGazeMPC", "Collection"),
        C("getGP", "GazeProgress", "setGazeMPC", "ParameterValue"),
        C("setGazeMPC", "then", "branchDone", "execute"),
        C("getGP", "GazeProgress", "gDone", "A"),
        C("gDone", "ReturnValue", "branchDone", "Condition"),
        C("branchDone", "then", "setStarted", "execute"),
        C("setStarted", "then", "hideTgt", "execute"),
        C("gTgt", "StartTarget", "hideTgt", "self"),
        C("hideTgt", "then", "playGaze", "execute"),
        C("gPlayer", "Player", "playGaze", "self"),
        C("tickAnchor", "Anchor", "tickValid", "InputObject"),
        C("tickValid", "Is Valid", "branchFar", "execute"),
        C("tickPawn", "ReturnValue", "root", "self"),
        C("root", "ReturnValue", "relT", "self"),
        C("relT", "ReturnValue", "breakT", "InTransform"),
        C("breakT", "Location", "sum", "A"),
        C("hmd", "DevicePosition", "sum", "B"),
        C("sum", "ReturnValue", "dist", "A"),
        C("dist", "ReturnValue", "far", "A"),
        C("far", "ReturnValue", "branchFar", "Condition"),
        C("branchFar", "then", "snap", "execute"),
        C("hmd", "DevicePosition", "negate", "A"),
        C("negate", "ReturnValue", "snap", "NewRelativeLocation"),
        C("tickPawn", "ReturnValue", "snap", "self"),
        # Enzo swap check, every frame once the story is playing
        C("branchStarted", "then", "enzoValid", "exec"),
        C("getEnzo", "EnzoOverlay", "enzoValid", "InputObject"),
        C("enzoValid", "Is Valid", "getBlend", "execute"),     # impure node: must sit on the exec chain
        C("getBlend", "then", "branchSwap", "execute"),
        C("getSwapped", "Swapped", "notSwapped", "A"),
        C("getMV2", "MariaView", "isMariaView", "A"),
        C("eMPC", "Perception", "getBlend", "Collection"),
        C("getBlend", "ReturnValue", "blendDone", "A"),
        C("notSwapped", "ReturnValue", "and1", "A"),
        C("isMariaView", "ReturnValue", "and1", "B"),
        C("and1", "ReturnValue", "and2", "A"),
        C("blendDone", "ReturnValue", "and2", "B"),
        C("and2", "ReturnValue", "branchSwap", "Condition"),
        C("branchSwap", "then", "setSwapped", "execute"),
        C("setSwapped", "then", "hideDavid", "execute"),
        C("getBodyD2", "BodyDavid", "hideDavid", "self"),
        C("hideDavid", "then", "showEnzo", "execute"),
        C("getEnzo", "EnzoOverlay", "showEnzo", "self"),
    ]
    return json.loads(unreal.MCPythonHelper.build_blueprint_graph(
        bp, "EventGraph", json.dumps({"nodes": nodes, "connections": connections})))


def disable_locomotion():
    """Remove IA_Turn / IA_Move mappings from the template's default mapping context."""
    imc = unreal.load_asset("/Game/XRFramework/Input/IMC_Default")
    removed = 0
    for action_name in ("IA_Turn", "IA_Move"):
        action = unreal.load_asset(f"/Game/XRFramework/Input/Actions/{action_name}")
        if imc is None or action is None:
            continue
        def count():
            return len(imc.get_editor_property("default_key_mappings").get_editor_property("mappings"))
        before = count()
        imc.unmap_all_keys_from_action(action)
        removed += before - count()
    if imc is not None:
        # Scripted unmaps don't mark the package dirty; a save-if-dirty writes nothing.
        eas.save_asset("/Game/XRFramework/Input/IMC_Default", only_if_is_dirty=False)
    log(f"locomotion disabled: {removed} thumbstick mappings removed from IMC_Default")


def place_director(bp):
    by_label = {a.get_actor_label(): a for a in acts.get_all_level_actors()}
    d = acts.spawn_actor_from_class(bel.generated_class(bp), unreal.Vector(250, 225, 300), unreal.Rotator(0, 0, 0))
    d.set_actor_label("StoryDirector")
    d.set_folder_path("Story")
    for var, label in [("AnchorDavid", "Anchor_David"), ("AnchorMaria", "Anchor_Maria"),
                       ("AnchorCorner", "Anchor_Corner"), ("BodyDavid", "David_StandIn"),
                       ("BodyMaria", "Maria_StandIn"), ("StartTarget", "StartTarget"),
                       ("EnzoOverlay", "Enzo_Overlay")]:
        if label in by_label:
            d.set_editor_property(var, by_label[label])
        else:
            log(f"missing {label}; {var} left empty")
    les.save_current_level()
    log("placed StoryDirector in " + MAP_PATH)


def build():
    ensure_level()
    remove_placed_directors()
    bp = recreate_blueprint()

    actor_ref = bel.get_object_reference_type(unreal.Actor)
    for name in ("AnchorDavid", "AnchorMaria", "AnchorCorner", "BodyDavid", "BodyMaria"):
        add_var(bp, name, actor_ref, True)
    add_var(bp, "StartTarget", actor_ref, True)
    add_var(bp, "EnzoOverlay", actor_ref, True)
    add_var(bp, "Swapped", bel.get_basic_type_by_name("bool"), False)
    add_var(bp, "Player", bel.get_object_reference_type(unreal.LevelSequencePlayer), False)
    add_var(bp, "GazeProgress", bel.get_basic_type_by_name("real"), False)
    add_var(bp, "Started", bel.get_basic_type_by_name("bool"), False)
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
    disable_locomotion()
    return bp


bp = build()
