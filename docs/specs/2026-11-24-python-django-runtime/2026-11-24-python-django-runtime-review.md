# Python and Django runtime — Code Review

> Agent-generated from `superpowers/requesting-code-review`. Update **Status** as the user gives feedback.

**Epic:** [Runtime upgrades](../../epics/2026-11-24-runtime-upgrades.md)
**Design:** [`2026-11-24-python-django-runtime-design.md`](./2026-11-24-python-django-runtime-design.md)
**Plan:** [`2026-11-24-python-django-runtime-plan.md`](./2026-11-24-python-django-runtime-plan.md)
**Branch:** `feat/2026-11-24-python-django-runtime`
**Review range:** `feat/2026-11-24-python-django-runtime` against `origin/main` (2026-11-24)

## Assessment

**Ready to merge?** Yes

**Reasoning:** The toolchain, Django 6.1.3 range, beat override, image digests, and lock parity match the design. The croniter 7.0.0 pin and the raw-line holdback check fix the earlier findings, and `py test-all --full` passed again after that fix.

## Strengths

- The olib gitlink is `791294d6d57b3707cea1838c0b6ac48c2f65b91d` with a clean submodule tree. `.pre-commit-config.yaml` is still the symlink and contains `python: python3.15`. The four chief members require `>=3.15,<3.16`. Both locks record `requires-python = "==3.15.*"`. `.venv/bin/python` is 3.15.2.
- Django stays `>=6.1.3,<6.2` and both locks resolve 6.1.3. `django-celery-beat==2.9.0` comes from PyPI in both locks. The same `override-dependencies = ["django>=6.1.3,<6.2"]` is in the root and backend manifests, and both lock manifests contain `overrides = [{ name = "django", specifier = ">=6.1.3,<6.2" }]`. No `dependency-metadata`, no beat git source, and `0ee32beb51ebcfe4198d47f075e43db4d1b5aa9a` is absent. `cron-descriptor` is 1.4.5 in both locks. `dill` stays olib’s git source and is not copied into a chief manifest.
- Direct `chief-backend-env` versions match across `uv.lock` and `backend/uv.lock`. The workspace virtual root is `{ virtual = "backend" }` and the standalone root is `{ virtual = "." }`. Extras stay `psycopg[binary]`, `psycopg[pool]`, backend `uvicorn` without an extra, and vault `uvicorn[standard]`. `dropbox`, vault `fastapi`, and vault `httpx` are exact pins. `croniter==7.0.0` is the same version in `backend/pyproject.toml` and both locks. Packages that look behind PyPI’s absolute latest (`redis` 8.1.0, `pydantic` 2.14.3, `dropbox` 12.2.4, `openai` 3.49.0, `fastapi` 0.162.3) are the newest non-prerelease uploads outside the 14-day window as of the 2026-11-24 lock.
- Images match the design: unpinned `python:3.15` in `backend/Dockerfile.dev`, the slim digest `sha256:63bb298d2b7b88f176f51b5189f54ce6535c997682ea70885d2132f5d473a8a5` on prod and vault, and uv `0.13.9` at `sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d`. Prod still exports `--frozen` and installs `--require-hashes`. `_NGINX_IMAGE`, `infra/k8s/Dockerfile.static.stage`, Compose postgres/redis/nginx tags, and `OBSIDIAN_HEADLESS_VERSION=0.0.14` are unchanged.
- Chief code changes stay small. `_CronSlice.get_range` accepts `random` and forwards it, matching python-crontab 3.4.0. The httpx versus httpx2 and `click.get_text_stream` ignores are limited to the call sites the new stubs reject. `backend/chief/tests/test_python_django_runtime.py` locks the gitlink, interpreter, override, and pin contract on `OTestCase`.

## Issues

### Critical

| # | Status | Location | Finding | Notes |
|---|--------|----------|---------|-------|
| — | | | none | |

### Important

| # | Status | Location | Finding | Notes |
|---|--------|----------|---------|-------|
| 1 | Fixed | `backend/pyproject.toml:23` | `croniter` stayed `==6.0.0`. The design says every other direct backend and vault dependency is upgraded to the newest release that resolves on Python 3.15 and Django 6.1.3, inside `--exclude-newer "14 days"`. croniter 7.0.0 (uploaded 2026-11-09, `requires-python >=3.9`, not yanked, depends only on `python-dateutil`) is outside that window relative to the 2026-11-24 lock. The plan’s loosen list omitted `croniter`, so the upgrade lock never considered it, and there is no holdback comment. Leaving a direct dependency on the previous major release without that comment misses the dependency rule. Loosen `croniter`, rerun the same non-upgrade lock in both places, and pin the resolved version. If 7.0.0 fails `py test-all` or the three image builds, pin the newest older release that passes and add `# holdback: refused 7.0.0 because <reason>`. | Plan step 4 lists the names to loosen and does not include `croniter`. The design’s Dependencies section does. |

### Minor

| # | Status | Location | Finding | Notes |
|---|--------|----------|---------|-------|
| 1 | Fixed | `backend/chief/tests/test_python_django_runtime.py:23` | The holdback check cannot see a valid holdback. `_dependency_lines` reads dependencies through `tomllib`, which drops `#` comments, and `HOLDBACK_PATTERN` still requires a leading `#` on the text after `#` was split off (`test_direct_pins_match_locked_versions`, around lines 257–268). A line `# holdback: refused 7.0.0 because …` would not match. No dependency has a holdback today, so the suite stays green. Read the raw manifest lines and match `holdback: refused <version> because <reason>` on the comment text. | Dormant until a holdback is added. Matters if finding 1 ends in a holdback comment. |

## Recommendations

- `./olib/scripts/orun init --py --force` exits non-zero on `uv sync --locked` because these locks now record `exclude-newer-span`. Init calls `run_uv_sync_locked`, which does not use the exclude-newer fallback in `run_uv_sync`. A later `uv sync` with the same exclude-newer flags succeeded, and `.venv/bin/python` is 3.15.2. Fixing that path edits `olib/`, which this spec forbids. Track it on the olib side. This review does not ask for an olib change.
- `click.get_text_stream` in `config.py` is the Click 8.5 private helper that Click 9 plans to remove. The `type: ignore[operator]` is enough for this toolchain. Replace the call when Click 9 is adopted.
- Parent gates: `./olib/scripts/orunr py test-all --full` exited 0 again after the croniter fix. JS unit, lint, and `tsc` were scoped to `backend/apps/web/static/web` and exited 0. This branch does not change JS. Unscoped `js test-unit` also runs olib browser tests, which hung at baseline on main and were not re-run. `docker build` for `backend/Dockerfile.dev`, `backend/Dockerfile.prod`, and `services/obsidian/Dockerfile` exited 0 before the croniter lock update.

## Re-review (2026-11-24)

Re-checked the croniter fix. Important #1 is fixed: `croniter==7.0.0` in `backend/pyproject.toml` and both locks, and croniter 7 no longer pulls `pytz`. Minor #1 is fixed: `_dependency_lines_raw` keeps inline `#` comments, and `HOLDBACK_PATTERN` matches `holdback: refused <version> because <reason>` on that comment text. No new open findings.
