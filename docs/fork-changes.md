# Changes in this fork (`kolezka/spiderfoottoe`)

This file documents the deltas vs. upstream `poppopjmp/spiderfoot` introduced
by the `kolezka/spiderfoottoe` fork. The fork's goal is **a self-hosted dev
deployment that actually boots, persists configuration, and runs scans
end-to-end** — without the rough edges that surface the first time you bring
up the full Compose stack.

## Summary

| Area | Symptom upstream | Fix in this fork | Commit |
|---|---|---|---|
| Container filesystems | `OSError errno 30 read-only filesystem` on `/home/spiderfoot/cache` whenever a scan task tried to write a cache file in `sf-api`, `sf-celery-worker`, or `sf-celery-worker-active`. The `read_only: true` rootfs had no writable mount for the cache dir. | Added `tmpfs:` mounts for `/home/spiderfoot/cache` (512 MiB) and `/home/spiderfoot/logs` (128 MiB) with `mode=1777` so the non-root `spiderfoot` user can write. Applied to `core.yml` (api + celery-worker) and `scan.yml` (celery-worker-active). | `af41a0eb`, `54833ff1` |
| Module loading | 4 modules (`sfp_adsbexchange`, `sfp_aprsfi`, `sfp_aviationstack`, `sfp_datalastic`) failed at load time with `TypeError: setup() takes 1 positional argument but 3 were given`. Their `setup()` declared `(self)` while the framework calls `(self, sfc, userOpts)`. | Aligned signatures with peer `SpiderFootAsyncPlugin` modules and chained through `super().setup()`. | `989b498f` |
| Permanently broken modules | `sfp_subdomain_takeover` aborted with `Extra data: line 1 column 4 (char 3)` because `haccer/subjack/master/fingerprints.json` is 404. `sfp_bambenek` always failed because the public C2/DGA feeds moved behind paid access. | Flagged both modules `flags: ["deprecated"]`. The `ScanProfile.resolve_modules()` resolver auto-excludes `deprecated`-tagged modules from every profile. | `9b0fc3f1` |
| Tool path discovery | The 33 Go-built recon tools in `Dockerfile.active-scanner` (`subfinder`, `naabu`, `dnsx`, `katana`, `amass`, `masscan`, `hakrawler`, …) were installed under `/tools/bin` but that directory was **not on `$PATH`**. Modules with empty default `*_path` opts silently failed to find binaries. | Added `/tools/bin` to `PATH` in `Dockerfile.active-scanner` (image-level fix) and as a runtime override in `scan.yml` so it works without a rebuild. | `9b0fc3f1` |
| Module config persistence | Saving an API key in **Settings → Modules** returned `success: true` but the value disappeared after F5 refresh — and again after every container restart. Two distinct bugs: (1) `update_module_config()` mutated in-memory state but never called `save_config()`; (2) at boot `configUnserialize()` was called against an empty `__modules__` reference, so all `sfp_NAME:opt` rows in `tbl_config` were dropped — and the next save serialised the empty defaults back over the DB. | `update_module_config` now persists. `Config.__init__` re-runs `configUnserialize()` after filesystem modules are loaded, so DB-stored module options are correctly applied to the populated reference. | `9b0fc3f1`, `d2ab6378` |
| Multi-worker drift | The API runs 4 uvicorn workers; `GET /api/config` and `GET /api/data/modules` read from the per-worker in-memory singleton without reloading from DB. A refresh after a save would land on a sibling worker that had never seen the write and return stale state. | Added `cfg.reload()` to GET `/api/config`, `/api/data/modules`, and `/api/data/modules/{name}` so reads always see DB state regardless of which worker handles the request. `PUT /api/config` and `update_module_config` now also call `save_config()`. | `d2ab6378`, `fc981936` |
| `sf-qdrant` crash-loop | Qdrant panicked on boot: `Can't create Snapshots directory: ReadOnlyFilesystem`. The `QDRANT__STORAGE__SNAPSHOTS_PATH` pointed at `/qdrant/snapshots`, which is on the read-only rootfs. | Pointed the snapshots path at `/qdrant/storage/snapshots`, which is inside the existing `qdrant-data` volume, so snapshots persist with the rest of the data. | `935a4ad4` |
| `sf-pg-backup` crash-loop | The pg-backup sidecar tried to install MinIO's `mc` into `/usr/local/bin`, which fails on a read-only rootfs. After patching that, `mc` then failed to write its alias config to `~/.mc`, also read-only. | Use the shared `/opt/mc-share/mc` binary published by `minio-init`, falling back to downloading into `/tmp` (tmpfs). Pass `--config-dir /tmp` to every `mc` invocation. | `935a4ad4`, `012893dc` |
| Scan logging crashes | When the multiprocessing-spawned scan subprocess tore down (or a stale handler from a prior scan survived spawn), the QueueHandler's queue became `None` or closed, and the stock `QueueHandler.emit` crashed with `AttributeError: 'NoneType' object has no attribute 'put_nowait'` on every subsequent log call — polluting scan output and aborting `__del__` cleanup mid-run. | Wrapped the queue handler with `SafeQueueHandler` that drops a record rather than crashing the operation when the queue is unusable. | `f33b1a73` |
| urllib3 warning spam | OSINT scans deliberately make unverified HTTPS requests to many target hosts. urllib3 emitted a `InsecureRequestWarning` for **every** target, drowning the scan log in identical traceback noise. | Disabled `urllib3.exceptions.InsecureRequestWarning` once at `spiderfoot/__init__.py` import time. | `db201fec` |

## Commit log

```
54833ff1 fix(scan): add writable tmpfs for cache & logs in celery-worker-active
db201fec chore(observability): silence urllib3 InsecureRequestWarning at package import
f33b1a73 fix(logger): swallow None/closed-queue errors in scan QueueHandler
012893dc fix(pg-backup): use --config-dir /tmp so mc works on read-only rootfs
935a4ad4 fix(storage): qdrant snapshots path & pg-backup mc lookup on read-only rootfs
fc981936 fix(api): reload from DB in /data/modules endpoints
d2ab6378 fix(api): persist and reload module options correctly across workers
9b0fc3f1 fix(api,modules,docker): persist module config; disable broken modules; expose tool PATH
989b498f fix(modules): correct setup() signature in 4 async plugin modules
af41a0eb fix(compose): mount writable tmpfs for spiderfoot cache and logs
```

## Why a fork-of-fork?

| Project | Repo | Role |
|---|---|---|
| Original | [`smicallef/spiderfoot`](https://github.com/smicallef/spiderfoot) | Original SpiderFoot by Steve Micallef (since 2012) |
| Active fork | [`poppopjmp/spiderfoot`](https://github.com/poppopjmp/spiderfoot) | Modern v6 microservices rewrite (Agostino "Van1sh" Panico) — the upstream this fork tracks |
| This fork | [`kolezka/spiderfoottoe`](https://github.com/kolezka/spiderfoottoe) | Self-hosted dev fixes — read-only-fs, persistence, logging |

Upstream `poppopjmp/spiderfoot` v6 is an ambitious rewrite (microservices,
GraphQL, AI agents, Vector/Qdrant/MinIO/Tika). The first-boot experience
exposed several integration gaps when you run the full Compose profile
end-to-end: containers couldn't write to their cache dirs because of the
hardened `read_only` rootfs, multi-worker uvicorn dropped saved settings,
and a few modules were stale. This fork fixes those so the stack boots,
persists configuration across restarts, and survives a real scan.

These changes are kept narrowly scoped to maximise the chance of being
useful upstream — there's a clean `git log` of small, single-concern fixes
ready to be cherry-picked.
