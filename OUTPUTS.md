# OUTPUTS — result files / 결과 파일

`python run.py --config X.json --out OUTDIR` writes (all UTF-8; times are epoch ms unless the column says `_kst`;
KST = fixed UTC+9 regardless of the PC's time zone):

| file | content |
|---|---|
| `summary.json` | **flat headline metrics** — the same columns as the .172/.173 `comparison.csv` (see below). Best file for a GUI. |
| `report.json` | full report (same builder as the original `report_v2_0173`): headline numbers, `monthly`, rescue (`cyc`) stats, repayment, stuck positions, filter counters, `rules169` (pause hours, L/S × normal/rescue PnL, max-normal-side blocks, …), `definitions` (text definitions of every metric), and `summary` (= summary.json) |
| `trades.csv` | every closing fill record: `t_in,t,id,strat,side,entry,exit,qty,pnl,pnl_rebate,pnl_pct_margin,pnl_pct_equity,result,why,info` (`pnl` = after fees without rebate, `pnl_rebate` = with 70 % rebate; one position can have several records for partial TPs) |
| `entries.csv` | one row per entry (normal and rescue), identical format to the original `entries_0.9.17x_<run>.csv`: id, strat, rule, frame, side, entry/exit time (KST) & price, qty, TP, exit reason (`열림` = still open), PnL (realized/unrealized/total, exact-rebate), hold hours, MAE/MFE %, held_by_rescue, exposure/margin %, gate values (h4 SMA120, h1 RSI14, …) |
| `monthly.csv` | `month,start,end,pnl_rebate_mtm,return_rebate_pct,realized_pnl_rebate,cyc_realized_pnl_rebate,trades,first_bar_open,last_bar_open` — month-end vs previous month-end equity **including** cumulative rebate, mark-to-market (open PnL included); first/last months partial |
| `equity.csv` | `t,equity,price` — raw equity (no rebate) sampled every 15 min |
| `equity_minutes.csv` | `t,equity_raw,rebate_total,margin,price,margin50_skips` — every replayed minute close (MDD/margin are computed from these) |
| `open_positions_end.csv` | positions still open at the end (“stuck”): id, strat (`cyc` = rescue add), side, entry time/price, qty, unrealized PnL at the final mark |
| `repayments.csv` | .152 held-repayment events |
| `events.log` | engine event log (`YYYY-MM-DD HH:MM KST <event>`); first line is the wall-clock INIT stamp |
| `validation_entries.json`, `cash_checks.csv` | self-checks of the entries export (cash/fee/equity reconstruction errors must be < 1e-7) |
| `run_meta.json` | config path + SHA256, engine version + source SHA256, data file SHA256, warm-up/seed ranges, runtime seconds, peak RSS MB, Python/numpy/pandas versions |
| `audit/` | only with `--audit`: per-minute gate/rescue/candidate logs (≈150 MB per year) |

## Key metrics (summary.json / report.json)

| summary key | report key | meaning |
|---|---|---|
| `return_rebate70_pct` | `return_rebate70_pct` | **환급 포함 수익률**: (raw equity + cumulative 70 % rebate) / initial − 1 |
| `return_raw_pct` | `return_raw_pct` | 환급 제외 수익률 (fees fully paid, no rebate) |
| `mdd_raw_pct` | `mdd_raw_minute_pct` | **raw MDD**: max drawdown of minute-close raw equity (wallet + unrealized, rebate excluded) |
| `mdd_rebate_exact_pct` | `mdd_rebate70_exact_minute_pct` | exact-rebate MDD: minute raw equity + rebate accrued **at that minute** |
| — | `mdd_rebate70_legacy_15m_approx_pct` | old dashboard approximation (comparability only) |
| `max_margin_pct` | `max_margin_usage_pct` | max minute-close margin / raw equity |
| `rescue_sessions`, `rescue_ongoing_at_end`, `longest_session_hours` | `rescue_sessions` | rescue (구출) sessions |
| `margin_pause_skips` | `margin_guard_skips` | rescue adds skipped by the margin pause (≥ 40 %) |
| `stuck_total_open_end`, `_unreal` | `trapped_total_at_end` | positions stuck at the end (rescue adds + held normals): count and unrealized gross PnL |
| `held_normal_open_end`, `rescue_adds_open_end`, `normal_nonheld_open_end` (+`_unreal`) | `initial_held_open_at_end`, `rules169.rescue_adds_open_at_end`, `normal_nonheld_open_at_end` | breakdown of the open positions at the end |
| `pause_hours_L/S`, `pause_hours_active_L/S` | `rules169.trend_pause_hours` | trend-pause hours per side (all / while a rescue was active) |
| `pause_suppressed`, `pause_cancels` | `rules169.pause_*` | rescue add placements suppressed / resting slots cancelled by the pause |
| `v2_blocked`, `v2_blocked_open_L/S`, `v2_blocked_market_L/S`, `v2_market_minute_checks_blocked` | `rules169.rules171.max2_blocked` | **blocked entries** by the max-normal-per-side rule (limit opens / market-minute checks) |
| `pnl_rebate_{L,S}_{normal,rescue}`, `open_unreal_…`, `open_count_…` | `rules169.pnl_by_side_kind` | **long/short × normal/rescue** realized PnL (rebate incl.), open unrealized, open count (B6 has no rules169: computed by run.py, same definitions) |
| `div1m_refused`, `off_events166`, `neutral_hours`, `sl_*` | `rules169.rules170` | U4+ counters |
| `slope_bars`, `rescue_size_pct`, `rescue_margin_pct`, `max_normal_side`, `rescue_tp` | params echo | effective parameters |
| `trades_closed_records`, `entries`, `equity_raw_end`, `equity_rebate70_end` | — | counts and final equity |

Omitted vs. the original report.json: the research appendices `m1_market_cohort` and `tf_signal_cohorts`
(slow, not used for any judgment) and round bookkeeping labels. All other values are produced by the same code.

## compare.py → comparison.csv

`python compare.py --out comparison.csv --pair W4 out/W4_Y2024 out/W4_Y2025 --pair X1 out/X1_Y2024 out/X1_Y2025`

One row per condition: `condition, Y2024_period, Y2024_<every summary key>, Y2025_…, two_year_rebate_sum_pct,
both_rebate_positive, both_raw_mdd_le_25, candidate` (candidate = both years rebate return > 0 and both raw MDD ≤ 25 %,
the rule used in rounds .169–.173). Written as UTF-8 with BOM so Excel opens it correctly.
