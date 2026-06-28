// Deep analysis of 41 closed paper trades
import fs from 'fs';

const d = JSON.parse(fs.readFileSync('./analysis_vps/paper-positions.json', 'utf8'));
const all = Object.values(d.positions);
const closed = all.filter(p => p.status === 'closed');
const open = all.filter(p => p.status !== 'closed');

console.log('='.repeat(70));
console.log('OVERVIEW');
console.log('='.repeat(70));
console.log(`Total: ${all.length} | Closed: ${closed.length} | Open: ${open.length}`);

const wins = closed.filter(p => p.net_pnl > 0);
const losses = closed.filter(p => p.net_pnl <= 0);
const totalPnl = closed.reduce((s, p) => s + p.net_pnl, 0);
const totalFees = closed.reduce((s, p) => s + p.fees_earned, 0);
const totalIl = closed.reduce((s, p) => s + p.il_usd, 0);

console.log(`W/L: ${wins.length}/${losses.length} | WR: ${(wins.length/closed.length*100).toFixed(1)}%`);
console.log(`Total PnL: $${totalPnl.toFixed(2)} | Fees: $${totalFees.toFixed(2)} | IL: $${totalIl.toFixed(2)}`);
console.log(`Fee/IL ratio: ${(totalFees/Math.abs(totalIl)).toFixed(2)}x`);

// === EXIT REASONS ===
console.log('\n' + '='.repeat(70));
console.log('EXIT REASON BREAKDOWN');
console.log('='.repeat(70));
const exitStats = {};
for (const p of closed) {
  const r = p.close_reason || 'unknown';
  if (!exitStats[r]) exitStats[r] = { count: 0, pnl: 0, fees: 0, il: 0 };
  exitStats[r].count++;
  exitStats[r].pnl += p.net_pnl;
  exitStats[r].fees += p.fees_earned;
  exitStats[r].il += p.il_usd;
}
for (const [r, s] of Object.entries(exitStats).sort((a,b) => b[1].count - a[1].count)) {
  console.log(`${r.padEnd(30)} n=${String(s.count).padStart(3)} | avg PnL ${(s.pnl/s.count).toFixed(3)} | total ${s.pnl.toFixed(2)} | fees ${s.fees.toFixed(2)} | IL ${s.il.toFixed(2)}`);
}

// === HOLD TIME ANALYSIS ===
console.log('\n' + '='.repeat(70));
console.log('HOLD TIME (minutes)');
console.log('='.repeat(70));
const holdTimes = closed.map(p => {
  const open = new Date(p.opened_at).getTime();
  const close = new Date(p.closed_at).getTime();
  return { ...p, hold_min: (close - open) / 60000 };
});
const bins = [0, 10, 20, 30, 60, 120, 240, 480, 1440];
for (let i = 0; i < bins.length - 1; i++) {
  const lo = bins[i], hi = bins[i+1];
  const inBin = holdTimes.filter(p => p.hold_min >= lo && p.hold_min < hi);
  if (inBin.length === 0) continue;
  const wr = inBin.filter(p => p.net_pnl > 0).length / inBin.length * 100;
  const avgPnl = inBin.reduce((s,p) => s + p.net_pnl, 0) / inBin.length;
  const avgFees = inBin.reduce((s,p) => s + p.fees_earned, 0) / inBin.length;
  console.log(`${String(lo).padStart(4)}-${String(hi).padStart(4)} min: n=${String(inBin.length).padStart(3)} | WR ${wr.toFixed(0)}% | avg PnL ${avgPnl.toFixed(3)} | avg fees ${avgFees.toFixed(3)}`);
}
const winners = holdTimes.filter(p => p.net_pnl > 0);
const losers = holdTimes.filter(p => p.net_pnl <= 0);
console.log(`Winners avg hold: ${(winners.reduce((s,p)=>s+p.hold_min,0)/winners.length).toFixed(1)} min`);
console.log(`Losers avg hold:  ${(losers.reduce((s,p)=>s+p.hold_min,0)/losers.length).toFixed(1)} min`);

// === OOR RATE BY HOLD TIME ===
console.log('\n' + '='.repeat(70));
console.log('OOR QUICKLY? (% of positions that OOR-d within X min)');
console.log('='.repeat(70));
for (const threshold of [5, 10, 15, 20, 30, 60]) {
  const oorQuick = closed.filter(p => p.close_reason && p.close_reason.includes('OOR') && p.hold_min < threshold).length;
  const totalOor = closed.filter(p => p.close_reason && p.close_reason.includes('OOR')).length;
  console.log(`OOR exits under ${threshold} min: ${oorQuick}/${totalOor} (${(oorQuick/totalOor*100).toFixed(0)}%)`);
}

// === RANGE SIZE IMPACT ===
console.log('\n' + '='.repeat(70));
console.log('RANGE WIDTH (% above entry to upper, % below entry to lower)');
console.log('='.repeat(70));
const withRange = closed.filter(p => p.entry_price && p.lower_price && p.upper_price).map(p => {
  const rangeDown = (p.entry_price - p.lower_price) / p.entry_price * 100;
  const rangeUp = (p.upper_price - p.entry_price) / p.entry_price * 100;
  return { ...p, rangeDown, rangeUp, totalRange: rangeDown + rangeUp };
});
const rangeBins = [0, 5, 10, 15, 20, 30, 50, 100];
for (let i = 0; i < rangeBins.length - 1; i++) {
  const lo = rangeBins[i], hi = rangeBins[i+1];
  const inBin = withRange.filter(p => p.totalRange >= lo && p.totalRange < hi);
  if (inBin.length === 0) continue;
  const wr = inBin.filter(p => p.net_pnl > 0).length / inBin.length * 100;
  const avgPnl = inBin.reduce((s,p) => s + p.net_pnl, 0) / inBin.length;
  console.log(`Range ${lo}-${hi}%: n=${String(inBin.length).padStart(3)} | WR ${wr.toFixed(0)}% | avg PnL ${avgPnl.toFixed(3)}`);
}

// === POSITION SIZE vs OUTCOME ===
console.log('\n' + '='.repeat(70));
console.log('DEPOSIT SIZE (SOL) vs OUTCOME');
console.log('='.repeat(70));
const sizes = closed.map(p => p.deposit_amount).sort((a,b) => a-b);
const minS = sizes[0], maxS = sizes[sizes.length-1];
console.log(`Size range: ${minS.toFixed(2)} - ${maxS.toFixed(2)} SOL`);

// === STRATEGY TYPE ===
console.log('\n' + '='.repeat(70));
console.log('STRATEGY TYPE BREAKDOWN');
console.log('='.repeat(70));
const stratStats = {};
for (const p of closed) {
  const s = p.strategy_type || 'unknown';
  if (!stratStats[s]) stratStats[s] = { count: 0, pnl: 0, wins: 0 };
  stratStats[s].count++;
  stratStats[s].pnl += p.net_pnl;
  if (p.net_pnl > 0) stratStats[s].wins++;
}
for (const [s, st] of Object.entries(stratStats)) {
  console.log(`${s.padEnd(20)} n=${String(st.count).padStart(3)} | WR ${(st.wins/st.count*100).toFixed(0)}% | total PnL ${st.pnl.toFixed(2)} | avg ${(st.pnl/st.count).toFixed(3)}`);
}

// === POOL CONCENTRATION ===
console.log('\n' + '='.repeat(70));
console.log('TOP POOLS BY FREQUENCY');
console.log('='.repeat(70));
const poolStats = {};
for (const p of closed) {
  const k = p.pair || 'unknown';
  if (!poolStats[k]) poolStats[k] = { count: 0, pnl: 0, fees: 0, wins: 0 };
  poolStats[k].count++;
  poolStats[k].pnl += p.net_pnl;
  poolStats[k].fees += p.fees_earned;
  if (p.net_pnl > 0) poolStats[k].wins++;
}
const top = Object.entries(poolStats).sort((a,b) => b[1].count - a[1].count).slice(0, 15);
for (const [k, s] of top) {
  console.log(`${k.padEnd(30)} n=${String(s.count).padStart(3)} | WR ${(s.wins/s.count*100).toFixed(0)}% | PnL ${s.pnl.toFixed(2)} | fees ${s.fees.toFixed(2)}`);
}

// === PEAK PNL vs ACTUAL PNL (left money on table?) ===
console.log('\n' + '='.repeat(70));
console.log('PEAK vs CLOSED — how much PnL left on the table');
console.log('='.repeat(70));
const withPeak = closed.filter(p => typeof p.peak_pnl_pct === 'number');
const left = withPeak.map(p => ({
  ...p,
  leftOnTable: p.peak_pnl_pct - (p.net_pnl / (p.initial_x_usd + p.initial_y_usd) * 100)
})).filter(p => Number.isFinite(p.leftOnTable));
const avgLeft = left.reduce((s,p) => s + p.leftOnTable, 0) / left.length;
const peakWinMissed = left.filter(p => p.peak_pnl_pct >= 2 && p.net_pnl <= 0).length;
const peakWinReduced = left.filter(p => p.peak_pnl_pct >= 3 && Math.abs(p.leftOnTable) > 1).length;
console.log(`Avg "left on table" (peak_pnl - closed_pnl): ${avgLeft.toFixed(2)}%`);
console.log(`Positions that hit ≥2% peak then closed negative: ${peakWinMissed}`);
console.log(`Positions that hit ≥3% peak then closed >1% below peak: ${peakWinReduced}`);

// === HOUR OF DAY (when do wins/losses happen) ===
console.log('\n' + '='.repeat(70));
console.log('HOUR OF DAY (UTC) — entry hour distribution');
console.log('='.repeat(70));
const hourStats = {};
for (const p of closed) {
  const h = new Date(p.opened_at).getUTCHours();
  if (!hourStats[h]) hourStats[h] = { count: 0, pnl: 0, wins: 0 };
  hourStats[h].count++;
  hourStats[h].pnl += p.net_pnl;
  if (p.net_pnl > 0) hourStats[h].wins++;
}
for (let h = 0; h < 24; h++) {
  const s = hourStats[h];
  if (!s) continue;
  const bar = '█'.repeat(Math.min(20, Math.abs(s.pnl)*2));
  const sign = s.pnl >= 0 ? '+' : '';
  console.log(`${String(h).padStart(2)}h: n=${String(s.count).padStart(2)} | WR ${(s.wins/s.count*100).toFixed(0)}% | PnL ${sign}${s.pnl.toFixed(2)} ${bar}`);
}

// === CANDLES IN RANGE ===
console.log('\n' + '='.repeat(70));
console.log('CANDLES IN RANGE (% time in range)');
console.log('='.repeat(70));
const rangeStats = {};
for (const p of closed) {
  const c = p.candles_total;
  if (!c) continue;
  const pct = p.candles_in_range / c * 100;
  const bucket = Math.floor(pct / 20) * 20;
  if (!rangeStats[bucket]) rangeStats[bucket] = { count: 0, pnl: 0, wins: 0 };
  rangeStats[bucket].count++;
  rangeStats[bucket].pnl += p.net_pnl;
  if (p.net_pnl > 0) rangeStats[bucket].wins++;
}
for (const [b, s] of Object.entries(rangeStats).sort((a,b) => Number(a[0]) - Number(b[0]))) {
  console.log(`${b}-${Number(b)+20}% in range: n=${String(s.count).padStart(3)} | WR ${(s.wins/s.count*100).toFixed(0)}% | PnL ${s.pnl.toFixed(2)}`);
}

// === BIGGEST LESSONS ===
console.log('\n' + '='.repeat(70));
console.log('TOP 5 BEST & TOP 5 WORST TRADES');
console.log('='.repeat(70));
const sorted = [...closed].sort((a,b) => b.net_pnl - a.net_pnl);
console.log('\n--- BEST ---');
for (const p of sorted.slice(0, 5)) {
  const hold = (new Date(p.closed_at) - new Date(p.opened_at)) / 60000;
  console.log(`${p.pair.padEnd(28)} hold ${hold.toFixed(0)}m | PnL +${p.net_pnl.toFixed(3)} | fees ${p.fees_earned.toFixed(3)} | close: ${p.close_reason} | peak ${(p.peak_pnl_pct||0).toFixed(1)}%`);
}
console.log('\n--- WORST ---');
for (const p of sorted.slice(-5).reverse()) {
  const hold = (new Date(p.closed_at) - new Date(p.opened_at)) / 60000;
  console.log(`${p.pair.padEnd(28)} hold ${hold.toFixed(0)}m | PnL ${p.net_pnl.toFixed(3)} | fees ${p.fees_earned.toFixed(3)} | close: ${p.close_reason} | peak ${(p.peak_pnl_pct||0).toFixed(1)}%`);
}
