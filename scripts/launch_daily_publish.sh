#!/bin/zsh
# Wrapper for com.folloze.content-engine.daily LaunchAgent.
# Sources ~/.zshrc so API keys exported from Keychain are available to Python.
[[ -f "$HOME/.zshrc" ]] && source "$HOME/.zshrc" 2>/dev/null
export PYTHONPATH="$HOME/Projects/llm-gateway${PYTHONPATH:+:$PYTHONPATH}"

# Emit a one-line key-presence audit to stderr (goes to launchagent-error.log).
# Values are never logged — only whether each var is set or missing.
echo "[launch_daily_publish] keychain audit: GEMINI=${GEMINI_API_KEY:+set} DEEPSEEK=${AI_DEEPSEEK_KEY:+set} OPENAI=${AI_OPENAI_KEY:+set} MINIMAX=${AI_MINIMAX_KEY:+set} BRAVE=${BRAVE_API_KEY:+set}" >&2

exec "$HOME/Projects/folloze-content-engine/.venv/bin/python" \
    "$HOME/Projects/folloze-content-engine/scripts/run_daily_publish.py" "$@"
