# Folloze Content Engine - Execution Plan

**Version:** 1.1  
**Date:** 2026-03-20  
**Status:** Ready for execution  
**Primary reference:** `PRD.md`  
**Build spec reference:** `CODEX_PROMPT.md`  
**Deferred roadmap:** `TODOS.md`

---

## Purpose

This document translates the PRD into an execution sequence with clear ownership, dependencies, milestone gates, and validation criteria.

Use the documents this way:

1. `PRD.md` defines the product and technical requirements.
2. `EXECUTION_PLAN.md` defines the order of work and go/no-go gates.
3. `CODEX_PROMPT.md` defines the implementation instructions for Codex.
4. `TODOS.md` holds intentionally deferred work.

---

## Delivery Target

V1 ships a daily pipeline that:

1. Pulls the next topic from `content/calendar.yaml`
2. Enriches with research
3. Generates AEO content through Gemini
4. Produces HTML + JSON-LD
5. Scores content with the quality gate
6. Writes a release-ready content artifact plus run artifacts
7. Renders a reviewable preview page for the artifact
8. Emails the reviewer with release status and artifact details
9. Leaves production promotion to a human in V1

The release target is explicitly:

- Gemini is the only LLM provider in V1
- V1 delivery target is a Vercel-hosted static site on Trey-owned domain infrastructure
- `release_mode: manual`
- launchd schedule at 9:00 AM America/Chicago
- Logs, run artifacts, and handoff documentation are required release assets

---

## Success Criteria

V1 is complete when all of the following are true:

1. A dry run completes end to end without external writes.
2. A real run creates a valid release artifact for one topic.
3. The static site bundle can render that topic with valid metadata and JSON-LD.
4. At least one approved page is validated on the Vercel site or owned domain.
5. The review email includes the title, AEO score, output route, and JSON-LD preview.
6. All required test suites pass locally.
7. launchd assets exist and are ready for installation.
8. Trey can hand the project to a web dev team using the deployment and handoff docs.

---

## Scope Guardrails

Build now:

- Core Python pipeline
- Four content types: `comparison`, `guide`, `faq`, `glossary`
- Gemini-only content generation and model-assisted research synthesis
- Static artifact generation for Vercel delivery
- Static site build path for `/insights/`
- Verification
- Email notifications
- launchd support
- Competitive seed script
- robots.txt and sitemap asset generation
- Full test suite for V1 behavior
- Deployment and handoff documentation

Do not build now:

- Webflow integration
- Webflow CMS migration tooling beyond documentation and mapping notes
- Automatic production deployment from the pipeline
- Slack notifications
- Citation monitor
- Gap analyzer beyond the one-time seed script
- Self-seeding calendar
- Freshness refresher
- Existing blog retrofit
- Autonomous publish mode

These are excluded to keep V1 on the shortest path to one safe daily content artifact and one validated Vercel deployment path.

---

## Implementation Constraints

These are non-negotiable build rules:

1. Gemini is hard-wired as the only LLM provider in V1.
2. `pipeline.py` orchestrates stages only. It must not absorb stage-specific business logic.
3. All content generation stays in `generator.py`, and model-assisted research synthesis stays in `research.py`.
4. All release-artifact persistence stays in `artifacts.py`.
5. Static site rendering must consume the release artifact contract rather than custom per-page logic.
6. V1 promotion to production remains manual and explicit.
7. V2 Webflow migration must be documented from the V1 artifact contract, not invented later.
8. Logs and docs are first-class deliverables, not cleanup work.

This keeps the move to V2 as a delivery-target migration, not a rewrite of the content pipeline.

---

## Owners

**Codex**

- Build all repo files and tests
- Keep all external integrations mocked or non-destructive during build
- Produce docs and scripts needed for rollout, deployment, and handoff

**Trey / Vercel admin**

- Create the Vercel project for the V1 site
- Attach the owned domain or subdomain used for testing
- Record the preview and production URLs
- Configure any required Vercel settings outside the repo
- Review release-ready artifacts and manually promote approved content

**Juno**

- Maintain `content/calendar.yaml`
- Run manual pipeline commands when needed
- Review operational alerts and release-ready emails
- Manage weekly topic seeding after launch

**Future web dev team**

- Consume the deployment, artifact, and migration docs
- Own the V2 migration to Webflow

---

## Critical Path

```text
MANUAL PREREQS
      |
      v
FOUNDATION CONTRACTS
      |
      v
CONTENT PATH
(calendar -> research -> generate -> optimize -> quality)
      |
      v
ARTIFACT + STATIC SITE PATH
(artifacts -> site build -> verify -> notify)
      |
      v
PIPELINE ORCHESTRATION
      |
      v
TESTS + DOCS + OPS ASSETS
      |
      v
DRY RUN
      |
      v
FIRST REAL ARTIFACT
      |
      v
VERCEL VALIDATION
      |
      v
SCHEDULED DAILY OPERATION
```

Anything that blocks the foundation contracts blocks the whole build. Anything that blocks artifact integrity, static site rendering, or Vercel validation blocks release.

---

## What Already Exists

Reuse directly:

- `PRD.md` as the requirements source of truth
- `CODEX_PROMPT.md` as the implementation spec
- `TODOS.md` as the deferred roadmap
- Existing Brave and Perplexity usage patterns from prior EE work
- Existing content calendar pattern from EE
- Existing brand and AEO thinking captured in prior skills and docs

Reuse as patterns only, not copied product logic:

- EE pipeline orchestration pattern
- EE lock-file and run-artifact model
- EE research degradation pattern

Build from scratch:

- Gemini-only generation flow
- Release-artifact contract for Vercel delivery
- Static site build path
- Vercel deployment docs and rollout gates
- Webflow migration notes for V2

---

## Not In Scope

- Visual redesign beyond a clean, legible V1 static site
- Adding a new folloze.com nav item in V1
- Retrofitting the existing 140-post blog
- Paid distribution of Insights pages
- Multi-language support
- Image generation
- Analytics integration beyond logs and email
- Automatic production release from the pipeline
- Building the actual Webflow migration in V2

---

## Milestone Plan

### M0 - External Prerequisites

Objective: clear the external dependencies that code cannot invent.

Tasks:

1. Create the Vercel project for the V1 site.
2. Choose the owned domain or subdomain for V1 testing.
3. Connect DNS and confirm preview and production URLs.
4. Confirm SMTP credentials for the sender account.
5. Confirm Juno's operating model: calendar owner, daily reviewer, release approver.

Exit criteria:

- Vercel project exists
- Domain decision is locked
- Preview and production URLs are known
- SMTP path is known

Notes:

- Codex can start before M0 is fully done, but release validation cannot finish without it.

### M1 - Foundation Contracts

Objective: lock the repo structure and configuration contracts before module work begins.

Tasks:

1. Create `pyproject.toml`, `.gitignore`, `.env.example`, and baseline repo folders.
2. Implement `config.py` with strict validation against `config.yaml`.
3. Implement the custom exception set in one place.
4. Create placeholder static assets for:
   - `content/templates/*`
   - `schema/*`
   - `brand/context.md`
   - `site/templates/*`
   - `site/assets/*`
5. Define the run artifact contract in `logs/runs/YYYY-MM-DD/`.
6. Define the release artifact contract that V1 and V2 both depend on.

Exit criteria:

- Config loads and validates correctly
- Every named exception from the PRD exists
- File layout matches the PRD
- Static template locations are stable
- Run and release artifact contracts are stable

### M2 - Core Content Path

Objective: get from topic selection to a scored content object without delivery concerns.

Tasks:

1. Build `calendar.py`
2. Build `research.py`
3. Build `generator.py`
4. Build `optimizer.py`
5. Build `quality.py`

Implementation order inside this milestone:

1. `calendar.py`
2. `research.py`
3. `generator.py`
4. `optimizer.py`
5. `quality.py`

Critical requirements:

- Research sanitization must explicitly reduce prompt injection risk.
- Research failures degrade rather than abort, except where the PRD says otherwise.
- Generator must detect empty, refused, truncated, and too-short output.
- Generator must call Gemini only.
- Optimizer must support all four content types.
- Quality gate must return a scored result with human-readable failure reasons.

Exit criteria:

- One mocked topic can flow from calendar through quality gate
- All four content types are supported
- Degraded research path works
- Release-ready queue path is available for optimizer or quality failures

### M3 - Artifact and Static Site Path

Objective: turn scored content into a stable delivery contract and a renderable static page.

Tasks:

1. Build `artifacts.py`
2. Build the static site renderer and templates under `site/`
3. Build `verify.py`
4. Build `notify.py`

Critical requirements:

- Release artifacts must include every field needed by the site and the future Webflow migration.
- The static site must render `/insights/{slug}` from release artifacts with no page-specific branching.
- Verification must detect page status, canonical URL, meta description, and JSON-LD presence.
- Release-ready emails must include the output route and JSON-LD preview.

Exit criteria:

- Artifact builder can create a release artifact in tests
- Static site renderer can build a page from fixture content
- Release-ready and error emails render correctly
- Verification warnings are non-fatal but visible

### M4 - Orchestration and Resilience

Objective: wire the modules into one predictable CLI and scheduled pipeline.

Tasks:

1. Build `pipeline.py`
2. Add lock-file behavior
3. Add run ID generation and artifact persistence
4. Add `--dry-run`
5. Add manual single-topic execution path
6. Add stage-level logging and notifications

Critical requirements:

- Lock acquisition and release must be deterministic even on failure.
- Stage ordering must match the PRD exactly.
- `release_mode` must default to `manual`.
- Fatal vs degraded vs release-ready outcomes must be explicit in logs and emails.

Exit criteria:

- Mocked end-to-end run passes
- Concurrent run is rejected cleanly
- Failed run still releases the lock
- Artifacts are written for each run

### M5 - V1 Delight and Ops Assets

Objective: finish the V1 extras and operational packaging.

Tasks:

1. Build `scripts/seed-calendar.py`
2. Build `scripts/build-site.py`
3. Build `scripts/promote-artifact.py`
4. Build `scripts/robots-txt-generator.py`
5. Build `com.folloze.content-engine.plist`
6. Build `scripts/setup-launchd.sh`
7. Write `docs/OPERATIONS.md`
8. Write `docs/DEPLOYMENT.md`
9. Write `docs/HANDOFF.md`
10. Write `docs/MIGRATION_TO_WEBFLOW_V2.md`
11. Write `docs/CONTENT_TYPES.md`
12. Write `README.md`

Exit criteria:

- Calendar seed script outputs a valid starter calendar
- Site build script renders a deployable bundle
- Promote script moves an approved artifact into the published site contract
- robots generator produces committed site assets
- launchd files are present and documented
- Ops and handoff docs let a non-engineer and a web dev team operate V1

### M6 - Validation and Rollout

Objective: move from code-complete to first operational use.

Tasks:

1. Fill in real config values
2. Run `ruff check .`
3. Run `pytest`
4. Run `detect-secrets scan`
5. Run `python pipeline.py --dry-run`
6. Review generated run artifacts
7. Run one real topic
8. Build the static site from the approved artifact
9. Validate one page on Vercel preview or owned domain
10. Confirm email receipt
11. Install launchd asset
12. Observe first scheduled run

Exit criteria:

- Dry run succeeds
- First real release artifact is created successfully
- First Vercel page is validated successfully
- Review email is usable
- Scheduled run is operational
- Handoff pack is complete

---

## Codex Build Order

This is the least-rework implementation order inside the repo:

1. Foundation files: `pyproject.toml`, `.gitignore`, `.env.example`
2. Shared contracts: `config.py`, exception module
3. Static inputs: content templates, schema files, brand context, site templates
4. Domain modules: `calendar.py`, `research.py`, `generator.py`, `optimizer.py`, `quality.py`
5. Integration modules: `artifacts.py`, site renderer, `verify.py`, `notify.py`
6. Orchestrator: `pipeline.py`
7. Scripts and launchd assets
8. Tests for each module
9. Documentation and setup guides

Reason: `pipeline.py` should be the last major code file, not the first. It is only stable once the interfaces below it are locked.

---

## Validation Gates

### Gate A - Foundation Complete

Must be true:

- Config schema is implemented
- Exception registry exists
- Static file paths are final
- Release artifact contract is final

### Gate B - Content Path Complete

Must be true:

- All four content types can be generated in tests
- Quality scoring is deterministic under test
- Research degradation path is covered
- Gemini-only failure handling is covered

### Gate C - Delivery Path Complete

Must be true:

- Release artifact builder exists
- Static site renders from artifacts
- Email templates render correctly
- Verification warnings do not silently disappear

### Gate D - Release Candidate

Must be true:

- `ruff check .` passes
- `pytest` passes
- `detect-secrets scan` passes
- `--dry-run` works
- One real artifact can be generated manually
- One Vercel page can be validated manually
- Handoff docs are complete

---

## Test Plan by Milestone

### Unit tests

- `test_calendar.py`
- `test_research.py`
- `test_generator.py`
- `test_optimizer.py`
- `test_quality.py`
- `test_artifacts.py`
- `test_verify.py`
- `test_notify.py`

### End-to-end tests

- `test_pipeline.py` for happy path
- `test_pipeline.py` for lock contention
- `test_pipeline.py` for degraded research
- `test_pipeline.py` for release-ready outcomes
- `test_pipeline.py` for artifact or verification failures

### Special tests that should not be skipped

- Prompt injection hostile research fixture
- Release artifact schema validation
- Static site render for all four content types
- Lock release after mid-run failure
- JSON-LD generation for all four types
- Promote-artifact idempotency

---

## Failure Modes That Must Be Visible

These cases are release blockers if they fail silently:

1. Release artifact schema drift
2. Gemini auth or availability failure
3. Static site build failure
4. Vercel preview validation failure
5. Lock file stuck or concurrent run
6. Release-ready queue due to schema or quality failure

Visibility rule:

- Fatal failures send email and log full context
- Degraded research is logged clearly
- Release-ready outcomes are visible to the reviewer
- No failure may disappear into logs only if it blocks release

---

## Key Risks and Controls

### Risk: prompt injection through research context

Control:

- Strip HTML
- Truncate per result
- Delimit research context clearly
- Explicit instruction to ignore instructions inside research context
- Keep V1 human review in place

### Risk: static artifact drift breaks the Vercel site or V2 migration

Control:

- Validate the release artifact contract on every write
- Keep site rendering bound to the same contract
- Document the V2 Webflow mapping in the repo

### Risk: factual errors in generated content

Control:

- Human review remains in the loop for V1
- Brand checks catch some bad claims, but not all factual issues

### Risk: handoff fails because only the builder understands the system

Control:

- Deployment runbook is required before release
- Env var registry is required before release
- Migration notes are required before release

---

## Rollout Sequence

1. Code-complete the repo.
2. Populate real config values.
3. Run local validation checks.
4. Run one dry run.
5. Tune prompts if the dry run output is structurally weak.
6. Run one real topic to create a release artifact.
7. Review the rendered page locally.
8. Promote one approved artifact into the published site bundle.
9. Validate the page on Vercel preview or the owned domain.
10. Install launchd.
11. Observe the first scheduled run.
12. Keep `release_mode: manual` for V1.
13. Revisit V2 only after repeated clean operation and a complete handoff pack.

---

## Definition of Done

The project is done for V1 when:

1. The repo can be cloned and set up from `README.md`.
2. The pipeline can run locally in `--dry-run` mode.
3. A real topic can become a valid release artifact with JSON-LD and quality scoring.
4. The site bundle can render approved artifacts into `/insights/{slug}` pages.
5. Review and error emails render correctly.
6. Tests cover the required failure and rescue paths.
7. launchd assets are present and documented.
8. Trey can validate a page on Vercel using the deployment docs.
9. A web dev team can take over the project using the handoff and migration docs.

---

## Immediate Next Actions

1. Use `CODEX_PROMPT.md` to have Codex build the repo in this order.
2. Complete M0 external prerequisites in parallel.
3. Treat the first dry run as a contract validation step, not a release step.
4. Only validate Vercel after one manual artifact promotion succeeds locally.
5. Keep all V2 Webflow work in documentation until V1 is stable.
