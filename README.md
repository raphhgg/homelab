# Homelab

> Documentation for my self-hosted home server. Includes Docker stacks for the different services, infrastructure and deployement pipeline.

---

**WORK IN PROGRESS**

## Table Of Contents

* Quick Start
* Infrastructure
   * Servers & NAS
   * Networking
   * Smart Home
* Services
   * Media Server 
   * Home Assistant
   * Monitoring
   * Proxy Management
* Deployement Pipeline

// each readme in subfolder

---

## 🚀 Quick Start

1. **Clone the repo:**
   ```bash
   git clone <your-repo-url>
   cd homelab
   ```
2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```
3. **Deploy a service:**
   ```bash
   cd services/<service-name>
   docker-compose up -d
   ```
4. **(Optional) Deploy infrastructure:**
   See [INFRASTRUCTURE.md](infrastructure/README.md)

---

## 🚢 Deployment

Deployment is automated via GitHub Actions using a self-hosted runner (see [infrastructure/github-runner](infrastructure/github-runner/)).

### Triggers
- **Automatic:** On push to `main` branch affecting `services/**`
- **Manual:** Via GitHub Actions workflow dispatch (with options for dry-run or deploy-all)

### Workflow Steps
1. **Environment Setup:**
   - Creates `.env` on the runner with secrets from GitHub
   - Uses `scripts/deploy/00_create_job_env.sh`
2. **Deploy Services:**
   - Runs `scripts/deploy/01_deploy.sh` (with optional flags)
   - Deploys only changed or all services
3. **Sync to NAS/Compose Directory:**
   - Creates directory structure, syncs repo, generates metadata, creates management helpers, verifies sync
   - Uses scripts: `02_create_compose_dirs.sh`, `03_debug_env.sh`, `04_sync_repo.sh`, `05_create_metadata.sh`, `06_create_manage_helper.sh`, `07_verify_sync.sh`
4. **Notify:**
   - Sends deployment status to Discord via `08_notify_status.sh`

For script details, see [SCRIPTS.md](SCRIPTS.md).

---
