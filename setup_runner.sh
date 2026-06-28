#!/usr/bin/env bash
set -euo pipefail

SRC=/opt/meridian
DST=/opt/meridian-runner

echo "=== 1. Stop existing runner (if any) + fresh copy ==="
systemctl stop meridian-runner 2>/dev/null || true
rm -rf "$DST"
cp -r "$SRC" "$DST"
echo "Copied $SRC -> $DST"

echo "=== 2. Patch concentration floor (config.js MIN_SAFE_BINS_BELOW 35 -> 8) ==="
python3 - <<'PY'
p = "/opt/meridian-runner/config.js"
s = open(p).read()
old = "export const MIN_SAFE_BINS_BELOW = 35;"
new = "export const MIN_SAFE_BINS_BELOW = 8;"
assert old in s, "MIN_SAFE_BINS_BELOW anchor not found"
open(p, "w").write(s.replace(old, new, 1))
print("  config.js floor -> 8")
PY

echo "=== 3. Experiment config (concentration + let winners run) ==="
python3 - <<'PY'
import json
p = "/opt/meridian-runner/user-config.json"
c = json.load(open(p))
c["minBinsBelow"]       = 8     # concentrate (vs 35 main)
c["maxBinsBelow"]       = 20    # concentrate (vs 69 main)
c["defaultBinsBelow"]   = 20
c["takeProfitPct"]      = 200   # effectively OFF (no +5% ceiling)
c["trailingTriggerPct"] = 8     # don't protect until +8%
c["trailingDropPct"]    = 8     # 8 PnL-points room to breathe
# everything else identical to main (deploy 1.1, maxPositions 1, same screening filters)
json.dump(c, open(p, "w"), indent=2)
print("  bins 8-20 | TP off (200) | trailing 8/8 | deploy", c["deployAmountSol"], "| maxPos", c["maxPositions"])
PY

echo "=== 4. Reset runner state (fresh, isolated) ==="
python3 - <<'PY'
import json, os
d = "/opt/meridian-runner"
json.dump({"positions": {}, "_meta": {"note": "RUNNER experiment: 8-20 bins concentration, no TP cap, trailing 8/8"}},
          open(os.path.join(d, "paper-positions.json"), "w"), indent=2)
for f in ["pool-memory.json", "lessons.json", "decision-log.json", "state.json"]:
    fp = os.path.join(d, f)
    if os.path.exists(fp):
        os.remove(fp)
print("  paper-positions emptied; pool-memory/lessons/decision-log/state cleared")
PY

echo "=== 5. Disable Telegram in runner .env (avoid 409 polling conflict) ==="
python3 - <<'PY'
p = "/opt/meridian-runner/.env"
disable = {"TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_THREAD_ID", "TELEGRAM_ALLOWED_USER_IDS"}
out = []
for ln in open(p).read().splitlines():
    key = ln.split("=", 1)[0].strip()
    out.append(key + "=" if key in disable else ln)
open(p, "w").write("\n".join(out) + "\n")
print("  Telegram vars blanked")
PY

echo "=== 6. Clear runner logs ==="
rm -f "$DST"/logs/* 2>/dev/null || true

echo "=== 7. Create systemd unit meridian-runner ==="
cat > /etc/systemd/system/meridian-runner.service <<'UNIT'
[Unit]
Description=Meridian DLMM LP Agent — RUNNER experiment (concentration + let-winners-run)
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/meridian-runner
ExecStart=/usr/bin/node index.js
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT
echo "  unit written"

echo "=== 8. Start runner ==="
systemctl daemon-reload
systemctl enable meridian-runner 2>/dev/null
systemctl start meridian-runner
sleep 3
echo "  main:   $(systemctl is-active meridian)"
echo "  runner: $(systemctl is-active meridian-runner)"
