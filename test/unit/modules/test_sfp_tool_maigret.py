from __future__ import annotations

"""Tests for sfp_tool_maigret module."""

import json
import os

import pytest

from modules.sfp_tool_maigret import sfp_tool_maigret
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_module_base import TestModuleBase


def _root_event() -> SpiderFootEvent:
    """Build a valid ROOT SpiderFootEvent for use as a sourceEvent."""
    return SpiderFootEvent("ROOT", "alice", "", "")


class TestModuleToolMaigret(TestModuleBase):

    def test_opts(self):
        module = sfp_tool_maigret()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_maigret()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_tool_maigret()
        self.assertIsInstance(module.watchedEvents(), list)
        self.assertIn("USERNAME", module.watchedEvents())

    def test_producedEvents_should_return_list(self):
        module = sfp_tool_maigret()
        produced = module.producedEvents()
        self.assertIsInstance(produced, list)
        self.assertIn("ACCOUNT_EXTERNAL_OWNED", produced)
        self.assertIn("RAW_RIR_DATA", produced)

    def test_handleEvent_no_tool_path_and_not_on_PATH_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_maigret()
        module.setup(sf, {"maigret_path": ""})

        target = SpiderFootTarget("alice", "USERNAME")
        module.setTarget(target)

        evt = SpiderFootEvent("USERNAME", "alice", "test_seed", _root_event())

        # Force shutil.which to return None so PATH lookup fails.
        import modules.sfp_tool_maigret as mod
        original_which = mod.shutil.which
        mod.shutil.which = lambda *_a, **_kw: None
        try:
            result = module.handleEvent(evt)
        finally:
            mod.shutil.which = original_which

        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    def test_build_args_includes_required_flags(self):
        module = sfp_tool_maigret()
        module.opts = dict(sfp_tool_maigret.opts)
        args = module._build_args("/tools/bin/maigret", "alice", "/tmp/out")
        self.assertEqual(args[0], "/tools/bin/maigret")
        self.assertEqual(args[1], "alice")
        self.assertIn("--json", args)
        self.assertIn("simple", args)
        self.assertIn("--folderoutput", args)
        self.assertIn("/tmp/out", args)
        self.assertIn("--no-progressbar", args)

    def test_build_args_optional_flags(self):
        module = sfp_tool_maigret()
        module.opts = dict(sfp_tool_maigret.opts)
        module.opts["use_disabled_sites"] = True
        module.opts["tags"] = "us,photo"
        module.opts["top_sites"] = 100
        args = module._build_args("/tools/bin/maigret", "alice", "/tmp/out")
        self.assertIn("--use-disabled-sites", args)
        self.assertIn("--tags", args)
        self.assertIn("us,photo", args)
        self.assertIn("--top-sites", args)
        self.assertIn("100", args)

    def test_handleEvent_emits_account_events_from_report(self, tmp_path=None):
        """Stub maigret execution end-to-end with a fake binary + report file."""
        import subprocess as real_subprocess
        import modules.sfp_tool_maigret as mod
        import tempfile

        fake_report = {
            "GitHub": {
                "status": "Claimed",
                "url_user": "https://github.com/alice",
                "tags": ["coding", "us"],
            },
            "NotFoundSite": {
                "status": "Available",
                "url_user": "https://notfound.example/alice",
            },
            "WeirdShape": "ignored-non-dict",
        }

        # Replace the resolution + the report parsing so we don't need a real binary.
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_maigret()
        module.setup(sf, {"maigret_path": "/fake/maigret"})
        target = SpiderFootTarget("alice", "USERNAME")
        module.setTarget(target)

        # Patch _resolve_binary so we don't depend on filesystem state.
        module._resolve_binary = lambda: "/fake/maigret"
        # Patch _parse_report to return our canned dict regardless of file.
        module._parse_report = staticmethod(lambda _p: fake_report)
        # The scan loader normally assigns self.__name__ — replicate that here.
        module.__name__ = "sfp_tool_maigret"

        # Stub Popen to write the expected report file then exit 0.
        class _StubProc:
            returncode = 0
            def communicate(self, timeout=None):
                return (b"", b"")
            def kill(self):
                pass

        def _fake_popen(args, **kw):
            # Find the --folderoutput value and create the expected file there.
            try:
                outdir = args[args.index("--folderoutput") + 1]
                username = args[1]
                with open(os.path.join(outdir, f"report_{username}_simple.json"), "w") as fh:
                    json.dump(fake_report, fh)
            except Exception:
                pass
            return _StubProc()

        original_popen = mod.Popen
        mod.Popen = _fake_popen

        emitted = []
        module.notifyListeners = lambda e: emitted.append(e)

        try:
            module.handleEvent(SpiderFootEvent("USERNAME", "alice", "test_seed", _root_event()))
        finally:
            mod.Popen = original_popen

        # We expect: 1 RAW_RIR_DATA + 1 ACCOUNT_EXTERNAL_OWNED (only the Claimed one)
        types = [e.eventType for e in emitted]
        self.assertIn("RAW_RIR_DATA", types)
        account_events = [e for e in emitted if e.eventType == "ACCOUNT_EXTERNAL_OWNED"]
        self.assertEqual(len(account_events), 1)
        self.assertIn("github.com/alice", account_events[0].data)
        self.assertIn("Category: coding, us", account_events[0].data)
