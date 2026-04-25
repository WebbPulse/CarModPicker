# Codebase Map

Generated: 2026-04-25T05:02:24Z | Files: 500 | Described: 0/500
<!-- gsd:codebase-meta {"generatedAt":"2026-04-25T05:02:24Z","fingerprint":"301e57911e7ee8825345439541a34811ea0124ca","fileCount":500,"truncated":true} -->
Note: Truncated to first 500 files. Run with higher --max-files to include all.

### (root)/
- `.gitignore`
- `.mcp.json`
- `CLAUDE.md`
- `LICENSE`
- `README.md`
- `TODO.md`

### .githooks/
- `.githooks/pre-commit`
- `.githooks/pre-push`

### .github/
- `.github/dependabot.yml`

### .github/workflows/
- `.github/workflows/backend-ci.yml`
- `.github/workflows/backend-deploy.yml`
- `.github/workflows/chrome-extension-ci.yml`
- `.github/workflows/chrome-extension-deploy.yml`
- `.github/workflows/frontend-ci.yml`
- `.github/workflows/frontend-deploy.yml`

### backend/
- `backend/.bandit`
- `backend/.dockerignore`
- `backend/alembic.ini`
- `backend/docker-compose.yml`
- `backend/Dockerfile`
- `backend/mypy.ini`
- `backend/pyproject.toml`
- `backend/pyrightconfig.json`
- `backend/pytest.ini`
- `backend/requirements.txt`
- `backend/runtime.txt`
- `backend/start.sh`

### backend/alembic/
- `backend/alembic/env.py`
- `backend/alembic/README`
- `backend/alembic/script.py.mako`

### backend/alembic/versions/
- *(36 files: 36 .py)*

### backend/app/
- `backend/app/__init__.py`
- `backend/app/main.py`

### backend/app/api/
- `backend/app/api/__init__.py`
- `backend/app/api/protocols.py`

### backend/app/api/dependencies/
- `backend/app/api/dependencies/__init__.py`
- `backend/app/api/dependencies/auth.py`

### backend/app/api/endpoints/
- `backend/app/api/endpoints/__init__.py`
- `backend/app/api/endpoints/app_settings.py`
- `backend/app/api/endpoints/bug_reports.py`
- `backend/app/api/endpoints/build_list_parts.py`
- `backend/app/api/endpoints/build_list_phases.py`
- `backend/app/api/endpoints/build_lists.py`
- `backend/app/api/endpoints/build_logs.py`
- `backend/app/api/endpoints/car_generations.py`
- `backend/app/api/endpoints/categories.py`
- `backend/app/api/endpoints/crawled_pages.py`
- `backend/app/api/endpoints/crawler_adapter_configs.py`
- `backend/app/api/endpoints/crawler_schedules.py`
- `backend/app/api/endpoints/images.py`
- `backend/app/api/endpoints/part_manufacturers.py`
- `backend/app/api/endpoints/parts.py`
- `backend/app/api/endpoints/reports.py`
- `backend/app/api/endpoints/retailers.py`
- `backend/app/api/endpoints/search.py`
- `backend/app/api/endpoints/users.py`
- `backend/app/api/endpoints/votes.py`

### backend/app/api/endpoints/admin/
- `backend/app/api/endpoints/admin/__init__.py`
- `backend/app/api/endpoints/admin/_helpers.py`
- `backend/app/api/endpoints/admin/crawlers.py`
- `backend/app/api/endpoints/admin/db_ops.py`
- `backend/app/api/endpoints/admin/jobs.py`
- `backend/app/api/endpoints/admin/parts.py`
- `backend/app/api/endpoints/admin/stats.py`

### backend/app/api/endpoints/auth/
- `backend/app/api/endpoints/auth/__init__.py`
- `backend/app/api/endpoints/auth/_helpers.py`
- `backend/app/api/endpoints/auth/core.py`
- `backend/app/api/endpoints/auth/oauth.py`
- `backend/app/api/endpoints/auth/two_factor.py`
- `backend/app/api/endpoints/auth/webauthn.py`

### backend/app/api/middleware/
- `backend/app/api/middleware/__init__.py`
- `backend/app/api/middleware/crawl_upload_body_limit.py`
- `backend/app/api/middleware/error_handler.py`
- `backend/app/api/middleware/rate_limiter.py`
- `backend/app/api/middleware/request_context.py`

### backend/app/api/models/
- *(26 files: 26 .py)*

### backend/app/api/models/associations/
- `backend/app/api/models/associations/__init__.py`
- `backend/app/api/models/associations/crawler_schedule_adapter.py`
- `backend/app/api/models/associations/part_car.py`

### backend/app/api/schemas/
- *(23 files: 23 .py)*

### backend/app/api/services/
- `backend/app/api/services/__init__.py`
- `backend/app/api/services/base_crud_service.py`
- `backend/app/api/services/base_report_service.py`
- `backend/app/api/services/base_vote_service.py`
- `backend/app/api/services/bug_report_service.py`
- `backend/app/api/services/build_list_service.py`
- `backend/app/api/services/car_generation_service.py`
- `backend/app/api/services/crawler_schedule_service.py`
- `backend/app/api/services/part_linker_service.py`
- `backend/app/api/services/part_listing_service.py`
- `backend/app/api/services/report_service.py`
- `backend/app/api/services/storage_service.py`
- `backend/app/api/services/user_service.py`
- `backend/app/api/services/vote_service.py`

### backend/app/api/utils/
- `backend/app/api/utils/__init__.py`
- `backend/app/api/utils/approximate_count.py`
- `backend/app/api/utils/authorization.py`
- `backend/app/api/utils/base_endpoint_router.py`
- `backend/app/api/utils/base_report_router.py`
- `backend/app/api/utils/base_vote_router.py`
- `backend/app/api/utils/bucket_orphan_utils.py`
- `backend/app/api/utils/common_operations.py`
- `backend/app/api/utils/common_patterns.py`
- `backend/app/api/utils/endpoint_decorators.py`
- `backend/app/api/utils/endpoint_registry.py`
- `backend/app/api/utils/google_oauth.py`
- `backend/app/api/utils/image_url_utils.py`
- `backend/app/api/utils/image_utils.py`
- `backend/app/api/utils/pagination_utils.py`
- `backend/app/api/utils/response_patterns.py`
- `backend/app/api/utils/subscription_utils.py`

### backend/app/core/
- `backend/app/core/__init__.py`
- `backend/app/core/car_generations_data.json`
- `backend/app/core/car_generations_data.py`
- `backend/app/core/car_generations.py`
- `backend/app/core/car_inference.py`
- `backend/app/core/category_inference.py`
- `backend/app/core/cloudwatch_emf.py`
- `backend/app/core/config.py`
- `backend/app/core/email.py`
- `backend/app/core/init_cars.py`
- `backend/app/core/init_categories.py`
- `backend/app/core/init_crawler_adapter_configs.py`
- `backend/app/core/init_service_accounts.py`
- `backend/app/core/log_context.py`
- `backend/app/core/logging.py`
- `backend/app/core/part_categories_data.py`
- `backend/app/core/sentry.py`
- `backend/app/core/worker_identity.py`

### backend/app/core/email_templates/
- `backend/app/core/email_templates/job_report.html`
- `backend/app/core/email_templates/reset_password.html`
- `backend/app/core/email_templates/verify_email.html`

### backend/app/crawlers/
- `backend/app/crawlers/__init__.py`
- `backend/app/crawlers/__main__.py`
- `backend/app/crawlers/archive_rescrape.py`
- `backend/app/crawlers/base.py`
- `backend/app/crawlers/compliance_audit.py`
- `backend/app/crawlers/ecs_rescrape_runner.py`
- `backend/app/crawlers/ecs_runner.py`
- `backend/app/crawlers/fetchers.py`
- `backend/app/crawlers/parsing.py`
- `backend/app/crawlers/README.md`
- `backend/app/crawlers/runner.py`
- `backend/app/crawlers/sanitize.py`
- `backend/app/crawlers/universal_extractor_demo.py`

### backend/app/crawlers/adapters/
- `backend/app/crawlers/adapters/__init__.py`
- `backend/app/crawlers/adapters/base.py`
- `backend/app/crawlers/adapters/generic.py`
- `backend/app/crawlers/adapters/RETAILER_BACKLOG.md`
- `backend/app/crawlers/adapters/VARIANTS.md`

### backend/app/crawlers/adapters/tier0_http/
- *(84 files: 84 .py)*

### backend/app/crawlers/adapters/tier1_tls/
- `backend/app/crawlers/adapters/tier1_tls/__init__.py`
- `backend/app/crawlers/adapters/tier1_tls/apr.py`
- `backend/app/crawlers/adapters/tier1_tls/cobbtuning.py`
- `backend/app/crawlers/adapters/tier1_tls/enjukuracing.py`
- `backend/app/crawlers/adapters/tier1_tls/forgeline.py`
- `backend/app/crawlers/adapters/tier1_tls/fortuneauto.py`
- `backend/app/crawlers/adapters/tier1_tls/goodwinracing.py`
- `backend/app/crawlers/adapters/tier1_tls/kwsuspensions.py`
- `backend/app/crawlers/adapters/tier1_tls/mackinindustries.py`
- `backend/app/crawlers/adapters/tier1_tls/racingbeat.py`
- `backend/app/crawlers/adapters/tier1_tls/suncoastparts.py`
- `backend/app/crawlers/adapters/tier1_tls/texasspeed.py`
- `backend/app/crawlers/adapters/tier1_tls/tomeiusa.py`
- `backend/app/crawlers/adapters/tier1_tls/turnermotorsport.py`
- `backend/app/crawlers/adapters/tier1_tls/vividracing.py`
- `backend/app/crawlers/adapters/tier1_tls/z1motorsports.py`

### backend/app/crawlers/adapters/tier2_browser/
- `backend/app/crawlers/adapters/tier2_browser/__init__.py`
- `backend/app/crawlers/adapters/tier2_browser/aemelectronics.py`
- `backend/app/crawlers/adapters/tier2_browser/americanmuscle.py`
- `backend/app/crawlers/adapters/tier2_browser/apexwheels.py`
- `backend/app/crawlers/adapters/tier2_browser/dinan.py`
- `backend/app/crawlers/adapters/tier2_browser/ecstuning.py`
- `backend/app/crawlers/adapters/tier2_browser/fcpeuro.py`
- `backend/app/crawlers/adapters/tier2_browser/jegs.py`
- `backend/app/crawlers/adapters/tier2_browser/speedindustry.py`
- `backend/app/crawlers/adapters/tier2_browser/summitracing.py`
- `backend/app/crawlers/adapters/tier2_browser/tirerack.py`

### backend/app/crawlers/site_problem_notes/
- `backend/app/crawlers/site_problem_notes/americanmuscle.md`
- `backend/app/crawlers/site_problem_notes/apexwheels.md`
- `backend/app/crawlers/site_problem_notes/bimmerworld.md`
- `backend/app/crawlers/site_problem_notes/cobbtuning.md`
- `backend/app/crawlers/site_problem_notes/ecstuning.md`
- `backend/app/crawlers/site_problem_notes/enjukuracing.md`
- `backend/app/crawlers/site_problem_notes/fcpeuro.md`
- `backend/app/crawlers/site_problem_notes/goodwinracing.md`
- `backend/app/crawlers/site_problem_notes/hksusa.md`
- `backend/app/crawlers/site_problem_notes/ind.md`
- `backend/app/crawlers/site_problem_notes/jegs.md`
- `backend/app/crawlers/site_problem_notes/ktuner.md`
- `backend/app/crawlers/site_problem_notes/README.md`
- `backend/app/crawlers/site_problem_notes/roadsportsupply.md`
- `backend/app/crawlers/site_problem_notes/speedindustry.md`
- `backend/app/crawlers/site_problem_notes/texasspeed.md`
- `backend/app/crawlers/site_problem_notes/tirerack.md`
- `backend/app/crawlers/site_problem_notes/vividracing.md`
- `backend/app/crawlers/site_problem_notes/wheelsboutique.md`
- `backend/app/crawlers/site_problem_notes/z1motorsports.md`

### backend/app/crawlers/specs/
- `backend/app/crawlers/specs/__init__.py`
- `backend/app/crawlers/specs/base.py`
- `backend/app/crawlers/specs/brake.py`
- `backend/app/crawlers/specs/category_bridge.py`
- `backend/app/crawlers/specs/coilover.py`
- `backend/app/crawlers/specs/registry.py`
- `backend/app/crawlers/specs/turbo.py`
- `backend/app/crawlers/specs/universal.py`

### backend/app/db/
- `backend/app/db/__init__.py`
- `backend/app/db/base_class.py`
- `backend/app/db/base.py`
- `backend/app/db/session.py`

### backend/app/services/
- `backend/app/services/__init__.py`
- `backend/app/services/job_service.py`

### backend/scripts/
- `backend/scripts/backfill_adapter_names.py`
- `backend/scripts/check_build_logs_lazy_branch_removed.py`
- `backend/scripts/check_migrations.py`
- `backend/scripts/export_car_generations.py`
- `backend/scripts/flatten_migrations.py`
- `backend/scripts/generate_ext_api_contract.py`
- `backend/scripts/sync_crawl_archive_to_prod.py`
- `backend/scripts/test_migration_round_trip.sh`

### backend/static_assets/
- `backend/static_assets/README.md`

### backend/static_assets/categories/
- `backend/static_assets/categories/.gitkeep`

### backend/static_assets/manufacturers/
- `backend/static_assets/manufacturers/.gitkeep`

### backend/tests/
- `backend/tests/__init__.py`
- `backend/tests/conftest.py`

### backend/tests/api/endpoints/
- *(23 files: 23 .py)*

### backend/tests/auth/
- `backend/tests/auth/__init__.py`
- `backend/tests/auth/test_characterization_2fa_totp.py`
- `backend/tests/auth/test_characterization_login.py`
- `backend/tests/auth/test_characterization_oauth_link.py`
- `backend/tests/auth/test_characterization_oauth_signin.py`
- `backend/tests/auth/test_characterization_password_reset.py`
- `backend/tests/auth/test_characterization_signup_verify.py`
- `backend/tests/auth/test_characterization_webauthn.py`

### backend/tests/cassettes/auth/
- `backend/tests/cassettes/auth/.gitkeep`

### backend/tests/crawlers/
- *(67 files: 67 .py)*

### backend/tests/crawlers/fixtures/amsperformance/
- `backend/tests/crawlers/fixtures/amsperformance/expected.json`
- `backend/tests/crawlers/fixtures/amsperformance/product.html`

### backend/tests/crawlers/fixtures/briantooleyracing/
- `backend/tests/crawlers/fixtures/briantooleyracing/expected.json`
- `backend/tests/crawlers/fixtures/briantooleyracing/product.html`

### backend/tests/crawlers/fixtures/cobbtuning/
- `backend/tests/crawlers/fixtures/cobbtuning/expected.json`
- `backend/tests/crawlers/fixtures/cobbtuning/product.html`

### backend/tests/crawlers/fixtures/spec_contract_samples/
- `backend/tests/crawlers/fixtures/spec_contract_samples/coilover_sample.html`

### backend/tests/crawlers/fixtures/subispeed/
- `backend/tests/crawlers/fixtures/subispeed/expected.json`
- `backend/tests/crawlers/fixtures/subispeed/product.html`

### backend/tests/crawlers/fixtures/texasspeed/
- `backend/tests/crawlers/fixtures/texasspeed/expected.json`
- `backend/tests/crawlers/fixtures/texasspeed/product.html`
