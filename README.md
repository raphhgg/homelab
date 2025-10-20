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
   cp .env.example .env.example
   # Edit .env.example with your actual values
   ```
3. **Deploy a service:**
   ```bash
   cd services/<service-name>
   docker-compose up -d
   ```
4. **(Optional) Deploy infrastructure:**
   See [INFRASTRUCTURE.md](infrastructure/README.md)

---
