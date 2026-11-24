# Python and Django runtime — Design

Epic: [Runtime upgrades](../../epics/2026-11-24-runtime-upgrades.md) · Spec **1 of 3** · Item: **Python and Django runtime**

**Branch:** `feat/2026-11-24-python-django-runtime`
Status: **design**

## Goal

Move Chief onto Python 3.15 and Django 6.1.3, upgrade the chief-owned Python dependencies, and point the images and the olib submodule at that toolchain. Behavior stays the same. Code changes only keep tests, lint, and the dev stack working.

## Baseline

Workspace members `pyproject.toml`, `backend/pyproject.toml`, `infra/pyproject.toml`, and `services/obsidian/pyproject.toml` require `>=3.13,<3.14`. Both `uv.lock` and `backend/uv.lock` record `requires-python = "==3.13.*"`. The backend Django pin is `Django>=5.2.13,<5.3`, and the workspace lock resolves Django 5.2.15.

`backend/Dockerfile.dev` uses `python:3.13`. `backend/Dockerfile.prod` and `services/obsidian/Dockerfile` use `python:3.13-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91`. The production image copies uv from `ghcr.io/astral-sh/uv:0.11.29@sha256:eb2843a1e56fd9e30c7276ce1a52cba86e64c7b385f5e3279a0e08e02dd058fc`.

`.pre-commit-config.yaml` is a symlink to `olib/.pre-commit-config.yaml`. mypy’s `python_version` lives in olib `config/mypy`, not in a chief file.

## Olib pointer

Set the olib gitlink to `791294d6d57b3707cea1838c0b6ac48c2f65b91d` (`Finish the Python 3.15 toolchain and upgrade locked dependencies. (#137)`). That commit has `requires-python = ">=3.15,<3.16"`, `PYTHON_VERSION = '3.15.2'`, pre-commit `python: python3.15`, `pyupgrade --py315-plus`, `black --target-version=py315`, and mypy `python_version = 3.15`.

Do not edit any file inside `olib/`. Do not run `orun py upgrade`: that command also runs `uv lock` in `./olib` and would rewrite the submodule. The symlink picks up the pre-commit lines from this commit.

## Interpreter pins

Set `requires-python = ">=3.15,<3.16"` on the four chief workspace members listed in **Baseline**. Leave olib’s own `pyproject.toml` untouched. `uv lock` rewrites both lockfiles’ `requires-python` to `==3.15.*`. Nobody edits those lock lines by hand.

## Dependencies

Django stays a range: `Django>=6.1.3,<6.2` in `backend/pyproject.toml`. Django 6.1.3 was uploaded on 2026-11-03, so it is inside the upgrade window below. `django-celery-beat` is pinned exactly at `==2.9.0` before the lock runs, as specified in **django-celery-beat**.

Every other direct dependency in `backend/pyproject.toml` and `services/obsidian/pyproject.toml` is upgraded to the newest release that resolves on Python 3.15 and Django 6.1.3. Extras stay as they are (`psycopg[binary]`, `psycopg[pool]`, `uvicorn[standard]` on the vault service). After the locks resolve, write each of those dependencies back as an exact `==` pin of the locked version. `dropbox`, `fastapi`, vault `uvicorn[standard]`, and vault `httpx` are unpinned today and gain an exact pin the same way. Django remains the range, not an exact pin.

Upgrade window, matching olib’s shared rule: `--exclude-newer "14 days"` and `--exclude-newer-package parproc=2100-01-01`. Resolve with `--python 3.15.2`.

Lock order:

1. From the repo root, with the gitlink, the Django override, the `django-celery-beat==2.9.0` pin, and the other loosened manifests in place, run `uv lock --upgrade --python 3.15.2` with the two exclude-newer flags. That rewrites the workspace `uv.lock` only.
2. Copy `backend/pyproject.toml` into an empty directory outside the workspace and run the same `uv lock` there. Copy the resulting `uv.lock` back to `backend/uv.lock`. The standalone lock’s root stays `source = { virtual = "." }`. Do not copy the workspace `pyproject.toml` into that directory.
3. Write the exact pins from step 1 back into the two chief manifests, then run `uv lock` again in both places without `--upgrade` so the locks match those pins and the versions do not move. Leave `django-celery-beat==2.9.0` and the Django range as they are.

For every direct dependency of `chief-backend-env`, the version in `backend/uv.lock` equals the version in the workspace `uv.lock`. Vault `fastapi`, `uvicorn`, and `httpx` are pinned from the workspace lock.

A direct dependency other than `django-celery-beat` that has no release which installs on this Python and Django stays on the newest release that does install. Record it as an exact pin with a comment naming the refused version and the reason. Do not remove that dependency, and do not add an override for it. The Django override in **django-celery-beat** is the only override this spec adds. If the gates still fail after chief code is adapted, and the failure comes from that dependency, move the pin to the newest older release for which the gates pass and update the comment. The locks from the last `uv lock` without `--upgrade` are the ones that ship.

`dill`’s git source stays olib’s. It enters the workspace lock through the submodule. Do not copy it into a chief manifest.

## django-celery-beat

Floors does not use `django-celery-beat` or `DatabaseScheduler`, and it is still on Django 5.2. It is not a model for this pin.

Published `django-celery-beat` 2.9.0 (2026-02-28) is the newest release. Its runtime requirement is `Django>=2.2,<6.1`, so it already allows Django 6.0 and refuses Django 6.1.3. Chief pins it as `django-celery-beat==2.9.0` from PyPI. The unreleased cap bump is not installed.

`uv` replaces every requirement on a package when `override-dependencies` names that package. A workspace member’s override is ignored when the workspace root is locked, which a probe confirmed. The same override is therefore written in both manifests that produce a lock:

- `pyproject.toml` at the repo root, under `[tool.uv]`
- `backend/pyproject.toml`, under `[tool.uv]`

```toml
override-dependencies = ["django>=6.1.3,<6.2"]
```

That replaces beat’s `Django>=2.2,<6.1` and matches Chief’s Django range. It leaves beat’s other requirements as published, including `cron-descriptor<2.0.0,>=1.2.32`, `django-timezone-field>=5.0`, and `celery<6.0,>=5.2.3`. `cron-descriptor` stays on a 1.x release. There is no override and no direct pin that lifts it to 2.x. `dependency-metadata` is not used. `[tool.uv.sources]` has no `django-celery-beat` entry.

The workspace `uv lock` reads the root override. The standalone `backend/uv.lock` is produced from a copy of `backend/pyproject.toml`, which carries the same override. Both lock manifests contain:

```toml
overrides = [{ name = "django", specifier = ">=6.1.3,<6.2" }]
```

`django-celery-beat` is an exact `==2.9.0` pin, like the other direct dependencies. It is not a holdback and not a git source. If `./olib/scripts/orunr py test-all` fails because beat does not run on Django 6.1, stop and report that failure. Do not switch to a git revision unless a later request says to.

## Images

`backend/Dockerfile.dev` uses `FROM python:3.15` with no digest. It still installs uv with pip.

`backend/Dockerfile.prod` and `services/obsidian/Dockerfile` both use:

`python:3.15-slim@sha256:63bb298d2b7b88f176f51b5189f54ce6535c997682ea70885d2132f5d473a8a5`

That is the OCI index digest of the tag `python:3.15-slim` on 2026-11-24. The production uv copy becomes:

`ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d`

The `COPY --from=… /uv /usr/local/bin/uv` path stays. uv 0.13.9 is the release that regenerates the locks. The vault image keeps installing uv with pip. `OBSIDIAN_HEADLESS_VERSION` stays `0.0.14`, and the Node 22 install stays.

`backend/chief/tests/test_compose_config.py` updates `_PYTHON_IMAGE` and `_UV_IMAGE` to those two references. The vault test in that file asserts the vault `FROM` line equals `_PYTHON_IMAGE`. `_NGINX_IMAGE` stays.

## Code changes

Adapt chief code only where the upgraded packages or Django 6.1.3 make `./olib/scripts/orunr py test-all` fail. A failure whose stack is inside `olib/` at this gitlink stops the spec; do not patch the submodule. A failure because `django-celery-beat` 2.9.0 does not run on Django 6.1 stops the spec and is reported; do not switch that pin to a git revision.

Generate Django migrations with Django’s tooling when chief models change. Do not hand-write migration files. `django-celery-beat`’s own migrations stay inside that package.

Recreate the venv only after both locks are written: `./olib/scripts/orun init --py --force` from the repo root. That runs `uv venv --python 3.15.2` and a locked sync.

## Out of this spec

Dashboard JS packages, Compose `postgres` / `redis` / `nginx` tags, `infra/k8s/Dockerfile.static.stage`, and the `obsidian-headless` version are specs 2 and 3. Historical specs and plans stay as they are.

## Epic phasing

The epic phasing sentence published with this design is:

```markdown
Phasing: Spec 1 uses olib `791294d6d57b3707cea1838c0b6ac48c2f65b91d`, whose `requires-python` covers 3.15 and whose `PYTHON_VERSION` is `'3.15.2'`. Specs 2 and 3 stay queued behind spec 1.
```

## Acceptance

The spec is done when all of the following are true.

The olib gitlink is `791294d6d57b3707cea1838c0b6ac48c2f65b91d` and `git status` inside `olib/` is clean. `.pre-commit-config.yaml` is still a symlink to `olib/.pre-commit-config.yaml` and shows `python: python3.15`. The four chief workspace members require `>=3.15,<3.16`. Both locks record `==3.15.*`. `.venv/bin/python` reports 3.15.2.

`backend/pyproject.toml` pins `Django>=6.1.3,<6.2`. Both locks resolve `django-celery-beat` 2.9.0 and a Django version in `>=6.1.3,<6.2`. Both lock manifests contain `overrides = [{ name = "django", specifier = ">=6.1.3,<6.2" }]`. The root `pyproject.toml` and `backend/pyproject.toml` each declare that same `override-dependencies` entry.

`cron-descriptor` in both locks satisfies `cron-descriptor<2.0.0,>=1.2.32`. No chief manifest depends on `cron-descriptor` 2.x.

Every other direct backend and vault dependency is an exact `==` pin of the locked version, extras unchanged. Direct `chief-backend-env` versions match across the two locks. Each holdback has a comment with the refused version and the reason. `django-celery-beat` is `==2.9.0` from PyPI. `[tool.uv.sources]` has no `django-celery-beat` entry, and the git rev `0ee32beb51ebcfe4198d47f075e43db4d1b5aa9a` is absent.

The three Dockerfiles and `_PYTHON_IMAGE` / `_UV_IMAGE` match **Images**. The vault `FROM` line matches `_PYTHON_IMAGE`. `OBSIDIAN_HEADLESS_VERSION` is still `0.0.14`.

`./olib/scripts/orunr py test-all` passes. If it fails because beat does not run on Django 6.1, the spec stops with that failure reported. `docker build -f backend/Dockerfile.dev`, `docker build -f backend/Dockerfile.prod`, and `docker build -f services/obsidian/Dockerfile` succeed from the repo root. The implementation branch is `feat/2026-11-24-python-django-runtime`.
