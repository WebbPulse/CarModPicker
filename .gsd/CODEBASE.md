# Codebase Map

Generated: 2026-04-26T00:12:34Z | Files: 1008 | Described: 0/1008
<!-- gsd:codebase-meta {"generatedAt":"2026-04-26T00:12:34Z","fingerprint":"36f9fe71c4eec9f581be5a0b11e33954ec46947e","fileCount":1008,"truncated":false} -->

### (root)/
- `.gitignore`
- `.mcp.json`
- `CLAUDE.md`
- `docker-compose.test.yml`
- `LICENSE`
- `package-lock.json`
- `README.md`
- `TODO.md`

### "frontend/e2e/price-alerts.spec.ts-snapshots/
- `"frontend/e2e/price-alerts.spec.ts-snapshots/subscribe-\342\206\222-manage-\342\206\222-unsubscribe-demo-flow-1-desktop-linux.png"`
- `"frontend/e2e/price-alerts.spec.ts-snapshots/subscribe-\342\206\222-manage-\342\206\222-unsubscribe-demo-flow-1-mobile-linux.png"`
- `"frontend/e2e/price-alerts.spec.ts-snapshots/subscribe-\342\206\222-manage-\342\206\222-unsubscribe-demo-flow-1-tablet-linux.png"`

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
- *(37 files: 37 .py)*

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
- *(21 files: 21 .py)*

### backend/app/api/endpoints/admin/
- `backend/app/api/endpoints/admin/__init__.py`
- `backend/app/api/endpoints/admin/_helpers.py`
- `backend/app/api/endpoints/admin/crawlers.py`
- `backend/app/api/endpoints/admin/db_ops.py`
- `backend/app/api/endpoints/admin/extraction_health.py`
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
- *(27 files: 27 .py)*

### backend/app/api/models/associations/
- `backend/app/api/models/associations/__init__.py`
- `backend/app/api/models/associations/crawler_schedule_adapter.py`
- `backend/app/api/models/associations/part_car.py`

### backend/app/api/schemas/
- *(24 files: 24 .py)*

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
- `backend/app/api/services/part_price_aggregation_service.py`
- `backend/app/api/services/part_price_alert_service.py`
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
- `backend/app/core/email_templates/price_drop_alert.html`
- `backend/app/core/email_templates/reset_password.html`
- `backend/app/core/email_templates/verify_email.html`

### backend/app/crawlers/
- `backend/app/crawlers/__init__.py`
- `backend/app/crawlers/__main__.py`
- `backend/app/crawlers/archive_rescrape.py`
- `backend/app/crawlers/backfill.py`
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
- `backend/scripts/m002_s03_apply_category_targets.py`
- `backend/scripts/sync_crawl_archive_to_prod.py`
- `backend/scripts/test_migration_round_trip.sh`

### backend/scripts/perf/
- `backend/scripts/perf/_parse_locust_csv.py`
- `backend/scripts/perf/locustfile_price_history.py`
- `backend/scripts/perf/README.md`
- `backend/scripts/perf/run_price_history_loadtest.sh`

### backend/static_assets/
- `backend/static_assets/README.md`

### backend/static_assets/categories/
- `backend/static_assets/categories/.gitkeep`

### backend/static_assets/manufacturers/
- `backend/static_assets/manufacturers/.gitkeep`

### backend/tests/
- *(46 files: 46 .py)*

### backend/tests/api/endpoints/
- *(26 files: 26 .py)*

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
- *(88 files: 88 .py)*

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

### backend/tests/dependencies/
- `backend/tests/dependencies/test_admin_auth.py`
- `backend/tests/dependencies/test_auth_utils.py`

### backend/tests/fixtures/
- `backend/tests/fixtures/.gitkeep`
- `backend/tests/fixtures/openapi_snapshot.json`

### backend/tests/fixtures/perf/
- `backend/tests/fixtures/perf/locust_stats_failing.csv`
- `backend/tests/fixtures/perf/locust_stats_passing.csv`

### backend/tests/middleware/
- `backend/tests/middleware/__init__.py`
- `backend/tests/middleware/test_error_handler.py`

### backend/tests/models/
- `backend/tests/models/__init__.py`
- `backend/tests/models/test_part_price_alert.py`

### backend/tests/services/
- `backend/tests/services/__init__.py`
- `backend/tests/services/test_bug_report_service.py`
- `backend/tests/services/test_build_list_service.py`
- `backend/tests/services/test_car_generation_service.py`
- `backend/tests/services/test_crawler_schedule_service.py`
- `backend/tests/services/test_job_service_sweep.py`
- `backend/tests/services/test_part_linker_concurrency.py`
- `backend/tests/services/test_part_linker_integration.py`
- `backend/tests/services/test_part_price_aggregation_service.py`
- `backend/tests/services/test_part_price_alert_evaluation.py`
- `backend/tests/services/test_report_service.py`
- `backend/tests/services/test_user_service.py`
- `backend/tests/services/test_vote_service.py`

### backend/tests/utils/
- `backend/tests/utils/__init__.py`
- `backend/tests/utils/test_authorization.py`
- `backend/tests/utils/test_common_operations.py`
- `backend/tests/utils/test_common_patterns.py`
- `backend/tests/utils/test_google_oauth_nonce.py`
- `backend/tests/utils/test_image_utils.py`
- `backend/tests/utils/test_pagination_utils.py`
- `backend/tests/utils/test_response_patterns.py`

### chrome-extension/
- `chrome-extension/.gitignore`
- `chrome-extension/API_CONTRACT.md`
- `chrome-extension/clean-build.js`
- `chrome-extension/DEVELOPMENT.md`
- `chrome-extension/manifest.json`
- `chrome-extension/options.entry.html`
- `chrome-extension/options.html`
- `chrome-extension/package-lock.json`
- `chrome-extension/package.json`
- `chrome-extension/popup.entry.html`
- `chrome-extension/popup.html`
- `chrome-extension/README.md`
- `chrome-extension/STORE_DESCRIPTION.md`
- `chrome-extension/tsconfig.json`
- `chrome-extension/vite.config.ts`

### chrome-extension/scripts/
- `chrome-extension/scripts/inline-content.js`

### chrome-extension/src/
- `chrome-extension/src/background.ts`
- `chrome-extension/src/content.ts`
- `chrome-extension/src/index.css`
- `chrome-extension/src/main-options.tsx`
- `chrome-extension/src/main-popup.tsx`

### chrome-extension/src/components/common/
- `chrome-extension/src/components/common/SearchableSelect.tsx`

### chrome-extension/src/components/popup/
- `chrome-extension/src/components/popup/LoginScreen.tsx`
- `chrome-extension/src/components/popup/MainScreen.tsx`
- `chrome-extension/src/components/popup/PartDialog.tsx`
- `chrome-extension/src/components/popup/RecordPriceDialog.tsx`

### chrome-extension/src/pages/
- `chrome-extension/src/pages/options.tsx`
- `chrome-extension/src/pages/popup.tsx`

### chrome-extension/src/types/
- `chrome-extension/src/types/index.ts`

### chrome-extension/src/utils/
- `chrome-extension/src/utils/imageUrlUtils.ts`

### docs/
- `docs/PARALLEL_TESTING.md`
- `docs/RATE_LIMITING.md`

### docs/planning/
- `docs/planning/copyright-liability-todos.md`
- `docs/planning/user-engagement-metrics.md`

### email-templates/
- `email-templates/package-lock.json`
- `email-templates/package.json`
- `email-templates/tsconfig.json`

### email-templates/emails/
- `email-templates/emails/ResetPassword.tsx`
- `email-templates/emails/VerifyEmail.tsx`

### email-templates/scripts/
- `email-templates/scripts/build.ts`

### frontend/
- `frontend/.dockerignore`
- `frontend/.nvmrc`
- `frontend/.prettierrc.json`
- `frontend/env.example`
- `frontend/eslint.config.js`
- `frontend/index.html`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/playwright.config.ts`
- `frontend/tsconfig.app.json`
- `frontend/tsconfig.json`
- `frontend/tsconfig.node.json`
- `frontend/vite.config.ts`
- `frontend/vitest.config.ts`

### frontend/e2e/
- `frontend/e2e/build-list.spec.ts`
- `frontend/e2e/components.spec.ts`
- `frontend/e2e/parts-catalog.spec.ts`
- `frontend/e2e/price-alerts.spec.ts`
- `frontend/e2e/price-history.spec.ts`
- `frontend/e2e/smoke.spec.ts`
- `frontend/e2e/tsconfig.json`

### frontend/public/
- `frontend/public/robots.txt`
- `frontend/public/sitemap.xml`

### frontend/scripts/
- `frontend/scripts/prerender.mjs`

### frontend/src/
- `frontend/src/App.coverage.test.tsx`
- `frontend/src/App.tsx`
- `frontend/src/index.css`
- `frontend/src/main.tsx`
- `frontend/src/vite-env.d.ts`

### frontend/src/api/
- *(42 files: 42 .ts)*

### frontend/src/components/admin/
- `frontend/src/components/admin/ReportDialog.tsx`

### frontend/src/components/ads/
- `frontend/src/components/ads/AdBanner.tsx`
- `frontend/src/components/ads/AdColumnSpacer.tsx`
- `frontend/src/components/ads/adsenseConfig.ts`
- `frontend/src/components/ads/README.md`

### frontend/src/components/auth/
- `frontend/src/components/auth/AuthCard.tsx`
- `frontend/src/components/auth/AuthForm.tsx`
- `frontend/src/components/auth/AuthRedirectLink.tsx`

### frontend/src/components/authentication/
- `frontend/src/components/authentication/GoogleAuthFlow.tsx`

### frontend/src/components/buildListParts/
- `frontend/src/components/buildListParts/BuildListPartList.tsx`
- `frontend/src/components/buildListParts/BuildListPartListItem.tsx`
- `frontend/src/components/buildListParts/BuildListParts.tsx`
- `frontend/src/components/buildListParts/CreateBuildListPartForm.tsx`
- `frontend/src/components/buildListParts/EditBuildListPartForm.tsx`

### frontend/src/components/buildLists/
- `frontend/src/components/buildLists/BuildListCard.tsx`
- `frontend/src/components/buildLists/BuildListCatalogList.tsx`
- `frontend/src/components/buildLists/BuildListItem.tsx`
- `frontend/src/components/buildLists/BuildListList.tsx`
- `frontend/src/components/buildLists/CreateBuildListForm.tsx`
- `frontend/src/components/buildLists/EditBuildListForm.tsx`

### frontend/src/components/buttons/
- `frontend/src/components/buttons/ActionButton.tsx`
- `frontend/src/components/buttons/Button.tsx`
- `frontend/src/components/buttons/LinkButton.tsx`
- `frontend/src/components/buttons/SecondaryButton.tsx`
- `frontend/src/components/buttons/StretchButton.tsx`

### frontend/src/components/cars/
- `frontend/src/components/cars/CarList.tsx`
- `frontend/src/components/cars/CarListItem.tsx`

### frontend/src/components/charts/
- `frontend/src/components/charts/Sparkline.test.tsx`
- `frontend/src/components/charts/Sparkline.tsx`

### frontend/src/components/common/
- *(27 files: 27 .tsx)*

### frontend/src/components/layout/
- `frontend/src/components/layout/Divider.tsx`
- `frontend/src/components/layout/PageHeader.tsx`
- `frontend/src/components/layout/SectionHeader.tsx`

### frontend/src/components/layout/globalFooter/
- `frontend/src/components/layout/globalFooter/Footer.tsx`

### frontend/src/components/layout/globalHeader/
- `frontend/src/components/layout/globalHeader/Header.tsx`
- `frontend/src/components/layout/globalHeader/HeaderNavLink.tsx`
- `frontend/src/components/layout/globalHeader/HeaderSeparator.tsx`

### frontend/src/components/parts/
- `frontend/src/components/parts/AddToBuildListDialog.tsx`
- `frontend/src/components/parts/CategoryFilter.tsx`
- `frontend/src/components/parts/CreatePartForm.tsx`
- `frontend/src/components/parts/EditPartForm.tsx`
- `frontend/src/components/parts/ImageGallery.tsx`
- `frontend/src/components/parts/ImageGalleryManage.tsx`
- `frontend/src/components/parts/PartList.priceHistory.test.tsx`
- `frontend/src/components/parts/PartList.tsx`
- `frontend/src/components/parts/PartListItem.tsx`
- `frontend/src/components/parts/PartsActiveFilterChips.tsx`
- `frontend/src/components/parts/PartsFilterSidebar.tsx`
- `frontend/src/components/parts/PriceAlertSubscribeButton.test.tsx`
- `frontend/src/components/parts/PriceAlertSubscribeButton.tsx`
- `frontend/src/components/parts/PriceDeltaLine.test.tsx`
- `frontend/src/components/parts/PriceDeltaLine.tsx`
- `frontend/src/components/parts/PriceHistoryLineChart.tsx`
- `frontend/src/components/parts/SparklineCell.test.tsx`
- `frontend/src/components/parts/SparklineCell.tsx`
- `frontend/src/components/parts/VoteButtons.tsx`

### frontend/src/components/profile/
- `frontend/src/components/profile/ChangePasswordDialog.tsx`
- `frontend/src/components/profile/ConnectedAccountsSettings.tsx`
- `frontend/src/components/profile/PasskeySettings.tsx`
- `frontend/src/components/profile/SecuritySettings.tsx`
- `frontend/src/components/profile/SecuritySettingsDialog.tsx`
- `frontend/src/components/profile/SocialLinks.tsx`
- `frontend/src/components/profile/TwoFactorAuthDialog.tsx`

### frontend/src/components/routes/
- `frontend/src/components/routes/EmailVerifiedRoute.tsx`
- `frontend/src/components/routes/GuestRoute.tsx`
- `frontend/src/components/routes/ProtectedRoute.tsx`

### frontend/src/components/ui/
- `frontend/src/components/ui/.gitkeep`
- `frontend/src/components/ui/button.tsx`
- `frontend/src/components/ui/combobox.tsx`
- `frontend/src/components/ui/confirm-dialog.test.tsx`
- `frontend/src/components/ui/confirm-dialog.tsx`
- `frontend/src/components/ui/dialog.tsx`
- `frontend/src/components/ui/dropdown-menu.tsx`
- `frontend/src/components/ui/input.tsx`
- `frontend/src/components/ui/select.tsx`
- `frontend/src/components/ui/sheet.tsx`
- `frontend/src/components/ui/tabs.tsx`
- `frontend/src/components/ui/toast.tsx`

### frontend/src/components/users/
- `frontend/src/components/users/UserCard.tsx`

### frontend/src/config/
- `frontend/src/config/google.ts`

### frontend/src/constants/
- `frontend/src/constants/index.ts`

### frontend/src/contexts/
- `frontend/src/contexts/AppSettingsContext.test.tsx`
- `frontend/src/contexts/AppSettingsContext.tsx`
- `frontend/src/contexts/AppSettingsContextDefinition.ts`
- `frontend/src/contexts/AuthContext.test.tsx`
- `frontend/src/contexts/AuthContext.tsx`
- `frontend/src/contexts/AuthContextDefinition.ts`

### frontend/src/hooks/
- *(22 files: 18 .ts, 4 .tsx)*

### frontend/src/lib/
- `frontend/src/lib/sentry.test.ts`
- `frontend/src/lib/sentry.ts`
- `frontend/src/lib/utils.ts`

### frontend/src/pages/
- *(27 files: 27 .tsx)*

### frontend/src/pages/account/
- `frontend/src/pages/account/AccountAlerts.test.tsx`
- `frontend/src/pages/account/AccountAlerts.tsx`

### frontend/src/pages/admin/
- `frontend/src/pages/admin/AdminDashboard.test.tsx`
- `frontend/src/pages/admin/AdminDashboard.tsx`
- `frontend/src/pages/admin/BugReportReview.test.tsx`
- `frontend/src/pages/admin/BugReportReview.tsx`
- `frontend/src/pages/admin/CrawlerAdmin.test.tsx`
- `frontend/src/pages/admin/CrawlerAdmin.tsx`
- `frontend/src/pages/admin/ExtractionHealth.test.tsx`
- `frontend/src/pages/admin/ExtractionHealth.tsx`
- `frontend/src/pages/admin/PartsCuration.test.tsx`
- `frontend/src/pages/admin/PartsCuration.tsx`
- `frontend/src/pages/admin/ReportReview.test.tsx`
- `frontend/src/pages/admin/ReportReview.tsx`
- `frontend/src/pages/admin/SystemAdmin.test.tsx`
- `frontend/src/pages/admin/SystemAdmin.tsx`
- `frontend/src/pages/admin/SystemStatistics.test.tsx`
- `frontend/src/pages/admin/SystemStatistics.tsx`
- `frontend/src/pages/admin/UserManagement.test.tsx`
- `frontend/src/pages/admin/UserManagement.tsx`

### frontend/src/pages/authentication/
- `frontend/src/pages/authentication/ExtensionAuth.test.tsx`
- `frontend/src/pages/authentication/ExtensionAuth.tsx`
- `frontend/src/pages/authentication/ForgotPassword.test.tsx`
- `frontend/src/pages/authentication/ForgotPassword.tsx`
- `frontend/src/pages/authentication/ForgotPasswordConfirm.test.tsx`
- `frontend/src/pages/authentication/ForgotPasswordConfirm.tsx`
- `frontend/src/pages/authentication/Login.test.tsx`
- `frontend/src/pages/authentication/Login.tsx`
- `frontend/src/pages/authentication/Register.test.tsx`
- `frontend/src/pages/authentication/Register.tsx`
- `frontend/src/pages/authentication/VerifyEmail.test.tsx`
- `frontend/src/pages/authentication/VerifyEmail.tsx`
- `frontend/src/pages/authentication/VerifyEmailConfirm.test.tsx`
- `frontend/src/pages/authentication/VerifyEmailConfirm.tsx`

### frontend/src/pages/buildLists/
- `frontend/src/pages/buildLists/BuildListsCatalog.test.tsx`
- `frontend/src/pages/buildLists/BuildListsCatalog.tsx`
- `frontend/src/pages/buildLists/ViewBuildLog.test.tsx`
- `frontend/src/pages/buildLists/ViewBuildLog.tsx`

### frontend/src/pages/builder/
- `frontend/src/pages/builder/Builder.test.tsx`
- `frontend/src/pages/builder/Builder.tsx`
- `frontend/src/pages/builder/ViewBuildlist.test.tsx`
- `frontend/src/pages/builder/ViewBuildlist.tsx`
- `frontend/src/pages/builder/ViewCar.test.tsx`
- `frontend/src/pages/builder/ViewCar.tsx`
- `frontend/src/pages/builder/ViewPart.priceSummary.test.tsx`
- `frontend/src/pages/builder/ViewPart.test.tsx`
- `frontend/src/pages/builder/ViewPart.tsx`

### frontend/src/pages/parts/
- `frontend/src/pages/parts/EditPart.test.tsx`
- `frontend/src/pages/parts/EditPart.tsx`
- `frontend/src/pages/parts/PartsCatalog.test.tsx`
- `frontend/src/pages/parts/PartsCatalog.tsx`
- `frontend/src/pages/parts/UserParts.test.tsx`
- `frontend/src/pages/parts/UserParts.tsx`

### frontend/src/services/
- `frontend/src/services/Api.ts`

### frontend/src/styles/
- `frontend/src/styles/.gitkeep`
- `frontend/src/styles/tokens.css`

### frontend/src/test/
- `frontend/src/test/setup.ts`

### frontend/src/test/guards/
- `frontend/src/test/guards/extension-content-type.test.ts`
- `frontend/src/test/guards/no-legacy-gradient.test.ts`
- `frontend/src/test/guards/no-process-env.test.ts`
- `frontend/src/test/guards/README.md`

### frontend/src/test/mocks/
- `frontend/src/test/mocks/api.ts`

### frontend/src/test/mocks/admin/
- `frontend/src/test/mocks/admin/bugs.ts`
- `frontend/src/test/mocks/admin/crawlers.ts`
- `frontend/src/test/mocks/admin/curation.ts`
- `frontend/src/test/mocks/admin/jobs.ts`
- `frontend/src/test/mocks/admin/reports.ts`
- `frontend/src/test/mocks/admin/stats.ts`
- `frontend/src/test/mocks/admin/users.ts`

### frontend/src/test/utils/
- `frontend/src/test/utils/async.ts`
- `frontend/src/test/utils/test-mocks.ts`
- `frontend/src/test/utils/test-utils.tsx`
- `frontend/src/test/utils/TestProviders.tsx`
- `frontend/src/test/utils/TestWrapper.tsx`

### frontend/src/types/
- `frontend/src/types/Api.ts`

### frontend/src/utils/
- `frontend/src/utils/carUtils.test.ts`
- `frontend/src/utils/carUtils.ts`
- `frontend/src/utils/dailyDismiss.ts`
- `frontend/src/utils/externalImageUrls.test.ts`
- `frontend/src/utils/externalImageUrls.ts`
- `frontend/src/utils/lazyWithReload.ts`
- `frontend/src/utils/subscription.ts`

### scripts/
- `scripts/__init__.py`
- `scripts/_rename_car_refactor.py`
- `scripts/export_global_parts_for_car_inference_analysis.py`
- `scripts/export_global_parts_for_category_analysis.py`
- `scripts/populate_sample_data.py`
- `scripts/README.md`

### terraform/
- *(25 files: 22 .tf, 1 .hcl, 1 .txt, 1 .md)*

### terraform/cloudfront_functions/
- `terraform/cloudfront_functions/uri_rewrite.js`
