# Vitest jsdom unit config: disable Node Web Storage

**Date:** 2026-11-14
**Branch:** `fix/vitest-node-webstorage`

## Problem

Chief CI (`js.test-unit::backend_apps_web_static_web`, run 43647042457) fails one test in
`activity_tree.test.js`. Chief has no `.node-version`, so `orun init --js` selects
`fnm use lts-latest` (Node 25+). Since Node 25, Node defines a global `localStorage` that is
`undefined` unless `--localstorage-file` is given (`ExperimentalWarning: localStorage is not
available because --localstorage-file was not provided`). That global shadows jsdom's
`localStorage`, so `expansion intent is keyed by activity id for page lifetime only` fails with
`TypeError: Cannot read properties of undefined (reading 'length')` at `localStorage.length`.

## Approach

**Tests:** code (failing test first). The failing test already exists; no new test file.

Set `execArgv: ['--no-experimental-webstorage']` on the Vitest `test` block in
`backend/apps/web/static/web/vitest.config.js` so worker processes start without Node's built-in
Web Storage and jsdom's `localStorage` is visible. Must be the config option; `--execArgv` on the
vitest CLI has no effect. Same fix as olib `js/vitest.config.ts` (2026-11-11).

## Changes

- `backend/apps/web/static/web/vitest.config.js`: `execArgv: ['--no-experimental-webstorage']` with
  a comment stating the Node 25+ shadow constraint.
- `backend/apps/web/static/web/vitest.config.js`: pre-commit license-header tooling reordered the
  file header and added the SPDX line; the result matches `olib/js/vitest.config.ts`.
- `docs/fixes/2026-11-14-vitest-node-webstorage.md`: this note.

## Verification

- Red: `./olib/scripts/orunr js test-unit backend/apps/web/static/web/activity_tree.test.js` before
  the change: 1 failed (`localStorage.length` TypeError).
- Green: `pnpm run test:unit` in `backend/apps/web/static/web` after the change: 74/74 passed
  (no ExperimentalWarning; `expansion intent is keyed by activity id for page lifetime only`
  passes).
- Gates: `./olib/scripts/orunr js test-unit`, `./olib/scripts/orunr js lint`, and
  `./olib/scripts/orunr js tsc` passed from the worktree.

## Review

| # | Severity | Status | Location | Finding | Notes |
|---|----------|--------|----------|---------|-------|
| 1 | Minor | Fixed | `docs/fixes/2026-11-14-vitest-node-webstorage.md:27-29` | The Changes list does not mention that the license header in `vitest.config.js` was also reordered and gained an SPDX line. That diff comes from pre-commit header tooling and matches `olib/js/vitest.config.ts`, so it is harmless, but a reader of the diff may wonder why it is there. | Optional: add one bullet saying the header was normalized by tooling. No code change. |

Status: `Fixed` | `Rejected` (empty while review is in progress).

## Links

- PR: <url when opened>
