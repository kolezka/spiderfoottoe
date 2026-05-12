from __future__ import annotations

"""SpiderFoot plug-in module: subdomain_takeover."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_subdomain_takeover
# Purpose:     Check if affiliated subdomains are vulnerable to takeover
#              using the fingerprints.json list from subjack by haccer:
#              - https://github.com/haccer/subjack/master/fingerprints.json
#
# Author:      <bcoles@gmail.com>
#
# Created:     2020-06-21
# Copyright:   (c) bcoles 2020
# Licence:     MIT
# -------------------------------------------------------------------------------

import json

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_subdomain_takeover(SpiderFootAsyncPlugin):

    """Check if affiliated subdomains are vulnerable to takeover."""

    meta = {
        'name': "Subdomain Takeover Checker",
        'summary': "Check if affiliated subdomains are vulnerable to takeover.",
        'flags': ["deprecated"],
        'useCases': ["Footprint", "Investigate"],
        'categories': ["Crawling and Scanning"],
        "dataSource": {
            "website": "https://github.com/EdOverflow/can-i-take-over-xyz",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": ["https://github.com/EdOverflow/can-i-take-over-xyz"],
            "description": "Detect potential subdomain takeover vulnerabilities via dangling CNAME records.",
        },
    }

    # Default options
    opts = {
    }

    # Option descriptions
    optdescs = {
    }

    results = None
    errorState = False
    fingerprints = dict()

    # Initialize module and module options
    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.errorState = False
        # haccer/subjack/master/fingerprints.json was removed upstream;
        # use EdOverflow's actively-maintained list as the authoritative
        # source. The schema is similar (cname/service/nxdomain) but
        # ``fingerprint`` is a single string rather than a list, so
        # _normalise_fingerprints() coerces it.
        content = self.cache_get("takeover-fingerprints", 48)
        if content is None:
            url = "https://raw.githubusercontent.com/EdOverflow/can-i-take-over-xyz/master/fingerprints.json"
            res = self.fetch_url(url, useragent="SpiderFoot")

            if res['content'] is None:
                self.error(f"Unable to fetch {url}")
                self.errorState = True
                return

            self.cache_put("takeover-fingerprints", res['content'])
            content = res['content']

        try:
            raw = json.loads(content)
        except Exception as e:
            self.error(
                f"Unable to parse subdomain takeover fingerprints list: {e}")
            self.errorState = True
            return

        self.fingerprints = self._normalise_fingerprints(raw)

    @staticmethod
    def _normalise_fingerprints(raw):
        """Coerce upstream entries into the schema this module expects.

        Each entry must have list-typed ``cname`` and ``fingerprint`` fields
        and a ``nxdomain`` boolean. Entries missing ``cname`` are dropped.
        EdOverflow's source uses a single string for ``fingerprint``; wrap
        it in a list. Some entries omit ``fingerprint`` entirely (typically
        the NXDOMAIN-only ones) — those get an empty fingerprint list, so
        the AFFILIATE_INTERNET_NAME branch silently skips them while the
        AFFILIATE_INTERNET_NAME_UNRESOLVED branch still fires when nxdomain
        is set.
        """
        if not isinstance(raw, list):
            return []
        out = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            cnames = entry.get("cname") or []
            if isinstance(cnames, str):
                cnames = [cnames]
            if not cnames:
                continue
            fp = entry.get("fingerprint")
            if fp is None:
                fps = []
            elif isinstance(fp, str):
                fps = [fp] if fp else []
            elif isinstance(fp, list):
                fps = [f for f in fp if isinstance(f, str) and f]
            else:
                fps = []
            out.append({
                "service": entry.get("service") or "Unknown",
                "cname": cnames,
                "fingerprint": fps,
                "nxdomain": bool(entry.get("nxdomain")),
            })
        return out

    # What events is this module interested in for input
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ["AFFILIATE_INTERNET_NAME", "AFFILIATE_INTERNET_NAME_UNRESOLVED"]

    # What events this module produces
    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["AFFILIATE_INTERNET_NAME_HIJACKABLE"]

    # Handle events sent to this module
    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        if eventData in self.results:
            return

        self.results[eventData] = True

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventName == "AFFILIATE_INTERNET_NAME":
            for data in self.fingerprints:
                if self.checkForStop():
                    return
                service = data.get("service")
                cnames = data.get("cname")
                fingerprints = data.get("fingerprint")
                nxdomain = data.get("nxdomain")

                if nxdomain:
                    continue

                for cname in cnames:
                    if cname.lower() not in eventData.lower():
                        continue

                    for proto in ["https", "http"]:
                        res = self.fetch_url(
                            f"{proto}://{eventData}/",
                            timeout=15,
                            useragent=self.opts['_useragent'],
                            verify=False
                        )
                        if not res:
                            continue
                        if not res['content']:
                            continue
                        for fingerprint in fingerprints:
                            if fingerprint in res['content']:
                                self.info(
                                    f"{eventData} appears to be vulnerable to takeover on {service}")
                                evt = SpiderFootEvent(
                                    "AFFILIATE_INTERNET_NAME_HIJACKABLE", eventData, self.__name__, event)
                                self.notifyListeners(evt)
                                break

        if eventName == "AFFILIATE_INTERNET_NAME_UNRESOLVED":
            for data in self.fingerprints:
                if self.checkForStop():
                    return
                service = data.get("service")
                cnames = data.get("cname")
                nxdomain = data.get("nxdomain")

                if not nxdomain:
                    continue

                for cname in cnames:
                    if cname.lower() not in eventData.lower():
                        continue
                    self.info(
                        f"{eventData} appears to be vulnerable to takeover on {service}")
                    evt = SpiderFootEvent(
                        "AFFILIATE_INTERNET_NAME_HIJACKABLE", eventData, self.__name__, event)
                    self.notifyListeners(evt)

# End of sfp_subdomain_takeover class
