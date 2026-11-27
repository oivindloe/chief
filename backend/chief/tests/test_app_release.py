# Copyright 2024 Øivind Loe
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0 (the "License");
# See LICENSE file or http://www.apache.org/licenses/LICENSE-2.0 for details.
# ~
"""Chief image manifest, static Dockerfile contract, and workflow layout."""

import contextlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import parproc as pp

from olib.py.cli.run.templates.buildArgoService import ClusterInfo as DeployClusterInfo
from olib.py.cli.run.templates.buildArgoService import (
    _implementApp,
    deploy_target_names,
)
from olib.py.django.test.cases import OTestCase
from olib.py.infra.images.manifest import load_manifest
from olib.py.infra.site import cdns as site_cdns
from olib.py.infra.site import promotion_repositories, registries

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import config  # noqa: E402

_BINDINGS = [
    ('dev', 'backend', 'release', 'chief-stage'),
    ('dev', 'static', 'stage', 'chief-stage'),
]


class AppReleaseTests(OTestCase):
    def test_images_manifest_matches_the_release_table(self) -> None:
        """images.yml matches backend/static recipes, bindings, and the chief-stage promotion."""
        with contextlib.chdir(REPOSITORY_ROOT):
            loaded = load_manifest(Path('images.yml'), registries, config.Config.promotions)
        self.assertEqual(loaded.severities, ['CRITICAL'])

        backend = loaded.images['backend']
        self.assertEqual(backend.repository, 'apps/chief/backend')
        self.assertEqual(backend.context, '.')
        self.assertEqual(backend.consumers, ['backend', 'celery-worker', 'celery-beat'])
        release = backend.variants['release']
        self.assertEqual(release.dockerfile, 'backend/Dockerfile.prod')
        self.assertEqual(release.requires, [])
        self.assertEqual(release.tag_strategy, 'git')
        self.assertEqual(release.verify_strategy, 'registry-digest')

        static = loaded.images['static']
        self.assertEqual(static.repository, 'apps/chief/static')
        self.assertEqual(static.context, '.')
        self.assertEqual(static.consumers, ['static'])
        stage = static.variants['stage']
        self.assertEqual(stage.dockerfile, 'infra/k8s/Dockerfile.static.stage')
        self.assertEqual(stage.requires, ['django.collectstatic::backend'])
        self.assertEqual(stage.tag_strategy, 'git')
        self.assertEqual(stage.verify_strategy, 'registry-digest')

        self.assertEqual(set(loaded.images), {'backend', 'static'})

        binding_rows = [
            (binding.registry.name, binding.image, binding.variant, binding.promotion.name)
            for binding in loaded.bindings
        ]
        self.assertEqual(binding_rows, _BINDINGS)
        for binding in loaded.bindings:
            self.assertEqual(binding.expect_success_within_seconds, 0)

        promo = config.Config.promotions['chief-stage']
        self.assertEqual(promo.name, 'chief-stage')
        self.assertEqual(promo.key, 'images')
        self.assertEqual(promo.values_file, 'chief/chief-stage/values.yml')
        self.assertEqual(promo.repository, promotion_repositories['env'])

        dockerfile_paths = [
            variant.dockerfile for image in loaded.images.values() for variant in image.variants.values()
        ]
        self.assertNotIn('backend/Dockerfile.dev', dockerfile_paths)
        self.assertNotIn('services/obsidian/Dockerfile', dockerfile_paths)

    def test_static_dockerfile_copies_collected_static(self) -> None:
        """Stage static image ships collected backend static files into nginx storage."""
        dockerfile = (REPOSITORY_ROOT / 'infra/k8s/Dockerfile.static.stage').read_text(encoding='utf-8')
        self.assertIn(
            'COPY --chown=nginx:nginx backend/.output/static /etc/storage/public/static',
            dockerfile,
        )

    def test_workflow_file_stays_the_dev_test_workflow(self) -> None:
        """Chief keeps a single olib dev-test workflow and does not add release automation."""
        workflows = list((REPOSITORY_ROOT / '.github/workflows').iterdir())
        self.assertEqual([path.name for path in workflows], ['olib-dev-test-all.yml'])

    def test_clusters_omit_registry_fields(self) -> None:
        """Stage deploys through image release and shares the site CDN table."""
        self.assertIs(config.Config.cdns, site_cdns)
        stage = cast(config.ClusterInfo, config.Config.clusters['chief-stage'])
        self.assertEqual(stage.docker_images, {})
        self.assertIsNone(stage.registry_url)
        self.assertIsNone(stage.registry_ca_cert_path)
        self.assertEqual(stage.cdn, 'onas')
        self.assertEqual(stage.release_name, 'chief-stage')
        self.assertEqual(stage.cluster, 'dev')
        self.assertEqual(stage.host, 'https://chief.dev.oivindloe.com')
        self.assertEqual(stage.static_dir, 'backend/.output/static')
        self.assertEqual(stage.version_tag_prefix, 'chief')
        self.assertEqual(stage.version_increments, ['debug'])
        self.assertFalse(stage.version_push_tag)
        self.assertTrue(stage.default)
        compose = config.Config.clusters['compose']
        self.assertEqual(compose.release_name, 'compose')
        with contextlib.chdir(REPOSITORY_ROOT):
            targets = deploy_target_names(config.Config.clusters, Path('images.yml'))
        self.assertEqual(targets, ['chief-stage'])

    def test_deploy_graph_waits_on_both_releases(self) -> None:
        """k8s.write-env and k8s.deploy wait on dev backend and static releases."""
        with contextlib.chdir(REPOSITORY_ROOT):
            chief_stage = cast(config.ClusterInfo, config.Config.clusters['chief-stage'])
            cluster_map = cast(dict[str, DeployClusterInfo], {'chief-stage': chief_stage})
            context = SimpleNamespace(params={'config': SimpleNamespace(clusters=cluster_map)})
            with patch.dict(pp.get_protos(), clear=True), patch.dict(pp.get_procs(), clear=True):
                _implementApp(cluster_map)
                write_proto = pp.get_protos()['k8s.write-env::[target]']
                write_deps = write_proto.deps[0](context, target='chief-stage')
                self.assertIn('image.release::dev::backend::chief-stage', write_deps)
                self.assertIn('image.release::dev::static::chief-stage', write_deps)
                self.assertNotIn('k8s.build-images::[target]', write_deps)
                deploy_proto = pp.get_protos()['k8s.deploy::[target]']
                deploy_deps = deploy_proto.deps[0](context, target='chief-stage')
                self.assertIn('k8s.write-env::[target]', deploy_deps)
                self.assertIn('image.release::dev::backend::chief-stage', deploy_deps)
                self.assertIn('image.release::dev::static::chief-stage', deploy_deps)
                self.assertNotIn('k8s.build-image-sboms::[target]', deploy_deps)

    def test_cdn_upload_remains_a_reverse_dependency_of_deploy(self) -> None:
        """CDN upload still runs ahead of deploy via the existing rdep edge."""
        self.assertEqual(pp.get_protos()['cdn.upload::[target]'].rdeps, ['k8s.deploy::[target]'])
