# Issue tracker: GitHub

Issues and specs for this repository live as GitHub Issues. Use the `gh` CLI for all operations. The repository is inferred from the configured Git remote (`Jonhow324/Imagenia`).

## Conventions

- **Create an issue:** `gh issue create --title "..." --body "..."`
- **Read an issue:** `gh issue view <number> --comments`
- **List issues:** `gh issue list --state open --json number,title,body,labels,comments`
- **Comment:** `gh issue comment <number> --body "..."`
- **Apply or remove labels:** `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close:** `gh issue close <number> --comment "..."`

When a skill says to publish to the issue tracker, create a GitHub Issue. When it says to fetch a ticket, use `gh issue view <number> --comments`.

## Pull requests as a triage surface

**PRs as a request surface: no.** Pull requests are not triaged as incoming feature requests in this repository.

## Dependencies and blocking

Prefer GitHub native issue dependencies when available. If they are unavailable, include a `Blocked by: #<number>` line at the top of the issue body. A ticket is ready when all blocking issues are closed.
