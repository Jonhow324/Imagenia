# Repository Guidelines

## Project Structure & Module Organization

This repository is documentation-first. Key paths are:

- `docs/qwenpaw-plugin-development-research.md` — Chinese-language research and implementation guidance for QwenPaw plugins.
- `.agents/` and `.codex/` — agent configuration directories; treat them as tooling metadata unless a task explicitly targets them.

Add new research notes under `docs/` with kebab-case names (for example, `docs/plugin-security-review.md`). If executable plugin code is introduced, keep each plugin self-contained in a named directory with its own `plugin.json`, backend entry point, dependencies, README, and tests.

## Build, Test, and Development Commands

There is no repository-wide build system or automated test suite yet. Use lightweight checks for documentation changes:

```bash
sed -n '1,120p' docs/qwenpaw-plugin-development-research.md
```

Reviews the rendered source structure and opening content.

```bash
grep -n '^#' docs/*.md
```

Checks heading order across Markdown files. If available locally, run `markdownlint "**/*.md"` before submitting. For future QwenPaw plugin code, document exact install, launch, and test commands in the plugin's README rather than assuming global tooling.

## Coding Style & Naming Conventions

Use UTF-8, LF line endings, and spaces rather than tabs. Keep Markdown paragraphs short, use fenced code blocks with language tags, and prefer tables only when they improve scanning. Preserve the existing document language within a file. Use kebab-case for documentation filenames and lowercase, hyphenated IDs in `plugin.json` (for example, `hello-tool`). Python examples should use four-space indentation, type annotations, concise docstrings, and relative imports inside plugin packages.

## Testing Guidelines

Documentation changes must be checked for accurate commands, valid JSON/Python examples, working internal links, and consistent heading levels. When plugin code is added, cover normal behavior, invalid input, missing configuration, external-service failures, install/upgrade/uninstall flows, and the minimum and latest supported QwenPaw versions. Name Python tests `test_<behavior>.py` and keep them under the relevant plugin's `tests/` directory.

## Commit & Pull Request Guidelines

No usable Git history is present in this checkout, so follow Conventional Commits: `docs: clarify version compatibility` or `feat: add hello tool example`. Keep commits focused. Pull requests should summarize the change, identify affected documents or plugins, list validation performed, and link related issues or source material. Include screenshots only for rendered UI or formatting changes when visual review helps.

## Security & Configuration Tips

Never commit credentials, tokens, personal paths, or production configuration. Use placeholders in examples. Clearly label network, file, and shell capabilities, validate model-supplied inputs, and avoid exposing stack traces or secrets in plugin responses.
