# AI GitHub PR Reviewer

🚧 Work in progress.

An automated PR reviewer — analyzes diffs, leaves inline comments, flags bugs/security issues/style problems, and posts a summary review.

## Idea

Manual PR review misses things and doesn't scale. This bot runs multiple focused review passes (correctness, security, style, test coverage) over every PR diff, then posts findings back to GitHub as inline comments plus a summary verdict — configurable per repo.

## Planned Architecture

- **GitHub integration** — Action or App (TBD) reacting to PR events
- **Diff fetcher** — pulls the diff + surrounding file context via GitHub API
- **Review engine** — separate passes for bugs, security, style, and missing tests, each returning structured findings
- **Comment poster** — maps findings to GitHub inline comments + a summary comment
- **Config** — `.ai-reviewer.yml` per repo (enabled checks, severity threshold, ignored paths)

## Tech Stack

- Python, FastAPI
- PostgreSQL / SQLite
- Docker / docker-compose
- OpenAI + GitHub API

## Status

Currently deciding between GitHub Action and GitHub App integration, building out the review pass engine. Setup instructions, example review output, and eval results will be added as the project progresses.

## License

MIT