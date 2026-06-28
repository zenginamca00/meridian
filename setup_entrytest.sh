#!/usr/bin/env bash
set -euo pipefail

SRC=/opt/meridian
DST=/opt/meridian-entrytest

echo "=== 1. Fresh copy ==="
systemctl stop meridian-entrytest 2>/dev/null || true
rm -rf "$DST"
cp -r "$SRC" "$DST"
echo "Copied -> $DST"

echo "=== 2. Patch screening.js — entry momentum gate ==="
python3 - <<'PY'
p = "/opt/meridian-entrytest/tools/screening.js"
s = open(p).read()
OLD = '''        pushFilteredReason(filteredOut, p, "token cooldown active");
        return false;
      }
      return true;
    })'''
NEW = '''        pushFilteredReason(filteredOut, p, "token cooldown active");
        return false;
      }
      // Entry momentum gate (experiment): only enter tokens that recently pumped,
      // betting on a pullback into the below-price SOL range to cut instant OOR.
      const _minPC = Number(process.env.ENTRY_MIN_PC ?? 0);
      const _maxPC = Number(process.env.ENTRY_MAX_PC ?? Infinity);
      if (_minPC > 0) {
        const _pc = Number(p.price_change_pct);
        if (!Number.isFinite(_pc) || _pc < _minPC || _pc > _maxPC) {
          pushFilteredReason(filteredOut, p, `price_change ${Number.isFinite(_pc) ? _pc : "unknown"}% outside entry band [${_minPC}, ${_maxPC}]`);
          return false;
        }
      }
      return true;
    })'''
assert OLD in s, "screening.js anchor not found"
open(p, "w").write(s.replace(OLD, NEW, 1))
print("  entry gate added (reads ENTRY_MIN_PC / ENTRY_MAX_PC)")
PY

echo "=== 3. .env — empty burner wallet, paper, telegram off, entry band ==="
python3 - <<'PY'
# reuse the old empty-wallet key from the runner (never funded) so even a DRY_RUN bug can't lose money
runner_key = ""
for ln in open("/opt/meridian-runner/.env").read().splitlines():
    if ln.startswith("WALLET_PRIVATE_KEY="):
        runner_key = ln.split("=", 1)[1]; break

ep = "/opt/meridian-entrytest/.env"
disable = {"TELEGRAM_BOT_TOKEN","TELEGRAM_CHAT_ID","TELEGRAM_THREAD_ID","TELEGRAM_ALLOWED_USER_IDS"}
out = []
for ln in open(ep).read().splitlines():
    k = ln.split("=", 1)[0].strip()
    if k == "WALLET_PRIVATE_KEY": out.append("WALLET_PRIVATE_KEY=" + runner_key)
    elif k == "DRY_RUN":          out.append("DRY_RUN=true")
    elif k in disable:            out.append(k + "=")
    else:                          out.append(ln)
out += ["ENTRY_MIN_PC=4", "ENTRY_MAX_PC=30"]
open(ep, "w").write("\n".join(out) + "\n")
print("  wallet=empty-burner, DRY_RUN=true, telegram off, ENTRY band [4,30]")
PY

echo "=== 4. Config — standard paper sizing (bins 35-69 untouched) ==="
python3 - <<'PY'
import json
p = "/opt/meridian-entrytest/user-config.json"
c = json.load(open(p))
c["deployAmountSol"] = 0.6
c["maxDeployAmount"] = 2
c["minSolToOpen"]    = 0.65
c["gasReserve"]      = 0.2
c["positionSizePct"] = 0.35
c["maxPositions"]    = 1
json.dump(c, open(p, "w"), indent=2)
print("  deploy 0.6 / maxPos 1 / bins 35-69 (single-sided baseline + entry filter)")
PY

echo "=== 5. Reset state ==="
python3 - <<'PY'
import json, os
d = "/opt/meridian-entrytest"
json.dump({"positions": {}, "_meta": {"note": "ENTRY-FILTER experiment: deploy only if token price_change in [4,30]% — bet on pullback into below-price range"}},
          open(os.path.join(d, "paper-positions.json"), "w"), indent=2)
for f in ["pool-memory.json", "lessons.json", "decision-log.json", "state.json"]:
    fp = os.path.join(d, f)
    if os.path.exists(fp): os.remove(fp)
print("  state cleared")
PY

echo "=== 6. Clear logs ==="
rm -f "$DST"/logs/* 2>/dev/null || true

echo "=== 7. systemd unit (start only, not boot-enabled) ==="
cat > /etc/systemd/system/meridian-entrytest.service <<'UNIT'
[Unit]
Description=Meridian DLMM LP Agent — ENTRY-FILTER experiment (deploy after >=4% pump)
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/meridian-entrytest
ExecStart=/usr/bin/node index.js
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl start meridian-entrytest
sleep 4
echo "  live:      $(systemctl is-active meridian)"
echo "  runner:    $(systemctl is-active meridian-runner)"
echo "  entrytest: $(systemctl is-active meridian-entrytest)"
