#!/bin/bash
set -euo pipefail

mkdir -p ~/Projects/folloze-content-engine/logs
cp ~/Projects/folloze-content-engine/com.folloze.content-engine.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.folloze.content-engine.plist
echo "Installed. Check with: launchctl list | grep folloze"

