"""Transcribe a meeting recording with word-level timestamps (mlx-whisper, Apple Silicon).

Usage:
  python transcribe.py AUDIO --out-dir DIR [--prompt "names, jargon"] [--model REPO]

Writes into DIR:
  audio.wav    16 kHz mono copy (used later by embed.py)
  words.json   [{"s": start_sec, "e": end_sec, "w": " word"}, ...]
Prints "DONE <n_words> <duration_sec>" when finished. Roughly 3-5 min per hour of audio on M-series.
"""
import argparse, json, os, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument("audio")
ap.add_argument("--out-dir", required=True)
ap.add_argument("--prompt", default="", help="Attendee names and jargon to bias spelling")
ap.add_argument("--model", default="mlx-community/whisper-large-v3-turbo")
ap.add_argument("--language", default="en")
a = ap.parse_args()

os.makedirs(a.out_dir, exist_ok=True)
wav = os.path.join(a.out_dir, "audio.wav")
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", a.audio, "-ac", "1", "-ar", "16000", wav], check=True)
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", wav],
                           capture_output=True, text=True, check=True).stdout.strip())
print(f"audio {dur/60:.1f} min -> {wav}", flush=True)

import mlx_whisper  # imported late so ffmpeg errors surface first
r = mlx_whisper.transcribe(
    wav, path_or_hf_repo=a.model, language=a.language,
    condition_on_previous_text=False,  # avoids runaway repetition loops on long meetings
    word_timestamps=True, initial_prompt=a.prompt or None,
)
words = [{"s": w["start"], "e": w["end"], "w": w["word"]}
         for seg in r["segments"] for w in seg.get("words", [])]
json.dump(words, open(os.path.join(a.out_dir, "words.json"), "w"))
print("DONE", len(words), round(dur), flush=True)
