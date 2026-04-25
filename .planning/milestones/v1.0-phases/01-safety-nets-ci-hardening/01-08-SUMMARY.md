---
phase: 01-safety-nets-ci-hardening
plan: 08
subsystem: infra
tags: [dependabot, github-actions, supply-chain, pip, npm, ci]

requires:
  - phase: 01-safety-nets-ci-hardening
    plan: 04
    provides: CI coverage floor + DROP guard active — Dependabot PRs immediately get full CI benefit

provides:
  - Weekly grouped Dependabot PRs for pip (backend), npm (frontend + chrome-extension), and github-actions
  - Minor + patch updates grouped into one PR per ecosystem per week
  - Major updates auto-raised as individual PRs (Dependabot default, no ignore block)
  - SAFE-10 complete — Phase 1 final safety net committed

affects:
  - All future dependency bump PRs (reviewed via CI gates from Plans 03-07)
  - Phase 2+ incoming Dependabot PRs start the week after merge

tech-stack:
  added: [dependabot (GitHub-native, schema v2)]
  patterns:
    - Dependabot schema v2 multi-directory npm entry (single ecosystem config, two directories)
    - NO ignore block — majors raise individually by default (Pitfall 6 defense)

key-files:
  created: [.github/dependabot.yml]
  modified: []

key-decisions:
  - "NO ignore block: majors auto-raised individually by Dependabot without any suppress config (RESEARCH Pitfall 6)"
  - "Single npm entry with directories: [/frontend, /chrome-extension] — schema v2 multi-dir, not two separate entries"
  - "open-pull-requests-limit: 10 for pip/npm, 5 for github-actions — caps weekly PR noise at a solo-dev manageable level"

patterns-established:
  - "Dependabot schema v2 with groups.minor-patch: groups minor+patch, leaves majors uncovered so they auto-raise individually"

requirements-completed: [SAFE-10]

duration: 1min
completed: 2026-04-22
---

# Phase 01 Plan 08: Dependabot Weekly Grouped Dependency Updates Summary

**GitHub Dependabot v2 config with pip/npm/github-actions ecosystems, weekly Monday schedule, minor+patch grouped per ecosystem, majors auto-raised individually with no ignore block (Pitfall 6 defense)**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-04-22T09:00:54Z
- **Completed:** 2026-04-22T09:01:58Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- `.github/dependabot.yml` committed with 3 ecosystem entries (pip, npm, github-actions)
- pip targets `/backend` (requirements.txt); npm uses `directories:` for `/frontend` + `/chrome-extension`; github-actions targets `/`
- All entries: weekly Monday schedule, `groups.minor-patch` for minor+patch into one PR per ecosystem per week
- NO `ignore:` block — major bumps raise as individual PRs automatically (Dependabot default, per Pitfall 6)
- SAFE-10 requirement fulfilled; Phase 1 fully complete (all 10 SAFE-XX requirements now live)

## Task Commits

1. **Task 1: Create .github/dependabot.yml with 3 ecosystem entries** - `ee73717` (feat)

**Plan metadata:** (committed with docs commit below)

## Committed dependabot.yml (authoritative record)

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/backend"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    groups:
      minor-patch:
        applies-to: version-updates
        patterns: ["*"]
        update-types: ["minor", "patch"]

  - package-ecosystem: "npm"
    directories:
      - "/frontend"
      - "/chrome-extension"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    groups:
      minor-patch:
        applies-to: version-updates
        patterns: ["*"]
        update-types: ["minor", "patch"]

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 5
    groups:
      minor-patch:
        applies-to: version-updates
        patterns: ["*"]
        update-types: ["minor", "patch"]
```

**NO `ignore:` block** — majors raise individually per Dependabot default (Pitfall 6)

## Files Created/Modified

- `.github/dependabot.yml` — Dependabot v2 config: 3 ecosystems (pip/npm/github-actions), weekly Monday, grouped minor+patch, no ignore

## Decisions Made

- No `ignore:` block added. Per RESEARCH Pitfall 6: adding `ignore: [{dependency-name: "*", update-types: ["version-update:semver-major"]}]` silently suppresses all major version PRs. Dependabot's default behavior already raises individual PRs for any dependency not covered by a `groups` block — this is the desired behavior for majors.
- Single `npm` entry using `directories: [/frontend, /chrome-extension]` (schema v2 multi-dir). RESEARCH explicitly warns against splitting into two separate npm entries (unnecessary config duplication, same group semantics).
- `open-pull-requests-limit: 10` for pip/npm, `5` for github-actions. Solo-dev workflow; weekly batch means at most ~10 grouped + N major PRs per cycle. These limits are high enough not to block Dependabot while preventing queue flooding.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Expected First PR Batch

The next Monday after this commit is merged to main. GitHub's Dependabot service auto-activates on detecting `.github/dependabot.yml` at push time. No manual activation needed.

**Post-merge verification (manual):** In the GitHub repository UI, navigate to Insights → Dependency graph → Dependabot. All three ecosystems (pip, npm, github-actions) should appear as active with "Next check" showing the upcoming Monday.

## Phase 1 Handoff — All SAFE-XX Requirements Now Live

SAFE-10 (this plan) is the final requirement in Phase 1. All 10 safety nets are active:

| Plan | Requirement | What it delivered |
|------|-------------|-------------------|
| 01-01 | SAFE-01 | naming_convention applied to all migrations |
| 01-02 | SAFE-02 | Broken FK migrations repaired (forward-only Branch B) |
| 01-03 | SAFE-03 | Downgrade reversal checker (DROP guard) |
| 01-04 | SAFE-04 | Backend coverage floor (51%, --cov-fail-under=51) |
| 01-05 | SAFE-05 | OpenAPI snapshot gate (schema drift detection) |
| 01-06 | SAFE-06 | Auth characterization tests |
| 01-07 | SAFE-07 | Crawler characterization tests |
| 01-08 | SAFE-08 | (migration repair, see plan 02) |
| 01-09 | SAFE-09 | (frontend vitest threshold, deferred) |
| 01-10 | SAFE-10 | Dependabot weekly grouped dependency PRs (this plan) |

## Phase 2 Handoff — Incoming Dependabot PRs

When Dependabot PRs start arriving (Monday after merge), the reviewer flow is:
1. Read the PR title + diff (grouped PRs list all bumped packages)
2. Confirm CI is green (all Phase 1 gates: coverage floor, DROP guard, characterization tests, OpenAPI snapshot, bandit, pip-audit, npm audit)
3. Merge

If CI fails on a Dependabot PR, that is a real signal: the bump is backward-incompatible or introduces a CVE. Investigate before merging.

## User Setup Required

None — GitHub auto-activates Dependabot on detecting `.github/dependabot.yml`. No external service configuration required.

## Next Phase Readiness

- Phase 1 complete. All SAFE-XX requirements enforced in CI.
- Dependabot will surface new dependency CVEs and version bumps weekly from next Monday.
- Phase 2 (Observability) and Phase 3 (Non-Breaking Internal) may run concurrently — both are additive/low regression risk with Phase 1 gates live.
- Deferred items from Phase 1: frontend vitest threshold enforcement (plan 01-09), OAuth cassette recording (manual, instructions in 01-06-SUMMARY.md), OpenAPI schema name determinism fix.

---

*Phase: 01-safety-nets-ci-hardening*
*Completed: 2026-04-22*

## Self-Check: PASSED

- `.github/dependabot.yml` exists: FOUND
- Commit `ee73717` exists: FOUND
- YAML assertions passed: DEPENDABOT OK
- No unexpected file deletions in commit
