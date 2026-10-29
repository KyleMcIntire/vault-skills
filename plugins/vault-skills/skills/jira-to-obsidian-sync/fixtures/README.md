Offline test for `jira_acli.py` using a fictional `acli` stand-in:

    python3 -I jira_acli.py --site acme.invalid --acli fixtures/bin/acli search 'assignee = currentUser()'
    python3 -I jira_acli.py --site acme.invalid --acli fixtures/bin/acli issue ABC-1

Without `JIRA_TOKEN`, `web_links` and `prs` report an error object; everything else works.
