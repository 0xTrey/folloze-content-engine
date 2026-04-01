# Operations

## Daily workflow

1. Run `python scripts/run_daily_publish.py` or let launchd run it.
2. Check `logs/runs/YYYY-MM-DD/run-manifest.json` for the pipeline status.
3. Check `logs/daily-publish.log` and `logs/deployments.jsonl` for promotion, deploy, and verification results.
4. If the job fails before promotion, inspect `logs/runs/YYYY-MM-DD/rendered-preview.html` and `quality-report.json`.
5. If the job fails after export or deploy, rerun `python scripts/run_daily_publish.py --date YYYY-MM-DD`.
6. If nothing is live by 9:15 AM, run `python scripts/run_publish_canary.py --date YYYY-MM-DD` or let the canary LaunchAgent recover it automatically.

## Calendar updates

- Edit `content/calendar.yaml`.
- Use `pending` for new topics.
- Use `release_ready` only when the pipeline sets it.
- Use `published` only after promotion.

## Logs

- Rolling log: `logs/content-engine.log`
- Daily publish log: `logs/daily-publish.log`
- Daily canary log: `logs/daily-publish-canary.log`
- Run artifacts: `logs/runs/YYYY-MM-DD/`
- Canary incidents: `logs/incidents/YYYY-MM-DD/`
- Structured run events: `logs/runs/YYYY-MM-DD/run-events.jsonl`
- Promotion log: `logs/promotions.jsonl`
- Deploy log: `logs/deployments.jsonl`
- launchd logs: `logs/launchagent.log`, `logs/launchagent-error.log`
- canary launchd logs: `logs/launchagent-canary.log`, `logs/launchagent-canary-error.log`

## Escalation

- Content or config issues: Trey
- Vercel deploy or domain issues: Trey or web dev team
