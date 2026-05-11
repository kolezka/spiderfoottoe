from __future__ import annotations

"""SpiderFoot plug-in module: tool_maigret."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_tool_maigret
# Purpose:     SpiderFoot plug-in for the 'maigret' OSINT username search tool.
#              Tool: https://github.com/soxoj/maigret
# -------------------------------------------------------------------------------

import json
import os
import shutil
import tempfile
from subprocess import PIPE, Popen, TimeoutExpired

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_tool_maigret(SpiderFootAsyncPlugin):

    """Search ~3000 sites for the existence of an account with the given username, using maigret."""

    meta = {
        'name': "Tool - Maigret",
        'summary': "Search ~3000 sites for the existence of an account with the given username, using maigret.",
        'flags': ["tool", "slow"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Social Media"],
        'toolDetails': {
            'name': "Maigret",
            'description': "Maigret is an OSINT tool that collects a dossier on a "
                "person by username only, checking for accounts on a huge number "
                "of sites and gathering all the available information from web "
                "pages. No API keys required.",
            'website': "https://github.com/soxoj/maigret",
            'repository': "https://github.com/soxoj/maigret",
        },
    }

    opts = {
        'maigret_path': '',
        'timeout': 300,
        'top_sites': 500,
        'use_disabled_sites': False,
        'tags': '',
    }

    optdescs = {
        'maigret_path': "Path to the maigret binary. Leave blank to use $PATH.",
        'timeout': "Per-username scan timeout in seconds.",
        'top_sites': "Limit the lookup to the N most popular sites (0 = all).",
        'use_disabled_sites': "Include sites that maigret has marked as unreliable.",
        'tags': "Comma-separated tag filter (e.g. 'us,photo'). Blank = no filter.",
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.errorState = False
        self.__dataSource__ = "Maigret"

    def _resolve_binary(self) -> str | None:
        """Resolve the maigret binary: explicit path → $PATH → None."""
        custom = self.opts.get('maigret_path', '') or ''
        if custom:
            exe = custom + 'maigret' if custom.endswith('/') else custom
            if os.path.isfile(exe):
                return exe
            return None
        return shutil.which('maigret')

    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ['USERNAME']

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ['ACCOUNT_EXTERNAL_OWNED', 'RAW_RIR_DATA']

    def _build_args(self, exe: str, username: str, outdir: str) -> list[str]:
        """Construct the maigret CLI invocation."""
        args = [
            exe,
            username,
            '--json', 'simple',
            '--no-color',
            '--no-progressbar',
            '--folderoutput', outdir,
            '--timeout', str(int(self.opts['timeout'])),
        ]
        top = int(self.opts.get('top_sites') or 0)
        if top > 0:
            args += ['--top-sites', str(top)]
        if self.opts.get('use_disabled_sites'):
            args.append('--use-disabled-sites')
        tags = (self.opts.get('tags') or '').strip()
        if tags:
            args += ['--tags', tags]
        return args

    @staticmethod
    def _parse_report(report_path: str) -> dict:
        """Read and JSON-decode a maigret simple-format report file."""
        with open(report_path, 'r', encoding='utf-8') as fh:
            return json.load(fh)

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if self.errorState:
            return

        username = (eventData or '').strip()
        if not username:
            return

        if username in self.results:
            self.debug(f"Skipping {username}, already scanned.")
            return
        self.results[username] = True

        exe = self._resolve_binary()
        if not exe:
            self.error(
                "maigret binary not found. Set 'maigret_path' in the module "
                "options or install maigret on $PATH (e.g. `pip install maigret`).")
            self.errorState = True
            return

        with tempfile.TemporaryDirectory(prefix='sf-maigret-') as outdir:
            args = self._build_args(exe, username, outdir)
            try:
                proc = Popen(args, stdout=PIPE, stderr=PIPE)
                stdout, stderr = proc.communicate(
                    timeout=int(self.opts['timeout']) + 30)
            except TimeoutExpired:
                proc.kill()
                self.error(f"maigret timed out for username '{username}'.")
                return
            except Exception as e:
                self.error(f"Unable to run maigret on '{username}': {e}")
                return

            if proc.returncode not in (0, 1):
                # 0 = found accounts, 1 = no accounts found; anything else is a real error
                err = (stderr or b'').decode('utf-8', errors='replace').strip()
                self.error(
                    f"maigret exited with code {proc.returncode} for '{username}': {err}")
                return

            report_path = os.path.join(outdir, f'report_{username}_simple.json')
            if not os.path.isfile(report_path):
                self.debug(f"No maigret report produced for '{username}'.")
                return

            try:
                report = self._parse_report(report_path)
            except Exception as e:
                self.error(f"Failed to parse maigret report for '{username}': {e}")
                return

        if not isinstance(report, dict):
            return

        raw_evt = SpiderFootEvent(
            'RAW_RIR_DATA', json.dumps(report), self.__name__, event)
        self.notifyListeners(raw_evt)

        for site_name, info in report.items():
            if not isinstance(info, dict):
                continue
            status = info.get('status')
            if isinstance(status, dict):
                # Older simple format wraps the status object
                status_str = status.get('status')
            else:
                status_str = status
            if str(status_str).lower() != 'claimed':
                continue
            url = info.get('url_user') or info.get('url') or info.get('url_main')
            if not url:
                continue
            tags = info.get('tags') or []
            category = ', '.join(tags) if isinstance(tags, list) and tags else 'Unknown'
            data = f"{site_name} (Category: {category})\n<SFURL>{url}</SFURL>"
            evt = SpiderFootEvent(
                'ACCOUNT_EXTERNAL_OWNED', data, self.__name__, event)
            self.notifyListeners(evt)

# End of sfp_tool_maigret class
