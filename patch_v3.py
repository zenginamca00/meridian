# -*- coding: utf-8 -*-
"""
V3 changes:
1. Config: deployAmountSol 0.6 -> 1.1, maxPositions 2 -> 1
2. paper-stats.mjs: add gas model (honest gate) + GATE_SAMPLE 30 -> 15
3. Reset paper-positions.json (archive v2, start empty)
"""
import json
import shutil
from datetime import datetime

# ── 1. CONFIG ─────────────────────────────────────────────────────────────────
cfg_path = "/opt/meridian/user-config.json"
cfg = json.load(open(cfg_path))
cfg["deployAmountSol"] = 1.1
cfg["maxPositions"] = 1
json.dump(cfg, open(cfg_path, "w"), indent=2)
print(f"✅ Config: deployAmountSol={cfg['deployAmountSol']} | maxPositions={cfg['maxPositions']}")

# ── 2. PAPER-STATS GAS MODEL + GATE SAMPLE ────────────────────────────────────
stats_path = "/opt/meridian/paper-stats.mjs"
stats = open(stats_path, encoding="utf-8").read()

# E: gas constant after GATE_WR
OLD_E = "const GATE_WR     = 15; // %"
NEW_E = ("const GATE_WR     = 15; // %\n"
         "const GAS_PER_TRADE_SOL = 0.006; // est. non-refundable Meteora round-trip gas; calibrate after 1 real deploy+close")
assert OLD_E in stats, "anchor E not found"
stats = stats.replace(OLD_E, NEW_E, 1)

# D: gate sample
OLD_D = "const GATE_SAMPLE = 30;"
NEW_D = "const GATE_SAMPLE = 15;"
assert OLD_D in stats, "anchor D not found"
stats = stats.replace(OLD_D, NEW_D, 1)

# A: gas helpers + redefined pct/wins/losses/sum
OLD_A = ("const pct = (p) => (p.deposit_amount > 0 ? (p.net_pnl / p.deposit_amount) * 100 : 0);\n"
         "const wins = closed.filter((p) => p.net_pnl > 0);\n"
         "const losses = closed.filter((p) => p.net_pnl <= 0);\n"
         "const sum = (arr, f) => arr.reduce((a, x) => a + f(x), 0);")
NEW_A = (
    "// Gas model — paper sim runs DRY_RUN (no on-chain tx), so gas is modeled here\n"
    "// to keep the validation gate honest. Round-trip = deploy+close+swap, non-refundable.\n"
    "const gasUsd = (p) => {\n"
    "  const solPrice = (p.deposit_sol && p.deposit_amount > 0) ? p.deposit_amount / p.deposit_sol : 70;\n"
    "  return GAS_PER_TRADE_SOL * solPrice;\n"
    "};\n"
    "const netG = (p) => (p.net_pnl || 0) - gasUsd(p);\n"
    "const pct = (p) => (p.deposit_amount > 0 ? (netG(p) / p.deposit_amount) * 100 : 0);\n"
    "const wins = closed.filter((p) => netG(p) > 0);\n"
    "const losses = closed.filter((p) => netG(p) <= 0);\n"
    "const sum = (arr, f) => arr.reduce((a, x) => a + f(x), 0);"
)
assert OLD_A in stats, "anchor A not found"
stats = stats.replace(OLD_A, NEW_A, 1)

# B: gross win/loss use netG
OLD_B = ("const grossWin = sum(wins, (p) => p.net_pnl);\n"
         "const grossLoss = Math.abs(sum(losses, (p) => p.net_pnl));")
NEW_B = ("const grossWin = sum(wins, netG);\n"
         "const grossLoss = Math.abs(sum(losses, netG));")
assert OLD_B in stats, "anchor B not found"
stats = stats.replace(OLD_B, NEW_B, 1)

# C: netUsd use netG + add gross/gas totals
OLD_C = "const netUsd = sum(closed, (p) => p.net_pnl);"
NEW_C = ("const netUsd = sum(closed, netG);\n"
         "const grossPnlUsd = sum(closed, (p) => p.net_pnl || 0);\n"
         "const totalGasUsd = sum(closed, gasUsd);")
assert OLD_C in stats, "anchor C not found"
stats = stats.replace(OLD_C, NEW_C, 1)

# F: net PnL display -> gross/gas/net
OLD_F = "console.log(`  Net PnL: $${f(netUsd)} · Fees: $${netFees.toFixed(2)}`);"
NEW_F = ("console.log(`  Gross PnL: $${f(grossPnlUsd)} · Gas: -$${totalGasUsd.toFixed(2)} (@${GAS_PER_TRADE_SOL} SOL/trade)`);\n"
         "console.log(`  Net (after gas): $${f(netUsd)} · Fees: $${netFees.toFixed(2)}`);")
assert OLD_F in stats, "anchor F not found"
stats = stats.replace(OLD_F, NEW_F, 1)

open(stats_path, "w", encoding="utf-8").write(stats)
print("✅ paper-stats.mjs: gas model added + GATE_SAMPLE=15")

# ── 3. RESET PAPER POSITIONS (full archive, start empty) ──────────────────────
pp_path = "/opt/meridian/paper-positions.json"
backup = "/opt/meridian/paper-positions-v2-backup.json"
data = json.load(open(pp_path))
shutil.copy2(pp_path, backup)

positions = data.get("positions", {})
closed_n = sum(1 for v in positions.values() if v.get("status") == "closed")
open_n = sum(1 for v in positions.values() if v.get("status") != "closed")
print(f"✅ Archived {backup}: {closed_n} closed + {open_n} open")

now = datetime.now().isoformat() + "Z"
new_data = {
    "positions": {},
    "_meta": {
        "reset_at": now,
        "v2_backup": backup,
        "v2_closed_count": closed_n,
        "note": "V3 fresh: deploy 1.1 SOL, max 1 position, gas-aware gate (GATE_SAMPLE=15)"
    }
}
for k, v in data.items():
    if k not in ("positions", "_meta"):
        new_data[k] = v
json.dump(new_data, open(pp_path, "w"), indent=2)
print("✅ paper-positions.json reset to empty (fresh V3 run)")
print("\nAll V3 changes done. Restart meridian next.")
