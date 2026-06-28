# Add /net Telegram command to index.js — real net PnL (wallet + live position value - baseline).
path = "/opt/meridian/index.js"
s = open(path).read()

ANCHOR = r"""  const poolMatch = text.match(/^\/pool\s+(\d+)$/i);"""
assert ANCHOR in s, "poolMatch anchor not found"
assert "/net" not in s.split("setupTelegram")[0] or True  # idempotency soft-check

NET_HANDLER = r'''  if (text === "/net") {
    try {
      const BASELINE_SOL = 1.048638; // 0.3234 first-live + 0.725 deposit Indodax (update kalau nambah modal)
      const [wallet, posData] = await Promise.all([getWalletBalances(), getMyPositions({ force: true })]);
      const solPrice = wallet.sol_price || 75;
      const liquidSol = wallet.sol || 0;
      const positions = posData.positions || [];
      let posUsd = 0;
      for (const p of positions) posUsd += (p.total_value_usd || 0) + (p.unclaimed_fees_usd || 0);
      const posSol = solPrice > 0 ? posUsd / solPrice : 0;
      const totalSol = liquidSol + posSol;
      const netSol = totalSol - BASELINE_SOL;
      const netUsd = netSol * solPrice;
      const sign = netSol >= 0 ? "+" : "-";
      const msg = [
        "NET PnL (real, after everything)",
        "",
        "Modal invested : " + BASELINE_SOL.toFixed(4) + " SOL",
        "Wallet liquid  : " + liquidSol.toFixed(4) + " SOL",
        "Open positions : " + posSol.toFixed(4) + " SOL ($" + posUsd.toFixed(2) + ") [" + positions.length + " pos]",
        "Total          : " + totalSol.toFixed(4) + " SOL ($" + (totalSol * solPrice).toFixed(2) + ")",
        "NET: " + sign + Math.abs(netSol).toFixed(4) + " SOL (" + sign + "$" + Math.abs(netUsd).toFixed(2) + ") [" + sign + Math.abs(netSol / BASELINE_SOL * 100).toFixed(2) + "%]",
      ].join("\n");
      await sendMessage(msg).catch(() => {});
    } catch (e) {
      await sendMessage("Error: " + e.message).catch(() => {});
    }
    return;
  }

'''

s = s.replace(ANCHOR, NET_HANDLER + ANCHOR, 1)

HELP_ANCHOR = '    "/positions — list open positions",'
if HELP_ANCHOR in s:
    s = s.replace(HELP_ANCHOR, HELP_ANCHOR + '\n    "/net — real net PnL (wallet + posisi - modal)",', 1)

open(path, "w").write(s)
print("  /net command added to index.js")
