import json

CUTOFF = "2026-06-10T08:50"

# ── 1. Atribusi: closed trades terakhir, dibuka kapan ──
with open("/opt/meridian/paper-positions.json") as f:
    data = json.load(f)
all_pos = sorted(data.get("positions", {}).values(), key=lambda x: x.get("opened_at", ""))
closed = [p for p in all_pos if p.get("status") == "closed"]

recent_closed = [p for p in closed if (p.get("closed_at") or "") >= "2026-06-08T00:00"]
print("=== CLOSED sejak 8 Juni (atribusi open time) ===")
for p in recent_closed:
    net = p.get("net_pnl", 0) or 0
    dep = p.get("deposit_amount", 0) or 0
    ep = (net / dep * 100) if dep else 0
    tag = "POST-FIX" if p.get("opened_at", "") >= CUTOFF else "pre-fix "
    print("  [{}] {} {:>12} | open {} | close {} | {:+.2f}% | {}".format(
        "W" if net >= 0 else "L", tag, p.get("pair", "?")[:12],
        p.get("opened_at", "?")[:16], (p.get("closed_at") or "?")[:16], ep,
        (p.get("close_reason") or "?")[:40]))

pre = [p for p in recent_closed if p.get("opened_at", "") < CUTOFF]
post = [p for p in recent_closed if p.get("opened_at", "") >= CUTOFF]
def wl(arr):
    w = len([p for p in arr if (p.get("net_pnl", 0) or 0) >= 0])
    return "{}W/{}L net ${:+.2f}".format(w, len(arr) - w, sum((p.get("net_pnl", 0) or 0) for p in arr))
print()
print("  Pre-fix entries  : " + wl(pre))
print("  Post-fix entries : " + wl(post))

# ── 2. Decision log sejak perubahan ──
print()
print("=== DECISION LOG sejak {} ===".format(CUTOFF))
try:
    with open("/opt/meridian/decision-log.json") as f:
        dlog = json.load(f)
    entries = dlog if isinstance(dlog, list) else dlog.get("decisions", dlog.get("entries", []))
    recent = [e for e in entries if str(e.get("timestamp", e.get("ts", ""))) >= CUTOFF]
    print("Cycles: {}".format(len(recent)))
    for e in recent:
        ts = str(e.get("timestamp", e.get("ts", "?")))[:16]
        dec = e.get("decision", e.get("action", "?"))
        reason = str(e.get("reason", e.get("summary", "")))[:150]
        pool = e.get("pool", e.get("pair", ""))
        print("  {} | {} | {} {}".format(ts, dec, pool, reason))
except Exception as ex:
    print("  decision-log parse error: {}".format(ex))

# ── 3. Identitas dua pool 清正 di pool-memory ──
print()
print("=== POOL MEMORY: dua pool 清正 ===")
try:
    with open("/opt/meridian/pool-memory.json") as f:
        pm = json.load(f)
    pools = pm.get("pools", pm)
    for addr in ["2mhma8RrxWUpXB4aoXgebJe88PhvagG1NsBQSvc5dcR7",
                 "8DtwLdoCahLZ1DAxk8ZviDYrAuTyFBRuE9UhXghudd2M"]:
        entry = pools.get(addr)
        if entry is None:
            print("  {}: NOT IN MEMORY".format(addr[:8]))
            continue
        keep = {k: v for k, v in entry.items() if k in (
            "pair", "name", "token", "base_mint", "mint", "mint_x", "token_mint",
            "bin_step", "deploy_count", "deploys", "last_deploy", "notes")}
        print("  {}: {}".format(addr[:8], json.dumps(keep, ensure_ascii=False)[:400]))
except Exception as ex:
    print("  pool-memory parse error: {}".format(ex))
