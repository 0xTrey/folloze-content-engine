# Migration To Webflow V2

## Principle

The upstream pipeline stays the same. Only the delivery target changes.

## Mapping

- `title` -> `name`
- `slug` -> `slug`
- `content_type` -> `content-type`
- `body_html` -> `body`
- `meta_title` -> `meta-title`
- `meta_description` -> `meta-description`
- `json_ld` -> `json-ld`
- `target_keywords` -> `target-keywords`
- `published_date` -> `published-date`
- `citation_score` -> `citation-score`
- `word_count` -> `word-count`

## Guardrails

- Preserve canonical URL behavior
- Preserve JSON-LD exactly
- Do not move generation logic into the delivery layer
- Keep logs and run artifacts available during migration

