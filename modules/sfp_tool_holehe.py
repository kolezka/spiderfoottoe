from __future__ import annotations

"""SpiderFoot plug-in module: tool_holehe.

Wraps the ``holehe`` OSINT tool (https://github.com/megadose/holehe),
which checks whether an email address is registered on >120 sites by
exercising their forgotten-password / signup endpoints.
"""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_tool_holehe
# Purpose:     SpiderFoot plug-in for the 'holehe' OSINT email tool.
#              Tool: https://github.com/megadose/holehe
# -------------------------------------------------------------------------------

import csv
import glob
import json
import os
import shutil
import tempfile
from subprocess import PIPE, Popen, TimeoutExpired

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


_TRUTHY = {'true', 'yes', '1'}


def _is_truthy(val) -> bool:
    """Normalize the various 'exists' representations to a bool."""
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    return str(val).strip().lower() in _TRUTHY


class sfp_tool_holehe(SpiderFootAsyncPlugin):

    """Check whether an email address is registered on ~120 sites using holehe."""

    meta = {
        'name': "Tool - Holehe",
        'summary': "Check whether an email address is registered on ~120 sites using holehe.",
        'flags': ["tool", "slow"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Social Media"],
        'toolDetails': {
            'name': "Holehe",
            'description': "Holehe checks if an email is attached to an account "
                "on sites like twitter, instagram, imgur and more than 120 "
                "others. It exercises forgotten-password / signup endpoints "
                "and returns whether the address is known. No API keys "
                "required.",
            'website': "https://github.com/megadose/holehe",
            'repository': "https://github.com/megadose/holehe",
        },
    }

    opts = {
        'holehe_path': '',
        'timeout': 180,
    }

    optdescs = {
        'holehe_path': "Path to the holehe binary. Leave blank to use $PATH.",
        'timeout': "Per-email scan timeout in seconds.",
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.errorState = False
        self.__dataSource__ = "Holehe"

    def _resolve_binary(self) -> str | None:
        """Resolve the holehe binary: explicit path → $PATH → None."""
        custom = self.opts.get('holehe_path', '') or ''
        if custom:
            exe = custom + 'holehe' if custom.endswith('/') else custom
            if os.path.isfile(exe):
                return exe
            return None
        return shutil.which('holehe')

    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ['EMAILADDR']

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ['ACCOUNT_EXTERNAL_OWNED', 'RAW_RIR_DATA']

    def _build_args(self, exe: str, email: str) -> list[str]:
        """Construct the holehe CLI invocation."""
        return [
            exe,
            '--only-used',
            '--no-color',
            '--no-clear',
            '-C',
            email,
        ]

    @staticmethod
    def _parse_csv(csv_path: str) -> list[dict]:
        """Parse a holehe results CSV into a list of dicts."""
        with open(csv_path, 'r', encoding='utf-8', newline='') as fh:
            return list(csv.DictReader(fh))

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

        exe = self._resolve_binary()
        if not exe:
            self.error(
                "holehe binary not found. Set 'holehe_path' in the module "
                "options or install holehe on $PATH (e.g. `pip install holehe`).")
            self.errorState = True
            return

        # Disable holehe's startup auto-update probe noise.
        env = os.environ.copy()
        env['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'

        with tempfile.TemporaryDirectory(prefix='sf-holehe-') as outdir:
            args = self._build_args(exe, email)
            try:
                proc = Popen(
                    args, stdout=PIPE, stderr=PIPE, cwd=outdir, env=env)
                stdout, stderr = proc.communicate(
                    timeout=int(self.opts['timeout']) + 30)
            except TimeoutExpired:
                proc.kill()
                self.error(f"holehe timed out for email '{email}'.")
                return
            except Exception as e:
                self.error(f"Unable to run holehe on '{email}': {e}")
                return

            matches = sorted(glob.glob(os.path.join(outdir, 'holehe_*.csv')))
            if not matches:
                self.debug(
                    f"No holehe CSV produced for '{email}' "
                    f"(rc={proc.returncode}).")
                return

            try:
                rows = self._parse_csv(matches[0])
            except Exception as e:
                self.error(f"Failed to parse holehe CSV for '{email}': {e}")
                return

        if not isinstance(rows, list):
            return

        # Canonical raw output.
        try:
            raw_payload = json.dumps(rows)
        except (TypeError, ValueError):
            raw_payload = str(rows)
        self.notifyListeners(SpiderFootEvent(
            'RAW_RIR_DATA', raw_payload, self.__name__, event))

        for row in rows:
            if not isinstance(row, dict):
                continue
            if not _is_truthy(row.get('exists')):
                continue
            site_name = (row.get('name') or row.get('domain') or '').strip()
            domain = (row.get('domain') or '').strip()
            if not site_name and not domain:
                continue
            if not site_name:
                site_name = domain
            url = f"https://{domain}" if domain else ''
            category = (row.get('category') or 'Unknown').strip() or 'Unknown'
            data = f"{site_name} (Category: {category})\n<SFURL>{url}</SFURL>"
            self.notifyListeners(SpiderFootEvent(
                'ACCOUNT_EXTERNAL_OWNED', data, self.__name__, event))

# End of sfp_tool_holehe class
