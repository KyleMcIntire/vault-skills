"""Compute speaker embeddings over the speech in a transcribed recording.

Usage:
  python embed.py --out-dir DIR

Needs DIR/audio.wav and DIR/words.json from transcribe.py. Slides a 1.5 s window
(0.75 s hop) over regions where words were spoken and embeds each window with
SpeechBrain ECAPA (VoxCeleb). Uses Apple's GPU (mps) when available: about 1 min
per hour of audio on mps, 10+ min on CPU.

Writes DIR/E.npy (unit-normalized embeddings) and DIR/C.npy (window centers, sec).
"""
import argparse, json, os
import numpy as np, soundfile as sf, torch
from speechbrain.inference.speaker import EncoderClassifier

ap = argparse.ArgumentParser()
ap.add_argument("--out-dir", required=True)
ap.add_argument("--win", type=float, default=1.5)
ap.add_argument("--hop", type=float, default=0.75)
a = ap.parse_args()

dev = "mps" if torch.backends.mps.is_available() else "cpu"
wav, sr = sf.read(os.path.join(a.out_dir, "audio.wav"), dtype="float32")
words = json.load(open(os.path.join(a.out_dir, "words.json")))
enc = EncoderClassifier.from_hparams(
    source="speechbrain/spkrec-ecapa-voxceleb",
    savedir=os.path.join(os.environ.get("HF_HOME", "/tmp"), "ecapa"),
    run_opts={"device": dev})

T = len(wav) / sr
step = 0.05
speech = np.zeros(int(T / step) + 2, bool)
for w in words:
    speech[int(w["s"] / step):int(w["e"] / step) + 1] = True

embs, centers, batch, bt = [], [], [], []
def flush():
    global batch, bt
    if not batch:
        return
    x = torch.tensor(np.stack(batch)).to(dev)
    with torch.no_grad():
        e = enc.encode_batch(x).squeeze(1).cpu().numpy()
    embs.extend(e); centers.extend(bt); batch, bt = [], []

t, n_total = 0.0, int(T / a.hop)
i = 0
while t + a.win <= T:
    lo, hi = int(t / step), int((t + a.win) / step)
    if speech[lo:hi].mean() > 0.5:
        batch.append(wav[int(t * sr):int((t + a.win) * sr)]); bt.append(t + a.win / 2)
        if len(batch) == 64:
            flush()
    t += a.hop; i += 1
    if i % 1000 == 0:
        print(f"progress {100*i/n_total:.0f}%", flush=True)
flush()
E = np.array(embs); E /= np.linalg.norm(E, axis=1, keepdims=True)
np.save(os.path.join(a.out_dir, "E.npy"), E)
np.save(os.path.join(a.out_dir, "C.npy"), np.array(centers))
print("DONE", len(E), "windows on", dev, flush=True)
