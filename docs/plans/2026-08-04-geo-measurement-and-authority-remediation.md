# Folloze GEO Measurement and Authority Remediation Plan

**Prepared:** 2026-08-04
**Status:** Plan only; no calendar edits, publishing, migrations, or live-site changes authorized
**Primary publication:** `https://www.folloze-blog.com`
**Primary implementation repos:**

- `/Users/treyharnden/Projects/folloze-content-engine`
- `/Users/treyharnden/Projects/Folloze-Sales-Stack/projects/reporting-platform`

## Goal

Build a defensible measurement system for SEO, GEO, and AEO across the domains Trey controls, then use that system to improve source quality, close non-branded visibility gaps, strengthen the controlled publication, and build third-party authority without depending on edit access to Folloze.com.

Success means the weekly report can distinguish and trend:

1. Brand mentions
2. Linked citations to a Folloze-controlled URL
3. Google Search and Google generative-search visibility
4. AI referral sessions and conversions
5. New, lost, and qualified backlinks
6. Page-level movement following a publish or refresh

## Decisions

1. Keep `www.folloze-blog.com` as the canonical publication for at least 90 days. Do not migrate to `insights.folloze.com` or `folloze.com/insights` during measurement remediation.
2. Treat Folloze.com as a separate, read-only comparison property. Its sitemap does not need to list URLs from an independently hosted root domain.
3. Complete the existing GSC and GA4 connectors in the reporting platform instead of building duplicates in the content engine.
4. Keep provider-native AI response collection in the content engine. Export normalized observations to the reporting platform for cross-source reporting.
5. Preserve all historical monitor data, but label pre-fix results `metric_version=v1_mention_as_citation` and exclude them from true citation-rate comparisons.
6. Do not create five duplicate gap pages. Create two new canonicals and refresh four existing canonicals covering the remaining monitored intents.
7. Nothing in this plan publishes automatically. New and refreshed artifacts remain review-only until explicitly approved.

## Verified current state

| Area | Current evidence | Implication |
|---|---|---|
| Search Console | Mailbox confirms access to `https://www.folloze.com/`; no confirmation was found for `folloze-blog.com` | Verify a separate Domain property for the controlled publication |
| GA4 | Mailbox confirms an active GA4 account | Account access exists, but property and stream coverage must be inventoried |
| Insights analytics tag | No GA4 tag was found in the live Insights HTML or site build | Instrument the controlled domain before expecting referral reporting |
| Reporting platform | GSC and GA4 connectors, staging models, and marts already exist but are marked blocked | Finish auth/property access and extend the existing connectors |
| AI citation monitor | A Folloze mention is currently classified as a citation; provider source metadata is not reliably preserved | Rename v1 output to mention rate and implement citation parsing v2 |
| Content evidence | At audit time, 134 of 138 published artifacts had no external source URL; 23 scores exceeded 100 | Add a blocking, claim-level evidence gate before further scale |
| Domain state | `www.folloze-blog.com` is the functioning canonical publication; `insights.folloze.com` is unavailable | There is no live duplicate-domain split to repair |
| Folloze.com access | Trey cannot edit Folloze.com content or its sitemap | Corporate linking is optional, not part of the critical path |

The published-artifact count changed during the audit because the working tree is active. Implementation must rerun all inventory counts from a stable snapshot.

## Target architecture

```text
AI answer surfaces
  Perplexity / OpenAI Search / Gemini Grounding / Claude / Copilot
          |
          v
folloze-content-engine
  raw provider response
  provider-native citations
  prompt, variant, provider, surface, locale, timestamp
  mention and linked-citation classification
  versioned JSON/JSONL export
          |
          v
reporting-platform / Neon
  GSC + GA4 + backlinks + AI observations
  page/domain registry
  daily facts and weekly marts
          |
          v
Weekly GEO report v2
  mentions != citations != referrals
  branded != non-branded
  API panel != consumer-surface validation
  7/28/90-day trends and page-level outcomes
```

## Workstream 1: Fix the measurement layer

### 1A. Create an owned-property registry

Add a property registry in the reporting platform rather than hard-coding one site:

```yaml
properties:
  - property_key: folloze_insights
    canonical_origin: https://www.folloze-blog.com
    control_level: owned
    gsc_site_url: sc-domain:folloze-blog.com
    ga4_property_id_env: FOLLOZE_INSIGHTS_GA4_PROPERTY_ID
    sitemap_urls:
      - https://www.folloze-blog.com/sitemap.xml
      - https://www.folloze-blog.com/insights-sitemap.xml
  - property_key: folloze_corporate
    canonical_origin: https://www.folloze.com
    control_level: read_only_comparison
    gsc_site_url: https://www.folloze.com/
```

Store property IDs and credential paths in runtime secrets, never in committed configuration.

**Likely reporting-platform changes**

- `common/config.py`
- `connectors/gsc/connector.py`
- `connectors/ga4/connector.py`
- `deploy/schema.sql`
- `dbt/models/staging/stg_gsc_query_daily.sql`
- `dbt/models/staging/stg_ga4_traffic_daily.sql`
- New `docs/runbooks/google_measurement_access.md`

### 1B. Activate Search Console for the controlled domain

1. Verify the Search Console Domain property `sc-domain:folloze-blog.com` through DNS.
2. Also add the URL-prefix property `https://www.folloze-blog.com/` for focused inspection workflows.
3. Submit both controlled-domain sitemaps.
4. Grant the reporting service account read access to the property.
5. Enable the Search Console API and validate one query-page-date pull.
6. Backfill the maximum useful available period by date, page, query, country, device, and search appearance.
7. Query `searchAppearance` dynamically. If Google's generative-AI appearance types are present, ingest them. If unavailable for the property, store `not_available`, not zero.

Google exposes Search Analytics through `searchanalytics.query`, including query, page, country, device, and search-appearance dimensions. The new dedicated generative-AI Search Console reporting is in a limited rollout, so availability must be detected rather than assumed:

- https://developers.google.com/webmaster-tools/v1/searchanalytics/query
- https://developers.google.com/search/blog/2026/06/gen-ai-performance-reports

### 1C. Instrument and activate GA4 on the controlled domain

1. Inventory existing GA4 properties and streams. Reuse an existing `folloze-blog.com` stream if one exists; otherwise create a dedicated web stream/property for the publication.
2. Add a configurable GA4 measurement ID to the site builder.
3. Define the consent/privacy behavior before enabling production collection.
4. Grant the reporting service account Viewer access to the GA4 property.
5. Extend the existing GA4 connector beyond channel grain to collect:

   - `sessionSource`
   - `sessionMedium`
   - `sessionDefaultChannelGroup`
   - `landingPagePlusQueryString`
   - sessions
   - engaged sessions
   - engagement rate
   - key events

6. Classify known AI referrers with a versioned rule set, including ChatGPT/OpenAI, Perplexity, Claude, Gemini, Copilot/Bing Chat, You.com, Phind, and Poe.
7. Retain `direct / none` separately. AI systems can strip referrers; direct traffic must never be relabeled as AI without evidence.
8. Record a deployment annotation when the GA4 tag becomes live so pre-tag and post-tag periods are not blended.

The GA4 Data API supports service-account or user authentication and `runReport`. GA4 traffic-source dimensions can be used to identify known referral sources, while missing referrers remain direct traffic:

- https://developers.google.com/analytics/devguides/reporting/data/v1/quickstart
- https://support.google.com/analytics/answer/15612152
- https://support.google.com/analytics/answer/15258820

### 1D. Implement provider-native citation parsing v2

Replace text-regex URL discovery as the primary evidence source. Every provider adapter must return a shared structure:

```text
provider
surface_type                  api_grounded | consumer_ui
model_or_product
prompt_id
variant_id
response_text
brand_mentioned
citations[]
  url
  title
  cited_text_or_span
  provider_source_id
  is_folloze_controlled_url
search_queries[]
raw_response_path
collected_at
parser_version
```

Provider rules:

- **Perplexity:** use returned `search_results` and numbered citation IDs.
- **OpenAI Search:** use Responses API web-search `url_citation` annotations and web-search source items.
- **Gemini:** enable Google Search grounding and parse `url_citation` annotations or grounding metadata.
- **Claude:** parse native web-search citation blocks when supported by the selected endpoint; otherwise classify it as a consumer-surface sample, not an API citation run.
- **Copilot:** use controlled consumer-surface sampling unless a supported endpoint returns the actual cited sites. Bing index results are a proxy, not Copilot citations.
- **Google AI Overviews:** use the GSC generative-AI report for visibility and clicks. Capture citation URLs through a fixed browser/authorized third-party panel because Search Console performance data does not itself prove which source URL appeared in an overview.

Official provider examples confirm that source metadata is available for grounded API responses:

- Perplexity: https://docs.perplexity.ai/docs/cookbook/articles/streaming-citations/README
- OpenAI: https://platform.openai.com/docs/api-reference/responses-streaming/response/file_search_call
- Gemini: https://ai.google.dev/gemini-api/docs/google-search

**Likely content-engine changes**

- `citation_monitor/providers.py`
- `citation_monitor/monitor.py`
- `citation_monitor/storage.py`
- `citation_monitor/report.py`
- `scripts/run_citation_monitor.py`
- `tests/test_citation_monitor.py`
- New `citation_monitor/contracts.py`
- New parser fixtures under `tests/fixtures/citation_monitor/`

### 1E. Correct the metric definitions

| Metric | Definition |
|---|---|
| Mention rate | Responses containing the Folloze entity / valid responses |
| Linked citation rate | Responses with at least one provider-native citation URL on a Folloze-controlled domain / valid grounded responses |
| Source attribution rate | Linked citations with a captured source URL / all claimed citations |
| Non-branded mention rate | Folloze mentions on prompts that do not contain Folloze / valid non-branded responses |
| Non-branded linked citation rate | Folloze-linked citations on non-branded prompts / valid grounded non-branded responses |
| Share of AI voice | Folloze brand sightings / all tracked-brand sightings on the same fixed panel |
| AI Overview visibility | GSC generative-AI impressions when available; otherwise fixed-panel presence, clearly labeled |
| AI referral sessions | GA4 sessions whose source/referrer matches the versioned AI source rules |
| Qualified referring domains | Relevant, independently hosted domains with verified live links to a controlled target URL |

Rules:

- A paragraph position is not a citation position.
- A plain brand mention is never a citation.
- A response with no source metadata is not a linked citation even when it names Folloze.
- API-grounded results and consumer-product UI observations must be reported separately.
- Provider failures and missing surfaces are excluded from denominators and shown as coverage gaps.
- Every rate must show numerator, denominator, providers, runs, date window, parser version, and prompt-panel version.

### 1F. Join the measurement sources in the reporting platform

Add a content-GEO connector that ingests a versioned export from the content engine. Do not give the content engine direct write access to Neon.

Recommended new reporting objects:

- `stg.stg_ai_visibility_observation`
- `stg.stg_ai_citation`
- `stg.stg_backlink_snapshot`
- `core.fact_ai_visibility_daily`
- `core.fact_ai_citation_daily`
- `core.fact_search_daily` extended with `property_key` and search appearance
- `core.fact_web_traffic_daily` extended with property, landing page, and AI-referral classification
- `mart.mart_geo_visibility_weekly`
- `mart.mart_content_outcome_28d`

`mart_content_outcome_28d` should compare each publish or refresh against its own pre-change baseline and report 7-, 14-, and 28-day changes in:

- GSC impressions, clicks, CTR, and position
- Generative-AI impressions when available
- AI mentions and linked citations
- AI referral sessions and key events
- New links/referring domains to the page

### 1G. Replace the weekly report

The weekly email should include:

1. Data coverage and freshness by source
2. Mention rate and linked citation rate as separate cards
3. Branded and non-branded results separately
4. API panel and consumer-surface panel separately
5. Provider, prompt, and run counts
6. GSC search and generative-AI trends for controlled properties
7. GA4 AI referral landing pages and key events
8. New/lost backlinks and top linked pages
9. Page-level 7/14/28-day movement after publishes and refreshes
10. Gaps converted into content actions only when the evidence is stable

Until v2 passes validation, relabel the existing email as an experimental mention monitor and remove the word `citation` from v1 cards.

### 1H. Backlink measurement

1. Inventory access to Semrush and Ahrefs. Existing Semrush mail proves an account relationship, not API entitlement.
2. Build a provider-neutral CSV importer first so GSC Links, Bing Webmaster Tools, Semrush, or Ahrefs exports can establish a baseline immediately.
3. Add direct API ingestion only for a provider with verified entitlement.
4. Store source URL, referring domain, target URL, anchor, first seen, last seen, follow status, authority metric with provider name, and topical relevance.
5. Never merge Semrush Authority Score and Ahrefs Domain Rating into one synthetic number.

## Workstream 2: Make source quality enforceable

### 2A. Add a proof and source registry

Create in the content engine:

- `brand/proof-registry.yaml`
- `evidence.py`
- `scripts/audit_published_evidence.py`

Each proof must have a stable ID, exact claim, public source URL, source type, approval status, review date, expiry date, and allowed uses. External research sources need publisher, canonical URL, publication/update date, retrieval date, authority tier, and supported claim IDs.

### 2B. Preserve source metadata through the pipeline

1. Extend `ResearchContext` in `research.py` with structured source candidates.
2. Preserve Brave result metadata and provider-native Perplexity sources.
3. Treat LLM prose as discovery, never as evidence.
4. Write `source-candidates.json` and `evidence-plan.json` to each run.
5. Generate from approved source IDs rather than asking the model to invent attribution language or URLs.
6. Render the Sources section deterministically from approved IDs.

### 2C. Add a blocking evidence gate

Release requires:

- `evidence_status == ready`
- 100% coverage of material claims
- evidence score at least 90/100
- zero unsupported numbers, customer outcomes, competitor claims, rankings, superiority claims, quotes, or named studies
- at least two public sources for educational pages
- one current official source for each vendor discussed in a comparison
- zero orphan citations, unused source entries, invented URLs, or broken URLs

Do not require every article to contain a statistic or Folloze proof point. Require evidence only when a claim is made. Cap every score at 100 and do not average unsupported evidence away inside a composite score.

### 2D. Carry provenance into artifacts

Add to release artifacts:

- `evidence_status`
- `evidence_score`
- `claim_source_matrix`
- `sources`
- `proof_ids`
- `date_modified`

The pipeline must stop before release-artifact creation if the evidence gate fails.

### 2E. Backfill without disturbing published work

1. Batch A: the six canonicals covering persistent monitored gaps.
2. Batch B: all comparison/evaluation pages.
3. Batch C: pages with scores above 100 and pages containing customer outcomes or named quotes.
4. Batch D: remaining guides, definitions, FAQs, and blogs in groups of 20–25.

The audit script produces remediation manifests and review artifacts only. Existing URLs remain unchanged. A material refresh updates `dateModified`; it does not delete or redirect the published page.

## Workstream 3: Close persistent non-branded gaps without cannibalization

| Prompt package | Action | Canonical strategy |
|---|---|---|
| `t1-001`: best AI marketing platform | Create `Best AI Marketing Platforms for B2B: Evaluation Criteria and Shortlist` | New comparison page; the current glossary draft does not match vendor-evaluation intent |
| `t1-003`: personalize without rebuilding | Refresh `how-to-personalize-content-for-different-accounts-without-hiring-more-people` | Keep existing URL and add exact answer blocks and evidence |
| `t2-001`: individual-level personalization | Create `What Is Individual-Level Personalization in B2B Marketing?` | New definition page linked from existing individual-engagement and ABM-breakdown content |
| `t1-006`: DSR definition | Refresh `digital-sales-rooms-for-b2b-revenue-teams` | Keep existing definition canonical |
| `t1-007`: enterprise DSR evaluation | Refresh `best-digital-sales-room-software-for-enterprise-revenue-teams` | Keep existing evaluation canonical |
| `t3-001`: one marketer scales AI campaigns | Refresh `how-one-marketer-can-run-enterprise-campaigns-with-folloze` | Keep existing URL and retitle toward the exact non-branded intent |

Each work package must carry its monitor `prompt_id`, approved evidence pack, canonical decision, target answer block, internal-link plan, and pre-change baseline.

Candidate calendar swaps after the evidence gate and refresh workflow are ready:

| Candidate date | Defer | Prepare instead |
|---|---|---|
| Aug 5 | What Is a Buying Committee Engagement Platform? | New `t1-001` comparison |
| Aug 7 | B2B Buyer Journey Personalization Software | Refresh `t1-003` canonical |
| Aug 8 | Governed AI-Assisted Campaign Workflows | Refresh `t3-001` canonical |
| Aug 10 | What Is a Signal-Driven Marketing Platform? | New `t2-001` definition |
| Aug 16 | DSRs for Buying Committees | Refresh `t1-006` canonical |
| Aug 22 | Deal Enablement Platform vs DSR | Refresh `t1-007` canonical |

These are proposed swaps, not authorized calendar edits. If the evidence gate is not ready by a candidate date, keep the live calendar intact and move the remediation package to the next review slot. Displaced topics move into the September draft; they are not discarded.

## Workstream 4: Resolve domain architecture without a migration

### Current decision

Keep `https://www.folloze-blog.com` as the sole canonical publication. A separate root domain maintains its own sitemap; Folloze.com sitemap access is unnecessary.

Actions Trey controls:

1. Declare `www.folloze-blog.com` the canonical system of record in configuration and operating docs.
2. Remove dormant `insights.folloze.com` references from non-generated assets and tests.
3. Generate robots and sitemaps from `config.site.origin` as the single source of truth.
4. Verify Search Console for `folloze-blog.com` and submit its own sitemaps.
5. Add stable `WebSite` or `Blog`, `Organization`, `Person`, and `isPartOf` entity relationships.
6. Confirm that the publication is authorized to represent itself as published by Folloze. If not, identify the actual operator in the disclosure.
7. Refresh controlled-site legacy positioning without waiting for Folloze.com edits.

Do not publish on two domains. Do not migrate until there is a business reason, a complete URL map, 90 days of baseline data, both GSC properties, analytics on the new host, and direct one-hop redirects for every old URL.

## Workstream 5: Build authority without Folloze.com edit access

Replace the old dependency “pass authority from Folloze.com” with a controlled-site program:

1. Build four topic hubs:

   - Personalization
   - Digital sales rooms
   - AI-assisted campaign execution
   - ABM/ABX and buying groups

2. Give every priority page at least three contextual internal inbound links.
3. Eliminate orphan pages and keep crawl depth at three clicks or fewer.
4. Link out to relevant Folloze product, help, integration, and customer-proof pages when they support the claim.
5. Add visible sourcing methodology, corrections policy, commercial disclosure, author credentials, and real update history.
6. Publish a transparent Folloze AI-visibility benchmark with methodology and downloadable summaries as the primary linkable asset.

Optional corporate request, not a blocker:

- One permanent contextual link from a relevant Folloze.com resource or research page to the Insights publication or benchmark.
- No Folloze.com sitemap change is required.

## Workstream 6: Build backlinks and third-party authority

Start with a verified baseline, then run a 90-day acquisition program.

1. Partner and integration resources: 6sense, Demandbase, Marketo, Salesforce, HubSpot, LeanData, ZoomInfo, and Segment.
2. Customer evidence: co-authored stories, attributable expert quotes, and customer-hosted references.
3. Editorial distribution: B2B marketing newsletters, podcasts, webinars, and guest analysis linking to specific research pages.
4. Entity and review presence: accurate G2, TrustRadius, Capterra, LinkedIn, YouTube, and partner-directory profiles where authorized.
5. Original research: one transparent, repeatable benchmark per quarter, including methodology, sample size, time window, limitations, and data-source description.

Initial 90-day targets:

- 10 new qualified referring domains
- 5 links to gap pages or research assets
- 3 partner/customer-hosted links
- 2 editorial, podcast, webinar, or newsletter links
- zero purchased links, link farms, mass-directory submissions, or artificial sitewide exchanges

## Implementation sequence

### Phase 0: Access and baseline, 1–3 days

- Verify `folloze-blog.com` GSC property.
- Inventory GA4 properties/streams and add the controlled-domain stream if missing.
- Grant the reporting service account GSC and GA4 read access.
- Capture manual GSC, GA4, GSC Links/Bing, and available Semrush/Ahrefs baselines.
- Record all properties in the owned-property registry.

**Exit:** one authenticated GSC pull and one authenticated GA4 pull for the controlled domain.

### Phase 1: Measurement semantics and native citations, 3–5 days

- Add parser v2 contracts and provider fixtures.
- Fix mention/citation classification.
- Add provider-native citation extraction.
- Version historical data and report v1 separately.
- Add normalized AI observation export.

**Exit:** a fixture containing “Folloze” without a Folloze citation URL records a mention and zero linked citations; provider-native Folloze URLs are preserved exactly.

### Phase 2: Cross-source reporting, 3–5 days

- Extend GSC/GA4 connector grain and property support.
- Ingest AI observations and backlink snapshots into the reporting platform.
- Build daily facts and weekly/28-day marts.
- Replace the weekly email with v2 coverage and trend reporting.

**Exit:** one weekly report contains nonempty, source-labeled GSC, GA4, AI mention, linked-citation, and backlink sections with run counts and freshness.

### Phase 3: Source-quality gate, 4–7 days

- Add proof registry, evidence contracts, deterministic sources rendering, artifact provenance, and blocking tests.
- Run the published-evidence audit from a stable snapshot.

**Exit:** no release artifact can be created with an unsupported material claim or a score above 100.

### Phase 4: Gap package and controlled-site authority, 5–10 days

- Prepare two new pages and four canonical refreshes as review artifacts.
- Build topic hubs and internal-link manifests.
- Capture pre-change measurements.

**Exit:** all six packages are evidence-ready, canonically distinct, internally linked, and unpublished pending approval.

### Phase 5: Backlink and third-party program, ongoing 90 days

- Publish the benchmark only after evidence and methodology review.
- Execute partner, customer, editorial, and directory/profile work.
- Verify links weekly and report new/lost qualified domains.

## Control and dependency matrix

| Item | Trey controls | One-time access needed | Corporate dependency |
|---|---:|---:|---:|
| `folloze-blog.com` GSC property | Yes | DNS verification | No |
| `folloze-blog.com` GA4 tag/stream | Yes | GA4 property role | No |
| GSC/GA4 reporting connectors | Yes | Service-account grants | No |
| AI provider citations | Yes | Provider keys/accounts | No |
| Backlink CSV baseline | Yes | Tool exports | No |
| Backlink API automation | Yes | Paid/API entitlement | No |
| Content evidence gate and refreshes | Yes | Approved proof sources | Some proof approval may be needed |
| Controlled-domain hubs and internal links | Yes | None | No |
| Folloze.com content, sitemap, schema, or navigation | No | N/A | Yes; excluded from critical path |
| One Folloze.com backlink | No | N/A | Optional request |
| `insights.folloze.com` migration | No under current access | DNS and hosting delegation | Yes; deferred |

## Acceptance criteria

### Measurement

- Mention and linked-citation rates are separately defined and separately stored.
- A linked citation requires provider-native evidence containing a Folloze-controlled URL.
- All raw responses and citation metadata are traceable by run, provider, prompt, parser version, and timestamp.
- API-grounded and consumer-surface results are never blended without labels.
- GSC and GA4 pulls work for every owned property in the registry.
- Google generative-AI reporting shows `available`, `not_available`, or `error`; it never silently reports unavailable data as zero.
- GA4 reports known AI referral sources and preserves unknown/direct traffic separately.
- Weekly trends include numerator, denominator, run count, source freshness, and 7/28/90-day windows.
- Historical v1 data remains intact and visibly non-comparable to citation v2.

### Source quality and content

- Every material claim maps to a public source or approved proof ID.
- No evidence or quality score exceeds 100.
- No release artifact exists unless evidence status is `ready`.
- Existing canonical URLs remain unchanged during refreshes.
- The six priority work packages have exact query-matching answer blocks, linked evidence, internal-link manifests, and pre-change baselines.
- No new page competes with an existing canonical for the same intent.

### Domain and authority

- Every indexable page self-canonicalizes to `www.folloze-blog.com`.
- Generated robots, sitemap, and canonical URLs agree with the configured origin.
- Zero generated `insights.folloze.com` references remain.
- The bare domain and preview host redirect to the canonical host in one hop.
- Four controlled-domain topic hubs exist, with zero orphan priority pages.
- Backlink reporting tracks new/lost links and referring domains without mixing provider-specific authority scores.

## AEO review

**Status:** `unsupported`

### Claim-source matrix

| Claim | Status |
|---|---|
| The existing monitor measures true citations | Unsupported; it currently promotes mentions to citations |
| GSC and GA4 architecture is missing | Unsupported; connectors already exist but access and property activation are blocked |
| GSC and GA4 currently measure the controlled publication | Unsupported; only corporate GSC access was confirmed and no Insights GA4 tag was found |
| A two-domain duplicate-content split exists | Unsupported; only `www.folloze-blog.com` serves the publication |
| Folloze.com sitemap access is required | Unsupported; an independent root domain submits its own sitemap |
| Five non-branded gaps require five new pages | Unsupported; four intents already have suitable canonicals to refresh |
| Measurement and authority work can proceed without Folloze.com edit access | Supported |

### Missing evidence

- Verified GSC ownership and API access for every controlled domain
- Verified GA4 property/stream IDs and production events for every controlled domain
- Service-account access to both Google properties
- Provider-native citation fixtures from every selected AI surface
- Search Console generative-AI report availability for the controlled property
- Current GSC Links/Bing/Semrush/Ahrefs backlink baseline
- Public approved proof URLs for customer outcomes and product claims
- Corporate authorization for the publication's Folloze publisher representation

### Fix pack

- **Claim:** “Citation rate is 27%.”
  **Issue:** A brand mention is currently counted as a citation.
  **Fix:** Relabel historical results as mention rate and require provider-native Folloze URLs for citation v2.

- **Claim:** “We already have GSC and GA4 for these sites.”
  **Issue:** Account access exists, but property coverage for the controlled publication is not verified and the live publication has no GA4 tag.
  **Fix:** Inventory properties, verify `folloze-blog.com`, add the GA4 stream/tag, grant service-account access, and validate API pulls.

- **Claim:** “We need Folloze.com sitemap access to fix authority.”
  **Issue:** Independent domains maintain independent sitemaps.
  **Fix:** Submit the controlled publication's own sitemaps; treat one corporate backlink as optional.

- **Claim:** “We should create five new gap articles.”
  **Issue:** That would duplicate existing search intent for four monitored gaps.
  **Fix:** Create two new canonicals and refresh four existing canonicals with evidence and exact answer blocks.

- **Claim:** “The source gate protects us from unsupported claims.”
  **Issue:** It counts attribution phrasing and discards source metadata.
  **Fix:** Implement claim-level evidence records, deterministic citation rendering, and a blocking evidence status.
