"""
P1: Two-part false-entry protection

Part A — executor.js: Block pool with recent OOR streak (2+ OOR closes in <4h).
  Prevents GO-SOL type re-entries into pools actively dumping.

Part B — paper-positions.js: Fast-exit "never in range" positions after 4 candles.
  Cuts dead-on-arrival positions after 20min instead of waiting full OOR timer.
"""

# ─── Part A: executor.js ──────────────────────────────────────────────────────

exec_path = "/opt/meridian/tools/executor.js"
with open(exec_path) as f:
    executor = f.read()

OLD_DUP = """      // Block same base token across different pools
      if (args.base_mint) {"""

NEW_DUP = """      // Block pool with recent OOR streak — prevents re-entry into actively dumping pools
      try {
        const poolMem = getPoolMemory({ pool_address: args.pool_address });
        if (poolMem?.deploys?.length) {
          const fourHoursAgo = Date.now() - 4 * 60 * 60 * 1000;
          const recentOOR = poolMem.deploys.filter(
            (d) => d.closed_at && new Date(d.closed_at).getTime() > fourHoursAgo &&
              typeof d.close_reason === "string" && d.close_reason.includes("out of range")
          );
          if (recentOOR.length >= 2) {
            return {
              pass: false,
              reason: `OOR streak: pool had ${recentOOR.length} OOR exits in the last 4h — likely dumping. Skip.`,
            };
          }
        }
      } catch (_) {}

      // Block same base token across different pools
      if (args.base_mint) {"""

assert OLD_DUP in executor, "executor.js Part A anchor not found"
executor_new = executor.replace(OLD_DUP, NEW_DUP, 1)
assert executor_new != executor

with open(exec_path, "w") as f:
    f.write(executor_new)
print("✅ Part A: OOR-streak block added to executor.js pre-deploy checks")

# ─── Part B: paper-positions.js ──────────────────────────────────────────────

pp_path = "/opt/meridian/paper-positions.js"
with open(pp_path) as f:
    pp = f.read()

# Insert before the stale dead-money check
OLD_STALE = """    } else if (
      mgmtConfig.staleCloseMinutes != null && mgmtConfig.staleCloseMinutes > 0 &&
      ageMinutes >= mgmtConfig.staleCloseMinutes &&
      inRangePct < (mgmtConfig.staleMaxInRangePct ?? 25)
    ) {
      reason = `stale dead-money (age ${ageMinutes}m, in-range ${inRangePct.toFixed(0)}%)`;"""

NEW_STALE = """    } else if (
      pos.candles_total >= 4 &&
      pos.candles_in_range === 0 &&
      ageMinutes < 120
    ) {
      reason = `false entry: never in range after ${pos.candles_total} candles (${ageMinutes}m)`;
    } else if (
      mgmtConfig.staleCloseMinutes != null && mgmtConfig.staleCloseMinutes > 0 &&
      ageMinutes >= mgmtConfig.staleCloseMinutes &&
      inRangePct < (mgmtConfig.staleMaxInRangePct ?? 25)
    ) {
      reason = `stale dead-money (age ${ageMinutes}m, in-range ${inRangePct.toFixed(0)}%)`;"""

assert OLD_STALE in pp, "paper-positions.js Part B anchor not found"
pp_new = pp.replace(OLD_STALE, NEW_STALE, 1)
assert pp_new != pp

with open(pp_path, "w") as f:
    f.write(pp_new)
print("✅ Part B: false-entry fast-exit added to paper-positions.js evaluatePaperExits")
print()
print("Both patches done. Run reset_paper.py next, then restart meridian.")
