# Operations: CLI, Observability, Web UI

## CLI (Go)

SpiderFoot ships with a **cross-platform Go CLI** (`cli/`) that compiles to a single static binary for Linux, macOS, and Windows. Built with [Cobra](https://github.com/spf13/cobra) and [Viper](https://github.com/spf13/viper).

```bash
cd cli && go build -o sf .

# Health check
sf health --server http://localhost:8001

# Scan management
sf scan list
sf scan start --target example.com --name "Recon"
sf scan get <scan-id>
sf scan stop <scan-id>

# Export
sf export json <scan-id>
sf export stix <scan-id>

# Schedules
sf schedule list
sf schedule create --name "Daily" --target example.com --interval 24

# Modules
sf modules --filter passive -o json
```

Cross-compile for all platforms:

```bash
cd cli && make all
# Produces: build/sf-linux-amd64, sf-darwin-arm64, sf-windows-amd64.exe, ...
```

Configuration via flags, `SF_*` environment variables, or `~/.spiderfoot.yaml`. See [cli/README.md](../cli/README.md) for full documentation.

## Monitoring & Observability

SpiderFoot includes a complete observability stack, with **Vector.dev** serving as the unified telemetry pipeline (replacing both Promtail and OpenTelemetry Collector).

| Component | Purpose | Access |
|-----------|---------|--------|
| **Grafana** | Dashboards, alerting, log/metric exploration | `http://localhost:3000` |
| **Loki** | Log aggregation (backed by MinIO S3 storage) | via Grafana |
| **Prometheus** | Metrics collection from all services | `http://localhost:9090` |
| **Jaeger** | Distributed tracing (OTLP via Vector.dev) | `http://localhost:16686` |
| **Vector.dev** | Log/metrics/traces pipeline | Internal |

### Pre-built Dashboards

Five Grafana dashboards are auto-provisioned: Platform Overview (19 panels), Scan Operations (22 panels), Celery Task Queue (16 panels), Infrastructure (22 panels), and Service Logs (17 panels).

## Web UI

SpiderFoot ships with a modern **React SPA** built with TypeScript, Vite, and Tailwind CSS. The UI features a dark theme with cyan accents, responsive layout, and real-time scan updates via WebSocket subscriptions.

### Login

Secure JWT-based authentication with SSO support (OIDC/SAML).

### Dashboard

The main dashboard provides at-a-glance statistics — active scans, total events, risk distribution, and recent activity.

### New Scan

Configure and launch OSINT scans against domains, IPs, email addresses, usernames, and more. Select module categories, set scan options, and start with a single click.

### Scan Detail Tabs

| Tab | Purpose |
|-----|---------|
| **Summary** | Key metrics, risk distribution, top modules, event-type breakdown |
| **Browse** | All discovered events filterable by type, risk, source module, with provenance |
| **Graph** | Interactive force-directed graph of entity relationships |
| **GeoMap** | World map plotting discovered IP locations with country aggregation |
| **Correlations** | YAML rule engine findings — severity, evidence, remediation |
| **AI Report** | LLM-generated CTI report (executive summary, findings, recommendations) |

### Workspaces

Organize scans into workspaces for multi-target campaigns. Each workspace groups related scans, tracks notes, and provides workspace-level analytics and AI-generated reports.

### Settings

Configure global application settings, module API keys, notification preferences, and scan defaults.

### Agents

Monitor and manage the 6 AI-powered analysis agents. View agent status, processed event counts, and recent analysis results.

### UX Features

- **Tooltip** — accessible, portal-based, viewport-clamped tooltips with `aria-describedby`
- **Real-time Progress** — SSE-powered scan progress bar with per-module breakdown
- **Celebration Banner** — animated success state when a scan completes
- **Notification Center** — bell icon with unread badge, panel (Zustand store, max 50 items)
- **Command Palette** — `Ctrl+K` / `⌘K` fuzzy search across pages and recent scans
- **Schedules Page** — full CRUD for recurring scan schedules
- **STIX 2.1 Export** — one-click export of scan data as a STIX bundle

Screenshots are in [documentation/images/](../documentation/images/).

## Frontend Testing

The React frontend includes **282 tests** across 27 test files, powered by Vitest 3 and Testing Library:

| Suite | Tests | Coverage |
|-------|-------|----------|
| UI Components | 47 | Button, Badge, StatusBadge, ProgressBar, CardSkeleton, EmptyState, ConfirmDialog, Toast, Tabs, ModalShell, PageHeader, RiskPills |
| API Layer | 45 | All endpoint methods, error handling, auth headers, AbortSignal |
| Auth | 36 | Login, logout, token refresh, SSO flows, role guards |
| Login Page | 21 | Form validation, submission, SSO redirects, error states |
| Layout | 18 | Navigation items, sidebar, responsive, NotificationCenter, CommandPalette |
| Markdown Renderer | 16 + 14 | DOMPurify sanitization, XSS prevention, rendering |
| Emotional Design | 13 | Tooltip lifecycle, notification store CRUD, cap enforcement |
| Sanitize | 7 | DOMPurify integration, script stripping, attribute cleaning |
| ErrorBoundary | 8 | Crash recovery, fallback UI, error logging |
| Schedules | 4 | Page rendering, empty state, data display, create modal |
| Safe Storage | 4 | localStorage quota handling |
| Scan Tabs | 5 | GraphTab, BrowseTab, LogTab, GeoMapTab smoke tests |
| CommandPalette | 7 | Keyboard shortcuts, search, filtering, ARIA |

```bash
cd frontend && npx vitest run    # Run all tests
cd frontend && npx vitest --ui   # Interactive UI mode
```
