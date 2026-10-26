# Codex Spec 1/5 — Data assets (enum + structs)

> Part of the Dialogue MVP (see `PHASE0_FINDINGS.md` in this folder and
> `Docs/Scenarios/Scenario_MorningVisit.csv` for the content these carry).
> Claude's bridge cannot author UserDefinedStruct/Enum members — that's why this is a spec.
> Follow the backup convention first: copy any asset you touch into
> `Saved/CodexBackups/<Task>_<timestamp>/`.

## 1. `E_MariaEmotion` — UserDefinedEnum at `/Game/Dialogue/Data/E_MariaEmotion`

Entries, in this exact order (order matters — DataTable CSV import matches by name, but the
ABP Select node will be wired by index):

| Index | Display Name |
|---|---|
| 0 | Calm |
| 1 | Warm |
| 2 | Confused |
| 3 | Anxious |
| 4 | Agitated |

## 2. `S_DialogueNode` — UserDefinedStruct at `/Game/Dialogue/Data/S_DialogueNode`

Fields in this exact order with exact names (CSV headers must match — see the scenario CSV):

| Field | Type | Default |
|---|---|---|
| `Line` | String | "" |
| `VoiceAudio` | Sound Base (Object Reference) | None |
| `Emotion` | E_MariaEmotion | Calm |
| `DurationOverride` | Float | 0.0 |
| `AutoAdvanceTarget` | Name | None |
| `Option1Text` | String | "" |
| `Option1Target` | Name | None |
| `Option1Tag` | Name | None |
| `Option2Text` | String | "" |
| `Option2Target` | Name | None |
| `Option2Tag` | Name | None |
| `Option3Text` | String | "" |
| `Option3Target` | Name | None |
| `Option3Tag` | Name | None |
| `Option4Text` | String | "" |
| `Option4Target` | Name | None |
| `Option4Tag` | Name | None |
| `Notes` | String | "" |

## 3. `S_ChoiceLogEntry` — UserDefinedStruct at `/Game/Dialogue/Data/S_ChoiceLogEntry`

| Field | Type |
|---|---|
| `NodeId` | Name |
| `OptionIndex` | Integer |
| `Tag` | Name |
| `TimeSeconds` | Float |

## 4. DataTable creation + import (Claude takes over after 1-3 exist)

Claude will run: create `DT_Scenario_MorningVisit` from `S_DialogueNode` via the data_table MCP
tool, fill rows from `Docs/Scenarios/Scenario_MorningVisit.csv`, and set the CSV as the reimport
source. **Codex only needs to deliver assets 1–3 and report done.**

## Acceptance check

- All three assets exist at the exact paths, compile/save clean.
- `S_DialogueNode` field names EXACTLY match the CSV header row (case-sensitive):
  `Line,VoiceAudio,Emotion,DurationOverride,AutoAdvanceTarget,Option1Text,Option1Target,Option1Tag,…,Notes`
- Fallback if Codex tooling can't author struct members either: the human creates them in-editor
  from the tables above (~5 min); everything downstream is unchanged.
