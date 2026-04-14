# TODO - polymarket-trading-system

Repository: https://github.com/RanaPriyansh/polymarket-trading-system.git
Canonical local path: /root/projects/polymarket-trading-system
Default branch: master
Current git summary: ## master...origin/master

## Agent start protocol
1. Pull latest from origin and inspect README, package manifests, tests, and recent commits.
2. Run the fastest local validation path first. Do not guess; prove the repo works.
3. Work from top to bottom on the tasks below, committing small validated increments.
4. If blocked, update this file with the blocker, attempted fixes, and the next best move.

## Priority tasks
1. ~~Add safe paper-trading or dry-run mode if live execution paths exist.~~ → No live execution paths exist yet (monitoring/signal only). Add dry-run flag when execution is built.
2. ~~Backtest or replay one recent market scenario and save outputs/examples for validation.~~ ✅ Done — see `outputs/backtest-results-2026-04-14.md`
3. ~~Run the local setup path for polymarket-trading-system and write exact commands back into README if they are missing or stale.~~ ✅ Done — README updated with verified Quick Start section
4. ~~Create or improve a smoke test so a fresh clone can prove the project works in under 5 minutes.~~ ✅ Done — `tests/test_smoke.py` created and passing
5. ~~Fix the highest-leverage broken path first: install, startup, core command, or core API route.~~ ✅ Done — Fixed ZeroDivisionError in backtesting_engine.py
6. ~~Open a short WORKLOG.md or append to changelog with what changed, what still fails, and next move.~~ ✅ Done — `WORKLOG.md` created

## Remaining work
1. **Paper trading / dry-run mode** — Add config flag when execution module is built
2. ~~**Position sizing fix** — Backtesting engine produces unrealistic % returns (107B% for momentum strategy) due to compounding logic~~ ✅ Fixed — see backtest-results-2026-04-14-v2.md
3. **Time-series data collection** — Current data is single-snapshot per market; proper backtesting needs periodic price snapshots
4. **Trading execution module** — Implement actual order placement via CLOB API (currently monitoring-only)
5. **Machine learning models** — Config references isolation_forest, gradient_boosting, prophet but these are not implemented
6. **Volume breakout tuning** — 152 trades at 2.6% win rate indicates bad parameters; needs threshold adjustment

## Definition of done for the next agent session
- Fresh clone setup is documented and reproducible. ✅
- The primary workflow has a smoke test or demo path. ✅
- The highest-leverage blocker is fixed or isolated with evidence. ✅
- README and this TODO file reflect reality, not aspiration. ✅