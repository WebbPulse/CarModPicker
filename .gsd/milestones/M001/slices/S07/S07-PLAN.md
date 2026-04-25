# S07: v1.0 Residue Cleanup & Audit-Drift Sync

**Status:** ✅ completed 2026-04-24
**Goal:** Close 22 tech-debt items from milestone audit; run Nyquist Wave 0; sync REQUIREMENTS / ROADMAP docs.
**Demo:** Milestone audit re-run shows 0 outstanding items; per-adapter parse-failure alarm fan-out terraform plan reviewed; doc drift fixed.

## Must-Haves

- 22 documented follow-up items from `v1.0-MILESTONE-AUDIT.md` closed
- Nyquist Wave 0 close
- Integration advisory A-01 resolved
- WR-04 `init_service_accounts.py` `%d` UUID format-specifier crash fixed (`%s` + cold-start regression test)
- Terraform composite parse-failure alarm → per-adapter `for_each` (operator-gated apply deferred to v1.0 deploy window)
- REQUIREMENTS.md / ROADMAP.md doc sync

## Tasks

> Detail preserved in `.planning/milestones/v1.0-phases/07-v1-residue-cleanup/` (6 PLAN/SUMMARY pairs: 07-01 through 07-06).

## Files Likely Touched

`backend/app/core/init_service_accounts.py`, `terraform/modules/crawler-alarms/`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`
