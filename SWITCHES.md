# SWITCHES — config keys / 설정 스위치

A config is one JSON file = one run (one condition × one period). Ready-made configs live in `configs/`
(`B6/T1/U4/V4/W4/W6/X1–X6 × Y2024/Y2025`). Copy one and edit it; do not edit the engine sources.

> **Important:** the engine classes only accept *reviewed* values. Many switches raise
> `ValueError('Unreviewed ...')` for any value outside the lists below — this is intentional
> (it is how the original paper rounds guaranteed exact reproduction). Allowed values are listed.
> A switch that is omitted takes the class default shown, but every shipped config states all switches explicitly.

## 1. Run / period / data

| key | default | meaning |
|---|---|---|
| `name` | config file stem | label written into outputs |
| `engine_module`, `engine_class` | — (required) | engine version: `engine167/Engine167` (B6), `engine169/Engine169` (T1), `engine170/Engine170` (U4), `engine171/Engine171` (V4), `engine172/Engine172` (W4, W6), `engine173/Engine173` (X1–X6) |
| `start_kst` | — (required) | first replayed minute, KST. `"YYYY-MM-DD"` (=00:00) or `"YYYY-MM-DD HH:MM"` |
| `end_kst` | — (required) | `"YYYY-MM-DD"` = **that whole day included** (end = next day 00:00); `"YYYY-MM-DD HH:MM"` = **exclusive** cut-off minute. Y2024 uses `"2025-11-03"`, Y2025 uses `"2026-11-07 23:54"` (the original data cut-off) |
| `start_ms`, `end_ms` | — | optional epoch-ms overrides (end exclusive) |
| `initial_equity` | `1000.0` | starting USDT (all frozen results use 1000) |
| `edits` | — | user line-edit file (manual lines / exclusions / style samples); all rounds used `inputs/line_edits_20261103b.json` |
| `minute_files` | `["data/btcusdt_1m_master.npz"]` | 1m data files, merged by open time; **later files override earlier ones**. Y2025 configs add `data/btcusdt_1m_Y2025_engine_input.npz` (exact original Y2025 input, see data/MANIFEST.json) |

Warm-up (automatic, identical to .168–.173): strategy warm-up starts at `start − 13 days` floored to a 4h UTC
boundary; TREND/RSI filter seeds use completed 1h/4h/1d bars of the 70 days before that; the .169+ SMA table is
built from every minute in the data files before `end`. The data must contain **every minute** from
`warm_start − 70 days` to `end`, otherwise run.py stops with exit code 2 and a `DataCoverageError` message
(no silent gaps). With the shipped master file the earliest possible start is about **2024-10-23** and the latest
end is **2026-11-09 00:00 KST**; extend with `fetch_data.py` for later periods.

**Size switch inside the engine (engine13 `SWITCH`, 고정):** from **2026-11-04 09:29 KST** on, every candidate engine
(B6…X6) sizes normal entries larger: trendline `pat*` 5 % → 8 %, fib 2 % → 5 %, tri1 3 % → 6 % and rsi 6 % → 9 % of the
seed. This reproduces the live paper engine's change at that moment. Y2025 contains its last ~4 days; a custom period
ending after that date is affected too. It is not a switch.

Fees are **not** switches: maker 0.018 %, taker 0.042 %, rebate 70 % are engine constants (engine8.py), leverage 3×,
contract 0.0001 BTC, tick 0.1.

## 2. Strategy switches (engine constructor arguments)

### `flags` (engine154)
| key | default | used | meaning |
|---|---|---|---|
| `TREND` | true | true (all) | block NORMAL longs below / shorts above the completed 4h SMA120 |
| `RSI` | true | true (all) | block NORMAL longs when 1h RSI14 > `rsi_upper`, shorts when < `rsi_lower` |
| `STRETCH` | false | false | block when price > 1.10× / < 0.90× daily SMA50 |
| `UNTIL_ZERO` | false | false | .153 old-add 24h repayment until side ROI ≥ 0 (Engine30); false = exact .152 held-only repayment |
| `SIDE_BLOCK` | true | true | no new same-side normal entries while that side's rescue session holds normal positions |

### `settings155`
| key | default | allowed | used | meaning |
|---|---|---|---|---|
| `rsi_upper` | 75 | number | 70 | RSI upper gate |
| `rsi_lower` | 25 | number | 30 | RSI lower gate |
| `pos30` | false | bool | false | 30-day high/low position gate (>90 blocks L, <10 blocks S) |

### `need_held` (engine156) — default false, used false. True = a rescue session may start only if the side has an open normal position.

### `rescue_params158` (rescue = "구출", 3m cycle adds, strat `cyc`)
| key | default | allowed | used | meaning |
|---|---|---|---|---|
| `rescue_max_open` | 20 | 10, 20 | 20 | max simultaneously open rescue adds per session |
| `rescue_gap` | 0.003 | 0.003, 0.01 | 0.003 | min price gap between adds (0.3 %) |
| `rescue_margin_pct` | 50 | 40, 50 | 40 | margin-use % at/above which a new rescue add is skipped ("margin pause") |
| `rescue_size_pct` | 3 | 2, 3 | 3 | add size = % of available × 3 leverage (overridden by params171/172) |
| `open_limit` | true | true | true | OPEN_LIMIT on (must be true) |

### `params159`
| key | default | allowed | used | meaning |
|---|---|---|---|---|
| `held_block` | false | bool | false | adopt new same-side normal entries into the active rescue (HELD_BLOCK) |
| `start_roi` | −1.5 (−2 from engine162M on) | −1.5, −3 here; −1, −1.5, −2 in engine162 | −2 | side ROI % (mark, ×3) at or below which a rescue session starts |
| `rescue_tp` | 38 | 38, 60 | 60 | rescue add take-profit distance in USDT (BTC price) |

### `params162` — `normal_cap_pct` default 20, allowed 15/20/25, used 20: NORMAL entries refused when the side's margin share ≥ this % of equity.

### `params162m`
| key | default | allowed | used | meaning |
|---|---|---|---|---|
| `m1_market` | false (true in engine164+) | bool | true | 1m PatternRun break signals enter at next minute OPEN as taker |
| `m1_break_tp` | 50 (90 in engine164+) | 30,50,80,120,200,300 (engine164+ forces 90) | 90 | TP distance for those M1 market entries |

### `params167` (engine166/167 TP & OFF overlay)
| key | default | used | meaning |
|---|---|---|---|
| `tp_set` | {} | `{"ma:1h":200,"mat:1h":200}` | TP distance override per `group:frame` (groups ma, mat, fib, break, other; frames 15m, 1h, 4h) |
| `off` | `["mat:15m"]` | B6/T1: `["mat:15m"]`; U4 and later: `["mat:15m","ma20:15m","ma60:15m","ma20:1h"]` (OFF4) | signal families disabled (`ma20/ma60/ma120/mat…:frame`) |
| `market_frames` | [] | [] | must stay empty |
| `ma_market_frames` | [] | [] | `15m`/`1h` MA signals as market entries (unused) |

### `params169` (engine169+, T1 and later). `sma_table` is built automatically — do not set it.
| key | default | allowed | used | meaning |
|---|---|---|---|---|
| `pause_tf` | null | null, "4h", "1d" | "4h" | trend pause: no NEW counter-trend rescue adds (UP ⇒ no short adds, DOWN ⇒ no long adds) using closed 4h SMA120 (1d: SMA50) |
| `stale_days` | null | null/30 | null | market-close rescue adds older than N days |
| `opp_bank` | false | bool | false | opposite-side profit bank repayment |
| `opp_age_days` | 7 | number | 7 | age for opp_bank |
| `loss_cap_pct` | null | null/10 | null | per-side losing rescue-add cap (% equity) |
| `net_tf` | null | null,"4h","1d" | null | TrendNet adds in trend direction |
| `net_size_pct` | 3 | 3, 4 | 3 | TrendNet add size |

### `params170` (engine170+, U4 and later)
| key | default | allowed | used | meaning |
|---|---|---|---|---|
| `div1m_off` | false | bool | true (U4+) | refuse 1m RSI-divergence normal entries (`pat1` 다이버전스, `rsi1`) |
| `sl_pct` | null | null, 3 | null | 3 % stop-loss on NORMAL entries (taker) |
| `pause_mode` | "T1" | "T1","A","B" | "B" (U4+) | T1 = close vs SMA; A = ±2 % band; B = close vs SMA **and** SMA slope vs `slope_bars` closed 4h bars ago, else NEUTRAL (no pause) |

### `params171` (engine171+, V4 and later)
| key | default | allowed | used | meaning |
|---|---|---|---|---|
| `rescue_size_pct171` | null | null, 4 | 4 (V4+; engine172+ requires 4) | rescue add size 4 % of available |
| `rescue_margin_pct171` | null | null, 50 | null | margin pause threshold 50 % |
| `slope_bars` | 6 | 6, 12 | 6; 12 in X2/X3/X6 | Pause-B slope look-back (closed 4h bars) |
| `bounce_short_off` | false | bool | false | refuse 1m trendline-bounce SHORT normal entries |
| `max_normal_side` | null | must be null in engine172+ (use params172) | — | — |

### `params172` (engine172+, W*)
| key | default | allowed | used | meaning |
|---|---|---|---|---|
| `max_normal_side172` | null | null, 1, 2, 3 | W4/X1/X2/X4/X5/X6: 1; W6/X3: 2 | max simultaneously open NORMAL positions per side (rescue adds excluded; normals held by a rescue still count) |
| `rescue_size_pct172` | null | null, 5 | X5: 5 | rescue add size 5 % |
| `rescue_tp172` | null | null, 80 | W6: 80 | rescue TP +60 → +80 |

### `params173` (engine173, X*) — `rescue_tp173`: null / 80 / 100 (X1, X2, X3, X5: 80; X4: 100; X6: none). Cannot be combined with `rescue_tp172`.

## 3. Values per condition (summary)

| cond | engine | off list | pause | div1m_off | size% | max normal/side | rescue TP | slope | notes |
|---|---|---|---|---|---|---|---|---|---|
| B6 | engine167 | mat:15m | — | — | 3 | — | 60 | — | Y2024 = .168 B6, Y2025 = .167 G1 |
| T1 | engine169 | mat:15m | 4h T1 | — | 3 | — | 60 | — | trend pause 4h |
| U4 | engine170 | OFF4 | 4h B | true | 3 | — | 60 | 6 | |
| V4 | engine171 | OFF4 | 4h B | true | 4 | — | 60 | 6 | |
| W4 | engine172 | OFF4 | 4h B | true | 4 | 1 | 60 | 6 | current V1 paper (0.9.170 W4) |
| W6 | engine172 | OFF4 | 4h B | true | 4 | 2 | 80 | 6 | |
| X1 | engine173 | OFF4 | 4h B | true | 4 | 1 | 80 | 6 | |
| X2 | engine173 | OFF4 | 4h B | true | 4 | 1 | 80 | 12 | |
| X3 | engine173 | OFF4 | 4h B | true | 4 | 2 | 80 | 12 | |
| X4 | engine173 | OFF4 | 4h B | true | 4 | 1 | 100 | 6 | |
| X5 | engine173 | OFF4 | 4h B | true | 5 | 1 | 80 | 6 | **adopted (app 0.9.171)** |
| X6 | engine173 | OFF4 | 4h B | true | 4 | 1 | 60 | 12 | |

Common to all: flags TREND/RSI on, SIDE_BLOCK on; RSI 70/30; rescue max 20 / gap 0.3 % / margin pause 40 %;
start ROI −2; normal cap 20 %; M1 market on with TP 90; tp_set ma:1h=200, mat:1h=200.
Exact per-file values: `configs/*.json`.

**X5 (adopted, app 0.9.171)** = W4 + rescue add size 4 % → 5 % (`params172.rescue_size_pct172: 5`) + rescue TP +60 → +80
(`params173.rescue_tp173: 80`). Everything else is W4 (max normal/side 1, slope 6, OFF4, pause 4h B). The live paper engine
`engine_v1_x5_gate` (config sha256 `f4c330bc…`) states its backtest reference as
`Engine173(rescue_tp173=80) + Engine172(max_normal_side172=1, rescue_size_pct172=5)`. That is exactly
`configs/X5_Y2024.json` / `configs/X5_Y2025.json`, which are copies of the live_0173 X5 runs. Reference values: Y2024 +9.292 % /
raw MDD 20.325 %, Y2025 +20.079 % / 9.771 %.

## 4. Trendline / triangle / Fibonacci strategies — tunable vs 고정 (fixed)

Two layers can change these strategies:

* **Reviewed engine switches**: `params167.tp_set` and `params167.off`, the engine166 overlay. They apply ONLY to
  15m/1h/4h. Keys are `group:tf`, where group is `break` (every `pat{15,60,240}` entry: breakout-retest, touch-reverse,
  divergence, channel), `fib`, `ma`/`ma20|60|120`, `mat`/`mat20|60|120` or `other` (`tri*`, `rsi*`) and tf is `15m|1h|4h`.
  `off` refuses new entries. `tp_set` replaces the TP distance (+USDT).
* **`strategy_overrides`** (new, run.py → `gl/overrides.py`): EXPERIMENTAL and **not used by any frozen condition**.
  Every key defaults to absent. With the block absent or `{}`, **nothing is patched** and the engine is byte-for-byte the
  original (see VERIFY.md §4). It covers 1m and the module constants. Values are not range-checked beyond basic types, so
  results outside the defaults are unreviewed.

```json
"strategy_overrides": {
  "disable_strats": ["tri1"],
  "disable_rules": ["추세선 닿으면 반대"],
  "size_scale": {"pat1": 0.5, "fib": 1.0},
  "tp_usdt": {"pat1": 60, "fib1": 40},
  "fib_levels": [0.382, 0.5, 0.618, 0.722, 0.786, 0.886],
  "fib_uses": 3,
  "retest_bars": 15,
  "bounce_slope": 20,
  "bounce_uses": 3,
  "triangle_enabled": true
}
```

| override key | engine target | default (= current) | effect |
|---|---|---|---|
| `disable_strats` | `Engine8.open` filter | `[]` | refuse NEW normal entries of the listed strats (`cyc` rescue is never affected; warm-up is never affected). The count goes to run_meta `override_refused_entries`. |
| `disable_rules` | `Engine8.open` filter | `[]` | refuse NEW normal entries whose entry text (entries.csv `rule`) contains any substring. This is the way to turn off ONE strategy on ONE TF, e.g. `"1m 추세선 닿으면 반대"`, `"15m 5파동"`, `"M1MARKET"`, `"triangle"`. |
| `size_scale` | `Engine8.open` size | `{}` (all 1.0) | multiply the order size (notional, or seed pct for tri/rsi) of normal entries. The key is an exact strat (`pat1`) or a family prefix (`pat`, `fib`, `tri`, `rsi`, `ma`, `mt`); an exact strat wins. It is applied after the engine's own sizing (base × engine9/13 scale; see the table below). |
| `tp_usdt` | `engine15.tp_off` | `fib1 40, fib15 40, fib60 100, pat15 100, others 50` | TP distance (+USDT) for exit-mode `pat` entries: trendline breakout-retest, touch-reverse, divergence, channel (`pat*`) and fib (`fib*`). It does NOT affect M1MARKET (use `params162m.m1_break_tp`), tri/rsi (cost-based TP) or ma/mt. For 15m/1h/4h, `params167.tp_set` (if set) still has priority. |
| `fib_levels` | `engine7.ENTRY` | 0.382, 0.5, 0.618, 0.722, 0.786, 0.886 | retracement levels of a 5-wave impulse at which a maker limit order is placed. Only 0.886 also ends the fib after its fill. |
| `fib_uses` | `engine7.FIB_USES` | 3 | max fills per fib signal before it is retired. The `(n/3)` text in `rule` is a fixed label. |
| `retest_bars` | `engine5.RETEST` | 15 | breakout-retest signal lifetime in bars of its own TF (15 × 1m, 15 × 15m, ...). |
| `bounce_slope` | `engine17.SLOPE` | 20 USDT/h | min abs. line slope for touch-reverse lines. It ALSO blocks breakouts against a line steeper than this (the same constant in the engine). |
| `bounce_uses` | `engine17.BUSES` | 3 | max trades per touch-reverse line. |
| `triangle_enabled` | `engine4.ENABLED['tri1']` | true | 1m triangle breakout on/off. |

Safety: the targets are module globals read at call time, or the single common entry point `Engine8.open`. Returning
None from `open` is already what the engine's own refusals (DropGuard, `params167.off`) do, so callers handle it.
Constants that are bound as default arguments or imported by name into other modules are NOT exposed (see 고정 below).

### 4.1 Per-strategy, per-TF inventory

Base size = % of free balance × LEV 3. It is multiplied by the engine9 scale, which changes at the engine13 SWITCH
2026-11-04 09:29 KST: **before → after**.

**A. Trendline breakout-retest (`pat{f}`, rule `추세선/수평선/내 선/추천선 돌파 리테스트`; 1m breakouts are converted into `M1MARKET`)**

| item | 1m | 15m | 1h | 4h | tunable? |
|---|---|---|---|---|---|
| enable | `disable_rules` "1m 추세선 돌파" / "M1MARKET" | `params167.off` `break:15m` | `break:1h` | `break:4h` | yes |
| line source | auto lines (when learned samples < 5) + manual/learned lines from `edits` | manual/learned lines only | same | same | via `edits` file only |
| entry | `params162m.m1_market`=true: taker at the next 1m open, TP `m1_break_tp` (90) | maker limit at the line on retest | same | same | m1: yes (reviewed values) |
| size | M1MARKET 4 % base → 5 % / 8 % | 4 % → 5 % / 8 % | same | same | `size_scale` |
| TP (+USDT) | M1MARKET 90 (`m1_break_tp`); retest 50 | 100 | 50 | 50 | `tp_usdt`; `params167.tp_set break:tf` |
| retest wait | 15 bars | 15 bars | 15 bars | 15 bars | `retest_bars` (all TFs at once) |
| breakout confirm | 2 consecutive closes beyond line ± tol with growing distance | same | same | same | 고정 |
| line acceptance | lookback 240 bars; pivots radius 3 (1m) / 2 (others), major pivots 10 bars; min span 15 bars; tol = ATR14 × 0.25; touches ≥ 2 pivots + no close beyond tol in between; "flat" if \|Δ\| ≤ 0.5 ATR; top 2 lines per side by score (span + 15 × touches + 60 triangle − age/4) | same | same | same | 고정 (`LOOKBACK`, `MAJOR`, `MIN_SPAN` are bound as default args / imported by name) |
| against-slope block | breakout against a line with \|slope\| ≥ 20 USDT/h is skipped | same | same | same | `bounce_slope` (shared) |
| other filters | DropGuard (no 1m longs ≥ 1 % below 60-bar high), side block, normal cap, pause, max normal/side | same | same | same | the existing param groups |

In the frozen W4 runs every 1m breakout went through M1MARKET (`1m M1MARKET trend/flat`). There were no
retest fills on 15m/1h/4h (no qualifying manual/learned lines).

**B. Trendline touch-reverse ("bounce", `pat{f}`, rule `추세선 닿으면 반대`)**

| item | 1m | 15m | 1h | 4h | tunable? |
|---|---|---|---|---|---|
| enable | `disable_rules` "1m 추세선 닿으면 반대" | `params167.off break:15m` (also turns off 15m breakout) or `disable_rules` "15m 추세선 닿으면 반대" | 1h same | 4h same | yes |
| line | sloped auto/manual line (not flat, triangle or channel), \|slope\| ≥ 20 USDT/h; a falling line above price → short at the line, a rising line below → long | same | same | same | `bounce_slope` |
| entry | maker limit following the line; needs ≥ 60 bars | same | same | same | 고정 |
| size | 4 % → 5 % / 8 % | same | same | same | `size_scale` |
| TP | 50 | 100 | 50 | 50 | `tp_usdt`, `tp_set break:tf` |
| uses / end | max 3 trades per line; ends after 2 closes through the line, the line no longer being recommended, or its `until` | same | same | same | `bounce_uses`; end rule 고정 |

**C. Market breakout (M1MARKET, `pat1`, rule `1m M1MARKET trend|flat|learned|manual`)**: 1m only. Switch
`params162m.m1_market` (true) with TP `m1_break_tp` (90, reviewed values only). The size is 4 % base (scaled as above)
and the entry is a taker at the next 1m open. Families (`trend`, `flat`, `learned`, `manual`) and the 60 s expiry are 고정.

**D. Triangle (`tri1`, rule `1m asc|desc|sym triangle break up|down (...)`)**: 1m only.

| item | value | tunable? |
|---|---|---|
| enable | true | `triangle_enabled`, or `disable_strats ["tri1"]` |
| window | last 120 1m bars, tol = ATR × 0.25 | 고정 |
| lines | resistance and support `find_line` (pivot radius 3, wick ≥ body; no high/low beyond line ± tol between pivots; no later close beyond) | 고정 |
| acceptance | overlap ≥ 6 bars; asc = flat top + rising bottom, desc = falling top + flat bottom, sym = both converging (flat = \|Δ\| ≤ tol); end width ≥ 2 tol and ≤ 0.9 × start width (shrink ≥ tol); price inside; ≥ 2 wick touches on EACH side (≥ 3 bars apart) and ≥ 1 alternation | 고정 |
| trigger | 1m high > upper + tol (long) / low < lower − tol (short); each triangle trades once; max 10 open `tri1` | 고정 |
| size | seed pct 2 % → 3 % / 6 % | `size_scale {"tri1": x}` |
| TP | `cost5full`: fee cost × 5 move, single TP | 고정 |

**E. Fibonacci 5-wave retracement (`fib{f}`, rule `5파동 피보나치 <level> (n/3)`)**

| item | 1m | 15m | 1h | 4h | tunable? |
|---|---|---|---|---|---|
| enable | `disable_strats ["fib1"]` | `params167.off fib:15m` or `disable_strats ["fib15"]` | `fib:1h` / `fib60` | `fib:4h` / `fib240` | yes |
| wave detection | auto 5-wave impulse (pivot radius r=3 on 1m / 2 on others, tried at r, r+2, 3r); sweep fallback ≥ 3 ATR; +30 rank if wave5 ≈ wave1 (±10 %); ≥ 30 bars (40 for waves) + my fibs from `edits` | same | same | same | 고정 |
| levels | 0.382, 0.5, 0.618, 0.722, 0.786, 0.886 | same | same | same | `fib_levels` (all TFs) |
| split sizing | EQUAL size at every level: 1 % base → 2 % / 5 % per fill | same | same | same | `size_scale {"fib1": x}` (no per-level weights; 고정) |
| uses | each level max 3 fills (busy until its TP); 0.886 fill retires the fib | same | same | same | `fib_uses`; 0.886 rule 고정 |
| TP | 40 | 40 | 100 | 50 | `tp_usdt`, `tp_set fib:tf` |
| order | maker limit, only while price is on the favourable side of the level | same | same | same | 고정 |

**Also 고정**: divergence `DIVB=5` (lifetime of 1m/15m `상승/하락 다이버전스`; 1m is off via `params170.div1m_off`),
fake breakout `FAKE_BARS=5 / REPLACE=3`, the parallel-channel 4th point (1m longs off), fee/slippage constants,
LEV 3 and the engine13 SWITCH time.

### 4.2 entries.csv naming (grouping per signal)

`strat` = family + TF minutes. `rule` = `L|S <tf> <rule text> @<price> ...`. Group by `strat` + the rule text with side,
price and counters removed:

| strat | rule text contains | strategy |
|---|---|---|
| `pat1`,`pat15`,`pat60`,`pat240` | `추세선 돌파 리테스트` / `수평선 돌파 리테스트` / `내 선 돌파 리테스트` / `추천선 돌파 리테스트` | trendline breakout-retest (auto/flat/manual/learned line) |
| `pat1` | `M1MARKET trend` / `flat` / `learned` / `manual` | 1m market breakout |
| `pat{f}` | `추세선 닿으면 반대` | touch-reverse (bounce) |
| `pat{f}` | `평행채널 4번째 포인트` | parallel channel 4th point |
| `pat{f}` | `상승 다이버전스` / `하락 다이버전스` | divergence |
| `pat{f}` | `가짜 돌파 반대 진입` | fake-breakout reverse |
| `fib{f}` | `5파동 피보나치 <level> (n/3)` | Fibonacci retracement; `<level>` = which split |
| `tri1` | `asc/desc/sym triangle break up/down` | triangle |
| `rsi1`,`rsi15`,`rsi60` | `RSI9/RSI7 ... bull/bear div` | RSI divergence |
| `ma15`,`ma60`,`ma240` | `SMA20/60/120 turn <tf>` | SMA turn |
| `mt60`,`mt240` | `SMA20/60/120 touch <tf>` | SMA touch |
| `cyc` | `cycle rescue add n/20` | rescue add (not a signal; it belongs to the session it rescues) |

A grouping regex for Python/Excel: strip `^[LS] `, `@.*$`, `\(\d+/\d+\)`, and for tri/rsi the parenthesised numbers.
`entries.csv` `total_pnl_rebate70` is the per-entry PnL to sum.
