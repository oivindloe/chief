# Copyright 2024 Øivind Loe
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0 (the "License");
# See LICENSE file or http://www.apache.org/licenses/LICENSE-2.0 for details.
# ~
"""Verify Python 3.15, Django 6.1, lock pins, and the olib toolchain gitlink."""

import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from olib.py.django.test.cases import OTestCase

OLIB_GITLINK = '3e58ccffbb32c7cfdf4974dff742730141cec061'
FORBIDDEN_BEAT_REV = '0ee32beb51ebcfe4198d47f075e43db4d1b5aa9a'
DJANGO_RANGE = '>=6.1.3,<6.2'
BEAT_PIN = 'django-celery-beat==2.9.0'
DJANGO_OVERRIDE = 'django>=6.1.3,<6.2'
REQUIRES_PYTHON = '>=3.15,<3.16'

HOLDBACK_PATTERN = re.compile(r'holdback: refused (?P<version>\d+\.\d+(?:\.\d+)?) because (?P<reason>.+)$')


def _repo_root() -> Path:
    """Return the chief repository root (parent of ``backend/``)."""
    return Path(__file__).resolve().parents[3]


def _load_toml(path: Path) -> dict[str, Any]:
    """Parse a TOML file into a plain dict."""
    return tomllib.loads(path.read_text(encoding='utf-8'))


def _pep503(name: str) -> str:
    """Normalize a distribution name the way uv records it in lockfiles."""
    return re.sub(r'[-_.]+', '-', name).lower()


def _numeric_version(version: str) -> tuple[int, ...]:
    """Return leading dotted integer components, stopping at the first non-digit part."""
    parts: list[int] = []
    for segment in version.split('.'):
        if not segment.isdigit():
            break
        parts.append(int(segment))
    return tuple(parts)


def _package_versions(lock: dict[str, Any]) -> dict[str, str]:
    """Map locked package name to version for every ``[[package]]`` entry that has one."""
    return {package['name']: package['version'] for package in lock['package'] if 'version' in package}


def _virtual_root(lock: dict[str, Any], name: str) -> dict[str, Any]:
    """Return the workspace virtual-root package table for ``name``."""
    for package in lock['package']:
        if package.get('name') == name:
            return dict(package)
    raise AssertionError(f'lock has no virtual root {name!r}')


def _dependency_lines(pyproject: dict[str, Any]) -> list[str]:
    """Return raw dependency requirement strings from a pyproject ``project`` table."""
    return list(pyproject['project']['dependencies'])


def _dependency_lines_raw(path: Path) -> list[str]:
    """Parse ``project.dependencies`` from manifest source, keeping inline ``#`` comments."""
    lines_out: list[str] = []
    in_deps = False
    for line in path.read_text(encoding='utf-8').splitlines():
        if not in_deps:
            if re.match(r'^\s*dependencies\s*=\s*\[\s*$', line):
                in_deps = True
            continue
        if re.match(r'^\s*\]\s*,?\s*$', line):
            break
        match = re.match(r'^\s*"(?P<body>[^"]*)"\s*,?\s*(?P<comment>#.*)?\s*$', line)
        if match is not None:
            comment = match.group('comment') or ''
            lines_out.append(f'{match.group("body")}{comment}')
    return lines_out


class TestPythonDjangoRuntimePins(OTestCase):
    """Check interpreter, locks, Django range, beat pin, and olib submodule alignment."""

    def test_olib_checkout_is_the_315_toolchain(self) -> None:
        """``olib`` HEAD matches the pinned toolchain commit with a clean tree."""
        root = _repo_root()
        head = subprocess.run(
            ['git', '-C', str(root / 'olib'), 'rev-parse', 'HEAD'],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ['git', '-C', str(root / 'olib'), 'status', '--porcelain'],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        olib_project = _load_toml(root / 'olib/pyproject.toml')['project']

        self.assertEqual(head, OLIB_GITLINK)
        self.assertEqual(status, '')
        self.assertEqual(olib_project['requires-python'], REQUIRES_PYTHON)

    def test_precommit_symlink_selects_python315(self) -> None:
        """Pre-commit config is the olib symlink and targets Python 3.15."""
        root = _repo_root()
        precommit = root / '.pre-commit-config.yaml'
        text = precommit.read_text(encoding='utf-8')

        self.assertTrue(precommit.is_symlink())
        self.assertEqual(precommit.readlink(), Path('olib/.pre-commit-config.yaml'))
        self.assertIn('python: python3.15', text)
        self.assertNotIn('python: python3.13', text)

    def test_workspace_members_require_python_315(self) -> None:
        """Each chief workspace member declares Python 3.15 and root uv workspace metadata."""
        root = _repo_root()
        paths = (
            'pyproject.toml',
            'backend/pyproject.toml',
            'infra/pyproject.toml',
            'services/obsidian/pyproject.toml',
        )
        root_doc = _load_toml(root / 'pyproject.toml')
        tool_uv = root_doc['tool']['uv']

        for relative in paths:
            doc = _load_toml(root / relative)
            self.assertEqual(doc['project']['requires-python'], REQUIRES_PYTHON)

        self.assertFalse(tool_uv.get('package', True))
        self.assertEqual(tool_uv['index-strategy'], 'first-index')
        self.assertEqual(
            tool_uv['workspace']['members'],
            ['backend', 'infra', 'olib', 'services/obsidian'],
        )

    def test_locks_record_python_315_star(self) -> None:
        """Workspace and standalone backend locks target ``==3.15.*``."""
        root = _repo_root()
        for name in ('uv.lock', 'backend/uv.lock'):
            lock = _load_toml(root / name)
            self.assertEqual(lock['requires-python'], '==3.15.*')

    def test_django_range_and_beat_override(self) -> None:
        """Django range, beat 2.9.0, overrides, and lock resolution match the design."""
        root = _repo_root()
        root_doc = _load_toml(root / 'pyproject.toml')
        backend_doc = _load_toml(root / 'backend/pyproject.toml')
        workspace_lock = _load_toml(root / 'uv.lock')
        backend_lock = _load_toml(root / 'backend/uv.lock')
        deps = _dependency_lines(backend_doc)

        self.assertIn(f'Django{DJANGO_RANGE}', [d.split('#', 1)[0].strip() for d in deps])
        self.assertIn(BEAT_PIN, [d.split('#')[0].strip() for d in deps])
        self.assertTrue(all(not dep.startswith('Django==') for dep in deps))

        root_override = root_doc['tool']['uv'].get('override-dependencies', [])
        backend_override = backend_doc['tool']['uv'].get('override-dependencies', [])
        self.assertEqual(root_override, [DJANGO_OVERRIDE])
        self.assertEqual(backend_override, [DJANGO_OVERRIDE])

        for doc in (root_doc, backend_doc):
            self.assertNotIn('dependency-metadata', doc.get('tool', {}).get('uv', {}))
            sources = doc.get('tool', {}).get('uv', {}).get('sources', {})
            self.assertNotIn('django-celery-beat', sources)

        expected_override = [{'name': 'django', 'specifier': '>=6.1.3,<6.2'}]
        self.assertEqual(workspace_lock['manifest'].get('overrides'), expected_override)
        self.assertEqual(backend_lock['manifest'].get('overrides'), expected_override)

        for lock in (workspace_lock, backend_lock):
            versions = _package_versions(lock)
            beat = next(p for p in lock['package'] if p['name'] == 'django-celery-beat')
            self.assertEqual(beat['version'], '2.9.0')
            self.assertEqual(beat['source'], {'registry': 'https://pypi.org/simple'})
            django_version = versions['django']
            self.assertGreaterEqual(_numeric_version(django_version), (6, 1, 3))
            self.assertLess(_numeric_version(django_version), (6, 2))

        for path in (
            root / 'pyproject.toml',
            root / 'backend/pyproject.toml',
            root / 'uv.lock',
            root / 'backend/uv.lock',
            root / 'services/obsidian/pyproject.toml',
        ):
            self.assertNotIn(FORBIDDEN_BEAT_REV, path.read_text(encoding='utf-8'))

    def test_cron_descriptor_stays_on_1_x(self) -> None:
        """Locks keep cron-descriptor on 1.x and no chief manifest lists it directly."""
        root = _repo_root()
        manifests = (
            _load_toml(root / 'pyproject.toml'),
            _load_toml(root / 'backend/pyproject.toml'),
            _load_toml(root / 'infra/pyproject.toml'),
            _load_toml(root / 'services/obsidian/pyproject.toml'),
        )
        for doc in manifests:
            for dep in _dependency_lines(doc):
                name = re.match(r'([A-Za-z0-9_.-]+)', dep.strip())
                self.assertIsNotNone(name)
                if name and _pep503(name.group(1)) == 'cron-descriptor':
                    self.fail(f'unexpected direct cron-descriptor dependency: {dep}')

        for lock_name in ('uv.lock', 'backend/uv.lock'):
            versions = _package_versions(_load_toml(root / lock_name))
            version = versions['cron-descriptor']
            numeric = _numeric_version(version)
            self.assertGreaterEqual(numeric, (1, 2, 32))
            self.assertLess(numeric, (2,))

    def test_direct_pins_match_locked_versions(self) -> None:
        """Direct backend and vault deps are exact pins aligned with both locks."""
        root = _repo_root()
        workspace_lock = _load_toml(root / 'uv.lock')
        backend_lock = _load_toml(root / 'backend/uv.lock')
        locked = _package_versions(workspace_lock)
        backend_deps = _dependency_lines(_load_toml(root / 'backend/pyproject.toml'))
        vault_deps = _dependency_lines(_load_toml(root / 'services/obsidian/pyproject.toml'))

        for dep in backend_deps + vault_deps:
            stripped = dep.split('#')[0].strip()
            if stripped.startswith('Django'):
                continue
            self.assertIn('==', stripped, msg=f'expected exact pin: {dep}')
            match = re.fullmatch(r'([A-Za-z0-9_.-]+)(\[[^\]]+\])?==(.+)', stripped)
            self.assertIsNotNone(match, msg=f'unparsed pin: {dep}')
            assert match is not None
            name, extras, version = match.group(1), match.group(2) or '', match.group(3)
            lock_version = locked[_pep503(name)]
            self.assertEqual(version, lock_version, msg=f'{name}{extras}')

        self.assertTrue(any('psycopg[binary]==' in d for d in backend_deps))
        self.assertTrue(any('psycopg[pool]==' in d for d in backend_deps))
        self.assertTrue(any(d.startswith('uvicorn==') and '[' not in d for d in backend_deps))
        self.assertTrue(any('uvicorn[standard]==' in d for d in vault_deps))
        for name in ('dropbox', 'fastapi', 'httpx'):
            backend_has = any(d.split('#')[0].strip().startswith(f'{name}==') for d in backend_deps)
            vault_has = any(d.split('#')[0].strip().startswith(f'{name}==') for d in vault_deps)
            if name == 'dropbox':
                self.assertTrue(backend_has)
            else:
                self.assertTrue(vault_has)

        ws_root = _virtual_root(workspace_lock, 'chief-backend-env')
        be_root = _virtual_root(backend_lock, 'chief-backend-env')
        self.assertEqual(ws_root['source'], {'virtual': 'backend'})
        self.assertEqual(be_root['source'], {'virtual': '.'})

        ws_versions = {
            dep['name']: _package_versions(workspace_lock).get(dep['name']) for dep in ws_root.get('dependencies', [])
        }
        be_versions = {
            dep['name']: _package_versions(backend_lock).get(dep['name']) for dep in be_root.get('dependencies', [])
        }
        self.assertEqual(ws_versions, be_versions)

        for doc_path in (
            'pyproject.toml',
            'backend/pyproject.toml',
            'infra/pyproject.toml',
            'services/obsidian/pyproject.toml',
        ):
            for dep in _dependency_lines(_load_toml(root / doc_path)):
                self.assertNotIn('dill', dep.lower())

        for manifest in (root / 'backend/pyproject.toml', root / 'services/obsidian/pyproject.toml'):
            for dep in _dependency_lines_raw(manifest):
                base = dep.split('#', 1)[0].strip()
                if base.startswith(('Django', 'django-celery-beat')):
                    self.assertNotIn('#', dep, msg=f'no holdback on {base}')
                    continue
                if '#' not in dep:
                    continue
                comment = dep.split('#', 1)[1].strip()
                holdback_match = HOLDBACK_PATTERN.match(comment)
                self.assertIsNotNone(holdback_match, msg=f'invalid holdback comment: {dep}')
                assert holdback_match is not None
                self.assertTrue(holdback_match.group('reason').strip())

    def test_venv_interpreter_reports_3152(self) -> None:
        """The project venv runs CPython 3.15.2."""
        root = _repo_root()
        completed = subprocess.run(
            [str(root / '.venv/bin/python'), '-c', 'import sys; print(sys.version.split()[0])'],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.stdout.strip(), '3.15.2')
