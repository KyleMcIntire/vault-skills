#!/usr/bin/env bash
# Create (or reuse) the Python env for transcription + speaker identification.
# Runs on the user's Mac (Apple Silicon). Idempotent: safe to call every time.
set -e
ROOT="${MEETING_NOTES_HOME:-$HOME/.cache/meeting-notes}"
VENV="$ROOT/venv"
mkdir -p "$ROOT"
command -v ffmpeg >/dev/null || { echo "ffmpeg missing: brew install ffmpeg"; exit 1; }
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi
if ! "$VENV/bin/python" -c "import mlx_whisper, torch, speechbrain, sklearn, soundfile" 2>/dev/null; then
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q mlx-whisper torch torchaudio speechbrain scikit-learn soundfile
fi
"$VENV/bin/python" -c "import mlx_whisper, torch, speechbrain, sklearn; print('env ok', torch.__version__)"
echo "PYTHON=$VENV/bin/python"
echo "HF_HOME=$ROOT/hf"
