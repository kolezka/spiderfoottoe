from __future__ import annotations

"""Tests for sfp_tool_sherlock module."""

import os

import pytest

from modules.sfp_tool_sherlock import sfp_tool_sherlock
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_module_base import TestModuleBase


def _root_event() -> SpiderFootEvent:
    """Build a valid ROOT SpiderFootEvent for use as a sourceEvent."""
    return SpiderFootEvent("ROOT", "alice", "", "")


class TestModuleToolSherlock(TestModuleBase):

    def test_opts(self):
        module = sfp_tool_sherlock()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_sherlock()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_tool_sherlock()
        self.assertIsInstance(module.watchedEvents(), list)
        self.assertIn("USERNAME", module.watchedEvents())

    def test_producedEvents_should_return_list(self):
        module = sfp_tool_sherlock()
        produced = module.producedEvents()
        self.assertIsInstance(produced, list)
        self.assertIn("ACCOUNT_EXTERNAL_OWNED", produced)
        self.assertIn("RAW_RIR_DATA", produced)

    def test_handleEvent_no_tool_path_and_not_on_PATH_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_sherlock()
        module.setup(sf, {"sherlock_path": ""})
        module.__name__ = "sfp_tool_sherlock"

        target = SpiderFootTarget("alice", "USERNAME")
        module.setTarget(target)

        evt = SpiderFootEvent("USERNAME", "alice", "test_seed", _root_event())

        import modules.sfp_tool_sherlock as mod
        original_which = mod.shutil.which
        mod.shutil.which = lambda *_a, **_kw: None
        try:
            result = module.handleEvent(evt)
        finally:
            mod.shutil.which = original_which

        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    def test_build_args_includes_required_flags(self):
        module = sfp_tool_sherlock()
        module.opts = dict(sfp_tool_sherlock.opts)
        args = module._build_args("/tools/bin/sherlock", "alice", "/tmp/out")
        self.assertEqual(args[0], "/tools/bin/sherlock")
        self.assertIn("--no-color", args)
        self.assertIn("--print-found", args)
        self.assertIn("--folderoutput", args)
        self.assertIn("/tmp/out", args)
        self.assertIn("--timeout", args)
        # Username comes last as a positional.
        self.assertEqual(args[-1], "alice")

    def test_handleEvent_emits_account_events_from_report(self):
        """Stub sherlock execution end-to-end with a fake binary + txt file."""
        import modules.sfp_tool_sherlock as mod

        urls = [
            "https://github.com/alice",
            "https://twitter.com/alice",
        ]

        sf = SpiderFoot(self.default_options)
        module = sfp_tool_sherlock()
        module.setup(sf, {"sherlock_path": "/fake/sherlock"})
        target = SpiderFootTarget("alice", "USERNAME")
        module.setTarget(target)

        module._resolve_binary = lambda: "/fake/sherlock"
        module.__name__ = "sfp_tool_sherlock"

        class _StubProc:
            returncode = 0
            def communicate(self, timeout=None):
                return (b"", b"")
            def kill(self):
                pass

        def _fake_popen(args, **kw):
            outdir = args[args.index("--folderoutput") + 1]
            username = args[-1]
            with open(os.path.join(outdir, f"{username}.txt"), "w") as fh:
                for u in urls:
                    fh.write(u + "\n")
            return _StubProc()

        original_popen = mod.Popen
        mod.Popen = _fake_popen

        emitted = []
        module.notifyListeners = lambda e: emitted.append(e)

        try:
            module.handleEvent(SpiderFootEvent(
                "USERNAME", "alice", "test_seed", _root_event()))
        finally:
            mod.Popen = original_popen

        types = [e.eventType for e in emitted]
        self.assertIn("RAW_RIR_DATA", types)
        account_events = [e for e in emitted if e.eventType == "ACCOUNT_EXTERNAL_OWNED"]
        self.assertEqual(len(account_events), 2)
        joined = "\n".join(e.data for e in account_events)
        self.assertIn("github.com", joined)
        self.assertIn("twitter.com", joined)
        self.assertIn("https://github.com/alice", joined)
