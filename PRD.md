# Folloze Content Engine — PRD

**Version:** 1.1  
**Date:** 2026-03-20  
**Owner:** Trey Harnden  
**Agent operator:** Juno (OpenClaw)  
**Status:** Ready for build

---

## Overview

Folloze Content Engine is an automated AEO (Answer Engine Optimization) content pipeline that generates, optimizes, packages, and validates content for a Vercel-hosted Insights site under Trey-owned domain infrastructure. The system targets LLM crawlers first (GPTBot, ClaudeBot, PerplexityBot), human-readable second. Goal: Folloze appears as a cited source in LLM-generated answers for B2B marketing orchestration queries.

This is a new project, not a fork of ElevationEngine. It borrows the pipeline orchestration pattern from EE but has a different delivery target, content strategy, and artifact contract. V1 ships on a Vercel-hosted static site. V2 migrates the same content contract into Webflow after handoff to the marketing and web-dev teams.

---

## Business Outcome

When prospects ask ChatGPT, Perplexity, or Claude "what's the best ABM platform," "Folloze vs Mutiny," or "how does AI marketing orchestration work," Folloze appears in the answer. This channel cannot be bought. It must be earned through structured, citable content with a reliable publishing and handoff workflow.

---

## Product Intent

V1 is not a CMS. It is a disciplined content production and release system.

V1 must:

1. Generate one high-quality content artifact at a time.
2. Render approved artifacts into a static `/insights/` site that can be tested on Vercel.
3. Preserve logs, artifacts, and release documentation so the web-dev team can take over later.
4. Keep human review and manual production promotion in place.

V1 must not:

1. Depend on Webflow to ship.
2. Depend on provider abstraction or multi-provider fallback logic.
3. Hide deployment or migration knowledge outside the repo.

---

## Architecture

```text
CONTENT CALENDAR (YAML)
        │
        ▼
  ┌─────────────┐    ┌───────────────┐
  │ pipeline.py │───▶│ calendar.py   │ parse next unprocessed topic
  │ orchestrator│    └───────────────┘
  │             │    ┌───────────────┐
  │             │───▶│ research.py   │ Brave + Perplexity + brand docs + Gemini synthesis
  │             │    └───────────────┘
  │             │    ┌───────────────┐
  │             │───▶│ generator.py  │ Gemini content generation
  │             │    └───────────────┘
  │             │    ┌───────────────┐
  │             │───▶│ optimizer.py  │ AEO HTML + JSON-LD schema
  │             │    └───────────────┘
  │             │    ┌───────────────┐
  │             │───▶│ quality.py    │ AEO scorecard + brand check
  │             │    └───────────────┘
  │             │    ┌───────────────┐
  │             │───▶│ artifacts.py  │ release artifact + site bundle inputs
  │             │    └───────────────┘
  │             │    ┌───────────────┐
  │             │───▶│ verify.py     │ local bundle + deployed URL validation
  │             │    └───────────────┘
  │             │    ┌───────────────┐
  │             │───▶│ notify.py     │ email notifications
  └─────────────┘    └───────────────┘
                         │
                         ▼
                  site/published/*.json
                         │
                         ▼
                   scripts/build-site.py
                         │
                         ▼
                     site/dist/
                         │
                         ▼
                 Vercel-hosted static site
```

**External dependencies:**

- Vercel-hosted static site for preview and production validation
- Brave Search API
- Perplexity API
- Gemini API
- SMTP / SendGrid

---

## Project Structure

```text
folloze-content-engine/
├── pipeline.py                 # Main orchestrator (entry point)
├── calendar.py                 # Topic queue parser
├── research.py                 # Research enrichment (Brave, Perplexity, brand docs)
├── generator.py                # Gemini content generation
├── optimizer.py                # AEO HTML + JSON-LD schema generation
├── quality.py                  # Quality gate (AEO scorecard + brand check)
├── artifacts.py                # Release-artifact writer and artifact validation
├── verify.py                   # Local and deployed page verification
├── notify.py                   # Email notifications
├── config.py                   # Config loader + validation
│
├── config.yaml                 # Runtime configuration
│
├── content/
│   ├── calendar.yaml           # Topic queue (Juno manages this)
│   └── templates/
│       ├── comparison.md       # Prompt template for comparison pages
│       ├── guide.md            # Prompt template for definitive guides
│       ├── faq.md              # Prompt template for FAQ hubs
│       └── glossary.md         # Prompt template for glossary/definitions
│
├── schema/
│   ├── comparison.json         # JSON-LD template: Article + FAQPage
│   ├── guide.json              # JSON-LD template: Article or HowTo
│   ├── faq.json                # JSON-LD template: FAQPage
│   └── glossary.json           # JSON-LD template: DefinedTerm + Article
│
├── brand/
│   └── context.md              # Folloze brand voice, proof points, ICP, banned terms
│
├── site/
│   ├── templates/
│   │   ├── base.html           # Shared page shell
│   │   └── insight.html        # Page template for /insights/{slug}
│   ├── assets/
│   │   └── styles.css          # Minimal static styles
│   ├── published/
│   │   ├── index.json          # Published artifact manifest
│   │   └── *.json              # Approved content artifacts for the public site
│   └── dist/                   # Generated static output for Vercel deployment
│
├── scripts/
│   ├── setup-launchd.sh        # Install launchd plist (macOS scheduling)
│   ├── seed-calendar.py        # One-time competitive gap seed
│   ├── build-site.py           # Render site/dist from site/published
│   ├── promote-artifact.py     # Copy approved artifact into site/published
│   └── robots-txt-generator.py # Generate AI-bot-optimized robots.txt and sitemap assets
│
├── com.folloze.content-engine.plist  # launchd config (daily 9 AM CT)
│
├── logs/
│   ├── content-engine.log      # Rolling text log
│   └── runs/
│       └── YYYY-MM-DD/
│           ├── run-manifest.json
│           ├── research-context.json
│           ├── generated-content.json
│           ├── optimized-content.html
│           ├── quality-report.json
│           ├── release-artifact.json
│           └── rendered-preview.html
│
├── tests/
│   ├── test_calendar.py
│   ├── test_research.py
│   ├── test_generator.py
│   ├── test_optimizer.py
│   ├── test_quality.py
│   ├── test_artifacts.py
│   ├── test_verify.py
│   ├── test_notify.py
│   └── test_pipeline.py
│
├── docs/
│   ├── OPERATIONS.md           # Marketing and operator guide
│   ├── DEPLOYMENT.md           # Vercel deployment and validation runbook
│   ├── HANDOFF.md              # Web-dev handoff pack
│   ├── MIGRATION_TO_WEBFLOW_V2.md  # V2 field mapping and migration notes
│   └── CONTENT_TYPES.md        # Content type guide with examples
│
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
└── TODOS.md
```

---

## Configuration (`config.yaml`)

```yaml
# Runtime configuration — commit safe (no secrets)
site:
  origin: "https://insights.folloze.com"
  insights_path: "/insights"

delivery:
  target: "vercel_static"
  release_mode: "manual"           # V1 manual promotion only
  preview_url: "https://folloze-insights-preview.vercel.app"
  production_url: "https://insights.folloze.com"

pipeline:
  quality_threshold: 70            # AEO score out of 100 (0-100)
  max_retries_llm: 2
  verify_timeout_seconds: 300
  timezone: "America/Chicago"
  run_hour: 9
  log_level: "INFO"
  max_log_age_days: 30

notifications:
  email:
    enabled: true
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    from_address: "hermes@elevationengine.co"
    # Default Folloze Insights email recipients (errors/failures and non-weekly-GEO mail)
    to_addresses:
      - "trey.harnden@folloze.com"
    # Weekly GEO summary recipients only
    weekly_geo_to_addresses:
      - "trey.harnden@folloze.com"
      - "kristi.tutt@folloze.com"

content:
  default_audience: "B2B revenue teams"
  min_words_by_type:
    comparison: 900
    guide: 1000
    faq: 700
    glossary: 500

llm:
  provider: "gemini"
  generation_model: "gemini-2.5-flash"
  research_model: "gemini-2.5-flash"
```

---

## Release Artifact Contract

Each successful run that clears the quality gate writes `logs/runs/YYYY-MM-DD/release-artifact.json`.

Required fields:

| Field | Type | Required | Notes |
|---|---|---|---|
| `title` | string | Yes | Page title / H1 |
| `slug` | string | Yes | URL slug |
| `route` | string | Yes | `/insights/{slug}` |
| `content_type` | string | Yes | comparison, guide, faq, glossary |
| `body_html` | string | Yes | Full page HTML body |
| `meta_title` | string | Yes | SEO title |
| `meta_description` | string | Yes | SEO description |
| `json_ld` | string | Yes | JSON-LD markup |
| `target_keywords` | array[string] | Yes | Primary + secondary keywords |
| `published_date` | string | Yes | ISO date |
| `citation_score` | integer | Yes | AEO score 0-100 |
| `word_count` | integer | Yes | Rendered word count |
| `canonical_url` | string | Yes | `site.origin + route` |
| `source_run_id` | string | Yes | Trace back to run logs |
| `status` | string | Yes | `release_ready` or `published` |
| `review_notes` | array[string] | No | Quality warnings or operator notes |

The artifact contract is the stable interface between:

1. The Python content pipeline
2. The V1 Vercel static site
3. The V2 Webflow migration

---

## V2 Webflow Mapping Contract

V2 must map the release artifact contract into a Webflow collection without changing upstream modules.

| V1 artifact field | V2 Webflow field |
|---|---|
| `title` | `name` |
| `slug` | `slug` |
| `content_type` | `content-type` |
| `body_html` | `body` |
| `meta_title` | `meta-title` |
| `meta_description` | `meta-description` |
| `json_ld` | `json-ld` |
| `target_keywords` | `target-keywords` |
| `published_date` | `published-date` |
| `citation_score` | `citation-score` |
| `word_count` | `word-count` |

This mapping must be documented in `docs/MIGRATION_TO_WEBFLOW_V2.md` before V1 is considered complete.

---

## Content Types

### 1. Comparison (`comparison`)
**Target citation rate:** ~33%  
**URL pattern:** `/insights/folloze-vs-{competitor}`, `/insights/{concept-a}-vs-{concept-b}`  
**Schema:** Article + FAQPage JSON-LD  
**Min words:** 900

Required sections:

- TL;DR comparison table (always first)
- What is [A]? (definition block)
- What is [B]? (definition block)
- Feature-by-feature comparison (3-5 dimensions)
- Pricing comparison
- Who should choose [A] vs [B]?
- Bottom line
- FAQ (5 Q&A pairs)

### 2. Definitive Guide (`guide`)
**Target citation rate:** ~15%  
**URL pattern:** `/insights/{topic}-guide-{year}`, `/insights/how-to-{action}`  
**Schema:** Article or HowTo JSON-LD  
**Min words:** 1000

Required sections:

- What is [topic]? (definition block first)
- Why [topic] matters
- Step-by-step
- Common mistakes
- Tools and resources
- FAQ (5 Q&A pairs)

### 3. FAQ Hub (`faq`)
**Target citation rate:** ~25%  
**URL pattern:** `/insights/{topic}-faq`, `/insights/{topic}-questions`  
**Schema:** FAQPage JSON-LD  
**Min words:** 700

Required structure:

- 10-15 Q&A pairs
- Questions must match natural language queries
- Each answer must be 2-4 sentences, direct and complete
- No "learn more" redirects inside answers

### 4. Glossary (`glossary`)
**Target citation rate:** ~20%  
**URL pattern:** `/insights/what-is-{term}`, `/insights/{term}-definition`  
**Schema:** DefinedTerm + Article JSON-LD  
**Min words:** 500

Required sections:

- One-sentence definition first
- Extended definition
- How [term] works in practice
- [Term] vs related concepts
- FAQ (3-5 Q&A pairs)

---

## AEO Content Requirements (all types)

1. Cite sources for every statistic.
2. Include specific numbers, not vague claims.
3. Use quotations when useful.
4. Keep tone authoritative and direct.
5. Avoid keyword stuffing.
6. Make paragraphs self-contained.
7. Define every technical term on first use.
8. Use comparison tables where relevant.
9. Keep heading structure machine-readable.

---

## JSON-LD Requirements

Every page requires JSON-LD in the rendered HTML `<head>` of the V1 static site.

**All pages minimum:**

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "...",
  "description": "...",
  "author": {
    "@type": "Organization",
    "name": "Folloze",
    "url": "https://www.folloze.com"
  },
  "publisher": {
    "@type": "Organization",
    "name": "Folloze"
  },
  "datePublished": "YYYY-MM-DD",
  "dateModified": "YYYY-MM-DD",
  "mainEntityOfPage": {
    "@type": "WebPage",
    "@id": "https://insights.folloze.com/insights/{slug}"
  }
}
```

**FAQ pages additionally:**

```json
{
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "...",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "..."
      }
    }
  ]
}
```

Use `@graph` to combine multiple schema types on one page.

---

## Quality Gate

Pages must pass all of the following before entering the release-ready queue.

### AEO Scorecard (target ≥70/100)

| Check | Points | Method |
|---|---|---|
| Has definition block in first 100 words | 15 | Regex check |
| Has comparison table (if type=comparison) | 15 | HTML `<table>` present |
| Contains ≥2 cited sources | 15 | Link + attribution text pattern |
| Contains ≥1 statistic with number | 10 | Regex |
| Contains FAQ section | 10 | Heading check |
| Word count ≥ minimum for type | 10 | Word count check |
| JSON-LD schema validates | 10 | Local JSON/schema check |
| No keyword stuffing (primary keyword ≤5 uses) | 10 | Frequency count |
| Self-contained paragraphs (avg ≤4 sentences) | 5 | Sentence count per paragraph |

### Brand Check

Read brand context from `brand/context.md`. Fail if:

- Contains banned terms: "buyer experience platform", "revolutionary", "cutting-edge", "set it and forget it", "generator AI", "ABM platform" as category
- Contains em dashes or emojis
- Missing at least one Folloze proof point or Folloze product reference
- Makes competitor claims not supported by competitive intel context

---

## Error Handling Requirements

Every exception must be named, caught, and handled. No bare `except:` or `except Exception:`.

| Scenario | Exception class | Action |
|---|---|---|
| Calendar file missing | `FileNotFoundError` | Notify + exit clean |
| Calendar YAML corrupt | `yaml.YAMLError` | Notify + exit 1 |
| No unprocessed topics | `CalendarExhaustedError` | Notify + exit clean |
| Research API timeout | `requests.Timeout` | Retry 2x, degrade to brand-docs-only |
| Research API 429 | `RateLimitError` | Backoff, retry, degrade |
| Gemini empty response | `EmptyResponseError` | Retry 1x with stronger instruction |
| Gemini refusal | `RefusalError` | Skip topic, notify |
| Gemini unavailable | `ProviderUnavailableError` | Queue topic, notify, exit |
| Content below word count | `ValidationError` | Retry with expand instruction |
| JSON-LD template missing | `TemplateError` | Should not happen — caught by tests |
| Release artifact write failure | `ArtifactWriteError` | Log full context, notify, exit |
| Published manifest corrupt | `ArtifactSchemaError` | Block promotion, notify urgently |
| Page not live after timeout | `VerificationTimeoutError` | Log warning, notify |
| Deployed page missing expected metadata | `PreviewValidationError` | Block release, notify |

---

## Email Notification Spec

### Release ready for review (V1)
**Trigger:** Quality gate PASS  
**Subject:** `[Folloze Insights] Release ready: {title}`

Body:

- Title + content type + AEO score
- Intended route
- JSON-LD preview
- Review notes and warnings
- Run ID and artifact path
- Instructions: review rendered preview, then promote the artifact if approved

### Published successfully
**Trigger:** Approved artifact rendered and validated on Vercel  
**Subject:** `[Folloze Insights] Published: {title}`

Body:

- Live URL
- AEO score
- Content type
- Word count
- Validation status

### Pipeline error
**Trigger:** Any unrecoverable error  
**Subject:** `[Folloze Insights] ERROR: {error_type}`

Body:

- Error type
- Stage
- Full traceback
- Suggested fix

### Validation blocked
**Trigger:** `PreviewValidationError` or related release blocker  
**Subject:** `[URGENT] Folloze Insights: release blocked for {title}`

Body:

- Blocking validation result
- Last known route or URL
- Next step to recover

---

## Secrets & Environment Variables

All secrets in macOS Keychain, exported via `~/.zshrc`.

| Env var | Keychain service name | Purpose |
|---|---|---|
| `BRAVE_API_KEY` | `brave-search-api` | Research enrichment |
| `PERPLEXITY_API_KEY` | `perplexity-api` | Research enrichment |
| `GEMINI_API_KEY` | `gemini-api-key` | Gemini generation and research synthesis |
| `SMTP_PASSWORD` | `smtp-password` | Email notifications |
| `NOTIFY_EMAIL_TO` | (optional override) | Overrides config-based email routing for all notification emails; leave unset to preserve split routing between default Insights/error recipients and weekly GEO recipients |

**`.env.example` must document all of the above. Never write actual values to any file.**

---

## Scheduling (launchd)

File: `com.folloze.content-engine.plist`  
Install: `~/Library/LaunchAgents/com.folloze.content-engine.plist`  
Schedule: 9:00 AM America/Chicago daily  
Entry point: `python /Users/treyharnden/Projects/folloze-content-engine/pipeline.py`  
Logs: `logs/launchagent.log`, `logs/launchagent-error.log`

Install command: `scripts/setup-launchd.sh`

---

## Juno's Role (Agent Operations)

Juno operates the content engine after it is built:

- Weekly: seed `content/calendar.yaml` with new topics
- Daily: review release-ready emails and run manual approvals when needed
- Monthly: review citation performance and content mix
- Ad hoc: manual run via `python pipeline.py --topic "..." --type comparison`

Juno's expanded skills: `ai-seo`, `schema-markup`, `aeo-citation-review`, `content-strategy`

---

## Competitive Content Gap Seed (V1)

Script: `scripts/seed-calendar.py`

Purpose:

1. Scrape competitor sitemaps for Mutiny, Userled, and PathFactory
2. Extract likely topics
3. Score each gap using Gemini for citation value and content type
4. Output starter entries into `content/calendar.yaml`

---

## robots.txt Optimization (V1)

Script: `scripts/robots-txt-generator.py`

Outputs:

- `site/assets/robots.txt`
- `site/assets/insights-sitemap.xml`

AI bot user agents to explicitly allow:

- `GPTBot`
- `ChatGPT-User`
- `ClaudeBot`
- `anthropic-ai`
- `PerplexityBot`
- `Google-Extended`
- `Bingbot`
- `Bytespider`
- `Applebot-Extended`
- `cohere-ai`
- `CCBot`
- `ia_archiver`

---

## Testing Requirements

**Framework:** `pytest` with `pytest-mock`

Every module has a dedicated test file. Minimum coverage:

| Test file | Key scenarios |
|---|---|
| `test_calendar.py` | Valid YAML, empty calendar, malformed, all-processed, duplicate slugs |
| `test_research.py` | Brave success, Brave timeout, Brave 429, Perplexity success, Perplexity failure, degraded synthesis, brand docs missing |
| `test_generator.py` | All 4 content types, word count pass, word count fail + retry, Gemini refusal, Gemini empty, Gemini unavailable |
| `test_optimizer.py` | All 4 JSON-LD types, schema validation pass, schema validation fail |
| `test_quality.py` | Score ≥70, score <70, banned terms, missing proof point |
| `test_artifacts.py` | Artifact schema validation, route generation, preview render output |
| `test_verify.py` | Local page render valid, deployed page valid, JSON-LD missing, timeout |
| `test_notify.py` | Release-ready email renders, error email renders, success email renders |
| `test_pipeline.py` | Full happy path, lock contention, degraded research, partial failure recovery |

Run: `pytest tests/ -v`

Pre-release checks:

- `ruff check .`
- `pytest`
- `detect-secrets scan`
- `python pipeline.py --dry-run`
- `python scripts/build-site.py`

---

## Phase Roadmap

| Phase | Scope | Status |
|---|---|---|
| **Phase 1 (V1)** | Content engine + release artifacts + Vercel validation + handoff docs | **Build now** |
| **Phase 2** | Webflow migration + marketing handoff | After V1 stabilizes |
| **Phase 3** | Citation monitor + gap analyzer + Slack notifications | After multiple pages are live |
| **Phase 4** | Self-seeding calendar | After citation data exists |
| **Phase 5** | Freshness auto-refresh | After content library matures |

---

## TODOS

See `TODOS.md` for full backlog. The important framing change is:

- Webflow migration is a V2 delivery-target project, not a V1 dependency.
- Slack notifications no longer define Phase 2 by themselves.

---

## Prerequisites (before build starts)

1. Vercel project created and reachable
2. Owned domain or subdomain selected for V1
3. Preview and production URLs recorded
4. SMTP credentials confirmed
5. Juno skill list updated

---

## Brand Context Quick Reference

Full context in `brand/context.md`. Key points for code:

**One-line:** "Folloze is an AI orchestration platform that enables B2B revenue teams to launch, optimize, and prove autonomous campaigns from prompt to pipeline."

**Approved terms:** AI orchestration platform, autonomous marketing, prompt to pipeline, revenue teams, ABM, demand gen, campaign orchestration

**Banned terms:** buyer experience platform, revolutionary, cutting-edge, set it and forget it, generator AI, em dashes, emojis

**Proof points:**

- Conga: $6.3M attributed pipeline
- Microsoft: 560 leads, 478 MQLs, $10M influenced pipeline
- RingCentral: 98% account engagement
- ServiceNow: $750K/year savings
- Campaign Agent: 5x faster campaign creation
