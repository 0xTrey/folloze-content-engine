# Persistent-gap evidence remediation plan

Status: review only. No calendar entry, published artifact, canonical, or live page was changed.

## Outcome

The six persistent monitor prompts resolve to two new pages and four canonical refreshes. The source and brief package is stored in `content/review-only/persistent-gap-evidence-packs-2026-08.yaml` and is intentionally outside the active publishing calendar.

| Prompt | Slot | Action | Canonical |
| --- | --- | --- | --- |
| `t1-001` | 2026-08-05 | New comparison | `https://www.folloze-blog.com/insights/best-ai-marketing-platforms-for-b2b` |
| `t1-003` | 2026-08-07 | Refresh | `https://www.folloze-blog.com/insights/how-to-personalize-content-for-different-accounts-without-hiring-more-people` |
| `t3-001` | 2026-08-08 | Refresh | `https://www.folloze-blog.com/insights/how-one-marketer-can-run-enterprise-campaigns-with-folloze` |
| `t2-001` | 2026-08-10 | New glossary | `https://www.folloze-blog.com/insights/what-is-individual-level-personalization-in-b2b-marketing` |
| `t1-006` | 2026-08-16 | Refresh | `https://www.folloze-blog.com/insights/digital-sales-rooms-for-b2b-revenue-teams` |
| `t1-007` | 2026-08-22 | Refresh | `https://www.folloze-blog.com/insights/best-digital-sales-room-software-for-enterprise-revenue-teams` |

## Why four pages should be refreshed

- `t1-003` already has a close canonical about personalizing content without additional people. A second page about avoiding page rebuilds would compete for the same intent.
- `t3-001` already has a one-marketer enterprise-campaign canonical. The correct fix is a non-branded title, a segment workflow, and sourced evidence.
- `t1-006` already has the core DSR definition page. Its outdated AI-oriented title and unsupported evidence need repair, not a new definition URL.
- `t1-007` already has the exact enterprise DSR evaluation canonical. A new checklist is a supporting spoke only after the core page is repaired.

## Remediation batches

### Batch A1: new gap pages

Target review slots: August 5 and August 10.

1. `t1-001`: balanced AI marketing platform comparison using official Folloze, Mutiny, Demandbase, and 6sense product sources.
2. `t2-001`: vendor-neutral individual-level personalization definition using current Folloze, Demandbase, and 6sense sources.

These pages require a new canonical review because no current artifact owns the exact intent.

### Batch A2: same-canonical refreshes

Target review slots: August 7, 8, 16, and 22.

1. `t1-003`: scalable personalization operating model.
2. `t3-001`: lean-team AI-assisted campaign workflow.
3. `t1-006`: DSR definition and buyer-workspace model.
4. `t1-007`: criteria-led enterprise DSR comparison.

The refresh process must preserve each slug and `datePublished`, update `dateModified` only after approval, and remove or source every unsupported number, quote, and vendor claim.

### Batch B: remaining evaluation pages

After A1 and A2 pass review, audit the remaining comparison artifacts. Each vendor row must link to that vendor's current official page, and vendor-reported results must be labeled or omitted.

### Batch C: remaining unsupported proof

Prioritize pages with scores above 100, customer outcomes, named quotes, and legacy proof strings. A proof registry should map every reusable claim to a public URL and approval status before these pages are refreshed.

## Source rules used in the packs

- Official product pages, Help Center documentation, and first-party public customer stories only.
- AI summaries and search snippets may discover a source but cannot support a claim.
- Vendor pages support claims about that vendor; they do not support universal rankings.
- Every comparison cell must resolve to a cited official page.
- Quantified customer outcomes must be explicitly attributed and must not be generalized.

## Files created

- `content/review-only/persistent-gap-evidence-packs-2026-08.yaml`
- `scripts/validate_gap_evidence_packs.py`
- `tests/test_gap_evidence_packs.py`
- `docs/plans/2026-08-04-persistent-gap-evidence-remediation.md`

## Validation

Run structural and canonical validation:

```bash
.venv/bin/python scripts/validate_gap_evidence_packs.py
```

Run live URL checks:

```bash
.venv/bin/python scripts/validate_gap_evidence_packs.py --check-urls
```

Run the focused test:

```bash
.venv/bin/pytest tests/test_gap_evidence_packs.py -q
```

## Acceptance criteria

- Exactly six unique prompt IDs are present.
- Every pack remains `review_only`, with `calendar_action: none` and `publication_action: none`.
- New slugs do not exist in `site/published`; refresh slugs and canonicals match existing artifacts.
- Every answer-first block is 40 to 60 words.
- Every major claim maps to one or more source IDs in the same pack.
- Every source is an HTTPS official product, Help Center, vendor guide, or public customer-story URL checked on August 4, 2026.
- Every internal link resolves to an existing published artifact.
- The active `content/calendar.yaml` remains untouched.
- No existing artifact is altered and nothing is published.
