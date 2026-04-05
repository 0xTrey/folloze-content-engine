# Automation

## Daily publish job

The daily publishing entrypoint is `scripts/run_daily_publish.py`. It runs the full happy path:

1. `python pipeline.py`
2. promote the generated artifact
3. export the Vercel prebuilt bundle
4. deploy to Vercel production
5. verify the live route against the artifact
6. send the published notification to Discord and email

`config.yaml` now defaults to `delivery.release_mode: "auto"`, which means the normal production path is unattended. The standalone `pipeline.py` command still writes a release artifact, but it no longer sends a "release ready" review notification unless you explicitly switch back to `manual`.

The primary LaunchAgent plist for macOS lives at `launchd/com.folloze.content-engine.daily.plist` and is scheduled for 7:30 AM America/Chicago.

## 8:45 canary job

The recovery entrypoint is `scripts/run_publish_canary.py`. At 8:45 AM America/Chicago it:

1. checks whether a post published for today is actually live on production
2. inspects the latest run manifest, run events, and provider log lines if nothing is live
3. resumes an interrupted `release_ready` artifact or reruns the oldest overdue topic
4. writes an incident report to `logs/incidents/YYYY-MM-DD/`
5. sends a canary notification with the diagnosis, actions taken, and long-term fix recommendation

The canary LaunchAgent plist lives at `launchd/com.folloze.content-engine.canary.plist`.

## Social brief artifact

Every successful promotion now writes a machine-readable social brief for downstream distribution systems:

- `site/published/social-briefs/<slug>.json`
- `site/published/social-briefs/latest.json`
- `https://www.folloze-blog.com/social-briefs/latest.json`

That JSON artifact is the handoff contract for the LinkedIn content engine.

## Nightly citation monitor

The GEO citation monitor entrypoint is `scripts/run_citation_monitor.py`. It runs nightly at 10:00 PM local time and writes to the citation monitor SQLite database plus `logs/citation-monitor.log`.

The citation monitor LaunchAgent plist lives at `launchd/com.folloze.content-engine.citation-monitor.plist`.

## Required prerequisites

- Pending topics must exist in `content/calendar.yaml`
- Gemini, Brave, and Perplexity credentials must be available via env vars or macOS Keychain
- Vercel CLI must be installed and authenticated, or `VERCEL_TOKEN` must be available via env var or Keychain
- The project virtualenv must exist at `.venv`
- `config.yaml` must point to the active Vercel URLs
- Notifications post directly to the Juno Discord channel configured in `config.yaml`
- Email notifications use SMTP if `SMTP_PASSWORD` exists. Otherwise they fall back to Juno via AgentMail when `agentmail-api` is in Keychain.

## Notification routing

- Content-engine release, published, and error events post directly to Discord target `channel:1480677039169081434`
- The direct Discord path uses the local `openclaw` CLI and does not depend on SMTP
- Juno inbox mirroring runs through a separate AgentMail poller LaunchAgent every five minutes
- A local AgentMail webhook server is installed for future public webhook ingress, but it will only receive live webhooks once a public URL is pointed at the Mac

## Install on macOS

1. Run `scripts/setup-launchd.sh`
2. Confirm with `launchctl print gui/$(id -u)/com.folloze.content-engine.daily`
3. Confirm with `launchctl print gui/$(id -u)/com.folloze.content-engine.canary`
4. Confirm with `launchctl print gui/$(id -u)/com.folloze.content-engine.citation-monitor`

The old repo-root plist `com.folloze.content-engine.plist` is deprecated and should not be installed. `scripts/setup-launchd.sh` now removes that legacy LaunchAgent from `~/Library/LaunchAgents` before installing the current set.

## Logs

- Workflow log: `logs/daily-publish.log`
- Canary log: `logs/daily-publish-canary.log`
- launchd stdout: `logs/launchagent.log`
- launchd stderr: `logs/launchagent-error.log`
- canary stdout: `logs/launchagent-canary.log`
- canary stderr: `logs/launchagent-canary-error.log`
- citation monitor log: `logs/citation-monitor.log`
- citation monitor stderr: `logs/citation-monitor-error.log`
- Run artifacts: `logs/runs/YYYY-MM-DD/`
- Canary incidents: `logs/incidents/YYYY-MM-DD/`
- Deploy events: `logs/deployments.jsonl`
- AgentMail poller stdout: `~/.openclaw/workspace/skills/agentmail/logs/juno-discord-poller.log`
- AgentMail poller stderr: `~/.openclaw/workspace/skills/agentmail/logs/juno-discord-poller-error.log`
- AgentMail webhook stdout: `~/.openclaw/workspace/skills/agentmail/logs/webhook-server.log`
- AgentMail webhook stderr: `~/.openclaw/workspace/skills/agentmail/logs/webhook-server-error.log`
