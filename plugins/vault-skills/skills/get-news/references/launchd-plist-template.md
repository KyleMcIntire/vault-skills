# Daily digest with launchd (macOS, optional)

The skill runs on demand. To produce a digest every morning, run Claude Code headless from a small wrapper
script, scheduled by a LaunchAgent. Replace every `<PLACEHOLDER>`; nothing here is filled in for you.

## 1. Wrapper script `<BIN_DIR>/run-get-news` (make it executable)

```bash
#!/bin/bash
set -euo pipefail
cd "<VAULT_PATH>"
# Narrow allowlist: the script, reading and writing notes under the news folder, web fetches, Slack reads if you use them.
claude -p "/vault-skills:get-news" \
  --allowedTools "Bash(python3 -I *get-news/fetch_news.py*)" "Read" "Write" "Edit" "WebFetch" \
  >> "<LOG_DIR>/get-news.log" 2>> "<LOG_DIR>/get-news.err"
```

Note: a headless run cannot answer questions. Put the weather location, feeds and pins in `.vault-skills.yaml`
beforehand so the skill never needs to ask.

## 2. LaunchAgent `~/Library/LaunchAgents/<LABEL>.plist`

`<LABEL>` is a reverse-DNS name you choose, for example `com.example.get-news`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string><LABEL></string>
  <key>ProgramArguments</key>
  <array><string><BIN_DIR>/run-get-news</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>0</integer></dict>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string></dict>
</dict>
</plist>
```

## 3. Load, test, unload

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/<LABEL>.plist
launchctl kickstart gui/$(id -u)/<LABEL>          # run once now; then read <LOG_DIR>/get-news.log
launchctl bootout gui/$(id -u)/<LABEL>            # stop scheduling
```

A Mac that is asleep at the scheduled time runs the job when it wakes. Logs and the plist live outside the vault.
