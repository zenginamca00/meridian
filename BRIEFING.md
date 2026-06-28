# MERIDIAN — FULL BRIEFING
> Last updated: 2026-06-10 | Branch: simulator-paper | Mode: DRY_RUN (paper trading)

---

## 1. APA INI

**Meridian** adalah autonomous LP (Liquidity Provider) bot untuk Meteora DLMM pools di Solana. Bot ini otomatis:
- **Screening** — cari pool trending tiap 30 menit, filter berdasarkan fee/TVL, holder, organic score, mcap
- **Deploy** — masuk posisi LP dengan SOL, tentukan range bins, strategi curve
- **Manage** — pantau posisi tiap 10 menit, exit kalau OOR / TP / stale
- **Learn** (parsial) — catat performa ke lessons.json, secara teori evolve threshold

Sekarang berjalan dalam **paper trading mode** (`DRY_RUN=true`) — tidak ada transaksi on-chain, semua simulasi berdasarkan candle data Meteora API.

---

## 2. VPS & AKSES

```
Provider : DigitalOcean (Ubuntu)
IP       : 129.212.239.227
User     : root
SSH      : ssh -i ~/.ssh/id_ed25519_trading root@129.212.239.227
SCP      : scp -i ~/.ssh/id_ed25519_trading <local> root@129.212.239.227:/opt/meridian/<file>
Dir      : /opt/meridian/
Service  : systemctl [status|restart|stop] meridian
Node     : v20.20.2
```

**Check cepat apakah bot hidup:**
```bash
ssh -i ~/.ssh/id_ed25519_trading root@129.212.239.227 \
  "systemctl is-active meridian && journalctl -u meridian -n 5 --no-pager"
```

**Local SSH key:** `C:\Users\ADHYAKSA RAHMAN\.ssh\id_ed25519_trading`

---

## 3. ARSITEKTUR FILE

```
index.js           — Entry point: REPL + cron (management 10m, screening 30m, paper-tick 5m)
agent.js           — ReAct loop: LLM → tool call → repeat (max 15 rounds)
config.js          — Load user-config.json + .env → expose config object
prompt.js          — Build system prompt per role (SCREENER / MANAGER / GENERAL)
paper-positions.js — Paper position tracker: open/tick/exit/stats (paper-positions.json)
pool-memory.js     — Per-pool deploy history + cooldown (pool-memory.json)
lessons.js         — Learning engine: recordPerformance() → lessons.json
state.js           — Real position registry (state.json)
telegram.js        — Bot polling + notifications

tools/
  executor.js      — Tool dispatch: safety checks + paper bridge (dry_run → paper position)
  dlmm.js          — Meteora DLMM SDK: deploy/close/claim/positions/PnL
  screening.js     — Pool discovery (Meteora API) + condensePool()
  wallet.js        — SOL/token balances (Helius) + Jupiter swap
  token.js         — Token info/holders/narrative
```

**Alur kerja utama:**
```
Cron 30m → SCREENER agent
  → getTopCandidates() [Meteora API, filter by config]
  → LLM evaluate candidates (narrative, metrics, entry timing)
  → deploy_position() [safety checks in executor.js]
  → DRY_RUN: executor bridges → openPaperPosition()
  → Telegram notify

Cron 5m → tickPaperPositions() + evaluatePaperExits()
  → Fetch new 5m candles per position
  → Update fees/IL/PnL
  → Check exit rules (OOR / TP / SL / trailing / stale)
  → Auto-close → recordPoolDeploy() + recordPerformance()

Cron 10m → MANAGER agent
  → Review open positions
  → Decide: hold / close / claim fees
```

---

## 4. CONFIG AKTIF (`user-config.json`)

```
Model            : MiniMax-M3 (semua role: management, screening, general)
DRY_RUN          : true (paper trading)
PAPER_WALLET_SOL : 1.7 SOL (simulated balance)

Strategy         : curve (concentrated at current price)
Deploy per posisi: 0.6 SOL (floor), max posisi sekaligus: 2
Range            : bins_below = round(35 + (volatility/5) * 34), bins_above = sama
                   → range 35–69 bins dari active price ke bawah, mirrored atas

Screening (30m timeframe):
  minTvl               : $10,000
  maxTvl               : $80,000
  minVolume            : $5,000
  minOrganic           : 60%
  minHolders           : 500
  minMcap              : $150,000
  maxMcap              : $5,000,000
  minFeeActiveTvlRatio : 0.3%
  maxBotHoldersPct     : 40%

Exit rules:
  outOfRangeWaitMinutes : 20 menit OOR → close
  takeProfitPct         : 5%
  stopLossPct           : -20% (longstop, jarang trigger)
  trailingTakeProfit    : true, trigger 4%, drop 3%
  staleCloseMinutes     : 120 menit
  staleMaxInRangePct    : 40%  ← dinaikkan dari default 25

Cooldown:
  repeatDeployCooldownHours : 24 jam  ← dinaikkan dari default 12
```

---

## 5. CARA CEK STATUS & PAPER TRADE

### Stats lengkap semua trade
```bash
ssh -i ~/.ssh/id_ed25519_trading root@129.212.239.227 "python3 /tmp/paperstats.py"
```

### Log real-time
```bash
ssh -i ~/.ssh/id_ed25519_trading root@129.212.239.227 \
  "tail -f /opt/meridian/logs/agent-$(date +%Y-%m-%d).log | grep -E 'paper_sim|SCREEN|DEPLOY|CLOSE'"
```

### Decision log (kenapa no-deploy tiap siklus)
```bash
ssh -i ~/.ssh/id_ed25519_trading root@129.212.239.227 \
  "python3 -c \"import json; d=json.load(open('/opt/meridian/decision-log.json')); [print(e.get('timestamp','')[:16], '|', str(e.get('reason',''))[:120]) for e in d[-20:]]\""
```

### Paper positions JSON langsung
```bash
ssh -i ~/.ssh/id_ed25519_trading root@129.212.239.227 \
  "cat /opt/meridian/paper-positions.json | python3 -c 'import json,sys; d=json.load(sys.stdin); opens=[p for p in d[\"positions\"].values() if p[\"status\"]!=\"closed\"]; print(len(opens),\"open\"); [print(p[\"pair\"],p[\"net_pnl\"]) for p in opens]'"
```

### Telegram
Bot posting **hourly report** ke group Telegram dengan posisi open, gate validation, dan metrics ringkas.

---

## 6. PAPER TRADE HISTORY (per 10 Jun 2026, ~17:00 UTC)

```
Periode      : 3 Jun 2026 – sekarang (7 hari)
Total trades : 43 (41 closed, 2 open)
W/L          : 26 / 15  —  WR 63.4%
Avg Win      : +1.96%
Avg Loss     : -0.85%
Profit Factor: 4.15  (gate ≥1.2 → PASS)
Net PnL      : $+15.68  (dari total deposit ~$1,607)
Total Fees   : $38.44
Fee/IL ratio : ~2.2×  (target 3–5×, masih marginal)
```

### Exit breakdown
| Tipe | Jumlah | Rata-rata |
|------|--------|-----------|
| OOR 20 menit | 33 | +0.73% |
| Take Profit 5% | 2 | +5.18% |
| Stale dead-money | 4 | -0.05% |
| Stop Loss | 0 | — |

### Trade highlight
- **Best:** Magpie-SOL +6.85%, HUNTER-SOL +5.24%, 清正-SOL +5.06%
- **Worst:** PATCHA-SOL -3.27% (fade entry, OOR dalam 39 menit)
- **TP hits:** 3 kali 5% TP triggered — positif, trailing TP belum pernah aktif (butuh peak ≥4% dulu)

### Pool yang sering dientry (pre-fix, sebelum cooldown aktif)
- Magpie-SOL: 5× entry, HUNTER-SOL: 4×, HONTER-SOL: 4×

---

## 7. PERUBAHAN YANG SUDAH DIBUAT (10 Jun 2026)

### Tier 1 — Bug fix yang bikin bot berhenti dagang

#### T1-A: Single-candidate rule (`prompt.js`)
- **Masalah:** Rule lama butuh smart-wallet confirmation untuk deploy 1 kandidat. `smart-wallets.json` kosong → kondisi mustahil terpenuhi → 16-24% siklus di-skip padahal kandidat bagus
- **Fix:** Smart wallet sekarang jadi **bonus, bukan syarat**. Deploy kalau narrative spesifik + metrik bersih. "0 smart wallets" bukan alasan skip.

#### T1-B: Wallet 0 SOL di dry-run (`tools/wallet.js`)
- **Masalah:** Wallet on-chain 0 SOL, LLM baca "no capital", skip ~16% siklus
- **Fix:** Fungsi `applyPaperWalletSol()` inject `PAPER_WALLET_SOL=1.7` ke semua return path `getWalletBalances()` saat `DRY_RUN=true`

### Tier 2 — Pertebal edge per-trade

#### T2-A: Entry timing guidance (`prompt.js`)
- Tambah section **ENTRY TIMING** di screener prompt
- `fee_change_pct > 0 && volume_change_pct > 0` = pool pre-peak → prioritasin
- `fee_change_pct < 0 && volume_change_pct < 0` = pool post-peak → hindari
- Bukan hard filter — tetap masuk kalau sole candidate dengan metrik bersih

#### T2-B: Cooldown pool re-entry (`user-config.json`)
- `repeatDeployCooldownHours`: null → **24 jam** (dari default 12)
- Setelah 3× deploy ke pool yang sama, istirahat 24 jam
- Tujuan: stop pola Magpie 5×, HUNTER 4× (re-entry ke pool yang sudah declining)

#### T2-C: Faster dead-money cull (`user-config.json`)
- `staleMaxInRangePct`: null → **40%** (dari default 25%)
- Posisi in-range <40% selama ≥120 menit langsung di-close
- Frees capital lebih cepat untuk redeployment

### Bug fix post-deployment (sore 10 Jun)

#### FIX-C: `base_mint` hilang dari paper bridge (`tools/dlmm.js` line 695)
- **Masalah:** `would_deploy` object tidak include `base_mint` → semua paper position tersimpan `base_mint: null` → dedup by token tidak pernah work → bisa masuk 2 mint kembar sekaligus (PVP twin)
- **Fix:** Tambah `base_mint: baseMint` ke `would_deploy`

#### FIX-D: Cooldown & lessons mati di paper mode (`paper-positions.js`)
- **Masalah:** `recordPoolDeploy()` dan `recordPerformance()` hanya dipanggil dari `dlmm.js` (real close), tidak dari `evaluatePaperExits()` → `pool-memory.json` tidak pernah ditulis → cooldown 24h tidak pernah trigger → learning loop tidak belajar dari 41 paper trades
- **Fix:** Import + call kedua fungsi di dalam `evaluatePaperExits()` setelah setiap close (fire-and-forget)

---

## 8. KNOWN ISSUES / YANG BELUM DIFIX

| Issue | Dampak | Catatan |
|-------|--------|---------|
| MiniMax M3 "no tool call" ~10–35% siklus | Bot gagal execute, hanya narasi | User pilih tetap MiniMax, bukan ganti ke DeepSeek |
| `fees_sol ≥ 30 SOL` threshold | Blok ~19% siklus di market sepi | User tidak minta ubah |
| `evolveThresholds()` di lessons.js key salah | Evolve `maxVolatility`/`minFeeTvlRatio` yang tidak ada di config → no-op | Bug dokumentasi, tidak urgent |
| `lpAgentRelayEnabled: true` | LPAgent server pernah 504 | Monitor saja |
| `pool-memory.json` belum ada | Dibuat otomatis saat exit pertama post-fix-D | Normal |

---

## 9. STRATEGI AKTIF — RINGKASAN

**Philosophy:** Fee farming via concentrated liquidity. Masuk pool yang lagi growing, farm fee selama harga stay in range, exit kalau OOR 20 menit (realokasi ke peluang lebih baik).

**Strategy shape — `curve`:** Liquidity terkonsentrasi di tengah range (distribusi normal). Lebih banyak fee saat harga di tengah, kurang efisien kalau harga langsung ke ujung range.

**Sizing:** 0.6 SOL per posisi, max 2 sekaligus. Dengan simulated wallet 1.7 SOL → 1.2 SOL deployed, 0.5 SOL reserve gas + buffer.

**Kenapa OOR dominasi exits (33/41):** DLMM pools token meme sangat volatile — 30m timeframe sering spike keluar range dalam hitungan jam. Normal dan acceptable selama fees > IL. Fee/IL saat ini ~2.2× — positif tapi tipis. Target 3–5×.

**Yang sedang diupayakan:** Entry lebih awal di pool lifecycle (pre-peak, fee sedang naik). Data `fee_change_pct` dan `volume_change_pct` sudah tersedia di screening output, LLM diarahkan memprioritaskan yang positif.

---

## 10. NEXT CHECKPOINT

Pantau setelah **~15–20 trade baru** (estimasi 2–3 hari):

1. **Deploy frequency** — slot kosong terisi dalam <30 menit? (harusnya ya setelah T1 fix)
2. **Pool repeat cooldown** — pool yang sama max 3× dalam seminggu? (aktif setelah FIX-D)
3. **base_mint dedup** — tidak ada lagi 2 posisi dengan ticker sama beda mint bersamaan
4. **Fee/IL ratio** — naik dari 2.2× ke arah 3× setelah entry timing guidance berjalan?
5. **lessons.json** — sudah ada isinya? Berarti learning loop hidup

---

## 11. QUICK REFERENCE COMMANDS

```bash
# Status service
ssh -i ~/.ssh/id_ed25519_trading root@129.212.239.227 "systemctl status meridian --no-pager | head -20"

# Paper stats
ssh -i ~/.ssh/id_ed25519_trading root@129.212.239.227 "python3 /tmp/paperstats.py"

# Restart
ssh -i ~/.ssh/id_ed25519_trading root@129.212.239.227 "systemctl restart meridian"

# Live log
ssh -i ~/.ssh/id_ed25519_trading root@129.212.239.227 \
  "tail -f /opt/meridian/logs/agent-$(date +%Y-%m-%d).log"

# Deploy file ke VPS
scp -i ~/.ssh/id_ed25519_trading "D:\1. Ainggg\Projects\meridian\<file>" \
  root@129.212.239.227:/opt/meridian/<file>

# Edit config langsung di VPS
ssh -i ~/.ssh/id_ed25519_trading root@129.212.239.227 "nano /opt/meridian/user-config.json"
```
