from __future__ import annotations

"""Tests for sfp_tool_ghunt module."""

import json
import os

import pytest

from modules.sfp_tool_ghunt import sfp_tool_ghunt
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_module_base import TestModuleBase


def _root_event() -> SpiderFootEvent:
    """Build a valid ROOT SpiderFootEvent for use as a sourceEvent."""
    return SpiderFootEvent("ROOT", "alice@example.com", "", "")


class TestModuleToolGhunt(TestModuleBase):

    def test_opts(self):
        module = sfp_tool_ghunt()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_ghunt()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_tool_ghunt()
        self.assertIsInstance(module.watchedEvents(), list)
        self.assertIn("EMAILADDR", module.watchedEvents())

    def test_producedEvents_should_return_list(self):
        module = sfp_tool_ghunt()
        produced = module.producedEvents()
        self.assertIsInstance(produced, list)
        self.assertIn("ACCOUNT_EXTERNAL_OWNED", produced)
        self.assertIn("SOCIAL_MEDIA", produced)
        self.assertIn("HUMAN_NAME", produced)
        self.assertIn("RAW_RIR_DATA", produced)

    def test_handleEvent_missing_creds_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_ghunt()
        module.setup(sf, {"ghunt_path": "/fake/ghunt"})
        module.__name__ = "sfp_tool_ghunt"

        target = SpiderFootTarget("alice@example.com", "EMAILADDR")
        module.setTarget(target)

        # Force the creds check to fail.
        module._creds_present = staticmethod(lambda: False)

        evt = SpiderFootEvent(
            "EMAILADDR", "alice@example.com", "test_seed", _root_event())
        result = module.handleEvent(evt)

        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    def test_handleEvent_no_tool_path_and_not_on_PATH_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_ghunt()
        module.setup(sf, {"ghunt_path": ""})
        module.__name__ = "sfp_tool_ghunt"

        # Pretend creds exist so we get past that check and exercise the
        # binary-resolution branch.
        module._creds_present = staticmethod(lambda: True)

        target = SpiderFootTarget("alice@example.com", "EMAILADDR")
        module.setTarget(target)

        evt = SpiderFootEvent(
            "EMAILADDR", "alice@example.com", "test_seed", _root_event())

        import modules.sfp_tool_ghunt as mod
        original_which = mod.shutil.which
        mod.shutil.which = lambda *_a, **_kw: None
        try:
            result = module.handleEvent(evt)
        finally:
            mod.shutil.which = original_which

        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    def test_build_args_includes_required_flags(self):
        module = sfp_tool_ghunt()
        module.opts = dict(sfp_tool_ghunt.opts)
        args = module._build_args(
            "/tools/bin/ghunt", "alice@example.com", "/tmp/ghunt.json")
        self.assertEqual(args[0], "/tools/bin/ghunt")
        self.assertEqual(args[1], "email")
        self.assertEqual(args[2], "alice@example.com")
        self.assertIn("--json", args)
        self.assertIn("/tmp/ghunt.json", args)

    def test_handleEvent_emits_events_from_report(self):
        """Stub ghunt execution end-to-end with a fake binary + report file."""
        import modules.sfp_tool_ghunt as mod

        fake_report = {
            "PROFILE_CONTAINER": {
                "profile": {
                    "names": [{"fullname": "Alice Example"}],
                    "personId": "1234567890",
                }
            },
            "services": [
                {
                    "name": "YouTube",
                    "url": "https://youtube.com/channel/abc",
                    "category": "Google",
                },
                {
                    "name": "Maps",
                    "url": "https://maps.google.com/contributions/abc",
                },
                "ignored-non-dict",
            ],
        }

        sf = SpiderFoot(self.default_options)
        module = sfp_tool_ghunt()
        module.setup(sf, {"ghunt_path": "/fake/ghunt"})
        target = SpiderFootTarget("alice@example.com", "EMAILADDR")
        module.setTarget(target)

        module._resolve_binary = lambda: "/fake/ghunt"
        module._creds_present = staticmethod(lambda: True)
        module._parse_report = staticmethod(lambda _p: fake_report)
        module.__name__ = "sfp_tool_ghunt"

        class _StubProc:
            returncode = 0
            def communicate(self, timeout=None):
                return (b"", b"")
            def kill(self):
                pass

        def _fake_popen(args, **kw):
            try:
                # ghunt CLI: ghunt email <email> --json <outfile>
                outfile = args[args.index("--json") + 1]
                with open(outfile, "w") as fh:
                    json.dump(fake_report, fh)
            except Exception:
                pass
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
        self.assertIn("HUMAN_NAME", types)
        self.assertIn("SOCIAL_MEDIA", types)
        account_events = [e for e in emitted if e.eventType == "ACCOUNT_EXTERNAL_OWNED"]
        self.assertEqual(len(account_events), 2)
        joined = "\n".join(e.data for e in account_events)
        self.assertIn("YouTube", joined)
        self.assertIn("Maps", joined)
        human = [e for e in emitted if e.eventType == "HUMAN_NAME"]
        self.assertEqual(human[0].data, "Alice Example")
        social = [e for e in emitted if e.eventType == "SOCIAL_MEDIA"]
        self.assertIn("1234567890", social[0].data)
