# Roblox Up-and-Coming Top-10 Forecaster

Entry for make.fun bounty [Predict Roblox's Up-and-Coming top 10](https://make.fun/bounty/roblox-up-and-coming-forecast-01).

## What it does

`main.py` reads the chart history (`/input/history.ndjson`, `/input/task.json`) and writes
`/output/forecast.json`: per-place probabilities (places 1-10) plus a top-10 guess, scored
by log score against hourly chart reads over a 72-hour window.

## Model

- **Strength score** per game: blend of current/recent chart rank (0.7/0.3) plus
  player-count momentum (24h and 72h growth slopes).
- **Per-place probabilities**: Gaussian kernel over strength distance from each place's
  expected strength, mixed 10% toward uniform for calibration.
- **Reserve mass** (8% per place) left unnamed, shared by games that join the chart later —
  new entrants appear constantly on this chart, and log-score punishes zero probabilities.

Parameters were tuned on the public practice archive (2026-10-30 → 11-07 history,
72h window) and chosen from the center of a robust plateau, not the single best point:
practice log score **-30.9** vs. the house baseline **-43.51**.

## Run

```bash
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Python 3.13, standard library only, deterministic, runs in well under a second.

## License

MIT
