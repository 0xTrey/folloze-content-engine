# Folloze Content Engine Customer Brief

## Board identity

- Save intent: net-new Folloze board creation
- Board name: `Folloze Content Engine | ABM + GEO Customer Walkthrough`
- Vendor: Folloze
- Audience: Folloze customer conversation, reusable one-to-many product/workbench motion
- Local source: `/Users/treyharnden/Projects/folloze-content-engine/docs/folloze-content-engine-customer-brief.html`
- Source PDF: `/Users/treyharnden/Desktop/folloze-content-engine-customer-walkthrough.pdf`
- Board ID: `247800`
- Designer URL: `https://app.folloze.com/app/board/247800/designer`
- Folloze save status: created successfully through production Folloze MCP on 2026-07-16
- Public deployment URL: pending; MCP returned only the signed-in designer URL
- Public verification: an anonymous request to the designer URL redirected to the Folloze app root; no anonymous public board URL is currently available for verification
- Tracker status: first-create record written and verified in `Demo Environments!A104:H104` on 2026-07-16

## Holistic buyer goal

Help a customer understand how a governed content workflow turns buyer questions into research-backed ABM articles, ships them with SEO/GEO structure, and learns from search, AI visibility, and engagement signals.

## Message spine

- Buyer priority: publish credible ABM content consistently and improve visibility in search and AI answers.
- Why change: ad hoc publishing does not create a repeatable, measurable answer library.
- Why now: AI increases content speed, but customers still need product truth, governance, release quality, and measurement.
- Folloze promise: a repeatable content engine can connect strategy inputs, research, generation, quality, publishing, and learning.
- Proof: 116 published artifacts; 30 of 30 recent runs passed; 96 average composite score; 86 average GEO score.
- Next action: map the customer's priority themes, approved sources, Search Console baseline, and AI prompt panel.

## Experience shape

- Shape: product/workbench with narrative workflow
- First viewport: customer questions to AI-citable ABM content
- Section order: engine walkthrough, operating controls, operational visibility metrics, measurement loop, customer inputs, planning CTA
- Navigation: shell-safe scroll buttons, no hash links
- Theme mode: `no`, explicitly confirmed by Trey; the Folloze MCP theme tool was called with `use_folloze_theme: "no"` on 2026-07-16
- Theme ID: `4`
- Required theme URL: `https://cdn.folloze.com/theme/135433/4.css?v=1764160175`

## Source and QA state

- Folloze brand source: bundled Folloze Brand Kit plus current Folloze homepage patterns
- Metrics source: `site/published/index.json` and latest 30 `logs/runs/*/quality-report.json` files
- Local desktop QA: passed at 1383 x 1260 on 2026-07-16 after the final annotation pass
- Local mobile QA: passed at 500 x 900 and 320 x 800 on 2026-07-16 with no horizontal overflow
- Analytics pre-save check: external CTA safety and direct CTA analytics passed; stage tabs and shell-safe scroll interactions are tracked
- MCP creation guide: read on 2026-07-16
- Post-save local annotation pass on 2026-07-16: expanded the results headline to the full content rail and removed the five operational monitor rows so only the four measurement value cards remain. Board 247800 has not been repushed for this local-only pass.

## AI visibility evidence for the results section

- Do not use the emailed 23% to 29% or 9% to 11% rollup as an improvement claim. The April report crossed a schema change and defaulted missing new metric keys to zero.
- Comparable raw Perplexity rows: Apr 14-20 brand visibility/citation 27.5%, non-branded visibility 11.3%, share of voice 29.0%; May 14-20 brand visibility/citation 28.7%, non-branded visibility 10.8%, share of voice 20.8%.
- Comparable movement: +1.2 percentage points visibility, -0.5 points non-branded visibility, -8.2 points share of voice.
- The local database spans Apr 1-Jul 13, not six months. Comparable completed history is Perplexity-only from Apr 13-May 23. OpenAI, Claude, and Gemini support exists in current code, but later cross-provider runs are incomplete or dry-run data.
- Kristi's PromptWatch snapshot covered Jan 10-Apr 9, main domain, organic plus competitor-comparison prompts: 19% unbranded visibility. Sentiment was 81 brand-specific, 80 organic, and 62 competitor comparison.
- Kristi explicitly rejected a `20% to 31%` story because the higher figure mixed in branded prompts. Do not use it.
- Kristi's directional platform read: the clearest improvement was in ChatGPT; Perplexity and Copilot remained weaker. No later numeric per-provider series was found.
- A six-month provider-by-provider improvement chart is not currently defensible from available Slack, Gmail, or repo evidence. It requires a PromptWatch or Noble export.
- The customer page now uses a clearer like-for-like daily snapshot comparison from agent emails: Apr 20 to May 20 on the same internal 15-prompt Perplexity panel.
- The customer-facing visual labels this as a `30-Day Snapshot` with `Start` and `Day 30`; exact dates and source provenance remain in this internal evidence note rather than on the page.
- Apr 20 Juno snapshot: 27% visibility/citation, 50% sentiment, 10% non-branded visibility, 27% share of voice.
- May 20 Hermes AgentMail verification: 29% visibility/citation, 68% sentiment, 12% non-branded visibility, 20% share of voice.
- Defensible first-month story: visibility +2 points, sentiment +18 points, and non-branded visibility +2 points; share of voice fell 7 points and is explicitly shown as the next gap.
- Kristi's reply in the Apr 21 thread validated the fixed-prompt methodology and its role alongside PromptWatch, while reinforcing that branded, organic, competitor, and provider coverage must remain distinct.

## Current weekly monitor state

- The installed LaunchAgent runs Mondays at 10:00 PM local time from `launchd/com.folloze.content-engine.citation-monitor.plist`.
- The unattended wrapper defaults to Perplexity and Gemini, the two provider paths verified healthy on 2026-07-15. OpenAI remains blocked by insufficient quota and Claude lacks a local Anthropic key.
- Run 45 completed on 2026-07-15 with 15 prompts, five variants per prompt, two providers, 150 of 150 checks, and zero final-run failures.
- Both Perplexity and Gemini measured 26.7% visibility/citation, 100% branded visibility, and 8.3% non-branded visibility. The combined share of voice was 21.2% and sentiment was 72.5%.
- Today’s Perplexity result does not support a new improvement claim. The customer page uses the comparable Apr 20 to May 20 daily snapshots and presents them externally as a `30-Day Snapshot`.
