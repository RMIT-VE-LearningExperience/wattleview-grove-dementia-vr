"""Generate placeholder TTS WAVs for dialogue scenario lines (SAPI / Microsoft Hazel).

Reads the scenario CSV, finds every row with a VoiceAudio reference, and synthesizes
Docs/Scenarios/tts_out/SW_Maria_<NodeId>.wav via Windows SAPI (System.Speech, offline).
Voice: Microsoft Hazel Desktop (en-GB female), rate -1 for an unhurried elderly cadence.
Output: 44.1 kHz 16-bit mono WAV, ready for UE SoundWave import.

Swap for real VO later by replacing the imported SoundWave assets - no system changes.

Usage: python Scripts/generate_tts.py [Docs/Scenarios/Scenario_MorningVisit.csv]
"""
import csv, os, subprocess, sys, tempfile

csv_path = sys.argv[1] if len(sys.argv) > 1 else "Docs/Scenarios/Scenario_MorningVisit.csv"
out_dir = os.path.join(os.path.dirname(csv_path), "tts_out")
os.makedirs(out_dir, exist_ok=True)

with open(csv_path, newline="", encoding="utf-8-sig") as fh:
    rows = [r for r in csv.DictReader(fh) if (r.get("VoiceAudio") or "").strip()]

print(f"{len(rows)} voiced lines to synthesize -> {out_dir}")

PS_TEMPLATE = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('Microsoft Hazel Desktop')
$s.Rate = -1
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(44100, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$s.SetOutputToWaveFile('{out}', $fmt)
$s.Speak([IO.File]::ReadAllText('{txt}', [Text.Encoding]::UTF8))
$s.Dispose()
"""

fail = 0
for r in rows:
    node = r["Name"].strip()
    line = r["Line"].strip()
    wav = os.path.abspath(os.path.join(out_dir, f"SW_Maria_{node}.wav"))
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tf:
        tf.write(line)
        txt = tf.name
    ps = PS_TEMPLATE.format(out=wav.replace("'", "''"), txt=txt.replace("'", "''"))
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    os.unlink(txt)
    ok = os.path.exists(wav) and os.path.getsize(wav) > 1000
    print(("  OK   " if ok else "  FAIL ") + f"SW_Maria_{node}.wav" + ("" if ok else f"  ({res.stderr.strip()[:120]})"))
    if not ok:
        fail += 1

print("RESULT:", "ALL OK" if fail == 0 else f"{fail} FAILED")
sys.exit(0 if fail == 0 else 1)
