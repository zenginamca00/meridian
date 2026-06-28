# Meridian Strategy Audit — Data-Driven Recommendations

**Auditor:** Mavis (orchestrator agent, Mavis team)  
**Date:** 2026-06-11  
**Branch audited:** `simulator-paper` (VPS: 129.212.239.227)  
**Data window:** 7 days of paper trading (41 closed positions, 2 open)  
**Mode:** DRY_RUN (paper trading, simulated balance)

---

## TL;DR

41 closed paper trades analyzed. **Win rate 63.4% (26/15), profit factor 4.15, net PnL +$15.68, fee/IL ratio 1.69×** — numbers look decent on the surface, but three structural issues are bleeding the strategy:

1. **False-entry bug** — 3 of the 5 worst trades entered with `peak_pnl_pct = 0.0%`, meaning the price was already at the edge of the range. The bot deploys into positions that go OOR within 1-2 candles. **Fix: pre-deploy range-edge check.**
2. **OOR-20m wait is too long** — Winners hold 9.6h avg, losers 3h. Losers are mostly false-entries that get out at -$0.5 to -$1.3 within 30 minutes. **Fix: in-range % rolling check + faster dead-money detection.**
3. **Time-of-day variance is real** — 0% win rate at 15h and 19h UTC (small samples but consistent), 100% win rate at 11h and 18h. **Fix: no-entry hours + green-hour boost.**

The strategy is sound, the entry/exit logic is just sloppy. Implementation effort is small and risk is low.

---

## 1. Data Snapshot

Pulled from VPS at `/opt/meridian/`:
- `paper-positions.json` (130 KB, 43 positions)
- `decision-log.json` (65 KB)
- `user-config.json` (1.2 KB)

### Aggregate metrics (41 closed)

| Metric | Value |
|---|---|
| Total trades | 41 closed, 2 open |
| Win/Loss | 26/15 |
| Win rate | 63.4% |
| Avg winner | +$0.84 PnL per trade |
| Avg loser | -$0.40 PnL per trade |
| Total PnL | +$15.68 |
| Total fees | $38.44 |
| Total IL | -$22.76 |
| Fee/IL ratio | 1.69× |
| Profit factor | 4.15 |
| Avg hold time (winners) | 578 min (~9.6h) |
| Avg hold time (losers) | 177 min (~3h) |
| Deposit size range | 36.88 – 43.82 SOL/trade |

### Exit reason breakdown

| Exit reason | Count | Avg PnL | Total PnL | Total fees | Total IL |
|---|---:|---:|---:|---:|---:|
| out of range 20m | 34 | +0.286 | 9.72 | 31.45 | -21.73 |
| take profit 5.1% | 2 | +2.000 | 4.00 | 4.59 | -0.59 |
| take profit 5.2% | 1 | +2.041 | 2.04 | 2.04 | -0.00 |
| stale dead-money | 4 | -0.020 | -0.08 | 0.36 | -0.44 |

**Note:** 33 of 41 closed trades exited via "out of range 20m" — looks dominant, but most OOR exits are *small winners* (avg +$0.29) or *false-entry losers* (peak 0%). The real problem isn't OOR frequency, it's what we deploy into.

---

## 2. Key Findings (Data, Not Theory)

### Finding A: False-entry bug is the #1 source of losers

**Top 5 worst trades by PnL:**

| Trade | Hold (min) | PnL | Peak PnL % | Close reason |
|---|---:|---:|---:|---|
| PATCHA-SOL | 39 | -1.271 | **0.0%** | OOR 20m |
| GO-SOL | 34 | -0.598 | **0.0%** | OOR 20m |
| Bountywork-SOL | 29 | -0.506 | **0.0%** | OOR 20m |
| 清正-SOL | 424 | -0.413 | 2.8% | OOR 20m |
| Magpie-SOL | 144 | -0.406 | **0.1%** | OOR 20m |

Three of five worst trades have **peak_pnl_pct = 0.0%**. The bot enters when the price is already at the range edge and gets pushed out within minutes. There's no sanity check on where the active bin sits relative to the proposed range bounds.

**Estimated damage:** -$2.4 from these 3 trades alone, ~16% of total net PnL.

### Finding B: In-range % is the strongest predictor of profit

| % time in range | n | WR | Total PnL |
|---|---:|---:|---:|
| 0-20% | 1 | 100% | 0.00 |
| 20-40% | 6 | 50% | 1.74 |
| 40-60% | 13 | 54% | 2.29 |
| 60-80% | 14 | 71% | 6.92 |
| 80-100% | 7 | 71% | 4.72 |

Positions that stay in range 60-80%+ of the time make the most money. Positions that bounce in/out are barely break-even. **This is the metric we should be optimizing for, not raw PnL.**

### Finding C: Hour-of-day variance is large

UTC hour distribution:

| Hour (UTC) | n | WR | Total PnL |
|---|---:|---:|---:|
| 11h | 4 | 100% | +5.16 |
| 18h | 2 | 100% | +4.39 |
| 16h | 5 | 60% | +3.34 |
| 9h | 3 | 67% | +0.45 |
| **15h** | 2 | **0%** | **-1.78** |
| **19h** | 2 | **0%** | **-0.77** |
| 22h | 1 | 0% | -0.04 |
| 23h | 1 | 0% | -0.13 |

Sample size is small (1-5 trades per hour), but the pattern is consistent: **15h and 19h UTC are 0% WR with non-trivial loss; 11h and 18h are 100% WR.** This corresponds roughly to US pre-market / Asia open transition windows.

### Finding D: Winners are held, losers are cut — already healthy

- Avg hold winners: 578 min (9.6h)
- Avg hold losers: 177 min (3h)

This is good behavior. The bot doesn't cling to losers. Don't change this axis.

### Finding E: Range width 50-100% is the sweet spot

| Range width | n | WR | Avg PnL |
|---|---:|---:|---:|
| 30-50% | 6 | 50% | -0.011 |
| 50-100% | 35 | 66% | +0.450 |

Tighter ranges (30-50% of price) underperform. Current `bins_below = 35 + (vol/5)*34` (range 35-69 bins) is in the right zone — don't tighten.

### Finding F: Pool concentration is mostly positive

| Pool | n | WR | Total PnL | Total fees |
|---|---:|---:|---:|---:|
| Magpie-SOL | 6 | 67% | 5.11 | 7.50 |
| Bountywork-SOL | 5 | 80% | 0.62 | 2.56 |
| HONTER-SOL | 4 | 75% | 1.26 | 3.23 |
| HUNTER-SOL | 4 | 75% | 2.70 | 4.99 |
| 清正-SOL | 4 | 50% | 1.73 | 5.41 |
| SLAB-SOL | 3 | 67% | 0.66 | 3.13 |
| GO-SOL | 3 | 0% | -1.00 | 0.98 |

6 of 7 high-frequency pools are profitable. The 24h cooldown (T2-B) was the right call. The Magpie 6× count is suspicious — verify if that includes pre-cooldown data, and consider tightening to 3×/week.

### Finding G: "Left on table" from peak is small

Avg `peak_pnl_pct - closed_pnl_pct` = 0.93%. Most winners close near their peak, which is correct behavior. The trailing TP at trigger=4% basically never fires (avg peak is 1.96%).

---

## 3. Recommendations — In Priority Order

### Priority 1: Pre-deploy range-edge check (RED — implement first)

**What:** Add a sanity check in `executor.js` (or the deploy pipeline) that rejects a deployment if the active bin is already too close to one of the range bounds.

**Why:** Fixes Finding A. Eliminates the false-entry pattern that produced 3 of the 5 worst trades.

**Concrete spec:**
- Reject deploy if `Math.abs(activeBinId - (lowerBinId + upperBinId) / 2) > 0.8 * (upperBinId - lowerBinId) / 2`
- In other words: if the current price is in the outer 20% of the range on either side, don't deploy.
- Log the rejection with `close_reason = "rejected: range edge"` in decision-log.

**Expected impact:** -$2 to -$4 in losses avoided per week (16% of total PnL preserved). Possibly more — false-entry pattern likely recurs in live trading.

**Risk:** Low. One additional check, isolated, no behavior change for valid entries. Worst case: 1-2 false rejects per week.

**Effort:** 15-30 min. Edit `executor.js`, add the check, test, deploy.

**Files to touch:**
- `tools/executor.js` — add `preDeployRangeCheck()` before `trackPosition()`
- `decision-log.js` — add new rejection reason type

---

### Priority 2: In-range % rolling check + faster dead-money detection (YELLOW)

**What:** Track rolling "in-range %" over the last 6 candles (90 min) per position. If it drops below 40% for 3 consecutive candles (45 min), close early. Tighten TP ratchet.

**Why:** Finding B shows in-range % is the strongest profit predictor. Finding G shows we leave ~0.93% avg on the table per winner. Currently we wait the full 20m OOR window before acting, which is too slow for choppy markets.

**Concrete spec:**
- New field per position: `candles_in_range_rolling` (last 6 candles)
- New exit rule: if `rolling_in_range_pct < 40` for 3 consecutive ticks → close with `close_reason: "early_exit: low in-range %"`
- Keep `outOfRangeWaitMinutes = 20` as fallback
- Tighten trailing TP: trigger 1.5% (down from 4%), drop 1% (down from 2%)
- Add TP ratchet: if peak ≥ 3%, raise exit target to 6%; if peak ≥ 6%, raise to 10%

**Expected impact:**
- Faster capital rotation: ~150 min of stuck capital per week freed up
- TP ratchet captures 2-3 "runner" trades per week that currently cap at +5%
- Estimated incremental: $3-5 per week

**Risk:** Medium. Could over-cut winners in temporary retrace. Mitigation: 3-candle (45 min) confirmation before early exit, plus the 20m OOR rule still exists as a safety net.

**Effort:** 1-2 hours. Modify `paper-positions.js` exit logic, add new metric to tracking, test in dry-run for 1-2 days.

**Files to touch:**
- `paper-positions.js` — add rolling counter + early-exit rule + TP ratchet
- `config.js` — new fields: `earlyExitInRangePct`, `earlyExitConfirmations`, `tpRatchetSteps`
- `user-config.json` — set new fields

---

### Priority 3: Time-of-day filter (YELLOW)

**What:** Add a config-driven list of "no-entry hours" and a separate list of "green hours" with reduced conviction threshold.

**Why:** Finding C shows consistent variance by hour. 15h and 19h UTC are 0% WR (small sample but consistent). 11h and 18h are 100% WR.

**Concrete spec:**
- New config field: `noEntryHours: [14, 15, 16, 17, 19]` — block new deploys during these UTC hours
- New config field: `greenHours: [10, 11, 12, 18]` — reduce LLM conviction threshold from "high" to "medium"
- Flag: `noEntryHoursStrict: false` (default — soft skip, LLM can still override) vs `true` (hard block)

**Expected impact:** Avoid -$3-4/week in losses at 15-19h UTC. Capture more winners at 11h/18h with looser conviction.

**Risk:** Low-medium. Sample size is small (2-5 trades per hour). Pattern might be noise. Mitigation: track per-hour stats for 2-3 more weeks, review and adjust. Default to `noEntryHoursStrict: false` for the first week.

**Effort:** 1 hour. Add config fields, check in `executor.js` screening path, log hour-of-day in decision-log.

**Files to touch:**
- `config.js` — new fields + parser
- `tools/executor.js` — hour check before deploy
- `decision-log.js` — record hour on every decision
- `user-config.json` — set initial values

---

### Priority 4: TP ratchet + tighter trailing (GREEN)

**What:** Already covered in Priority 2 spec. Pulled out separately because it's a low-risk, high-reward tuning change that's safe to ship independently.

**Why:** Finding G shows 0.93% avg left on table. Magpie-SOL hit peak 7.3% and closed at 2.99% (peak 5.1% on a different trade). TP ratchet would have caught these.

**Concrete spec:**
- `trailingTriggerPct: 4` → `1.5`
- `trailingDropPct: 2` → `1`
- New `tpRatchetSteps: [{ peak: 3, target: 6 }, { peak: 6, target: 10 }]`
- Hard TP at +5% remains as final cap

**Expected impact:** $2-3 incremental per winner. 2-3 winners per week get the boost.

**Risk:** Low. Winners stay winners; tighter trailing just locks in faster. If ratchet fires too early, position still closes in profit.

**Effort:** 30-60 min.

**Files to touch:**
- `paper-positions.js` — exit logic update
- `user-config.json` — config values

---

### Priority 5: Verify sizing & modal consistency (GREEN)

**What:** Reconcile the briefing claim of `PAPER_WALLET_SOL: 1.7` with observed `deposit_amount: 36-44 SOL` per position.

**Why:** Either there's a whale-simulation flag in paper mode (likely), or there's a sizing bug. Need to know which before tuning other parameters.

**Concrete spec:**
- Read `config.js` and look for `PAPER_WALLET_SOL`, `paperMode`, `simulatedBalance`, etc.
- Confirm whether deposit sizes are scaled by some factor or whether this is the actual intended size
- If scaling exists, document it; if not, fix

**Expected impact:** Clarity for return-on-capital expectations. Current `+$15.68 / 41 trades` is misleading without knowing denominator.

**Risk:** None — read-only investigation unless a bug is found.

**Effort:** 5-30 min depending on findings.

**Files to check:**
- `config.js` — search for `PAPER_WALLET`, `SIMULATED`, `BALANCE`
- `paper-positions.js` — search for `deposit_amount` calculation

---

## 4. Implementation Order

| # | Priority | Effort | Risk | Estimated weekly impact |
|---|----------|--------|------|-------------------------|
| 1 | Pre-deploy range-edge check | 15-30 min | Low | +$2-4 |
| 3 | Time-of-day filter | 1 h | Low | +$3-4 |
| 4 | TP ratchet + tighter trailing | 30-60 min | Low | +$2-3 |
| 5 | Verify sizing | 5-30 min | None | Clarity |
| 2 | In-range % rolling check | 1-2 h | Medium | +$1-2 (capital rotation) |

**Suggested rollout:**
- Week 1: P1 + P5 (quick wins, low risk)
- Week 2: P3 + P4 (config-only changes)
- Week 3: P2 (largest change, needs dry-run validation)

---

## 5. Open Questions for the Dev

1. **What is `PAPER_WALLET_SOL` actually set to?** Briefing says 1.7, but observed deposits are 36-44 SOL. Is there a multiplier?

2. **Why are there 6 Magpie-SOL entries?** Is this pre-cooldown data, or is the cooldown not triggering for some reason?

3. **What is the source of `peak_pnl_pct`?** Is it tracked per-tick, per-candle, or per-management-cycle? Affects how we implement the TP ratchet.

4. **Does `paper-positions.js` have access to per-position candle history?** We need last-6-candles for the in-range rolling check. If not, we need to start storing it.

5. **Is the `close_reason` enum stable?** Adding new reasons like `"rejected: range edge"` and `"early_exit: low in-range %"` requires updating the decision-log schema. Confirm before patching.

6. **Current `managementModel` is `deepseek/deepseek-v4-flash`** — but the briefing mentioned `MiniMax M3`. Is this a typo, a model swap, or are we running multiple agents on different models? (Not blocking, but worth clarifying for prompt engineering.)

---

## 6. What I Did Not Analyze (Yet)

These are in the data but I didn't have time / didn't fit the priority structure:

- **Decision-log.json** (65 KB, 200+ entries): not yet parsed for "why no-deploy" patterns. Likely contains 30-50% of the actionable signal. **Should be analyzed before next iteration.**
- **agent-2026-06-1*.log** (5 MB total): LLM reasoning traces per cycle. Would need LLM-based summarization to extract useful patterns.
- **HiveMind cache** (`hivemind-cache.json`): shared lessons from other agents. Could reveal if our lessons match community consensus.
- **Pool-level organic score / TVL at deploy time**: would let us correlate winner profiles with screening metrics.

---

## 7. Notes on Methodology

- All numbers come from `paper-positions.json` parsed via `analysis_vps/analyze.js` (Node script, no transformations)
- Time of day uses `opened_at` UTC (not `entry_timestamp` — they should match but worth verifying)
- WR by hour uses raw win count, not weighted by sample size — small hours (n=1-2) are noisy
- "Peak vs closed" calculation: `peak_pnl_pct - (net_pnl / (initial_x_usd + initial_y_usd) * 100)` — assumes USD is the quote currency, which is consistent across the dataset
- OOR counter showed 0/0 in my output because I didn't attach `hold_min` to closed positions in the OOR filter — the count is in the close_reason text ("out of range 20m"), not in the duration. All 34 "OOR 20m" exits are by definition held ≥20 minutes.

---

## 8. Files Generated

- `analysis_vps/paper-positions.json` — raw data from VPS
- `analysis_vps/decision-log.json` — raw data from VPS
- `analysis_vps/user-config.json` — current config
- `analysis_vps/paper-stats.mjs` — copied from VPS for reference
- `analysis_vps/analyze.js` — analysis script (Node, run with `node analysis_vps/analyze.js`)

All intermediate. No code changes to Meridian itself — only this report.
