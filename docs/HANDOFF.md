# Handoff

## System overview

- Python pipeline generates release artifacts.
- Approved artifacts are promoted into `site/published`.
- `scripts/build-site.py` renders a static bundle into `site/dist`.
- `scripts/export-vercel.py` copies the bundle into `.vercel/output/`.
- Vercel serves the prebuilt bundle.

## Required environment variables

- `BRAVE_API_KEY`
- `PERPLEXITY_API_KEY`
- `GEMINI_API_KEY`
- `SMTP_PASSWORD`

## Key paths

- Config: `config.yaml`
- Calendar: `content/calendar.yaml`
- Run artifacts: `logs/runs/YYYY-MM-DD/`
- Structured run events: `logs/runs/YYYY-MM-DD/run-events.jsonl`
- Published artifacts: `site/published/`
- Static output: `site/dist/`
- Deployment manifest: `site/dist/deployment-manifest.json`
- Vercel prebuilt output: `.vercel/output/`
- Promotion log: `logs/promotions.jsonl`
- Deploy log: `logs/deployments.jsonl`

## Common recovery steps

- Missing email: check `SMTP_PASSWORD` and `logs/content-engine.log`
- Missing JSON-LD: inspect `release-artifact.json` and rerun `python scripts/build-site.py`
- Bad live page: compare `site/dist/` to the promoted artifact and rerun `python scripts/verify-deploy.py`
- Wrong domain alias: inspect the Vercel dashboard alias target and compare against `config.yaml`

## Marketing and web-dev handoff

- Marketing team operates the calendar and release approvals.
- Web dev team owns the Vercel project, DNS, domain aliasing, and the V2 Webflow migration.
- Use `docs/MIGRATION_TO_WEBFLOW_V2.md` to map the release artifact fields into future Webflow CMS fields.
