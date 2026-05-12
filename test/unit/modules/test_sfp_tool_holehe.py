from __future__ import annotations

"""Tests for sfp_tool_holehe module."""

import csv
import json
import os

import pytest

from modules.sfp_tool_holehe import sfp_tool_holehe
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_module_base import TestModuleBase


def _root_event() -> SpiderFootEvent:
    """Build a valid ROOT SpiderFootEvent for use as a sourceEvent."""
    return SpiderFootEvent("ROOT", "alice@example.com", "", "")


class TestModuleToolHolehe(TestModuleBase):

    def test_opts(self):
        module = sfp_tool_holehe()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_holehe()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_tool_holehe()
        self.assertIsInstance(module.watchedEvents(), list)
        self.assertIn("EMAILADDR", module.watchedEvents())

    def test_producedEvents_should_return_list(self):
        module = sfp_tool_holehe()
        produced = module.producedEvents()
        self.assertIsInstance(produced, list)
        self.assertIn("ACCOUNT_EXTERNAL_OWNED", produced)
        self.assertIn("RAW_RIR_DATA", produced)

    def test_handleEvent_no_tool_path_and_not_on_PATH_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_holehe()
        module.setup(sf, {"holehe_path": ""})
        module.__name__ = "sfp_tool_holehe"

        target = SpiderFootTarget("alice@example.com", "EMAILADDR")
        module.setTarget(target)

        evt = SpiderFootEvent(
            "EMAILADDR", "alice@example.com", "test_seed", _root_event())

        import modules.sfp_tool_holehe as mod
        original_which = mod.shutil.which
        mod.shutil.which = lambda *_a, **_kw: None
        try:
            result = module.handleEvent(evt)
        finally:
            mod.shutil.which = original_which

        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    def test_build_args_includes_required_flags(self):
        module = sfp_tool_holehe()
        module.opts = dict(sfp_tool_holehe.opts)
        args = module._build_args("/tools/bin/holehe", "alice@example.com")
        self.assertEqual(args[0], "/tools/bin/holehe")
        self.assertIn("--only-used", args)
        self.assertIn("--no-color", args)
        self.assertIn("--no-clear", args)
        self.assertIn("-C", args)
        self.assertIn("alice@example.com", args)

    def test_handleEvent_emits_account_events_from_csv(self):
        """Stub holehe execution end-to-end with a fake binary + CSV file."""
        import modules.sfp_tool_holehe as mod

        sf = SpiderFoot(self.default_options)
        module = sfp_tool_holehe()
        module.setup(sf, {"holehe_path": "/fake/holehe"})
        target = SpiderFootTarget("alice@example.com", "EMAILADDR")
        module.setTarget(target)

        module._resolve_binary = lambda: "/fake/holehe"
        module.__name__ = "sfp_tool_holehe"

        class _StubProc:
            returncode = 0
            def communicate(self, timeout=None):
                return (b"", b"")
            def kill(self):
                pass

        # Mimic holehe writing a CSV into cwd.
        rows = [
            {
                "name": "twitter",
                "domain": "twitter.com",
                "method": "register",
                "frequent_rate_limit": "False",
                "rateLimit": "False",
                "exists": "True",
                "emailrecovery": "",
                "phoneNumber": "",
                "others": "",
            },
            {
                "name": "instagram",
                "domain": "instagram.com",
                "method": "register",
                "frequent_rate_limit": "False",
                "rateLimit": "False",
                "exists": "False",
                "emailrecovery": "",
                "phoneNumber": "",
                "others": "",
            },
        ]

        def _fake_popen(args, **kw):
            cwd = kw.get("cwd")
            assert cwd is not None, "holehe must be invoked with cwd=tmpdir"
            csv_path = os.path.join(
                cwd, "holehe_20260101_alice_results.csv")
            with open(csv_path, "w", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            return _StubProc()

        original_popen = mod.Popen
        mod.Popen = _fake_popen

        emitted = []
        module.notifyListeners = lambda e: emitted.append(e)

        try:
            module.handleEvent(SpiderFootEvent(
                "EMAILADDR", "alice@example.com", "test_seed", _root_event()))
        finally:
            mod.Popen = original_popen

        types = [e.eventType for e in emitted]
        self.assertIn("RAW_RIR_DATA", types)
        account_events = [e for e in emitted if e.eventType == "ACCOUNT_EXTERNAL_OWNED"]
        # only the row with exists=True
        self.assertEqual(len(account_events), 1)
        self.assertIn("twitter", account_events[0].data)
        self.assertIn("https://twitter.com", account_events[0].data)

    def test_is_truthy_helper(self):
        from modules.sfp_tool_holehe import _is_truthy
        self.assertTrue(_is_truthy(True))
        self.assertTrue(_is_truthy("True"))
        self.assertTrue(_is_truthy("true"))
        self.assertTrue(_is_truthy("1"))
        self.assertFalse(_is_truthy(False))
        self.assertFalse(_is_truthy("False"))
        self.assertFalse(_is_truthy(""))
        self.assertFalse(_is_truthy(None))
