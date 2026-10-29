# Running the learner on a schedule (optional)

An unattended run must be started by something outside Claude Code. Use a headless call with a narrow tool allowlist and a prompt that says nobody is watching, so the skill asks nothing, offers nothing, writes only the two profile notes and never touches memory.

Everything in angle brackets is a placeholder you fill in. Nothing here is a real path or account.

## Wrapper script `<HOME>/bin/run-learn-preferences`

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "<VAULT_PATH>"
export GITHUB_USER="<github-login>" GITHUB_ORG="<github-org>"
export JIRA_SITE="<site>.atlassian.net" JIRA_NAMES="<Display Name>"
claude -p "Run /vault-skills:learn-preferences. Unattended: nobody is watching. Ask nothing, offer nothing, write only the profile notes, never write memory." \
  --allowedTools "Read,Edit,Write,Bash(python3 -I <SKILL_DIR>/collect.py*),Bash(gh *),Bash(acli *)" \
  >> "<LOG_DIR>/learn-preferences.log" 2>&1
```

Adjust `--allowedTools` to the sources you enabled; add the Slack search and thread tools if you use the Slack source.

## macOS launchd: `<HOME>/Library/LaunchAgents/<reverse.domain>.learn-preferences.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string><reverse.domain>.learn-preferences</string>
  <key>ProgramArguments</key><array><string><HOME>/bin/run-learn-preferences</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>45</integer></dict>
  <key>StandardErrorPath</key><string><LOG_DIR>/learn-preferences.err</string>
</dict></plist>
```

Load it with `launchctl bootstrap gui/$(id -u) <that plist>`; unload with `launchctl bootout gui/$(id -u) <that plist>`.

## Linux cron

```cron
45 18 * * * <HOME>/bin/run-learn-preferences
```

The first run reads the look-back window (default 30 days) and is capped per source, so a busy history drains over several runs. Because the delta is stored as watermarks, a missed day just makes the next run larger.
