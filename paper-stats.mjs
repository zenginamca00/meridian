#!/usr/bin/env node
/**
 * paper-stats.mjs — Validation gate for the paper simulator.
 * All monetary values in SOL (◎). Reads paper-positions.json.
 * Run anytime: `node paper-stats.mjs`
 */
import { readFileSync, existsSync } from "fs";
import { fileURLToPath } from "url";
import path from "path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FILE = path.join(__dirname, "paper-positions.json");

// ── Gates ────────────────────────────────────────────────────────
const GATE_SAMPLE = 15;
const GATE_PF     = 1.2;
const GATE_WR     = 15; // %

// ── Cost model (SOL) ─────────────────────────────────────────────
const GAS_SOL       = 0.006;  // non-refundable Meteora round-trip gas
const SWAP_SLIP_CAP = 0.20;   // max modeled slippage 20%
const SWAP_LIQ_FAC  = 0.011;  // calibrated to SPCX live
const SWAP_GAS_SOL  = 0.001;  // jupiter swap gas floor in SOL

if (!existsSync(FILE)) {
  console.log("No paper-positions.json yet — run the agent (npm start) first.");
  process.exit(0);
}

const state = JSON.parse(readFileSync(FILE, "utf8"));
const all    = Object.values(state.positions || {});
const open   = all.filter((p) => p.status === "open");
const closed = all.filter((p) => p.status === "closed");

// ── Helpers ───────────────────────────────────────────────────────
// Derive SOL price from stored deposit fields (set at open time)
const solPrice  = (p) => (p.deposit_sol > 0 && p.deposit_amount > 0)
  ? p.deposit_amount / p.deposit_sol : 150;
const toSol     = (p, usd) => usd / solPrice(p);

const pnlSol    = (p) => toSol(p, p.net_pnl    || 0);
const feesSol   = (p) => toSol(p, p.fees_earned || 0);
const ilSol     = (p) => toSol(p, p.il_usd      || 0);

const gasSol    = (_p) => GAS_SOL; // fixed per trade (SOL)

function swapSlipSol(p) {
  const lo = p.lower_price, hi = p.upper_price, px = p.last_price;
  if (!lo || !hi || !px || hi <= lo) return 0;
  const pc = Math.max(lo, Math.min(hi, px));
  const yFrac = (Math.sqrt(pc) - Math.sqrt(lo)) / (Math.sqrt(hi) - Math.sqrt(lo));
  const xFrac = 1 - yFrac;
  // position value in SOL
  const posValSol = (p.deposit_sol || 0) + pnlSol(p);
  const swapSol   = posValSol * xFrac;
  if (swapSol <= 0.0001) return 0;
  // tvl in USD → convert denominator to SOL for consistent units
  const bins   = (p.upper_bin_id - p.lower_bin_id + 1) || 1;
  const tvlUsd = (p.avg_existing_bin_tvl || 0) * bins;
  const tvlSol = tvlUsd > 0 ? tvlUsd / solPrice(p) : 0;
  if (tvlSol <= 0) return SWAP_GAS_SOL;
  const slipPct = Math.min(SWAP_SLIP_CAP, swapSol / (tvlSol * SWAP_LIQ_FAC));
  return swapSol * slipPct + SWAP_GAS_SOL;
}

const netG   = (p) => pnlSol(p) - gasSol(p) - swapSlipSol(p);
const pct    = (p) => (p.deposit_sol > 0) ? (netG(p)    / p.deposit_sol) * 100 : 0;
const gPct   = (p) => (p.deposit_sol > 0) ? (pnlSol(p)  / p.deposit_sol) * 100 : 0;

const wins   = closed.filter((p) => netG(p) > 0);
const losses = closed.filter((p) => netG(p) <= 0);
const sum    = (arr, f) => arr.reduce((a, x) => a + f(x), 0);

const grossWin  = sum(wins,   netG);
const grossLoss = Math.abs(sum(losses, netG));
const pf  = grossLoss > 0 ? grossWin / grossLoss : (grossWin > 0 ? Infinity : 0);
const wr  = closed.length ? (wins.length / closed.length) * 100 : 0;
const avgW = wins.length   ? sum(wins,   pct) / wins.length   : 0;
const avgL = losses.length ? sum(losses, pct) / losses.length : 0;

const netSol      = sum(closed, netG);
const grossSol    = sum(closed, pnlSol);
const totalGasSol = sum(closed, gasSol);
const totalSlipSol= sum(closed, swapSlipSol);
const totalFees   = sum(closed, feesSol);
const best  = closed.length ? Math.max(...closed.map(pct)) : 0;
const worst = closed.length ? Math.min(...closed.map(pct)) : 0;

// Exit category
const cat = (r) => {
  const s = String(r || "").toLowerCase();
  if (s.includes("stop loss"))  return "SL";
  if (s.includes("take profit"))return "TP";
  if (s.includes("trailing"))   return "TRAILING";
  if (s.includes("stale"))      return "STALE";
  if (s.includes("range"))      return "OOR";
  return "OTHER";
};
const exits = {};
for (const p of closed) {
  const c = cat(p.close_reason);
  exits[c] = exits[c] || { n: 0, sumPct: 0 };
  exits[c].n++;
  exits[c].sumPct += pct(p);
}

const pf_str = pf === Infinity ? "∞" : pf.toFixed(3);
const s  = (v) => (v >= 0 ? "+" : "") + v.toFixed(4); // SOL with sign
const sp = (v) => (v >= 0 ? "+" : "") + v.toFixed(2); // pct with sign

// ── Open positions ────────────────────────────────────────────────
if (open.length) {
  console.log(`\n🟢 OPEN POSITIONS (${open.length})\n${"─".repeat(40)}`);
  for (const p of open) {
    const inRange = p.candles_total > 0 ? (p.candles_in_range / p.candles_total) * 100 : 0;
    const ageMin  = Math.floor((Date.now() / 1000 - (p.entry_timestamp || 0)) / 60);
    const live    = p.last_price >= p.lower_price && p.last_price <= p.upper_price
      ? "IN RANGE" : "OUT OF RANGE";
    const dep     = p.deposit_sol ? `◎${p.deposit_sol.toFixed(3)}` : `$${p.deposit_amount}`;
    console.log(`  ${p.pair}  ${dep}  ${p.strategy_type}`);
    console.log(`    PnL: ◎${s(pnlSol(p))} (${sp(gPct(p))}%) | fees ◎${feesSol(p).toFixed(4)} | IL ◎${ilSol(p).toFixed(4)}`);
    console.log(`    peak: ${sp(p.peak_pnl_pct || 0)}% | in-range: ${inRange.toFixed(0)}% | now: ${live} | age: ${ageMin}m`);
  }
}

// ── Gate ──────────────────────────────────────────────────────────
console.log(`\n📊 PAPER VALIDATION GATE\n${"─".repeat(40)}`);
console.log(`Sample: ${closed.length} closed / ${open.length} open`);
console.log("");
console.log(`${closed.length >= GATE_SAMPLE ? "✅" : "❌"} Sample ${closed.length}/${GATE_SAMPLE}`);
console.log(`${pf >= GATE_PF      ? "✅" : "❌"} PF ${pf_str} (gate ≥${GATE_PF})`);
console.log(`${wr  >= GATE_WR     ? "✅" : "❌"} WR ${wr.toFixed(1)}% (gate ≥${GATE_WR}%)`);
console.log(`\nMetrics:`);
console.log(`  Win/Loss: ${wins.length} / ${losses.length}`);
console.log(`  Avg W: ${sp(avgW)}% · Avg L: ${sp(avgL)}%`);
console.log(`  Gross: ◎${s(grossSol)} · Gas: ◎-${totalGasSol.toFixed(4)} · Swap slip: ◎-${totalSlipSol.toFixed(4)}`);
console.log(`  NET  : ◎${s(netSol)} · Fees: ◎${totalFees.toFixed(4)}`);
console.log(`  Best: ${sp(best)}% · Worst: ${sp(worst)}%`);
console.log(`\nExit breakdown:`);
for (const [k, v] of Object.entries(exits)) {
  console.log(`  ${k}: ${v.n} · avg ${sp(v.sumPct / v.n)}%`);
}

const verdict = closed.length >= GATE_SAMPLE && pf >= GATE_PF && wr >= GATE_WR;
console.log(`\nVerdict: ${
  closed.length < GATE_SAMPLE
    ? `🟡 PENDING — need ${GATE_SAMPLE - closed.length} more trades`
    : verdict ? "🟢 PASS — edge confirmed" : "🔴 FAIL — strategy not profitable enough"
}`);
console.log("");
