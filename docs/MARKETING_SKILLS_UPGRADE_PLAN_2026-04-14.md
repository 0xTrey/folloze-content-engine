# Marketing Skills Upgrade Plan for Folloze Content Engine

Date: 2026-04-14
Focus: improve the repo's blog-content writer around:
- AEO
- SEO
- copywriting quality
- LLM visibility / discoverability

## Executive diagnosis

The repo already has meaningful infrastructure for AEO and GEO:
- generation
- optimization
- quality scoring
- citation monitoring
- calendarized topic production

The biggest immediate weakness is not missing theory. It is contract mismatch.

Specifically:
- `quality.py` expects stronger citation-ready and GEO-friendly structure
- `blog.md` is still comparatively thin and concise
- `optimizer.py` is mostly structural, not strategic
- the blog writer is likely relying on repair loops to achieve standards that should be present in the first draft

## What is already in place

### AEO / GEO infrastructure already present
- `generator.py`
- `optimizer.py`
- `quality.py`
- `citation_monitor/*`
- `schema/blog.json`
- GEO checks and tests in `tests/test_quality_geo.py`

### Strong signs the repo is already aimed at the right target
- PRD explicitly says LLM crawlers first
- GEO quality threshold exists in config
- citation monitor exists and is not just planned
- blog content type exists end-to-end

## The four workstreams to prioritize

## 1) AEO upgrade for blog writer

### Current issue
The blog prompt requires:
- 550 to 700 words
- 3 short sections
- brief FAQ
- 2 attributed statements
- 1 statistic

But the quality/GEO layer wants content that is more citation-ready, including checks around:
- TL;DR / summary presence
- answer-first paragraphs
- heading density
- citation formatting
- freshness signals
- entity consistency
- emotion-first intro

### Diagnosis
The blog writer is under-specified relative to the quality gate.
That means the writer is probably not producing the cleanest AEO-native blog form on the first attempt.

### Proposed AEO upgrades
1. Add a required **TL;DR / key takeaways block** near the top.
2. Require a stronger **definition-first + answer-first opening**.
3. Increase default blog depth from "short launch post" mode to a more citable format when topic intent is educational or category-defining.
4. Require a clearer **FAQ contract**:
   - 3 to 5 FAQ pairs
   - FAQ questions must align to search intent variations
5. Require stronger **question clustering** in H2s:
   - what is X
   - why does X matter
   - how to do X / how Folloze approaches X
   - common mistakes or FAQs
6. Make blog output include at least one explicit **trade-off / caveat** section when topic is strategic or comparative.

## 2) SEO upgrade for blog writer

### Current issue
The repo captures target keywords and meta description, but the blog prompt is more AEO-first than holistic SEO-first.
There is not enough explicit prompt pressure around search-intent matching, SERP structure, internal-link architecture, and title/meta click behavior.

### Proposed SEO upgrades
1. Add **search-intent classification** to topic inputs:
   - informational
   - comparative
   - integration / how-to
   - category definition
2. Require the prompt to align article structure to intent.
3. Add explicit blog constraints for:
   - title tag quality
   - meta description quality
   - first-100-word relevance
   - secondary keyword coverage via natural subheads
4. Add an SEO scoring extension for:
   - title length / clarity
   - meta description length
   - primary keyword in H1
   - primary keyword or close variant in first paragraph
   - internal link spread beyond just 2 mandatory Folloze links
5. Add optional **entity-supporting outbound citations** to credible sources where appropriate.
6. Add pre-publish search-gap context from existing Perplexity/Brave research so the article can deliberately fill missing SERP/answer gaps.

## 3) Copywriting upgrade for blog writer

### Current issue
The system already blocks fluff via kill-list terms, but good copywriting is not only the absence of hype.
The prompt does not yet enforce enough around rhythm, specificity, quotability, executive readability, or point-of-view sharpness.

### Proposed copywriting upgrades
1. Add a **quote-worthy sentence requirement**:
   - at least 2 sentences should be short, specific, and citation-friendly
2. Add a **point-of-view requirement**:
   - every blog should state a clear Folloze angle, not just summarize the category
3. Add a **specificity requirement**:
   - at least one concrete example, scenario, or workflow
4. Add a **proof hierarchy rule**:
   - Folloze proof if relevant
   - third-party proof if stronger
   - no unsupported abstract claims
5. Add a **reader payoff rule**:
   - every H2 should answer an actual buyer/researcher question
6. Add **anti-generic copy checks** beyond kill-list words:
   - vague claims like "improves results"
   - unsupported absolutes
   - overused AI-marketing tropes

## 4) LLM visibility / discoverability upgrade

### Current issue
The repo is philosophically aligned to GEO, but blog content still looks like it may be optimized more for passing a gate than for being the easiest thing for an LLM to quote.

### Proposed discoverability upgrades
1. Explicitly require a **citation block pattern** in blog content:
   - "According to [Source] (Year)..."
   - short fact + implication
2. Add a **quotability pass** in generation or repair prompt:
   - concise definitions
   - framework bullets
   - terminology clarity
3. Add a **retrieval-friendly summary section** with short declarative bullets.
4. Add a **buyer-question coverage map** in the prompt so each blog addresses adjacent prompts, not just one keyword.
5. Add a new quality check for **framework extractability**:
   - lists, rules, steps, comparison bullets, or decision criteria
6. Add a pre-publish **"Ask an LLM" delta check** as already noted in `TODOS.md` TODO-7.

## Highest-leverage code changes

## Phase 1: blog writer contract upgrade
Files:
- `content/templates/blog.md`
- `tests/test_generator.py`
- maybe `tests/test_quality_geo.py`

Change goals:
- align blog prompt with the current quality/gEO gate
- reduce repair-loop dependence
- generate more citation-ready structure on first pass

### Specific edits to make
- require TL;DR block
- require 3 to 5 FAQ pairs, not just a brief FAQ section
- require 700 to 1000 words for substantive blog topics, or at minimum raise the default target above the current 550 to 700 band for non-launch posts
- require one explicit trade-off / caveat section where relevant
- require a stronger answer-first first paragraph
- require at least 2 quote-worthy declarative lines
- require one source citation in the exact `(Year)` pattern

## Phase 2: SEO scoring extension
Files:
- `quality.py`
- `tests/test_quality.py` or new `tests/test_quality_seo.py`

Add checks for:
- title quality / length
- meta description quality / length
- keyword in first paragraph
- variant coverage in headings
- internal link sufficiency by article length

## Phase 3: copywriting quality extension
Files:
- `quality.py`
- `generator.py`
- `brand_rules.py`

Add checks or prompt rules for:
- quote-worthy specificity
- unsupported generic claim detection
- scenario/example presence
- stronger POV signal

## Phase 4: LLM discoverability assist layer
Files:
- `research.py`
- `generator.py`
- `pipeline.py`
- maybe notifications / review email path

Build:
- pre-publish "what Perplexity currently says" block
- gap-aware prompt instructions
- explicit "what new information should this page contribute" prompt section

## Concrete repo findings behind this plan

### Blog prompt is thinner than comparison/guide prompts
`content/templates/blog.md` is concise and light:
- 550 to 700 words
- 3 short sections
- brief FAQ

By contrast, `comparison.md` and `guide.md` are more explicit about:
- trade-offs
- structure
- buyer criteria
- richer utility

### Quality expectations are stronger than blog prompt expectations
`quality.py` currently checks for GEO behavior such as:
- TL;DR presence
- answer-first paragraphs
- heading density
- citation format
- freshness
- emotion-first intro

That is directionally right.
But the blog prompt should induce these patterns directly, not depend on downstream repair.

### Schema is fine but not enough on its own
`schema/blog.json` already includes:
- Article
- author
- datePublished
- dateModified

So schema is not the main bottleneck.
The bottleneck is the article contract itself.

## Suggested execution order

1. Upgrade `content/templates/blog.md`
2. Add blog-specific tests proving the new contract
3. Add SEO scoring checks in `quality.py`
4. Add stronger copy-quality checks
5. Add the pre-publish LLM gap test from TODO-7

## What success looks like

A strong blog draft should:
- read like expert briefing, not marketing filler
- answer the primary query immediately
- include quote-worthy definitions and facts
- include enough structure that an LLM can safely extract it
- support both classic SEO and LLM citation behavior
- require fewer repair loops to clear the gate

## Recommended next implementation step

Start with **Phase 1: tighten `content/templates/blog.md`**.

Reason:
- highest leverage
- lowest risk
- immediately improves AEO, copywriting, and discoverability together
- likely reduces quality-repair churn across the whole pipeline
