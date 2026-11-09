# GateLadder 0.9.169 — two-year survival round 1 (PAPER ONLY)

Request: pt212u (T1–T6) + t213 (T7–T8). The goal is to survive both years, not to earn more. Real accounts, the live app, and the V1 live paper (0.9.166 B6) were not touched.

## Periods
- Y2024 = 2024-11-04 00:00 ~ 2025-11-03 23:59 KST. Same input and warmup as 0.9.168 ①.
- Y2025 = 2025-11-04 00:00 ~ 2026-11-07 KST. Same input and warmup as .167 G1.

## Common settings = B6 exactly
- Engine167 with the .167 G1 config.
- Rescue START −2.0%; max 20 open; gap 0.3%; add size 3%; cyc TP +60; margin 40% pre-order pause.
- 1m line break market with TP +90; OFF mat:15m; TP_SET ma:1h=200 / mat:1h=200.
- TREND+RSI 30/70; per-direction cap 20%; fixed 3x.
- Fees: maker 0.018%, taker 0.042%, rebate 70%. These are the engine8 constants, which the frozen B6 baselines also used, so the fees are comparable.

## Baseline B6 is frozen and was not rerun
- Y2024 = live_0168/B6: rebate −19.296%, raw MDD 45.945%.
- Y2025 = live_0167/G1: rebate +15.712%, raw MDD 16.799%.

## New rules (rescue adds only; normal entry rules unchanged) — `engine169.py`
- **Trend pause.** Uses a closed-bar SMA: 4h close SMA120 (T1, T4–T7) or UTC-day close SMA50 (T2, T8). Bars are UTC-epoch aligned, like Binance candles.
  - Regime is set at each minute end: minute close > SMA ⇒ UP ⇒ no new short-rescue add orders, and any resting short add limit is cancelled before the next minute's fill check. Close ≤ SMA ⇒ DOWN ⇒ the same for longs.
  - The 3-tick counter keeps updating while paused. Already-filled adds keep their +60 TP and repayment.
- **Stale add close (30 days).** A filled rescue add open for more than 30 days is closed at the minute close ∓0.05% as taker. This is the same execution model as the existing .152 repay.
- **Opposite repay bank.**
  - Deposits: when a rescue-add TP on side A earns price gross while side B has an add older than 7 days, that gross is moved into B's bank and removed from A's .152 HELD bank. There is no double use.
  - Repays: at every closed 3m bar, B's oldest losing adds older than 7 days are closed in k-contract chunks, oldest first, using the .152 unit formula and execution. The loss is paid from the bank, not from B's own HELD bank.
- **Loss cap (10%).** If the sum of a side's losing rescue-add unrealized PnL exceeds 10% of account equity, the oldest losing adds are closed at market until the sum is under 10%.
- **TrendNet (T7/T8).**
  - Starting a net session: the trend side (UP ⇒ long, DOWN ⇒ short) gets one whenever it has no real active rescue session. The first add limit is placed at minute close −/+0.3%; it stays until filled or replaced.
  - Adding: after the first add, the same 3m 3-tick rule applies. Gap 0.3% vs open net adds, max 20 open net adds, margin 40% guard, TP +60. Size is 3% (T7) or 4% (T8, net adds only).
  - Ending: a trend flip or a real rescue start ends the net session. No new adds are placed after that; filled adds wait for their TP.
  - Net adds are excluded from side ROI and from rescue recovery accounting, so they never trigger or prolong a real rescue. They do count in margin, equity, and normal-direction exposure.

## Conditions
T1 pause 4h · T2 pause 1d · T3 stale30 · T4 T1+T3 · T5 T1+T3+opposite bank · T6 T1+loss cap 10 · T7 T1+TrendNet 4h (3%) · T8 1d pause + TrendNet 1d (net 4%).

## Files
- Per run: report.json (full .167-format report plus `rules169`), monthly.csv, repayments.csv, entries CSV, forced169.csv (every rule close), net_sessions169.csv, config, COMPLETE/finalized proofs, and independent_verification.txt.
- Top level: comparison.csv (both years side by side; B6 rows marked frozen), monthly_all.csv, judgment.json, SUMMARY_KO.md, INPUTS.json, VERIFICATION.json, SHA256.json, and DONE.json (last).

## Judgment
- Adoption candidate: rebate > 0 in both years AND raw MDD ≤ 25% in both years. Among candidates, pick the largest 2-year sum.
- If there is no candidate: the next-round base is the condition with Y2025 rebate ≥ +10% and the best Y2024 rebate.
- Adoption is the user's decision.
