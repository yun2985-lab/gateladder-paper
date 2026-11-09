# GateLadder paper engine — portable export (engine_export)

모의(페이퍼) 백테스트 엔진을 윈도우 PC에서 그대로 돌릴 수 있게 내보낸 패키지입니다.
계산은 원래 리눅스에서 돌던 엔진 소스(engine4 … engine173)를 **한 글자도 고치지 않고** 그대로 씁니다.
실계좌·거래소 키·네트워크 주문은 전혀 없습니다 (run.py는 네트워크를 쓰지 않음).

This is the exact GateLadder paper-trading backtest engine (unmodified sources engine4 … engine173) with a
portable runner. One run = one condition × one period. No exchange keys, no live trading, run.py is offline.

## 빠른 시작 / Quick start (Windows)

```bat
:: Python 3.13 64-bit (python.org installer, "Add python.exe to PATH")
cd engine_export
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python verify_data.py
python run.py --config configs\W4_Y2025.json --out results\W4_Y2025
python run.py --config configs\W4_Y2024.json --out results\W4_Y2024
python verify_results.py results\W4_Y2025
python compare.py --out results\comparison.csv --pair W4 results\W4_Y2024 results\W4_Y2025
```
macOS/Linux: `python3 -m venv .venv && . .venv/bin/activate`, same commands with `/`.

Expected: W4_Y2025 → rebate **+15.684 %**, raw MDD **7.675 %**; W4_Y2024 → **+4.976 %**, **19.986 %** (see VERIFY.md).
Adopted condition **X5** (app 0.9.171 = W4 + rescue add 5 % + rescue TP +80, engine173 switches `params172.rescue_size_pct172=5`, `params173.rescue_tp173=80`):
`configs/X5_Y2024.json` → **+9.292 %** / rawMDD **20.325 %**, `configs/X5_Y2025.json` → **+20.079 %** / **9.771 %**.

## 두 해 방식 / Two-year method
Each condition is run twice — Y2024 (2024-11-04 ~ 2025-11-03 KST) and Y2025 (2025-11-04 ~ 2026-11-07 23:53 KST) —
and compared side by side with `compare.py`. Any other period: copy a config and change `start_kst` / `end_kst`
(see SWITCHES.md §1; data must cover warm-up, otherwise run.py exits with code 2 and a clear message).

## Files
| path | |
|---|---|
| `run.py` | CLI entry: `python run.py --config CFG --out DIR` (one run, PROGRESS lines, exit 0/1/2) |
| `compare.py` | side-by-side comparison.csv of finished runs |
| `verify_results.py` | checks a finished run against frozen reference values |
| `verify_data.py` | checks data hashes; `--derive` proves derived seeds/SMA/minutes equal the original pickled inputs |
| `fetch_data.py` | re-downloads Binance 1m klines (master file or extra months) |
| `engine/` | 43 engine modules, byte-identical to the originals (SHA256 in SHA256.json) |
| `gl/` | runner helpers: data derivation, KST, report builder, entries exporter (ported from the original scripts) |
| `configs/` | B6, T1, U4, V4, W4, W6, X1–X6 × Y2024/Y2025 (24 files) |
| `inputs/line_edits_20261103b.json` | user line edits used by every round |
| `data/` | 1m BTCUSDT data (npz) + MANIFEST.json |
| `expected/frozen_baselines.json` | reference results of the original runs |
| SWITCHES.md / OUTPUTS.md / VERIFY.md | switches, output formats, verification |

## Progress line (one per 2,500 bars ≈ 1.7 days of data)
```
PROGRESS 47.6% bar 2025-04-26 14:40 KST eq_raw 981.18 eq_rebate 1012.40 mdd_raw 5.16% elapsed 812s
...
EXPORT entries.csv ...
DONE W4_Y2025 rebate +15.684% raw +5.824% rawMDD 7.675% rebateMDD 4.835% maxMargin 41.855% trades 4275 equity_raw 1058.240470 time 1400s
```
Lines start with `PREPARE`, `PROGRESS`, `EXPORT`, `DONE` or `ERROR` — easy to parse from a GUI (read stdout line by line;
use `python -u` or rely on the built-in flush). Exit code: 0 ok, 2 config/data error, 1 engine error.

## Install notes / Windows caveats
- **Python 3.13 x64** (tested 3.13.5). Only `numpy==2.5.4` and `pandas==3.0.6` are needed to run; `requests` only for fetch_data.py.
  numba / scipy / matplotlib are **not** used by the engine. All have Windows wheels — no compiler needed.
- **Time zone:** all KST handling is a fixed UTC+9 offset inside the package (the one engine call that used the OS
  local time, engine28 month buckets, is redirected). Results do not depend on the PC's time-zone setting.
- **One run per process.** For parallel runs start several processes (e.g. `subprocess.Popen` from the GUI), one per
  CPU core; nothing uses multiprocessing/fork, and each run writes only into its own `--out` directory (no file locks,
  no shared state). Run.py has the `if __name__ == '__main__':` guard, so it is also safe to import `run.main([...])`.
- **Memory:** peak RSS ≈ 600–680 MB per 1-year run, ≈ 300 MB for a 1-month run (measured on Linux, see VERIFY.md). Plan ~1 GB per parallel process. Disk ≈ 60–80 MB per 1-year result
  directory (equity_minutes.csv is the largest file; delete it if not needed).
- **Speed:** 1-year run ≈ 40–60 min, 1-month run ≈ 4 min (single thread, CPU-bound, measured at nice 19 on a shared Linux box, see VERIFY.md). Short custom periods are proportionally faster
  (warm-up adds ~13 days of bars).
- **Caveat (size switch):** the engine itself enlarges normal entry sizes from 2026-11-04 09:29 KST (engine13 SWITCH,
  see SWITCHES.md §1). Periods after that date are not comparable 1:1 with earlier ones.
- **Strategy overrides:** optional `strategy_overrides` (SWITCHES.md §4) are experimental; absent = original engine.
- **Paths:** pathlib everywhere, relative paths in configs are resolved against the package folder. Avoid very deep
  folders (Windows 260-char limit) or enable long paths; keep the folder name ASCII if possible.
- **Line endings:** `.gitattributes` disables CRLF conversion so SHA256.json stays valid after a git checkout on Windows.
  If you copied files another way, `verify_data.py` checks numeric content, not only bytes.
- **CSV + Excel:** result CSVs are UTF-8 (no BOM) except comparison.csv (UTF-8 BOM). Korean text in `entries.csv`
  (rule/exit_reason) shows correctly in Excel via Data → From Text/CSV → UTF-8.
- **Antivirus/OneDrive:** put results outside OneDrive-synced folders; syncing large CSVs during a run slows it.

## 한국어 요약
- 설치: Python 3.13(64비트) → `pip install -r requirements.txt` (numpy, pandas만 필수).
- 실행: `python run.py --config configs\W4_Y2025.json --out results\W4_Y2025` (한 번에 1개 run, 진행률 한 줄씩).
- 기간 바꾸기: config의 `start_kst`, `end_kst` 수정 (날짜만 쓰면 그날 끝까지 포함, 시각까지 쓰면 그 분 직전까지).
- 비교: `python compare.py --out comparison.csv --pair W4 결과\W4_Y2024 결과\W4_Y2025 ...`
- 검증: `python verify_results.py results\W4_Y2025` → PASS 이면 원래 엔진과 숫자가 같음.
- 키·비밀번호·서명키는 들어 있지 않고, 네트워크는 fetch_data.py(바이낸스 공개 시세)만 씁니다.
- 주의: 엔진 자체에 2026-11-04 09:29 KST 이후 진입 크기를 키우는 스위치(engine13 SWITCH, 고정)가 있습니다 (SWITCHES.md §1).
- 추세선·삼각수렴·피보나치 조절값과 `strategy_overrides`(실험용, 기본값 = 원래 엔진 그대로)는 SWITCHES.md §4에 있습니다.
- entries.csv의 `strat`/`rule`로 신호별 손익을 묶는 방법도 SWITCHES.md §4.2에 있습니다.
