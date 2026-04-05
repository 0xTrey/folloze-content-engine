# Folloze Content Engine

Folloze Content Engine is a Python-based AEO content pipeline that generates, repairs, publishes, and verifies Folloze Insights content on a daily schedule.

## What it does

- pulls the next pending topic from `content/calendar.yaml`
- carries `topic.notes` into research and prompt generation so product marketing guidance, emotional territory, link priorities, and platform-specific optimization survive the pipeline
- enriches it with research
- generates content with Gemini
- optimizes HTML and JSON-LD
- scores quality and brand fit
- writes release artifacts and preview HTML
- publishes a machine-readable same-day social brief at `/social-briefs/latest.json` for downstream distribution systems
- auto-promotes, deploys, and verifies the daily publish flow through `scripts/run_daily_publish.py`
- runs an 8:45 AM canary through `scripts/run_publish_canary.py` to verify the post is live, recover missed publishes, and write an incident report when the morning job fails

## Setup

1. Create and activate a Python 3.12 environment.
2. Install with `pip install -e ".[dev]"`.
3. Export the env vars from `.env.example`, or rely on the macOS Keychain service names documented in `docs/ENVIRONMENT.md`.
4. Confirm `config.yaml` values.

## Commands

- `python pipeline.py`
- `python pipeline.py --dry-run`
- `python scripts/run_daily_publish.py`
- `python scripts/promote-artifact.py --artifact logs/runs/YYYY-MM-DD/release-artifact.json`
- `python scripts/build-site.py`
- `python scripts/export-vercel.py`
- `python scripts/verify-deploy.py --artifact logs/runs/YYYY-MM-DD/release-artifact.json --target preview`

## Structure

- pipeline modules live at repo root
- topic scheduling and operator guidance live in `content/calendar.yaml`
- content prompts in `content/templates/`
- JSON-LD templates in `schema/`
- published artifacts in `site/published/`
- static output in `site/dist/`
- Vercel prebuilt output in `.vercel/output/`
- deploy and promotion logs in `logs/deployments.jsonl` and `logs/promotions.jsonl`

## Development log

- 2026-03-20: initial Gemini-only, Vercel-first build scaffold
- 2026-04-05: calendar strategy refocused around buyer-intent clusters, integration pages, and tighter answer-engine definitions
