"""Generate placeholder voice lines for Story V2 with Windows SAPI (offline).

Reads Docs/Production/Story_V2_Lines.csv and writes Docs/Production/tts_out/VO_<Id>.wav
(44.1 kHz 16-bit mono) for import as SoundWaves. Placeholder only: final voices will be
generated with ElevenLabs once the script is locked, using the same Ids, so swapping is
an asset reimport with no timeline changes.

Voices on this machine: Maria = Microsoft Hazel (en-GB), slowed for an older cadence.
David = Microsoft Zira pitched down via SSML (no male SAPI voice is installed).

Usage: python Scripts/generate_story_tts.py
"""
import csv
import os
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "Docs", "Production", "Story_V2_Lines.csv")
OUT_DIR = os.path.join(ROOT, "Docs", "Production", "tts_out")

VOICES = {
    # speaker: (SAPI voice, SSML prosody rate, pitch)
    "Maria": ("Microsoft Hazel Desktop", "-25%", "-5%"),
    "David": ("Microsoft Zira Desktop", "-5%", "-30%"),
}

PS = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(44100, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$s.SetOutputToWaveFile('{out}', $fmt)
$s.SpeakSsml([IO.File]::ReadAllText('{ssml}', [Text.Encoding]::UTF8))
$s.Dispose()
"""


def ssml(voice, rate, pitch, text):
    return ('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-GB">'
            f'<voice name="{voice}"><prosody rate="{rate}" pitch="{pitch}">{escape(text)}</prosody></voice></speak>')


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    failed = 0
    for r in rows:
        voice, rate, pitch = VOICES[r["Speaker"]]
        wav = os.path.join(OUT_DIR, f"VO_{r['Id']}.wav")
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as tf:
            tf.write(ssml(voice, rate, pitch, r["Line"]))
            path = tf.name
        res = subprocess.run(["powershell", "-NoProfile", "-Command",
                              PS.format(out=wav.replace("'", "''"), ssml=path.replace("'", "''"))],
                             capture_output=True, text=True)
        os.unlink(path)
        ok = os.path.exists(wav) and os.path.getsize(wav) > 1000
        failed += 0 if ok else 1
        print(("OK   " if ok else "FAIL ") + f"VO_{r['Id']}.wav  {r['Speaker']}: {r['Line'][:50]}"
              + ("" if ok else f"  ({res.stderr.strip()[:160]})"))
    print("RESULT:", "ALL OK" if failed == 0 else f"{failed} FAILED")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
