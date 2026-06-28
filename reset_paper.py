"""
Reset paper-positions.json for a fresh dry run.
- Archives current file as paper-positions-v1-backup.json
- Keeps only the 2 currently OPEN positions
- Writes clean paper-positions.json with empty closed history
"""
import json
import shutil
from datetime import datetime

src = "/opt/meridian/paper-positions.json"
backup = "/opt/meridian/paper-positions-v1-backup.json"

with open(src) as f:
    data = json.load(f)

# Backup full state
shutil.copy2(src, backup)
print(f"✅ Backed up to {backup}")

positions = data.get("positions", {})
open_positions = {k: v for k, v in positions.items() if v.get("status") != "closed"}
closed_count = sum(1 for v in positions.values() if v.get("status") == "closed")

print(f"   {closed_count} closed positions archived")
print(f"   {len(open_positions)} open positions kept:")
for k, v in open_positions.items():
    print(f"     {v.get('pair','?')} | pool={v.get('pool_address','?')[:8]} | net_pnl=${v.get('net_pnl',0):.2f}")

# Build fresh state — only open positions, clean metadata
now = datetime.utcnow().isoformat() + "Z"
new_data = {
    "positions": open_positions,
    "_meta": {
        "reset_at": now,
        "v1_backup": backup,
        "v1_closed_count": closed_count,
        "note": "Fresh run v2: P1 false-entry filter + FIX-C base_mint + FIX-D cooldown/lessons active"
    }
}

# Preserve any top-level keys that aren't positions/_meta
for k, v in data.items():
    if k not in ("positions", "_meta"):
        new_data[k] = v

with open(src, "w") as f:
    json.dump(new_data, f, indent=2)

print(f"\n✅ Reset complete. New paper-positions.json has {len(open_positions)} open position(s).")
print("   Run: systemctl restart meridian")
