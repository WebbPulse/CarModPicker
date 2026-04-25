---
phase: 8
slug: frontend-coverage-expansion
status: verified
threats_open: 0
asvs_level: 1
created: 2026-04-24
---

# Phase 8 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Phase 8 is a test-coverage-only phase (SAFE-03). No new network endpoints, no auth paths, no schema changes, no production runtime code added — only Vitest test files, shared test scaffolding (`frontend/src/test/**`), the SAFE-03 threshold gate uncomment in `frontend/vitest.config.ts`, and reporting artifacts (`08-COVERAGE-*.txt`, `08-FAIL-FORCE-PROOF.txt`). The attack surface of the deployed application is unchanged.

Threat register below enumerates the three known threat patterns for this stack (per `08-RESEARCH.md` §"Known Threat Patterns") and confirms their standard mitigations are in place.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Test runtime ↔ source | Vitest jsdom workers import application source under test | None real — all network/auth values are fixtures from `frontend/src/test/mocks/**` and `test-mocks.ts` |
| CI runner ↔ repo | GitHub Actions runs `npm test -- --run --coverage` on every PR | Public source + lockfiles only; no secrets read by tests |

No new production trust boundaries introduced.

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-08-01 | Information Disclosure | Test fixtures (any of the 78 test files) | mitigate | Tests use synthetic data from `frontend/src/test/mocks/api.ts` and `frontend/src/test/mocks/admin/*` (see RESEARCH §Known Threat Patterns row 1). No real tokens, real PII, or real backend URLs in any test file. Verified: `grep -rE "Bearer [A-Za-z0-9_-]{20,}\|sk-\|eyJ[A-Za-z0-9_-]{20,}" frontend/src/**/*.test.* frontend/src/test/**` returns no matches. | closed |
| T-08-02 | Spoofing | `frontend/src/api/client.ts` request interceptor | mitigate | The Authorization-header interceptor branch is explicitly exercised by `frontend/src/api/client.test.ts` per RESEARCH §Known Threat Patterns row 2 — a regression that drops the header would now break the suite and (post-08-20) breach SAFE-03 thresholds. | closed |
| T-08-03 | Information Disclosure | Vitest snapshots | accept | Per `08-CONTEXT.md`, Phase 8 introduces no `toMatchSnapshot()` calls (verified — `grep -rn "toMatchSnapshot\|toMatchInlineSnapshot" frontend/src/**/*.test.*` returns no matches). Snapshot-leakage threat is N/A for this phase; documented in Accepted Risks. | closed |
| T-08-04 | Tampering | SAFE-03 coverage gate (`frontend/vitest.config.ts` thresholds + `.github/workflows/frontend-ci.yml`) | mitigate | Gate proven enforcing by `08-FAIL-FORCE-PROOF.txt` (RAISED lines:95 → exit 1 with "does not meet global threshold"; RESTORED lines:60 → exit 0). CI runs `npm test -- --run --coverage` on every PR (frontend-ci.yml:51), so a future PR that drops coverage below D-06 (60/50/50/60) is auto-blocked at the workflow level. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-08-01 | T-08-03 | Snapshot-secret-leakage threat is structurally N/A for Phase 8 — the phase introduces zero `toMatchSnapshot()` calls. Risk re-opens automatically if a future phase introduces snapshot tests. | Tyler Webb | 2026-04-24 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-24 | 4 | 4 | 0 | /gsd-secure-phase 8 (no auditor agent — threats_open: 0 short-circuit per workflow Step 3) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-24
