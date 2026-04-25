# M001: v1.0 Tech-Debt Audit + Fix-All

**Vision:** CarModPicker is a price-aggregation, parts-discovery, compatibility, and build-planning hub for car enthusiasts.

## Success Criteria

- 60/60 requirements satisfied across SAFE / OBS / CRAWL / DATA / AUTH / FE / QUAL areas
- 8/8 integration points verified, 3/3 E2E flows green
- No external API contract changes; net-additive observability and test coverage

## Slices

- [x] **S01: Safety Nets & CI Hardening** — completed 2026-04-23 `risk:medium` `depends:[]`
  > Coverage floors + characterization tests + migration DROP guard
- [x] **S02: Observability** — completed 2026-04-23 `risk:medium` `depends:[S01]`
  > Sentry + CloudWatch EMF + parse-failure alarm
- [x] **S03: Non-Breaking Internal Improvements** — completed 2026-04-22 `risk:medium` `depends:[S02]`
  > Crawler hardening + adapter auto-discovery + Pydantic v1 sweep
- [x] **S04: DB & Parts Hardening** — completed 2026-04-23 `risk:medium` `depends:[S03]`
  > N+1 fix + FK indexes + with_for_update + session.query sweep
- [x] **S05: Structural Router Splits** — completed 2026-04-23 `risk:medium` `depends:[S04]`
  > admin/auth subpackages + PyJWT migration
- [x] **S06: Frontend Cleanup & Final CI Gates** — completed 2026-04-23 `risk:medium` `depends:[S05]`
  > ESLint + RouteGroupBoundary + Tailwind v4 + stack upgrades
- [x] **S07: v1.0 Residue Cleanup & Audit-Drift Sync** — completed 2026-04-24 `risk:medium` `depends:[S06]`
  > Close 22 tech-debt items from audit + Nyquist Wave 0 + doc sync
- [x] **S08: Frontend Coverage Expansion (SAFE-03)** — completed 2026-04-24 `risk:medium` `depends:[S07]`
  > Lift coverage to 60/50/50/60 + enforce thresholds in CI
