"""Branch-integrity validator for dialogue scenario CSVs (S_DialogueNode schema).

Usage:  python Scripts/Codex/validate_dialogue_table.py [Docs/Scenarios/Scenario_MorningVisit.csv]

Checks: every Option/AutoAdvance target resolves to a row; option counts are 0 or 2-4;
options and AutoAdvanceTarget are mutually exclusive; at least one end state exists and is
reachable; no unreachable rows; Start row exists; audio paths (when set) follow the
/Game/Dialogue/Audio/SW_*.SW_* convention; every option has Text+Target+Tag together.
Exit code 0 = valid.
"""
import csv, sys, os

path = sys.argv[1] if len(sys.argv) > 1 else "Docs/Scenarios/Scenario_MorningVisit.csv"
errors, warnings = [], []

with open(path, newline="", encoding="utf-8-sig") as fh:
    rows = list(csv.DictReader(fh))

byname = {r["Name"]: r for r in rows}
if len(byname) != len(rows):
    errors.append("duplicate row names present")
if "Start" not in byname:
    errors.append("no 'Start' row")

def options(r):
    out = []
    for i in range(1, 5):
        t, tgt, tag = (r.get(f"Option{i}Text") or "").strip(), (r.get(f"Option{i}Target") or "").strip(), (r.get(f"Option{i}Tag") or "").strip()
        if t or tgt or tag:
            if not (t and tgt and tag):
                errors.append(f"{r['Name']}: Option{i} incomplete (needs Text+Target+Tag)")
            out.append((t, tgt, tag))
    return out

ends, edges = [], {}
for r in rows:
    name = r["Name"]
    opts = options(r)
    auto = (r.get("AutoAdvanceTarget") or "").strip()
    if opts and auto:
        errors.append(f"{name}: has both options and AutoAdvanceTarget")
    if len(opts) == 1:
        errors.append(f"{name}: exactly 1 option (must be 0 or 2-4)")
    targets = [t for _, t, _ in opts] + ([auto] if auto else [])
    for t in targets:
        if t not in byname:
            errors.append(f"{name}: target '{t}' does not exist")
    edges[name] = targets
    if not targets:
        ends.append(name)
    va = (r.get("VoiceAudio") or "").strip()
    if va and not (va.startswith("/Game/Dialogue/Audio/SW_") and "." in va):
        warnings.append(f"{name}: VoiceAudio '{va}' off-convention")
    if not va and float(r.get("DurationOverride") or 0) == 0:
        warnings.append(f"{name}: no audio and no DurationOverride (will use word-count fallback)")

if not ends:
    errors.append("no end state (row with no options and no auto-advance)")

# reachability from Start
seen, stack = set(), ["Start"] if "Start" in byname else []
while stack:
    n = stack.pop()
    if n in seen: continue
    seen.add(n)
    stack += [t for t in edges.get(n, []) if t in byname]
unreachable = sorted(set(byname) - seen)
for u in unreachable:
    errors.append(f"unreachable row: {u}")
if ends and not any(e in seen for e in ends):
    errors.append("no end state reachable from Start")

print(f"{os.path.basename(path)}: {len(rows)} rows, {len(ends)} end state(s): {ends}")
for w in warnings: print("  WARN:", w)
for e in errors: print("  ERROR:", e)
print("RESULT:", "VALID" if not errors else "INVALID")
sys.exit(0 if not errors else 1)
