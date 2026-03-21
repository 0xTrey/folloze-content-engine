# Folloze Content Engine

Folloze Content Engine is a Python-based AEO content pipeline that generates release-ready artifacts and renders a static Insights site bundle for Vercel validation.

## What it does

- pulls a topic from `content/calendar.yaml`
- enriches it with research
- generates content with Gemini
- optimizes HTML and JSON-LD
- scores quality and brand fit
- writes release artifacts and preview HTML
- supports manual promotion into the static site bundle

## Setup

1. Create and activate a Python 3.12 environment.
2. Install with `pip install -e ".[dev]"`.
3. Export the env vars from `.env.example`, or rely on the macOS Keychain service names documented in `docs/ENVIRONMENT.md`.
4. Confirm `config.yaml` values.

## Commands

- `python pipeline.py`
- `python pipeline.py --dry-run`
- `python scripts/promote-artifact.py --artifact logs/runs/YYYY-MM-DD/release-artifact.json`
- `python scripts/build-site.py`
- `python scripts/export-vercel.py`
- `python scripts/verify-deploy.py --artifact logs/runs/YYYY-MM-DD/release-artifact.json --target preview`

## Structure

- pipeline modules live at repo root
- content prompts in `content/templates/`
- JSON-LD templates in `schema/`
- published artifacts in `site/published/`
- static output in `site/dist/`
- Vercel prebuilt output in `.vercel/output/`
- deploy and promotion logs in `logs/deployments.jsonl` and `logs/promotions.jsonl`

## Development log

- 2026-03-20: initial Gemini-only, Vercel-first build scaffold
