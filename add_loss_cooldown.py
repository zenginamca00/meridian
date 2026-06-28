# Add "2 consecutive losses on a token -> cooldown" to pool-memory.js (all instances).
ANCHOR = "  if (config.management.repeatDeployCooldownEnabled) {"

BLOCK = '''  // 2 consecutive losses on this token -> cooldown (stop feeding a token that keeps losing)
  const lossTriggerCount = Math.max(1, Number(config.management.lossCooldownTriggerCount ?? 2));
  const lossCooldownHours = Math.max(0, Number(config.management.lossCooldownHours ?? 12));
  const recentLossDeploys = entry.deploys.filter((d) => d.pnl_pct != null).slice(-lossTriggerCount);
  const repeatedLosses =
    lossCooldownHours > 0 &&
    recentLossDeploys.length >= lossTriggerCount &&
    recentLossDeploys.every((d) => d.pnl_pct < 0);
  if (repeatedLosses) {
    const reason = `${lossTriggerCount} consecutive losses`;
    const poolCd = setPoolCooldown(entry, lossCooldownHours, reason);
    const mintCd = setBaseMintCooldown(db, entry.base_mint, lossCooldownHours, reason);
    log("pool-memory", `Loss cooldown: ${entry.name} -> ${poolCd} (${reason})`);
    if (entry.base_mint && mintCd) {
      log("pool-memory", `Base mint loss-cooldown ${entry.base_mint.slice(0, 8)} -> ${mintCd} (${reason})`);
    }
  }

'''

PATHS = [
    "/opt/meridian/pool-memory.js",
    "/opt/meridian-runner/pool-memory.js",
    "/opt/meridian-entrytest/pool-memory.js",
]
for p in PATHS:
    s = open(p).read()
    if "consecutive losses" in s:
        print("  already patched:", p); continue
    assert ANCHOR in s, "anchor not found in " + p
    s = s.replace(ANCHOR, BLOCK + ANCHOR, 1)
    open(p, "w").write(s)
    print("  patched:", p)
