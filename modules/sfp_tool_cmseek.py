from __future__ import annotations

"""SpiderFoot plug-in module: tool_cmseek."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_tool_cmseek
# Purpose:      SpiderFoot plug-in for using the 'CMSeeK' tool.
#               Tool: https://github.com/Tuhinshubhra/CMSeeK
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     16/12/2018
# Copyright:   (c) Steve Micallef 2018
# Licence:     MIT
# -------------------------------------------------------------------------------

import io
import json
import os.path
import shutil
from subprocess import PIPE, Popen, TimeoutExpired

from spiderfoot import SpiderFootEvent
from spiderfoot import SpiderFootHelpers
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_tool_cmseek(SpiderFootAsyncPlugin):

    """Identify what Content Management System (CMS) might be used."""

    meta = {
        'name': "Tool - CMSeeK",
        'summary': "Identify what Content Management System (CMS) might be used.",
        'flags': ["tool"],
        'useCases': ["Footprint", "Investigate"],
        'categories': ["Content Analysis"],
        'toolDetails': {
            'name': "CMSeeK",
            'description': "CMSeek is a tool that is used to extract Content Management System(CMS) details of a website.",
            'website': 'https://github.com/Tuhinshubhra/CMSeeK',
            'repository': 'https://github.com/Tuhinshubhra/CMSeeK'
        },
    }

    # Default options
    opts = {
        'pythonpath': "python3",
        'cmseekpath': ""
    }

    # Option descriptions
    optdescs = {
        'pythonpath': "Path to Python 3 interpreter to use for CMSeeK. If just 'python3' then it must be in your PATH.",
        'cmseekpath': "Path to the where the cmseek.py file lives. Must be set."
    }

    results = None
    errorState = False

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.errorState = False
        self.__dataSource__ = "Target Website"
    def _resolve_binary(self):
        """Resolve cmseek.py: explicit path → $PATH (cmseek/cmseek.py) → None.

        Returns a tuple (exe, resultpath) or (None, None) when not found.
        """
        custom = self.opts.get('cmseekpath', '') or ''
        if custom:
            if custom.endswith('cmseek.py'):
                exe = custom
                resultpath = custom.rsplit('cmseek.py', 1)[0].rstrip('/') + '/Result'
            elif custom.endswith('/'):
                exe = custom + 'cmseek.py'
                resultpath = custom + 'Result'
            else:
                exe = custom + '/cmseek.py'
                resultpath = custom + '/Result'
            if os.path.isfile(exe):
                return exe, resultpath
            return None, None

        # PATH fallback: prefer a 'cmseek' wrapper, else look for 'cmseek.py'.
        # shutil.which already verifies the file is executable, so we don't
        # double-check with os.path.isfile().
        found = shutil.which('cmseek') or shutil.which('cmseek.py')
        if found:
            resultpath = os.path.join(os.path.dirname(found), 'Result')
            return found, resultpath
        return None, None

    # What events is this module interested in for input
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ['INTERNET_NAME']

    # What events this module produces
    # This is to support the end user in selecting modules based on events
    # produced.
    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["WEBSERVER_TECHNOLOGY"]

    # Handle events sent to this module
    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if self.errorState:
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData} as already scanned.")
            return

        self.results[eventData] = True

        exe, resultpath = self._resolve_binary()
        if not exe:
            self.error(
                "cmseek.py not found. Set 'cmseekpath' in the module options "
                "or install cmseek on $PATH.")
            self.errorState = True
            return

        # Sanitize domain name.
        if not SpiderFootHelpers.sanitiseInput(eventData):
            self.error("Invalid input, refusing to run.")
            return

        args = [
            self.opts['pythonpath'],
            exe,
            '--follow-redirect',
            '--batch',
            '-u',
            eventData
        ]
        try:
            p = Popen(args, stdout=PIPE, stderr=PIPE)
            stdout, stderr = p.communicate(input=None, timeout=600)
        except TimeoutExpired:
            p.kill()
            stdout, stderr = p.communicate()
            self.debug(f"Timed out waiting for CMSeeK to finish on {eventData}")
            return
        except Exception as e:
            self.error(f"Unable to run CMSeeK: {e}")
            return

        if p.returncode != 0:
            self.error(
                f"Unable to read CMSeeK output\nstderr: {stderr}\nstdout: {stdout}")
            return

        if b"CMS Detection failed" in stdout:
            self.debug(f"Could not detect the CMS for {eventData}")
            return

        result_roots = [
            resultpath,
            os.path.join(os.path.expanduser('~'), 'Result')
        ]

        log_path = None
        for root in result_roots:
            candidate = os.path.join(root, eventData, 'cms.json')
            if os.path.isfile(candidate):
                log_path = candidate
                break

        if not log_path:
            self.error(
                f"CMSeeK report not found for {eventData} in "
                f"{', '.join(result_roots)}"
            )
            return

        try:
            f = io.open(log_path, encoding='utf-8')
            j = json.loads(f.read())
        except Exception as e:
            self.error(
                f"Could not parse CMSeeK output file {log_path} as JSON: {e}")
            return

        software = json.dumps(j, ensure_ascii=False)
        self.debug(f"software: {software}")

        if not software:
            return

        evt = SpiderFootEvent("WEBSERVER_TECHNOLOGY",
                              software, self.__name__, event)
        self.notifyListeners(evt)

# End of sfp_tool_cmseek class
