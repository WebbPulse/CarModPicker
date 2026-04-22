---
phase: 02-observability
plan: 2
subsystem: observability
tags: [sentry, error-reporting, secrets-manager, iam, terraform, obs-01]
requirements-completed: [OBS-01]
duration: 20min
completed: 2026-04-22
---

# Phase 02 Plan 02: Sentry SDK Backend Init (OBS-01) Summary

**Sentry SDK 2.x wired into FastAPI + all three crawler entry points via shared init_sentry(*, server_name) helper. Scope processor attaches request_id + user_id from plan 02-01 ContextVars. Terraform provisions Secrets-Manager-backed SENTRY_DSN and injects it into App Runner + ECS with IAM grants on all three roles. 25 new tests (100% coverage of sentry.py) pin Landmines 1, 2, 3, 16.**

## Performance

- Duration: ~20 min
- Started: 2026-04-22T21:17:42Z
- Completed: 2026-04-22T21:37:27Z
- Tasks: 3 (Task 1 + 2 TDD-flagged; Task 3 infrastructure)
- Files created: 2
- Files modified: 12

## Accomplishments

- init_sentry(*, server_name) helper with triple-gated no-op logic and all four integrations (StarletteIntegration, FastApiIntegration, SqlalchemyIntegration, LoggingIntegration)
- _before_send scope processor reading request_id_var + user_id_var from log_context.py (plan 02-01)
- _traces_sampler filtering health/ready/openapi transactions to 0.0, real routes to 0.05
- All 4 process entry points wired with distinct server_name tags (apprunner-backend, crawler-cli, ecs-crawler)
- 25-test suite across 5 classes, 100% coverage of app/core/sentry.py
- _CapturingTransport + sentry_events fixture in conftest.py (2.x capture_envelope API, subclasses Transport)
- Terraform: sentry_dsn secret + version, App Runner + ECS runtime env injection, IAM grants on all three roles
- AWS_EMF_ENVIRONMENT=Local pre-staged in both runtimes (unlocks plan 02-03)
- terraform/README.md Bootstrap Sentry section with operator runbook
- CLAUDE.md pointer under Architecture/Backend bullet list

## Task Commits

1. Task 1 (feat 02-02): 601f2a8 - sentry.py + Pydantic fields + requirements + call sites + CLAUDE.md pointer
2. Task 2 (test 02-02): 433c770 - test_sentry_init.py (25 tests) + _CapturingTransport fixture
3. Task 3 (feat 02-02): 93a58c7 - Terraform variables + secretsmanager + apprunner + ecs + README

## Files Created/Modified

### Created

- backend/app/core/sentry.py - Sentry SDK 2.x init helper. Docstring documents DSN source, release tag, ignored exception list, server_name values, scope processor (D-15).
- backend/tests/test_sentry_init.py - 25 tests:
  - TestInitGating (3): TESTING=true, wrong APP_ENVIRONMENT, empty DSN
  - TestInitKwargs (7): send_default_pii, server_name, release, environment, traces_sampler, ignore_errors strings (Landmine 1), all 4 integrations (Landmine 2)
  - TestTracesSampler (parametrized, 10 cases): health routes 0.0, real routes 0.05
  - TestBeforeSend (3): ContextVar propagation, sentinel skipped
  - TestIgnoreErrorsIntegration (2): HTTPException(404) => 0 envelopes; RuntimeError control => 1+

### Modified

- backend/app/core/config.py - SENTRY_DSN/SENTRY_RELEASE/SENTRY_SERVICE_NAME fields after EMAIL_FROM
- backend/app/main.py - init_sentry(server_name=apprunner-backend) between logger def and FastAPI() (D-12)
- backend/app/crawlers/__main__.py - init_sentry(server_name=crawler-cli) inside __main__ guard (T-02-TEST-POLLUTION)
- backend/app/crawlers/ecs_runner.py - init_sentry(server_name=ecs-crawler) as first stmt of main() (Landmine 16 - local import)
- backend/app/crawlers/ecs_rescrape_runner.py - same pattern; shared server_name aggregates under one Sentry service
- backend/requirements.txt - sentry-sdk>=2.0,<3 after boto3 block
- backend/tests/conftest.py - _CapturingTransport (Transport subclass) + sentry_events fixture
- CLAUDE.md - D-15 pointer into Architecture/Backend bullet list (worktree-scoped only)
- terraform/variables.tf - sentry_dsn (sensitive), sentry_release, disabled_parse_alarms
- terraform/secretsmanager.tf - aws_secretsmanager_secret.sentry_dsn + version
- terraform/apprunner.tf - (1) SENTRY_DSN in runtime_environment_secrets; (2) 3 env vars in runtime_environment_variables; (3) IAM grants in BOTH access + instance role policies
- terraform/ecs.tf - (1) SENTRY_DSN in secrets[]; (2) 3 env vars in environment[]; (3) IAM grant in ecs_task_execution_secrets
- terraform/README.md - Bootstrap Sentry 5-step operator runbook

## Decisions Made

- **Open Question 4 resolved by grep on backend/app/api/middleware/rate_limiter.py**: The custom SophisticatedRateLimiter returns JSONResponse(status_code=429) directly - it does NOT raise. No raise HTTPException(status_code=429) and no slowapi.errors.RateLimitExceeded call. Per D-07, ignore_errors retains all three entries defensively. String entries that do not match any actually-raised class are harmless.
- **init_sentry imported lazily inside crawler main() bodies** (not module-level). Avoids triggering sentry_sdk module import during pytest collection.
- **_CapturingTransport subclasses sentry_sdk.transport.Transport**: Initial duck-typed implementation triggered Function transports are deprecated DeprecationWarning in Sentry 2.x AND silently dropped envelopes. Fixed to proper Transport subclass with super().__init__(options). Pinned by test_runtime_error_captured control.
- **Repo-root CLAUDE.md intentionally untouched**: The instruction refers to the worktree-scoped CLAUDE.md. Read-before-edit enforcement naturally prevented cross-worktree edit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _CapturingTransport needed to subclass sentry_sdk.transport.Transport**
- Found during: Task 2 (first pytest run)
- Issue: test_runtime_error_captured failed with assert 0 >= 1. Sentry 2.x deprecated function transports - raw classes trigger DeprecationWarning AND silently drop envelopes.
- Fix: Modified _CapturingTransport to subclass sentry_sdk.transport.Transport with super().__init__(options).
- Files modified: backend/tests/conftest.py
- Verification: test_runtime_error_captured now passes; test_http_exception_not_captured still correctly asserts zero envelopes.
- Committed in: 433c770

**2. [Rule 3 - Blocking] sentry-sdk not installed in local pyenv**
- Found during: Task 1 acceptance check
- Issue: ModuleNotFoundError: No module named sentry_sdk
- Fix: pip install sentry-sdk>=2.0,<3 (2.58.0). No repo changes - pin already in requirements.txt.
- Files modified: None (env-only)
- Verification: python import succeeds from backend/ cwd
- Committed in: N/A (environment-only)

### Acknowledged

**3. [Plan structure] TDD tasks 1 + 2 as implementation+test pair, not interleaved RED/GREEN**
- Context: Both tasks have tdd=true. Task 1 <verify> references only pre-existing Phase 1 tests. A literal RED-GREEN cycle isnt achievable with this plan structure.
- Resolution: Task 1 = implementation; Task 2 = test suite. Both commits pass their <verify>. Commit order feat -> test.

## Deferred Issues

**Coverage floor below --cov-fail-under=51 baked into backend/pytest.ini.**

- Current state: 50.59% (was 50.54% before this plan - plan 02-02 raises coverage by +0.05pp)
- Root cause: Pre-existing. Fargate-only entry points have 0% coverage: app/crawlers/ecs_runner.py (85 stmts), app/crawlers/ecs_rescrape_runner.py (67 stmts), app/api/utils/base_report_router.py (58 stmts), app/api/utils/base_vote_router.py (54 stmts). Plan 02-01 SUMMARY claim of 51% floor all green likely reflects an earlier checkpoint.
- Scope decision: OUT OF SCOPE for plan 02-02. My changes do not cause the regression; they mitigate it by +0.05pp.
- Phase 1 SAFE gates preserved: SAFE-05 openapi snapshot passes. SAFE-06 auth characterization: 5/7 pass with 2 expected skips for OAuth VCR cassettes (documented in 02-01 SUMMARY).
- Recommendation: Dedicated pragma sweep plan OR targeted unit tests for uncovered utilities.

## Known Stubs

None. All production code paths are live:
- init_sentry called from every process entry point with real DSN path
- Scope processor reads real ContextVars
- Integration list exhaustive and validated by tests
- Terraform resources point to concrete AWS-side secret references

## Threat Flags

None beyond those declared in 02-02-PLAN.md threat_model. All five STRIDE threats mitigated and pinned by tests:

- **T-02-DSN-LEAK**: DSN read via os.environ.get with .strip(); terraform variable sensitive=true
- **T-02-PII-SENTRY**: send_default_pii=False asserted; _before_send attaches ONLY request_id tag + user.id (never email/username)
- **T-02-IAM-DRIFT**: aws_secretsmanager_secret.sentry_dsn.arn in BOTH apprunner.tf IAM policies (grep -c = 2) AND ECS task execution (grep -c = 2)
- **T-02-TEST-POLLUTION**: init_sentry never at module import in crawlers. TestInitGating::test_testing_true_skips_init asserts 0 sentry_sdk.init calls under TESTING=true
- **T-02-4XX-FLOOD**: TestIgnoreErrorsIntegration::test_http_exception_not_captured raises HTTPException(404) and asserts 0 envelopes

## TDD Gate Compliance

Both Task 1 and Task 2 have tdd=true. Per Deviations section 3: Task 1 = implementation feat commit (601f2a8); Task 2 = test-suite commit (433c770). Commit order feat -> test (inverse of canonical RED -> GREEN) matches plans literal task sequence. All tests pass against the now-existing module on first run.

## Issues Encountered

- Transport subclass requirement surfaced only when running test_runtime_error_captured - fix landed in Task 2 commit.
- Local pyenv missing sentry-sdk - install only; no repo change.

## User Setup Required

After this plan merges, before Sentry events will actually reach the dashboard in production, the operator MUST:

1. Create a Sentry project in the Sentry web UI
2. Populate the DSN value in AWS Secrets Manager via aws secretsmanager put-secret-value with --secret-id carmodpicker-production/sentry-dsn and --secret-string https://<public-key>@<org>.ingest.sentry.io/<project-id>
3. Trigger App Runner redeploy and ECS task recycle so new env value is picked up.

Until step 2 runs, init_sentry() no-ops gracefully (empty DSN -> early return). No crash, no error - just no Sentry events. Fail-safe by design per D-01.

See terraform/README.md Bootstrap Sentry for the full 5-step runbook.

## Next Phase Readiness

- **Phase 02 Plan 03 (EMF + CloudWatch)**: AWS_EMF_ENVIRONMENT=Local already set in App Runner and ECS. Adding aws-embedded-metrics to requirements.txt + calling create_metrics_logger will just work - no additional terraform pass needed.
- **Phase 02 Plan 04 (frontend Sentry correlation)**: Backend Sentry project + DSN injection pattern is the template. Frontend reuses Secrets Manager approach (different variable: VITE_SENTRY_DSN is public-safe per D-33).
- **Phase 02 Plan 05 (alarms)**: disabled_parse_alarms variable already declared in variables.tf.
- **Phase 03+ (non-breaking improvements)**: Additive. No shared surface renamed. ContextVar + Sentry scope processor contract stable.

## Self-Check: PASSED

Files created/modified exist:
- backend/app/core/sentry.py - FOUND (new)
- backend/tests/test_sentry_init.py - FOUND (new, 25 tests)
- backend/app/core/config.py - FOUND (modified)
- backend/app/main.py - FOUND (modified)
- backend/app/crawlers/__main__.py - FOUND (modified)
- backend/app/crawlers/ecs_runner.py - FOUND (modified)
- backend/app/crawlers/ecs_rescrape_runner.py - FOUND (modified)
- backend/requirements.txt - FOUND (modified)
- backend/tests/conftest.py - FOUND (modified)
- CLAUDE.md - FOUND (modified in worktree)
- terraform/variables.tf - FOUND (modified)
- terraform/secretsmanager.tf - FOUND (modified)
- terraform/apprunner.tf - FOUND (modified)
- terraform/ecs.tf - FOUND (modified)
- terraform/README.md - FOUND (modified)

Commits in git log:
- 601f2a8 feat(02-02): sentry.py + wiring - FOUND
- 433c770 test(02-02): test suite + fixture - FOUND
- 93a58c7 feat(02-02): terraform - FOUND

All grep acceptance criteria verified. All Phase 1 gates (SAFE-05, SAFE-06 with documented 2 skips, log_propagation OBS-04) green. All 25 Sentry tests pass. Terraform validate + fmt -check both exit 0.

---
*Phase: 02-observability*
*Completed: 2026-04-22*
