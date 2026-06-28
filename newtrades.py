import json
from datetime import datetime

CUTOFF = "2026-06-10T08:50"

with open("/opt/meridian/paper-positions.json") as f:
    data = json.load(f)

positions = data.get("positions", {})
all_pos = sorted(positions.values(), key=lambda x: x.get("opened_at", ""))

new = [p for p in all_pos if p.get("opened_at", "") >= CUTOFF]

print("=== TRADES SEJAK PERUBAHAN ({} UTC) ===".format(CUTOFF))
print("Jumlah: {} (closed: {}, open: {})".format(
    len(new),
    len([p for p in new if p.get("status") == "closed"]),
    len([p for p in new if p.get("status") != "closed"]),
))
print()

d = "$"
for i, p in enumerate(new, 1):
    pair = p.get("pair", p.get("pool_name", "?"))
    status = p.get("status", "?")
    opened = p.get("opened_at", "?")[:16]
    closed_at = (p.get("closed_at") or "")[:16]
    deposit = p.get("deposit_amount", 0) or 0
    net = p.get("net_pnl", 0) or 0
    fees = p.get("fees_earned", 0) or 0
    il = p.get("il_usd", 0) or 0
    peak = p.get("peak_pnl_pct", 0) or 0
    reason = p.get("close_reason", "-")
    pool = p.get("pool_address", "?")
    mint = p.get("base_mint", "?")
    total_c = p.get("candles_total", 0) or 0
    in_c = p.get("candles_in_range", 0) or 0
    ir = (in_c / total_c * 100) if total_c else 0
    ep = (net / deposit * 100) if deposit else 0
    icon = "OPEN" if status != "closed" else ("WIN" if net >= 0 else "LOSS")
    print("{:2}. [{}] {}".format(i, icon, pair))
    print("     Buka: {} | Tutup: {}".format(opened, closed_at or "-"))
    print("     PnL: {:+.2f}% ({}{:+.4f}) | Peak: +{:.2f}% | Fees: {}{:.4f} | IL: {}{:.4f}".format(ep, d, net, peak, d, fees, d, il))
    print("     In-range: {:.0f}% | Reason: {}".format(ir, reason))
    print("     Pool: {}".format(pool))
    print("     Mint: {}".format(mint))
    print()

# Cek duplikat antar posisi OPEN
opens = [p for p in all_pos if p.get("status") != "closed"]
print("=== DEDUP CHECK (open positions) ===")
for p in opens:
    print("  {} | pool={} | mint={}".format(
        p.get("pair", "?"), p.get("pool_address", "?"), p.get("base_mint", "?")
    ))
if len(opens) == 2:
    a, b = opens
    print("  same pool? {} | same mint? {}".format(
        a.get("pool_address") == b.get("pool_address"),
        (a.get("base_mint") or "A") == (b.get("base_mint") or "B"),
    ))
