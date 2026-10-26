# Codex Spec 3/4 — BP_Maria function + ABP emotion chain

Prereq: `E_MariaEmotion` exists (Spec 1). Backup convention applies.
Reference dumps: `PHASE0_FINDINGS.md` (this folder).

## A. BP_Maria (`/Game/MetaHumans/Maria/BP_Maria`)

Already present (do NOT recreate): `VoiceAudio` AudioComponent (Z=150, auto-activate off),
`bIsSpeaking` (bool).

1. Add variable `CurrentEmotion` of type `E_MariaEmotion` (default Calm). (Claude's bridge can't
   make enum-typed vars until the enum exists; if you can't either, human fallback: 30 s in-editor.)
2. New function `SetConversationState(Emotion: E_MariaEmotion, Speaking: bool)`:
   `Set CurrentEmotion = Emotion` → `Set bIsSpeaking = Speaking`. Nothing else. (~4 nodes)

## B. ABP (`/Game/MetaHumans/Maria/Animations/ABP_Maria_NaturalLook`)

Already present: float vars `GazeAlpha`, `GazeAlphaTarget` (defaults 1.0).

### EventGraph — append to the existing `Event Blueprint Update Animation` chain
(after the existing `Set LookAtTargetWorld`, sequence off its exec):

1. `TryGetPawnOwner` is WRONG here — Maria isn't the pawn. Use `GetOwningActor` → `Cast to
   BP_Maria` (pure).
2. From cast: get `CurrentEmotion` → `Select` node (enum-driven, 5 pins):
   Calm=1.0, Warm=1.0, Confused=0.65, Anxious=0.5, Agitated=0.15 → this is `BaseTarget`.
3. Get `bIsSpeaking`; get `CurrentEmotion != Agitated` (NotEqual enum, literal Agitated);
   `AND` them → Branch/Select: if true → `GazeAlphaTarget = Max(BaseTarget, 0.9)` else
   `GazeAlphaTarget = BaseTarget`. (FMax node.)
4. `FInterpTo(Current=GazeAlpha, Target=GazeAlphaTarget, DeltaTime=GetWorldDeltaSeconds,
   InterpSpeed=1.5)` → `Set GazeAlpha`.
5. Cast-fail path: `Set GazeAlphaTarget = 1.0` (safety default so gaze never sticks off).

### AnimGraph — bind the two Alpha pins (see PHASE0_FINDINGS for node names)

- `AnimGraphNode_LookAt_16` (neck_02): Alpha pin currently literal **0.35** → expose/bind to
  `GazeAlpha * 0.35` (Multiply node, literal 0.35).
- `AnimGraphNode_LookAt_17` (head): Alpha literal **0.85** → bind to `GazeAlpha * 0.85`.
This preserves today's neck/head ratio exactly when GazeAlpha=1.0 (the out-of-conversation
default), so existing behavior is unchanged until a conversation modulates it.

## Acceptance

Compiles clean. In PIE with no conversation: behavior identical to before (gaze tracks HMD).
Setting `CurrentEmotion=Agitated` on the level Maria via console/debug → her head visibly stops
tracking (averts) within ~1–2 s; back to Calm → recovers. `bIsSpeaking=true` while Confused →
tracking strengthens to 0.9.
