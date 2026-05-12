from __future__ import annotations

"""SpiderFoot plug-in module: tool_ignorant.

Wraps the ``ignorant`` OSINT tool
(https://github.com/megadose/ignorant), which checks whether a phone
number is registered on Amazon, Instagram and Snapchat.

ignorant ships a CLI but only emits coloured stdout (no machine-readable
output), so we drive the library API directly via trio. Import paths
are based on the upstream package layout at the time of writing
verified against ignorant 1.2.x as installed in the active-scanner
image: ``amazon`` lives under ``ignorant.modules.shopping`` while
``instagram`` and ``snapchat`` live under
``ignorant.modules.social_media``. The setup() handler defers the
import and degrades gracefully if the shape changes again upstream.
"""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_tool_ignorant
# Purpose:     SpiderFoot plug-in for the 'ignorant' OSINT phone tool.
#              Tool: https://github.com/megadose/ignorant
# -------------------------------------------------------------------------------

import json

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


_SUPPORTED_SERVICES = ('amazon', 'instagram', 'snapchat')


class sfp_tool_ignorant(SpiderFootAsyncPlugin):

    """Check whether a phone number is registered on Amazon, Instagram or Snapchat using ignorant."""

    meta = {
        'name': "Tool - Ignorant",
        'summary': "Check whether a phone number is registered on Amazon, Instagram or Snapchat using ignorant.",
        'flags': ["tool", "slow"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Social Media"],
        'toolDetails': {
            'name': "Ignorant",
            'description': "Ignorant checks whether a phone number is "
                "registered on Amazon, Instagram and Snapchat by exercising "
                "their forgotten-password flows. No API keys required.",
            'website': "https://github.com/megadose/ignorant",
            'repository': "https://github.com/megadose/ignorant",
        },
    }

    opts = {
        'timeout': 60,
        'services': '',
    }

    optdescs = {
        'timeout': "Per-phone scan timeout in seconds.",
        'services': (
            "Comma-separated list of services to query "
            "(amazon,instagram,snapchat). Blank = all."
        ),
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.errorState = False
        self.__dataSource__ = "Ignorant"

        # Defer the import: this is a library-driven module (no binary)
        # and the package layout may shift between releases.
        try:
            import trio  # noqa: F401
            import phonenumbers  # noqa: F401
            from ignorant.modules.shopping import amazon  # noqa: F401
            from ignorant.modules.social_media import instagram  # noqa: F401
            from ignorant.modules.social_media import snapchat  # noqa: F401
        except ImportError as e:
            self.error(
                "ignorant module is not importable. Install with "
                "`pip install ignorant trio phonenumbers`. Underlying "
                f"error: {e}")
            self.errorState = True
            return

    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ['PHONE_NUMBER']

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ['ACCOUNT_EXTERNAL_OWNED', 'RAW_RIR_DATA']

    def _selected_services(self) -> tuple[str, ...]:
        """Return the subset of services configured by the user."""
        raw = (self.opts.get('services') or '').strip()
        if not raw:
            return _SUPPORTED_SERVICES
        wanted = tuple(
            s.strip().lower() for s in raw.split(',') if s.strip()
        )
        return tuple(s for s in wanted if s in _SUPPORTED_SERVICES)

    def _parse_phone(self, raw: str) -> tuple[str, str] | None:
        """Parse an E.164 phone number into (country_code, national)."""
        import phonenumbers
        try:
            parsed = phonenumbers.parse(raw, None)
        except Exception as e:
            self.debug(f"ignorant: failed to parse phone '{raw}': {e}")
            return None
        country = getattr(parsed, 'country_code', None)
        national = getattr(parsed, 'national_number', None)
        if not country or not national:
            self.debug(
                f"ignorant: phone '{raw}' missing country code or national "
                f"number after parsing.")
            return None
        return str(country), str(national)

    def _run_lookups(self, country_code: str, national: str) -> list[dict]:
        """Drive the ignorant trio-based async API for the chosen services."""
        import trio
        from ignorant.modules.shopping.amazon import amazon
        from ignorant.modules.social_media.instagram import instagram
        from ignorant.modules.social_media.snapchat import snapchat

        registry = {
            'amazon': amazon,
            'instagram': instagram,
            'snapchat': snapchat,
        }
        services = self._selected_services()
        if not services:
            return []

        results: list[dict] = []

        async def runner() -> None:
            for svc in services:
                fn = registry.get(svc)
                if fn is None:
                    continue
                out: list[dict] = []
                try:
                    await fn(national, country_code, out)
                except Exception as exc:  # pragma: no cover - upstream
                    self.debug(f"ignorant: {svc} probe failed: {exc}")
                    continue
                results.extend(out)

        try:
            trio.run(runner)
        except Exception as e:
            self.error(f"ignorant: trio.run failed: {e}")
            return []
        return results

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if self.errorState:
            return

        phone = (eventData or '').strip()
        if not phone:
            return

        if phone in self.results:
            self.debug(f"Skipping {phone}, already scanned.")
            return
        self.results[phone] = True

        parsed = self._parse_phone(phone)
        if parsed is None:
            return
        country_code, national = parsed

        results = self._run_lookups(country_code, national)
        if not isinstance(results, list):
            return

        try:
            raw_payload = json.dumps(results)
        except (TypeError, ValueError):
            raw_payload = str(results)
        self.notifyListeners(SpiderFootEvent(
            'RAW_RIR_DATA', raw_payload, self.__name__, event))

        for row in results:
            if not isinstance(row, dict):
                continue
            if not row.get('exists'):
                continue
            site_name = (row.get('name') or row.get('domain') or '').strip()
            domain = (row.get('domain') or '').strip()
            if not site_name and not domain:
                continue
            if not site_name:
                site_name = domain
            url = f"https://{domain}" if domain else ''
            category = (row.get('category') or 'Phone').strip() or 'Phone'
            data = f"{site_name} (Category: {category})\n<SFURL>{url}</SFURL>"
            self.notifyListeners(SpiderFootEvent(
                'ACCOUNT_EXTERNAL_OWNED', data, self.__name__, event))

# End of sfp_tool_ignorant class
