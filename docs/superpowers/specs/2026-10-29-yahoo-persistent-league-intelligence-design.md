# Yahoo Persistent League Intelligence — Design

Date: 2026-10-29  
Repository: `paul090181/fantasy-football-feed`

## Intent

Build a durable, read-only Yahoo fantasy-football intelligence system that helps Paul maximize championship probability this season and creates reusable advantages across future seasons. It must analyze the full league rather than only Paul's roster and current matchup.

The system advises. It never submits claims, drops, lineup changes, or trades without Paul's explicit approval.

## Goals

- Collect every team's full roster and current lineup, league settings, standings, matchups, waiver priority or FAAB data Yahoo exposes, transactions, and relevant available-player pools.
- Preserve dated history needed to measure manager behavior, roster changes, and prior recommendations, subject to Yahoo's API terms.
- Produce actionable lineup, waiver, free-agent, trade, opponent, playoff, and rest-of-season analysis.
- Forecast waiver competition and generate ordered primary and contingency claims.
- Identify mutually beneficial trade partners, recommend offers with value/risk analysis, and draft natural messages for Paul.
- Distinguish current facts, model estimates, uncertainty, and unavailable data.
- Keep Yahoo isolated so failures cannot disrupt the working Sleeper feed.
- Design normalized outputs so the same analysis architecture can later support Sleeper.

## Non-goals

- No autonomous roster transactions or trade submissions.
- No fabricated projections, injuries, FAAB balances, waiver priorities, or opponent intentions.
- No recommendation merely to create activity.
- No guarantee of championships; optimize expected results under uncertainty.

## Anti-goals

The system fails if it gives confident advice from stale or incomplete data, treats Yahoo projections as truth, recommends a trade without roster-context and replacement-value analysis, or accumulates history without using it to improve decisions.

## Current State and Constraints

Yahoo authentication, hourly refresh, GitHub output, Google Drive delivery, and the daily ChatGPT automation are operational. The feed currently requests league metadata, settings, standings, scoreboard, team summaries, transactions, Paul's roster, and Paul's matchups. It does not fetch every opponent roster.

Yahoo data is deeply nested and occasionally omits fields. API calls must be bounded, retried safely, and never expose OAuth credentials. Provider-data retention must remain compatible with Yahoo's applicable agreement. NFL news used for decisions must be current and authoritative.

## Approaches Considered

1. **Prompt-only upgrade:** Fast but rejected because missing opponent rosters cannot be recovered through better instructions.
2. **Full-league current snapshot:** Useful for today's decisions but weak at learning manager habits or improving across seasons.
3. **Persistent league intelligence:** Selected. Adds full-league data, normalized analytical views, dated history, decision reports, and manager-tendency learning.

## Data Collection

Each successful Yahoo refresh will retrieve and validate:

- League metadata, settings, roster positions, scoring, current week, playoff rules, and waiver system.
- Standings, records, points for/against, rank, waiver priority, FAAB where exposed, and team identity.
- Every team's current roster with player IDs, selected position, eligible positions, status, and acquisition metadata where exposed.
- Current scoreboard and matchups; weekly team matchups where practical.
- League transactions with adds, drops, trades, timestamps, source/destination teams, and bid amounts where exposed.
- Targeted available-player pools by relevant positions, with pagination and configurable limits.
- Paul's owned team, roster, matchup, and near-term lock information.

A refresh is marked healthy only when required resources are present, timestamps are current, Paul's team resolves uniquely, and opponent-roster coverage meets the league team count. Partial data is labeled explicitly.

## Storage and Outputs

Keep raw provider payloads separate from normalized analytical data.

- `yahoo_snapshot.json`: full current raw snapshot.
- `yahoo_daily.json`: bounded current data needed for routine analysis.
- `yahoo_status.json`: freshness, coverage, counts, warnings, and failure details.
- `yahoo_league_intel.json`: normalized teams, rosters, needs, strengths, waiver context, transaction tendencies, and matchup facts.
- `history/yahoo/<season>/<timestamp>.json` or an equivalent compact append-only history subject to repository-size and provider-retention constraints.
- `yahoo_decision_log.json`: recommendations, confidence, alternatives, and later observed outcome when available.

Large raw files should not grow without bound. History will use compact normalized records, deduplication, and a documented retention policy.

## Analytical Layer

### Team strength

Calculate position-group depth, starter quality, replacement value, injury/bye exposure, bench usability, concentration risk, weekly scoring strength, and playoff-schedule context. Separate observed results from projection-derived estimates.

### Waivers and free agents

For each meaningful target:

- Estimate Paul's roster value gained and opportunity cost of the drop.
- Identify teams with matching positional needs, open roster spots, injuries, byes, and higher waiver priority/greater FAAB.
- Estimate claim competition as a probability range rather than certainty.
- Produce exact ordered claims, shared-drop contingencies, maximum rational FAAB where applicable, and post-waiver free-agent fallbacks.
- Track processed claims, winning bids/priorities, and remaining budgets to update manager-tendency estimates.

### Trades

Identify complementary roster imbalances. Evaluate offers using expected starter improvement, replacement value, depth loss, injury/bye risk, playoff schedule, and counterparty incentives. Provide:

- Preferred offer.
- Acceptable counter range.
- Walk-away threshold.
- Why the other manager might accept.
- Risks and uncertainty.
- A ready-to-send natural message.

Avoid lowball spam and avoid trades whose apparent gain comes mainly from name value or unreliable projections.

### Weekly and postseason planning

Optimize lineups with lock times and injury uncertainty. Compare Paul's current opponent while also tracking the entire league. Estimate playoff odds and likely playoff opponents only when sufficient data exists. Prioritize roster moves that improve championship equity, not merely the current projection.

### Long-term learning

Retain manager-specific tendencies such as positional preferences, churn rate, bid aggressiveness, waiver behavior, trade responsiveness when observable, and recurring drops. Treat small samples conservatively and decay old evidence between seasons.

## Reports and Cadence

- **Daily concise review:** only material actions, alerts, and watch items.
- **Tuesday waiver report:** exact claim order, drops, contingency tree, competition estimates, and bid/priority strategy.
- **Trade report:** only when a credible positive-value opportunity exists.
- **Pre-lock review:** Thursday/early games and final Sunday injury decisions.
- **Weekly league intelligence summary:** power rankings, team needs, playoff outlook, transaction patterns, and upcoming opportunities.
- **Post-waiver learning:** who won each player, winning priority/bid where available, and model updates.

The existing 8:15 AM Eastern automation remains the primary daily delivery unless later changed.

## Reliability and Safety

- Read-only Yahoo scopes and no automated transactions.
- Credentials and tokens remain encrypted and excluded from logs and outputs.
- Yahoo failure cannot block Sleeper.
- Atomic file writes; previous valid output remains available after a failed refresh.
- API pagination, timeouts, retry/backoff, and rate-conscious request limits.
- Explicit freshness and coverage indicators in every report.
- Tests use fixtures and mocks; live secrets are never required locally.

## Verification

Implementation is complete only when:

1. Automated tests cover team discovery, every-roster collection, pagination, normalization, partial failures, stale data, and secret redaction.
2. A live Yahoo workflow succeeds.
3. Coverage reports the expected number of league teams and full rosters.
4. Google Drive receives updated outputs.
5. The daily automation reads the new intelligence file.
6. A practice report demonstrates opponent strengths/weaknesses, waiver competition, at least one evaluated trade path (or explains why none qualifies), and exact actionable recommendations.
7. Sleeper's existing workflow remains successful and unchanged except for explicitly shared, backward-compatible infrastructure.

## Builder Decisions

- Prefer a small normalized intelligence module over embedding more logic in the API client.
- Use conservative heuristics first; add predictive models only after enough historical observations exist.
- Store both evidence and confidence for inferred manager behavior.
- Keep output sizes bounded so ChatGPT can reliably read the files.

## Future Extension

After Yahoo stabilizes, apply the normalized league-intelligence schema to Sleeper so both leagues receive comparable analysis while retaining platform-specific waiver and roster rules.
