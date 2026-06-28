#!/usr/bin/env bash
set -euo pipefail
DST=/opt/meridian-runner

echo "=== 1. Revert concentration floor (config.js 8 -> 35) ==="
python3 - <<'PY'
p="/opt/meridian-runner/config.js"
s=open(p).read()
old="export const MIN_SAFE_BINS_BELOW = 8;"
new="export const MIN_SAFE_BINS_BELOW = 35;"
assert old in s, "floor anchor not found"
open(p,"w").write(s.replace(old,new,1))
print("  floor -> 35")
PY

echo "=== 2. Wide two-sided config (mirror live exits) ==="
python3 - <<'PY'
import json
p="/opt/meridian-runner/user-config.json"
c=json.load(open(p))
c["minBinsBelow"]=35; c["maxBinsBelow"]=69; c["defaultBinsBelow"]=69   # wide (undo 8-20)
c["deployAmountSol"]=0.6; c["maxDeployAmount"]=0.6                      # 0.6 split via sim 50/50
c["gasReserve"]=0.12; c["minSolToOpen"]=0.72; c["positionSizePct"]=0.7
c["maxPositions"]=1
c["takeProfitPct"]=5; c["stopLossPct"]=-20                             # restore TP cap (undo 200)
c["trailingTriggerPct"]=2; c["trailingDropPct"]=1.5                    # match live (undo 8/8)
c["outOfRangeWaitMinutes"]=20; c["staleCloseMinutes"]=120; c["staleMaxInRangePct"]=40
c["repeatDeployCooldownHours"]=24
json.dump(c,open(p,"w"),indent=2)
print("  bins 35-69 | deploy 0.6 | TP5 SL-20 trail2/1.5 OOR20 | maxPos1")
PY

echo "=== 3. Reset state ==="
python3 - <<'PY'
import json,os
d="/opt/meridian-runner"
json.dump({"positions":{}, "_meta":{"note":"TWO-SIDED reference: wide range, sim entry=midpoint + 50/50 split = two-sided. Mirror live exits. Compare OOR%/WR/net vs LIVE single-sided."}}, open(os.path.join(d,"paper-positions.json"),"w"), indent=2)
for f in ["pool-memory.json","lessons.json","decision-log.json","state.json"]:
    fp=os.path.join(d,f)
    if os.path.exists(fp): os.remove(fp)
print("  state cleared")
PY

echo "=== 4. Restart ==="
rm -f "$DST"/logs/* 2>/dev/null || true
systemctl restart meridian-runner
sleep 4
echo "  runner: $(systemctl is-active meridian-runner)"
