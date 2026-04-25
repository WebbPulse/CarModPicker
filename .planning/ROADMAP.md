# Roadmap: CarModPicker

## Milestones

- ✅ **v1.0 Tech-Debt Audit + Fix-All** — Phases 1–8 (shipped 2026-04-24) — see [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md), [`milestones/v1.0-REQUIREMENTS.md`](milestones/v1.0-REQUIREMENTS.md), [`milestones/v1.0-MILESTONE-AUDIT.md`](milestones/v1.0-MILESTONE-AUDIT.md), [`MILESTONES.md`](MILESTONES.md)
- 📋 **Next milestone** — Data enrichment + user-facing planner tooling (ENRICH-01..04, LLM-01..03) — *not yet scoped; run `/gsd-new-milestone` to start*

## Phases

<details>
<summary>✅ v1.0 Tech-Debt Audit + Fix-All (Phases 1–8) — SHIPPED 2026-04-24</summary>

- [x] Phase 1: Safety Nets & CI Hardening (8/8 plans) — completed 2026-04-23
- [x] Phase 2: Observability (5/5 plans) — completed 2026-04-23
- [x] Phase 3: Non-Breaking Internal Improvements (5/5 plans) — completed 2026-04-22
- [x] Phase 4: DB & Parts Hardening (6/6 plans) — completed 2026-04-23
- [x] Phase 5: Structural Router Splits (4/4 plans) — completed 2026-04-23
- [x] Phase 6: Frontend Cleanup & Final CI Gates (6/6 plans) — completed 2026-04-23
- [x] Phase 7: v1.0 Residue Cleanup & Audit-Drift Sync (6/6 plans) — completed 2026-04-24
- [x] Phase 8: Frontend Coverage Expansion (SAFE-03) (20/20 plans) — completed 2026-04-24

Phase artifacts archived under [`milestones/v1.0-phases/`](milestones/v1.0-phases/).

**Outcome:** 60/60 requirements satisfied, 8/8 integration points verified, 3/3 E2E flows green. Audit verdict `tech_debt` (no critical blockers); 22 follow-up items closed in Phase 7. One operator-gated item carried to v1.0 deploy window: terraform apply for per-adapter parse-failure alarm fan-out (~108 alarm creates, ~$10.80/mo CloudWatch delta).

</details>

### 📋 Next Milestone (Planned)

*Not yet scoped.* Run `/gsd-new-milestone` to start the questioning → research → requirements → roadmap cycle.

Forward-looking themes seeded in `PROJECT.md`:
- **Data enrichment** — rich structured extraction (specs, attributes, compatibility hints), per-adapter schema contract, price-history derivation, transformative-use comparative data
- **LLM-assisted user tools** (post-enrichment) — build helper, build planner, part-page summarization
- **v1.0 carry-overs** — OAuth cassette recording (Google sandbox required); operator-gated terraform apply for per-adapter alarm fan-out

## Progress

| Milestone | Phases | Plans | Status      | Shipped    |
| --------- | ------ | ----- | ----------- | ---------- |
| v1.0 Tech-Debt Audit + Fix-All | 8 | 60/60 | ✅ Complete | 2026-04-24 |
| (next)    | —      | —     | Not started | —          |
