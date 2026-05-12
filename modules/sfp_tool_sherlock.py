from __future__ import annotations

"""SpiderFoot plug-in module: tool_sherlock.

Wraps the ``sherlock`` OSINT tool
(https://github.com/sherlock-project/sherlock), which hunts a username
across hundreds of social-media sites.

The PyPI package is ``sherlock-project`` but it installs the ``sherlock``
CLI command — keep that distinction in mind when bumping requirements.
"""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_tool_sherlock
# Purpose:     SpiderFoot plug-in for the 'sherlock' OSINT username tool.
#              Tool: https://github.com/sherlock-project/sherlock
# -------------------------------------------------------------------------------

import json
import os
import shutil
import tempfile
from subprocess import PIPE, Popen, TimeoutExpired
from urllib.parse import urlparse

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_tool_sherlock(SpiderFootAsyncPlugin):

    """Hunt a username across hundreds of social-media sites using sherlock."""

    meta = {
        'name': "Tool - Sherlock",
        'summary': "Hunt a username across hundreds of social-media sites using sherlock.",
        'flags': ["tool", "slow"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Social Media"],
        'toolDetails': {
            'name': "Sherlock",
            'description': "Sherlock is a Python tool that hunts down usernames "
                "across more than 400 social networks. It writes a per-username "
                "text file containing the URLs of every account it found.",
            'website': "https://github.com/sherlock-project/sherlock",
            'repository': "https://github.com/sherlock-project/sherlock",
        },
    }

    opts = {
        'sherlock_path': '',
        'timeout': 60,
    }

    optdescs = {
        'sherlock_path': "Path to the sherlock binary. Leave blank to use $PATH.",
        'timeout': "Per-site request timeout in seconds (also bounds the scan).",
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.errorState = False
        self.__dataSource__ = "Sherlock"

    def _resolve_binary(self) -> str | None:
        """Resolve the sherlock binary: explicit path → $PATH → None."""
        custom = self.opts.get('sherlock_path', '') or ''
        if custom:
            exe = custom + 'sherlock' if custom.endswith('/') else custom
            if os.path.isfile(exe):
                return exe
            return None
        return shutil.which('sherlock')

    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ['USERNAME']

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ['ACCOUNT_EXTERNAL_OWNED', 'RAW_RIR_DATA']

    def _build_args(self, exe: str, username: str, outdir: str) -> list[str]:
        """Construct the sherlock CLI invocation."""
        return [
            exe,
            '--no-color',
            '--print-found',
            '--folderoutput', outdir,
            '--timeout', str(int(self.opts['timeout'])),
            username,
        ]

    @staticmethod
    def _parse_report(report_path: str) -> list[str]:
        """Read a sherlock per-username .txt and return found URLs."""
        urls: list[str] = []
        with open(report_path, 'r', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                # sherlock writes one URL per line (typically prefixed
                # with the site name in stdout, but the file output is
                # bare URLs). Accept anything that parses as http(s)://.
                if line.startswith('http://') or line.startswith('https://'):
                    urls.append(line)
                    continue
                # Fall back to a tail-of-line URL if present.
                for token in line.split():
                    if token.startswith('http://') or token.startswith('https://'):
                        urls.append(token)
                        break
        return urls

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
                "sherlock binary not found. Set 'sherlock_path' in the module "
                "options or install sherlock on $PATH (e.g. "
                "`pip install sherlock-project`).")
            self.errorState = True
            return

        with tempfile.TemporaryDirectory(prefix='sf-sherlock-') as outdir:
            args = self._build_args(exe, username, outdir)
            try:
                proc = Popen(args, stdout=PIPE, stderr=PIPE)
                stdout, stderr = proc.communicate(
                    timeout=int(self.opts['timeout']) + 60)
            except TimeoutExpired:
                proc.kill()
                self.error(f"sherlock timed out for username '{username}'.")
                return
            except Exception as e:
                self.error(f"Unable to run sherlock on '{username}': {e}")
                return

            # sherlock returns 0 even when nothing is found, so don't
            # branch on returncode — just look for the output file.
            report_path = os.path.join(outdir, f"{username}.txt")
            if not os.path.isfile(report_path):
                self.debug(
                    f"No sherlock report produced for '{username}' "
                    f"(rc={proc.returncode}).")
                return

            try:
                urls = self._parse_report(report_path)
            except Exception as e:
                self.error(f"Failed to parse sherlock report for '{username}': {e}")
                return

        if not isinstance(urls, list):
            return

        # Canonical raw output: emit the list as JSON.
        try:
            raw_payload = json.dumps(urls)
        except (TypeError, ValueError):
            raw_payload = '\n'.join(urls)
        self.notifyListeners(SpiderFootEvent(
            'RAW_RIR_DATA', raw_payload, self.__name__, event))

        for url in urls:
            try:
                site_name = urlparse(url).hostname or url
            except Exception:
                site_name = url
            data = f"{site_name} (Category: Unknown)\n<SFURL>{url}</SFURL>"
            self.notifyListeners(SpiderFootEvent(
                'ACCOUNT_EXTERNAL_OWNED', data, self.__name__, event))

# End of sfp_tool_sherlock class
