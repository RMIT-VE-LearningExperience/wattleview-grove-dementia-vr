# Codex Spec 4/4 — BP_DialogueStation interpreter

Asset: `/Game/Dialogue/Blueprints/BP_DialogueStation` (duplicate of BP_Menu — see
`PHASE0_FINDINGS.md` for the full 154-node EventGraph inventory of what it inherited).
Prereqs: Specs 1–3 done; `DT_Scenario_MorningVisit` exists (Claude creates it right after Spec 1).
Backup convention applies.

Already present: Widget component → `WBP_DialoguePanel` @900×700; vars `StartRow`("Start"),
`TriggerDistance`(200.0), `CurrentRowName`, `bConversationActive`.

## 1. Add remaining variables

- `DialogueTable` — DataTable object ref, default `DT_Scenario_MorningVisit`
- `ChoiceLog` — Array of `S_ChoiceLogEntry`
- `MariaRef` — BP_Maria object ref | `PanelRef` — WBP_DialoguePanel object ref
- `ProximityHits` — Integer

## 2. Strip inherited hand-menu behavior (keep the interaction core!)

KEEP: BeginPlay EnableInput + AddMappingContext(IMC_Menu); cursor axis chains
(IA_Menu_Cursor_*) + cursor clamping; IA_Menu_Interact_* Press/Release PointerKey chains;
MenuLaser Niagara update + visibility; OpenMenuAnimationTimeline; `Set Widget Interaction
References`/`Set Motion Controller Reference` functions (the pawn calls them — verify the caller;
if they're only called by the menu-summon flow, call them ourselves in StartConversation using
the pawn's WidgetInteraction/controller components).

DELETE/NEUTRALIZE:
- Tick blocks "Rotate Widget towards camera" and "Move the widget to a comfortable location"
  (static bedside panel — level transform is authoritative)
- Attach-to-motion-controller chains (AttachComponentToComponent on MotionControllerAimRef)
- `CloseMenu` → DestroyActor: replace destroy with `Widget SetVisibility(false)` + laser off +
  RemoveMappingContext (station persists for re-trigger… MVP: no re-trigger, but don't destroy)

## 3. Wire the interpreter (§Runtime flow of the approved plan)

**BeginPlay** (append after inherited input setup): `MariaRef = GetActorOfClass(BP_Maria)`;
`PanelRef = Cast(Widget.GetUserWidgetObject)`; Bind `PanelRef.OnOptionChosen` →
`HandleOptionChosen`; `Widget.SetVisibility(false)`; `SetTimerByEvent(CheckProximity, 0.25, loop)`
after a `Delay(5.0)`.

**CheckProximity** (custom event): if `bConversationActive` → return. Distance(
`GetPlayerCameraManager(0).GetCameraLocation`, `MariaRef.GetActorLocation`) < `TriggerDistance`
→ `ProximityHits += 1` else `= 0`. If hits ≥ 2 → `StartConversation`.

**StartConversation**: `bConversationActive = true`; `Widget.SetVisibility(true)` (+ play
OpenMenuAnimationTimeline if trivially reusable); `PresentNode(StartRow)`.

**PresentNode(Row: Name)** (function or custom event): `CurrentRowName = Row`.
`GetDataTableRow(DialogueTable, Row)` → on fail: PrintString warn + `EndConversation`.
On success (break `S_DialogueNode`):
- `MariaRef.SetConversationState(Emotion, true)`
- `PanelRef.SetSubtitle(Line)`; `PanelRef.SetOptions(empty array)`
- If `VoiceAudio` valid: `MariaRef.VoiceAudio.SetSound(VoiceAudio)` + `.Play()`;
  `D = VoiceAudio.GetDuration()`; elif `DurationOverride > 0`: `D = DurationOverride`;
  else `D = 2.0 + 0.35 * (word count of Line)` (Split string by space → array length; a simple
  ParseIntoArray node).
- `SetTimerByEvent(OnLineFinished, D, no-loop)` (store handle; clear any prior).

**OnLineFinished**: `MariaRef.SetConversationState(row.Emotion, false)`.
Build `Opts` String-array from the row: for i=1..4 append `Option{i}Text` if non-empty.
If `Opts.Length > 0` → `PanelRef.SetOptions(Opts)`.
Elif `AutoAdvanceTarget` not None → `PresentNode(AutoAdvanceTarget)`.
Else → `EndConversation`.
(Row access: either re-fetch `GetDataTableRow(CurrentRowName)` — simplest — or cache the struct
in a var at PresentNode. Re-fetch is fine.)

**HandleOptionChosen(OptionIndex: int)**: re-fetch row. Select Target/Tag by index
(0→Option1Target/Tag … 3→Option4…). Append to `ChoiceLog`:
`{NodeId=CurrentRowName, OptionIndex, Tag, TimeSeconds=GetGameTimeInSeconds}`.
`PanelRef.SetOptions(empty)` → `PresentNode(Target)`.

**EndConversation**: `PanelRef.SetSubtitle("(conversation ends)")`; `Delay(3.0)` →
`Widget.SetVisibility(false)`; laser visibility off; RemoveMappingContext(IMC_Menu);
`bConversationActive` stays true (no re-trigger in MVP). ForEach `ChoiceLog` → PrintString
`NodeId | OptionIndex | Tag | Time` (dev debrief stub).

**GetChoiceLog** (pure function): returns `ChoiceLog`.

## Acceptance (PIE, VR Preview or flat)

Walk to Maria → conversation starts once (not during 5 s grace, never re-triggers).
Subtitle shows while options hidden; audio plays from Maria; options appear after the line;
laser-click each button; all branches reachable (PrintString `CurrentRowName` breadcrumb);
auto-advance beat (Start→Greet) plays; both end states reachable; ChoiceLog prints ordered
tagged entries; no errors in log. Claude then runs functional PIE checks + device build.
