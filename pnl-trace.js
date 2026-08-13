import fs from "fs";
import path from "path";
import { repoPath } from "./repo-root.js";

/**
 * Per-tick PnL trace.
 *
 * The normal log only records PnL when a peak *rises* — so the way down, which
 * is exactly where exits are decided, leaves no trace at all. That gap is why
 * questions like "is confirmTicks=2 right?", "what should trailingDropPct be?"
 * and "are the fast-path thresholds sensible?" can only be guessed at: the
 * finest public candle data is 1 minute, 30x coarser than a 2s tick, and
 * reconstructing a busy pool from chain costs tens of thousands of signature
 * fetches per case.
 *
 * This writes one JSON object per position per poll tick to its own daily file,
 * so the answers can come from measurement in a few days instead.
 *
 * Deliberately separate from logger.js: this is high volume (~15k lines/day at
 * a 2s tick and the observed ~36% duty cycle, roughly 2MB/day), machine-read
 * rather than human-read, and must never drown out the operational log or
 * journald.
 */

const TRACE_DIR = repoPath("logs/pnl-trace");
const RETENTION_DAYS = 30;

let _ready = false;
let _lastPruneDay = null;

function ensureDir() {
  if (_ready) return;
  fs.mkdirSync(TRACE_DIR, { recursive: true });
  _ready = true;
}

/** Drop trace files past the retention window — once per day, not per tick. */
function pruneOldFiles(today) {
  if (_lastPruneDay === today) return;
  _lastPruneDay = today;
  try {
    const cutoff = Date.now() - RETENTION_DAYS * 86400_000;
    for (const name of fs.readdirSync(TRACE_DIR)) {
      const m = name.match(/^pnl-(\d{4}-\d{2}-\d{2})\.jsonl$/);
      if (!m) continue;
      if (new Date(m[1]).getTime() < cutoff) {
        fs.unlinkSync(path.join(TRACE_DIR, name));
      }
    }
  } catch { /* pruning is best-effort; never break the poller over it */ }
}

/**
 * Append one tick sample.
 *
 * Never throws: the poller is the exit path, and losing a trace line must never
 * be able to stop a position from closing.
 *
 * @param {Object} p        position data from the poller
 * @param {Object} tracked  matching entry from state.json (peak, trailing flag)
 */
export function tracePnlTick(p, tracked) {
  try {
    ensureDir();
    const ts = new Date().toISOString();
    const day = ts.slice(0, 10);
    pruneOldFiles(day);

    const row = {
      t: ts,
      pos: p.position,
      pair: p.pair ?? null,
      pnl: p.pnl_pct ?? null,
      peak: tracked?.peak_pnl_pct ?? null,
      trail: !!tracked?.trailing_active,
      inr: p.in_range ?? null,
      // Both stop loss and trailing TP are gated behind !pnl_pct_suspicious, so
      // a run of these marks a window where the position had no exit cover.
      susp: !!p.pnl_pct_suspicious,
      fee: p.unclaimed_fees_usd ?? null,
      bin: p.active_bin ?? null,
      lo: p.lower_bin ?? null,
      hi: p.upper_bin ?? null,
      age: p.age_minutes ?? null,
    };

    fs.appendFileSync(path.join(TRACE_DIR, `pnl-${day}.jsonl`), JSON.stringify(row) + "\n");
  } catch { /* tracing is never worth an exception here */ }
}
