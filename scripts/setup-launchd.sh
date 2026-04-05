#!/bin/bash
set -euo pipefail

ROOT="${HOME}/Projects/folloze-content-engine"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
LEGACY_PLIST="${AGENTS_DIR}/com.folloze.content-engine.plist"

mkdir -p "${ROOT}/logs" "${AGENTS_DIR}"

if [ -f "${LEGACY_PLIST}" ]; then
  launchctl bootout "gui/$(id -u)" "${LEGACY_PLIST}" 2>/dev/null || true
  rm -f "${LEGACY_PLIST}"
  echo "Removed legacy LaunchAgent: com.folloze.content-engine.plist"
fi

for plist in \
  "com.folloze.content-engine.daily.plist" \
  "com.folloze.content-engine.canary.plist" \
  "com.folloze.content-engine.citation-monitor.plist"
do
  cp "${ROOT}/launchd/${plist}" "${AGENTS_DIR}/${plist}"
  launchctl bootout "gui/$(id -u)" "${AGENTS_DIR}/${plist}" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "${AGENTS_DIR}/${plist}"
done

echo "Installed Folloze daily publish, canary, and citation-monitor LaunchAgents."
echo "Check with:"
echo "  launchctl print gui/$(id -u)/com.folloze.content-engine.daily"
echo "  launchctl print gui/$(id -u)/com.folloze.content-engine.canary"
echo "  launchctl print gui/$(id -u)/com.folloze.content-engine.citation-monitor"
