# Environment

## Required secrets

- `BRAVE_API_KEY`: Brave web search key for research grounding.
- `PERPLEXITY_API_KEY`: Perplexity key for secondary research synthesis.
- `GEMINI_API_KEY`: primary Gemini key used for research and first-pass generation.
- `AI_OPENAI_KEY`, `AI_DEEPSEEK_KEY`, `AI_GEMINI_KEY`, `AI_KIMI_KEY`, `AI_MINIMAX_KEY`: optional cloud fallback keys for `LLMGateway` when Gemini output is unusable.
- `SMTP_PASSWORD`: optional SMTP password for release and error emails.
- Local AgentMail CLI at `/Users/treyharnden/.openclaw/workspace/skills/agentmail/agentmail.py`: primary fallback notification path when SMTP is not configured.
- `agentmail-api` in macOS Keychain: AgentMail API credential for `juno@elevationengine.co` and inbox relay polling.

## macOS Keychain fallback

- `BRAVE_API_KEY` falls back to `brave-search-api`
- `PERPLEXITY_API_KEY` falls back to `perplexity-api`
- `GEMINI_API_KEY` falls back to `gemini-api` and then `gemini-api-key`
- `AI_GEMINI_KEY` falls back to `gemini-api` and then `gemini-api-key`
- `AI_OPENAI_KEY` falls back to `openai-api` and then `openai-api-key`
- `AI_DEEPSEEK_KEY` falls back to `deepseek-api`
- `AI_KIMI_KEY` falls back to `kimi-api`
- `AI_MINIMAX_KEY` falls back to `minimax-api`
- `SMTP_PASSWORD` falls back to `smtp-password`, `gmail-app-password`, and `gmail-smtp`
- Notification delivery falls back to AgentMail automatically when SMTP is not configured and the local AgentMail CLI is available.
- Cloudflare Email Sending must not be used for arbitrary stakeholder reports; it requires destination-recipient verification and is only suitable for explicitly enabled diagnostics/internal-agent transport.
- Discord notifications use `openclaw` directly and read the target channel from `config.yaml`

## Commit-safe configuration

- `config.yaml` holds site origin, preview URL, production URL, review mode, quality threshold, and scheduling defaults.
- `.env.example` is the operator template for local shells, launchd, or CI/CD runners.

## Ownership notes

- Trey owns the live Vercel project, domain alias, and DNS records in v1.
- Marketing reviewers only need artifact URLs, preview HTML, and notification emails.
- Web dev handoff should include the final `config.yaml`, `.env.example`, and the latest deploy log files.
- The local AgentMail webhook service is ready for future public ingress, but today the durable Juno relay is the five-minute poller because no public webhook endpoint is attached to this Mac.
