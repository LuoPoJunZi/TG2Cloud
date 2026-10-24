"""Stdlib-only proxy rendering compatibility, including the host Python floor."""
from __future__ import annotations

import unittest

from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.proxy import manager, rendering
from tg2cloud.deployment.proxy.state import empty_state, state_with_route


class RenderingCompatibilityTests(unittest.TestCase):
    def test_old_imports_are_the_actual_shared_implementation(self):
        for name in ("render_certbot_loop", "render_compose", "render_nginx_conf", "render_default_conf",
                     "render_bootstrap_conf", "render_route_conf", "render_config_set"):
            self.assertIs(getattr(manager, name), getattr(rendering, name))

    def test_two_management_routes_and_acme_keep_their_existing_boundaries(self):
        state = empty_state()
        for edition in ("clouddrive2", "openlist"):
            state = state_with_route(state, PRODUCTS[edition], edition + '.example.test')
        files = rendering.render_config_set(state, candidate_domain='candidate.example.test')
        self.assertIn('conf.d/10-acme-bootstrap.conf', files)
        for edition in ('clouddrive2', 'openlist'):
            route = files['conf.d/20-' + edition + '.conf']
            self.assertIn('location = /dav', route)
            self.assertIn('return 403', route)
        self.assertEqual(manager.render_config_set(state), rendering.render_config_set(state))
