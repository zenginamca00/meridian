#!/usr/bin/env bash
set -euo pipefail

echo "=== 1. dlmm.js: asymmetric dry range (deep below + ~30% above active) ==="
python3 - <<'PY'
p="/opt/meridian-entrytest/tools/dlmm.js"
s=open(p).read()
old="    const dryMaxBinId = isSingleSidedSol ? activeBin.binId : activeBin.binId + activeBinsAbove;"
new="    const dryMaxBinId = activeBin.binId + Math.round(activeBinsBelow * 0.3); // ASYMMETRIC experiment: ~30% bins above active"
assert old in s, "dryMaxBinId anchor not found"
open(p,"w").write(s.replace(old,new,1))
print("  dry range -> [active-binsBelow, active + 0.3*binsBelow]")
PY

echo "=== 2. paper-stats.mjs: add entry-swap slippage (two-sided pays it) ==="
python3 - <<'PY'
p="/opt/meridian-entrytest/paper-stats.mjs"
s=open(p).read()
anchor="const netG = (p) => (p.net_pnl || 0) - gasUsd(p) - swapSlipUsd(p);"
newfn='''const entrySlipUsd = (p) => {
  const ix = p.initial_x_usd || 0;
  if (ix <= 0.01) return 0;
  const numBins = (p.upper_bin_id - p.lower_bin_id + 1) || 1;
  const tvl = (p.avg_existing_bin_tvl || 0) * numBins;
  if (tvl <= 0) return 0;
  return ix * Math.min(SWAP_SLIP_CAP, ix / (tvl * SWAP_LIQ_FACTOR));
};
const netG = (p) => (p.net_pnl || 0) - gasUsd(p) - swapSlipUsd(p) - entrySlipUsd(p);'''
assert anchor in s, "netG anchor not found"
open(p,"w").write(s.replace(anchor,newfn,1))
print("  entry-swap slippage added (uses initial_x_usd)")
PY

echo "=== 3. config + disable entry filter + reset ==="
python3 - <<'PY'
import json, os
c=json.load(open("/opt/meridian-entrytest/user-config.json"))
c["minBinsBelow"]=35; c["maxBinsBelow"]=50; c["defaultBinsBelow"]=42
c["deployAmountSol"]=0.6; c["maxDeployAmount"]=0.6
c["gasReserve"]=0.12; c["minSolToOpen"]=0.72; c["positionSizePct"]=0.7; c["maxPositions"]=1
c["takeProfitPct"]=5; c["stopLossPct"]=-20; c["trailingTriggerPct"]=2; c["trailingDropPct"]=1.5
c["outOfRangeWaitMinutes"]=20; c["staleCloseMinutes"]=120; c["staleMaxInRangePct"]=40; c["repeatDeployCooldownHours"]=24
json.dump(c,open("/opt/meridian-entrytest/user-config.json","w"),indent=2)
ep="/opt/meridian-entrytest/.env"
out=["ENTRY_MIN_PC=0" if ln.startswith("ENTRY_MIN_PC=") else ln for ln in open(ep).read().splitlines()]
open(ep,"w").write("\n".join(out)+"\n")
json.dump({"positions":{}, "_meta":{"note":"ASYMMETRIC two-sided: range [active-binsBelow, active+0.3*binsBelow]. FIRST valid two-sided test. Deep buffer (jarang OOR-down) + small upside catch + small entry swap. net = gross - gas - exit slip - entry slip."}}, open("/opt/meridian-entrytest/paper-positions.json","w"), indent=2)
for f in ["pool-memory.json","lessons.json","decision-log.json","state.json"]:
    fp="/opt/meridian-entrytest/"+f
    if os.path.exists(fp): os.remove(fp)
print("  bins 35-50 below + ~30% above | entry filter OFF | reset")
PY

echo "=== 4. syntax + restart ==="
node --check /opt/meridian-entrytest/tools/dlmm.js && node --check /opt/meridian-entrytest/paper-stats.mjs && echo "SYNTAX OK"
systemctl restart meridian-entrytest
sleep 4
echo "  entrytest: $(systemctl is-active meridian-entrytest)"
