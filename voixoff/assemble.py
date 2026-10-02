#!/usr/bin/env python3
"""Pose chaque prise ElevenLabs sur son moment d'entrée (script voix off Athlete Pulse).

Les lignes à repères multiples (4, 8, 18, 19, 23) sont découpées aux pauses
naturelles de la prise, et chaque morceau est calé sur son repère à l'écran.
"""
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
TAKES = HERE / "prises"
TOTAL = 89.0  # la vidéo dure 1:29

# (n°, entrée en s, durée dispo en s, [(début morceau dans la prise, repère)] ou None)
SCRIPT = [
    (1, 1.5, 2.3, None),
    (2, 4.5, 2.0, None),
    (3, 7.0, 1.0, None),
    (4, 8.2, 4.0, [(0.00, 8.3), (0.71, 9.1), (1.41, 9.9), (2.17, 10.7), (2.86, 11.5)]),
    (5, 12.4, 1.1, None),
    (6, 14.0, 2.4, None),
    (7, 17.1, 2.7, None),
    (8, 20.1, 3.2, [(0.00, 20.2), (0.54, 20.8), (1.06, 21.4), (1.62, 21.9), (2.22, 22.4)]),
    (9, 23.7, 2.2, None),
    (10, 26.0, 1.6, None),
    (11, 27.9, 1.6, None),
    (12, 29.6, 2.4, None),
    (13, 34.2, 2.8, None),
    (14, 37.3, 2.8, None),
    (15, 40.3, 4.0, None),
    (16, 44.7, 3.0, None),
    (17, 48.1, 5.5, None),
    (18, 53.8, 6.7, [(0.00, 53.8), (1.22, 54.9), (2.97, 56.9), (4.07, 58.8)]),
    (19, 61.0, 3.4, [(0.00, 61.0), (0.90, 61.8), (1.74, 62.6)]),
    (20, 64.5, 2.2, None),
    (21, 66.8, 2.5, None),
    (22, 70.2, 3.0, None),
    (23, 73.6, 3.6, [(0.00, 73.5), (0.73, 74.8), (1.43, 76.0)]),
    (24, 77.7, 3.2, None),
    (25, 81.6, 1.4, None),
    (26, 83.3, 1.4, None),
]


def lead_silence(path):
    """Durée du silence en tête de prise, pour que la voix démarre pile au repère."""
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af",
         "silencedetect=noise=-35dB:d=0.02", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    m = re.search(r"silence_start: (-?[0-9.e-]+)\n.*?silence_end: ([0-9.]+)", out, re.S)
    return float(m.group(2)) if m and float(m.group(1)) <= 0.01 else 0.0


def duration(path):
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True).stdout)


def main():
    pieces = []  # (fichier, début, fin|None, position en s)
    for n, entry, avail, cues in SCRIPT:
        f = TAKES / f"{n:02d}.mp3"
        if cues is None:
            lead = lead_silence(f)
            pieces.append((f, lead, None, entry))
            speech = duration(f) - lead
            if speech > avail + 0.05:
                print(f"! ligne {n}: {speech:.2f}s pour {avail}s dispo")
        else:
            for i, (start, at) in enumerate(cues):
                end = cues[i + 1][0] if i + 1 < len(cues) else None
                lead = lead_silence(f) if i == 0 else 0.0
                pieces.append((f, max(start, lead), end, at))

    inputs, filters = [], []
    for k, (f, start, end, at) in enumerate(pieces):
        inputs += ["-i", str(f)]
        trim = f"atrim=start={start}" + (f":end={end}" if end else "")
        filters.append(f"[{k}:a]{trim},asetpts=PTS-STARTPTS,aresample=44100,"
                       f"adelay={int(at * 1000)}:all=1[p{k}]")
    mix = "".join(f"[p{k}]" for k in range(len(pieces)))
    filters.append(f"{mix}amix=inputs={len(pieces)}:normalize=0,apad=whole_dur={TOTAL},"
                   f"atrim=end={TOTAL},loudnorm=I=-16:TP=-1.5[out]")
    out = HERE / "voix_off_athlete_pulse.wav"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
                    "-filter_complex", ";".join(filters), "-map", "[out]",
                    "-ar", "48000", str(out)], check=True)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(out),
                    "-b:a", "192k", str(out.with_suffix(".mp3"))], check=True)
    print(f"OK {out} ({duration(out):.2f}s)")


if __name__ == "__main__":
    main()
