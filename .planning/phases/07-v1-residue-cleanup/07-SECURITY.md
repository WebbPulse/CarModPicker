---
phase: 07-v1-residue-cleanup
type: security-audit
asvs_level: 1
block_on: critical
threats_total: 18
threats_mitigate: 8
threats_accept: 9
threats_na: 1
threats_closed: 18
threats_open: 0
audited: 2026-04-24
auditor: gsd-security-auditor
---

# Phase 07 Security Audit — v1 Residue Cleanup

All 18 threats declared across plans 07-01..07-06 verified against implementation.

## Summary

| Plan | Threats | Mitigate | Accept | N/A | Status |
|------|---------|----------|--------|-----|--------|
| 07-01 Operational Bug Verification | 4 | 1 | 3 | 0 | CLOSED |
| 07-02 Code Review Residue | 2 | 1 | 0 | 1 | CLOSED |
| 07-03 Dead Code Cleanup | 4 | 0 | 4 | 0 | CLOSED |
| 07-04 Integration Advisory A-01 | 4 | 2 | 2 | 0 | CLOSED |
| 07-05 Nyquist Validation Close | 2 | 2 | 0 | 0 | CLOSED |
| 07-06 Documentation Drift Sync | 2 | 2 | 0 | 0 | CLOSED |
| **TOTAL** | **18** | **8** | **9** | **1** | **18/18 CLOSED** |

Scope is intentionally low-risk: regression tests + dead-code deletion + doc sync + terraform alarm fan-out + observability wrapping. No new production endpoints, no new auth flows, no new external inputs.

## Mitigate Threats (verified in code)

| Threat ID | Category | Evidence |
|-----------|----------|----------|
| T-07-01-02 | Tampering — free-tier cap bypass regression pin | `backend/tests/api/endpoints/test_build_lists.py:832` `test_copy_free_tier_cap`; asserts 402 at line 868 and "Free accounts are limited to 1 build list" message at line 878 |
| T-07-02-01 | Tampering — divergent count/main filter predicates | `backend/app/api/endpoints/build_lists.py:155` `def _apply_build_list_filters`; called at line 177 (count) + line 191 (main). Static regression: `backend/tests/test_build_lists_in01_helper.py` (3 tests, 79 lines) pins helper def count == 1 and call-site count >= 3 |
| T-07-04-01 | Repudiation — lifespan orphan-sweep log forensics | `backend/app/main.py:105` `with bg_log_context("orphan-schedule-sweep")`, `backend/app/main.py:118` `with bg_log_context("orphan-jobs-sweep")` (grep count of `bg_log_context("orphan-` == 2, exactly as declared). Regression: `backend/tests/test_lifespan_bg_log_context.py` (3 tests, 136 lines) captures `request_id_var.get()` during each sweep and asserts the expected `bg:orphan-*-sweep:-` tag |
| T-07-04-03 | Spoofing — AdapterName dimension producer/consumer parity | Producer: `backend/app/core/cloudwatch_emf.py:125` `"AdapterName": adapter_name`. Consumer: `terraform/monitoring.tf:218` and `:233` `AdapterName = each.value` on both `ingested` and `failures` metric_query maps. Pinned by `backend/tests/test_cloudwatch_emf.py:90` `assert set(dims) == {"AdapterName", "Environment", "RunType"}` |
| T-07-05-01 | Tampering — false frontmatter flip on failed validation | All 6 phase VALIDATION.md frontmatters show `status: accepted`, `wave_0_complete: true`, `nyquist_compliant: true`. `/gsd-validate-phase` blocking gate executed per plan 07-05 checkpoint; each flip reviewed before approval |
| T-07-05-02 | Repudiation — which commits/tests closed each Nyquist phase | Git log shows per-phase atomic commits (`git log --grep="docs(07-05)"` returns 7 commits: one per phase 01-06 + plan wrap-up). Discoverable audit trail per VALIDATION.md execution log sections |
| T-07-06-01 | Tampering — SAFE-03 misread as satisfied | `.planning/REQUIREMENTS.md:18` retains `- [ ] **SAFE-03**`; `.planning/REQUIREMENTS.md:183` retains `\| SAFE-03 \| Phase 8 \| Pending \|`; audit-reference footer at line 261 ("Milestone v1.0 status sync") names the audit source and date. Single `[ ]` + single `Pending` row + footer = three independent signals |
| T-07-06-02 | Repudiation — REQUIREMENTS.md / VERIFICATION.md drift | Counts aligned: `Pending` count == 1 (SAFE-03), `Satisfied` count == 59; ROADMAP.md Progress table shows 6/6 `Complete` rows for Phases 1-6 with dated entries |

## Accepted Risks (rationale in PLAN threat_model)

Each accept threat's rationale was reviewed for coherence and checked for contradicting evidence in code. None found.

| Threat ID | Category | Rationale Source | Supporting Evidence |
|-----------|----------|------------------|---------------------|
| T-07-01-01 | Information Disclosure — UUID+username in log | 07-01-PLAN threat_model (no PII, %s formatter, existing behavior). | `backend/app/core/init_service_accounts.py:53,57,59` — all three log calls use `%s` (no `%d`); grep for `%d` in file = 0 matches |
| T-07-01-03 | Denial of Service — 10-thread concurrency test | 07-01-PLAN threat_model (test-only, 30s budget, opt-in Postgres). | `backend/tests/services/test_part_linker_concurrency.py:33` `pytestmark = pytest.mark.postgres` (opt-in); `timeout=30` deadlock guard present |
| T-07-01-04 | Elevation of Privilege — test deletes service-account rows | 07-01-PLAN threat_model (in-memory SQLite only, standard pytest isolation). | `backend/tests/crawlers/test_crawler_user_fallback.py` uses `db_session` fixture (SQLite in-memory per test) |
| T-07-03-01 | Tampering — dead-code removal | 07-03-PLAN threat_model (grep-verified zero callers at planning + execution time). | Grep confirms zero external callers for all 11 removed helpers |
| T-07-03-02 | Elevation of Privilege — removed auth/admin helpers | 07-03-PLAN threat_model (helpers were never wired to any route; live enforcement is `get_current_admin_user`). | `get_admin_dependencies` / `verify_entity_ownership_or_admin` return 0 grep matches in `backend/app/` and `backend/tests/` |
| T-07-03-03 | Spoofing — vote/report helpers removed | 07-03-PLAN threat_model (zero callers; votes/reports handled by `base_vote_router` / `base_report_router`). | `handle_vote_operation` / `remove_vote_operation` / `handle_report_creation` return 0 grep matches outside the deleted definitions |
| T-07-03-04 | Information Disclosure — conftest.py 1.x→2.0 migration | 07-03-PLAN threat_model (pure syntactic change; same SQL emitted). | `grep -cE '^[^#]*\b(db\|db_session)\.query\(' backend/tests/conftest.py` returns 0 (migration complete); test-only file |
| T-07-04-02 | Denial of Service — per-adapter alarm fan-out | 07-04-PLAN threat_model (SNS can absorb ~108 alarms; per-adapter independence). | `terraform/monitoring.tf:185` `var.disabled_parse_alarms` opt-out; line 199 `actions_enabled = var.enable_per_adapter_alarms` kill-switch (added post-plan per WR-02 fix in phase 07 git history) |
| T-07-04-04 | Information Disclosure — adapter_names.txt committed in repo | 07-04-PLAN threat_model (retailer names already discoverable externally; no secrets). | `terraform/adapter_names.txt` contains 108 lowercase adapter names (e.g. `034motorsport`, `27won`, `a90shop`). No API keys, URLs, or credentials |

## N/A

| Threat ID | Category | Reason |
|-----------|----------|--------|
| T-07-02-02 | Spoofing | Plan 07-02 is a static regression test pinning an existing helper. No auth or identity surface changed. |

## Threat Flags (from SUMMARY.md)

- 07-01: no `## Threat Flags` section (no new flags raised).
- 07-02: no `## Threat Flags` section (no new flags raised).
- 07-03: no `## Threat Flags` section (no new flags raised).
- 07-04: "None — all changes strengthen existing trust boundaries." (explicit no-flag statement).
- 07-05: no `## Threat Flags` section (no new flags raised).
- 07-06: no `## Threat Flags` section (no new flags raised).

No unregistered flags detected.

## Accepted Risks Log

(This section exists to satisfy the `accept` disposition requirement. Rationale references live in the plan-level `<threat_model>` blocks. The risks below are active-in-production artifacts of phase 07 changes.)

1. **T-07-04-02 per-adapter alarm fan-out DoS via alarm noise** — 108 SNS alarms. Kill-switch available via `var.enable_per_adapter_alarms=false`; per-adapter opt-out via `var.disabled_parse_alarms`. Monthly cost: ~$10.80.
2. **T-07-04-04 adapter_names.txt committed** — retailer names in plaintext. Already public information (scrapable from product pages). Committed so PR diff shows adapter adds/removes.

All other `accept` threats are test-only or build-time cleanups with no live production surface.

## Audit Complete

- All 18 threats classified and verified per declared disposition.
- Zero open threats.
- Zero unregistered flags.
- No implementation gaps requiring escalation.
