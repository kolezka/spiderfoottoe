from __future__ import annotations

"""Tests for sfp_tool_ignorant module.

ignorant is a library-only integration (no subprocess, no binary path),
so these tests focus on:

  * the option / event surface,
  * phone-number parsing,
  * stubbing the trio runner + the per-service async functions.

Importantly, this module is NOT included in the strict $PATH-fallback
parametrize list — there's no binary to resolve.
"""

import json
import sys
import types

import pytest

from modules.sfp_tool_ignorant import sfp_tool_ignorant
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_module_base import TestModuleBase


def _root_event() -> SpiderFootEvent:
    """Build a valid ROOT SpiderFootEvent for use as a sourceEvent."""
    return SpiderFootEvent("ROOT", "+33644637111", "", "")


def _install_fake_trio() -> None:
    """Install a minimal fake ``trio`` module.

    The real trio is heavy and not in the test venv. We only need
    ``trio.run(coro_fn)`` for the module under test, so we drive the
    coroutine via asyncio's loop instead.
    """
    import asyncio
    fake = types.ModuleType("trio")

    def _run(async_fn, *args, **kwargs):
        return asyncio.run(async_fn(*args, **kwargs))

    fake.run = _run
    sys.modules["trio"] = fake


def _install_fake_ignorant_package() -> None:
    """Install fakes for the ignorant submodules the wrapper imports.

    Mirrors the actual package layout: ``amazon`` lives under
    ``ignorant.modules.shopping`` while ``instagram`` and ``snapchat``
    live under ``ignorant.modules.social_media``. We install fakes
    BEFORE the module's setup() runs so the deferred imports succeed
    even when the real package isn't installed in the test environment.
    """
    pkg = types.ModuleType("ignorant")
    pkg.__path__ = []  # mark as package
    sub_modules = types.ModuleType("ignorant.modules")
    sub_modules.__path__ = []
    sub_shopping = types.ModuleType("ignorant.modules.shopping")
    sub_shopping.__path__ = []
    sub_social = types.ModuleType("ignorant.modules.social_media")
    sub_social.__path__ = []

    async def _fake_amazon(phone, country_code, out):
        out.append({
            "name": "amazon", "domain": "amazon.com", "method": "register",
            "frequent_rate_limit": False, "rateLimit": False, "exists": True,
        })

    async def _fake_instagram(phone, country_code, out):
        out.append({
            "name": "instagram", "domain": "instagram.com", "method": "register",
            "frequent_rate_limit": False, "rateLimit": False, "exists": False,
        })

    async def _fake_snapchat(phone, country_code, out):
        out.append({
            "name": "snapchat", "domain": "snapchat.com", "method": "register",
            "frequent_rate_limit": False, "rateLimit": False, "exists": True,
        })

    amazon_mod = types.ModuleType("ignorant.modules.shopping.amazon")
    amazon_mod.amazon = _fake_amazon
    instagram_mod = types.ModuleType("ignorant.modules.social_media.instagram")
    instagram_mod.instagram = _fake_instagram
    snapchat_mod = types.ModuleType("ignorant.modules.social_media.snapchat")
    snapchat_mod.snapchat = _fake_snapchat

    sys.modules["ignorant"] = pkg
    sys.modules["ignorant.modules"] = sub_modules
    sys.modules["ignorant.modules.shopping"] = sub_shopping
    sys.modules["ignorant.modules.social_media"] = sub_social
    sys.modules["ignorant.modules.shopping.amazon"] = amazon_mod
    sys.modules["ignorant.modules.social_media.instagram"] = instagram_mod
    sys.modules["ignorant.modules.social_media.snapchat"] = snapchat_mod


class TestModuleToolIgnorant(TestModuleBase):

    def setUp(self):
        super().setUp()
        _install_fake_trio()
        _install_fake_ignorant_package()

    def tearDown(self):
        for k in list(sys.modules):
            if k == "ignorant" or k.startswith("ignorant.") or k == "trio":
                del sys.modules[k]
        super().tearDown()

    def test_opts(self):
        module = sfp_tool_ignorant()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_ignorant()
        module.setup(sf, dict())
        # With our fake ignorant package available, errorState stays False.
        self.assertFalse(module.errorState)

    def test_setup_missing_ignorant_sets_errorState(self):
        # Drop our fake package — the real one isn't installed in the
        # test venv either, so the import should fail.
        for k in list(sys.modules):
            if k == "ignorant" or k.startswith("ignorant."):
                del sys.modules[k]
        # Block any real import from succeeding too.
        sys.modules["ignorant"] = None
        try:
            sf = SpiderFoot(self.default_options)
            module = sfp_tool_ignorant()
            module.setup(sf, dict())
            self.assertTrue(module.errorState)
        finally:
            if "ignorant" in sys.modules:
                del sys.modules["ignorant"]
            _install_fake_ignorant_package()

    def test_watchedEvents_should_return_list(self):
        module = sfp_tool_ignorant()
        self.assertIsInstance(module.watchedEvents(), list)
        self.assertIn("PHONE_NUMBER", module.watchedEvents())

    def test_producedEvents_should_return_list(self):
        module = sfp_tool_ignorant()
        produced = module.producedEvents()
        self.assertIsInstance(produced, list)
        self.assertIn("ACCOUNT_EXTERNAL_OWNED", produced)
        self.assertIn("RAW_RIR_DATA", produced)

    def test_parse_phone_valid_e164(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_ignorant()
        module.setup(sf, dict())
        result = module._parse_phone("+33644637111")
        self.assertIsNotNone(result)
        country, national = result
        self.assertEqual(country, "33")
        self.assertEqual(national, "644637111")

    def test_parse_phone_invalid_returns_none(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_ignorant()
        module.setup(sf, dict())
        # Garbage input — phonenumbers will raise; we should swallow it.
        self.assertIsNone(module._parse_phone("not-a-phone"))

    def test_selected_services_default(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_ignorant()
        module.setup(sf, dict())
        self.assertEqual(
            module._selected_services(),
            ("amazon", "instagram", "snapchat"),
        )

    def test_selected_services_filtered(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_ignorant()
        module.setup(sf, {"services": "amazon,snapchat"})
        self.assertEqual(
            module._selected_services(),
            ("amazon", "snapchat"),
        )

    def test_handleEvent_emits_events_from_library(self):
        """End-to-end with the fake ignorant + fake trio.run."""
        import modules.sfp_tool_ignorant as mod

        sf = SpiderFoot(self.default_options)
        module = sfp_tool_ignorant()
        module.setup(sf, dict())
        module.__name__ = "sfp_tool_ignorant"

        target = SpiderFootTarget("+33644637111", "PHONE_NUMBER")
        module.setTarget(target)

        emitted = []
        module.notifyListeners = lambda e: emitted.append(e)

        evt = SpiderFootEvent(
            "PHONE_NUMBER", "+33644637111", "test_seed", _root_event())
        module.handleEvent(evt)

        types_ = [e.eventType for e in emitted]
        self.assertIn("RAW_RIR_DATA", types_)
        account_events = [e for e in emitted if e.eventType == "ACCOUNT_EXTERNAL_OWNED"]
        # amazon (exists=True) + snapchat (exists=True), instagram skipped
        self.assertEqual(len(account_events), 2)
        joined = "\n".join(e.data for e in account_events)
        self.assertIn("amazon", joined)
        self.assertIn("snapchat", joined)
        self.assertNotIn("instagram", joined)

        # RAW_RIR_DATA should be JSON of the result list.
        raw = [e for e in emitted if e.eventType == "RAW_RIR_DATA"][0]
        decoded = json.loads(raw.data)
        self.assertIsInstance(decoded, list)
        self.assertEqual(len(decoded), 3)

    def test_handleEvent_invalid_phone_skips_silently(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_ignorant()
        module.setup(sf, dict())
        module.__name__ = "sfp_tool_ignorant"
        target = SpiderFootTarget("+33644637111", "PHONE_NUMBER")
        module.setTarget(target)

        emitted = []
        module.notifyListeners = lambda e: emitted.append(e)

        evt = SpiderFootEvent(
            "PHONE_NUMBER", "garbage-phone", "test_seed", _root_event())
        module.handleEvent(evt)

        # No events should be emitted.
        self.assertEqual(emitted, [])
        self.assertFalse(module.errorState)
