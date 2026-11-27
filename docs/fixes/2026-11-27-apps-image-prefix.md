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

## Links

- PR:
