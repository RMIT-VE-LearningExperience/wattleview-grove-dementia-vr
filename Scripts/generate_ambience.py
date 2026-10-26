"""Synthesize placeholder ambience and effects for Story V2 (numpy + Windows SAPI, offline).

Writes Docs/Production/tts_out/AMB_*.wav and SFX_*.wav at 22.05 kHz 16-bit mono.
Loops (AMB_*) are made seamless by crossfading their tail into their head.

  AMB_RoomTone          quiet room noise floor (loop)
  AMB_Fan               ceiling fan hum + blade whoosh (loop). Last sound to fade in Maria's view.
  AMB_Garden            birds over soft wind, heard through the window (loop)
  AMB_TVNews            newsreader babble through a small TV speaker (loop)
  AMB_TVNews_Muffled    the same, muffled: Maria hears the TV as "a grey blur of speech" (loop)
  SFX_Corridor_Normal   45 s of ordinary hallway chatter through a door (David / observer)
  SFX_Corridor_Loud     45 s of the same chatter amplified and overlapping (Maria, 3:15-4:00)
  SFX_Heartbeat         50 s heartbeat, Maria's view 1:40-2:30

Placeholder quality: replace with recorded/library audio later using the same names.
Usage: python Scripts/generate_ambience.py
"""
import os
import subprocess
import tempfile
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "Docs", "Production", "tts_out")
SR = 22050
rng = np.random.default_rng(20261026)


# ------------------------------------------------------------------ dsp helpers
def band(x, lo=None, hi=None):
    """Zero-phase FFT band-pass (brick wall softened with a short cosine ramp)."""
    n = len(x)
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    gain = np.ones_like(f)
    w = 0.25
    if lo:
        gain *= np.clip((f - lo * (1 - w)) / (lo * w), 0, 1)
    if hi:
        gain *= np.clip((hi * (1 + w) - f) / (hi * w), 0, 1)
    return np.fft.irfft(spec * gain, n)


def norm(x, peak=0.9):
    m = np.max(np.abs(x)) or 1.0
    return x * (peak / m)


def db(x, gain_db):
    return x * (10 ** (gain_db / 20))


def seamless(x, fade_s=1.5):
    """Crossfade the last fade_s seconds into the start so the clip loops cleanly."""
    k = int(fade_s * SR)
    head, body, tail = x[:k], x[k:-k], x[-k:]
    ramp = np.linspace(0, 1, k)
    return np.concatenate([tail * (1 - ramp) + head * ramp, body])


def echo(x, delays=(0.09, 0.17, 0.29), decay=0.45):
    y = x.copy()
    for i, d in enumerate(delays):
        s = int(d * SR)
        y[s:] += x[:-s] * (decay ** (i + 1))
    return y


def write(name, x):
    os.makedirs(OUT, exist_ok=True)
    data = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    path = os.path.join(OUT, name + ".wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print(f"OK   {name}.wav  {len(x) / SR:.1f} s")


def noise(seconds):
    return rng.standard_normal(int(seconds * SR))


# ------------------------------------------------------------------ speech babble via SAPI
PS = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('{voice}')
$s.Rate = {rate}
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo({sr}, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$s.SetOutputToWaveFile('{out}', $fmt)
$s.Speak([IO.File]::ReadAllText('{txt}', [Text.Encoding]::UTF8))
$s.Dispose()
"""


def speak(text, voice, rate):
    with tempfile.TemporaryDirectory() as td:
        txt = os.path.join(td, "t.txt")
        wav = os.path.join(td, "o.wav")
        with open(txt, "w", encoding="utf-8") as fh:
            fh.write(text)
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        PS.format(voice=voice, rate=rate, sr=SR, out=wav, txt=txt)],
                       capture_output=True, check=True)
        with wave.open(wav) as w:
            return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768


VOICES = ["Microsoft Hazel Desktop", "Microsoft Zira Desktop"]

CHATTER = [
    "Morning! Is the tea trolley coming round soon?",
    "Has anyone seen the key for the linen cupboard?",
    "Room twelve needs a hand with breakfast, when you get a minute.",
    "Her daughter rang again, she'll come in after lunch.",
    "I'll take the trolley down, can you grab the towels?",
    "Did you sign the handover sheet yet?",
    "Lovely day out there, isn't it.",
    "The physio's running late this morning.",
    "Just going to do the round on the east wing.",
    "Can someone check on Mister Harris, he was up early.",
]

NEWS = [
    "Good morning, and here are the headlines. Overnight showers have cleared across the state, "
    "with a warm and sunny day expected for most areas.",
    "In local news, community gardens have reported a record harvest this season, "
    "with volunteers sharing produce across the region.",
    "Traffic on the main arterial roads is moving well this morning, with some delays near the city.",
    "And the weather today, mostly sunny, a top of twenty eight degrees, light winds in the afternoon.",
]


def babble(lines, seconds, layers):
    out = np.zeros(int(seconds * SR))
    clips = [speak(t, VOICES[i % 2], (i % 3) - 1) for i, t in enumerate(lines)]
    for layer in range(layers):
        pos = int(rng.uniform(0, 3) * SR)
        while pos < len(out):
            c = clips[rng.integers(len(clips))] * rng.uniform(0.5, 1.0)
            end = min(len(out), pos + len(c))
            out[pos:end] += c[: end - pos]
            pos = end + int(rng.uniform(0.4, 2.5) * SR)
    return out


# ------------------------------------------------------------------ beds
def room_tone():
    x = band(noise(30), 40, 900)
    return seamless(db(norm(x), -38))


def fan():
    t = np.arange(int(30 * SR)) / SR
    hum = 0.6 * np.sin(2 * np.pi * 50 * t) + 0.3 * np.sin(2 * np.pi * 100 * t)
    whoosh = band(noise(30), 150, 1800) * (0.55 + 0.45 * np.sin(2 * np.pi * 2.6 * t) ** 2)
    return seamless(db(norm(0.25 * hum + whoosh), -24))


def garden():
    secs = 30
    x = band(noise(secs), 80, 600) * 0.15          # soft wind
    t = np.arange(int(0.12 * SR)) / SR
    for _ in range(70):                              # chirps: quick downward sine sweeps
        f0 = rng.uniform(2800, 5200)
        sweep = np.sin(2 * np.pi * (f0 * t - rng.uniform(4000, 9000) * t * t))
        env = np.sin(np.pi * t / t[-1]) ** 2
        chirp = sweep * env * rng.uniform(0.2, 0.6)
        for rep in range(rng.integers(1, 4)):
            start = int(rng.uniform(0, secs - 1) * SR) + rep * int(0.15 * SR)
            end = min(len(x), start + len(chirp))
            x[start:end] += chirp[: end - start]
    return seamless(db(norm(x), -22))


def tv_news():
    x = babble(NEWS, 40, 1)
    tv = band(x, 280, 4200)                           # small TV speaker
    muffled = band(x, 120, 700)                       # "grey blur of muffled speech"
    return seamless(db(norm(tv), -20)), seamless(db(norm(muffled), -20))


def corridor():
    x = babble(CHATTER, 45, 3)
    normal = db(norm(band(x, 150, 1600)), -26)        # through a closed door, ordinary
    loud = band(babble(CHATTER, 45, 6), 90, 6000)     # more voices, overlapping
    loud = db(norm(echo(loud)), -6)                   # amplified, hard to make out
    fade = np.minimum(1, np.arange(len(loud)) / (4 * SR))   # swells in over 4 s
    return normal, loud * fade


def heartbeat():
    secs, bpm = 50, 88
    x = np.zeros(int(secs * SR))
    t = np.arange(int(0.11 * SR)) / SR
    thump = np.sin(2 * np.pi * 55 * t) * np.exp(-t * 38)
    beat = 60.0 / bpm
    k = 0.0
    while k < secs - 1:
        rate_up = 1 - 0.18 * min(1, k / secs * 2)      # quickens a little
        for offset, amp in ((0.0, 1.0), (0.24, 0.7)):  # lub-dub
            s = int((k + offset) * SR)
            x[s:s + len(thump)] += thump * amp
        k += beat * rate_up
    return db(norm(band(x, 30, 300)), -10)


def main():
    write("AMB_RoomTone", room_tone())
    write("AMB_Fan", fan())
    write("AMB_Garden", garden())
    tv, muffled = tv_news()
    write("AMB_TVNews", tv)
    write("AMB_TVNews_Muffled", muffled)
    normal, loud = corridor()
    write("SFX_Corridor_Normal", normal)
    write("SFX_Corridor_Loud", loud)
    write("SFX_Heartbeat", heartbeat())
    print("RESULT: ALL OK")


if __name__ == "__main__":
    main()
