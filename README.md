# Homelab Docker Compose Testing

Automated testing system for Docker Compose services using GitHub Actions. Tests only changed services and prevents broken configurations from reaching production.

## 🚀 Quick Start

1. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

2. **Create a feature branch:**
   ```bash
   git checkout -b feature/update-plex
   ```

3. **Make changes to services:**
   ```bash
   # Edit any service compose file
   nano services/plex/docker-compose.yml
   ```

4. **Push and create PR:**
   ```bash
   git add services/plex/docker-compose.yml
   git commit -m "Update Plex configuration"
   git push origin feature/update-plex
   # Create PR on GitHub
   ```

5. **Tests run automatically** - only for changed services!

## 🏗️ How It Works

### Workflow Triggers

```yaml
on:
  pull_request:
    branches: [ main ]
    paths: [ 'services/**' ]
```

- **When:** Only on pull requests to `main`
- **What:** Only when files in `services/` directory change
- **Smart:** Detects which specific services changed

### Test Pipeline

```bash
🔍 Changed services detection
   ↓
🧪 Individual service testing
   ↓  
🔒 Security scanning
   ↓
📊 Resource validation
   ↓
✅ Results & cleanup
```

## 📋 What Gets Tested

### For Each Changed Service:

1. **Syntax Validation**
   ```bash
   docker-compose config --quiet
   ```

2. **Container Startup**
   ```bash
   docker-compose up -d
   # Wait for initialization
   ```

3. **Health Checks**
   - Container running status
   - Built-in health checks
   - Service-specific functionality

4. **Service-Specific Tests**
   - Web interfaces
   - APIs
   - Directory permissions
   - Network connectivity

### Security Scans (All Services):

- ❌ Default passwords (`admin/admin`, `password/123`)
- ⚠️ Privileged containers
- ⚠️ Services binding to `0.0.0.0`
- ℹ️ Missing resource limits

## 🎯 Service-Specific Tests

### 🎬 Plex (`scripts/tests/plex.sh`)
- Web interface (`http://localhost:32400/web`)
- Plex API endpoints
- Media directory access (`/data/medias`)
- Hardware acceleration (`/dev/dri`)
- Transcoding directory (`/transcode`)

### 📺 Sonarr (`scripts/tests/sonarr.sh`)
- Web UI and API (`http://localhost:8989`)
- Downloads directory (`/downloads`)
- TV shows directory (`/tv` or `/data/medias/tv`)
- Configuration persistence
- PUID/PGID validation

### 🎬 Radarr (`scripts/tests/radarr.sh`)
- Web UI and API (`http://localhost:7878`)
- Downloads directory (`/downloads`)
- Movies directory (`/movies` or `/data/medias/movies`)
- Configuration persistence

### 🔍 Prowlarr (`scripts/tests/prowlarr.sh`)
- Web UI and API (`http://localhost:9696`)
- External network connectivity
- DNS resolution
- Indexer domain accessibility

### ⬇️ qBittorrent (`scripts/tests/qbittorrent.sh`)
- Web UI (`http://localhost:8080`)
- Downloads directory permissions
- External IP detection
- VPN integration checks
- BitTorrent port exposure

### 🛡️ Pi-hole + Unbound (`scripts/tests/pihole_unbound.sh`)
- Pi-hole web interface (`http://localhost/admin`)
- DNS resolution functionality
- Ad blocking validation
- Unbound integration
- DNSSEC support

## ⚡ Performance

### Typical Test Times:
- **Single service change:** ~3-5 minutes
- **Multiple services:** ~6-10 minutes
- **Integration tests:** ~15-20 minutes

### What Affects Speed:
- **Faster:** Config changes, cached images, simple services
- **Slower:** New services, image downloads, heavy services (Plex, databases)

## 🔧 Adding New Service Tests

### 1. Create Service-Specific Test

```bash
# Create new test file
nano scripts/tests/myservice.sh
```

```bash
#!/bin/bash
set -e

echo "🔧 Testing MyService..."

# Wait for service to start
sleep 30

# Test web interface
if curl -f -s http://localhost:8080 > /dev/null; then
    echo "✅ MyService web interface accessible"
else
    echo "❌ MyService web interface not accessible"
    exit 1
fi

# Test specific functionality
if docker exec myservice_myservice_1 test -d /config; then
    echo "✅ MyService config directory accessible"
else
    echo "❌ MyService config directory not found"
    exit 1
fi

echo "🔧 MyService tests completed!"
```

### 2. Make It Executable

```bash
chmod +x scripts/tests/myservice.sh
```

### 3. Test Locally (Optional)

```bash
cd services/myservice
docker-compose up -d
cd ../..
bash scripts/test-service.sh myservice
```

## 🏷️ Integration Testing

For complex multi-service testing, add the `integration-test` label to your PR:

```bash
# Tests service dependencies and communication
# Example: Prowlarr ↔ Sonarr connectivity
```

## 📚 Examples

### Basic Service Update
```bash
# Change Plex memory limit
services/plex/docker-compose.yml:
  mem_limit: 6g  # was 4g

# Result: Only Plex tests run (~3 minutes)
```

### Multiple Service Update
```bash
# Update Sonarr and Radarr
services/sonarr/docker-compose.yml
services/radarr/docker-compose.yml

# Result: Both services tested (~6 minutes)
```

### New Service Addition
```bash
# Add new service
services/newservice/docker-compose.yml

# Result: Default tests run (basic container health)
# Consider adding scripts/tests/newservice.sh
```

## 🚨 Troubleshooting

### Test Failures

```bash
❌ Container failed to start
```
**Solution:** Check compose syntax, environment variables, volume paths

```bash
❌ Web interface not accessible
```
**Solution:** Verify port mapping, container startup time, health checks

```bash
⚠️ Directory not writable
```
**Solution:** Check PUID/PGID settings, volume permissions

### Common Issues

1. **Missing `.env` file**
   ```bash
   # Create from example
   cp .env.example .env
   ```

2. **Wrong PUID/PGID**
   ```bash
   # Check your user ID
   id
   # Update .env accordingly
   ```

3. **Port conflicts**
   ```bash
   # Check what's running on ports
   netstat -tulpn | grep :8080
   ```

## 🔄 Development Workflow

### Safe Development Process:

1. **Branch** → Create feature branch
2. **Develop** → Make changes to services
3. **Test** → Push branch, create PR
4. **Review** → Automated tests + manual review
5. **Deploy** → Merge to main (auto-deploys to NAS)

### Branch Protection Setup:

1. Go to GitHub repo → Settings → Branches
2. Add rule for `main` branch:
   - ✅ Require pull request reviews
   - ✅ Require status checks to pass
   - ✅ Require branches to be up to date
   - Select: `validate-compose`

## 📁 File Structure

```
homelab/
├── .github/workflows/
│   ├── deploy.yml          # Production deployment
│   └── test.yml           # Testing workflow
├── services/              # Docker Compose services
│   ├── plex/
│   ├── sonarr/
│   └── ...
├── scripts/
│   ├── deploy.sh          # Deployment script
│   ├── test-service.sh    # Test dispatcher
│   └── tests/             # Individual service tests
│       ├── default.sh
│       ├── plex.sh
│       └── ...
├── .env                   # Environment variables (create manually)
├── .env.example           # Environment template
└── README.md             # This file
```

## 🎯 Best Practices

### Service Configuration:
- ✅ Always include resource limits (`mem_limit`, `cpu_shares`)
- ✅ Use health checks where possible
- ✅ Avoid privileged containers unless necessary
- ✅ Use specific image tags, not `latest`

### Testing:
- 🧪 Test one service at a time when possible
- 🏷️ Use `integration-test` label sparingly
- 📝 Add service-specific tests for complex services
- 🔄 Run tests locally before pushing

### Security:
- 🔒 Never commit real passwords/API keys
- 🔒 Use `.env` for sensitive values
- 🔒 Review security scan results
- 🔒 Keep images updated

## 🤝 Contributing

1. **Fork** the repository
2. **Create** feature branch (`git checkout -b feature/amazing-feature`)
3. **Add** service or improve existing ones
4. **Test** your changes (create PR to see tests run)
5. **Submit** pull request

For questions or issues, create a GitHub issue with:
- Service name
- Error message
- Test logs
- Expected vs actual behavior

---

**Happy Testing! 🚀** 