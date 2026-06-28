import json
from datetime import datetime

with open("/opt/meridian/paper-positions.json") as f:
    data = json.load(f)

positions = data.get("positions", {})
all_pos = list(positions.values())

closed = [p for p in all_pos if p.get("status") == "closed"]
open_pos = [p for p in all_pos if p.get("status") != "closed"]
closed_sorted = sorted(closed, key=lambda x: x.get("opened_at", ""))

nets = [p.get("net_pnl", 0) or 0 for p in closed]
total_net = sum(nets)
total_fees = sum(p.get("fees_earned", 0) or 0 for p in closed)
total_deposit = sum(p.get("deposit_amount", 0) or 0 for p in closed)
wins = [p for p in closed if (p.get("net_pnl", 0) or 0) >= 0]
losses = [p for p in closed if (p.get("net_pnl", 0) or 0) < 0]
avg_w = (
    sum(p.get("net_pnl", 0) / p.get("deposit_amount", 1) * 100 for p in wins if p.get("deposit_amount", 0))
    / len(wins)
    if wins
    else 0
)
avg_l = (
    sum(p.get("net_pnl", 0) / p.get("deposit_amount", 1) * 100 for p in losses if p.get("deposit_amount", 0))
    / len(losses)
    if losses
    else 0
)

d = "$"
print("=== PAPER STATS ===")
print("Total: {} | Closed: {} | Open: {}".format(len(all_pos), len(closed), len(open_pos)))

first_o = closed_sorted[0].get("opened_at", "?")[:19] if closed_sorted else "?"
last_c = closed_sorted[-1].get("closed_at", "?")[:19] if closed_sorted else "?"
print("First signal: {} UTC".format(first_o))
print("Last closed:  {} UTC".format(last_c))
print("W/L: {}/{} | WR: {:.1f}%".format(len(wins), len(losses), len(wins) / len(closed) * 100))
print("Avg W: +{:.2f}% | Avg L: {:.2f}%".format(avg_w, avg_l))
print("Total deposit: {}{:.2f}".format(d, total_deposit))
print("Total net PnL: {}{:+.4f}".format(d, total_net))
print("Total fees:    {}{:.4f}".format(d, total_fees))
print()

print("=== CLOSED POSITIONS ===")
print()
for i, p in enumerate(closed_sorted, 1):
    opened = p.get("opened_at", "?")
    closed_at = p.get("closed_at", "?")
    pair = p.get("pair", p.get("pool_name", "?"))
    deposit = p.get("deposit_amount", 0) or 0
    net = p.get("net_pnl", 0) or 0
    fees = p.get("fees_earned", 0) or 0
    il = p.get("il_usd", 0) or 0
    peak = p.get("peak_pnl_pct", 0) or 0
    reason = p.get("close_reason", "?")
    exit_pct = (net / deposit * 100) if deposit else 0
    total_c = p.get("candles_total", 0) or 0
    in_c = p.get("candles_in_range", 0) or 0
    in_range_pct = (in_c / total_c * 100) if total_c else 0
    try:
        dt_o = datetime.fromisoformat(opened.replace("Z", "+00:00"))
        dt_c = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
        dm = (dt_c - dt_o).total_seconds() / 60
        dur = "{}h{}m".format(int(dm // 60), int(dm % 60)) if dm >= 60 else "{:.0f}m".format(dm)
    except Exception:
        dur = "?"
    icon = "WIN" if net >= 0 else "LOSS"
    o_str = opened[:16]
    c_str = closed_at[:16]
    print("{:2}. [{}] {} ({})".format(i, icon, pair, dur))
    print("     Buka:  {} UTC".format(o_str))
    print("     Tutup: {} UTC".format(c_str))
    print("     Exit: {:+.2f}% ({}{:+.4f}) | Peak: +{:.2f}%".format(exit_pct, d, net, peak))
    print("     Deposit: {}{:.2f} | Fees: {}{:.4f} | IL: {}{:.4f}".format(d, deposit, d, fees, d, il))
    print("     In-range: {:.0f}% | Reason: {}".format(in_range_pct, reason))
    print()

print("=== OPEN NOW ===")
for p in open_pos:
    pair = p.get("pair", p.get("pool_name", "?"))
    opened = p.get("opened_at", "?")
    deposit = p.get("deposit_amount", 0) or 0
    net = p.get("net_pnl", 0) or 0
    peak = p.get("peak_pnl_pct", 0) or 0
    total_c = p.get("candles_total", 0) or 0
    in_c = p.get("candles_in_range", 0) or 0
    ir = (in_c / total_c * 100) if total_c else 0
    ep = (net / deposit * 100) if deposit else 0
    o_str = opened[:16]
    print(
        "  {} | Buka: {} UTC | Dep: {}{:.2f} | PnL: {:+.2f}% ({}{:+.4f}) | Peak: +{:.2f}% | In-range: {:.0f}%".format(
            pair, o_str, d, deposit, ep, d, net, peak, ir
        )
    )
