#!/usr/bin/env python3
"""Roblox Up-and-Coming top-10 forecaster for make.fun bounty.

Reads /input/history.ndjson (chart snapshot history) and /input/task.json,
writes /output/forecast.json with per-place probabilities and a top-10 guess.

Model: strength = rank blend + player-count momentum, converted to per-place
probabilities with a Gaussian kernel around each place's expected strength,
mixed toward uniform for calibration (log-score friendly). Parameters were
tuned on the public practice archive and kept on a robust plateau.
"""
import json
import math
import os
from datetime import datetime, timezone

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

# tuned / robust plateau (practice backtest ~ -30.9, house baseline -43.51)
W_RANK = 0.5      # weight on rank-based strength
W_MOM = 0.5       # weight on player-count momentum
SPREAD = 3.5      # Gaussian kernel width (places of strength)
UNIFORM_MIX = 0.1
RESERVE = 0.08    # mass left unnamed per place for games that join the chart later
MOM_SCALE = 3.0


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def build_features(history):
    series = {}
    for line in history:
        t = parse_ts(line["at"])
        for g in line["up_and_coming"]:
            series.setdefault(g["universe_id"], []).append((t, g["rank"], g["playing"]))
    last = history[-1]
    t_last = parse_ts(last["at"])
    feats = {}
    for g in last["up_and_coming"]:
        uid = g["universe_id"]
        s = sorted(series.get(uid, []))
        cur_play = g["playing"]

        def slope(hours):
            past = [p for (t, r, p) in s if 0 < (t_last - t).total_seconds() <= hours * 3600]
            if not past:
                return 0.0
            return (cur_play - past[0]) / max(past[0], 1)

        prev_ranks = [r for (t, r, p) in s if 0 < (t_last - t).total_seconds() <= 48 * 3600]
        feats[uid] = {
            "rank": g["rank"],
            "playing": cur_play,
            "mom24": slope(24),
            "mom72": slope(72),
            "prev_min_rank": min(prev_ranks) if prev_ranks else g["rank"],
        }
    return feats


def forecast(feats, places=10):
    uids = list(feats.keys())
    strengths = {}
    for uid, f in feats.items():
        mom = 0.6 * f["mom24"] + 0.4 * f["mom72"]
        rs = -(0.7 * f["rank"] + 0.3 * f["prev_min_rank"])
        strengths[uid] = W_RANK * rs + W_MOM * (mom * MOM_SCALE)
    order = sorted(uids, key=lambda u: (-strengths[u], u))
    probs = {}
    n = len(uids)
    for k in range(1, places + 1):
        expected = strengths[order[min(k - 1, n - 1)]]
        scores = {u: math.exp(-((strengths[u] - expected) / SPREAD) ** 2) for u in uids}
        tot = sum(scores.values())
        for u in uids:
            probs[(u, k)] = (1 - UNIFORM_MIX) * scores[u] / tot + UNIFORM_MIX * (1.0 / n)
            probs[(u, k)] *= 1.0 - RESERVE
    return probs, order[:places]


def main():
    task = json.load(open(os.path.join(INPUT_DIR, "task.json")))
    places = task.get("places", 10)
    history = []
    with open(os.path.join(INPUT_DIR, "history.ndjson")) as f:
        for line in f:
            line = line.strip()
            if line:
                history.append(json.loads(line))

    feats = build_features(history)
    probs, top10 = forecast(feats, places)

    out = {
        "probabilities": [
            {"universe_id": u, "place": k, "p": round(p, 8)}
            for (u, k), p in sorted(probs.items())
        ],
        "top10": [int(u) for u in top10],
    }
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, task.get("output", "forecast.json")), "w") as f:
        json.dump(out, f, separators=(",", ":"))


if __name__ == "__main__":
    main()
