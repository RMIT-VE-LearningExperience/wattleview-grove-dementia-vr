# Phase 0 findings — Dialogue MVP (read-only graph dumps, 2026-07-20)

Backups: `Saved/CodexBackups/DialogueMVP_20260720_2134/` (BP_Maria, ABP_Maria_NaturalLook,
BP_Menu, WBP_Menu, BP_XRPawn, HospitalRoom.umap).

## ABP_Maria_NaturalLook

AnimGraph (7 nodes): `AnimGraphNode_SequencePlayer_8` (AS_Maria_RelaxedIdle) →
`AnimGraphNode_LocalToComponentSpace_8` → `AnimGraphNode_LookAt_16` (**Bone: neck_02, Alpha pin
UNLINKED literal 0.35**) → `AnimGraphNode_LookAt_17` (**Bone: head, Alpha pin UNLINKED literal
0.85**) → `AnimGraphNode_ComponentToLocalSpace_8` → `AnimGraphNode_Root_0`. Both LookAtLocation
pins linked (fed from LookAtTargetWorld).

EventGraph (14 nodes): BlueprintUpdateAnimation → GetPlayerPawn → CastTo BP_XRPawn → Get Camera →
GetWorldLocation → VInterpTo (smoothing) → Set LookAtTargetWorld. (Init event seeds it unsmoothed.)

**Spec implication**: emotion chain sets `GazeAlphaTarget` → FInterpTo → `GazeAlpha`; AnimGraph
binds `GazeAlpha` to BOTH LookAt Alpha pins. Scale head/neck: head = GazeAlpha × 0.85, neck =
GazeAlpha × 0.35 (preserve current ratio) OR simply bind both raw pins to
`GazeAlpha × <literal>` — pick simplest in editor.

## BP_Menu (154 EventGraph nodes) — duplication base for BP_DialogueStation

KEEP (device-verified interaction core):
- BeginPlay: EnableInput(PC0) + EnhancedInput AddMappingContext IMC_Menu (priority 1, note
  "Consume Input" comment)
- Cursor: `Get IA_Menu_Cursor_Left/Right` axis → cursor move + clamp (CursorLocationLimitY/Z from
  widget paint geometry)
- Click: `EnhancedInputAction IA_Menu_Interact_Left/Right_Pressed` → PressPointerKey /
  ReleasePointerKey on the pawn's WidgetInteraction components (WidgetInteractionRefLeft/Right,
  set via `Set Widget Interaction References`)
- Laser: MenuLaser Niagara vector-array updates + visibility
- OpenMenuAnimationTimeline (open/close scale anim)
- RemoveMappingContext on close path

STRIP/NEUTRALIZE (hand-menu behavior wrong for a static bedside panel):
- Attach-to-motion-controller chains (AttachComponentToComponent + MotionControllerAimRef
  positioning, bActiveMenuHandRight toggle logic can stay dormant if unlinked)
- Tick "Rotate Widget towards camera" + "Move the widget to a comfortable location" repositioning
- CloseMenu → DestroyActor (replace with hide; station persists)
- The four menu button handlers (bound in WBP: ExitButton, RestartButton, PassthroughButton,
  ResetOrientationButton)

## BP_Maria (29 EventGraph nodes)

BeginPlay/AnimInit → LiveLink setup (UseLiveLink bool). Tick → GetPlayerPawn → cast → camera loc →
FindLookAtRotation → clamp → RInterpToConstant → SetActorRotation = **whole-body slow turn toward
player** (Codex-added). Leave untouched; gaze-aversion via LookAt alphas still reads correctly
against a facing body.

**Spec implication**: add function `SetConversationState(Emotion E_MariaEmotion, bSpeaking bool)`
setting the two new vars. ~4 nodes. Also new `VoiceAudio` AudioComponent (added in Phase 2,
template-level).

## WBP_Menu (10 widgets) — duplication base for WBP_DialoguePanel

Tree: `Border_0` → `VerticalBox_48` → Buttons `PassthroughButton`, `ResetOrientationButton`,
`RestartButton`, `ExitButton`, each with one TextBlock child (`Text_*`).

Restructure for WBP_DialoguePanel: rename buttons → `Option1Button..Option4Button` (+ their
TextBlocks → `Option1Text..`), insert at top of VerticalBox: `SpeakerLabel` TextBlock ("MARIA")
and `SubtitleText` TextBlock (wrap on, ~36pt). Widget events to (re)wire: 4 × OnClicked →
`OnOptionChosen(index)` dispatcher; functions `SetSubtitle(String)`, `SetOptions(String[])`.

## MCPythonHelper notes (for graph work)

`get_blueprint_graph_info(<loaded BP asset>, '<GraphName>')` — takes the loaded Blueprint object,
NOT a path string. Write tools exist: `add_blueprint_node`, `connect_blueprint_pins`,
`build_blueprint_graph`. JSON keys: `node_name`, `node_title`, `node_class`, `pins[]` with
`pin_name`, `direction`, `type`, `sub_type`, `default_value`, `linked_to[]`.
