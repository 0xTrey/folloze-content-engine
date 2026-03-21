# Automation

## Daily publish job

The daily publishing entrypoint is `scripts/run_daily_publish.py`. It runs the full happy path:

1. `python pipeline.py`
2. promote the generated artifact
3. export the Vercel prebuilt bundle
4. deploy to Vercel production
5. verify the live route against the artifact
6. send the published notification to Discord and email

The LaunchAgent plist for macOS lives at `launchd/com.folloze.content-engine.daily.plist` and is scheduled for 9:05 AM local time.

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

1. Copy `launchd/com.folloze.content-engine.daily.plist` to `~/Library/LaunchAgents/`
2. Run `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.folloze.content-engine.daily.plist` if it is already loaded
3. Run `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.folloze.content-engine.daily.plist`
4. Confirm with `launchctl print gui/$(id -u)/com.folloze.content-engine.daily`

## Logs

- Workflow log: `logs/daily-publish.log`
- launchd stdout: `logs/launchagent.log`
- launchd stderr: `logs/launchagent-error.log`
- Run artifacts: `logs/runs/YYYY-MM-DD/`
- Deploy events: `logs/deployments.jsonl`
- AgentMail poller stdout: `~/.openclaw/workspace/skills/agentmail/logs/juno-discord-poller.log`
- AgentMail poller stderr: `~/.openclaw/workspace/skills/agentmail/logs/juno-discord-poller-error.log`
- AgentMail webhook stdout: `~/.openclaw/workspace/skills/agentmail/logs/webhook-server.log`
- AgentMail webhook stderr: `~/.openclaw/workspace/skills/agentmail/logs/webhook-server-error.log`
