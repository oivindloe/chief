# Run chief CI on the heavy ARC runner

**Date:** 2026-11-07
**Branch:** `fix/chief-heavy-runner`

## Problem

`olib-dev-test-all` ran on `ol-base-oivindloe-light` (6Gi memory limit). Prometheus showed the runner pod pinned at its 6Gi limit from about 4 minutes into "Dev test-all" until GitHub lost the runner 19 minutes in, so the job failed with no step result or log.

## Approach

**Tests:** authored surface (no new test) — instance config only.

Switch `githubTestRunner` to `ol-base-oivindloe-heavy` (12Gi limit) and re-render the managed workflow with `orun init --github`.

## Changes

- `config.py`: `githubTestRunner = 'ol-base-oivindloe-heavy'`
- `.github/workflows/olib-dev-test-all.yml`: re-rendered; only `runs-on` changes

## Verification

- Command: `./olib/scripts/orunr py test-all`
- Result: all test, mypy, and migrate jobs pass. `py.lint::.` fails with 5 `E0611 no-name-in-module` in `evals/inbox/` (`apps.runner`, `apps.sessions`). The same 5 failures reproduce on `origin/main` without this change; out of scope here.

## Review

Reviewer verdict: ready to merge. No Critical or Important findings.

| # | Severity | Status | Location | Finding | Notes |
|---|----------|--------|----------|---------|-------|
| 1 | Minor | Rejected | `infrabase/runbooks/arc/README.md:12` | Runbook still says floors is the only heavy user; chief and floors now share heavy's 4-runner cap | Different repo; follow-up in infrabase |
| 2 | Minor | Rejected | `docs/fixes/2026-11-07-chief-heavy-runner.md` Verification | Local verification does not prove 12Gi is enough | Only the ARC runner can show it; the PR's own `olib-dev-test-all` check is that evidence |
| 3 | Minor | Fixed | `docs/fixes/2026-11-07-chief-heavy-runner.md` Review | Missing status legend and review outcome | Added |

Status values: `Fixed` | `Rejected`

## Links

- PR: https://github.com/oivindloe/chief/pull/69
