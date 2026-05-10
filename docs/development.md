# Development

## Project Structure

```
spiderfoot/
├── api/                  # FastAPI application (38+ routers)
│   ├── graphql/          # Strawberry GraphQL (queries, mutations, subscriptions)
│   ├── routers/          # REST endpoint routers
│   ├── schemas.py        # Pydantic v2 contracts
│   └── versioning.py     # /api/v1/ prefix
├── agents/               # AI analysis agents (6 LLM-powered)
├── enrichment/           # Document enrichment pipeline
├── user_input/           # User-defined input ingestion
├── config/               # App configuration
├── db/                   # Database layer (repositories, migrations)
├── events/               # Event types, relay, dedup
├── plugins/              # Module loading and registry
├── security/             # Auth, CSRF, middleware
├── services/             # External integrations (embedding, cache, DNS)
├── observability/        # Logging, metrics, health, tracing
├── reporting/            # Report generation and export
├── cli/commands/         # Python CLI commands (25 commands)
└── vector_correlation.py # Vector correlation engine
cli/                      # Go CLI (cross-platform, Cobra-based)
├── cmd/                  # Commands: scan, modules, export, schedule, health, config
├── internal/client/      # HTTP client with auth, TLS
├── internal/output/      # Table, JSON, CSV formatters
├── Makefile              # Cross-compilation (6 targets)
└── go.mod                # Go module definition
frontend/                 # React SPA (TypeScript + Vite + Tailwind)
├── src/components/       # UI components (20+ primitives, Layout, NotificationCenter, CommandPalette)
├── src/pages/            # 14 pages (Dashboard, Scans, ScanDetail, Schedules, ...)
├── src/hooks/            # Custom hooks (useScanProgress SSE)
├── src/lib/              # API client, auth, notifications store
├── src/__tests__/        # 282 tests — Vitest + Testing Library
└── vite.config.ts        # Build config
infra/                    # Infrastructure configs
├── grafana/              # Dashboards + datasource provisioning
├── loki/                 # Loki local config (MinIO S3 backend)
├── litellm/              # LiteLLM model config
└── prometheus/           # Scrape targets config
modules/                  # 309 OSINT modules
correlations/             # 95 YAML correlation rules
documentation/            # Comprehensive upstream docs (preserved)
docs/                     # This fork's curated docs (architecture, api, scanning, ...)
scripts/                  # Utility and maintenance scripts
docker/                   # Docker build files + nginx config
helm/                     # Kubernetes Helm chart
```

## Running Tests

```bash
# Backend tests
pip install -r requirements.txt
pytest --tb=short -q

# Frontend tests (282 tests, 27 files)
cd frontend && npx vitest run

# Go CLI tests
cd cli && go test ./...
```

## Version Management

```bash
cat VERSION                            # Check current version
python update_version.py --set 6.0.1   # Update all references
python update_version.py --check       # Validate consistency
```

## Use Cases

### Offensive Security (Red Team / Pen Test)

- Target reconnaissance and attack surface mapping
- Sub-domain discovery and hijack detection
- Credential exposure discovery
- Technology stack fingerprinting

### Defensive Security (Blue Team)

- Asset inventory and shadow IT detection
- Data breach monitoring
- Brand protection and phishing detection
- Threat intelligence enrichment

### Scan Targets

IP addresses · domains · subdomains · hostnames · CIDR subnets · ASNs · email addresses · phone numbers · usernames · person names · Bitcoin/Ethereum addresses
