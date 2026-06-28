# Add swap-slippage model to paper-stats.mjs (all paper instances) + fix netpnl baseline.
STATS_PATHS = [
    "/opt/meridian/paper-stats.mjs",
    "/opt/meridian-runner/paper-stats.mjs",
    "/opt/meridian-entrytest/paper-stats.mjs",
]

A_GAS = 'const GAS_PER_TRADE_SOL = 0.006; // est. non-refundable Meteora round-trip gas; calibrate after 1 real deploy+close'
A_GAS_NEW = A_GAS + '''
const SWAP_SLIP_CAP   = 0.20;   // max modeled slippage 20%
const SWAP_LIQ_FACTOR = 0.011;  // calibrated to live SPCX: ~$26 swap / $48K TVL -> ~5% slip
const SWAP_GAS_USD    = 0.10;   // jupiter swap gas/fee floor'''

A_NETG = 'const netG = (p) => (p.net_pnl || 0) - gasUsd(p);'
A_NETG_NEW = '''// Swap slippage — positions holding base token must swap it back to SOL on close.
// Paper sim ignores this; modeled here. Thin pools (low TVL) = big slippage.
const swapSlipUsd = (p) => {
  const lo = p.lower_price, hi = p.upper_price, px = p.last_price;
  if (!lo || !hi || !px || hi <= lo) return 0;
  const pc = Math.max(lo, Math.min(hi, px));
  const yFrac = (Math.sqrt(pc) - Math.sqrt(lo)) / (Math.sqrt(hi) - Math.sqrt(lo));
  const xFrac = 1 - yFrac;                                   // base-token fraction at close
  const posValue = (p.deposit_amount || 0) + (p.net_pnl || 0);
  const swapUsd = posValue * xFrac;                          // token value to swap -> SOL
  if (swapUsd <= 0.01) return 0;
  const numBins = (p.upper_bin_id - p.lower_bin_id + 1) || 1;
  const tvl = (p.avg_existing_bin_tvl || 0) * numBins;
  if (tvl <= 0) return SWAP_GAS_USD;
  const slipPct = Math.min(SWAP_SLIP_CAP, swapUsd / (tvl * SWAP_LIQ_FACTOR));
  return swapUsd * slipPct + SWAP_GAS_USD;
};
const netG = (p) => (p.net_pnl || 0) - gasUsd(p) - swapSlipUsd(p);'''

A_TOT = 'const totalGasUsd = sum(closed, gasUsd);'
A_TOT_NEW = 'const totalGasUsd = sum(closed, gasUsd);\nconst totalSlipUsd = sum(closed, swapSlipUsd);'

A_DISP = 'console.log(`  Gross PnL: $${f(grossPnlUsd)} · Gas: -$${totalGasUsd.toFixed(2)} (@${GAS_PER_TRADE_SOL} SOL/trade)`);'
A_DISP_NEW = 'console.log(`  Gross PnL: $${f(grossPnlUsd)} · Gas: -$${totalGasUsd.toFixed(2)} · Swap slip: -$${totalSlipUsd.toFixed(2)}`);'

for path in STATS_PATHS:
    s = open(path).read()
    for a, _ in [(A_GAS, 1), (A_NETG, 1), (A_TOT, 1), (A_DISP, 1)]:
        assert a in s, f"anchor missing in {path}: {a[:40]}"
    s = s.replace(A_GAS, A_GAS_NEW, 1).replace(A_NETG, A_NETG_NEW, 1)
    s = s.replace(A_TOT, A_TOT_NEW, 1).replace(A_DISP, A_DISP_NEW, 1)
    open(path, "w").write(s)
    print(f"  slippage model added: {path}")

# netpnl baseline (account for Indodax deposit)
np = "/opt/meridian/netpnl.py"
n = open(np).read()
old = "BASELINE_SOL = 0.323400177   # wallet saat pertama LIVE (2026-06-15)"
new = "BASELINE_SOL = 1.048638      # 0.3234 first-live + 0.725 deposit Indodax (2026-06-15)"
assert old in n, "netpnl baseline anchor missing"
open(np, "w").write(n.replace(old, new, 1))
print("  netpnl.py baseline -> 1.0486 (incl deposit)")
print("Done.")
