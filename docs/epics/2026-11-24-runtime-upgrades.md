# Epic: Runtime upgrades

Status: **in progress**
Roadmap: none.

Bring Chief onto Django 6.1.3 and Python 3.15, and refresh the other runtimes in the dev stack: chief-owned Python packages and Python base images, the dashboard JS packages, and the Compose service images plus `obsidian-headless`. Each surface is its own spec so one lockfile failure stays in one place. Behavior stays the same. Code changes only keep tests, lint, and the dev stack working on the new versions.

## Specs

- [ ] 1. Python and Django runtime — [spec](../specs/2026-11-24-python-django-runtime/)
- [ ] 2. Dashboard JS packages
- [ ] 3. Compose service images and obsidian-headless

Build order (implementation): **1 → 2 → 3**

Phasing: Spec 1 uses olib `791294d6d57b3707cea1838c0b6ac48c2f65b91d`, whose `requires-python` covers 3.15 and whose `PYTHON_VERSION` is `'3.15.2'`. Specs 2 and 3 stay queued behind spec 1.

## Build order

| Step | Spec | Delivers |
|------|------|----------|
| 1 | 1 | Python 3.15, Django 6.1.3, upgraded chief Python deps, both uv locks, Python base images, olib pointer |
| 2 | 2 | Upgraded dashboard JS dependencies and a refreshed pnpm lock |
| 3 | 3 | Newer Compose Postgres, Redis, and nginx pins, the digest-pinned static nginx image, and a newer `obsidian-headless` |

## Spec details

### 1. Python and Django runtime

Set chief workspace members (`pyproject.toml`, `backend`, `infra`, `services/obsidian`) to `requires-python` `>=3.15,<3.16`. Pin Django to the 6.1 line at 6.1.3 or a later 6.1 bugfix, and regenerate `uv.lock` and `backend/uv.lock`. Upgrade chief-owned Python dependencies, including the vault service’s `fastapi`, `uvicorn`, and `httpx`. Move `backend/Dockerfile.dev` to `python:3.15`, and move the digest-pinned slim images in `backend/Dockerfile.prod` and `services/obsidian/Dockerfile` to current `python:3.15-slim` digests. Refresh the production image’s pinned `ghcr.io/astral-sh/uv` copy to a release that can export the regenerated locks. Point the olib submodule at a commit that already allows 3.15, and set `.pre-commit-config.yaml`’s default Python to `python3.15`. Update `backend/chief/tests/test_compose_config.py` for the new production Python image. A dependency with no installable release on this pair stays on the newest release that still installs and is listed as an exception. The spec stops if Django 6.1.3 cannot be installed, or if no qualifying olib commit exists.

### 2. Dashboard JS packages

Upgrade dependencies and devDependencies in `backend/apps/web/static/web/package.json` and refresh `pnpm-lock.yaml`. Adjust the editor bundle, rich-content build, lint, unit tests, and browser tests only where the new packages require it. Assets that are not entries in that package.json stay as they are.

### 3. Compose service images and obsidian-headless

At implementation time, set `chief-postgres`, `chief-redis`, `chief-nginx`, and `chief-static` in `infra/docker/docker-compose.yml` to the newest stable major tags of the official images (stable nginx, not mainline). Postgres and Redis must still pass the existing healthcheck and Django’s current connection settings on an empty volume. A major that fails those checks falls back to the newest older major that passes, and the failed major is an exception. Developers recreate an existing local Postgres volume; this spec does not add dump/restore or `pg_upgrade`. Compose nginx and `infra/k8s/Dockerfile.static.stage` use the same nginx major. The static Dockerfile stays digest-pinned, and Compose stays a tag without a digest. `test_compose_config.py` follows that digest. `obsidian-headless` moves to the newest npm release whose vault supervisor tests pass. Node stays on the major already in `services/obsidian/Dockerfile` unless that release requires a newer Node. The Python `FROM` line and the Python lock install in that Dockerfile stay with spec 1.

## Constraints

- olib source stays unchanged. Spec 1 only moves the submodule pointer.
- The same exception rule covers every spec: take the newest release that still installs and works, list it, and keep going. Spec 1 fails as a whole only when Django 6.1.3 cannot be installed.
- No new product behavior, endpoints, or schema redesign. Fixes are limited to breakage from the version moves.
- One spec is one later design, plan, and implementation cycle. Specs 2 and 3 remain checklist items until spec 1 is underway.
