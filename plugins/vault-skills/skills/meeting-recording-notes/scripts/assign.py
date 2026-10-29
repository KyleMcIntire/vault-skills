"""Group voices into speakers and build a speaker-labeled transcript. Fast (seconds); rerun freely.

Two modes:

1) Discovery: cluster into N voices and print sample lines per voice so you can name them.
     python assign.py --out-dir DIR --speakers 4
   Writes DIR/samples.txt and a provisional DIR/transcript.txt with "Speaker 1..N".

2) Named: seed each speaker from stretches where you know who was talking, then refine.
     python assign.py --out-dir DIR \
       --anchor "Alex=15:50-17:10,51:44-54:00" --anchor "Sam=1:00:27-1:03:00" ...
   Or map discovery clusters straight to names (cluster numbers from samples.txt):
     python assign.py --out-dir DIR --speakers 4 --names "1=Sam,2=Jo,3=Pat,4=Alex"
   Optional fixes for obvious slips: --override "19:33=Sam" (line starting at that time).

Outputs:
  DIR/lines.json      [{"s": sec, "sp": name, "t": text}, ...]
  DIR/transcript.txt  [HH:MM:SS] Name: text
  DIR/anchor_check.txt  (named mode) how cleanly each anchor matched its speaker
"""
import argparse, json, os, re
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--out-dir", required=True)
ap.add_argument("--speakers", type=int)
ap.add_argument("--anchor", action="append", default=[])
ap.add_argument("--names", default="")
ap.add_argument("--override", action="append", default=[])
a = ap.parse_args()
D = a.out_dir

def tsec(x):
    p = [float(v) for v in x.strip().split(":")]
    s = 0
    for v in p: s = s * 60 + v
    return s
def hms(s):
    s = int(s); return f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}"

E = np.load(os.path.join(D, "E.npy")); C = np.load(os.path.join(D, "C.npy"))
W = json.load(open(os.path.join(D, "words.json")))

if a.anchor:
    names, cents, report = [], [], []
    for spec in a.anchor:
        name, ranges = spec.split("=", 1)
        idx = np.concatenate([np.where((C >= tsec(r.split("-")[0])) & (C <= tsec(r.split("-")[1])))[0]
                              for r in ranges.split(",")])
        if len(idx) == 0:
            raise SystemExit(f"anchor {name}: no speech windows in {ranges}")
        names.append(name.strip()); c = E[idx].mean(0); cents.append(c / np.linalg.norm(c))
        report.append((name.strip(), idx))
    cent = np.array(cents)
    for _ in range(10):  # k-means style refinement seeded by the anchors
        lab = (E @ cent.T).argmax(1)
        cent = np.array([E[lab == k].mean(0) if (lab == k).any() else cent[k] for k in range(len(names))])
        cent /= np.linalg.norm(cent, axis=1, keepdims=True)
    with open(os.path.join(D, "anchor_check.txt"), "w") as f:
        for k, (n, idx) in enumerate(report):
            p = (E[idx] @ cent.T).argmax(1)
            share = (p == k).mean()
            f.write(f"{n}: {share:.0%} of its anchor windows matched ({len(idx)} windows)"
                    + ("  <-- weak anchor, pick a cleaner stretch\n" if share < 0.6 else "\n"))
else:
    if not a.speakers:
        raise SystemExit("give --speakers N (discovery) or --anchor NAME=ranges")
    from sklearn.cluster import KMeans
    km = KMeans(n_clusters=a.speakers, n_init=10, random_state=0).fit(E)
    cent = km.cluster_centers_ / np.linalg.norm(km.cluster_centers_, axis=1, keepdims=True)
    # number clusters by first appearance so labels read naturally
    lab0 = (E @ cent.T).argmax(1)
    order = list(dict.fromkeys(lab0.tolist()))
    order += [k for k in range(a.speakers) if k not in order]
    cent = cent[order]
    names = [f"Speaker {i+1}" for i in range(a.speakers)]
    if a.names:
        m = dict(kv.split("=") for kv in a.names.split(","))
        names = [m.get(str(i + 1), names[i]).strip() for i in range(a.speakers)]

S = E @ cent.T
# smooth window scores over ~±1.6 s so single noisy windows don't flip the speaker
sm = np.zeros_like(S)
for i in range(len(S)):
    sm[i] = S[np.abs(C - C[i]) <= 1.6].mean(0)

lab_w = []
for w in W:
    m = (w["s"] + w["e"]) / 2
    j = np.where(np.abs(C - m) <= 0.8)[0]
    if len(j) == 0:
        j = [int(np.abs(C - m).argmin())]
    lab_w.append(int(sm[j].sum(0).argmax()))

# remove flicker: <=2-word blips under 1 s between the same speaker
changed = True
while changed:
    changed = False
    runs, i = [], 0
    while i < len(lab_w):
        j = i
        while j + 1 < len(lab_w) and lab_w[j + 1] == lab_w[i]: j += 1
        runs.append((i, j)); i = j + 1
    for r, (s0, s1) in enumerate(runs):
        if 0 < r < len(runs) - 1 and s1 - s0 + 1 <= 2 and W[s1]["e"] - W[s0]["s"] < 1.0:
            if lab_w[runs[r - 1][0]] == lab_w[runs[r + 1][0]]:
                for k in range(s0, s1 + 1): lab_w[k] = lab_w[runs[r - 1][0]]
                changed = True

# words -> lines: break on speaker change, pause > 1.5 s, or a long run ending a sentence
lines, cur = [], None
for i, w in enumerate(W):
    sp = names[lab_w[i]]
    gap = w["s"] - W[i - 1]["e"] if i else 0
    if cur is None or sp != cur["sp"] or gap > 1.5 or (len(cur["t"].split()) > 45 and cur["t"].rstrip()[-1:] in ".?!"):
        if cur: lines.append(cur)
        cur = {"sp": sp, "s": w["s"], "t": w["w"].strip()}
    else:
        cur["t"] += w["w"]
if cur: lines.append(cur)

# fold tiny same-speaker fragments into the next line
merged = []
for l in lines:
    if merged and merged[-1]["sp"] == l["sp"] and len(merged[-1]["t"].split()) < 4 and l["s"] - merged[-1]["s"] < 6:
        merged[-1]["t"] += " " + l["t"]
    else:
        merged.append(dict(l))
lines = merged

for ov in a.override:
    t, name = ov.split("=")
    target = tsec(t)
    best = min(lines, key=lambda l: abs(l["s"] - target))
    best["sp"] = name.strip()

json.dump(lines, open(os.path.join(D, "lines.json"), "w"))
with open(os.path.join(D, "transcript.txt"), "w") as f:
    f.write("\n".join(f"[{hms(l['s'])}] {l['sp']}: {l['t']}" for l in lines) + "\n")

from collections import Counter
cnt = Counter(l["sp"] for l in lines)
if not a.anchor and not a.names:
    with open(os.path.join(D, "samples.txt"), "w") as f:
        for n in names:
            mine = sorted([l for l in lines if l["sp"] == n], key=lambda l: -len(l["t"]))[:6]
            f.write(f"=== {n}: {cnt[n]} lines\n")
            for l in sorted(mine, key=lambda l: l["s"]):
                f.write(f"  [{hms(l['s'])}] {l['t'][:220]}\n")
print("DONE", len(lines), "lines", dict(cnt))
