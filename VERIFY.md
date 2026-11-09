# VERIFY — reproduction of the original runs / 원래 엔진 재현 검증

Verified on 2026-11-10 (KST). The runs used a **clean copy** of this package (`/tmp/ee_verify`, `/tmp/ee_verify2`; nothing
imported from the original work dir: run_meta `foreign_modules` = {}), a fresh venv with `requirements.txt` (Python 3.13.5,
numpy 2.5.4, pandas 3.0.6), and the package CLI `python run.py --config configs/<NAME>.json --out <DIR>`.
`python verify_results.py <DIR>` compares a run against `expected/frozen_baselines.json`. It checks the % values at 3
decimals, equity_raw at 6 decimals, and the closed-trade record count.

## 1. Full-year reproduction (expected = frozen original Linux runs)

| run | expected rebate % / raw MDD % | got | trades exp / got | equity_raw exp / got | trades.csv vs original | wall time | peak RSS |
|---|---|---|---|---|---|---|---|
| W4_Y2024 | +4.976 / 19.986 | **+4.976 / 19.986** | 5051 / 5051 | 939.507516 / 939.507516 | byte-identical | 3376 s* | 594 MB |
| W4_Y2025 | +15.684 / 7.675 | **+15.684 / 7.675** | 4275 / 4275 | 1058.240470 / 1058.240470 | byte-identical (+ monthly, equity, repayments) | 3493 s* | 678 MB |
| X5_Y2024 | +9.292 / 20.325 | **+9.292 / 20.325** | 4938 / 4938 | 971.332202 / 971.332202 | byte-identical | 2497 s | 601 MB |
| X5_Y2025 | +20.079 / 9.771 | **+20.079 / 9.771** | 4004 / 4004 | 1098.971697 / 1098.971697 | byte-identical | 2621 s | 678 MB |

All four PASS. The other figures also match exactly: raw return, rebate MDD and max margin
(W4_Y2024 −6.049 / 13.312 / 40.833; W4_Y2025 +5.824 / 4.835 / 41.855; X5_Y2024 −2.867 / 14.327 / 46.289;
X5_Y2025 +9.897 / 6.927 / 43.283).
\* W4 ran at nice 15 while 12 other backtests were using the CPU. X5 ran at nice 19 on a less loaded machine.
Expect ≈ 40–60 min per year on one core.

X5 = adopted app 0.9.171 condition (W4 + rescue add 5 % + rescue TP +80; see SWITCHES.md §3). Frozen values for
X1–X4 and X6 and for B6/T1/U4/V4/W6 are also in `expected/frozen_baselines.json`, but only W4 and X5 were rerun here.

## 2. Derived inputs
`python verify_data.py --derive` proves that the warm-up seeds, the SMA table and the replay minute set built from
`data/*.npz` are bit-identical (canonical SHA256) to the pickled inputs of the original Y2024/Y2025 runs.

## 3. Custom period smoke (master data only)

| config | period (KST) | rebate % | raw MDD % | trades | wall | peak RSS |
|---|---|---|---|---|---|---|
| examples/W4_custom_2026-03.json | 2026-03-01 ~ 2026-03-31 (whole day) | +0.687 | 2.875 | 484 | 231 s | 305 MB |
| examples/X5_custom_2026-03.json | same | +1.191 | 3.501 | 504 | 229 s | 305 MB |

All outputs were written (report.json, summary.json, trades.csv, entries.csv, monthly.csv, equity.csv, …). These have no
frozen reference; they are smoke tests only.

## 4. `strategy_overrides` default = original engine (method)
The full-year W4 runs above were made BEFORE `gl/overrides.py` was added. The X5 full-year runs were made with the final
code (no overrides set) and match exactly. In addition, a **bit-identical short-window check** was done:
the 3-day W4 window 2026-03-01 ~ 03-03 (45 trades) was run with the final code and compared with the same window run
by the unmodified code. trades.csv, equity.csv, monthly.csv, repayments.csv, entries.csv and report.json are
byte-identical, and events.log is identical line by line apart from the wall-clock prefix.
With overrides set (`disable_rules ["추세선 닿으면 반대"]`, `triangle_enabled false`, `tp_usdt {"fib1": 60}`), the same
window removed the touch-reverse and triangle entries (2 refused, 0 tri1; −0.823 % → −0.461 %). This shows the switches
take effect, while the default changes nothing.

## 5. Error paths
A period before the data, a missing minute, an unknown or unreviewed switch value (engine constructor ValueError /
assert) or unknown `strategy_overrides` keys each stop with exit code **2** and an `ERROR …` line. Engine exceptions
exit with code **1**.
