import json
from datetime import datetime
from collections import defaultdict

with open('/opt/meridian/paper-positions.json') as f:
    data = json.load(f)

closed = [p for p in data['positions'].values() if p.get('status') == 'closed']
closed_sorted = sorted(closed, key=lambda x: x.get('opened_at', ''))

# --- P5: Sizing ---
print('=== P5: SIZING CHECK (first 5 trades) ===')
for p in closed_sorted[:5]:
    dsol = p.get('deposit_sol', '?')
    dusd = p.get('deposit_amount', '?')
    print('  {} | deposit_sol={} | deposit_usd=${}'.format(p.get('pair','?')[:15], dsol, dusd))

# --- P1: All peak<0.05% trades ---
print()
print('=== P1: PEAK<0.05% TRADES ===')
zeros = [p for p in closed if (p.get('peak_pnl_pct') or 0) < 0.05]
for p in sorted(zeros, key=lambda x: x.get('net_pnl', 0)):
    peak = p.get('peak_pnl_pct', 0) or 0
    net = p.get('net_pnl', 0) or 0
    opened = p.get('opened_at', '')
    closed_at = p.get('closed_at') or opened
    try:
        dt_o = datetime.fromisoformat(opened.replace('Z', '+00:00'))
        dt_c = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
        mins = round((dt_c - dt_o).total_seconds() / 60)
    except Exception:
        mins = 0
    reason = p.get('close_reason', '') or ''
    print('  {:15s} | net={:+.3f} | peak={:.2f}% | hold={}m | {}'.format(
        p.get('pair','?')[:15], net, peak, mins, reason[:40]))

# --- P3: Hour-of-day ---
print()
print('=== P3: HOUR-OF-DAY (n, WR, PnL) ===')
by_hour = defaultdict(list)
for p in closed:
    opened = p.get('opened_at', '')
    try:
        h = datetime.fromisoformat(opened.replace('Z', '+00:00')).hour
    except Exception:
        h = -1
    by_hour[h].append(p)
for h in sorted(by_hour):
    arr = by_hour[h]
    wins = [p for p in arr if (p.get('net_pnl', 0) or 0) >= 0]
    total_pnl = sum(p.get('net_pnl', 0) or 0 for p in arr)
    print('  {}h UTC | n={:2d} | WR={:.0f}% | PnL={:+.2f}'.format(
        str(h).zfill(2), len(arr), len(wins)/len(arr)*100, total_pnl))

# --- P4: Peak distribution ---
print()
print('=== P4: PEAK PnL DISTRIBUTION (trailing TP assessment) ===')
buckets = [(0, 1), (1, 1.5), (1.5, 2), (2, 3), (3, 4), (4, 5), (5, 10)]
for lo, hi in buckets:
    arr = [p for p in closed if lo <= (p.get('peak_pnl_pct', 0) or 0) < hi]
    wins = [p for p in arr if (p.get('net_pnl', 0) or 0) >= 0]
    avg_peak = sum(p.get('peak_pnl_pct', 0) or 0 for p in arr) / len(arr) if arr else 0
    avg_close = sum((p.get('net_pnl', 0) or 0) / (p.get('deposit_amount', 1)) * 100 for p in arr) / len(arr) if arr else 0
    print('  peak {}-{}%: n={:2d} | {}W/{}L | avg_peak={:.2f}% | avg_close={:+.2f}%'.format(
        lo, hi, len(arr), len(wins), len(arr)-len(wins), avg_peak, avg_close))
