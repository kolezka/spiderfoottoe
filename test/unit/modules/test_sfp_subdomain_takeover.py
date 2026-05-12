from __future__ import annotations

"""Tests for sfp_subdomain_takeover module."""

import pytest
import unittest

from modules.sfp_subdomain_takeover import sfp_subdomain_takeover
from spiderfoot.sflib import SpiderFoot
from test.unit.utils.test_module_base import TestModuleBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleSubdomain_takeover(TestModuleBase):

    def test_opts(self):
        module = sfp_subdomain_takeover()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_subdomain_takeover()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_subdomain_takeover()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_subdomain_takeover()
        self.assertIsInstance(module.producedEvents(), list)

    def test_normalise_fingerprints_handles_edoverflow_schema(self):
        """EdOverflow's schema uses string fingerprints, sometimes missing."""
        raw = [
            # Single-string fingerprint — must be wrapped in a list.
            {"service": "Heroku", "cname": ["herokuapp.com"],
             "fingerprint": "There's nothing here, yet.", "nxdomain": False},
            # Already a list — pass through.
            {"service": "GitHub", "cname": ["github.io"],
             "fingerprint": ["There isn't a GitHub Pages site here."],
             "nxdomain": False},
            # NXDOMAIN-only entry: no fingerprint at all.
            {"service": "AWS/EB", "cname": ["elasticbeanstalk.com"],
             "nxdomain": True},
            # Missing cname — drop entirely.
            {"service": "Bogus", "fingerprint": "x", "nxdomain": False},
            # Single-string cname — coerce to list.
            {"service": "Coerce", "cname": "single.example.com",
             "fingerprint": "marker", "nxdomain": False},
        ]
        out = sfp_subdomain_takeover._normalise_fingerprints(raw)
        services = [e["service"] for e in out]
        self.assertEqual(services, ["Heroku", "GitHub", "AWS/EB", "Coerce"])
        # Fingerprint is always a list.
        for e in out:
            self.assertIsInstance(e["cname"], list)
            self.assertIsInstance(e["fingerprint"], list)
            self.assertIsInstance(e["nxdomain"], bool)
        # NXDOMAIN-only entry has empty fingerprint list (not missing).
        nx = next(e for e in out if e["service"] == "AWS/EB")
        self.assertEqual(nx["fingerprint"], [])
        self.assertTrue(nx["nxdomain"])
        # Coerced cname.
        coerce = next(e for e in out if e["service"] == "Coerce")
        self.assertEqual(coerce["cname"], ["single.example.com"])

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
