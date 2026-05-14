# Folloze Content Engine: GEO Extension Plan

**Prepared:** 2026-03-31  
**Author:** Trey Harnden + Claude  
**Status:** Ready to build  
**Strategy source:** Kristi Tutt, Content Strategy + Technical Specification, March 2026

---

## Overview

Three new modules extend the existing content engine to close the feedback loop between content production and LLM citation performance. The engine already handles content generation correctly. The gap is entirely on the monitoring and optimization side.

**Goals:**
- SEO: rank for targeted keywords in Google
- LLM/GEO: increase Folloze Brand Visibility Score, citation rate, and share of voice across AI assistants on buyer questions
- AIO: appear in Google AI Overview and adjacent AI answer surfaces
- Revenue: connect AI visibility improvements to branded search lift, AI referral traffic, Folloze engagement, and pipeline progression

**Three modules to build:**

| Module | What it does | Schedule |
|---|---|---|
| Quality Gate Extensions | Extends `quality.py` with 10 new GEO checks | Inline on every publish run |
| Citation Monitor | Queries LLMs with target prompts, tracks Brand Visibility Score, citation rate, share of voice, sentiment, and source attribution over time | Nightly, 10 PM |
| Gap Analyzer | Scores prompt gaps by visibility gap + competitor dominance, proposes topics to calendar | Weekly, Sunday 6 AM |

**Build order:** Phase 1 (Quality Gate) → Phase 2 (Citation Monitor) → Phase 3 (Gap Analyzer). Each phase depends on the previous. Phase 3 needs at least one week of Monitor data before its first real run.

## Measurement framework alignment (updated 2026-04-14)

This plan is aligned to Folloze marketing's benchmark-and-measurement framework from
"AI-Native SEO & Visibility Framework for B2B Tech Clients."

Do not treat the monitor as a single blended score. The operating KPI stack is:

### Tier 1: AI Citation & Mention Tracking
- Brand Visibility Score = % of relevant prompts where Folloze appears
- Citation Rate = % of responses where Folloze is cited with a link
- Share of Voice = Folloze mentions / total mentions of all brands
- Sentiment Score = positive / neutral / negative tone of AI mentions
- Source Attribution = which URLs/snippets are cited by AI systems

Benchmarks to use in executive reporting:
- Brand Visibility Score: 30%+ on core category queries; top brands may reach 50%+
- Share of Voice: >=15% across core queries; enterprise leaders may reach 25-30% in focused niches
- Sentiment Score: >70% positive

### Tier 2: Branded Search Lift
- Track branded query growth in Google Search Console
- Use branded search lift as the leading downstream validation signal for LLM visibility improvements

### Tier 3: AI Referral Traffic
- Track AI assistant traffic in GA4 with a dedicated AI Traffic channel group
- Expect partial undercount because some AI surfaces strip referrers

### Tier 4: Pipeline & Revenue Attribution
- Add self-reported attribution for AI assistants on forms
- Connect AI visibility -> Folloze engagement -> CRM progression -> pipeline / revenue

Reporting guardrails:
- Always separate mentions from citations
- Benchmark Folloze against 3-5 competitors on the same prompt set
- Use monthly trend reporting and quarterly business-impact reporting
- Never claim improvement from one provider, one run, or one metric alone

---

## Architecture

Nothing in `pipeline.py`'s main loop changes. All integration is additive.

```
launchd 9:05 AM daily (existing)
  scripts/run_daily_publish.py
    └── pipeline.py → quality.gate()  ← EXTENDED with 10 GEO checks

launchd 10:00 PM nightly (NEW)
  scripts/run_citation_monitor.py
    └── citation_monitor/monitor.py
          └── writes to data/citation_monitor.db

launchd Sunday 6:00 AM weekly (NEW)
  scripts/run_gap_analyzer.py
    └── gap_analyzer/analyzer.py
          ├── reads data/citation_monitor.db
          └── proposes topics → content/calendar.yaml
```

**New top-level directories:**

```
data/               # SQLite databases (gitignored)
citation_monitor/   # Citation Monitor Python package
gap_analyzer/       # Gap Analyzer Python package
```

---

## Phase 1: Quality Gate Extensions

### What changes

`quality.py` gets 10 new GEO checks alongside the existing 10. The existing `gate()` signature does not change. `QualityResult` does not change. All existing 10 checks stay untouched.

The new checks split into two severity tiers:

- **Hard failures** — contribute 0 points AND add to `failures` list, trigger the existing repair loop in `pipeline.py`
- **Soft warnings** — contribute 0 points if failed but do NOT add to `failures` list; they appear in `reasons` only and lower the GEO sub-score

### New GEO checks

| Check | Points | Severity | What it detects |
|---|---|---|---|
| TL;DR present + contains a stat | 15 | Hard | `<section>` or `<div>` with class containing "tldr" or "summary", OR first `<p>` within first 150 words contains a digit/percentage |
| Kill-list words absent | 15 | Hard | Any of 20 banned marketing words (see `brand_rules.py` additions) |
| Entity consistency | 10 | Hard | Forbidden substitutes ("microsite builder", "buyer experience platform", "agentic", "page builder") absent; "Folloze" present at least once |
| Author attribution | 10 | Soft | Named author present in `<meta name="author">` or byline element or JSON-LD `author.name` |
| Freshness signal | 10 | Soft | Date string matching `Updated [Month] [Year]` or ISO date in `<time>` element or `dateModified` in JSON-LD |
| External citation format | 15 | Soft | At least one instance of pattern `According to .{1,60} \(\d{4}\)` or `per .{1,40} \(\d{4}\)` or `Source: ` |
| Heading density | 10 | Soft | At least one H2 or H3 per 200 words; computed as `(h2_count + h3_count) / (word_count / 200) >= 1.0` |
| Emotion-first intro | 10 | Soft | First `<p>` tag contains at least one word from `PAIN_SIGNALS` list before any word from `PRODUCT_SIGNALS` list |
| Answer-first paragraphs | 5 | Soft | At least 60% of H2s have a `<p>` immediately following that begins with a declarative sentence (subject + verb, no question mark, under 35 words) |
| Em-dash absent (promoted) | 0 | Hard | `—` or `&mdash;` or `&#8212;` — already checked in `_brand_failures` but must also appear in GEO reasons |

### Scoring

```python
# quality.py gate() function, extended section

aeo_score = ...  # existing 10 checks, max 100
geo_score = ...  # 10 new checks, max 100

composite = aeo_score + geo_score          # max 200
normalized = composite // 2               # back to /100 for QualityResult.score

passed = (
    aeo_score >= config.pipeline.quality_threshold         # existing: 70
    and geo_score >= config.pipeline.geo_quality_threshold # new: starts at 0
    and not brand_failures
    and not hard_geo_failures
)
```

`geo_quality_threshold` starts at **0** for a 2-week calibration period. After observing real GEO scores on content that already passes the AEO gate, raise to 40-50 via a single YAML change.

### File changes

#### `brand_rules.py` — add constants

```python
# Add after existing BANNED_TERMS and PROOF_POINTS

GEO_KILL_LIST: list[str] = [
    "streamline",
    "empower",
    "unlock",
    "leverage",
    "seamless",
    "cutting-edge",
    "game-changer",
    "best-in-class",
    "synergy",
    "holistic",
    "robust",
    "turnkey",
    "paradigm shift",
    "thought leader",
    "disrupt",
    "innovative",
    "revolutionize",
    "transformative",
    "next-generation",
    "future-proof",
]

ENTITY_REQUIRED: list[str] = [
    "folloze",
    "ai orchestration platform",
]

ENTITY_FORBIDDEN: list[str] = [
    "microsite builder",
    "buyer experience platform",
    "agentic",
    "page builder",
]

PAIN_SIGNALS: list[str] = [
    "problem",
    "challenge",
    "struggle",
    "slow",
    "weeks",
    "manual",
    "impossible",
    "frustrated",
    "behind",
    "losing",
    "miss",
    "fail",
    "anxiety",
    "pressure",
    "board",
    "pipeline",
    "nobody",
    "can't",
    "cannot",
    "without",
    "takes",
    "too long",
    "headcount",
    "budget",
    "small team",
    "two-person",
    "generic",
    "ignored",
    "skip",
    "credibility",
]

PRODUCT_SIGNALS: list[str] = [
    "folloze",
    "platform",
    "solution",
    "tool",
    "product",
    "feature",
    "campaign agent",
    "ai orchestration",
    "personalization engine",
    "request a demo",
    "get started",
]
```

#### `config.py` — add `geo_quality_threshold` to `PipelineConfig`

```python
# In PipelineConfig dataclass, add field:
geo_quality_threshold: int = 0
```

Also add two new config dataclasses:

```python
@dataclasses.dataclass(slots=True)
class CitationMonitorConfig:
    providers: list[str] = dataclasses.field(default_factory=lambda: ["perplexity", "openai"])
    variants_per_keyword: int = 10
    max_concurrency: int = 3
    alert_threshold: float = 0.1
    competitor_alert_threshold: int = 5
    branded_target: float = 0.25
    unbranded_target: float = 0.75

@dataclasses.dataclass(slots=True)
class GapAnalyzerConfig:
    top_n_proposals: int = 5
    lookback_days: int = 7
    min_gap_score_to_propose: float = 0.3
```

Add both as optional fields on `Config`:

```python
@dataclasses.dataclass(slots=True)
class Config:
    site: SiteConfig
    delivery: DeliveryConfig
    pipeline: PipelineConfig
    notifications: ...
    content: ContentConfig
    llm: LLMConfig
    citation_monitor: CitationMonitorConfig = dataclasses.field(default_factory=CitationMonitorConfig)
    gap_analyzer: GapAnalyzerConfig = dataclasses.field(default_factory=GapAnalyzerConfig)
```

In `Config.load()`, use `.get()` for both new sections so existing `config.yaml` files without them still load cleanly:

```python
citation_monitor_raw = data.get("citation_monitor", {})
gap_analyzer_raw = data.get("gap_analyzer", {})
```

#### `config.yaml` — add new sections

```yaml
# Under pipeline:
pipeline:
  quality_threshold: 70
  geo_quality_threshold: 0        # ← NEW; raise to 40-50 after calibration
  max_retries_llm: 2
  max_quality_repairs: 3
  verify_timeout_seconds: 300
  timezone: "America/Chicago"
  run_hour: 9
  log_level: "INFO"
  max_log_age_days: 30

# New top-level sections:
citation_monitor:
  providers:
    - perplexity
    - openai
  variants_per_keyword: 10
  max_concurrency: 3
  alert_threshold: 0.1
  competitor_alert_threshold: 5
  branded_target: 0.25
  unbranded_target: 0.75

gap_analyzer:
  top_n_proposals: 5
  lookback_days: 7
  min_gap_score_to_propose: 0.3
```

#### `quality.py` — new check functions

Add these 9 functions (em-dash is already in `_brand_failures`; it gets promoted to also appear in GEO reasons but not duplicated as a separate scorer):

```python
import re
from brand_rules import (
    GEO_KILL_LIST,
    ENTITY_REQUIRED,
    ENTITY_FORBIDDEN,
    PAIN_SIGNALS,
    PRODUCT_SIGNALS,
)

# ---------------------------------------------------------------------------
# GEO HARD CHECKS
# ---------------------------------------------------------------------------

def _check_tldr_present(html: str) -> tuple[int, str, str | None]:
    """TL;DR or executive summary block is present and contains a statistic."""
    soup = BeautifulSoup(html, "html.parser")

    # Look for explicit TL;DR container
    tldr_classes = ["tldr", "tl-dr", "summary", "executive-summary", "key-takeaway"]
    for cls in tldr_classes:
        if soup.find(class_=re.compile(cls, re.IGNORECASE)):
            container = soup.find(class_=re.compile(cls, re.IGNORECASE))
            has_stat = bool(re.search(r"\d+%|\d+x|\$\d+|\d{1,3},\d{3}", container.get_text()))
            if has_stat:
                return 15, "TL;DR with statistic: present", None
            return 0, "TL;DR present but missing statistic", "Add a specific number or metric to the TL;DR section"

    # Fallback: first <p> in first 200 words acts as TL;DR
    paragraphs = soup.find_all("p")
    if paragraphs:
        first_p = paragraphs[0].get_text()
        word_count = len(first_p.split())
        has_stat = bool(re.search(r"\d+%|\d+x|\$\d+|\d{1,3},\d{3}", first_p))
        if word_count <= 60 and has_stat:
            return 10, "First paragraph functions as TL;DR with statistic", None
        if not has_stat:
            return 0, "No TL;DR section found", "Add a TL;DR block with a direct answer and one specific statistic"

    return 0, "No TL;DR section found", "Add a TL;DR block with a direct answer and one specific statistic"


def _check_kill_list(html: str) -> tuple[int, str, str | None]:
    """None of the GEO kill-list marketing words appear in the content."""
    text = BeautifulSoup(html, "html.parser").get_text().lower()
    found = [term for term in GEO_KILL_LIST if term in text]
    if found:
        display = ", ".join(f'"{t}"' for t in found[:5])
        more = f" (+{len(found)-5} more)" if len(found) > 5 else ""
        return 0, f"Kill-list words found: {display}{more}", f"Remove these words: {', '.join(found)}"
    return 15, "No kill-list words found", None


def _check_entity_consistency(html: str) -> tuple[int, str, str | None]:
    """Forbidden brand substitutes are absent; 'Folloze' appears at least once."""
    text = BeautifulSoup(html, "html.parser").get_text().lower()
    forbidden_found = [term for term in ENTITY_FORBIDDEN if term in text]
    folloze_present = "folloze" in text

    if forbidden_found:
        return 0, f"Forbidden entity terms: {', '.join(forbidden_found)}", (
            f"Replace these with approved terminology: {', '.join(forbidden_found)}"
        )
    if not folloze_present:
        return 0, "Brand name 'Folloze' not found", "Ensure 'Folloze' appears at least once"
    return 10, "Entity consistency: pass", None


# ---------------------------------------------------------------------------
# GEO SOFT CHECKS
# ---------------------------------------------------------------------------

def _check_author_attribution(html: str, author_name: str = "Trey Harnden") -> tuple[int, str, str | None]:
    """Named author present in meta tag, byline element, or JSON-LD author field."""
    soup = BeautifulSoup(html, "html.parser")

    # Check <meta name="author">
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content"):
        return 10, f"Author meta tag: {meta_author['content']}", None

    # Check JSON-LD author
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict) and data.get("author", {}).get("name"):
                return 10, f"JSON-LD author: {data['author']['name']}", None
        except (json.JSONDecodeError, AttributeError):
            continue

    # Check byline patterns in text
    text = soup.get_text()
    byline_patterns = [
        re.compile(r"by\s+[A-Z][a-z]+\s+[A-Z][a-z]+", re.IGNORECASE),
        re.compile(r"author:\s*[A-Z]", re.IGNORECASE),
        re.compile(r"written by", re.IGNORECASE),
    ]
    for pattern in byline_patterns:
        if pattern.search(text):
            return 10, "Byline pattern found in content", None

    return 0, "No author attribution found", "Add author meta tag or byline with named Folloze team member"


def _check_freshness_signal(html: str) -> tuple[int, str, str | None]:
    """Visible date or 'Updated Month Year' signal is present."""
    soup = BeautifulSoup(html, "html.parser")

    # Check <time> element
    if soup.find("time"):
        return 10, "Date <time> element present", None

    # Check dateModified in JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict) and (data.get("dateModified") or data.get("datePublished")):
                return 10, "Date in JSON-LD schema", None
        except (json.JSONDecodeError, AttributeError):
            continue

    # Check text patterns
    text = soup.get_text()
    MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
    patterns = [
        re.compile(rf"Updated\s+({MONTHS})\s+20\d{{2}}", re.IGNORECASE),
        re.compile(rf"Last updated\s+({MONTHS})\s+20\d{{2}}", re.IGNORECASE),
        re.compile(r"20\d{2} Guide", re.IGNORECASE),
        re.compile(r"\(20\d{2}\)"),
    ]
    for pattern in patterns:
        if pattern.search(text):
            return 10, "Freshness signal found in text", None

    return 0, "No freshness signal found", "Add 'Updated [Month Year]' or a <time> element with publication date"


def _check_citation_format(html: str) -> tuple[int, str, str | None]:
    """At least one external fact is cited in the format 'According to [Source] (Year)'."""
    text = BeautifulSoup(html, "html.parser").get_text()
    patterns = [
        re.compile(r"According to .{1,80} \(\d{4}\)", re.IGNORECASE),
        re.compile(r"Per .{1,60} \(\d{4}\)", re.IGNORECASE),
        re.compile(r"Source:\s+.{1,60}", re.IGNORECASE),
        re.compile(r"—\s*.{1,60},\s+20\d{2}", re.IGNORECASE),  # em-dash citation style
        re.compile(r"\[\d+\]"),  # inline footnote markers
    ]
    for pattern in patterns:
        if pattern.search(text):
            return 15, "External citation format found", None
    return 0, "No external citation format found", (
        "Add at least one cited statistic in format: 'According to [Source] (Year), X%'"
    )


def _check_heading_density(html: str) -> tuple[int, str, str | None]:
    """H2 or H3 appears at least once per 200 words."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()
    word_count = len(text.split())
    heading_count = len(soup.find_all(["h2", "h3"]))

    if word_count == 0:
        return 0, "No content found for heading density check", None

    expected_headings = word_count / 200
    ratio = heading_count / expected_headings if expected_headings > 0 else 0

    if ratio >= 1.0:
        return 10, f"Heading density: {heading_count} headings / {word_count} words (good)", None
    if ratio >= 0.5:
        return 5, f"Heading density marginal: {heading_count} headings / {word_count} words", (
            f"Add more H2/H3 headings. Target: one per 200 words. Have {heading_count}, need ~{int(expected_headings)}"
        )
    return 0, f"Heading density too low: {heading_count} headings / {word_count} words", (
        f"Add H2/H3 headings. Target one per 200 words. Have {heading_count}, need ~{int(expected_headings)}"
    )


def _check_emotion_first_intro(html: str) -> tuple[int, str, str | None]:
    """First paragraph leads with pain/anxiety signal before product mentions."""
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.find_all("p")
    if not paragraphs:
        return 0, "No paragraphs found for emotion-first check", None

    first_p = paragraphs[0].get_text().lower()
    words = first_p.split()

    pain_positions = [i for i, w in enumerate(words) if any(signal in w for signal in PAIN_SIGNALS)]
    product_positions = [i for i, w in enumerate(words) if any(signal in w for signal in PRODUCT_SIGNALS)]

    if not pain_positions:
        return 0, "Intro does not lead with pain/anxiety signal", (
            "Open with a pain point, fear, or frustration before mentioning Folloze or product features. "
            "Reference one of the five emotional territories: AI Overwhelm, Campaign Chaos, Pipeline Anxiety, "
            "Credibility Risk, or Speed = Outcomes."
        )
    if product_positions and min(product_positions) < min(pain_positions):
        return 0, "Product mention appears before pain signal in intro", (
            "Move the emotional hook (pain, anxiety, frustration) before any product or feature mention"
        )
    return 10, "Emotion-first intro: pain signal precedes product mention", None


def _check_answer_first_paragraphs(html: str) -> tuple[int, str, str | None]:
    """At least 60% of H2s have an immediate answer paragraph."""
    soup = BeautifulSoup(html, "html.parser")
    h2s = soup.find_all("h2")
    if not h2s:
        return 5, "No H2s found; answer-first check skipped", None

    answer_first_count = 0
    QUESTION_MARK_RE = re.compile(r"\?")
    MAX_ANSWER_WORDS = 40

    for h2 in h2s:
        next_el = h2.find_next_sibling()
        if next_el and next_el.name == "p":
            p_text = next_el.get_text().strip()
            word_count = len(p_text.split())
            is_short = word_count <= MAX_ANSWER_WORDS
            is_declarative = not QUESTION_MARK_RE.search(p_text[:80])
            has_verb = bool(re.search(r"\b(is|are|can|does|helps|provides|allows|gives|means|refers)\b", p_text[:80], re.IGNORECASE))
            if is_short and is_declarative and has_verb:
                answer_first_count += 1

    ratio = answer_first_count / len(h2s)
    if ratio >= 0.6:
        return 5, f"Answer-first paragraphs: {answer_first_count}/{len(h2s)} H2s ({int(ratio*100)}%)", None
    return 0, f"Answer-first paragraphs: only {answer_first_count}/{len(h2s)} H2s lead with a direct answer", (
        "After each H2, write a short declarative sentence (under 40 words) that directly answers the heading question"
    )
```

#### `quality.py` — extend `gate()` function body

After the existing 10-check AEO block, add:

```python
# --- GEO CHECKS ---
geo_checks_hard: list[tuple[int, str, str | None]] = [
    _check_tldr_present(body_html),
    _check_kill_list(body_html),
    _check_entity_consistency(body_html),
]
geo_checks_soft: list[tuple[int, str, str | None]] = [
    _check_author_attribution(body_html, author_name),
    _check_freshness_signal(body_html),
    _check_citation_format(body_html),
    _check_heading_density(body_html),
    _check_emotion_first_intro(body_html),
    _check_answer_first_paragraphs(body_html),
]

geo_score = 0
hard_geo_failures: list[str] = []

for points, reason, fix in geo_checks_hard:
    geo_score += points
    reasons.append(f"[GEO] {reason}")
    if fix:
        hard_geo_failures.append(fix)

for points, reason, fix in geo_checks_soft:
    geo_score += points
    reasons.append(f"[GEO] {reason}")
    if fix:
        reasons.append(f"  → Fix: {fix}")

composite = aeo_score + geo_score
normalized = composite // 2

passed = (
    aeo_score >= config.pipeline.quality_threshold
    and geo_score >= config.pipeline.geo_quality_threshold
    and not brand_failures
    and not hard_geo_failures
)

return QualityResult(
    passed=passed,
    score=normalized,
    reasons=reasons,
    failures=failures + hard_geo_failures + brand_failures,
)
```

Update `gate()` signature to accept optional `author_name`:

```python
def gate(
    content: OptimizedContent,
    config: Config,
    brand_context: str,
    author_name: str = "Trey Harnden",
) -> QualityResult:
```

No changes needed at the call site in `pipeline.py` — the default value handles it.

#### `generator.py` — add GEO repair instructions

Add alongside `_quality_repair_instructions()`:

```python
def _geo_repair_instructions(failures: list[str]) -> str:
    instructions: list[str] = []
    if any("TL;DR" in f or "tldr" in f.lower() for f in failures):
        instructions.append(
            "Add a TL;DR section immediately after the H1. It must be 2-3 sentences, "
            "directly answer the primary question, and include at least one specific statistic "
            "(percentage, dollar amount, or multiplier)."
        )
    if any("kill-list" in f.lower() or "kill list" in f.lower() for f in failures):
        instructions.append(
            "Remove all marketing filler words. Specifically replace: streamline → simplify or speed up, "
            "empower → enable or give, leverage → use, robust → reliable, seamless → smooth, "
            "cutting-edge → current, game-changer → significant improvement. "
            "Write like an engineer explaining something to a teammate."
        )
    if any("forbidden entity" in f.lower() or "microsite" in f.lower() or "agentic" in f.lower() for f in failures):
        instructions.append(
            "Replace forbidden terminology: never use 'microsite builder', 'buyer experience platform', "
            "'agentic', or 'page builder'. Use 'AI orchestration platform' or 'ABX platform' consistently."
        )
    if any("pain" in f.lower() or "emotion" in f.lower() or "intro" in f.lower() for f in failures):
        instructions.append(
            "Rewrite the opening paragraph. Lead with pain or anxiety before mentioning Folloze or any feature. "
            "Reference one of: AI Overwhelm (everyone talks AI, nothing works), Campaign Chaos (3 weeks for a 3-day job), "
            "Pipeline Anxiety (board wants numbers, marketing can't prove attribution), "
            "Credibility Risk (generic content destroys trust), Speed = Outcomes (faster wins deals)."
        )
    if any("citation" in f.lower() or "according to" in f.lower() for f in failures):
        instructions.append(
            "Add at least one externally cited statistic in this format: "
            "'According to [Source Name] ([Year]), X% of [audience] [fact].' "
            "Use real, specific sources: Gartner, Forrester, HubSpot, Demand Gen Report, or Conductor research."
        )
    if any("answer-first" in f.lower() or "h2" in f.lower() for f in failures):
        instructions.append(
            "After every H2 heading, write a single declarative sentence (under 40 words) that directly answers "
            "what the heading asks. This sentence must come before any supporting context or examples."
        )
    return "\n".join(f"- {i}" for i in instructions)
```

In `regenerate_for_quality()`, append GEO repair instructions to the existing repair prompt:

```python
geo_instructions = _geo_repair_instructions(failures)
if geo_instructions:
    repair_prompt += f"\n\nGEO/LLM VISIBILITY FIXES REQUIRED:\n{geo_instructions}"
```

#### `tests/test_quality_geo.py` — new test file

Create at `/Users/treyharnden/Projects/folloze-content-engine/tests/test_quality_geo.py`.

Follow the exact pattern of `test_quality.py`: use `conftest.py` fixtures for `Config`, pass `OptimizedContent` objects with controlled `body_html`. Test cases needed:

```
test_tldr_present_with_stat_passes
test_tldr_present_without_stat_fails
test_tldr_missing_fails
test_kill_list_word_fails (one word from GEO_KILL_LIST)
test_kill_list_clean_passes
test_entity_forbidden_term_fails ("microsite builder" in content)
test_entity_folloze_absent_fails
test_entity_consistency_passes
test_author_meta_tag_passes
test_author_json_ld_passes
test_author_missing_soft_warning (does not add to failures)
test_freshness_time_element_passes
test_freshness_json_ld_passes
test_freshness_text_pattern_passes
test_citation_format_according_to_passes
test_citation_format_missing_soft_warning
test_heading_density_good_passes
test_heading_density_low_soft_warning
test_emotion_first_pain_before_product_passes
test_emotion_first_product_before_pain_fails
test_answer_first_60pct_threshold_passes
test_answer_first_below_threshold_soft_warning
test_geo_hard_failures_block_gate
test_geo_soft_failures_do_not_block_gate
test_geo_quality_threshold_zero_never_blocks
test_geo_repair_instructions_tldr
test_geo_repair_instructions_kill_list
test_geo_repair_instructions_emotion
```

---

## Phase 2: Citation Monitor

### Directory structure

```
/Users/treyharnden/Projects/folloze-content-engine/
  citation_monitor/
    __init__.py
    monitor.py          # CitationMonitor class, main orchestration
    providers.py        # LLM API call adapters (Perplexity, OpenAI)
    variants.py         # KEYWORDS registry + generate_variants()
    storage.py          # SQLite schema + CRUD layer
    report.py           # Daily HTML summary builder
  data/
    citation_monitor.db   # gitignored
  scripts/
    run_citation_monitor.py
  launchd/
    com.folloze.content-engine.citation-monitor.plist
```

Add to `.gitignore`:
```
data/*.db
data/
```

### SQLite schema — `storage.py`

```python
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS monitor_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date    TEXT NOT NULL,
    run_ts      TEXT NOT NULL,
    keyword_count   INTEGER NOT NULL DEFAULT 0,
    citation_count  INTEGER NOT NULL DEFAULT 0,
    alert_fired     INTEGER NOT NULL DEFAULT 0,
    summary_json    TEXT
);

CREATE TABLE IF NOT EXISTS keyword_variants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword         TEXT NOT NULL,
    tier            TEXT NOT NULL,  -- tier1, tier2, tier3
    variant_text    TEXT NOT NULL,
    created_date    TEXT NOT NULL,
    UNIQUE(keyword, variant_text)
);

CREATE TABLE IF NOT EXISTS citation_results (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              INTEGER NOT NULL REFERENCES monitor_runs(id),
    keyword             TEXT NOT NULL,
    tier                TEXT NOT NULL,
    variant_text        TEXT NOT NULL,
    provider            TEXT NOT NULL,
    response_text       TEXT,
    folloze_mentioned   INTEGER NOT NULL DEFAULT 0,  -- 0 or 1
    branded             INTEGER NOT NULL DEFAULT 0,  -- 1 = "Folloze" name, 0 = category mention
    competitors_mentioned TEXT NOT NULL DEFAULT '[]',  -- JSON array of strings
    citation_probability REAL,  -- computed per keyword across variants, stored on each row
    checked_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS competitor_sightings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES monitor_runs(id),
    keyword         TEXT NOT NULL,
    competitor      TEXT NOT NULL,
    sighting_count  INTEGER NOT NULL DEFAULT 0,
    checked_at      TEXT NOT NULL,
    UNIQUE(run_id, keyword, competitor)
);

CREATE INDEX IF NOT EXISTS idx_citation_results_keyword ON citation_results(keyword);
CREATE INDEX IF NOT EXISTS idx_citation_results_run ON citation_results(run_id);
CREATE INDEX IF NOT EXISTS idx_competitor_sightings_run ON competitor_sightings(run_id);
"""
```

Key functions in `storage.py`:

```python
def init_db(db_path: Path) -> sqlite3.Connection:
    """Create DB file and run SCHEMA_SQL. Returns open connection."""

def create_run(conn: sqlite3.Connection, run_date: str) -> int:
    """INSERT INTO monitor_runs and return the new id."""

def update_run_summary(conn: sqlite3.Connection, run_id: int, summary: "MonitorRunSummary") -> None:
    """UPDATE monitor_runs SET summary_json, citation_count, alert_fired WHERE id = run_id."""

def get_cached_variants(conn: sqlite3.Connection, keyword: str, max_age_days: int = 7) -> list[str]:
    """Return variant_text list for keyword if created within max_age_days, else []."""

def save_variants(conn: sqlite3.Connection, keyword: str, tier: str, variants: list[str]) -> None:
    """INSERT OR IGNORE into keyword_variants."""

def save_citation_result(conn: sqlite3.Connection, run_id: int, result: "CitationCheckResult") -> None:
    """INSERT INTO citation_results."""

def save_competitor_sightings(conn: sqlite3.Connection, run_id: int, keyword: str, sightings: dict[str, int]) -> None:
    """INSERT OR REPLACE INTO competitor_sightings."""

def get_citation_rates(conn: sqlite3.Connection, lookback_days: int = 7) -> dict[str, float]:
    """
    SELECT keyword, AVG(folloze_mentioned) as rate
    FROM citation_results
    WHERE checked_at > datetime('now', '-N days')
    GROUP BY keyword
    Returns {keyword: citation_probability} dict.
    """

def get_competitor_sightings_recent(conn: sqlite3.Connection, lookback_days: int = 7) -> list[dict]:
    """
    SELECT keyword, competitor, SUM(sighting_count) as total
    FROM competitor_sightings cs
    JOIN monitor_runs mr ON cs.run_id = mr.id
    WHERE mr.run_date > date('now', '-N days')
    GROUP BY keyword, competitor
    ORDER BY total DESC
    Returns list of {keyword, competitor, total} dicts.
    """

def get_trend_data(conn: sqlite3.Connection, days: int = 7) -> list[dict]:
    """
    SELECT run_date, citation_count, keyword_count, alert_fired, summary_json
    FROM monitor_runs
    ORDER BY run_date DESC LIMIT N
    Returns per-day summaries for the weekly trend table.
    """
```

### Keyword registry — `variants.py`

```python
# Master keyword list. Mirrors gap_analyzer/analyzer.py KEYWORD_REGISTRY.
# Any keyword added here should also be added there (with volume).

KEYWORDS: list[dict[str, str]] = [
    # Tier 1: High-intent, high-volume
    {"keyword": "ai marketing platform", "tier": "tier1"},
    {"keyword": "personalization technology", "tier": "tier1"},
    {"keyword": "ai personalization", "tier": "tier1"},
    {"keyword": "personalized landing pages", "tier": "tier1"},
    {"keyword": "website personalization", "tier": "tier1"},
    {"keyword": "microsites vs landing pages", "tier": "tier1"},
    {"keyword": "abx marketing", "tier": "tier1"},

    # Tier 2: Competitor + comparison
    {"keyword": "mutiny alternatives", "tier": "tier2"},
    {"keyword": "folloze vs userled", "tier": "tier2"},
    {"keyword": "pathfactory competitors", "tier": "tier2"},
    {"keyword": "best abm personalization tools", "tier": "tier2"},
    {"keyword": "prismic vs folloze", "tier": "tier2"},

    # Tier 3: Pain-point / unbranded discovery
    {"keyword": "how to personalize content for different accounts without hiring more people", "tier": "tier3"},
    {"keyword": "why do b2b campaigns take so long to launch", "tier": "tier3"},
    {"keyword": "how to make abm work with a small marketing team", "tier": "tier3"},
    {"keyword": "what tools help marketers create personalized buyer experiences", "tier": "tier3"},
    {"keyword": "how to use ai in b2b marketing without replacing my team", "tier": "tier3"},
    {"keyword": "scaling campaign creation without more budget or headcount", "tier": "tier3"},
]

VARIANT_PROMPT_TEMPLATE = """You are generating semantic search query variants for LLM citation monitoring.

Given the seed keyword: "{keyword}"

Generate {n} semantically varied phrasings that a B2B marketer might type into an AI assistant.
Include:
- Conversational questions ("What is the best way to...")
- Comparison queries ("X vs Y for ABM")
- How-to questions ("How do I...")
- Pain-point framings ("Why does X take so long...")
- Tool discovery queries ("What tools help with...")

Return ONLY a JSON array of strings. No explanations.
Example output: ["query one", "query two", "query three"]
"""

def generate_variants(
    keyword: str,
    tier: str,
    config: "Config",
    conn: sqlite3.Connection,
    n: int = 10,
) -> list[str]:
    """
    Returns n semantic variants for keyword.
    Checks cache first (keyword_variants table, max 7 days old).
    Falls back to deterministic template expansion if LLM fails.
    """
    cached = get_cached_variants(conn, keyword, max_age_days=7)
    if cached:
        return cached

    try:
        from llm_gateway import LLMGateway
        gw = LLMGateway(profile="workhorse")
        prompt = VARIANT_PROMPT_TEMPLATE.format(keyword=keyword, n=n)
        response = gw.chat([{"role": "user", "content": prompt}])
        variants = json.loads(response.strip())
        if isinstance(variants, list) and len(variants) >= 3:
            variants = [str(v) for v in variants[:n]]
            save_variants(conn, keyword, tier, variants)
            return variants
    except Exception:
        pass  # Fall through to deterministic fallback

    # Deterministic fallback — always produces exactly n variants
    templates = [
        f"What is {keyword}?",
        f"Best {keyword} tools for B2B",
        f"How to use {keyword} for B2B marketing",
        f"Why does {keyword} matter for enterprise marketing?",
        f"{keyword}: what marketers need to know",
        f"How do I get started with {keyword}?",
        f"What are the best {keyword} platforms in 2026?",
        f"Is {keyword} worth it for a small marketing team?",
        f"How does {keyword} compare to alternatives?",
        f"{keyword} guide for revenue teams",
    ]
    fallback_variants = templates[:n]
    save_variants(conn, keyword, tier, fallback_variants)
    return fallback_variants
```

### Provider adapters — `providers.py`

```python
import re
import time
import requests
from dataclasses import dataclass, field
from runtime_secrets import get_secret

# Detection patterns
FOLLOZE_RE = re.compile(r"\bfolloze\b", re.IGNORECASE)
BRANDED_RE = re.compile(r"\bfolloze\b", re.IGNORECASE)

COMPETITOR_PATTERNS: dict[str, re.Pattern] = {
    "mutiny": re.compile(r"\bmutiny\b", re.IGNORECASE),
    "userled": re.compile(r"\buserled\b", re.IGNORECASE),
    "pathfactory": re.compile(r"\bpathfactory\b", re.IGNORECASE),
    "prismic": re.compile(r"\bprismic\b", re.IGNORECASE),
    "demandbase": re.compile(r"\bdemandbase\b", re.IGNORECASE),
    "terminus": re.compile(r"\bterminus\b", re.IGNORECASE),
    "6sense": re.compile(r"\b6sense\b", re.IGNORECASE),
    "drift": re.compile(r"\bdrift\b", re.IGNORECASE),
)

@dataclass(slots=True)
class CitationCheckResult:
    provider: str
    keyword: str
    variant_text: str
    response_text: str
    folloze_mentioned: bool
    branded: bool  # True if "Folloze" brand name appears; False if category mention only
    competitors_mentioned: list[str] = field(default_factory=list)

def _detect_citation(response_text: str, keyword: str) -> tuple[bool, bool, list[str]]:
    """
    Returns (folloze_mentioned, branded, competitors_mentioned).
    folloze_mentioned: True if Folloze appears in any form
    branded: True if brand name "Folloze" appears explicitly
    competitors_mentioned: list of detected competitor names
    """
    folloze = bool(FOLLOZE_RE.search(response_text))
    branded = bool(BRANDED_RE.search(response_text))
    competitors = [name for name, pattern in COMPETITOR_PATTERNS.items() if pattern.search(response_text)]
    return folloze, branded, competitors

def _backoff_request(fn, max_retries: int = 3) -> requests.Response:
    """
    Calls fn() with exponential backoff on 429.
    Raises requests.HTTPError on non-retryable failures after max_retries.
    """
    for attempt in range(max_retries):
        resp = fn()
        if resp.status_code == 429:
            wait = 2 ** attempt
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()
    return resp

def query_perplexity(
    keyword: str,
    variant_text: str,
    timeout: int = 30,
) -> CitationCheckResult | None:
    """
    Query Perplexity sonar-pro with the variant text.
    Returns CitationCheckResult or None if API call fails.
    Follows the same pattern as research._perplexity_summary().
    """
    api_key = get_secret("PERPLEXITY_API_KEY", "perplexity-api")
    if not api_key:
        return None

    ENDPOINT = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar-pro",
        "messages": [{"role": "user", "content": variant_text}],
        "max_tokens": 512,
    }

    try:
        resp = _backoff_request(
            lambda: requests.post(ENDPOINT, headers=headers, json=payload, timeout=timeout)
        )
        response_text = resp.json()["choices"][0]["message"]["content"]
        time.sleep(1)  # Rate limit: 1 req/sec
        folloze, branded, competitors = _detect_citation(response_text, keyword)
        return CitationCheckResult(
            provider="perplexity",
            keyword=keyword,
            variant_text=variant_text,
            response_text=response_text,
            folloze_mentioned=folloze,
            branded=branded,
            competitors_mentioned=competitors,
        )
    except Exception:
        return None

def query_openai_web_search(
    keyword: str,
    variant_text: str,
    timeout: int = 45,
) -> CitationCheckResult | None:
    """
    Query OpenAI with web_search_preview tool enabled.
    Uses the /v1/responses endpoint.
    Returns CitationCheckResult or None if API call fails.

    NOTE: Before implementing, verify whether LLMGateway's "openai" profile
    already supports web search. If it does, replace this with a LLMGateway call.
    """
    api_key = get_secret("OPENAI_API_KEY", "openai-api")
    if not api_key:
        return _query_gateway_fallback(keyword, variant_text)

    ENDPOINT = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-4o",
        "tools": [{"type": "web_search_preview"}],
        "input": variant_text,
    }

    try:
        resp = _backoff_request(
            lambda: requests.post(ENDPOINT, headers=headers, json=payload, timeout=timeout)
        )
        # Parse response — exact field path depends on OpenAI Responses API spec
        # Adjust if the field is at a different path
        output = resp.json().get("output", [])
        response_text = ""
        for item in output:
            if item.get("type") == "message":
                for content_block in item.get("content", []):
                    if content_block.get("type") == "output_text":
                        response_text += content_block.get("text", "")
        if not response_text:
            return None
        time.sleep(1)
        folloze, branded, competitors = _detect_citation(response_text, keyword)
        return CitationCheckResult(
            provider="openai",
            keyword=keyword,
            variant_text=variant_text,
            response_text=response_text,
            folloze_mentioned=folloze,
            branded=branded,
            competitors_mentioned=competitors,
        )
    except Exception:
        return _query_gateway_fallback(keyword, variant_text)

def _query_gateway_fallback(keyword: str, variant_text: str) -> CitationCheckResult | None:
    """LLMGateway fallback when direct API keys are absent or provider is down."""
    try:
        from llm_gateway import LLMGateway
        gw = LLMGateway(profile="openai")
        response_text = gw.chat([{"role": "user", "content": variant_text}])
        folloze, branded, competitors = _detect_citation(response_text, keyword)
        return CitationCheckResult(
            provider="gateway_fallback",
            keyword=keyword,
            variant_text=variant_text,
            response_text=response_text,
            folloze_mentioned=folloze,
            branded=branded,
            competitors_mentioned=competitors,
        )
    except Exception:
        return None
```

### Orchestration — `monitor.py`

```python
from dataclasses import dataclass, field
from pathlib import Path
from config import Config
from citation_monitor.storage import (
    init_db, create_run, update_run_summary,
    save_citation_result, save_competitor_sightings, get_trend_data,
)
from citation_monitor.variants import KEYWORDS, generate_variants
from citation_monitor.providers import (
    query_perplexity, query_openai_web_search, CitationCheckResult,
)

@dataclass(slots=True)
class MonitorRunSummary:
    run_date: str
    keywords_checked: int
    overall_citation_rate: float    # fraction of keywords where Folloze appeared at least once
    branded_rate: float             # of all citations, fraction that are branded ("Folloze" name)
    unbranded_rate: float
    tier_breakdown: dict[str, float]  # {"tier1": 0.4, "tier2": 0.1, "tier3": 0.0}
    gaps: list[str]                   # keywords with citation_probability == 0.0
    competitor_leading: list[dict]    # [{"keyword": str, "competitor": str, "count": int}]
    alerts: list[str]

class CitationMonitor:

    def __init__(self, config: Config, db_path: Path) -> None:
        self.config = config
        self.db_path = db_path
        self.mc = config.citation_monitor  # CitationMonitorConfig

    def run(self) -> MonitorRunSummary:
        from datetime import date
        conn = init_db(self.db_path)
        run_date = date.today().isoformat()
        run_id = create_run(conn, run_date)

        all_results: list[CitationCheckResult] = []
        keyword_citation_counts: dict[str, int] = {}
        keyword_variant_counts: dict[str, int] = {}
        competitor_counts: dict[tuple[str, str], int] = {}  # (keyword, competitor) → count

        for kw_entry in KEYWORDS:
            keyword = kw_entry["keyword"]
            tier = kw_entry["tier"]
            variants = generate_variants(keyword, tier, self.config, conn, self.mc.variants_per_keyword)

            keyword_citation_counts[keyword] = 0
            keyword_variant_counts[keyword] = 0

            for variant in variants:
                for provider_name in self.mc.providers:
                    result = self._call_provider(provider_name, keyword, variant)
                    if result is None:
                        continue
                    save_citation_result(conn, run_id, result)
                    all_results.append(result)
                    keyword_variant_counts[keyword] += 1
                    if result.folloze_mentioned:
                        keyword_citation_counts[keyword] += 1
                    for comp in result.competitors_mentioned:
                        key = (keyword, comp)
                        competitor_counts[key] = competitor_counts.get(key, 0) + 1

        # Save competitor sightings
        seen: dict[str, dict[str, int]] = {}
        for (keyword, comp), count in competitor_counts.items():
            seen.setdefault(keyword, {})[comp] = count
        for keyword, sightings in seen.items():
            save_competitor_sightings(conn, run_id, keyword, sightings)

        # Build summary
        citation_probabilities = {
            kw: (keyword_citation_counts[kw] / keyword_variant_counts[kw])
            if keyword_variant_counts[kw] > 0 else 0.0
            for kw in keyword_citation_counts
        }
        overall_rate = (
            sum(1 for p in citation_probabilities.values() if p > 0) / len(citation_probabilities)
            if citation_probabilities else 0.0
        )
        branded_mentions = sum(1 for r in all_results if r.branded)
        total_mentions = sum(1 for r in all_results if r.folloze_mentioned)
        branded_rate = branded_mentions / total_mentions if total_mentions > 0 else 0.0
        unbranded_rate = 1.0 - branded_rate

        tier_keywords: dict[str, list[str]] = {}
        for kw_entry in KEYWORDS:
            tier_keywords.setdefault(kw_entry["tier"], []).append(kw_entry["keyword"])
        tier_breakdown = {
            tier: (
                sum(citation_probabilities.get(kw, 0) for kw in kws) / len(kws)
                if kws else 0.0
            )
            for tier, kws in tier_keywords.items()
        }

        gaps = [kw for kw, prob in citation_probabilities.items() if prob == 0.0]
        competitor_leading = [
            {"keyword": keyword, "competitor": comp, "count": count}
            for (keyword, comp), count in sorted(
                competitor_counts.items(), key=lambda x: x[1], reverse=True
            )
            if count >= self.mc.competitor_alert_threshold
        ]

        alerts = self._build_alerts(citation_probabilities, competitor_leading)

        summary = MonitorRunSummary(
            run_date=run_date,
            keywords_checked=len(KEYWORDS),
            overall_citation_rate=overall_rate,
            branded_rate=branded_rate,
            unbranded_rate=unbranded_rate,
            tier_breakdown=tier_breakdown,
            gaps=gaps,
            competitor_leading=competitor_leading,
            alerts=alerts,
        )
        update_run_summary(conn, run_id, summary)
        conn.close()
        return summary

    def _call_provider(
        self, provider_name: str, keyword: str, variant: str
    ) -> CitationCheckResult | None:
        if provider_name == "perplexity":
            return query_perplexity(keyword, variant)
        if provider_name == "openai":
            return query_openai_web_search(keyword, variant)
        return None

    def _build_alerts(
        self,
        citation_probabilities: dict[str, float],
        competitor_leading: list[dict],
    ) -> list[str]:
        alerts = []
        for kw, prob in citation_probabilities.items():
            if prob < self.mc.alert_threshold:
                alerts.append(f"LOW CITATION: '{kw}' — {prob:.0%} citation rate (threshold: {self.mc.alert_threshold:.0%})")
        for entry in competitor_leading:
            alerts.append(
                f"COMPETITOR LEADING: '{entry['competitor']}' cited {entry['count']}x on query '{entry['keyword']}'"
            )
        # Check branded/unbranded ratio
        if citation_probabilities:
            branded_total = sum(1 for kw in citation_probabilities if "folloze" in kw.lower())
            unbranded_total = len(citation_probabilities) - branded_total
            target_unbranded_pct = self.mc.unbranded_target
            actual_unbranded_pct = unbranded_total / len(citation_probabilities)
            if actual_unbranded_pct < target_unbranded_pct * 0.8:
                alerts.append(
                    f"RATIO WARNING: Unbranded citation coverage {actual_unbranded_pct:.0%} is below "
                    f"target of {target_unbranded_pct:.0%}. Prioritize Tier 3 pain-point content."
                )
        return alerts
```

### Report builder — `report.py`

```python
def build_daily_report(summary: MonitorRunSummary, db_path: Path) -> str:
    """
    Returns HTML string for send_canary_report() in notify.py.
    Format mirrors existing canary report HTML style.
    """
    conn = sqlite3.connect(db_path)
    trend_rows = get_trend_data(conn, days=7)
    conn.close()

    alert_html = ""
    if summary.alerts:
        items = "".join(f"<li style='color:#c0392b'>{a}</li>" for a in summary.alerts)
        alert_html = f"<h2>Alerts ({len(summary.alerts)})</h2><ul>{items}</ul>"

    gap_html = ""
    if summary.gaps:
        items = "".join(f"<li>{g}</li>" for g in summary.gaps)
        gap_html = f"<h2>Zero-citation keywords ({len(summary.gaps)})</h2><ul>{items}</ul>"

    competitor_html = ""
    if summary.competitor_leading:
        rows = "".join(
            f"<tr><td>{e['keyword']}</td><td>{e['competitor']}</td><td>{e['count']}</td></tr>"
            for e in summary.competitor_leading
        )
        competitor_html = f"""
        <h2>Competitor leading citations</h2>
        <table border='1' cellpadding='4'>
        <tr><th>Keyword</th><th>Competitor</th><th>Sightings</th></tr>
        {rows}
        </table>"""

    tier_rows = "".join(
        f"<tr><td>{tier}</td><td>{rate:.0%}</td></tr>"
        for tier, rate in summary.tier_breakdown.items()
    )

    trend_rows_html = ""
    for row in trend_rows:
        d = json.loads(row.get("summary_json") or "{}")
        trend_rows_html += (
            f"<tr><td>{row['run_date']}</td>"
            f"<td>{d.get('overall_citation_rate', 0):.0%}</td>"
            f"<td>{d.get('gaps', [])}</td>"
            f"<td>{'YES' if row['alert_fired'] else 'no'}</td></tr>"
        )

    return f"""
    <h1>Folloze GEO Citation Monitor — {summary.run_date}</h1>

    <h2>Summary</h2>
    <p>Keywords checked: <b>{summary.keywords_checked}</b> |
    Overall citation rate: <b>{summary.overall_citation_rate:.0%}</b> |
    Branded: <b>{summary.branded_rate:.0%}</b> |
    Unbranded: <b>{summary.unbranded_rate:.0%}</b></p>

    <h2>By tier</h2>
    <table border='1' cellpadding='4'>
    <tr><th>Tier</th><th>Citation rate</th></tr>
    {tier_rows}
    </table>

    {alert_html}
    {gap_html}
    {competitor_html}

    <h2>7-day trend</h2>
    <table border='1' cellpadding='4'>
    <tr><th>Date</th><th>Citation rate</th><th>Gaps</th><th>Alerts</th></tr>
    {trend_rows_html}
    </table>
    """
```

### Entry script — `scripts/run_citation_monitor.py`

```python
#!/usr/bin/env python3
"""Nightly citation monitor. Run by launchd at 10 PM."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import Config
from citation_monitor.monitor import CitationMonitor
from citation_monitor.report import build_daily_report
from notify import send_canary_report


def main() -> int:
    config = Config.load(ROOT / "config.yaml")
    db_path = ROOT / "data" / "citation_monitor.db"
    db_path.parent.mkdir(exist_ok=True)

    monitor = CitationMonitor(config, db_path)
    summary = monitor.run()
    body = build_daily_report(summary, db_path)
    subject = (
        f"[Folloze GEO] Citation Monitor — {summary.run_date} "
        f"({summary.overall_citation_rate:.0%} citation rate, "
        f"{len(summary.alerts)} alerts)"
    )
    send_canary_report(subject, body, config)
    return 1 if summary.alerts else 0


if __name__ == "__main__":
    sys.exit(main())
```

### launchd plist — `launchd/com.folloze.content-engine.citation-monitor.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.folloze.content-engine.citation-monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/treyharnden/Projects/folloze-content-engine/.venv/bin/python</string>
        <string>scripts/run_citation_monitor.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/treyharnden/Projects/folloze-content-engine</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>22</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/treyharnden/Projects/folloze-content-engine/logs/citation-monitor.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/treyharnden/Projects/folloze-content-engine/logs/citation-monitor-error.log</string>
    <key>RunAtLoad</key>
    <false/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
```

Install with: `cp launchd/com.folloze.content-engine.citation-monitor.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.folloze.content-engine.citation-monitor.plist`

### New secret needed

Add to `runtime_secrets.py` DEFAULT_KEYCHAIN_SERVICES mapping:

```python
"OPENAI_API_KEY": ("openai-api", "openai-api-key"),
```

**Before adding**: check whether `LLMGateway(profile="openai")` already has web search enabled. If it does, `query_openai_web_search()` can be simplified to a single LLMGateway call and the separate API key is not needed.

Store the key:
```bash
security add-generic-password -a "treyharnden" -s "openai-api" -w "<key>" -U
```

Add to `~/.zshrc`:
```bash
export OPENAI_API_KEY=$(security find-generic-password -s "openai-api" -w)
```

---

## Phase 3: Gap Analyzer

### Directory structure

```
/Users/treyharnden/Projects/folloze-content-engine/
  gap_analyzer/
    __init__.py
    analyzer.py          # KEYWORD_REGISTRY, scoring formula, GapAnalyzer class
    dominance.py         # DominanceGraph: keyword → competitor dominance scores
    calendar_writer.py   # Proposes topics to content/calendar.yaml
  data/
    gap_scores.db        # gitignored
  scripts/
    run_gap_analyzer.py
  launchd/
    com.folloze.content-engine.gap-analyzer.plist
```

### SQLite schema — `gap_scores.db`

```sql
CREATE TABLE IF NOT EXISTS gap_analysis_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date            TEXT NOT NULL,
    run_ts              TEXT NOT NULL,
    keywords_analyzed   INTEGER NOT NULL DEFAULT 0,
    gaps_identified     INTEGER NOT NULL DEFAULT 0,
    topics_proposed     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS keyword_scores (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                  INTEGER NOT NULL REFERENCES gap_analysis_runs(id),
    keyword                 TEXT NOT NULL,
    tier                    TEXT NOT NULL,
    search_volume           INTEGER,
    citation_rate           REAL,
    competitor_dominance    REAL,
    composite_gap_score     REAL,
    rank                    INTEGER,
    recommended_content_type TEXT,
    proposed_title          TEXT,
    proposed_slug           TEXT
);

CREATE TABLE IF NOT EXISTS competitor_dominance (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES gap_analysis_runs(id),
    keyword         TEXT NOT NULL,
    competitor      TEXT NOT NULL,
    citation_count  INTEGER NOT NULL DEFAULT 0,
    dominance_score REAL NOT NULL DEFAULT 0.0
);
```

### Dominance graph — `dominance.py`

```python
from dataclasses import dataclass
from pathlib import Path
import sqlite3

@dataclass(slots=True)
class DominanceNode:
    keyword: str
    competitor: str
    citation_count: int
    dominance_score: float  # citation_count / total_checks_for_keyword

class DominanceGraph:
    """
    Builds a keyword → competitor dominance map from citation_monitor.db data.
    Implements the DominanceGraph pattern from max-d3v/geo_toolkit.
    """

    def __init__(self, monitor_db: Path, lookback_days: int = 7) -> None:
        self._data: dict[str, list[DominanceNode]] = {}
        self._load(monitor_db, lookback_days)

    def _load(self, db_path: Path, lookback_days: int) -> None:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT cs.keyword, cs.competitor, SUM(cs.sighting_count) as total,
                   COUNT(DISTINCT cr.variant_text) as variant_count
            FROM competitor_sightings cs
            JOIN monitor_runs mr ON cs.run_id = mr.id
            LEFT JOIN citation_results cr
                ON cr.run_id = mr.id AND cr.keyword = cs.keyword
            WHERE mr.run_date > date('now', :days)
            GROUP BY cs.keyword, cs.competitor
        """, {"days": f"-{lookback_days} days"}).fetchall()
        conn.close()

        for row in rows:
            keyword = row["keyword"]
            node = DominanceNode(
                keyword=keyword,
                competitor=row["competitor"],
                citation_count=row["total"],
                dominance_score=(
                    row["total"] / row["variant_count"]
                    if row["variant_count"] > 0 else 0.0
                ),
            )
            self._data.setdefault(keyword, []).append(node)

    def dominance_for_keyword(self, keyword: str) -> dict[str, float]:
        """Returns {competitor: dominance_score} for this keyword."""
        return {node.competitor: node.dominance_score for node in self._data.get(keyword, [])}

    def top_dominant_competitor(self, keyword: str) -> tuple[str, float] | None:
        """Returns (competitor_name, dominance_score) for the most-cited competitor, or None."""
        nodes = self._data.get(keyword, [])
        if not nodes:
            return None
        top = max(nodes, key=lambda n: n.dominance_score)
        return top.competitor, top.dominance_score

    def max_competitor_dominance(self, keyword: str) -> float:
        """Returns the highest dominance score among all competitors for this keyword."""
        nodes = self._data.get(keyword, [])
        if not nodes:
            return 0.0
        return max(n.dominance_score for n in nodes)
```

### Scoring and orchestration — `analyzer.py`

```python
import math
import json
import dataclasses
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from config import Config
from gap_analyzer.dominance import DominanceGraph
from citation_monitor.storage import init_db, get_citation_rates

# ---------------------------------------------------------------------------
# Keyword registry
# Must stay in sync with citation_monitor/variants.py KEYWORDS.
# Add search_volume here for gap scoring.
# ---------------------------------------------------------------------------

KEYWORD_REGISTRY: list[dict] = [
    # Tier 1: High-intent, high-volume
    {"keyword": "ai marketing platform",            "tier": "tier1", "volume": 590},
    {"keyword": "personalization technology",       "tier": "tier1", "volume": 320},
    {"keyword": "ai personalization",               "tier": "tier1", "volume": 260},
    {"keyword": "personalized landing pages",       "tier": "tier1", "volume": 170},
    {"keyword": "website personalization",          "tier": "tier1", "volume": 130},
    {"keyword": "microsites vs landing pages",      "tier": "tier1", "volume": 260},
    {"keyword": "abx marketing",                    "tier": "tier1", "volume": 170},

    # Tier 2: Competitor + comparison
    {"keyword": "mutiny alternatives",              "tier": "tier2", "volume": 50},
    {"keyword": "folloze vs userled",               "tier": "tier2", "volume": 30},
    {"keyword": "pathfactory competitors",          "tier": "tier2", "volume": 40},
    {"keyword": "best abm personalization tools",   "tier": "tier2", "volume": 60},
    {"keyword": "prismic vs folloze",               "tier": "tier2", "volume": 20},

    # Tier 3: Pain-point / unbranded (highest weight — biggest LLM gap)
    {"keyword": "how to personalize content for different accounts without hiring more people",
     "tier": "tier3", "volume": 20},
    {"keyword": "why do b2b campaigns take so long to launch",
     "tier": "tier3", "volume": 15},
    {"keyword": "how to make abm work with a small marketing team",
     "tier": "tier3", "volume": 10},
    {"keyword": "what tools help marketers create personalized buyer experiences",
     "tier": "tier3", "volume": 12},
    {"keyword": "how to use ai in b2b marketing without replacing my team",
     "tier": "tier3", "volume": 18},
    {"keyword": "scaling campaign creation without more budget or headcount",
     "tier": "tier3", "volume": 8},
]

# Tier weights: Tier 3 highest because it is the largest LLM citation gap per strategy
TIER_WEIGHTS: dict[str, float] = {
    "tier1": 1.0,
    "tier2": 0.7,
    "tier3": 1.3,
}

CONTENT_TYPE_BY_TIER: dict[str, str] = {
    "tier1": "blog",
    "tier2": "comparison",
    "tier3": "guide",
}

def compute_gap_score(
    keyword: str,
    tier: str,
    volume: int,
    citation_rate: float,
    competitor_dominance: float,
) -> float:
    """
    Composite gap score formula:

        score = tier_weight * log10(volume + 1) * (1 - citation_rate) * (1 + competitor_dominance)

    Interpretation:
    - High volume AND low citation rate AND competitor actively leading = highest urgency
    - (1 - citation_rate): gap size. 1.0 if never cited, 0.0 if always cited.
    - (1 + competitor_dominance): multiplier. 1.0 if no competitors; up to ~2.0 if competitor dominates.
    - log10(volume + 1): diminishing returns on volume. 590/mo → 2.77, 20/mo → 1.32.
    - Returns 0.0 if already performing (citation_rate >= 0.75).
    """
    if citation_rate >= 0.75:
        return 0.0
    tier_weight = TIER_WEIGHTS.get(tier, 1.0)
    volume_factor = math.log10(volume + 1)
    gap_factor = 1.0 - citation_rate
    competition_factor = 1.0 + competitor_dominance
    return tier_weight * volume_factor * gap_factor * competition_factor


@dataclass(slots=True)
class ProposedTopic:
    title: str
    slug: str
    content_type: str
    keywords: list[str]
    priority: int          # 1–10
    source_keyword: str
    gap_score: float
    notes: str

@dataclass(slots=True)
class GapAnalysisResult:
    run_date: str
    ranked_gaps: list[dict]
    proposed_topics: list[ProposedTopic]
    total_keywords_analyzed: int
    avg_citation_rate: float


class GapAnalyzer:

    def __init__(self, config: Config, monitor_db: Path, gap_db: Path) -> None:
        self.config = config
        self.monitor_db = monitor_db
        self.gap_db = gap_db
        self.gc = config.gap_analyzer  # GapAnalyzerConfig

    def run(self) -> GapAnalysisResult:
        from gap_analyzer.storage import init_gap_db, create_gap_run, save_keyword_scores, save_competitor_dominance

        conn = init_db(self.monitor_db)
        citation_rates = get_citation_rates(conn, self.gc.lookback_days)
        conn.close()

        graph = DominanceGraph(self.monitor_db, self.gc.lookback_days)

        gap_conn = init_gap_db(self.gap_db)
        run_id = create_gap_run(gap_conn, date.today().isoformat())

        scored: list[dict] = []
        for kw_entry in KEYWORD_REGISTRY:
            keyword = kw_entry["keyword"]
            tier = kw_entry["tier"]
            volume = kw_entry["volume"]
            citation_rate = citation_rates.get(keyword, 0.0)
            competitor_dominance = graph.max_competitor_dominance(keyword)

            gap_score = compute_gap_score(keyword, tier, volume, citation_rate, competitor_dominance)
            top_competitor = graph.top_dominant_competitor(keyword)

            scored.append({
                "keyword": keyword,
                "tier": tier,
                "volume": volume,
                "citation_rate": citation_rate,
                "competitor_dominance": competitor_dominance,
                "top_competitor": top_competitor[0] if top_competitor else None,
                "gap_score": gap_score,
                "content_type": CONTENT_TYPE_BY_TIER[tier],
            })

        scored.sort(key=lambda x: x["gap_score"], reverse=True)
        for rank, item in enumerate(scored, start=1):
            item["rank"] = rank

        save_keyword_scores(gap_conn, run_id, scored)

        # Save competitor dominance snapshot
        for kw_entry in KEYWORD_REGISTRY:
            kw = kw_entry["keyword"]
            dom = graph.dominance_for_keyword(kw)
            save_competitor_dominance(gap_conn, run_id, kw, dom)

        # Propose topics for top-N gaps above threshold
        candidates = [
            s for s in scored
            if s["gap_score"] >= self.gc.min_gap_score_to_propose
        ][:self.gc.top_n_proposals]

        proposed_topics = [self._propose_topic(c) for c in candidates]

        avg_citation = (
            sum(citation_rates.values()) / len(citation_rates)
            if citation_rates else 0.0
        )

        result = GapAnalysisResult(
            run_date=date.today().isoformat(),
            ranked_gaps=scored,
            proposed_topics=proposed_topics,
            total_keywords_analyzed=len(KEYWORD_REGISTRY),
            avg_citation_rate=avg_citation,
        )

        gap_conn.close()
        return result

    def _propose_topic(self, score_entry: dict) -> ProposedTopic:
        keyword = score_entry["keyword"]
        tier = score_entry["tier"]
        content_type = score_entry["content_type"]
        top_competitor = score_entry.get("top_competitor")
        gap_score = score_entry["gap_score"]

        # Priority: 1–10 from gap_score thresholds
        if gap_score >= 2.0:
            priority = 9
        elif gap_score >= 1.0:
            priority = 7
        elif gap_score >= 0.5:
            priority = 5
        else:
            priority = 3

        competitor_context = (
            f" (currently {top_competitor} is leading citations on this keyword)"
            if top_competitor else ""
        )
        notes = (
            f"Gap Analyzer proposal. Tier: {tier}. Gap score: {gap_score:.2f}. "
            f"Citation rate: {score_entry['citation_rate']:.0%}.{competitor_context}"
        )

        # Try LLM-assisted title generation
        title = self._llm_title(keyword, tier, content_type, top_competitor)
        slug = self._slugify(title)

        return ProposedTopic(
            title=title,
            slug=slug,
            content_type=content_type,
            keywords=[keyword],
            priority=priority,
            source_keyword=keyword,
            gap_score=gap_score,
            notes=notes,
        )

    def _llm_title(
        self,
        keyword: str,
        tier: str,
        content_type: str,
        top_competitor: str | None,
    ) -> str:
        """Generate a specific, GEO-optimized title for the proposed content."""
        competitor_hint = (
            f"The leading competitor being cited is {top_competitor}. "
            f"Position Folloze as the better answer." if top_competitor else ""
        )
        tier_hint = {
            "tier1": "Optimize for high search volume. Use an outcome-focused, question-style H1.",
            "tier2": "This is a comparison keyword. Use 'vs' or 'alternatives' format in the title.",
            "tier3": "This is a pain-point discovery keyword. Lead with the pain in the title.",
        }.get(tier, "")

        prompt = (
            f"Generate a blog post title for Folloze (an AI orchestration platform for B2B marketing) "
            f"targeting the keyword: '{keyword}'.\n"
            f"Content type: {content_type}.\n"
            f"{tier_hint}\n"
            f"{competitor_hint}\n"
            f"Rules: Include the keyword naturally. Under 70 characters. "
            f"Question or outcome format where appropriate. Include (2026) if it adds credibility. "
            f"No marketing fluff. No em dashes. No colons unless necessary.\n"
            f"Return ONLY the title string, no quotes, no explanation."
        )
        try:
            from llm_gateway import LLMGateway
            gw = LLMGateway(profile="workhorse")
            response = gw.chat([{"role": "user", "content": prompt}])
            title = response.strip().strip('"').strip("'")
            if 10 < len(title) < 120:
                return title
        except Exception:
            pass

        # Deterministic fallback by tier
        if tier == "tier2" and top_competitor:
            return f"Folloze vs {top_competitor.title()}: Which Is Right for Your ABM Stack"
        if tier == "tier3":
            return keyword.capitalize().rstrip("?") + " (2026 Guide)"
        return f"How to Use {keyword.title()} for B2B Marketing in 2026"

    @staticmethod
    def _slugify(title: str) -> str:
        import re
        return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
```

### Calendar writer — `calendar_writer.py`

```python
import re
from pathlib import Path
import yaml
from gap_analyzer.analyzer import ProposedTopic

def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

def propose_to_calendar(
    topics: list[ProposedTopic],
    calendar_path: Path,
    dry_run: bool = False,
) -> list[str]:
    """
    Appends proposed topics to content/calendar.yaml with status='pending'.
    Skips topics whose slug already exists in the calendar.
    Returns list of slugs actually added.

    IMPORTANT: Does not overwrite or modify existing entries. Only appends.
    """
    with calendar_path.open() as f:
        raw = yaml.safe_load(f) or {}

    existing_slugs: set[str] = set()
    for item in raw.get("topics", []):
        existing_slug = item.get("slug") or _slugify(item.get("title", ""))
        existing_slugs.add(existing_slug)

    added: list[str] = []
    new_entries: list[dict] = []

    for topic in topics:
        if topic.slug in existing_slugs:
            continue  # Skip duplicate — never overwrite
        entry = {
            "title": topic.title,
            "content_type": topic.content_type,
            "slug": topic.slug,
            "keywords": topic.keywords,
            "priority": topic.priority,
            "status": "pending",
            "notes": topic.notes,
            "planned_date": None,  # No date set; pipeline picks up by priority
        }
        new_entries.append(entry)
        added.append(topic.slug)
        existing_slugs.add(topic.slug)

    if dry_run:
        return added  # Report what would be added without writing

    if new_entries:
        raw.setdefault("topics", []).extend(new_entries)
        with calendar_path.open("w") as f:
            yaml.safe_dump(raw, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return added
```

### Entry script — `scripts/run_gap_analyzer.py`

```python
#!/usr/bin/env python3
"""Weekly gap analyzer. Run by launchd Sunday 6 AM."""

import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import Config
from gap_analyzer.analyzer import GapAnalyzer
from gap_analyzer.calendar_writer import propose_to_calendar
from gap_analyzer.report import build_gap_report
from notify import send_canary_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Propose but do not write to calendar")
    parser.add_argument("--top-n", type=int, default=None, help="Override top_n_proposals from config")
    args = parser.parse_args()

    config = Config.load(ROOT / "config.yaml")
    monitor_db = ROOT / "data" / "citation_monitor.db"
    gap_db = ROOT / "data" / "gap_scores.db"
    gap_db.parent.mkdir(exist_ok=True)

    if not monitor_db.exists():
        print("ERROR: citation_monitor.db not found. Run citation monitor at least once first.")
        return 1

    analyzer = GapAnalyzer(config, monitor_db, gap_db)
    result = analyzer.run()

    top_n = args.top_n or config.gap_analyzer.top_n_proposals
    added = propose_to_calendar(
        result.proposed_topics[:top_n],
        ROOT / "content" / "calendar.yaml",
        dry_run=args.dry_run,
    )

    body = build_gap_report(result, added, dry_run=args.dry_run)
    subject = (
        f"[Folloze GEO] Weekly Gap Analysis — {result.run_date} "
        f"({len(result.proposed_topics)} topics proposed, avg citation rate {result.avg_citation_rate:.0%})"
    )
    send_canary_report(subject, body, config)

    if args.dry_run:
        print(f"DRY RUN: would have added {len(added)} topics:")
        for slug in added:
            print(f"  - {slug}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Gap report builder — `gap_analyzer/report.py`

```python
def build_gap_report(
    result: "GapAnalysisResult",
    added: list[str],
    dry_run: bool = False,
) -> str:
    """Returns HTML string for send_canary_report() in notify.py."""

    dry_run_banner = (
        "<p style='color:orange;font-weight:bold'>DRY RUN — no calendar entries written</p>"
        if dry_run else ""
    )

    proposed_rows = "".join(
        f"<tr><td>{t.title}</td><td>{t.content_type}</td>"
        f"<td>{t.priority}</td><td>{t.gap_score:.2f}</td>"
        f"<td>{'ADDED' if t.slug in added else 'SKIPPED (exists)'}</td></tr>"
        for t in result.proposed_topics
    )

    top_gap_rows = "".join(
        f"<tr><td>#{g['rank']}</td><td>{g['keyword']}</td><td>{g['tier']}</td>"
        f"<td>{g['citation_rate']:.0%}</td><td>{g.get('top_competitor') or '—'}</td>"
        f"<td>{g['gap_score']:.2f}</td></tr>"
        for g in result.ranked_gaps[:10]
    )

    return f"""
    <h1>Folloze GEO Gap Analyzer — {result.run_date}</h1>
    {dry_run_banner}

    <h2>Summary</h2>
    <p>Keywords analyzed: <b>{result.total_keywords_analyzed}</b> |
