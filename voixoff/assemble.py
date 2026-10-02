#!/usr/bin/env python3
"""Monte la voix off Athlete Pulse à partir des blocs ElevenLabs (dossier blocs/).

Chaque bloc a été généré d'un seul tenant pour garder une intonation qui enchaîne.
On le découpe aux pauses entre phrases et on pose chaque phrase sur son moment
d'entrée. Un fond d'air très léger court sous toute la piste et chaque morceau
entre et sort en fondu : le son ne tombe jamais à zéro.
"""
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
BLOCS = HERE / "blocs"
TOTAL = 89.0  # la vidéo dure 1:29
TARGET_LUFS = -16.0
AIR_DB = -43  # fond d'air ≈ -55 dBFS sur la piste finale, couvert par la musique

# (bloc, début parole, fin parole, position dans la vidéo, lignes du script)
UNITS = [
    ("A", 0.00, 1.82, 1.5, "1"),
    ("A", 2.11, 4.05, 4.5, "2"),
    ("A", 4.22, 4.79, 7.0, "3"),
    ("A", 5.08, 8.46, 8.2, "4"),
    ("A", 8.66, 9.44, 12.4, "5"),
    ("B", 0.00, None, 14.0, "6"),
    ("C", 0.00, 2.08, 17.1, "7"),
    ("C", 2.39, 6.16, 19.7, "8"),
    ("C", 6.62, 8.47, 23.7, "9"),
    ("C", 8.78, 10.21, 26.0, "10"),
    ("C", 10.37, 13.32, 27.9, "11-12"),
    ("D", 0.00, 1.93, 34.2, "13"),
    ("D", 2.29, 4.36, 37.3, "14"),
    ("D", 4.56, 7.89, 40.3, "15"),
    ("E", 0.00, 2.47, 44.7, "16"),
    ("E", 2.73, 7.17, 48.1, "17"),
    ("E", 7.50, 12.91, 53.8, "18"),
    ("E", 13.15, 16.15, 61.0, "19"),
    ("F", 0.00, 1.16, 64.5, "20"),
    ("F", 1.51, 2.70, 66.6, "21"),
    ("F", 2.99, 4.95, 70.2, "22"),
    ("G", 0.00, 0.60, 73.5, "23 Prévenir"),
    ("G", 0.78, 1.27, 74.8, "23 Adapter"),
    ("G", 1.76, 2.58, 76.0, "23 Individualiser"),
    ("G", 2.84, 5.63, 77.7, "24"),
    ("G", 5.86, 6.45, 81.6, "25"),
    ("G", 6.61, 7.28, 83.3, "26"),
]

PAD_IN, PAD_OUT = 0.04, 0.12  # on garde un peu d'attaque et la fin de souffle


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True)


def first_speech(path):
    out = run("ffmpeg", "-hide_banner", "-i", str(path), "-af",
              "silencedetect=noise=-35dB:d=0.02", "-f", "null", "-").stderr
    m = re.search(r"silence_start: (-?[0-9.e-]+)\n.*?silence_end: ([0-9.]+)", out, re.S)
    return float(m.group(2)) if m and float(m.group(1)) <= 0.01 else 0.0


def build(units, out_wav):
    inputs, filters = [], []
    for k, (bloc, start, end, at, _) in enumerate(units):
        f = BLOCS / f"{bloc}.mp3"
        if start == 0.0:
            start = first_speech(f)
        s = max(0.0, start - PAD_IN)
        trim = f"atrim=start={s:.3f}" + (f":end={end + PAD_OUT:.3f}" if end else "")
        length = (end + PAD_OUT - s) if end else 30
        inputs += ["-i", str(f)]
        filters.append(
            f"[{k}:a]{trim},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=mono,"
            f"afade=t=in:d=0.03,areverse,afade=t=in:d={min(0.12, length / 4):.3f},areverse,"
            f"adelay={int((at - (start - s)) * 1000)}:all=1[v{k}]")
    n = len(units)
    # piste muette de référence : ancre le mixage à 0:00
    filters.append(f"anullsrc=r=48000:cl=mono,atrim=end={TOTAL}[zero]")
    filters.append("[zero]" + "".join(f"[v{k}]" for k in range(n)) +
                   f"amix=inputs={n + 1}:normalize=0:duration=first[voice]")
    filters.append(f"anoisesrc=d={TOTAL}:c=pink:r=48000:a=1,highpass=f=120,lowpass=f=5000,"
                   f"volume={AIR_DB}dB[air]")
    filters.append("[voice][air]amix=inputs=2:normalize=0[out]")
    run("ffmpeg", "-y", "-hide_banner", *inputs, "-filter_complex", ";".join(filters),
        "-map", "[out]", "-ac", "1", "-ar", "48000", str(out_wav))


def main():
    raw = HERE / "_brut.wav"
    build(UNITS, raw)
    # gain linéaire vers -16 LUFS (pas de compression : le fond d'air reste au même niveau)
    stats = run("ffmpeg", "-hide_banner", "-i", str(raw), "-af", "ebur128", "-f", "null", "-").stderr
    lufs = float(re.findall(r"I:\s+(-?[0-9.]+) LUFS", stats)[-1])
    out = HERE / "voix_off_athlete_pulse.wav"
    run("ffmpeg", "-y", "-hide_banner", "-i", str(raw), "-af",
        f"volume={TARGET_LUFS - lufs:.2f}dB,alimiter=limit=0.84", str(out))
    run("ffmpeg", "-y", "-hide_banner", "-i", str(out), "-b:a", "192k", str(out.with_suffix(".mp3")))
    raw.unlink()
    print(f"OK {out} (gain {TARGET_LUFS - lufs:+.1f} dB)")


if __name__ == "__main__":
    main()
