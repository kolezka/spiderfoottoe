from __future__ import annotations

"""SpiderFoot plug-in module: tool_ghunt.

Wraps the ``ghunt`` OSINT tool (https://github.com/mxrch/GHunt), which
investigates Google accounts associated with an email address.

NOTE: ``ghunt`` is licensed under AGPL-3.0. Bundling it inside an image
imposes the obligation to make corresponding source code available to
users who interact with the resulting service over a network. SpiderFoot
itself remains MIT-licensed; only the optional ``ghunt`` integration is
copyleft. Operators must comply with the AGPL when running this module.
"""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_tool_ghunt
# Purpose:     SpiderFoot plug-in for the 'ghunt' OSINT email/Google-account
#              investigation tool.
#              Tool: https://github.com/mxrch/GHunt
# License:     ghunt is AGPL-3.0; see module docstring above.
# -------------------------------------------------------------------------------

import json
import os
import shutil
import tempfile
from subprocess import PIPE, Popen, TimeoutExpired

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


# Hard-coded upstream credentials path. ghunt does not honour an env-var
# override, so the file must exist here for the tool to function.
GHUNT_CREDS_PATH = '~/.malfrats/ghunt/creds.m'


class sfp_tool_ghunt(SpiderFootAsyncPlugin):

    """Investigate Google accounts associated with an email address using ghunt."""

    meta = {
        'name': "Tool - GHunt",
        'summary': "Investigate Google accounts associated with an email address using ghunt.",
        'flags': ["tool", "slow"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Social Media"],
        'toolDetails': {
            'name': "GHunt",
            'description': "GHunt is an offensive Google framework, designed to "
                "evolve over the years. It investigates Google accounts (Gmail "
                "addresses, Google profiles, GAIA IDs) and returns associated "
                "services such as YouTube, Maps, Photos, and Drive metadata. "
                "Requires a one-off authenticated session (`ghunt login`) on a "
                "host machine; the resulting ~/.malfrats/ghunt/ directory must "
                "be mounted into the scanner container.",
            'website': "https://github.com/mxrch/GHunt",
            'repository': "https://github.com/mxrch/GHunt",
        },
    }

    opts = {
        'ghunt_path': '',
        'timeout': 120,
    }

    optdescs = {
        'ghunt_path': "Path to the ghunt binary. Leave blank to use $PATH.",
        'timeout': "Per-email scan timeout in seconds.",
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.errorState = False
        self.__dataSource__ = "GHunt"

    def _resolve_binary(self) -> str | None:
        """Resolve the ghunt binary: explicit path → $PATH → None."""
        custom = self.opts.get('ghunt_path', '') or ''
        if custom:
            exe = custom + 'ghunt' if custom.endswith('/') else custom
            if os.path.isfile(exe):
                return exe
            return None
        return shutil.which('ghunt')

    @staticmethod
    def _creds_present() -> bool:
        """Return True iff the upstream creds file is on disk."""
        return os.path.isfile(os.path.expanduser(GHUNT_CREDS_PATH))

    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ['EMAILADDR']

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            'ACCOUNT_EXTERNAL_OWNED',
            'SOCIAL_MEDIA',
            'HUMAN_NAME',
            'RAW_RIR_DATA',
        ]

    def _build_args(self, exe: str, email: str, outfile: str) -> list[str]:
        """Construct the ghunt CLI invocation."""
        return [exe, 'email', email, '--json', outfile]

    @staticmethod
    def _parse_report(report_path: str) -> dict:
        """Read and JSON-decode a ghunt report file."""
        with open(report_path, 'r', encoding='utf-8') as fh:
            return json.load(fh)

    def _emit_from_report(self, report: dict, event: SpiderFootEvent) -> None:
        """Translate a ghunt JSON report into SpiderFoot events.

        ghunt's JSON shape varies between versions, so every field
        access is wrapped defensively — missing fields are debug-logged
        and skipped rather than treated as fatal.
        """
        # HUMAN_NAME — best-effort across known variants.
        try:
            profile = report.get('PROFILE_CONTAINER') or report.get('profile') or {}
            container = profile.get('profile') if isinstance(profile, dict) else None
            name = None
            if isinstance(container, dict):
                names = container.get('names') or []
                if isinstance(names, list) and names:
                    name = (
                        names[0].get('fullname')
                        if isinstance(names[0], dict)
                        else None
                    )
            if not name and isinstance(profile, dict):
                name = profile.get('name') or profile.get('fullname')
            if name:
                self.notifyListeners(SpiderFootEvent(
                    'HUMAN_NAME', str(name), self.__name__, event))
        except Exception as e:
            self.debug(f"ghunt: HUMAN_NAME extraction skipped: {e}")

        # SOCIAL_MEDIA — Google account itself (gaiaID / email handle).
        try:
            profile = report.get('PROFILE_CONTAINER') or report.get('profile') or {}
            container = profile.get('profile') if isinstance(profile, dict) else None
            gaia_id = None
            if isinstance(container, dict):
                gaia_id = container.get('personId') or container.get('gaiaID')
            if not gaia_id and isinstance(profile, dict):
                gaia_id = profile.get('gaiaID') or profile.get('personId')
            if gaia_id:
                data = (
                    f"Google (Account ID: {gaia_id})\n"
                    f"<SFURL>https://plus.google.com/{gaia_id}</SFURL>"
                )
                self.notifyListeners(SpiderFootEvent(
                    'SOCIAL_MEDIA', data, self.__name__, event))
        except Exception as e:
            self.debug(f"ghunt: SOCIAL_MEDIA extraction skipped: {e}")

        # ACCOUNT_EXTERNAL_OWNED — services array (YouTube, Maps, Photos, Drive).
        try:
            services = report.get('services') or report.get('SERVICES_CONTAINER') or []
            if isinstance(services, dict):
                services = list(services.values())
            if not isinstance(services, list):
                services = []
            for svc in services:
                if not isinstance(svc, dict):
                    continue
                # Accept both {name, url, ...} and {service, link} shapes.
                name = (
                    svc.get('name')
                    or svc.get('service')
                    or svc.get('title')
                )
                url = svc.get('url') or svc.get('link') or svc.get('profile_url')
                if not name:
                    continue
                category = svc.get('category') or 'Google'
                if url:
                    data = (
                        f"{name} (Category: {category})\n"
                        f"<SFURL>{url}</SFURL>"
                    )
                else:
                    data = f"{name} (Category: {category})"
                self.notifyListeners(SpiderFootEvent(
                    'ACCOUNT_EXTERNAL_OWNED', data, self.__name__, event))
        except Exception as e:
            self.debug(f"ghunt: services extraction skipped: {e}")

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if self.errorState:
            return

        email = (eventData or '').strip()
        if not email:
            return

        if email in self.results:
            self.debug(f"Skipping {email}, already scanned.")
            return
        self.results[email] = True

        if not self._creds_present():
            self.error(
                "ghunt requires authenticated session. Run `ghunt login` "
                "on a host machine and mount the resulting "
                "~/.malfrats/ghunt/ directory into the active-scanner "
                "container.")
            self.errorState = True
            return

        exe = self._resolve_binary()
        if not exe:
            self.error(
                "ghunt binary not found. Set 'ghunt_path' in the module "
                "options or install ghunt on $PATH (e.g. `pip install ghunt`).")
            self.errorState = True
            return

        with tempfile.TemporaryDirectory(prefix='sf-ghunt-') as outdir:
            outfile = os.path.join(outdir, 'ghunt.json')
            args = self._build_args(exe, email, outfile)
            try:
                proc = Popen(args, stdout=PIPE, stderr=PIPE)
                stdout, stderr = proc.communicate(
                    timeout=int(self.opts['timeout']) + 30)
            except TimeoutExpired:
                proc.kill()
                self.error(f"ghunt timed out for email '{email}'.")
                return
            except Exception as e:
                self.error(f"Unable to run ghunt on '{email}': {e}")
                return

            if not os.path.isfile(outfile):
                err = (stderr or b'').decode('utf-8', errors='replace').strip()
                self.debug(
                    f"No ghunt report produced for '{email}' "
                    f"(rc={proc.returncode}): {err}")
                return

            try:
                report = self._parse_report(outfile)
            except Exception as e:
                self.error(f"Failed to parse ghunt report for '{email}': {e}")
                return

        if not isinstance(report, dict):
            return

        # Canonical raw output.
        try:
            raw_payload = json.dumps(report)
        except (TypeError, ValueError):
            raw_payload = str(report)
        self.notifyListeners(SpiderFootEvent(
            'RAW_RIR_DATA', raw_payload, self.__name__, event))

        self._emit_from_report(report, event)

# End of sfp_tool_ghunt class
