# Installation Guide

*Author: poppopjmp*

This guide will walk you through installing SpiderFoot v6.0.0 on Linux, macOS, or Windows, as well as deploying with Docker for easy setup and portability. SpiderFoot includes 309 modules with advanced capabilities for TikTok OSINT, blockchain analytics, performance optimization, and AI-powered analysis.

---

## Requirements

- **Docker with Docker Compose** to run the stack
- **Python 3.11 or higher and pip** only for local Python development
- **Git** (for cloning the repository)
- **Memory**: Minimum 2GB RAM (4GB+ recommended for enhanced features)
- **Disk Space**: Minimum 2GB (additional space for caching and databases)

### Enhanced Features Requirements

For full functionality of enhanced modules:

- **API Keys**: TikTok Research API, BlockCypher, Etherscan, OpenAI (see [Configuration](configuration.md))
- **Additional Memory**: +500MB for performance optimization and caching
- **Network Access**: Outbound HTTPS for blockchain APIs and AI services

## Installation Steps (Linux, macOS, Windows)

1. **Clone this fork:**

   ```sh
   git clone https://github.com/kolezka/spiderfoottoe.git
   cd spiderfoottoe
   ```

2. **Start the core stack** using the Docker Compose instructions below. The images install the Python dependencies; you do not need to install them on the host.

3. Once the frontend is ready, open [http://127.0.0.1:3000](http://127.0.0.1:3000).

---

## Docker Installation

Docker is the easiest way to run SpiderFoot in a portable, isolated environment.

- **Run with Docker Compose (profiles):**

  ```sh
  cp .env.example .env
  # Edit .env — change passwords, uncomment profile sections as needed

  # The API and worker depend on a local base image; Compose does not build it.
  docker build -f docker/Dockerfile.base -t spiderfoot-base:latest .

  # Core only (5 services: postgres, redis, api, worker, frontend)
  docker compose -f docker-compose.yml up --build -d

  # Alternatively, start the full profile instead of core only:
  # docker compose -f docker-compose.yml --profile full up --build -d
  ```

  See [Docker Deployment Guide](docker_deployment.md) for available profiles and advanced configuration.

---

## Upgrading SpiderFoot

- To upgrade, pull the latest code from GitHub and reinstall dependencies:

  ```sh
  git pull
  pip install -r requirements.txt
  ```
- For Docker, pull the latest image:

  ```sh
  docker pull poppopjmp/spiderfoot
  ```

---

## Troubleshooting

- If you see missing dependency errors, run `pip install -r requirements.txt` again.
- For permission errors, try running as administrator or with `sudo` (Linux/macOS).
- For Docker issues, check container logs with `docker logs <container_id>`.
- See the [Troubleshooting Guide](troubleshooting.md) for more help.

---

Continue to the [Getting Started](getting_started.md) guide to launch your first scan.

