# Python and Django runtime Implementation Plan

Epic: [Runtime upgrades](../../epics/2026-11-24-runtime-upgrades.md) · Spec **1 of 3** · Item: **Python and Django runtime**

> **For workers:** `/impl` prepares a worktree first. Create
> `docs/specs/2026-11-24-python-django-runtime/2026-11-24-python-django-runtime-revision.md`
> from the revision template in `olib/docs/specs/01-superpowers/01-superpowers.spec.md` before
> Task 1, and do not read it during implementation. Run S_final after the last implementation
> task. Under `/ship`, the ship skill runs S_final.

**Goal:** Move Chief onto Python 3.15.2 and Django 6.1.3, upgrade the chief-owned Python dependencies, and point the images and the olib submodule at that toolchain. Behavior stays the same.

**Architecture:** The workspace root lock and the standalone `backend/uv.lock` are both regenerated against Python 3.15.2. Django stays a `>=6.1.3,<6.2` range. `django-celery-beat` stays the PyPI release 2.9.0, and the same `django` override is written in the root manifest and in `backend/pyproject.toml` so both locks accept Django 6.1. Chief code changes only where the new toolchain makes `py test-all` fail. The olib submodule moves to a commit that already speaks Python 3.15; nothing inside `olib/` is edited.

**Tech Stack:** Python 3.15.2, Django `>=6.1.3,<6.2`, uv 0.13.9, `django-celery-beat==2.9.0`, Docker `python:3.15` and the pinned `python:3.15-slim` digest, `OTestCase`.

**Branch:** `feat/2026-11-24-python-django-runtime`

**Gates (do not weaken):** `./olib/scripts/orunr py test-all` exits 0. From the repo root, `docker build -f backend/Dockerfile.dev .`, `docker build -f backend/Dockerfile.prod .`, and `docker build -f services/obsidian/Dockerfile .` each exit 0. Task 2 runs all four before its commit. S_final runs them again.

## Conventions

- Commands from the repo root (the directory that contains `config.py`). Read-only gates use `./olib/scripts/orunr`. Venv recreation uses `./olib/scripts/orun`. Do not run `./olib/scripts/orun py upgrade` (it also locks `./olib` and would rewrite the submodule).
- Per-task gate: `./olib/scripts/orunr py test-all` exits 0. This spec does not edit skill, agent, or command text, so tasks do not need `--full`. JavaScript is configured and must still pass; S_final runs the JS gates. Task 1 does not docker-build: the new base images install the locks Task 2 writes.
- Git: one commit per task, then `git fetch origin main && git rebase origin/main && git push -u origin HEAD`; stop on rebase conflicts. Do not commit on `main`.
- Function documentation: a brief docstring on every function written or changed (`AGENTS.md`).
- No compatibility re-exports: update imports, delete replaced modules.
- Test bases: `OTestCase`, `OTransactionTestCase`, or `OLiveServerTestCase` from `olib.py.django.test.cases` only. Capture CLI output with `self.captureStdout()`.
- Tests: code gets a failing test first; authored surface gets no new test. Uncertain classification is code. If logic and new copy land together, test the logic with fixture content and do not assert the live prose (`ai/skills/workflow/authored-surface.md`).
- Test names avoid the words error, exception, warning, notice, deprecated, deprecation.
- No license headers in new files (pre-commit adds them). If a commit hook rewrites files and rejects the commit, stage those rewrites and create a new commit with the same message.
- Do not edit any file inside `olib/`. Do not change dashboard JS packages, Compose `postgres` / `redis` / `nginx` tags, `infra/k8s/Dockerfile.static.stage`, `_NGINX_IMAGE`, or `OBSIDIAN_HEADLESS_VERSION`. Historical specs and plans stay as they are.
- Do not hand-edit `requires-python` inside either lockfile. Do not hand-write Django migration files.

## File structure

| File | Responsibility |
|------|----------------|
| `backend/chief/tests/test_compose_config.py` (modify) | Expected production Python and uv image references, the dev `FROM` line, and the vault `FROM` line |
| `backend/Dockerfile.dev` (modify) | Unpinned `python:3.15` base; uv still installed with pip |
| `backend/Dockerfile.prod` (modify) | Digest-pinned `python:3.15-slim` and uv 0.13.9 copy |
| `services/obsidian/Dockerfile` (modify) | Same slim digest as production; Node 22, headless `0.0.14`, and pip-installed uv stay |
| `backend/chief/tests/test_python_django_runtime.py` (create) | Gitlink, interpreter, lock, override, and exact-pin contract |
| `pyproject.toml` (modify) | Workspace `requires-python` and the `django` override |
| `backend/pyproject.toml` (modify) | Interpreter, Django range, beat pin, other exact pins, the same override |
| `infra/pyproject.toml` (modify) | `requires-python` only |
| `services/obsidian/pyproject.toml` (modify) | `requires-python` and exact vault pins |
| `uv.lock` (generated) | Workspace lock for Python 3.15 |
| `backend/uv.lock` (generated) | Standalone backend lock whose root stays `source = { virtual = "." }` |
| `olib` gitlink (modify) | Submodule pointer only, to `791294d6d57b3707cea1838c0b6ac48c2f65b91d` |
| Chief modules outside `olib/` (modify only if Task 2's suite fails) | Call-site fixes required by Django 6.1.3 or an upgraded dependency |

---

## Task 1: Python base images

**Test obligation:** code

**Files:**
- Modify: `backend/chief/tests/test_compose_config.py`
- Modify: `backend/Dockerfile.dev`, `backend/Dockerfile.prod`, `services/obsidian/Dockerfile`

**Interfaces:**
- Module constants in `test_compose_config.py` become:

```python
_PYTHON_IMAGE = 'python:3.15-slim@sha256:63bb298d2b7b88f176f51b5189f54ce6535c997682ea70885d2132f5d473a8a5'
_UV_IMAGE = (
    'ghcr.io/astral-sh/uv:0.13.9@'
    + 'sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d'
)
```

- `_NGINX_IMAGE` stays `nginx:1.29-alpine@sha256:5616878291a2eed594aee8db4dade5878cf7edcb475e59193904b198d9b830de`.
- `backend/Dockerfile.dev` first line: `FROM python:3.15`. No digest. The `python -m pip install … uv` line stays. No `ghcr.io/astral-sh/uv` copy.
- `backend/Dockerfile.prod` first line is `FROM ` plus `_PYTHON_IMAGE`. The uv copy stays `COPY --from=<uv image> /uv /usr/local/bin/uv` with `<uv image>` equal to `_UV_IMAGE`.
- `services/obsidian/Dockerfile` `FROM` line is the same `_PYTHON_IMAGE` value. Leave the license header, `ENV OBSIDIAN_HEADLESS_VERSION=0.0.14`, the Node 22 `setup_22.x` install, and `python -m pip install … uv`.

**Tests (write first, watch them fail):**

In `TestComposeObsidianVaultService.test_vault_service_pins_python_and_node_dependency_versions`, add:
- The `^FROM (\S+)` lines equal `[_PYTHON_IMAGE]`.
- The file contains `ENV OBSIDIAN_HEADLESS_VERSION=0.0.14`.
- The file contains `setup_22.x` and `python -m pip install --disable-pip-version-check --root-user-action=ignore uv`.
- The file does not contain `ghcr.io/astral-sh/uv`.

Add `TestPythonBaseImages(OTestCase)` in the same module:
- `test_dev_image_uses_unpinned_python_315` — `^FROM (\S+)` lines in `backend/Dockerfile.dev` equal `['python:3.15']`; the file contains the same pip uv install line; the file does not contain `ghcr.io/astral-sh/uv`.

Existing `test_deployment_images_pin_single_stage_runtime_inputs` and `test_production_backend_image_uses_shared_slim_runtime` follow the new constants. Give the new class and method a brief docstring.

**Acceptance criteria:**
- The three Dockerfiles match the design **Images** section.
- `_PYTHON_IMAGE` and `_UV_IMAGE` match those references. The vault `FROM` line equals `_PYTHON_IMAGE`.
- `_NGINX_IMAGE` and `infra/k8s/Dockerfile.static.stage` are unchanged.
- `OBSIDIAN_HEADLESS_VERSION` is `0.0.14` and the Node 22 install is still present.
- `./olib/scripts/orunr py test-all` exits 0.

**Commands:**
1. Update the constants and assertions. Run:

```bash
./olib/scripts/orunr py test "$PWD/backend/chief/tests/test_compose_config.py"
```

Expected: non-zero. `test_dev_image_uses_unpinned_python_315`, `test_vault_service_pins_python_and_node_dependency_versions`, and the production image assertions fail because the Dockerfiles still say `python:3.13`.
2. Update the three Dockerfiles. Re-run the same test command. Expected: exit 0.
3. `./olib/scripts/orunr py test-all` exits 0. Do not docker-build in this task.
4. Commit: `chore(docker): point Python images at 3.15`
5. `git fetch origin main && git rebase origin/main && git push -u origin HEAD`

---

## Task 2: Python 3.15 toolchain, locks, and gates

**Test obligation:** code

**Files:**
- Create: `backend/chief/tests/test_python_django_runtime.py`
- Modify: `pyproject.toml`, `backend/pyproject.toml`, `infra/pyproject.toml`, `services/obsidian/pyproject.toml`
- Generated: `uv.lock`, `backend/uv.lock`
- Modify: the `olib` gitlink
- Modify only as the suite requires: chief Python outside `olib/`, plus migrations Django's tooling generates

**Interfaces:**

Constants in the new test module:

- `OLIB_GITLINK = '791294d6d57b3707cea1838c0b6ac48c2f65b91d'`
- `FORBIDDEN_BEAT_REV = '0ee32beb51ebcfe4198d47f075e43db4d1b5aa9a'`
- `DJANGO_RANGE = '>=6.1.3,<6.2'`
- `BEAT_PIN = 'django-celery-beat==2.9.0'`
- `DJANGO_OVERRIDE = 'django>=6.1.3,<6.2'`

Helpers, each with a docstring:

- `_repo_root() -> Path` — `Path(__file__).resolve().parents[3]`.
- `_load_toml(path: Path) -> dict` — `tomllib.loads` of the file text.
- `_pep503(name: str) -> str` — `re.sub(r'[-_.]+', '-', name).lower()`.
- `_numeric_version(version: str) -> tuple[int, ...]` — leading dotted integers, stopping at the first non-digit component.
- `_package_versions(lock: dict) -> dict[str, str]` — `{package['name']: package['version']}` for every `[[package]]` entry that has `version`.
- `_virtual_root(lock: dict, name: str) -> dict` — the `[[package]]` table whose `name` is `name`.

Lock pin script (run from the repo root after the upgrade lock, before rewriting manifests). This is the version source for every exact pin. Do not type versions by hand.

```python
"""Print exact requirement strings from the workspace lock."""
import re
import tomllib
from pathlib import Path

def pep503(name: str) -> str:
    """Normalize a distribution name the way uv records it."""
    return re.sub(r'[-_.]+', '-', name).lower()

lock = tomllib.loads(Path('uv.lock').read_text())
versions = {pkg['name']: pkg['version'] for pkg in lock['package'] if 'version' in pkg}

def pin(requirement: str) -> str:
    """Return the exact pin for one loosened direct requirement."""
    match = re.fullmatch(r'([A-Za-z0-9_.-]+)(\[[^\]]+\])?', requirement.strip())
    if match is None:
        raise SystemExit(f'unparsed requirement: {requirement}')
    name, extras = match.group(1), match.group(2) or ''
    if name == 'Django':
        return 'Django>=6.1.3,<6.2'
    if name == 'django-celery-beat':
        if versions['django-celery-beat'] != '2.9.0':
            raise SystemExit(f"django-celery-beat locked {versions['django-celery-beat']}")
        return 'django-celery-beat==2.9.0'
    return f'{name}{extras}=={versions[pep503(name)]}'
```

Preserve the current dependency order and the current spelling (`PyYAML`, `ruamel.yaml`, `psycopg[binary]`, `psycopg[pool]`, vault `uvicorn[standard]`). A holdback comment already on that line stays on the rewritten line.

**Tests (write first, watch them fail):**

Class `TestPythonDjangoRuntimePins(OTestCase)` in `backend/chief/tests/test_python_django_runtime.py`.

- `test_olib_checkout_is_the_315_toolchain` — `git -C olib rev-parse HEAD` is `OLIB_GITLINK`; `git -C olib status --porcelain` is empty; `olib/pyproject.toml` `requires-python` is `>=3.15,<3.16`.
- `test_precommit_symlink_selects_python315` — `.pre-commit-config.yaml` is a symlink whose target is `olib/.pre-commit-config.yaml`; the text contains `python: python3.15` and does not contain `python: python3.13`.
- `test_workspace_members_require_python_315` — `pyproject.toml`, `backend/pyproject.toml`, `infra/pyproject.toml`, and `services/obsidian/pyproject.toml` each have `requires-python` `>=3.15,<3.16`. Root `[tool.uv]` still has `package = false`, `index-strategy = "first-index"`, and workspace members `["backend", "infra", "olib", "services/obsidian"]`.
- `test_locks_record_python_315_star` — both `uv.lock` and `backend/uv.lock` have top-level `requires-python` `==3.15.*`.
- `test_django_range_and_beat_override` — backend dependencies include `Django>=6.1.3,<6.2` and `django-celery-beat==2.9.0`, and no `Django==` pin. Root and backend `[tool.uv].override-dependencies` equal `['django>=6.1.3,<6.2']`. Neither file has `dependency-metadata`. Neither `[tool.uv.sources]` contains `django-celery-beat` (a missing `sources` table passes). Both locks' `manifest.overrides` equal `[{'name': 'django', 'specifier': '>=6.1.3,<6.2'}]`. Both locks' `django-celery-beat` package has `version == '2.9.0'` and `source == {'registry': 'https://pypi.org/simple'}`. `FORBIDDEN_BEAT_REV` is absent from both pyprojects, both locks, and `services/obsidian/pyproject.toml`. Both locks' `django` version satisfies `>= (6, 1, 3)` and `< (6, 2)` via `_numeric_version`.
- `test_cron_descriptor_stays_on_1_x` — both locks' `cron-descriptor` version satisfies `>= (1, 2, 32)` and `< (2,)`. None of the four chief manifests list a dependency whose pep503 name is `cron-descriptor`.
- `test_direct_pins_match_locked_versions` — every backend and vault direct dependency other than `Django` matches `==` plus the workspace-lock version of its pep503 name. Extras stay `psycopg[binary]`, `psycopg[pool]`, backend `uvicorn` without an extra, and vault `uvicorn[standard]`. `dropbox`, vault `fastapi`, vault `uvicorn`, and vault `httpx` are exact pins. For every dependency `name` on the workspace lock's `chief-backend-env` package, `_package_versions` agrees between `uv.lock` and `backend/uv.lock`. The workspace `chief-backend-env` source is `{'virtual': 'backend'}`. The standalone `chief-backend-env` source is `{'virtual': '.'}`. None of the four chief dependency lists include `dill`. A `#` on a dependency line matches `# holdback: refused <version> because <non-empty reason>` where `<version>` matches `\d+\.\d+(?:\.\d+)?`. The `Django` and `django-celery-beat` lines have no holdback comment. The absence of any holdback is valid.
- `test_venv_interpreter_reports_3152` — `.venv/bin/python -c 'import sys; print(sys.version.split()[0])'` exits 0 and prints `3.15.2`.

**Acceptance criteria:**
- The olib gitlink is `791294d6d57b3707cea1838c0b6ac48c2f65b91d` and `git status` inside `olib/` is clean. `.pre-commit-config.yaml` is still the symlink and shows `python: python3.15`.
- The four chief workspace members require `>=3.15,<3.16`. Both locks record `==3.15.*`. `.venv/bin/python` reports `3.15.2`.
- `backend/pyproject.toml` pins `Django>=6.1.3,<6.2`. Both locks resolve `django-celery-beat` 2.9.0 from PyPI and a Django version in `>=6.1.3,<6.2`. Both manifests and both locks carry the django override from the design. `cron-descriptor` in both locks satisfies `>=1.2.32,<2.0.0`. No chief manifest depends on `cron-descriptor` 2.x.
- Every other direct backend and vault dependency is an exact `==` pin of the locked version, extras unchanged. Direct `chief-backend-env` versions match across the two locks. Each holdback comment names the refused version and the reason. `FORBIDDEN_BEAT_REV` is absent. `[tool.uv.sources]` has no `django-celery-beat` entry. `dill` is not copied into a chief manifest.
- The standalone lock root stays `source = { virtual = "." }`.
- `./olib/scripts/orunr py test-all` exits 0.
- From the repo root, all three `docker build -f … .` commands exit 0.
- No file under `olib/` differs from `OLIB_GITLINK`. Dashboard JS, Compose postgres/redis/nginx tags, `infra/k8s/Dockerfile.static.stage`, and `OBSIDIAN_HEADLESS_VERSION` are unchanged.

**Commands:**

1. Write `test_python_django_runtime.py`. Run:

```bash
./olib/scripts/orunr py test "$PWD/backend/chief/tests/test_python_django_runtime.py"
```

Expected: non-zero. The new assertions fail on the Python 3.13 checkout, Django 5.2, and beat 2.8.1. A collection failure is not the expected red step.

2. Point the submodule at the toolchain commit. Do not edit files under `olib/`.

```bash
git -C olib fetch origin 791294d6d57b3707cea1838c0b6ac48c2f65b91d
git -C olib checkout --detach 791294d6d57b3707cea1838c0b6ac48c2f65b91d
```

`git -C olib rev-parse HEAD` prints `OLIB_GITLINK`. `git -C olib status --porcelain` is empty. If the fetch cannot see that commit, fetch the olib remote's default branch and check the commit out. If the submodule stays dirty, stop and report the dirty paths. Do not commit those paths.

3. Set `requires-python = ">=3.15,<3.16"` on the four chief members. In `backend/pyproject.toml`, set `Django>=6.1.3,<6.2` and `django-celery-beat==2.9.0`. Add this table entry to `[tool.uv]` in both `pyproject.toml` and `backend/pyproject.toml`:

```toml
override-dependencies = ["django>=6.1.3,<6.2"]
```

Leave beat's other requirements alone. Do not pin `cron-descriptor`. Do not add `[tool.uv.sources]` for beat. Do not add `dependency-metadata`.

4. Loosen every other direct requirement by deleting the version specifier and keeping extras. Django and beat stay as set in step 3. Backend names to loosen: `python-dotenv`, `django-environ`, `psycopg[binary]`, `psycopg[pool]`, `redis`, `celery`, `cryptography`, `jinja2`, `django-cors-headers`, `django-extensions`, `pydantic`, `openai`, `anthropic`, `PyYAML`, `uvicorn`, `uuid7`, `google-api-python-client`, `google-auth`, `dropbox`, `httpx`, `ruamel.yaml`. Vault names stay unpinned until step 6: `fastapi`, `uvicorn[standard]`, `httpx`.

5. Upgrade-lock the workspace, then the standalone backend, with `uv` on `PATH`:

```bash
uv lock --upgrade --python 3.15.2 --exclude-newer "14 days" --exclude-newer-package parproc=2100-01-01
standalone=$(mktemp -d)
cp backend/pyproject.toml "$standalone/pyproject.toml"
(
  cd "$standalone"
  uv lock --upgrade --python 3.15.2 --exclude-newer "14 days" --exclude-newer-package parproc=2100-01-01
)
cp "$standalone/uv.lock" backend/uv.lock
rm -rf "$standalone"
```

The first command rewrites `uv.lock` only. The standalone directory is outside the repo and receives only `backend/pyproject.toml`, never the workspace `pyproject.toml`. After the copy, the standalone `chief-backend-env` source is `{ "virtual": "." }`.

If `uv lock --upgrade` fails because one direct dependency other than `django-celery-beat` has no release that installs on this Python and Django, pin that dependency to the newest older release that the same command accepts. List candidates from `https://pypi.org/pypi/<pep503-name>/json` (`releases` keys that are not yanked). Try versions older than the refused one, newest first, with the other direct dependencies still loosened. Comment the line `# holdback: refused <version> because <reason from the resolver>`. Do not remove the dependency and do not add an override for it. The django override remains the only override. Retry until the upgrade lock exits 0. If Django 6.1.3 itself cannot be installed inside `>=6.1.3,<6.2`, stop and report that. Do not lower the Django range.

`git -C olib status --porcelain` must still be empty and HEAD must still be `OLIB_GITLINK`. If the lock dirties the submodule, stop and report the paths.

6. Rewrite the loosened requirements to the exact pins from the script above, using versions from the workspace `uv.lock`. Vault `fastapi`, `uvicorn[standard]`, and `httpx` use that same lock. Leave the Django range and `django-celery-beat==2.9.0` as they are.

7. Relock both places without `--upgrade`. Repeat the exclude-newer flags so uv does not treat the lock as stale and move versions:

```bash
uv lock --python 3.15.2 --exclude-newer "14 days" --exclude-newer-package parproc=2100-01-01
standalone=$(mktemp -d)
cp backend/pyproject.toml "$standalone/pyproject.toml"
(
  cd "$standalone"
  uv lock --python 3.15.2 --exclude-newer "14 days" --exclude-newer-package parproc=2100-01-01
)
cp "$standalone/uv.lock" backend/uv.lock
rm -rf "$standalone"
```

These two lockfiles are the ones that ship. Do not run `--upgrade` again unless a later holdback in step 10 changes a pin, and then run this step 7 again without `--upgrade`.

8. Recreate the venv only after both locks are written:

```bash
./olib/scripts/orun init --py --force
.venv/bin/python -c 'import sys; print(sys.version.split()[0])'
```

Expected print: `3.15.2`.

9. Re-run the new test file. Expected: exit 0. Then:

```bash
./olib/scripts/orunr py test-all
```

If it exits 0, go to step 11.

10. On a non-zero `py test-all`, classify the failure and stop or fix:

- A frame inside the `olib/` submodule: stop, report the output, do not patch the submodule, do not commit.
- `django-celery-beat` 2.9.0 does not run on Django 6.1 (import, startup, migration, or a failure whose traceback is inside `django_celery_beat`): stop and report that. Do not switch the pin to a git revision, do not add another override, and do not vendor the package. Do not commit.
- Otherwise change only chief code outside `olib/` so the same checks pass with the same behavior. When the fix changes logic, add a failing test that uses fixture content first; do not assert live page copy. When chief models must change, run `./olib/scripts/orunr django manage makemigrations` and commit only the files that command writes. `django-celery-beat` migrations stay inside that package. Do not edit dashboard JS, Compose postgres/redis/nginx tags, `infra/k8s/Dockerfile.static.stage`, or `OBSIDIAN_HEADLESS_VERSION`. If the only way to go green would edit those, stop and report.
- If chief code is adapted and a remaining failure comes from one direct dependency other than `django-celery-beat`, move that pin to the newest older non-yanked PyPI release (same JSON `releases` list, newest first) for which `./olib/scripts/orunr py test-all` and the three `docker build` commands pass. Update the holdback comment with the refused version and the reason. Run step 7, then step 8, then the gates again. Do not remove the dependency and do not add an override for it.

Repeat until `./olib/scripts/orunr py test-all` exits 0, or a stop rule fires.

11. From the repo root, build the three images. Do not drop `--frozen` or `--require-hashes` from the production install. If uv 0.13.9 rejects an existing export flag, change only the rejected flag and update the compose-config assertion that quotes it in this same commit.

```bash
docker build -f backend/Dockerfile.dev .
docker build -f backend/Dockerfile.prod .
docker build -f services/obsidian/Dockerfile .
```

Each command exits 0. A missing Docker daemon is a stop, not a skipped gate. If a build failure forces a file change, re-run `./olib/scripts/orunr py test-all` and the failing `docker build`.

12. `git -C olib status --porcelain` is empty. From the repo root, `git add olib` stages the gitlink only. Do not commit from inside `olib/`.

13. Commit: `chore(py): move Chief onto Python 3.15 and Django 6.1`
14. `git fetch origin main && git rebase origin/main && git push -u origin HEAD`

---

## S_final — Code review

**Test obligation:** code

Re-run the gates. Do not add a test that locks review prose.

1. From the worktree root, confirm every gate exits 0:

```bash
./olib/scripts/orunr py test-all
./olib/scripts/orunr py test-all --full
./olib/scripts/orunr js test-unit
./olib/scripts/orunr js lint
./olib/scripts/orunr js tsc
docker build -f backend/Dockerfile.dev .
docker build -f backend/Dockerfile.prod .
docker build -f services/obsidian/Dockerfile .
```

2. `git fetch origin main`, then `BASE_SHA=$(git merge-base HEAD origin/main)` and `HEAD_SHA=$(git rev-parse HEAD)`.
3. Dispatch `olib-reviewer` with the design path `docs/specs/2026-11-24-python-django-runtime/2026-11-24-python-django-runtime-design.md`, this plan path, `BASE_SHA`, `HEAD_SHA`, and the review file `docs/specs/2026-11-24-python-django-runtime/2026-11-24-python-django-runtime-review.md`.
4. Report findings. Track Status in that review file. Under `/ship` the ship skill sends findings to the implementer and re-verifies.
