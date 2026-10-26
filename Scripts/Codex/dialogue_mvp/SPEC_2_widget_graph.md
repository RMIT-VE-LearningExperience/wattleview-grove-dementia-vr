# Codex Spec 2/4 — WBP_DialoguePanel graph

Asset: `/Game/Dialogue/UI/WBP_DialoguePanel` (already duplicated, tree rebuilt, styled, compiled).
Widget tree: `Border_0 > VerticalBox_48 > [SpeakerLabel, SubtitleText, Option1Button>Option1Text,
… Option4Button>Option4Text]`. The four `OnClicked (OptionNButton)` event nodes ALREADY EXIST in
the EventGraph (pre-bound). Backup convention applies.

## 1. Event dispatcher

`OnOptionChosen` — one param: `OptionIndex` (Integer).

## 2. Wire the four existing OnClicked events

`OnClicked (Option1Button)` → `Call OnOptionChosen(OptionIndex = 0)`
… Option2 → 1, Option3 → 2, Option4 → 3. (0-based — the station maps 0→Option1Target etc.)

## 3. Function `SetSubtitle(InText: String)`

SubtitleText → SetText(Text = ToText(InText)).

## 4. Function `SetOptions(InOptions: String Array)`

For i = 0..3: if `InOptions` has index i and its value is non-empty → set `Option{i+1}Text` text
to it and `Option{i+1}Button` visibility **Visible**; else visibility **Collapsed**.
(Straight-line 4× IsValidIndex+branch is fine — no loop needed.)

## 5. Delete legacy menu handlers

Any leftover event nodes referencing the removed menu buttons (Exit/Restart/Passthrough/
ResetOrientation) and their call chains (QuitGame, OpenLevel, passthrough toggles) — delete.
Keep anything unrelated to those four buttons.

## Acceptance

Compiles clean. `SetOptions` with ["A","B"] shows exactly buttons 1-2; with [] all collapsed.
Dispatcher fires with correct 0-based index per button (test via PIE PrintString).
