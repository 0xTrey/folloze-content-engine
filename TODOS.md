# TODOS — Folloze Content Engine

Deferred work. Pick up in phase order.

---

## TODO-1: Citation Monitor
**Phase:** 3 | **Priority:** P1 | **Effort:** M

**What:** Periodically query ChatGPT, Perplexity, and Claude with target keywords. Check whether Folloze appears in the response. Track citation rate over time. Report weekly.

**Why:** Without this, you're publishing content but never knowing if LLMs are actually citing it. Citation monitor closes the feedback loop.

**Pros:** Measures actual impact. Identifies which content types get cited most. Guides future calendar priorities.

**Cons:** Costs API calls per query. Requires parsing LLM responses to detect mentions (fuzzy match needed).

**Context:** Build after V1 pipeline has been running for 2+ weeks and has 20+ pages published. Start with 10 target queries (e.g., "best ABM platform", "Folloze vs Mutiny", "AI marketing orchestration tool"). Log results to `logs/citations/YYYY-MM-DD.json`. Weekly digest email.

**Depends on:** V1 pipeline running, content published.

---

## TODO-2: Gap Analyzer
**Phase:** 3 | **Priority:** P1 | **Effort:** M

**What:** Compare published content against a keyword universe (B2B marketing orchestration terms, competitor names, use cases, industry questions). Identify queries where Folloze has no content. Score gaps by estimated citation value. Auto-suggest topics for calendar.

**Why:** Identifies where to publish next for maximum LLM visibility impact.

**Pros:** Makes content calendar decisions data-driven. Prevents duplicate content.

**Cons:** Requires building and maintaining a keyword universe. Scraping competitor sitemaps needs maintenance.

**Context:** Build keyword universe from: Folloze's own product pages, competitor blogs (Mutiny/Userled/PathFactory), B2B marketing glossaries, common ABM/demand gen questions. Output: ranked list of missing topics → append to `content/calendar.yaml` for Juno review.

**Depends on:** Citation monitor (TODO-1) for prioritization signal. V1 pipeline running.

---

## TODO-3: Slack Notifications
**Phase:** 3 | **Priority:** P2 | **Effort:** S

**What:** Replace email notifications with Slack messages to `#folloze-content-engine` channel. Release-ready reviews, publish confirmations, errors. Richer formatting with buttons/threads.

**Why:** Marketing teams work in Slack. Email notifications get missed or buried.

**Pros:** Faster review cycle. Slack reminders reduce forgotten drafts.

**Cons:** Requires Slack webhook setup. Email stays as backup.

**Context:** Keep email as fallback. Add `slack_webhook_url` to `config.yaml`. Reuse same notification templates — just swap the delivery transport in `notify.py`. Should be a 2-3 hour change.

**Depends on:** V1 email flow validated for 2+ weeks.

---

## TODO-8: Webflow Migration And Marketing Handoff
**Phase:** 2 | **Priority:** P1 | **Effort:** M

**What:** Migrate the V1 release-artifact contract into a Webflow collection and transfer day-to-day ownership to the marketing and web-dev teams.

**Why:** V1 intentionally ships on a Vercel-hosted static site so the content pipeline, logs, and handoff path can be validated first. V2 is the point where delivery moves into Webflow for the marketing team.

**Pros:** Keeps V1 simple. Preserves a stable content contract. Gives the web-dev team an explicit migration target instead of reverse-engineering the system.

**Cons:** Adds a platform migration after V1. Requires CMS field mapping and QA to avoid content regressions.

**Context:** Use `docs/MIGRATION_TO_WEBFLOW_V2.md` as the source of truth. Build a Webflow collection that maps one-to-one from the V1 release artifact fields. Keep upstream pipeline modules unchanged. Only the delivery target changes.

**Depends on:** V1 release artifacts stable. Deployment docs complete. Marketing team ready to own the CMS workflow.

---

## TODO-4: Freshness Refresher
**Phase:** 5 | **Priority:** P2 | **Effort:** M

**What:** Scan published pages for stale dates (e.g., "2026" when it's now 2027), outdated statistics, deprecated product claims ("Folloze v1" etc.), or retired positioning. Auto-regenerate stale sections and republish through the active delivery target.

**Why:** Princeton GEO research shows freshness is a ranking factor for AI citations. Content older than 12 months degrades in citation rate.

**Pros:** Keeps content library evergreen. Maintains citation rates over time.

**Cons:** Risk of over-regenerating content that's still accurate. Need careful freshness detection.

**Context:** Run as a weekly job separate from daily pipeline. Detect stale signals: (a) date strings older than 18 months, (b) statistics from pre-2025 sources, (c) product terms that have been retired per brand doc updates. Regenerate only the stale sections, not full pages. Queue for human review before republishing.

**Depends on:** V1 pipeline running. Established content library (50+ pages).

---

## TODO-5: Self-Seeding Calendar
**Phase:** 4 | **Priority:** P2 | **Effort:** M

**What:** Gap analyzer feeds directly into content calendar. Engine identifies missing topics, scores them by estimated citation impact, and appends to `content/calendar.yaml`. Juno reviews weekly rather than seeding manually.

**Why:** Removes human bottleneck from topic selection. Calendar stays full without manual work.

**Pros:** True autonomous operation. Calendar never runs dry.

**Cons:** Risk of off-brand or low-value topics if scoring model is wrong. Juno weekly review provides safety net.

**Context:** Output of gap analyzer (TODO-2) directly creates pending calendar entries with priority scores. Juno can approve/reject/reorder in weekly review. Never auto-approve without Juno review in V1 of this feature.

**Depends on:** Gap analyzer (TODO-2).

---

## TODO-6: Existing Blog AEO Retrofit
**Phase:** — | **Priority:** P3 | **Effort:** L

**What:** Analyze Folloze's existing 140 blog posts. Add enhanced JSON-LD overlays (FAQPage schema, comparison tables where appropriate), add cited sources, update to AEO-optimized structure, and republish through the active delivery target.

**Why:** Existing posts already have domain authority but lack AEO optimization. Retrofitting is high-leverage — free citation lift on established pages.

**Cons:** Risky — modifying 140 production blog posts. Requires access to whichever production content system owns the blog at that time. Significant effort.

**Context:** Approach: read existing post body, run through AEO optimizer in "retrofit" mode (less aggressive — add FAQ block + JSON-LD without rewriting existing copy). Stage the updates for review before publishing. Start with top 20 posts by organic traffic.

**Depends on:** V1 Insights pipeline proven. Active delivery target confirmed. Folloze marketing team approval.

---

## TODO-7: "Ask an LLM" Pre-Publish Test
**Phase:** — | **Priority:** P1 | **Effort:** S

**What:** Before publishing (or included in draft review email), query Perplexity with the target keyword. Check: (a) Does Folloze already appear? (b) Does the draft add new information the LLM doesn't already have? Include the query result snippet in the review email.

**Why:** Shows the reviewer exactly what gap they're filling. Builds confidence in the system and understanding of AEO impact.

**Pros:** Contextualizes every draft. Makes reviews meaningful. Detects redundant content before publishing.

**Cons:** Extra Perplexity API call per run.

**Context:** Add `pre_publish_llm_test: true` config flag. Run Perplexity with the primary keyword. Capture first 2-3 paragraphs of response. Check for Folloze mention. Include in draft email as "What Perplexity currently says" section. Flag if Folloze already appears (may indicate duplicate content).

**Depends on:** V1 pipeline running. Perplexity API access (already a research dependency).
