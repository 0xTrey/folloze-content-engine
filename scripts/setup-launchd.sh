#!/bin/bash
set -euo pipefail

ROOT="${HOME}/Projects/folloze-content-engine"
AGENTS_DIR="${HOME}/Library/LaunchAgents"

mkdir -p "${ROOT}/logs" "${AGENTS_DIR}"

for plist in \
  "com.folloze.content-engine.daily.plist" \
  "com.folloze.content-engine.canary.plist"
do
  cp "${ROOT}/launchd/${plist}" "${AGENTS_DIR}/${plist}"
  launchctl bootout "gui/$(id -u)" "${AGENTS_DIR}/${plist}" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "${AGENTS_DIR}/${plist}"
done

echo "Installed Folloze daily publish + canary LaunchAgents."
echo "Check with:"
echo "  launchctl print gui/$(id -u)/com.folloze.content-engine.daily"
echo "  launchctl print gui/$(id -u)/com.folloze.content-engine.canary"
