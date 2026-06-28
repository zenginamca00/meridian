import urllib.request, json

BASELINE_SOL = 1.048638      # 0.3234 first-live + 0.725 deposit Indodax (2026-06-15)
W = "2t6GfdVdHtjz4phfwN44VqhJrfFCBbwxpebqQVrf7uX4"
RENT_PER_POS = 0.057         # refundable position rent

def rpc(m, p):
    r = urllib.request.Request("https://api.mainnet-beta.solana.com",
        data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),
        headers={"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(r))["result"]

def solprice():
    try:
        r = urllib.request.urlopen("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd")
        return json.load(r)["solana"]["usd"]
    except Exception:
        return 73.6

sol = rpc("getBalance", [W])["value"] / 1e9
px = solprice()

# tokens still in wallet
ta = rpc("getTokenAccountsByOwner", [W,
    {"programId":"TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"}, {"encoding":"jsonParsed"}])
toks = []
for a in ta["value"]:
    info = a["account"]["data"]["parsed"]["info"]
    amt = info["tokenAmount"]["uiAmount"]
    if amt and amt > 0:
        toks.append((info["mint"][:8], amt))

# open LP positions from bot state (deposit + rent, refundable)
open_sol, open_count = 0.0, 0
try:
    st = json.load(open("/opt/meridian/state.json"))
    for _, p in st.get("positions", {}).items():
        if not p.get("closed"):
            open_sol += (p.get("amount_sol") or 0) + RENT_PER_POS
            open_count += 1
except Exception:
    pass

total = sol + open_sol
net = total - BASELINE_SOL
print("=== NET PnL (real, after everything) ===")
print(f"Modal invested : {BASELINE_SOL:.4f} SOL  (${BASELINE_SOL*px:.2f})")
print(f"Wallet liquid  : {sol:.4f} SOL  (${sol*px:.2f})")
if open_count:
    print(f"Open positions : {open_sol:.4f} SOL  (${open_sol*px:.2f})  [{open_count} pos: deposit+rent est]")
print(f"SOL price      : ${px:.2f}")
print(f"TOTAL          : {total:.4f} SOL  (${total*px:.2f})")
print(f"NET            : {net:+.4f} SOL  (${net*px:+.2f})  [{net/BASELINE_SOL*100:+.2f}%]")
if toks:
    print("Tokens wallet  :", ", ".join(f"{m}..x{a:g}" for m, a in toks), "(dust, belum dinilai)")
if open_count:
    print("NOTE: posisi open dinilai pakai deposit+rent (perkiraan); PnL unrealized-nya belum presisi.")
