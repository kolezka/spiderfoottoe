# Scanning Features

## Active Scan Worker

SpiderFoot includes a **dedicated active scan worker** — a separate Celery container that ships **33+ external reconnaissance tools** for comprehensive target assessment. The active worker handles all scan tasks on a dedicated `scan` queue, keeping general tasks isolated.

### Architecture

```
┌─────────────────────────────────────┐
│         Redis (broker)              │
└──────┬──────────────────┬───────────┘
       │                  │
       ▼                  ▼
┌──────────────┐   ┌───────────────────────┐
│ celery-worker│   │ celery-worker-active   │
│ (general)    │   │ (scanning)             │
│              │   │                        │
│ queues:      │   │ queue: scan            │
│ default,     │   │                        │
│ report,      │   │ 33+ recon tools:       │
│ export,      │   │ httpx, subfinder,      │
│ agents,      │   │ amass, gobuster, dnsx, │
│ monitor      │   │ naabu, masscan, katana,│
│              │   │ nikto, nuclei, nmap,   │
│              │   │ and 22 more...         │
└──────────────┘   └───────────────────────┘
```

### Tools Included

The active worker builds on top of the base image (which includes nmap, nuclei, testssl.sh, whatweb, dnstwist, CMSeeK, retire.js, trufflehog, wafw00f, nbtscan, onesixtyone, snallygaster) and adds:

| Category | Tools |
|----------|-------|
| **DNS & Subdomains** | httpx, subfinder, amass, dnsx, massdns, gobuster |
| **Web Crawling** | katana, gospider, hakrawler, gau, waybackurls |
| **Web Fuzzing** | ffuf, arjun |
| **Port Scanning** | naabu, masscan |
| **Vulnerability** | nikto, dalfox |
| **SSL/TLS** | tlsx, sslyze, sslscan |
| **Secrets/JS** | gitleaks, linkfinder |
| **Screenshots** | gowitness (with Chromium) |
| **Wordlists** | 8 curated SecLists + DNS resolvers |

### Build

```bash
# Build everything (base + active worker)
docker compose --profile scan up --build -d

# Or build just the active worker
docker build -f docker/Dockerfile.active-scanner -t spiderfoot-celery-worker-active:latest .
```

See [documentation/active-scan-worker.md](../documentation/active-scan-worker.md) for full details.

## Scan Profiles

SpiderFoot ships with **11 predefined scan profiles** for common use cases. Profiles control which modules are enabled, option overrides, and execution constraints.

| Profile | Description | Key Modules |
|---------|-------------|-------------|
| **quick-recon** | Fast passive scan, no API keys | Passive modules only |
| **full-footprint** | Comprehensive active footprinting | All non-Tor modules |
| **passive-only** | Zero direct target interaction | Strictly passive |
| **vuln-assessment** | Vulnerability & exposure focus | Vuln scanners, reputation |
| **tools-only** | All external recon tools | 36 tool modules (requires active worker) |
| **social-media** | Social media presence discovery | Social & secondary networks |
| **dark-web** | Tor hidden service search | Tor-enabled modules |
| **infrastructure** | DNS, ports, hosting, SSL mapping | DNS, infrastructure |
| **api-powered** | Premium API data sources only | API-key modules |
| **minimal** | Bare minimum for validation | DNS resolve, spider |
| **investigate** | Deep targeted investigation | Investigation modules |

### Tools-Only Profile

The `tools-only` profile runs **all 36 external tool modules** against a target. It includes `sfp_dnsresolve` and `sfp_spider` as core helpers to feed discovered data into the tool pipeline.

```bash
# Start a tools-only scan via API
curl -X POST http://localhost/api/scans \
  -H "Content-Type: application/json" \
  -d '{"target": "example.com", "type": "DOMAIN_NAME", "profile": "tools-only"}'
```

Profiles are managed via `spiderfoot.scan.scan_profile.ProfileManager` — see [documentation/developer_guide.md](../documentation/developer_guide.md).

## Modules

SpiderFoot has **309 modules**, most of which do not require API keys. Modules feed each other in a publisher/subscriber model for maximum data extraction.

### Module Categories

| Category | Examples | Count |
|----------|----------|-------|
| **DNS & Infrastructure** | DNS resolver, zone transfer, brute-force | ~20 |
| **Social Media** | Twitter, Instagram, Reddit, Telegram, TikTok | ~15 |
| **Threat Intelligence** | Shodan, VirusTotal, AlienVault, GreyNoise | ~30 |
| **Search Engines** | Google, Bing, DuckDuckGo, Baidu | ~10 |
| **Data Breaches** | HaveIBeenPwned, LeakCheck, Dehashed, Hudson Rock | ~11 |
| **Crypto & Blockchain** | Bitcoin, Ethereum, Tron, BNB | ~8 |
| **Reputation / Blacklists** | Spamhaus, SURBL, PhishTank, DNSBL | ~30 |
| **Internal Analysis** | Extractors, validators, identifiers | ~25 |
| **External Tools** | 36 tools: httpx, amass, nmap, nuclei, nikto, gobuster, etc. | ~36 |
| **Cloud Storage** | S3, Azure Blob, Google Cloud, DigitalOcean | ~5 |

For the full module list, see [documentation/modules.md](../documentation/modules.md).

## Correlation Engine

SpiderFoot includes a YAML-configurable rule engine with **95 pre-defined correlation rules**.

```bash
# View all rules
ls correlations/*.yaml

# Template for writing new rules
cat correlations/template.yaml
```

Rule categories: vulnerability severity, exposure detection, cross-scan outliers, stale hosts, infrastructure analysis, blockchain risk aggregation.

See [correlations/README.md](../correlations/README.md) for the full reference.

## AI Agents

Six LLM-powered agents automatically analyze high-risk findings and produce structured intelligence. They subscribe to Redis event bus topics and process events asynchronously.

| Agent | Trigger Events | Output |
|-------|---------------|--------|
| **FindingValidator** | `MALICIOUS_*`, `VULNERABILITY_*` | Verdict (confirmed/likely_false_positive), confidence, remediation |
| **CredentialAnalyzer** | `LEAKED_CREDENTIALS`, `API_KEY_*` | Severity, active status, affected services |
| **TextSummarizer** | `RAW_*`, `TARGET_WEB_CONTENT` | Summary, entities, sentiment, relevance score |
| **ReportGenerator** | `SCAN_COMPLETE` | Executive summary, threat assessment, recommendations |
| **DocumentAnalyzer** | `DOCUMENT_UPLOAD`, `USER_DOCUMENT` | Entities, IOCs, classification, scan targets |
| **ThreatIntelAnalyzer** | `MALICIOUS_*`, `CVE_*`, `DARKNET_*` | MITRE ATT&CK mapping, threat actor attribution |

API: `http://localhost/agents/` — see [documentation/ARCHITECTURE.md](../documentation/ARCHITECTURE.md) for endpoints.

## Document Enrichment

Upload documents (PDF, DOCX, XLSX, HTML, RTF, plain text) for automated entity and IOC extraction.

### Pipeline

1. **Convert** — Document → plain text (pypdf, python-docx, openpyxl, etc.)
2. **Extract** — Regex-based entity extraction (IPs, domains, hashes, CVEs, crypto addresses, etc.)
3. **Store** — Original + extracted content → MinIO `sf-enrichment` bucket
4. **Analyze** — Forward to DocumentAnalyzer agent for LLM-powered intelligence

API: `POST http://localhost/enrichment/upload` (100MB limit)

## User-Defined Input

Supply your own documents, IOCs, reports, and context to augment automated OSINT collection.

| Endpoint | Description |
|----------|-------------|
| `POST /input/document` | Upload document → enrichment → agent analysis |
| `POST /input/iocs` | Submit IOC list (IPs, domains, hashes) with dedup |
| `POST /input/report` | Structured report → entity extraction → analysis |
| `POST /input/context` | Set scope, exclusions, threat model for a scan |
| `POST /input/targets` | Batch target list for multi-scan |
