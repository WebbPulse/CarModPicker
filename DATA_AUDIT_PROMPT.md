# Data Scraping & Inferencing Audit Prompt

Use this prompt to spin up a team of parallel subagents to diagnose, troubleshoot, and **fix** issues with scraped data using the local Postgres DB and local MinIO archive bucket. Reuse this prompt verbatim for future audits.

---

## Goal

Use my localhost DB and bucket connections to diagnose and **apply fixes** for various issues with my data scraping and inferencing. Spin up a team of subagents in parallel, each focused on a different concern. Each agent should:

- Read directly from the live local Parts DB
- Pull archived HTML from local MinIO when it needs to verify what the source actually said
- Identify systemic issues, not one-offs — quantify the problem (counts, % affected, top offending adapters/retailers)
- **Apply** concrete fixes (DB writes, adapter code edits, Alembic migrations) per the write-authority rules below
- Report back what was changed, what was deferred, and what's still open — not what's pending approval

Each agent reports back a structured finding: **Changes applied → Evidence → Deferred → Open questions**.

## Setup

- See `memory/reference_local_data_audit.md` for how to query the live local parts DB and fetch archived HTML from MinIO.
- Spawn agents in **parallel** (single message, multiple Agent tool calls).
- Orchestrator pre-reads relevant `MEMORY.md` entries and inlines them into each agent's prompt — agents do not have access to the user's auto-memory.
- Orchestrator captures a **before** snapshot of key counts (parts_total, parts_universal, parts_null_pn, parts_null_mfr, distinct_mfrs, distinct_categories, car_generations, part_cars_rows, parts_other_cat) before spawning, and an **after** snapshot when consolidating.

## Write authority and safety rules (apply to ALL agents)

Each agent prompt must include this block verbatim:

```
WRITE AUTHORITY: You may execute INSERT/UPDATE/DELETE on the DB, edit adapter
           code under backend/app/crawlers/, and create Alembic migrations.

Rules:
  1. ALWAYS run the equivalent SELECT first to confirm row count before any
     UPDATE/DELETE. Log the count in your report.
  2. Wrap multi-statement DB changes in BEGIN; ... COMMIT; and ROLLBACK on any
     unexpected count.
  3. Before editing an adapter file, run `git status` and `git diff <file>` to
     check no other parallel agent has uncommitted changes on it. If yes,
     DEFER that file's edit and report it as an open follow-up.
  4. After an adapter code change, validate with
     `python -m app.crawlers --rescrape-url <one-archived-url>` from backend/
     (exit 0 = parsed_ok). Do NOT bulk-rescrape — orchestrator territory.
  5. Create at most ONE Alembic migration per agent. Use
     `alembic revision -m "..."` (NOT --autogenerate for data-only migrations)
     then write the migration body, then `alembic upgrade head`.
  6. Do NOT git commit. Orchestrator commits as a single batch.

SOURCE-OF-TRUTH RULE (critical — past audits got bitten by this):
  Some catalog tables are RE-SEEDED on backend startup from source files.
  A DB-only UPDATE will be silently reverted. Before writing to these tables,
  update the source file too — or use a migration. Specifically:

    - car_makes / car_models / car_generations
        Re-synced by app/core/init_cars.py from
        app/core/car_generations_data.json on every backend startup.
        Synced fields: generation_name, start_year, end_year, description,
        display_name. Lookup key: (car_model_id, slug). To make a change
        stick, edit the JSON entry that matches (make, model, generation_name).

    - categories
        Re-synced by app/core/init_categories.py from
        app/core/part_categories_data.py. Synced fields: display_name,
        description, icon, sort_order. Lookup key: name. To rename or change
        a category, edit the Python source.

    - part_manufacturers
        NOT re-seeded on startup, but precedent canonicalization lives in
        Alembic migrations (e.g. 080fc6916478_canonicalize_manufacturers.py).
        For any merge/rename, write a NEW idempotent data migration modeled
        on that file's _merge_cluster / _ensure_canonical_row helpers. A
        DB-only merge persists today but won't survive a fresh DB rebuild
        AND may conflict with prior migrations' canonical picks.

    - part_categories_data.py / category_inference.py
        Inference keyword lists. Edits ARE in source — safe.

  Tables that are NOT re-seeded (DB-only writes are safe):
    parts, part_cars, part_listings, part_price_history, crawled_pages,
    parts.image_urls, parts.part_number, parts.is_universal,
    parts.category_id (the parts row itself is not seeded; only the
    categories table is).

OUTPUT: ≤800 words. Lead with "Changes applied" (DB rows touched, files
        edited, migrations created, source-of-truth files updated), then
        "Evidence", then "Deferred", then "Open questions for orchestrator".
```

## Concurrency safety

Multiple agents touching the same DB and adapter tree introduces conflict risk:

- **DB**: Postgres handles concurrent writes; agent scopes are mostly disjoint by table/column. Where overlap exists (e.g. PN-normalization writes `parts.part_number*` while manufacturer agent writes `parts.part_manufacturer_id`), they're different columns on the same row — fine for concurrent UPDATE. Agents must use **targeted column updates**, never `SELECT * ... UPDATE`.
- **Adapter code**: per memory `project_concurrent_agent_work.md`, multiple agents already edit `backend/app/crawlers/` in parallel. Each agent **must** `git status` + `git diff` the file before editing, prefer adapter-scoped edits over cross-cutting refactors, and DEFER if another agent has uncommitted changes on the same file.
- **Migrations**: Alembic linearizes by parent revision. If two agents both create migrations, the second `alembic upgrade head` will fail on a divergent head. Mitigation: each agent creates at most ONE migration, the orchestrator runs `alembic heads` post-audit and merges divergent heads if needed.
- **Source-of-truth files** (JSON / Python seed): orchestrator should run a final consistency pass after agents return, comparing DB state to the source files for each seeded table.

## Subagent assignments

### 1. Car attribution agent
- Treat currently-flagged `is_universal=true` parts as a likely blind spot — `is_universal = not inferred_car_ids` per `backend/app/crawlers/base.py:971`, so universal is the catch-all when no car was inferred.
- Sample top-20 adapters by universal-count, classify each sample: (a) actually universal, (b) attribution miss with existing `car_generations` row, (c) miss with missing `car_generations` row.
- Quantify: per-adapter universal-rate vs. catalog median; rank biggest leakers.
- **Write authority**:
  - Class-b: `INSERT INTO part_cars` AND `UPDATE parts SET is_universal=false WHERE id IN (...)`.
  - Class-c: **first** add the missing entry to `car_generations_data.json` (per source-of-truth rule), then re-run `init_car_generations` via a one-off Python invocation OR insert directly with the same slug the JSON would compute. Then attribute as in (b).
  - Adapter-level: if a single adapter has >50% universal-rate AND a fixable extraction bug, edit the adapter file directly.
- Coordinate with the **car-naming agent** (#7): if you need to add a new car_generation, check whether that make/model has naming inconsistencies the naming agent is fixing — if so, defer the new add and surface for the naming agent to handle in the same edit.

### 2. Part number normalization agent
- Compare existing `parts.part_number_normalized` against a stricter rule (alphanumeric-only, lowercased). Quantify additional dedup collapse with SQL.
- Bucket NULL-PN parts by adapter; per memory `feedback_part_number_4char_floor.md`, sample for adapter-emitted real SKUs that got nulled by `is_junk_part_number`.
- Hunt label-leakage shapes per memory `feedback_pn_extract_label_leakage.md` (PNs that equal an H1 token, all-caps single words, label words like "FUEL"/"SKU"/"CODE"/"MODEL"/"CHASSIS"/"MSRP", spaces, year-shorthand `'NN`).
- **Write authority**:
  - Stricter normalization: modify normalization function in `parsing.py` AND backfill `UPDATE parts SET part_number_normalized = ...`.
  - Confirmed label leakage: `UPDATE parts SET part_number = NULL, part_number_normalized = NULL WHERE id IN (...)` AND fix the responsible adapter (scope SKU extraction to actual SKU DOM element + shape guard).
  - 4-char-floor false positives: edit adapter to brand-prefix per `roadsportsupply.py::_compose_rss_part_number`.
- **Coordination warning**: this agent and the manufacturer agent both write to `parts`. Use targeted column updates only.

### 3. Image URL agent
- Static checks: non-https, `data:` URIs, placeholder filenames, same image used for many parts (logo bug).
- HEAD-sample top-10 image-emitting adapters (50 URLs each, cap 500 total). Use GET fallback for adapters where HEAD returns 405 (e.g. NetSuite `media.nl`).
- **Write authority**:
  - Strip 4xx/5xx URLs from `parts.image_urls`; empty array if no images remain.
  - http→https rewrite where HEAD confirms https works.
  - Adapter-level bugs (one logo for all parts, hotlink-blocked CDN, badge images): edit adapter file. Read archived HTML to identify correct selector.

### 4. Part manufacturer attribution agent
- Permutation detection over `part_manufacturers`: Levenshtein clustering (`fuzzystrmatch` extension or Python difflib fallback), suffix-token strip per memory item 4 (drop `Performance | Racing | Tuning | Electronics | Induction | Industries | USA | America | Automotive | Inc | LLC | Ltd | Co`), OEM patterns per memory item 3 (`Genuine X` / `OEM X` → `X OEM`).
- Retailer-as-manufacturer: cross-check `retailers.name` against `part_manufacturers.name`.
- **Write authority** — IMPORTANT, this is the table where past audits got hurt:
  - Read the existing `alembic/versions/*canonicalize_manufacturers*.py` files FIRST. Don't re-pick a different canonical than prior migrations without an explicit reason.
  - Apply merges via a **new Alembic data migration** modeled on the existing pattern (`_merge_cluster` + `_ensure_canonical_row` helpers). Run `alembic revision -m "..."` then write the migration body, then `alembic upgrade head`. The migration is the source of truth — direct DB UPDATEs leave fresh-DB rebuilds in an inconsistent state.
  - For retailer-as-mfr bugs: `UPDATE parts SET part_manufacturer_id = NULL` AND fix the adapter so it stops attributing the retailer.

### 5. Category attribution agent
- Top focus: parts in the `other` category (~12% catalog smell) and NULL-mfr parts (correlate with category misses).
- Cluster `other` parts by name n-grams; propose new categories iff cluster ≥200 parts AND clearly distinct from existing 11.
- Inverse mismatches via keyword regexes (downpipe in body, clutch in brakes via "pad" false positive, etc.).
- **Write authority**:
  - Edit `app/core/category_inference.py` keyword lists (this is in source — safe).
  - Re-categorize confirmed misses: `UPDATE parts SET category_id = '<correct>' WHERE id IN (...)`.
  - New categories: edit `app/core/part_categories_data.py` (source of truth) AND extend `app/crawlers/specs/category_bridge.py`. Direct `INSERT INTO categories` will be re-synced by `init_part_categories` so the source edit is required.
  - Adapter-level miscategorization: edit adapter's category-resolution logic.

### 6. Car generation year-boundary agent
- Pull `car_generations` with `end_year BETWEEN 2022 AND 2024`. For each, determine if the nameplate is still in production for current MY (cheap signal: do recent listings tagged with this generation mention current/next MY in their name?).
- Inverse check: `WHERE end_year IS NULL` for known-discontinued cars (memory item 2: discontinued = final US MY year).
- **Write authority**:
  - **First** edit `app/core/car_generations_data.json` to set `"end_year": null` (current-gen) or the correct US MY (discontinued). The JSON is the source of truth — DB UPDATEs will be reverted by `init_car_generations` on next backend startup.
  - **Then** also apply the same change directly to the live DB (via `UPDATE car_generations SET end_year = ... WHERE id = ...`) so the audit's measured deltas reflect immediately. Both writes are required.
  - Avoid splitting/merging generations in this run — defer to follow-ups (per memory item 1, sub-trim splits are out of scope).

### 7. Car model & generation naming agent (NEW)
The catalog has inconsistent naming across `car_models` and `car_generations`. The user's stated priority — in order — is:

1. **Internal consistency**: any naming choice should follow a pattern that's also applied to similar rows. A reader should be able to predict the shape of a row they haven't seen yet from rows they have.
2. **Human readability**: optimize for a non-enthusiast scanning a dropdown or URL. Recognize that chassis codes (`G80`, `992`, `W223`) are gibberish to most users — they're acceptable only when they meaningfully disambiguate generations the average buyer would otherwise confuse, or when the enthusiast nameplate IS the chassis code (e.g. Porsche 911 generations are commonly called by code).
3. **Enthusiast-recognizable codes** are NOT a goal in themselves. Don't preserve a chassis code just because it's "correct" if a generation counter would be more readable.

The user is explicitly **not familiar with every brand's conventions** and is delegating judgment. The agent should make defensible choices and surface them, not ask "what should we do for BMW?" back to the user.

**Specific inconsistencies known to exist** (use these as starting points, not an exhaustive list):

- **Generation-name style mixing**. `car_generations.generation_name` currently uses at least four styles:
  - chassis codes (`E52`, `G80`, `992`, `8T`, `C257`, `V37`, `CN7`)
  - generation counters (`10th Gen`, `2nd Gen`, `Mk6`, `Mk2`)
  - free-text tails (`Plaid`, `VF Series`, `Maranello`, `SRT-4`)
  - slash-separated composites (`G20/G21`, `G22/G23/G26`, `W463 (New)`, `PO536 (Facelift)`)

  Per the readability priority: prefer `Nth Gen` when no widely-recognized name exists; preserve a chassis code only when readers commonly use it (Porsche 911 992, BMW M3 G80, VW Golf Mk7). When in doubt, default to `Nth Gen` — it's universally legible.

- **Trim-as-model splits**. BMW has `3 Series`, `328i`, `330i`, `335i`, `M3`, `M340i` as separate model rows; Mercedes splits `S-Class` + `S65 AMG` + `S63 AMG`; Audi splits `A5` + `RS5` + `S5`; BMW EV splits `i5` + `i5 M60`. There's no single right answer (`M3` arguably IS its own model in enthusiast culture; `330i` is just a trim of `3 Series`). Apply the **consistency** priority: pick a per-make rule and apply it uniformly. A reasonable starting heuristic — surface for the user but feel free to deviate with reasoning:
  - Performance halo cars with their own enthusiast identity (`M3`, `RS5`, `Type R`, `Golf R`, `WRX`, `GR Corolla`) → keep as separate model rows.
  - Engine/trim variants of the same nameplate (`328i`/`330i`/`335i`, `i5 M60` if it's just a trim of `i5`) → collapse into the parent model.

- **Parenthetical qualifiers** (`W463 (New)`, `PO536 (Facelift)`): informal and ugly. Move qualifier to `description`; rename to a clean form. If two generations of the same model share a chassis code, append a year range (`PO536 (2019–2023)` and `PO536 (2024–)` is fine but consider `Macan PO536` and `Macan PO536 Facelift` — readability vs disambiguation tradeoff).

- **Slash-separated multi-chassis** (`G20/G21`, `G22/G23/G26`): one row covering sedan + touring + Gran Coupe. This is fine as long as it's used **consistently**. Audit whether siblings follow the same convention (does `M3 G80` or `M3 G80/G81` exist? pick one).

- **Model name carries trim** (`SVT Lightning`, `Neon SRT-4`, `Civic Type R`, `Golf R`): per the trim-as-model heuristic above — these are halo cars and likely stay as separate model rows. Just confirm consistency.

**Process**:
1. Read `backend/app/core/car_generations_data.json` (source of truth) end to end. Build a per-make summary of which generation-naming style each row uses.
2. Sample UX-consuming code paths to understand what the user sees: `frontend/src/components/CarSelector*.tsx`, `frontend/src/pages/parts/*.tsx`, `backend/app/api/endpoints/search.py`, `backend/app/core/car_inference.py`. The dropdown render shape is the most important — that's where readability lives or dies.
3. Quantify: per-make breakdown of styles in use; total renames implied by your proposed convention; rows where slug-pinning will be needed to avoid breakage.
4. Apply your decisions. Surface the *rationale* in the report so the user can sanity-check the judgment, not the granular row-by-row picks.

**Write authority**:
- The naming surface is user-facing (search, dropdowns, URLs via slug). A wrong rename can break `canonical_part_id` linkage, fitment slugs, and SEO. So:
  - **For renames** (style standardization, parenthetical cleanup, casing): edit `car_generations_data.json` AND apply matching DB UPDATE. Use the explicit `slug` field per generation entry (per `car_generations_data.py:48`) to **pin the existing slug** so `init_cars.py` finds the existing row and updates its name, instead of creating a duplicate. Never let the slug auto-recompute on a rename.
  - **For trim-as-model collapses** (e.g. merging `330i` into `3 Series`): this is structural — affects `parts.id` → `part_cars.car_id` linkage. Apply only when the merge target is unambiguous AND you've SELECTed the affected `part_cars` rows first to confirm count. Use `BEGIN; ... COMMIT;` and ROLLBACK on surprises. If a model row has parts that don't cleanly belong under the parent, DEFER.
  - **For ambiguous cases**: defer to a recommendation in the report. Be specific — "I'd merge `i5 M60` into `i5` because it's a trim variant; defer because the M50 EV motor genuinely changes drivetrain platform" is better than "uncertain about EV splits."
- Coordinate with the **car attribution agent** (#1): write the make name(s) you're actively restructuring to `/tmp/audit_naming_inflight.txt` (one make per line) at the start of your work. The attribution agent reads this file before adding any new `car_generations` row and defers if the make is in-flight.

**Bias toward action over deferral.** The user is delegating judgment here. A reasoned change that turns out to need a small follow-up is better than a long "open questions" list that pushes the decision back. Defer only when the change is structurally risky (linkage breakage, ambiguous trim-vs-model) — not when you're unsure about brand convention. For brand convention, pick something defensible and apply it.

## Output format per agent

Each agent reports in this exact format (≤800 words):

```
## <Agent name>

### Changes applied
- DB: <rows touched, by table>
- Source-of-truth files: <JSON / Python seed files edited, with reason>
- Adapter / inference code edited: <list with one-line reason each>
- Migrations created: <revision id + name, or "none">

### Evidence
- Quantified findings: counts, top offenders, example rows
- 3-5 concrete examples (with URLs / IDs where applicable)

### Deferred
- File conflicts (other agent had uncommitted changes)
- Ambiguous cases that need user input
- Out-of-scope discoveries

### Open questions for orchestrator/user
```

## Post-audit consolidation (orchestrator)

After all agents return:

1. **Working-tree review**: `git status` + `git diff` — spot-check coherence (no agent overwrote another's work in a half-merged state).
2. **Migration head check**: `alembic heads` — merge revision if multiple heads exist, then `alembic upgrade head`.
3. **Source-of-truth consistency pass**: for every seeded table (car_generations, categories, part_manufacturers), compare DB state to source files. Flag and fix any drift the agents missed. **Past failure mode: year-boundary agent updated the DB without updating the JSON; manufacturer agent merged in DB without writing a migration. Both required orchestrator follow-up. The source-of-truth rule above prevents this for future runs — orchestrator should still verify.**
4. **Duplicate-row check** (especially after the naming agent runs): the naming agent applies many `car_generations` renames at once, and a missing `slug` pin causes `init_cars.py` to create a duplicate row instead of updating the existing one. Run these checks:

   ```sql
   -- Same (car_model_id, slug) appearing twice — should be impossible but verify.
   SELECT car_model_id, slug, count(*) FROM car_generations
   GROUP BY car_model_id, slug HAVING count(*) > 1;

   -- Same generation_name within a model (likely accidental dup from a missing slug-pin).
   SELECT car_model_id, generation_name, count(*) FROM car_generations
   GROUP BY car_model_id, generation_name HAVING count(*) > 1;

   -- Generation in DB but not in JSON (orphaned — name was renamed in JSON but slug
   -- didn't match, leaving the old DB row stranded).
   -- Diff DB rows against `get_all_car_generations()` from app/core/car_generations_data.py:
   -- any DB (car_model_id, slug) tuple not in JSON output is an orphan.

   -- Generation in JSON but not in DB (the rename DID create a new row; old row above
   -- is the stranded sibling).

   -- New: check that no part_cars rows reference an orphaned car_generation
   -- (would indicate the rename also broke fitment linkage).
   SELECT count(*) FROM part_cars pc
   WHERE NOT EXISTS (SELECT 1 FROM car_generations cg WHERE cg.id = pc.car_id);
   ```

   If duplicates or orphans exist, the fix is to merge: pick the row referenced by `part_cars` as canonical, repoint any stragglers, then delete the orphan. Same idempotent pattern as the manufacturer canonicalization migration. Do this before snapshotting deltas (next step) so the counts reflect the cleaned state.

   Also re-verify the naming agent's `car_generations_data.json` edits round-trip: `python -c "from app.core.car_generations import load_car_generations; load_car_generations.cache_clear(); load_car_generations()"` from `backend/` — should not raise.

5. **Snapshot deltas**: re-run the high-level shape query and report before/after.
6. **Single bulk-rescrape** (if and only if adapter fixes warrant it — orchestrator decision, not per-agent).
7. **Auto-memory updates**: surface durable conventions discovered (new normalization rules, naming decisions) for the user to confirm before saving to memory.
8. **Commit as a single audit batch** with a multi-line message summarizing each agent's contribution. Do not push without explicit user request.

## Out of scope

- Re-fetching from the live web (use archived HTML only — tier1/tier2 retailers are rate-limited / Cloudflared).
- Cross-cutting refactors of the crawler base classes — keep edits adapter-scoped.
- Pushing commits or opening PRs.
- Splitting/merging existing car_generations rows (defer per memory item 1).
