# Yahoo Persistent League Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only, full-league Yahoo intelligence pipeline that improves lineup, waiver, trade, opponent, playoff, and multi-season decisions.

**Architecture:** Extend Yahoo collection to fetch every roster and bounded available-player pages, normalize raw Yahoo payloads into a compact league-intelligence document, and retain compact historical observations separately from current data. Update delivery and the daily automation only after coverage and live workflow verification pass.

**Tech Stack:** Python 3, requests, pytest/unittest mocks, GitHub Actions, Google Drive uploader, ChatGPT Automations.

**Spec:** `docs/superpowers/specs/2026-10-29-yahoo-persistent-league-intelligence-design.md`

## Global Constraints

- Yahoo remains read-only; never submit claims, drops, lineup changes, or trades.
- Never expose OAuth credentials in source, output, tests, or logs.
- Yahoo failures must not interrupt Sleeper.
- Current facts, estimates, uncertainty, stale data, and unavailable fields must be distinguished.
- Atomic writes preserve the prior valid output after failure.
- History must be compact, bounded, and compatible with Yahoo's applicable agreement.
- No recommendation solely to create activity.

## Review Focus

- Yahoo returns fewer roster resources than the league team count: mark coverage partial and preserve evidence rather than claiming completeness.
- Nested Yahoo objects vary between list and dictionary forms: normalize both without losing player or team identity.
- Available-player pagination repeats or ends early: deduplicate by player key and enforce page/call limits.
- A refresh fails after some API calls: do not replace the prior valid analytical output with partial output.
- Historical manager tendencies have small samples or season changes: expose sample size and decay confidence rather than treating them as facts.

---

### Task 1: Full-League Yahoo Collection

**Files:**
- Modify: `yahoo_feed.py`
- Modify: `fetch_yahoo.py`
- Modify: `tests/test_yahoo_feed.py`

**Interfaces:**
- Consumes: existing `build_snapshot(get, generated_at=None) -> dict[str, Any]`
- Produces: `extract_team_keys(teams_payload: Any) -> list[str]`, `collect_team_rosters(get, team_keys: list[str]) -> dict[str, Any]`, and snapshot resources `team_rosters` plus `roster_coverage`

- [ ] **Step 1: Write failing tests for team-key extraction, all-roster requests, missing-roster coverage, and list/dict Yahoo shapes**

Assert deterministic unique team keys, one `team/{key}/roster` call per team, and coverage fields `expected`, `received`, `complete`, and `missing_team_keys`.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `python -m pytest tests/test_yahoo_feed.py -k "team_keys or team_rosters or roster_coverage" -v`  
Expected: FAIL because the interfaces/resources do not exist.

- [ ] **Step 3: Implement full-league roster collection**

Add the exact interfaces above. Keep Paul's existing `roster` resource for backward compatibility and add all-team resources without changing authentication.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_yahoo_feed.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -am "feat: collect every Yahoo league roster"`

### Task 2: Available-Player Pagination and Feed Health

**Files:**
- Modify: `yahoo_feed.py`
- Modify: `fetch_yahoo.py`
- Modify: `tests/test_yahoo_feed.py`

**Interfaces:**
- Consumes: Task 1 snapshot
- Produces: `collect_available_players(get, league_key: str, positions: list[str], page_size: int = 25, max_pages: int = 4) -> dict[str, Any]` and `assess_snapshot_health(snapshot: dict[str, Any]) -> dict[str, Any]`

- [ ] **Step 1: Write failing tests for pagination, duplicate player keys, early termination, hard page limits, partial roster coverage, and stale timestamps**

Assert deduplication by Yahoo player key, no more than `max_pages` calls per position, and health states `healthy`, `partial`, or `stale` with evidence.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_yahoo_feed.py -k "available or health" -v`  
Expected: FAIL because the interfaces do not exist.

- [ ] **Step 3: Implement bounded collection and health assessment**

Fetch QB/RB/WR/TE/K/DEF and any Yahoo league-specific OFF position when present in settings. Preserve raw pages under a bounded resource and never infer unavailable FAAB/priority data.

- [ ] **Step 4: Run full tests**

Run: `python -m pytest tests/test_yahoo_feed.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -am "feat: add Yahoo player pool and coverage health"`

### Task 3: Normalized League Intelligence

**Files:**
- Create: `yahoo_intelligence.py`
- Create: `tests/test_yahoo_intelligence.py`
- Modify: `fetch_yahoo.py`

**Interfaces:**
- Consumes: raw snapshot from Tasks 1–2
- Produces: `build_league_intelligence(snapshot: dict[str, Any]) -> dict[str, Any]` and atomic `yahoo_league_intel.json`

- [ ] **Step 1: Write failing fixture-based tests**

Cover normalized league/team/player identity, roster slots, position counts, bench/IR exposure, waiver rank/FAAB when present, current matchup, transaction counts, manager samples, missing fields, and full/partial coverage.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_yahoo_intelligence.py -v`  
Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement normalization**

Return schema/version metadata, freshness/coverage, teams keyed by team key, Paul's team key, current matchups, available-player index, transaction summaries, and evidence-backed needs/strength indicators. Store inference confidence and sample size.

- [ ] **Step 4: Write atomically only after validation**

Require a resolvable league key, Paul's team key, and at least one team. A failed build leaves the previous valid intelligence file untouched.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_yahoo_intelligence.py tests/test_yahoo_feed.py -v`  
Expected: PASS.

- [ ] **Step 6: Commit**

`git add yahoo_intelligence.py fetch_yahoo.py tests && git commit -m "feat: normalize Yahoo league intelligence"`

### Task 4: Compact Historical Learning and Decision Log

**Files:**
- Create: `yahoo_history.py`
- Create: `tests/test_yahoo_history.py`
- Modify: `fetch_yahoo.py`
- Modify: `.gitignore` or workflow retention configuration as required

**Interfaces:**
- Consumes: `yahoo_league_intel.json`
- Produces: `update_history(current: dict[str, Any], history: dict[str, Any] | None, max_observations: int = 256) -> dict[str, Any]` and `update_manager_profiles(history: dict[str, Any]) -> dict[str, Any]`

- [ ] **Step 1: Write failing tests for deduplication, bounded retention, season boundaries, small samples, confidence decay, and changed rosters**

Assert unchanged hourly snapshots do not create duplicate observations, retention never exceeds 256, and manager tendencies include sample size/confidence.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_yahoo_history.py -v`  
Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement compact history**

Retain hashes/deltas and normalized evidence, not repeated full raw snapshots. Separate seasons and decay prior-season behavioral confidence.

- [ ] **Step 4: Add a recommendation/decision-log schema**

Record timestamp, action type, recommendation, alternatives, evidence, confidence, and later outcome when known; never mark a recommendation as executed without platform evidence.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_yahoo_history.py tests/test_yahoo_intelligence.py -v`  
Expected: PASS.

- [ ] **Step 6: Commit**

`git add yahoo_history.py fetch_yahoo.py tests && git commit -m "feat: retain compact Yahoo league history"`

### Task 5: Workflow, Drive Delivery, and Status

**Files:**
- Modify: `.github/workflows/yahoo-update.yml`
- Modify: `upload_to_drive.py`
- Modify: `yahoo_status.json` generation
- Modify/Create: uploader tests if present

**Interfaces:**
- Consumes: current snapshot, daily, status, intelligence, and bounded history outputs
- Produces: Drive updates for `yahoo_league_intel.json` and compact history/status artifacts

- [ ] **Step 1: Add failing tests or dry-run assertions for the expanded Yahoo upload manifest**

Assert Yahoo uploads only Yahoo outputs and Sleeper's manifest remains unchanged.

- [ ] **Step 2: Verify failure**

Run the uploader test/dry-run command documented in the repository.  
Expected: new outputs are absent.

- [ ] **Step 3: Update workflow and uploader**

Upload current intelligence every run. Upload bounded history only when changed. Include team/roster counts, coverage state, timestamps, and warnings in status.

- [ ] **Step 4: Run all local tests**

Run: `python -m pytest -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

`git add .github/workflows/yahoo-update.yml upload_to_drive.py tests && git commit -m "feat: deliver Yahoo league intelligence"`

### Task 6: Automation Upgrade and End-to-End Verification

**Files:**
- Update externally: ChatGPT automation `Yahoo Daily + Waivers`
- Update: `README.md` with outputs and verification
- Update: plan checkboxes/results

**Interfaces:**
- Consumes: Drive `yahoo_daily.json`, `yahoo_snapshot.json`, `yahoo_status.json`, `yahoo_league_intel.json`, and history
- Produces: daily, Tuesday waiver, trade, pre-lock, weekly intelligence, and post-waiver reports

- [ ] **Step 1: Update the automation prompt**

Require full-league analysis, coverage/freshness validation, opponent strengths/weaknesses, waiver competition with probability ranges, exact contingency claims, trade partner/offer/counter/walk-away/message analysis, playoff planning, and concise output only when actionable.

- [ ] **Step 2: Trigger the live Yahoo GitHub workflow**

Expected: successful authorization, collection, intelligence build, commit/upload, and no Sleeper workflow regression.

- [ ] **Step 3: Verify live outputs**

Confirm expected league team count equals roster coverage; inspect at least two opponent rosters, available-player data, transaction evidence, and status freshness.

- [ ] **Step 4: Run the automation once**

Expected: a practice report that names league-wide strengths/weaknesses, waiver competitors, and at least one evaluated trade path or an evidence-based explanation that no trade qualifies.

- [ ] **Step 5: Verify safety and regression**

Run: `python -m pytest -v`  
Expected: PASS. Confirm repository search finds no plaintext Yahoo credential/token and Sleeper's latest workflow remains successful.

- [ ] **Step 6: Document and commit**

`git add README.md docs/superpowers/plans/2026-10-30-yahoo-persistent-league-intelligence.md && git commit -m "docs: verify Yahoo league intelligence"`
