# Folloze Controlled-Domain Authority Campaign

**Prepared:** 2026-08-04
**Campaign window:** 2026-08-04 through 2026-11-02
**Status:** Review only; no outreach, profile edits, content publication, or Folloze.com changes are authorized
**Controlled targets:** `www.folloze-blog.com` and `www.folloze-abm.com`

## Goal

Earn independently hosted, contextually relevant links and entity references to the two controlled Folloze publications while preserving a clean weekly backlink baseline for the reporting platform.

The 90-day outcome target is:

- 10 new qualified referring domains;
- at least 5 live links to persistent-gap pages or an approved research asset;
- at least 3 partner- or customer-hosted links;
- at least 2 editorial, webinar, podcast, or newsletter links; and
- zero purchased links, link farms, mass-directory submissions, artificial sitewide exchanges, or messages sent before review.

## Launch artifacts

- Campaign tracker: `docs/campaigns/assets/authority-campaign-tracker-2026-08-04.csv`
- Vendor-neutral reporting template: `docs/campaigns/assets/backlink-baseline-template.csv`
- Review-only message briefs: `docs/campaigns/2026-08-04-authority-message-briefs.md`
- Measurement and remediation plan: `docs/plans/2026-08-04-geo-measurement-and-authority-remediation.md`

## Operating sequence

### Days 0–14: baseline and approval

1. Export current links for both controlled domains from the available provider.
2. Normalize the export into `backlink-baseline-template.csv`.
3. Record the provider name exactly; do not convert provider-specific authority scores into a synthetic cross-provider score.
4. Review every proposed target asset for evidence readiness, current product facts, working URLs, and commercial disclosure.
5. Resolve the owner and approval dependency for each campaign row.
6. Keep every motion in `draft_review` or a `blocked_on_*` state.

### Days 15–30: partner and profile review wave

1. Prioritize partner resources tied to live, practical joint-workflow pages.
2. Route marketplace and directory changes to the authorized listing owner.
3. Do not replace the official Folloze.com website field with a controlled publication URL.
4. Approve a message only when the target asset and all vendor claims pass review.

### Days 31–60: customer and editorial review wave

1. Require written approval for every named customer outcome, quotation, logo, or customer-hosted story.
2. Do not pitch the proposed AI-visibility benchmark until it is published, evidence-ready, and accompanied by public methodology and limitations.
3. Keep editorial pitches educational and data-led; an editor must independently decide whether to cover or link to the work.

### Days 61–90: verification and second wave

1. Recheck every approved placement weekly.
2. Record live links in the reporting CSV only after the source and target both return 200.
3. Classify social, sponsored, UGC, and nofollow links accurately rather than counting every mention as a qualified backlink.
4. Compare new and lost referring domains by controlled target domain.
5. Close or re-plan any campaign that cannot pass the acceptance checks without stretching a claim.

## Status contract

| Status | Meaning |
|---|---|
| `draft_review` | Target and brief are prepared; no contact has occurred |
| `blocked_on_product_confirmation` | Current integration or product facts must be confirmed |
| `blocked_on_evidence` | Customer proof or claim support is not yet approved |
| `blocked_on_unpublished_asset` | The intended linkable asset is not live and must not be pitched |
| `blocked_on_account_owner` | An authorized external-profile or marketplace owner is required |
| `approved_to_contact` | Human reviewer has approved the exact recipient, message, and asset |
| `contacted` | A human has sent an approved message; this plan does not set this state |
| `live_verified` | The source page and target page are live and the link has been recorded |
| `closed_no_link` | Motion ended without a live link |

No automation may move a row to `approved_to_contact`, `contacted`, or `live_verified`.

## Qualified-link acceptance

A link counts as a qualified referring-domain result only when:

1. the source is independently hosted and topically relevant;
2. the source page and controlled target URL both return 200;
3. the link is visible, contextual, and accurately describes the target;
4. the placement is not purchased, part of a link scheme, or an artificial sitewide exchange;
5. `link_type` accurately records `follow`, `nofollow`, `sponsored`, `ugc`, or `unknown`;
6. the source domain has not already been counted as a new qualified referring domain in the same campaign window; and
7. the row is captured in the weekly backlink snapshot used by the reporting connector.

Social and directory links may support discovery and entity consistency without qualifying as followed backlinks. Report those outcomes separately.

## Reporting CSV contract

The baseline template intentionally matches the reporting platform's vendor-neutral importer:

| Column | Requirement | Notes |
|---|---|---|
| `source_url` | Required | Full referring-page URL |
| `target_url` | Required | Full URL on a controlled target domain |
| `anchor_text` | Optional | Preserve the source wording exactly |
| `authority_score` | Optional | Keep the provider-specific score; do not normalize it |
| `link_type` | Optional | `follow`, `nofollow`, `sponsored`, `ugc`, or `unknown` |
| `first_seen` | Optional | ISO date `YYYY-MM-DD` |
| `last_seen` | Optional | ISO date `YYYY-MM-DD` |
| `provider` | Optional but expected | For example `gsc`, `bing`, `ahrefs`, `semrush`, or `manual_verified` |

`source_domain`, `target_domain`, and the snapshot date are derived by the reporting connector. Use one snapshot file per reporting run. A header-only file is the safe empty template and loads as zero records.

## Review gates

Before any outreach is approved:

- the target page is live and evidence-ready;
- the exact joint-product or customer claim is supported;
- the authorized sender and recipient role are identified;
- any corporate profile or marketplace owner has approved the change;
- the ask is for editorial usefulness, not a link exchange; and
- the draft has no unsupported rankings, performance claims, endorsements, or implied partnerships.

## Weekly review

Every Monday:

1. Re-import the latest vendor or manual export through `rp sync backlinks snapshot` in the reporting platform.
2. Compare live links with the tracker and mark losses without deleting prior history.
3. Review rows whose `next_review_date` is due.
4. Report outcomes by controlled domain, motion, link type, and referring domain.
5. Keep mentions, AI citations, AI referrals, and backlinks as separate metric families.

## Boundaries

- Do not send any message from these briefs without explicit approval.
- Do not edit Folloze.com, its sitemap, or its profiles.
- Do not publish the proposed benchmark as part of this campaign setup.
- Do not overwrite current articles; any evidence repair remains a separate review package.
- Do not treat a directory listing, social mention, or unlinked brand mention as a qualified backlink.
