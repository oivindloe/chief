# Chief image releases use apps/ repository prefix

**Date:** 2026-11-27
**Branch:** `fix/apps-image-repository`

## Problem

Chief image release manifests pointed at `chief/backend` and `chief/static` repositories. Release pushes must target repositories under the `apps/` prefix to match organizational registry layout.

## Approach

**Tests:** code (manifest assertions already updated with config change)

Updated `images.yml` repository fields and aligned `test_app_release.py` manifest expectations. No other files changed.

## Changes

- `images.yml`: `repository` for backend and static images set to `apps/chief/backend` and `apps/chief/static`.
- `backend/chief/tests/test_app_release.py`: assert the same repository paths when loading the manifest.

## Verification

- Command: `./olib/scripts/orunr py test-all`
- Result: `py.test::backend` passed (including `chief.tests.test_app_release.AppReleaseTests.test_images_manifest_matches_the_release_table`). Suite stopped at `py.lint::.` due to pre-existing pylint `no-name-in-module` findings in `evals/inbox/` (unrelated to this change).

## Review

| # | Severity | Status | Location | Finding | Notes |
|---|----------|--------|----------|---------|-------|
| 1 | Critical | Rejected | `images.yml:4` | `repository` is the registry path image release pushes (`{registry.url}/{repository}`). After promotion writes `digest`, `chief.image` pulls `{registry}/chief/backend@digest` and `{registry}/chief/static@digest` (`charts/chief/templates/deployment.yaml:2`, `charts/chief/templates/migration.yaml:28`, `charts/chief/templates/deployment.yaml:191`, `charts/chief/templates/_helpers.tpl:75`). Hello and Floors use that same contract: images.yml and the digest helper are `hello/backend` and `floors/backend`, and the `apps/` prefix stays on the Helm `image` field used only before a digest exists. This change publishes backend and static on `apps/chief/backend` and `apps/chief/static`, which those digest pulls do not read. `backend/chief/tests/test_app_release.py:47` and `:57` lock the new paths. | Rejected: infrabase `fix/apps-image-repository` sets the chief digest helpers to `apps/chief/backend` and `apps/chief/static`. The chart and this release land together. The cited chart lines are main, before that change. |

## Links

- PR:
