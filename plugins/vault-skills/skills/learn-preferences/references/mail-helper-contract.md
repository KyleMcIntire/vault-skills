# Mail helper contract (optional `mail` source)

`collect.py` has no mail reader of its own. To enable the `mail` source, pass `--mail-script <path>` (or set `PREFS_MAIL_SCRIPT`) to a Python script that is read-only and speaks this interface. It is run as `python3 -I <script> ...`.

```text
<script> mail --mailbox "Sent Items" --since YYYY-MM-DD --limit 60
  -> JSON: {"messages": [{"message_id": "...", "subject": "...", "received": "<ISO 8601>", "outlook_link": "<url or null>"}]}

<script> message <message_id> --max-chars 4000
  -> JSON: {"body": "<plain text of the message>"}
```

If your mail setup differs, write a thin wrapper that adapts it to this shape. The collector drops quoted reply text, skips machine-made and sensitive subjects (automatic replies, benefits, payroll, medical, and similar), redacts token-like strings, and never records recipients. Without a helper the source reports one error and the other sources still run.
