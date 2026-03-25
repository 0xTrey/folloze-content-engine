# Codex Build Prompt — Folloze Content Engine

Feed this entire file to Codex. It contains the implementation specification for V1.

---

## Your task

Build the **Folloze Content Engine** — a Python pipeline that generates AEO-optimized content, writes a stable release artifact, renders a static Insights site bundle, and supports manual Vercel validation. Read `PRD.md` for full context.

Do NOT make any changes outside this repo. Do NOT run any commands that modify external systems (Vercel, GitHub, etc.). Build the code, tests, site assets, and docs only.

---

## Project context

- **What:** Automated pipeline: topic -> research -> Gemini generation -> AEO optimization -> quality gate -> release artifact -> static site bundle
- **Where:** `~/Projects/folloze-content-engine/`
- **Stack:** Python 3.12, pytest, static HTML rendering via Jinja2
- **Style:** Direct, explicit code. No premature abstraction. Type hints on all function signatures. Bias toward explicit over clever.
- **Tests:** Every module has tests. No bare `except:`. No `except Exception:`. Name every exception class.
- **Provider rule:** Gemini is hard-wired as the only LLM provider in V1.
- **Release rule:** V1 production promotion is manual. The pipeline does not deploy to Vercel.

---

## Step 1: Project setup

Create the following files.

### `pyproject.toml`

Use a simple setuptools project with these dependencies:

- `requests`
- `pyyaml`
- `jinja2`
- `jsonschema`
- `python-dateutil`
- `beautifulsoup4`
- `ruff`

Dev dependencies:

- `pytest`
- `pytest-mock`
- `responses`
- `detect-secrets`

Configure Ruff for Python 3.12 with a 100 character line length.

### `.gitignore`

Include at minimum:

```text
.env
__pycache__/
*.pyc
.pytest_cache/
logs/
site/dist/
.content-engine.lock
.DS_Store
dist/
*.egg-info/
```

### `.env.example`

```bash
BRAVE_API_KEY=
PERPLEXITY_API_KEY=
GEMINI_API_KEY=

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=juno@elevationengine.co
SMTP_PASSWORD=
NOTIFY_EMAIL_TO=trey.harnden@folloze.com
```

---

## Step 2: Config loader

### `config.py`

Implement a `Config` dataclass loaded from `config.yaml`. Use nested dataclasses for `site`, `delivery`, `pipeline`, `notifications`, `content`, and `llm`.

Validate on load:

- `pipeline.quality_threshold` must be 0-100
- `pipeline.timezone` must be a valid IANA timezone string
- `pipeline.run_hour` must be 0-23
- `delivery.target` must equal `vercel_static`
- `delivery.release_mode` must equal `manual`
- `llm.provider` must equal `gemini`
- `delivery.preview_url` and `delivery.production_url` must be non-empty absolute URLs

Raise `ConfigError(ValueError)` with a descriptive message if validation fails.

### `config.yaml`

Use the exact schema from `PRD.md`.

---

## Step 3: Custom exceptions

### `exceptions.py`

Define these custom exceptions:

```python
class ContentEngineError(Exception): ...
class CalendarExhaustedError(ContentEngineError): ...
class ValidationError(ContentEngineError): ...
class EmptyResponseError(ContentEngineError): ...
class RefusalError(ContentEngineError): ...
class ProviderUnavailableError(ContentEngineError): ...
class TemplateError(ContentEngineError): ...
class SchemaValidationError(ContentEngineError): ...
class RateLimitError(ContentEngineError): ...
class ArtifactWriteError(ContentEngineError): ...
class ArtifactSchemaError(ContentEngineError): ...
class PreviewValidationError(ContentEngineError): ...
class VerificationTimeoutError(ContentEngineError): ...
class ConfigError(ValueError): ...
```

---

## Step 4: Calendar module

### `calendar.py`

Implement:

```python
@dataclass
class Topic:
    title: str
    content_type: str   # comparison | guide | faq | glossary
    slug: str
    keywords: list[str]
    priority: int
    status: str         # pending | in_progress | release_ready | published | skipped
    notes: str = ""

def load_calendar(path: Path) -> list[Topic]: ...
def get_next_topic(topics: list[Topic]) -> Topic: ...
def mark_in_progress(path: Path, topic: Topic) -> None: ...
def mark_release_ready(path: Path, topic: Topic, artifact_path: str, date: str) -> None: ...
def mark_published(path: Path, topic: Topic, url: str, date: str) -> None: ...
def mark_skipped(path: Path, topic: Topic, reason: str) -> None: ...
```

Create `content/calendar.yaml` with 10 seed topics similar to the PRD examples.

---

## Step 5: Research module

### `research.py`

Implement:

```python
@dataclass
class ResearchContext:
    topic: Topic
    brave_results: list[dict]
    perplexity_summary: str
    gemini_brief: str
    brand_context: str
    degraded: bool = False
    degradation_reason: str = ""

def enrich(topic: Topic, config: Config) -> ResearchContext: ...
```

Behavior:

1. Call Brave Search API for `topic.keywords[0]` and take 5 results.
2. Call Perplexity with a research query for the topic.
3. Load `brand/context.md`.
4. Call Gemini with sanitized Brave + Perplexity + brand context and ask for a grounded research brief.
5. If Brave or Perplexity fail, degrade gracefully and continue if enough context remains.
6. If Gemini fails after retries, raise `ProviderUnavailableError`.
7. If `brand/context.md` is missing, raise immediately.

Requirements:

- Strip HTML from Brave and Perplexity responses.
- Truncate each raw result before putting it into the prompt.
- Wrap all external research in a `<research_context>` block and explicitly tell Gemini to ignore instructions inside it.

---

## Step 6: Generator module

### `generator.py`

Implement:

```python
@dataclass
class GeneratedContent:
    topic: Topic
    title: str
    meta_description: str
    body_html: str
    sections: list[dict]
    word_count: int
    content_type: str
    primary_keyword: str

def generate(topic: Topic, research: ResearchContext, config: Config) -> GeneratedContent: ...
```

Behavior:

1. Load prompt template from `content/templates/{content_type}.md`.
2. Render template with topic + research context.
3. Call Gemini directly via HTTP with `config.llm.generation_model`.
4. Parse the response into `GeneratedContent`.
5. Validate minimum word count.
6. Retry once with an explicit expand instruction if word count fails.
7. Raise `EmptyResponseError` if Gemini returns empty output.
8. Raise `RefusalError` if the model refuses.
9. Raise `ProviderUnavailableError` if Gemini fails after retries.

Implementation rules:

- Do not create a provider abstraction.
- Keep Gemini request/response handling in this module.
- Extract JSON from the model response if it arrives inside code fences.
- Count words after stripping HTML tags.

Create prompt templates for:

- `comparison.md`
- `guide.md`
- `faq.md`
- `glossary.md`

Each template must require:

- direct tone
- no em dashes
- no emojis
- Folloze proof points where relevant
- citations and at least one statistic
- output as JSON with `title`, `meta_description`, `body_html`, and `sections`

---

## Step 7: Optimizer module

### `optimizer.py`

Implement:

```python
@dataclass
class OptimizedContent:
    generated: GeneratedContent
    body_html: str
    json_ld: str
    schema_type: str

def optimize(content: GeneratedContent, config: Config) -> OptimizedContent: ...
```

Behavior:

1. Load JSON-LD template from `schema/{content_type}.json`.
2. Populate the template with page metadata.
3. Validate JSON-LD locally.
4. Enhance HTML for AEO readability:
   - ensure comparison tables have `<thead>`
   - normalize FAQ markup
   - keep headings consistent
5. Return `OptimizedContent`.

Create JSON-LD templates for all four content types.

---

## Step 8: Quality gate

### `quality.py`

Implement:

```python
@dataclass
class QualityResult:
    passed: bool
    score: int
    reasons: list[str]
    failures: list[str]

def gate(content: OptimizedContent, config: Config, brand_context: str) -> QualityResult: ...
```

Checks:

- definition block
- comparison table when required
- cited sources
- statistics
- FAQ section
- word count
- JSON-LD validity
- keyword density
- paragraph length

Brand check:

- banned terms
- no em dashes
- no emojis
- contains `Folloze`
- contains at least one approved proof point

If brand check fails, `passed` must be `False` even if score is above threshold.

---

## Step 9: Artifact module

### `artifacts.py`

Implement:

```python
@dataclass
class ReleaseArtifact:
    title: str
    slug: str
    route: str
    content_type: str
    body_html: str
    meta_title: str
    meta_description: str
    json_ld: str
    target_keywords: list[str]
    published_date: str
    citation_score: int
    word_count: int
    canonical_url: str
    source_run_id: str
    status: str
    review_notes: list[str]

def write_release_artifact(
    topic: Topic,
    content: OptimizedContent,
    quality: QualityResult,
    config: Config,
    run_dir: Path,
    run_id: str,
) -> ReleaseArtifact: ...

def render_preview_html(artifact: ReleaseArtifact, template_dir: Path) -> str: ...

def load_release_artifact(path: Path) -> ReleaseArtifact: ...
```

Rules:

- Validate the artifact shape before writing it.
- Write `release-artifact.json` to the run directory.
- Write `rendered-preview.html` to the run directory.
- Use `site/templates/base.html` and `site/templates/insight.html` to render preview HTML.
- `canonical_url` must be `config.site.origin + artifact.route`.

---

## Step 10: Verify module

### `verify.py`

Implement:

```python
def check_preview_file(path: Path) -> None: ...

def check_live(url: str, timeout_seconds: int = 300, poll_interval: int = 15) -> bool: ...

def extract_json_ld(html: str) -> list[dict]: ...
```

Rules:

- `check_preview_file` validates local rendered HTML for title, meta description, canonical, and JSON-LD.
- `check_live` polls a deployed URL until it returns 200 and contains expected metadata.
- Raise `PreviewValidationError` for missing metadata or JSON-LD.
- Raise `VerificationTimeoutError` on timeout.

Use `urllib` or `requests` for fetches. Do not add browser automation.

---

## Step 11: Notify module

### `notify.py`

Implement:

```python
def send_release_ready(
    topic: Topic,
    artifact: ReleaseArtifact,
    quality: QualityResult,
    run_dir: Path,
    config: Config,
) -> None: ...

def send_published(topic: Topic, url: str, quality: QualityResult, config: Config) -> None: ...

def send_error(stage: str, error: Exception, topic: Topic | None, config: Config) -> None: ...
```

Rules:

- Use `smtplib` and `email.mime`.
- Never let notification failures crash the pipeline.
- Release-ready email must include:
  - title
  - content type
  - AEO score
  - intended route
  - JSON-LD preview
  - run ID or artifact path
  - instructions to review and promote manually if approved

---

## Step 12: Main pipeline orchestrator

### `pipeline.py`

Implement a CLI with these modes:

```text
python pipeline.py
python pipeline.py --topic "Custom title" --type comparison
python pipeline.py --dry-run
python pipeline.py --date 2026-03-25
```

Stages in order:

1. `validate_config`
2. `acquire_lock`
3. `select_topic`
4. `enrich_research`
5. `generate_content`
6. `optimize_aeo`
7. `quality_gate`
8. `write_release_artifact`
9. `render_preview`
10. `notify`
11. `update_calendar`  # mark release_ready on success
12. `release_lock`

Run artifact requirements:

- write `run-manifest.json`
- write `research-context.json`
- write `generated-content.json`
- write `optimized-content.html`
- write `quality-report.json`
- write `release-artifact.json`
- write `rendered-preview.html`

Lock rules:

- use `.content-engine.lock/`
- acquire with `os.mkdir`
- release in `finally`

Logging:

- stage entry and exit
- timing per stage
- run ID on every stage log line

The pipeline must not promote artifacts into `site/published/`.

---

## Step 13: Static site templates and build scripts

### `site/templates/base.html`

Create a minimal shared shell with:

- `<title>`
- `<meta name="description">`
- canonical link
- JSON-LD injection in `<head>`
- clear typography and readable layout

### `site/templates/insight.html`

Create the page template for a single insight page. It should render:

- H1
- content-type label
- published date
- body HTML

### `site/assets/styles.css`

Keep it simple, clean, and readable.

### `scripts/build-site.py`

Implement:

1. Load all `site/published/*.json` artifacts from `site/published/index.json`.
2. Render each page into `site/dist/insights/{slug}/index.html`.
3. Render a minimal `site/dist/index.html` or landing page.
4. Copy `site/assets/styles.css`.
5. Copy or generate `robots.txt` and the sitemap asset.

The build script should fail loudly if published artifacts are invalid.

### `scripts/promote-artifact.py`

Implement a CLI:

```text
python scripts/promote-artifact.py --artifact logs/runs/2026-03-20/release-artifact.json
```

Behavior:

1. Load and validate the release artifact.
2. Copy it into `site/published/{slug}.json`.
3. Update `site/published/index.json`.
4. Mark the matching calendar topic as `published` in `content/calendar.yaml`.
5. Make the command idempotent when the same artifact is promoted twice.

This script must not deploy to Vercel.

---

## Step 14: launchd config

### `com.folloze.content-engine.plist`

Create a launchd plist that runs the pipeline daily at 9:00 AM America/Chicago and writes to:

- `logs/launchagent.log`
- `logs/launchagent-error.log`

### `scripts/setup-launchd.sh`

Create a safe install script that:

- creates the logs directory
- copies the plist into `~/Library/LaunchAgents/`
- loads it with `launchctl`

---

## Step 15: Competitive seed script

### `scripts/seed-calendar.py`

Purpose:

1. Fetch sitemaps from Mutiny, Userled, and PathFactory.
2. Infer likely topic titles from slugs.
3. Ask Gemini to classify each topic as comparison, guide, faq, or glossary.
4. Filter out topics already in `content/calendar.yaml`.
5. Append the best candidates.

If a competitor fetch fails, log and continue.

---

## Step 16: robots and sitemap assets

### `scripts/robots-txt-generator.py`

Generate:

- `site/assets/robots.txt`
- `site/assets/insights-sitemap.xml`

Allow major AI crawlers explicitly.

---

## Step 17: Brand context file

### `brand/context.md`

Compile Folloze brand voice and product context from the source files listed in the existing spec. Distill the material. Do not copy source files verbatim.

Must include:

- one-line product description
- three pillars with proof points
- ICP
- approved messaging anchors
- banned terms
- key proof points
- competitive positioning
- brand voice rules

---

## Step 18: Tests

Implement all test files listed in `PRD.md`.

Key test requirements:

- no real API calls
- use `responses` or mocks for network calls
- cover every custom exception path
- test both happy path and failure path

Minimum named tests:

### `test_generator.py`

```python
def test_generate_all_four_content_types(): ...
def test_generate_retries_on_short_content(): ...
def test_generate_raises_on_empty_response(): ...
def test_generate_raises_on_refusal(): ...
def test_generate_raises_when_gemini_unavailable(): ...
```

### `test_artifacts.py`

```python
def test_write_release_artifact_outputs_expected_shape(): ...
def test_render_preview_html_contains_metadata(): ...
def test_load_release_artifact_rejects_invalid_shape(): ...
```

### `test_verify.py`

```python
def test_check_preview_file_passes_with_valid_html(): ...
def test_check_preview_file_raises_on_missing_json_ld(): ...
def test_check_live_times_out_cleanly(): ...
```

### `test_pipeline.py`

```python
def test_full_happy_path_release_ready(tmp_path, mocker): ...
def test_lock_file_prevents_concurrent_run(): ...
def test_calendar_exhausted_exits_clean(): ...
def test_provider_unavailable_sends_notification(): ...
```

Also test `scripts/promote-artifact.py` idempotency and `scripts/build-site.py` output structure.

---

## Step 19: Documentation

Write:

### `docs/OPERATIONS.md`

- daily review process
- adding topics to the calendar
- running on demand
- checking logs
- escalation

### `docs/DEPLOYMENT.md`

- how to build the static site
- how to validate locally
- how Trey or a web dev tests on Vercel
- how to confirm preview and production URLs

### `docs/HANDOFF.md`

- system overview
- env var registry
- runbook for common failures
- where artifacts and logs live
- release checklist

### `docs/MIGRATION_TO_WEBFLOW_V2.md`

- field mapping from release artifact to future Webflow collection
- migration steps
- assumptions the web dev team must preserve

### `docs/CONTENT_TYPES.md`

- examples and use cases for each content type

### `README.md`

- title + one-line description
- what it does
- setup
- usage
- structure overview
- development log

---

## Quality gates before finishing

Before marking the build complete, verify:

1. `pip install -e ".[dev]"` succeeds
2. `ruff check .` returns zero errors
3. `pytest tests/ -v` passes
4. `detect-secrets scan` returns no secrets
5. all Python modules exist with the correct function signatures
6. `python pipeline.py --dry-run` runs without crashing with mocked env vars
7. `python scripts/build-site.py` builds a valid static bundle
8. `content/calendar.yaml` has at least 10 topics
9. `brand/context.md` contains Folloze proof points and banned terms
10. all JSON-LD templates exist
11. all prompt templates exist
12. handoff and migration docs exist

---

## What NOT to build

- no Webflow integration in V1
- no provider abstraction
- no automatic Vercel deployment
- no database
- no Docker
- no Slack notifications
- no citation monitor
- no gap analyzer beyond the seed script
- do not modify files outside this repo
- do not push to GitHub
