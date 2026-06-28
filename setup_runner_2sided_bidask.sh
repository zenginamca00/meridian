#!/usr/bin/env bash
set -euo pipefail
D=/opt/meridian-runner

echo "=== 1. dlmm.js: asymmetric dry range (deep below + ~30% above) ==="
python3 - <<'PY'
p="/opt/meridian-runner/tools/dlmm.js"
s=open(p).read()
old="    const dryMaxBinId = isSingleSidedSol ? activeBin.binId : activeBin.binId + activeBinsAbove;"
new="    const dryMaxBinId = activeBin.binId + Math.round(activeBinsBelow * 0.3); // ASYMMETRIC two-sided"
assert old in s, "dryMaxBinId anchor not found"
open(p,"w").write(s.replace(old,new,1))
print("  asymmetric range applied")
PY

echo "=== 2. paper-stats.mjs: add entry-swap slippage ==="
python3 - <<'PY'
p="/opt/meridian-runner/paper-stats.mjs"
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
print("  entry-swap slippage added")
PY

echo "=== 3. config: keep bid_ask, asymmetric bins, deploy 0.6 + reset ==="
python3 - <<'PY'
import json, os
c=json.load(open("/opt/meridian-runner/user-config.json"))
c["strategy"]="bid_ask"
c["minBinsBelow"]=35; c["maxBinsBelow"]=50; c["defaultBinsBelow"]=42
json.dump(c,open("/opt/meridian-runner/user-config.json","w"),indent=2)
json.dump({"positions":{}, "_meta":{"note":"ASYMMETRIC TWO-SIDED + BID_ASK. Sama kaya entrytest (curve) tapi shape bid_ask. A/B: curve vs bid_ask buat two-sided."}}, open("/opt/meridian-runner/paper-positions.json","w"), indent=2)
for f in ["pool-memory.json","lessons.json","decision-log.json","state.json"]:
    fp="/opt/meridian-runner/"+f
    if os.path.exists(fp): os.remove(fp)
print("  bid_ask | asymmetric 35-50 below + 30% above | reset")
PY

echo "=== 4. syntax + restart ==="
node --check /opt/meridian-runner/tools/dlmm.js && node --check /opt/meridian-runner/paper-stats.mjs && echo "SYNTAX OK"
systemctl restart meridian-runner
sleep 3
echo "  runner: $(systemctl is-active meridian-runner)"
