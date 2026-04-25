---
phase: 07
plan: 06
type: execute
wave: 2
depends_on: [07-01, 07-02, 07-03, 07-04, 07-05]
files_modified:
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
autonomous: true
tech_debt_items:
  - DOC-01  # REQUIREMENTS.md: 59 rows still marked "Pending" in traceability; SAFE-03 stays Pending
  - DOC-02  # REQUIREMENTS.md: 59 `[ ]` checkboxes need to flip to `[x]` (SAFE-03 stays unchecked)
  - DOC-03  # ROADMAP.md: Progress table shows Phase 1/2/5/6 as "Not started" despite verification complete
must_haves:
  truths:
    - "`.planning/REQUIREMENTS.md` traceability table: all 59 non-SAFE-03 rows have `Satisfied` in the Status column"
    - "`.planning/REQUIREMENTS.md` SAFE-03 row retains `Pending` (moved to Phase 8 per ROADMAP.md)"
    - "`.planning/REQUIREMENTS.md` v1 Requirements section: 59 of 60 checkboxes are `[x]` (SAFE-03 remains `[ ]`)"
    - "`.planning/ROADMAP.md` Progress table: Phase 1/2/5/6 rows updated from `Not started` to `Complete` with completion dates matching the phase VERIFICATION.md sign-off dates"
    - "A single commit `docs(07-06): sync REQUIREMENTS.md + ROADMAP.md with milestone v1.0 verification reality` lands the changes"
  artifacts:
    - path: ".planning/REQUIREMENTS.md"
      provides: "Documentation-truth: 59/60 requirements marked Satisfied; SAFE-03 pending; checkboxes match"
      contains: "| SAFE-03 | Phase 8 | Pending |"
    - path: ".planning/ROADMAP.md"
      provides: "Progress table reflects verified completion dates for Phase 1/2/5/6"
      contains: "Complete"
  key_links:
    - from: ".planning/REQUIREMENTS.md traceability table"
      to: "each phase's VERIFICATION.md"
      via: "Status column flips Pending → Satisfied when phase VERIFICATION.md confirms the requirement"
      pattern: "Satisfied"
    - from: ".planning/ROADMAP.md Progress table"
      to: ".planning/phases/NN-*/NN-VERIFICATION.md"
      via: "Completed date pulled from VERIFICATION.md frontmatter or phase-SUMMARY commit date"
      pattern: "^\\| \\d+\\. .+\\| \\d+/\\d+ \\| Complete \\| 2026-"
---

<objective>
Sync two documentation files with the milestone v1.0 verification reality that the audit flagged as stale:

1. **`.planning/REQUIREMENTS.md`** — the traceability table shows `Pending` on every row, and v1 Requirement checkboxes `[ ]` are unchecked on many requirements (SAFE-05, SAFE-06, SAFE-09, most OBS/CRAWL/QUAL/DATA/PARTS/ADMIN/AUTH/FE IDs) despite VERIFICATION.md confirming them satisfied. Flip 59 `Pending → Satisfied` and ensure 59 of 60 checkboxes are `[x]`. Leave SAFE-03 as `Pending` / `[ ]` because it moves to Phase 8.

2. **`.planning/ROADMAP.md`** — the Progress table still shows Phase 1, 2, 5, 6 as `Not started` even though the phase-detail sections mark them `[x]` and all VERIFICATIONs pass. Update the table to `Complete` with actual completion dates from each phase's VERIFICATION.md / last SUMMARY commit.

Purpose: `.planning/v1.0-MILESTONE-AUDIT.md` §Documentation Drift explicitly identifies both of these drifts as items to fix during `/gsd-complete-milestone`. Closing them now removes the last non-code gap before milestone archive.

Output: One commit modifying only `.planning/REQUIREMENTS.md` and `.planning/ROADMAP.md`. No production code changes.
</objective>

<execution_context>
@/home/tyler-webb/Documents/Github/CarModPicker/.claude/get-shit-done/workflows/execute-plan.md
@/home/tyler-webb/Documents/Github/CarModPicker/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/v1.0-MILESTONE-AUDIT.md
@.planning/phases/01-safety-nets-ci-hardening/01-VERIFICATION.md
@.planning/phases/02-observability/02-VERIFICATION.md
@.planning/phases/03-non-breaking-internal-improvements/03-VERIFICATION.md
@.planning/phases/04-db-parts-hardening/04-VERIFICATION.md
@.planning/phases/05-structural-router-splits/05-VERIFICATION.md
@.planning/phases/06-frontend-cleanup-final-ci-gates/06-VERIFICATION.md

<interfaces>
### Authoritative source: v1.0 milestone audit (`.planning/v1.0-MILESTONE-AUDIT.md`)

Frontmatter scores: `requirements: 60/60`, `phases: 6/6`. The body §Requirements Coverage confirms:

> All 60 REQ-IDs resolved `satisfied` after applying the status-determination matrix (VERIFICATION.md × SUMMARY.md frontmatter × REQUIREMENTS.md traceability table).
> Zero orphaned requirements.

SAFE-03 classification:
> SAFE-03 (Vitest coverage thresholds lines:60 / functions:50 / branches:50 / statements:60) was explicitly deferred by user decision at the Plan 01-04 checkpoint ... This is tracked deferral, not an unsatisfied requirement.

Per ROADMAP.md Phase 8, SAFE-03 is the sole v1 requirement belonging to Phase 8 (post-milestone). So in the Phase 07 sync:
- 59 requirements flip `Pending → Satisfied`; ensure all 59 checkboxes are `[x]`
- SAFE-03 stays `Pending` in traceability (mapped to Phase 8 in ROADMAP.md line 183) and `[ ]` in v1 Requirements

### Current `.planning/REQUIREMENTS.md` state (from file)

v1 Requirements section uses two formatting patterns inherited from history:
- Some requirements:  `- [x] **SAFE-01\n**: Backend ...`  (linebreak in the name)
- Other requirements: `- [ ] **SAFE-03**: Vitest config ...`  (no linebreak)
Both patterns must be preserved — the executor flips only the `[ ]` marker without reformatting the rest.

Traceability table (lines 181-240): 60 rows, every row ends with `| Pending |`. SAFE-03 row shows `| SAFE-03 | Phase 8 | Pending |` — phase assignment is already correct post-Phase-8-split (do not change phase; only flip the other 59 Status entries).

### Current `.planning/ROADMAP.md` Progress table (lines 168-178)

```markdown
| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Safety Nets & CI Hardening | 0/8 | Not started | - |
| 2. Observability | 0/TBD | Not started | - |
| 3. Non-Breaking Internal Improvements | 5/5 | Complete | 2026-04-22 |
| 4. DB & Parts Hardening | 0/6 | Not started | - |
| 5. Structural Router Splits | 0/TBD | Not started | - |
| 6. Frontend Cleanup & Final CI Gates | 0/TBD | Not started | - |
| 7. v1.0 Residue Cleanup & Audit-Drift Sync | 0/TBD | Not started | - |
| 8. Frontend Coverage Expansion (SAFE-03) | 0/TBD | Not started | - |
```

Target state (values derived from the audit table `## Phase-Level Status` and git history):
- Phase 1: 8 plans shipped, UAT signed 2026-04-23 → `8/8 | Complete | 2026-04-23`
- Phase 2: 5 plans shipped, UAT signed 2026-04-23 → `5/5 | Complete | 2026-04-23`
- Phase 3: Already correct → `5/5 | Complete | 2026-04-22`
- Phase 4: 6 plans shipped, no human UAT needed (per audit) → `6/6 | Complete | 2026-04-22` (use the date on the `.planning/phases/04-db-parts-hardening/04-VERIFICATION.md` frontmatter `verified:` field; if not present, use `2026-04-22`)
- Phase 5: 4 plans shipped, UAT signed 2026-04-23 → `4/4 | Complete | 2026-04-23`
- Phase 6: 6 plans shipped, UAT signed 2026-04-23 → `6/6 | Complete | 2026-04-23`
- Phase 7: Currently in progress (this plan lands in Phase 7). DO NOT mark Phase 7 Complete — leave as `In progress | -`. Phase 7 completion is set by `/gsd-verify-work` after this plan lands.
- Phase 8: Not started.

### Extracting Phase 4 completion date from the VERIFICATION file

Run:
```bash
grep -E "^(verified|completed|date):" .planning/phases/04-db-parts-hardening/04-VERIFICATION.md | head -5
```

If no `verified:` / `completed:` key exists, fall back to:
```bash
git log --format="%ad" --date=short .planning/phases/04-db-parts-hardening/ | head -1
```
(date of most recent commit touching the phase 4 directory)

### Plans Complete checkboxes in ROADMAP.md Phase Details

ROADMAP.md lines 111-114 (Phase 5 plans) currently show `- [ ]` for all four plans despite the audit verifying them. These checkboxes are in the Phase Details section (not the Progress table). Flip to `- [x]` for Phase 5 plans as part of this plan.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Flip 59 REQUIREMENTS.md traceability rows + checkboxes</name>

  <read_first>
    - .planning/REQUIREMENTS.md  (full file — understand the exact formatting of checkboxes and table rows to preserve the two bullet-format variants)
    - .planning/v1.0-MILESTONE-AUDIT.md  (§Requirements Coverage → 3-Source Cross-Reference — confirms 60/60 satisfied, SAFE-03 classified as tracked deferral)
  </read_first>

  <files>.planning/REQUIREMENTS.md</files>

  <action>
    **Step 1: Capture before-state counts.**
    ```bash
    grep -c "^- \[ \]" .planning/REQUIREMENTS.md   # count of unchecked v1 req bullets
    grep -c "^- \[x\]" .planning/REQUIREMENTS.md   # count of checked
    grep -c "| Pending |" .planning/REQUIREMENTS.md
    grep -c "| Satisfied |" .planning/REQUIREMENTS.md
    ```
    Record these four numbers in the plan's SUMMARY.md when you finish.

    **Step 2: Flip v1 Requirements checkboxes.**

    For every requirement in the "## v1 Requirements" section EXCEPT SAFE-03, ensure the bullet starts with `- [x] **<REQ-ID>`. Use the Edit tool (one per requirement) and only change the `[ ]` to `[x]`, preserving whatever whitespace/linebreak formatting follows the requirement ID.

    Requirements to flip (identified from current REQUIREMENTS.md):
    - SAFE-05, SAFE-06, SAFE-09 (3 — other SAFE-0X are already `[x]`)
    - OBS-01, OBS-02, OBS-03, OBS-04, OBS-05 (5)
    - CRAWL-01, CRAWL-02, CRAWL-03, CRAWL-04, CRAWL-05, CRAWL-06, CRAWL-07 (7)
    - QUAL-01, QUAL-02, QUAL-03, QUAL-04, QUAL-05, QUAL-06, QUAL-07, QUAL-08 (8)
    - ADMIN-01, ADMIN-02, ADMIN-03, ADMIN-04 (4)
    - AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06 (6)
    - FE-01, FE-02, FE-03, FE-04, FE-05, FE-06, FE-07 (7)
    = 40 requirements to flip from `[ ]` to `[x]`.
    - DATA-01..DATA-10 and PARTS-01..PARTS-03 — already `[x]` per current file. Verify with `grep "\- \[x\] \*\*DATA"` and `grep "\- \[x\] \*\*PARTS"`. If any are `[ ]`, flip them. (The final expected count of `[x]` rows is 59; SAFE-03 is the only `[ ]`.)

    SAFE-03 stays `- [ ] **SAFE-03**: Vitest config enforces a coverage threshold ...` — do NOT modify this line.

    **Step 3: Flip traceability table Status column (59 of 60 rows).**

    All 60 rows in the traceability table (lines 181-240) currently end with `| Pending |`. Execute a two-step replacement to preserve SAFE-03:

    Use the Edit tool for this — a global sed is risky because the table is large (60 rows across ~60 lines). Preferred approach: make ONE Edit call that replaces every occurrence in the traceability table.

    Do a bulk Edit of `| Pending |` → `| Satisfied |` targeting only the traceability section. Since the file's Out of Scope section uses `| Feature | Reason |` columns (no Pending/Satisfied column), a file-wide global replace is safe — the only `Pending` markers in the file are in the traceability table.

    After the bulk replace, do ONE corrective Edit: change `| SAFE-03 | Phase 8 | Satisfied |` back to `| SAFE-03 | Phase 8 | Pending |`.

    **Step 4: Add a footer note.**

    At the very end of the file (after the last `*Last updated:` line), append:
    ```markdown

    ---

    **Milestone v1.0 status sync (Phase 07 plan 07-06):**
    - 59 requirements flipped Pending -> Satisfied based on `.planning/v1.0-MILESTONE-AUDIT.md` (audited 2026-04-24).
    - SAFE-03 remains Pending — moved to Phase 8 (frontend coverage expansion).
    - Synced: (executor: fill in with today's ISO date at commit time).
    ```

    **Step 5: Verify after-state counts.**
    ```bash
    grep -c "^- \[ \]" .planning/REQUIREMENTS.md   # MUST return 1
    grep -c "^- \[x\]" .planning/REQUIREMENTS.md   # MUST return 59
    grep -c "| Pending |" .planning/REQUIREMENTS.md   # MUST return 1
    grep -c "| Satisfied |" .planning/REQUIREMENTS.md # MUST return 59
    grep "| SAFE-03 |" .planning/REQUIREMENTS.md      # MUST show one row ending with "| Pending |"
    ```
  </action>

  <verify>
    <automated>bash -c 'set -e; [ "$(grep -c "^- \[ \]" .planning/REQUIREMENTS.md)" = "1" ] &amp;&amp; [ "$(grep -c "^- \[x\]" .planning/REQUIREMENTS.md)" = "59" ] &amp;&amp; [ "$(grep -c "| Pending |" .planning/REQUIREMENTS.md)" = "1" ] &amp;&amp; [ "$(grep -c "| Satisfied |" .planning/REQUIREMENTS.md)" = "59" ] &amp;&amp; grep -q "| SAFE-03 | Phase 8 | Pending |" .planning/REQUIREMENTS.md &amp;&amp; echo OK'</automated>
  </verify>

  <acceptance_criteria>
    - `grep -c "^- \[ \]" .planning/REQUIREMENTS.md` returns exactly `1`
    - `grep -c "^- \[x\]" .planning/REQUIREMENTS.md` returns exactly `59`
    - `grep -c "| Pending |" .planning/REQUIREMENTS.md` returns exactly `1`
    - `grep -c "| Satisfied |" .planning/REQUIREMENTS.md` returns exactly `59`
    - `grep "| SAFE-03 | Phase 8 | Pending |" .planning/REQUIREMENTS.md` returns the SAFE-03 row (deferral-preserving)
    - `grep -q "Milestone v1.0 status sync (Phase 07 plan 07-06)" .planning/REQUIREMENTS.md`
  </acceptance_criteria>

  <done>
    REQUIREMENTS.md v1 Requirements section has 59 `[x]` + 1 `[ ]` (SAFE-03); traceability table has 59 `Satisfied` + 1 `Pending` (SAFE-03); audit-reference footer appended.
  </done>
</task>

<task type="auto">
  <name>Task 2: Update ROADMAP.md Progress table and Phase 5 plan checkboxes</name>

  <read_first>
    - .planning/ROADMAP.md  (lines 111-114 Phase 5 plans, 168-178 Progress table)
    - .planning/v1.0-MILESTONE-AUDIT.md  (§Phase-Level Status table — UAT dates per phase)
    - .planning/phases/04-db-parts-hardening/04-VERIFICATION.md  (extract completed/verified date if present)
  </read_first>

  <files>.planning/ROADMAP.md</files>

  <action>
    **Step 1: Extract Phase 4 completion date.**
    ```bash
    grep -E "^(verified|completed|date|status):" .planning/phases/04-db-parts-hardening/04-VERIFICATION.md
    ```
    Capture the date. If none is present in the frontmatter, fall back to:
    ```bash
    git log --format="%ad" --date=short -- .planning/phases/04-db-parts-hardening/04-VERIFICATION.md | head -1
    ```
    Use the resulting ISO date (likely `2026-04-22` based on commit history between Phase 3 close at 2026-04-22 and Phase 5 UAT at 2026-04-23).

    **Step 2: Flip Phase 5 plan checkboxes in Phase Details.**

    Currently (lines 111-114):
    ```markdown
    - [ ] 05-01-admin-split-PLAN.md — ADMIN-01/02/03/04: ...
    - [ ] 05-02-pyjwt-migration-PLAN.md — AUTH-04: ...
    - [ ] 05-03-api-contract-generator-PLAN.md — AUTH-05/06: ...
    - [ ] 05-04-auth-split-PLAN.md — AUTH-01/02/03: ...
    ```

    Flip each of these four lines from `- [ ]` to `- [x]`. Use the Edit tool (one per line is fine; four edits total).

    Also update the Phase 5 top-level bullet (line ~19): currently `- [ ] **Phase 5: Structural Router Splits** - ...`. Flip to `- [x]`.

    Similarly check Phase 1, 2, 6 top-level bullets on lines 15, 16, 20:
    ```markdown
    - [ ] **Phase 1: Safety Nets & CI Hardening** - ...
    - [ ] **Phase 2: Observability** - ...
    - [ ] **Phase 6: Frontend Cleanup & Final CI Gates** - ...
    ```
    Flip all three to `- [x]`. (Phase 3 and 4 are already `[x]`.)

    Verify the full set of top-level phase bullets after Steps 2:
    ```bash
    grep -E "^- \[(x| )\] \*\*Phase [0-9]+:" .planning/ROADMAP.md
    ```
    Expected output:
    ```
    - [x] **Phase 1: Safety Nets & CI Hardening** - ...
    - [x] **Phase 2: Observability** - ...
    - [x] **Phase 3: Non-Breaking Internal Improvements** - ...
    - [x] **Phase 4: DB & Parts Hardening** - ...
    - [x] **Phase 5: Structural Router Splits** - ...
    - [x] **Phase 6: Frontend Cleanup & Final CI Gates** - ...
    - [ ] **Phase 7: v1.0 Residue Cleanup & Audit-Drift Sync** - ...
    - [ ] **Phase 8: Frontend Coverage Expansion (SAFE-03)** - ...
    ```

    **Step 3: Update the Progress table (lines ~168-178).**

    Replace the current table with:
    ```markdown
    | Phase | Plans Complete | Status | Completed |
    |-------|----------------|--------|-----------|
    | 1. Safety Nets & CI Hardening | 8/8 | Complete | 2026-04-23 |
    | 2. Observability | 5/5 | Complete | 2026-04-23 |
    | 3. Non-Breaking Internal Improvements | 5/5 | Complete | 2026-04-22 |
    | 4. DB & Parts Hardening | 6/6 | Complete | <PHASE_4_DATE> |
    | 5. Structural Router Splits | 4/4 | Complete | 2026-04-23 |
    | 6. Frontend Cleanup & Final CI Gates | 6/6 | Complete | 2026-04-23 |
    | 7. v1.0 Residue Cleanup & Audit-Drift Sync | 6/6 | In progress | - |
    | 8. Frontend Coverage Expansion (SAFE-03) | 0/TBD | Not started | - |
    ```

    Substitute `<PHASE_4_DATE>` with the date extracted in Step 1 (expected: `2026-04-22`).

    **Step 4: Verify.**
    ```bash
    grep -cE "^\| [1-6]\. .*\| Complete \|" .planning/ROADMAP.md   # MUST return 6
    grep -cE "^\| 7\. .*\| In progress \|" .planning/ROADMAP.md     # MUST return 1
    grep -cE "^\| 8\. .*\| Not started \|" .planning/ROADMAP.md    # MUST return 1
    ```

    Also run `grep -cE "^- \[x\] \*\*Phase" .planning/ROADMAP.md` — must return 6 (Phases 1-6).
  </action>

  <verify>
    <automated>bash -c 'set -e; [ "$(grep -cE "^\| [1-6]\. .*\| Complete \|" .planning/ROADMAP.md)" = "6" ] &amp;&amp; [ "$(grep -cE "^\| 7\. .*\| In progress \|" .planning/ROADMAP.md)" = "1" ] &amp;&amp; [ "$(grep -cE "^- \[x\] \*\*Phase" .planning/ROADMAP.md)" = "6" ] &amp;&amp; echo OK'</automated>
  </verify>

  <acceptance_criteria>
    - `grep -cE "^\| [1-6]\. .*\| Complete \|" .planning/ROADMAP.md` returns `6`
    - `grep -cE "^\| 7\. .*\| In progress \|" .planning/ROADMAP.md` returns `1`
    - `grep -cE "^\| 8\. .*\| Not started \|" .planning/ROADMAP.md` returns `1`
    - `grep -cE "^- \[x\] \*\*Phase" .planning/ROADMAP.md` returns `6` (Phases 1-6 top-level bullets are now `[x]`)
    - `grep -cE "^- \[ \] \*\*Phase" .planning/ROADMAP.md` returns `2` (Phases 7 and 8)
    - `grep -c "^- \[x\] 05-0" .planning/ROADMAP.md` returns `4` (Phase 5's four plan checkboxes flipped)
    - `grep -cE "^- \[ \] 05-0" .planning/ROADMAP.md` returns `0`
    - Every Complete row has a date in `2026-04-XX` format — verify with `grep -E "^\| [1-6]\. .*\| Complete \| 2026-04-[0-9]{2} \|" .planning/ROADMAP.md` returns `6`.
  </acceptance_criteria>

  <done>
    ROADMAP.md top-level phase bullets 1-6 are `[x]`; Phase 5 plan-list checkboxes are `[x]`; Progress table shows 6 Complete rows (1-6) with dates, 1 In progress (Phase 7), 1 Not started (Phase 8).
  </done>
</task>

<task type="auto">
  <name>Task 3: Commit REQUIREMENTS.md + ROADMAP.md as one atomic doc-sync commit</name>

  <read_first>
    - CLAUDE.md  (conventional-commits guidance if present — this phase already uses `fix(07):` / `docs(07):` prefixes in recent history)
  </read_first>

  <files>(no files modified; git stage + commit only)</files>

  <action>
    Run:
    ```bash
    git add .planning/REQUIREMENTS.md .planning/ROADMAP.md
    git diff --cached --stat  # verify only these two files are staged
    git commit -m "$(cat <<'EOF'
    docs(07-06): sync REQUIREMENTS.md + ROADMAP.md with milestone v1.0 verification reality

    Per the 2026-04-24 milestone audit (.planning/v1.0-MILESTONE-AUDIT.md §Documentation Drift):

    REQUIREMENTS.md:
    - Traceability table: 59 rows flipped Pending -> Satisfied
    - v1 Requirements section: 59 checkboxes flipped [ ] -> [x]
    - SAFE-03 row preserved as Pending / [ ] (moved to Phase 8 per ROADMAP.md)

    ROADMAP.md:
    - Top-level phase bullets 1/2/5/6 flipped [ ] -> [x] (Phases 3 and 4 were already [x])
    - Phase 5 plan-list checkboxes 05-01..05-04 flipped [ ] -> [x]
    - Progress table: Phase 1/2/4/5/6 rows updated from Not started to Complete with dates
      - Phase 1 completed 2026-04-23 (UAT signed)
      - Phase 2 completed 2026-04-23 (UAT signed)
      - Phase 4 completed <PHASE_4_DATE> (no human UAT required)
      - Phase 5 completed 2026-04-23 (UAT signed)
      - Phase 6 completed 2026-04-23 (UAT signed)
    - Phase 7 left as In progress (this commit is part of Phase 7)

    No code changes. Closes DOC-01, DOC-02, DOC-03 tech-debt items in
    .planning/v1.0-MILESTONE-AUDIT.md.
    EOF
    )"
    ```

    If the user has commit-sign or hook requirements, respect them — do NOT add `--no-verify`.

    After commit, verify:
    ```bash
    git log -1 --stat
    git status  # must be clean
    ```
  </action>

  <verify>
    <automated>git log -1 --format="%s" | grep -q "docs(07-06): sync REQUIREMENTS.md + ROADMAP.md"</automated>
  </verify>

  <acceptance_criteria>
    - `git log -1 --format="%s"` starts with `docs(07-06): sync REQUIREMENTS.md`
    - `git log -1 --stat` shows only `.planning/REQUIREMENTS.md` and `.planning/ROADMAP.md` in the diff
    - `git status` reports clean working tree
  </acceptance_criteria>

  <done>
    One atomic commit lands the REQUIREMENTS.md and ROADMAP.md sync.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Planning docs → git history | Commit is scoped to two .planning/ files; no production code touched. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-06-01 | Tampering | SAFE-03 classification | mitigate | SAFE-03 is kept `Pending` / `[ ]` with a footer note referencing Phase 8. A future skim of REQUIREMENTS.md cannot misread it as satisfied — the single unchecked row + audit-reference footer provide two independent signals. |
| T-07-06-02 | Repudiation | Doc drift vs verification reality | mitigate | Without this sync, `/gsd-complete-milestone` would ship a milestone archive where the audit frontmatter says `60/60 satisfied` but REQUIREMENTS.md says all 60 are `Pending`. Reviewers could accuse the audit of falsely claiming satisfaction. This sync aligns the three sources (VERIFICATION.md × SUMMARY.md × REQUIREMENTS.md) and removes the discrepancy. |

**No new attack surface.** Documentation-only changes; no behavior change, no endpoint change, no dependency change.
</threat_model>

<verification>
End-to-end after all three tasks:
```bash
# REQUIREMENTS.md invariants
[ "$(grep -c '| Pending |' .planning/REQUIREMENTS.md)" = "1" ] && echo OK-1
[ "$(grep -c '| Satisfied |' .planning/REQUIREMENTS.md)" = "59" ] && echo OK-2
[ "$(grep -c '^- \[ \]' .planning/REQUIREMENTS.md)" = "1" ] && echo OK-3
[ "$(grep -c '^- \[x\]' .planning/REQUIREMENTS.md)" = "59" ] && echo OK-4

# ROADMAP.md invariants
[ "$(grep -cE '^\| [1-6]\. .*\| Complete \|' .planning/ROADMAP.md)" = "6" ] && echo OK-5
[ "$(grep -cE '^- \[x\] \*\*Phase' .planning/ROADMAP.md)" = "6" ] && echo OK-6

# Commit invariant
git log -1 --format="%s" | grep -q "docs(07-06): sync REQUIREMENTS.md" && echo OK-7
```
All 7 checks must print `OK-N`.
</verification>

<success_criteria>
- Phase 7 success criterion 9 closed: REQUIREMENTS.md traceability table flipped 59 `Pending → Satisfied`; 59 checkboxes `[ ] → [x]` (SAFE-03 preserved); ROADMAP.md Progress table shows Phase 1/2/4/5/6 Complete with dates.
</success_criteria>

<output>
After completion, create `.planning/phases/07-v1-residue-cleanup/07-06-SUMMARY.md`. Frontmatter must include `tech_debt_items_closed: [DOC-01, DOC-02, DOC-03]` and record the before/after grep counts from Task 1 Step 1.
</output>
