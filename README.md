<p align="center">
<img src="https://raw.githubusercontent.com/poppopjmp/spiderfoot/master/documentation/images/spiderfoot-wide.png" alt="SpiderFoot" />
</p>

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org)
[![Version](https://img.shields.io/badge/version-6.0.0-green)](VERSION)
[![Docker](https://img.shields.io/badge/docker-compose-2496ED?logo=docker)](docker-compose.yml)

# SpiderFoot — `kolezka/spiderfoottoe` fork

SpiderFoot is an open-source intelligence (OSINT) automation platform that
integrates **309+ data sources** to gather intelligence on IP addresses,
domains, hostnames, subnets, ASNs, email addresses, phone numbers,
usernames, Bitcoin addresses, and more. Written in **Python 3** and
**MIT-licensed**.

> ## ⚠ This is a fork-of-a-fork
>
> | Project | Repo | Role |
> |---|---|---|
> | Original | [`smicallef/spiderfoot`](https://github.com/smicallef/spiderfoot) | The original SpiderFoot by Steve Micallef (since 2012) |
> | Upstream | [`poppopjmp/spiderfoot`](https://github.com/poppopjmp/spiderfoot) | Modern v6 microservices rewrite (Agostino "Van1sh" Panico) — what this fork tracks |
> | **This fork** | [`kolezka/spiderfoottoe`](https://github.com/kolezka/spiderfoottoe) | Self-hosted dev fixes for read-only filesystems, multi-worker config persistence, scan logging |
>
> See **[docs/fork-changes.md](docs/fork-changes.md)** for the full changelog with commits.

---

## What this fork fixes

The upstream v6 stack ships with a hardened `read_only: true` rootfs, 4
uvicorn workers, and a 6-stage active-scanner image. The first-boot
experience exposed several integration gaps; this fork addresses them:

- **Containers can write again** — `tmpfs` mounts for `/home/spiderfoot/cache` and `/logs` on api, celery-worker, and celery-worker-active. `qdrant` snapshots moved into the persistent volume. `pg-backup` no longer tries to write to `/usr/local/bin`.
- **Module API keys actually persist** — `Config.__init__` now correctly applies DB-stored module options on boot, and `GET /api/config` and `GET /api/data/modules` reload from the DB so refreshes after a save show the latest state across all 4 API workers.
- **Modules with stale signatures load again** — `sfp_adsbexchange`, `sfp_aprsfi`, `sfp_aviationstack`, `sfp_datalastic` had broken `setup()` signatures.
- **Permanently broken modules are auto-skipped** — `sfp_subdomain_takeover` (upstream fingerprints 404) and `sfp_bambenek` (free feeds gone) flagged `deprecated`, excluded by every scan profile.
- **Active-scanner tools resolve via PATH** — `/tools/bin` (subfinder, naabu, dnsx, masscan, amass, …) is now on `PATH`.
- **Scan logging survives subprocess teardown** — `SafeQueueHandler` drops a record rather than crashing the scan when the multiprocessing log queue is `None`.
- **Cleaner scan output** — urllib3's per-host `InsecureRequestWarning` is silenced once at package import.

Full per-commit detail: **[docs/fork-changes.md](docs/fork-changes.md)**.

---

## Quick Start

```bash
git clone git@github.com:kolezka/spiderfoottoe.git
cd spiderfoottoe

# Configure environment (passwords, optional API keys)
cp .env.example .env

# Core only — 5 services: postgres, redis, api, worker, frontend
docker compose up --build -d

# Or full stack — adds object storage, vector DB, observability, AI
docker compose --profile storage --profile scan --profile ai --profile monitor up --build -d
```

**Core (no profile)** — `http://localhost:3000`:

| URL | Service |
|-----|---------|
| `http://localhost:3000` | React SPA |
| `http://localhost:3000/api/docs` | Swagger / OpenAPI |

**Full stack with `--profile proxy`** — `https://localhost` via Traefik:

| URL | Service |
|-----|---------|
| `https://localhost` | React SPA |
| `https://localhost/api/docs` | Swagger / OpenAPI |
| `https://localhost/api/graphql` | GraphiQL IDE |
| `https://localhost/grafana/` | Grafana dashboards |
| `https://localhost/flower/` | Celery Flower |
| `https://localhost/minio/` | MinIO console |
| `https://localhost/traefik/` | Traefik dashboard |

Default admin credentials: `admin / admin` (change in `.env`).

---

## Documentation

| Doc | Topic |
|-----|-------|
| **[docs/architecture.md](docs/architecture.md)** | Stack diagram, deployment modes, all services & profiles, volumes, security hardening |
| **[docs/api.md](docs/api.md)** | REST + GraphQL + Vector + MinIO endpoints, LiteLLM gateway, env-var configuration |
| **[docs/scanning.md](docs/scanning.md)** | Active-scanner build, scan profiles, modules, correlation engine, AI agents, document enrichment, user input |
| **[docs/operations.md](docs/operations.md)** | Go CLI, observability stack, Web UI, frontend testing |
| **[docs/development.md](docs/development.md)** | Project layout, running tests, version management, use cases |
| **[docs/fork-changes.md](docs/fork-changes.md)** | Per-commit fork changelog |
| `documentation/` | Upstream `poppopjmp` docs (preserved verbatim — installation, modules, API reference, troubleshooting, …) |

---

## License

[MIT](LICENSE) — same as both upstreams.

## Credits

- **Steve Micallef** — original SpiderFoot author (since 2012)
- **Agostino "Van1sh" Panico** — `poppopjmp/spiderfoot` v6 microservices rewrite
- **`kolezka`** — this fork (read-only-fs, persistence, logging fixes)
