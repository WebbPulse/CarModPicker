---
estimated_steps: 26
estimated_files: 5
skills_used: []
---

# T06: Final test gauntlet, milestone validation + summary, requirement promotion

Close M002. Run the full local gauntlet, then write the milestone-close artifacts and promote requirement statuses.

**Step 1 — Gauntlet:** Run sequentially and capture exit codes. Each MUST exit 0 (lint MUST be at the MEM062 baseline of 108 errors with zero NEW errors in S13-touched files):

- Backend: `TESTING=true pytest -n auto --rootdir=backend -q --no-cov` from project root
- Frontend type-check: `cd frontend && npm run type-check`
- Frontend unit: `cd frontend && npm test -- --run`
- Frontend e2e: `cd frontend && npm run test:e2e` (must pass at all 3 viewports — mobile/tablet/desktop)
- Frontend lint: `cd frontend && npm run lint` — exit code 1 is acceptable IF total errors == 108 (MEM062 baseline) AND grep of the lint output shows zero errors in S13-touched files (only T03 changes ViewPart.tsx + parts.ts + parts.test.ts + ViewPart.priceSummary.test.tsx)
- Crawler audit: `cd backend && python -m app.crawlers.compliance_audit` exits 0 reporting 108/108

Capture each command + exit code + verdict to `.gsd/milestones/M002/slices/S13/uat-evidence/gauntlet-evidence.json` as a JSON array (command/exitCode/verdict/durationMs).

**Step 2 — Promote requirement statuses via gsd_requirement_update:** For each of the 12 active M002 requirements, set status='validated' with a notes field referencing the evidence path:
- R002 (universal extractor) — evidence: T01 extraction-and-alert.log + T04 compliance-audit-stdout.txt
- R003 (108-adapter compliance) — evidence: T04 compliance-audit-stdout.txt
- R005 (backfill started) — evidence: T05 backfill-run.log + backfill-cursor-snapshot.json
- R006 (admin extraction-health) — evidence: T04 admin-extraction-health.json
- R008 (sparkline + delta line) — evidence: T01 parts-sparkline.png + S06 e2e baselines
- R009 (per-part detail view + retailer breakdowns + 60d caveat) — evidence: T01 parts-detail-breakdown.png + S06 e2e baselines
- R010 (price-drop alerts end-to-end) — evidence: T01 inbox-email-render.png + extraction-and-alert.log
- R016 (admin shell on new design system) — evidence: T01/T04 admin-extraction-health-ui.png + S11 e2e baselines
- R017 (all ~17 pages on new design system) — evidence: S12 vitest grep-guard test + ESLint no-restricted-imports + components/common+buttons deleted
- R018 (crawler test suite) — evidence: gauntlet pytest backend exit 0 + S03/S04 test counts in summaries
- R019 (perf gate at 10×) — evidence: T02 perf-gate-PASSED.json (or carry-forward as needs-remediation if FAIL)
- R020 (keyboard nav + focus + escape on dialogs) — evidence: S09/S10/S11 e2e desktop keyboard tests + Radix focus-trap behavior

**Step 3 — Author M002-VALIDATION.md via gsd_validate_milestone:** Set verdict='passed' (assuming gauntlet greens AND R019 PASSED — otherwise verdict='needs-remediation' with R036 in the remediation plan). Fill all required sections: successCriteriaChecklist (against the 9 M002 success criteria), sliceDeliveryAudit (S01-S13 — each shipped what was promised), crossSliceIntegration (T01 demo proves the full loop), requirementCoverage (the 12 promotions above + acknowledgement that the 12 still-active R001/R004/R007/R011/R012/R013/R014/R015 may have been covered by prior slice closures — confirm against REQUIREMENTS.md). verdictRationale: 'Live UAT exercised the full extraction → ingest → UI → alert email loop; perf gate met R019 budget; all S08-S12 design-system surfaces verified at 3 viewports; 108-adapter compliance held; backfill started.' Also fill verificationClasses if any prior slice's verification was deferred to S13.

**Step 4 — Author M002-SUMMARY.md via gsd_complete_milestone:** Set verificationPassed=true (assuming Step 3's verdict is 'passed'). Cross-link the uat-evidence/ files. Document carry-forward (NOT blockers): AccountAlerts MEM097 self-cancel useEffect bug (deferred to a future slice that touches that file), lint baseline 108 errors per MEM062 (pre-existing, not regression), backfill long-tail completion (R005 says 'started, not complete' — long-running completion is post-merge), light theme R035 (deferred carry-forward).

**Step 5 — Save M002-close decisions/learnings:** Append any S13-surfaced decisions to `.gsd/DECISIONS.md` via `gsd_save_decision` (e.g., D-XX 'M002 close: live UAT verifies SES path with `+`-suffix fixture inbox' if that decision is not yet captured). Surface any new gotchas via `capture_thought` (e.g., the live retailer fetch vs archive_rescrape vs sample-data trade-off if that picked up new sharp edges in T01).

AUTONOMOUS-MODE NOTE: gsd_validate_milestone and gsd_complete_milestone are DB-write tools that regenerate the markdown — do NOT hand-edit M002-VALIDATION.md or M002-SUMMARY.md. The auto-mode executor calls the tools with full payloads.

## Inputs

- ``.gsd/milestones/M002/slices/S13/uat-evidence/extraction-and-alert.log` — T01 evidence`
- ``.gsd/milestones/M002/slices/S13/uat-evidence/perf-gate-PASSED.json` — T02 evidence (or perf-gate-FAILED.json)`
- ``.gsd/milestones/M002/slices/S13/uat-evidence/compliance-audit-stdout.txt` — T04 evidence`
- ``.gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health.json` — T04 evidence`
- ``.gsd/milestones/M002/slices/S13/uat-evidence/backfill-run.log` — T05 evidence`
- ``.gsd/REQUIREMENTS.md` — current statuses of R002/R003/R005/R006/R008/R009/R010/R016/R017/R018/R019/R020`
- ``.gsd/milestones/M002/M002-ROADMAP.md` — slice delivery audit reference`
- ``.gsd/milestones/M002/M002-CONTEXT.md` — original milestone success criteria`

## Expected Output

- ``.gsd/REQUIREMENTS.md` — 12 requirements promoted from active to validated (regenerated by gsd_requirement_update)`
- ``.gsd/DECISIONS.md` — any S13-surfaced decisions appended (regenerated by gsd_save_decision)`
- ``.gsd/milestones/M002/M002-VALIDATION.md` — milestone validation artifact (rendered by gsd_validate_milestone)`
- ``.gsd/milestones/M002/M002-SUMMARY.md` — milestone close artifact (rendered by gsd_complete_milestone)`
- ``.gsd/milestones/M002/slices/S13/uat-evidence/gauntlet-evidence.json` — JSON array of gauntlet command results`

## Verification

test -f .gsd/milestones/M002/M002-VALIDATION.md && test -f .gsd/milestones/M002/M002-SUMMARY.md && test -f .gsd/milestones/M002/slices/S13/uat-evidence/gauntlet-evidence.json && python -c 'import json;d=json.load(open(".gsd/milestones/M002/slices/S13/uat-evidence/gauntlet-evidence.json"));assert all(c["exitCode"]==0 or (c["command"].endswith("npm run lint") and c["verdict"]=="baseline") for c in d)'

## Observability Impact

M002-VALIDATION.md and M002-SUMMARY.md are the durable record of milestone close. Future agents inspecting M002's outcome read these (regenerated by the gsd_validate_milestone / gsd_complete_milestone tools — never hand-edited). gauntlet-evidence.json captures the full sweep of test/lint/type-check exit codes at the close gate; future agents diagnosing 'did M002 ship clean?' read this artifact.
