# Repository Guidelines

## Project Structure & Module Organization

The product is the Imagenia QwenPaw plugin in `plugin/`. Research and design notes live under `docs/`. Key paths are:

- `plugin/` — backend (`src/imagenia_plugin/`, `plugin.py`, `dev.py`), React workbench (`frontend/`), and tests.
- `docs/` — architecture, ADRs, and QwenPaw research. `docs/qwenpaw-plugin-development-research.md` is the Chinese-language plugin research note.
- `.agents/` and `.codex/` — agent configuration directories; treat them as tooling metadata unless a task explicitly targets them.

Add new research notes under `docs/` with kebab-case names (for example, `docs/plugin-security-review.md`). Keep plugin code self-contained under `plugin/` with `plugin.json`, backend entry point, dependencies, README, and tests.

## Build, Test, and Development Commands

Canonical install, launch, and test commands are in `plugin/README.md`. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r plugin/requirements-dev.txt
npm ci --prefix plugin/frontend
.venv/bin/python -m pytest plugin/tests -q
npm run build --prefix plugin/frontend
```

Local development uses two processes. The default backend is offline fake mode (no API key and no external image calls):

```bash
.venv/bin/python plugin/dev.py
npm run dev --prefix plugin/frontend
```

The API listens on `http://127.0.0.1:8765` and the workbench on `http://127.0.0.1:5173`, which proxies `/api/imagenia`. For documentation-only edits, check heading order with `grep -n '^#' docs/*.md`.

## Coding Style & Naming Conventions

Use UTF-8, LF line endings, and spaces rather than tabs. Keep Markdown paragraphs short, use fenced code blocks with language tags, and prefer tables only when they improve scanning. Preserve the existing document language within a file. Use kebab-case for documentation filenames and lowercase, hyphenated IDs in `plugin.json` (for example, `hello-tool`). Python examples should use four-space indentation, type annotations, concise docstrings, and relative imports inside plugin packages.

## Testing Guidelines

Documentation changes must be checked for accurate commands, valid JSON/Python examples, working internal links, and consistent heading levels. When plugin code is added, cover normal behavior, invalid input, missing configuration, external-service failures, install/upgrade/uninstall flows, and the minimum and latest supported QwenPaw versions. Name Python tests `test_<behavior>.py` and keep them under the relevant plugin's `tests/` directory.

## Commit & Pull Request Guidelines

Follow Conventional Commits: `docs: clarify version compatibility` or `feat: add hello tool example`. Keep commits focused. Pull requests should summarize the change, identify affected documents or plugins, list validation performed, and link related issues or source material. Include screenshots only for rendered UI or formatting changes when visual review helps.

## Security & Configuration Tips

Never commit credentials, tokens, personal paths, or production configuration. Use placeholders in examples. Clearly label network, file, and shell capabilities, validate model-supplied inputs, and avoid exposing stack traces or secrets in plugin responses.

## Agent skills

### Issue tracker

Issues and specs for this repository live in GitHub Issues and are managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

This repository uses the default triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository. Read `CONTEXT.md` and relevant ADRs under `docs/adr/` before exploring or modifying the codebase. See `docs/agents/domain.md`.

## Cursor Cloud specific instructions

- Python 3.12 and Node.js 22 are required. Frontend tests pass `--experimental-strip-types` to Node, so do not switch to an older Node.
- The default image does not include `python3.12-venv`. Install that package before `python3 -m venv .venv`.
- Cloud Agent startup launches the offline fake backend and Vite in tmux sessions `imagenia-api` and `imagenia-web`. Reuse those sessions. Do not start `--provider openai`; that mode calls a paid image API.
- Fake mode seeds `plugin/.local-data/fake/` on the first empty start and does not reseed after jobs exist. Use `--seed 0 --data-dir` on a fresh directory to exercise an empty library.
- The workbench copy is Chinese. A representative check is to open `http://127.0.0.1:5173`, submit a prompt of at least 8 characters with 「开始生成」, and confirm the new image appears in the library.
