---
phase: 07
plan: 05
type: execute
wave: 2
depends_on: [07-01, 07-02, 07-03, 07-04]
files_modified:
  - .planning/phases/01-safety-nets-ci-hardening/01-VALIDATION.md
  - .planning/phases/02-observability/02-VALIDATION.md
  - .planning/phases/03-non-breaking-internal-improvements/03-VALIDATION.md
  - .planning/phases/04-db-parts-hardening/04-VALIDATION.md
  - .planning/phases/05-structural-router-splits/05-VALIDATION.md
  - .planning/phases/06-frontend-cleanup-final-ci-gates/06-VALIDATION.md
# /gsd-validate-phase may require interactive confirmation per phase; plan defaults to interactive to honor that
autonomous: false
tech_debt_items:
  - NYQUIST-01  # 6x wave_0_complete=false across all 6 phase VALIDATION.md files (cross-cutting, from audit frontmatter)
must_haves:
  truths:
    - "All 6 phase VALIDATION.md files have `wave_0_complete: true` in their frontmatter"
    - "All 6 phase VALIDATION.md files have `nyquist_compliant: true` in their frontmatter"
    - "All 6 phase VALIDATION.md files have `status: accepted` (or equivalent non-draft value) in frontmatter"
    - "Each VALIDATION.md contains an execution-time verification log showing the Quick/Full commands were run and passed"
    - "The commit closing each phase's VALIDATION.md explicitly references the `/gsd-validate-phase NN` invocation"
  artifacts:
    - path: ".planning/phases/01-safety-nets-ci-hardening/01-VALIDATION.md"
      provides: "Nyquist Wave 0 sign-off: status=accepted, wave_0_complete=true, nyquist_compliant=true"
      contains: "wave_0_complete: true"
    - path: ".planning/phases/02-observability/02-VALIDATION.md"
      provides: "Nyquist Wave 0 sign-off for Phase 2"
      contains: "wave_0_complete: true"
    - path: ".planning/phases/03-non-breaking-internal-improvements/03-VALIDATION.md"
      provides: "Nyquist Wave 0 sign-off for Phase 3"
      contains: "wave_0_complete: true"
    - path: ".planning/phases/04-db-parts-hardening/04-VALIDATION.md"
      provides: "Nyquist Wave 0 sign-off for Phase 4"
      contains: "wave_0_complete: true"
    - path: ".planning/phases/05-structural-router-splits/05-VALIDATION.md"
      provides: "Nyquist Wave 0 sign-off for Phase 5"
      contains: "wave_0_complete: true"
    - path: ".planning/phases/06-frontend-cleanup-final-ci-gates/06-VALIDATION.md"
      provides: "Nyquist Wave 0 sign-off for Phase 6"
      contains: "wave_0_complete: true"
  key_links:
    - from: "each phase VALIDATION.md"
      to: "each phase's test suite"
      via: "the Quick/Full commands documented in the file were run and passed"
      pattern: "wave_0_complete: true"
---

<objective>
Close the cross-cutting Nyquist validation gap — all 6 phase `VALIDATION.md` files are currently in `draft` status with `nyquist_compliant: false` and `wave_0_complete: false`. Tests themselves pass (2371 backend + 76 frontend), but the per-phase validation-strategy sign-off was deferred through the milestone. This plan runs `/gsd-validate-phase N` for each of the 6 phases and commits the frontmatter flip.

Purpose: `.planning/v1.0-MILESTONE-AUDIT.md` Cross-cutting §1 ("6× Nyquist `wave_0_complete: false`") and `.planning/v1.0-MILESTONE-AUDIT.md` `## Nyquist Validation Coverage` table explicitly call out this gap. The audit's recommended closure action is: "Run /gsd-validate-phase N for each phase to close" — this plan executes that recommendation.

Output: 6 validated VALIDATION.md files with frontmatter `wave_0_complete: true` + `nyquist_compliant: true` + `status: accepted`, each committed to git with a `docs(07-05):` commit message referencing the phase.
</objective>

<execution_context>
@/home/tyler-webb/Documents/Github/CarModPicker/.claude/get-shit-done/workflows/execute-plan.md
@/home/tyler-webb/Documents/Github/CarModPicker/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/v1.0-MILESTONE-AUDIT.md
@.planning/phases/01-safety-nets-ci-hardening/01-VALIDATION.md
@.planning/phases/02-observability/02-VALIDATION.md
@.planning/phases/03-non-breaking-internal-improvements/03-VALIDATION.md
@.planning/phases/04-db-parts-hardening/04-VALIDATION.md
@.planning/phases/05-structural-router-splits/05-VALIDATION.md
@.planning/phases/06-frontend-cleanup-final-ci-gates/06-VALIDATION.md

<interfaces>
### `/gsd-validate-phase N` contract (what the command does)
- Reads `.planning/phases/{NN}-*/{NN}-VALIDATION.md`.
- Runs the "Quick run command" and "Full suite command" documented in the file's "Test Infrastructure" table.
- For each REQ-ID in the "Per-Task Verification Map", runs the `Automated Command` column.
- On all-green: rewrites frontmatter to set `status: accepted`, `wave_0_complete: true`, `nyquist_compliant: true`; appends an execution-time validation-log section to the file body.
- On any failure: leaves frontmatter unchanged and emits a report of the failing checks.

### Existing frontmatter pattern (from 01-VALIDATION.md)
```
(frontmatter fence)
phase: 1
slug: safety-nets-ci-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-21
(frontmatter fence)
```

### Target frontmatter pattern (after validate-phase)
```
(frontmatter fence)
phase: 1
slug: safety-nets-ci-hardening
status: accepted
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-21
validated: 2026-04-2X  # ISO date of validation run
(frontmatter fence)
```

### Dependency on Wave 1 plans
This plan runs AFTER 07-01..07-04 because:
- 07-03 deletes `test_runner_circuit_breaker.py` — affects Phase 3 test collection count (validation log should reflect the post-cleanup count, not the pre-cleanup count).
- 07-01 adds ~10 new tests — affects Phase 4 test counts.
- 07-04 changes terraform state — `terraform validate` is part of Phase 2's validation commands.
- Running validate-phase before Wave 1 lands would freeze stale test counts into the VALIDATION.md execution log.
</interfaces>
</context>

<tasks>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 1: Run `/gsd-validate-phase 01..06` sequentially and confirm each frontmatter flip</name>
  <files>.planning/phases/01-safety-nets-ci-hardening/01-VALIDATION.md, .planning/phases/02-observability/02-VALIDATION.md, .planning/phases/03-non-breaking-internal-improvements/03-VALIDATION.md, .planning/phases/04-db-parts-hardening/04-VALIDATION.md, .planning/phases/05-structural-router-splits/05-VALIDATION.md, .planning/phases/06-frontend-cleanup-final-ci-gates/06-VALIDATION.md</files>
  <action>
    Invoke `/gsd-validate-phase NN` for each N in {01, 02, 03, 04, 05, 06}. Review and approve each frontmatter flip one at a time. Commit each phase's VALIDATION.md change as a separate `docs(07-05):` commit. Details in <how-to-verify>.
  </action>
  <verify>Manual: after all 6 runs, `grep -c "wave_0_complete: true" .planning/phases/*/*-VALIDATION.md` returns 6.</verify>
  <done>All 6 phase VALIDATION.md files have `status: accepted`, `wave_0_complete: true`, `nyquist_compliant: true`. 6 commits land in git history.</done>

  <what-built>
    Plan 07-05 depends on the planner-orchestrated `/gsd-validate-phase N` workflow, which is interactive by design (presents each VALIDATION.md's test results, asks the operator to confirm the frontmatter flip). This task is the execution envelope.

    Before starting:
    - All Wave 1 plans (07-01..07-04) must be merged to main and the full pytest + frontend vitest suites must be green.
    - `terraform validate` in `terraform/` must be green (Plan 07-04).

    Sequential execution:
    ```bash
    /gsd-validate-phase 01
    # Confirm frontmatter flip. Commit: docs(07-05): close Nyquist Wave 0 for Phase 1 (01-VALIDATION.md)
    /gsd-validate-phase 02
    # Confirm. Commit: docs(07-05): close Nyquist Wave 0 for Phase 2 (02-VALIDATION.md)
    /gsd-validate-phase 03
    # Confirm. Commit: docs(07-05): close Nyquist Wave 0 for Phase 3 (03-VALIDATION.md)
    /gsd-validate-phase 04
    # Confirm. Commit: docs(07-05): close Nyquist Wave 0 for Phase 4 (04-VALIDATION.md)
    /gsd-validate-phase 05
    # Confirm. Commit: docs(07-05): close Nyquist Wave 0 for Phase 5 (05-VALIDATION.md)
    /gsd-validate-phase 06
    # Confirm. Commit: docs(07-05): close Nyquist Wave 0 for Phase 6 (06-VALIDATION.md)
    ```
  </what-built>

  <how-to-verify>
    For each phase 01 through 06:

    1. Run `/gsd-validate-phase NN` where NN is the padded phase number.
    2. Review the command's output — it will show:
       - Test Infrastructure table contents
       - Quick / Full command runs with exit codes and summary counts
       - Per-REQ-ID automated check results
       - A diff of the proposed frontmatter flip
    3. If all checks pass, confirm (`approved` / `y`) — the command writes the frontmatter flip and appends an execution log section.
    4. If any check fails:
       - STOP. Do not force-approve the flip.
       - Investigate the failure. Common causes: a test was renamed, a Quick command is out of date, a new test introduced a warning/error that the validator is strict about.
       - Either (a) fix the test/command and re-run `/gsd-validate-phase NN`, or (b) if the failure is a true gap, close this plan as blocked and escalate to the user to open a new plan.
    5. Commit the frontmatter change and the appended validation-log section with `docs(07-05): close Nyquist Wave 0 for Phase N (NN-VALIDATION.md)`.
    6. Verify commit with `git log --oneline -1` and `grep "wave_0_complete: true" .planning/phases/NN-*/NN-VALIDATION.md`.

    After all 6 phases complete, run:
    ```bash
    for N in 01 02 03 04 05 06; do
      echo "Phase $N:"
      grep -E "(status|wave_0_complete|nyquist_compliant):" .planning/phases/$N-*/$N-VALIDATION.md
    done
    ```
    Every phase must show `status: accepted` (or equivalent), `wave_0_complete: true`, `nyquist_compliant: true`.
  </how-to-verify>

  <resume-signal>
    Reply "approved" after all 6 phases have validated successfully and committed. Reply with blocker notes if any phase's Quick/Full command fails — the failing phase's VALIDATION.md frontmatter will stay `draft` until the failure is resolved, and this plan stays blocked until then.
  </resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Planner → /gsd-validate-phase command | Command runs documented Quick/Full test commands; does not modify production code. |
| /gsd-validate-phase → VALIDATION.md frontmatter | Writes only to `.planning/phases/**/*-VALIDATION.md`; no other files touched. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-05-01 | Tampering | False-positive frontmatter flip | mitigate | Human checkpoint is `gate="blocking"`; operator reviews each phase's Quick/Full output before approving the flip. The checkpoint explicitly says "do not force-approve on failure" to prevent masking a real gap. |
| T-07-05-02 | Repudiation | Which commit / which tests were run | mitigate | Each commit is scoped per-phase with a conventional-commit message `docs(07-05): close Nyquist Wave 0 for Phase N`. `/gsd-validate-phase` appends an execution-log section with commands + exit codes + timestamps to the VALIDATION.md body, providing reviewable audit trail in git history. |

**No new attack surface introduced.** Pure documentation flip after operator-reviewed test execution.
</threat_model>

<verification>
After Task 1 completes (all 6 validations approved), run:
```bash
for N in 01 02 03 04 05 06; do
  phase_dir=$(ls -d .planning/phases/$N-*)
  val_file="$phase_dir/$N-VALIDATION.md"
  if grep -q "wave_0_complete: true" "$val_file" && grep -q "nyquist_compliant: true" "$val_file"; then
    echo "OK  — Phase $N"
  else
    echo "MISS — Phase $N: $val_file"
    exit 1
  fi
done
```
Must print "OK" for all 6 phases.
</verification>

<success_criteria>
- Phase 7 success criterion 8 closed: all 6 phase VALIDATION.md files have `wave_0_complete: true` and `nyquist_compliant: true`.
</success_criteria>

<output>
After completion, create `.planning/phases/07-v1-residue-cleanup/07-05-SUMMARY.md`. Frontmatter must include `tech_debt_items_closed: [NYQUIST-01]` and list the 6 commits created (one per phase validation).
</output>
