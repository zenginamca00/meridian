"""
Patch two bugs in paper-trading pipeline:

Fix A: paper-positions.js — call recordPoolDeploy + recordPerformance
        from evaluatePaperExits so cooldown & lessons work in paper mode.

Fix B: tools/dlmm.js — add base_mint to would_deploy so paper bridge
        can dedup by token and lessons track the right mint.
"""
import re

# ─── Fix B: dlmm.js ──────────────────────────────────────────────────────────

dlmm_path = "/opt/meridian/tools/dlmm.js"
with open(dlmm_path) as f:
    dlmm = f.read()

OLD_WOULD = """      would_deploy: {
        pool_address,
        strategy: activeStrategy,"""

NEW_WOULD = """      would_deploy: {
        pool_address,
        base_mint: baseMint,
        strategy: activeStrategy,"""

assert OLD_WOULD in dlmm, "dlmm.js patch anchor not found — check manually"
dlmm_new = dlmm.replace(OLD_WOULD, NEW_WOULD, 1)
assert dlmm_new != dlmm, "dlmm.js patch had no effect"

with open(dlmm_path, "w") as f:
    f.write(dlmm_new)
print("✅ Fix B applied: base_mint added to would_deploy in dlmm.js")

# ─── Fix A: paper-positions.js ───────────────────────────────────────────────

pp_path = "/opt/meridian/paper-positions.js"
with open(pp_path) as f:
    pp = f.read()

# 1. Add imports after the existing logger import
OLD_IMPORT = 'import { log } from "./logger.js";'
NEW_IMPORT = '''import { log } from "./logger.js";
import { recordPoolDeploy } from "./pool-memory.js";
import { recordPerformance } from "./lessons.js";'''

assert OLD_IMPORT in pp, "paper-positions.js import anchor not found"
pp_new = pp.replace(OLD_IMPORT, NEW_IMPORT, 1)

# 2. Add recordPoolDeploy + recordPerformance calls inside the `if (reason)` block,
#    right after the log line that says "Auto-closed".
OLD_LOG = '      log("paper_sim", `Auto-closed ${pos.id}: ${reason} | netPnL=$${pos.net_pnl} (${pnlPct.toFixed(1)}%)`);'
NEW_LOG = '''      log("paper_sim", `Auto-closed ${pos.id}: ${reason} | netPnL=$${pos.net_pnl} (${pnlPct.toFixed(1)}%)`);

      // Record to pool-memory (drives cooldown) and lessons (drives learning).
      // Fire-and-forget — paper exit must not block on I/O errors.
      try {
        recordPoolDeploy(pos.pool_address, {
          pool_name:   pos.pool_name,
          base_mint:   pos.base_mint ?? null,
          deployed_at: pos.opened_at,
          closed_at:   pos.closed_at,
        });
      } catch (e) {
        log("paper_sim", `recordPoolDeploy failed for ${pos.id}: ${e.message}`);
      }
      const _minutesHeld = pos.last_candle_timestamp && pos.entry_timestamp
        ? Math.floor((pos.last_candle_timestamp - pos.entry_timestamp) / 60) : 0;
      const _minutesInRange = pos.candles_total > 0
        ? Math.floor(_minutesHeld * (pos.candles_in_range / pos.candles_total)) : 0;
      recordPerformance({
        position:          pos.id,
        pool:              pos.pool_address,
        pool_name:         pos.pool_name,
        base_mint:         pos.base_mint ?? null,
        strategy:          pos.strategy_type,
        bin_step:          pos.bin_step ?? null,
        amount_sol:        pos.deposit_sol ?? null,
        fees_earned_usd:   pos.fees_earned,
        final_value_usd:   pos.deposit_amount + pos.net_pnl,
        initial_value_usd: pos.deposit_amount,
        minutes_in_range:  _minutesInRange,
        minutes_held:      _minutesHeld,
        close_reason:      pos.close_reason,
      }).catch((e) => log("paper_sim", `recordPerformance failed for ${pos.id}: ${e.message}`));'''

assert OLD_LOG in pp_new, "paper-positions.js log anchor not found"
pp_new = pp_new.replace(OLD_LOG, NEW_LOG, 1)
assert pp_new != pp, "paper-positions.js patch had no effect"

with open(pp_path, "w") as f:
    f.write(pp_new)
print("✅ Fix A applied: recordPoolDeploy + recordPerformance added to evaluatePaperExits")
print()
print("Both patches done. Restart meridian to activate.")
