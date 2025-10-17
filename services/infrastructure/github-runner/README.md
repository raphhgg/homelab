# GitHub Actions Self-Hosted Runner

Self-hosted GitHub Actions runner for executing CI/CD workflows on the Synology NAS.

## Overview

**Container**: `github-actions-runner`
**Networks**: `main`, `socket_proxy`
**Location**: `services/infrastructure/github-runner/`

This runner provides a self-hosted GitHub Actions environment that can execute workflows with direct access to the NAS resources and Docker infrastructure.

## Current Configuration

**Currently configured for**: `raaphhh/dotfiles` repository

**Runner Details:**
- **Runner name**: `ds423plus-runner-dotfiles`
- **Labels**: `synology`, `dotfiles`, `self-hosted`
- **Access**: Docker Socket Proxy for secure container operations
- **Restart policy**: `unless-stopped`

## Architecture

### Security

The runner connects to Docker via the Docker Socket Proxy for enhanced security:
- No direct access to Docker socket (`/var/run/docker.sock`)
- Limited to allowed Docker API operations via proxy
- Isolated network access through `socket_proxy` network

### Volume Mounts

```yaml
volumes:
  - ${DOCKER_APPDATA_PATH}/github-runner:/data
  - /var/run/docker.sock:/var/run/docker.sock  # For Docker operations
```

## Configuration

### Environment Variables

Required variables in `.env`:
- `GITHUB_OWNER`: GitHub username or organization
- `GITHUB_REPOSITORY`: Repository name (e.g., `dotfiles`)
- `GITHUB_TOKEN`: GitHub Personal Access Token with `repo` and `workflow` scopes

### Token Generation

To generate a GitHub Personal Access Token:
1. Go to GitHub Settings > Developer settings > Personal access tokens
2. Click "Generate new token (classic)"
3. Select scopes:
   - `repo` (Full control of private repositories)
   - `workflow` (Update GitHub Action workflows)
4. Copy token and add to `.env` file

## Usage

### Deploy Runner

```bash
cd services/infrastructure/github-runner
docker-compose up -d
```

### Verify Runner Status

```bash
# Check container logs
docker-compose logs -f github-actions-runner

# Verify runner is registered
# Go to: https://github.com/<owner>/<repo>/settings/actions/runners
```

### Workflow Example

Use the runner in GitHub Actions workflows:

```yaml
name: Deploy to Homelab

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: self-hosted  # Uses any available self-hosted runner
    # Or specify labels:
    # runs-on: [self-hosted, synology, dotfiles]

    steps:
      - uses: actions/checkout@v4

      - name: Deploy changes
        run: |
          echo "Deploying from self-hosted runner"
          # Runner has access to NAS filesystem and Docker
```

## Limitations

### Single Repository Limitation

**Important**: This runner configuration can only serve **one repository at a time**.

The runner is registered to a specific repository and cannot be shared across multiple repositories in this configuration.

**To use with multiple repositories:**

**Option 1: Multiple Runner Instances**
- Deploy separate runner containers for each repository
- Each runner needs its own configuration and GitHub token
- Example:
  ```
  services/infrastructure/github-runner-dotfiles/
  services/infrastructure/github-runner-homelab/
  ```

**Option 2: Organization-Level Runner**
- Create a free GitHub organization
- Register the runner at the organization level
- All repositories in the organization can use the runner
- Configuration: `GITHUB_OWNER=<org-name>`, no repository specified

### Resource Considerations

- Runner consumes minimal resources when idle (~50MB RAM)
- Workflow execution may spike CPU and memory usage
- Consider workflow timeout limits for long-running jobs
- Monitor disk space in `${DOCKER_APPDATA_PATH}/github-runner`

## Deployment Pipeline Status

**Note**: The GitHub Actions deployment pipeline for the homelab repository is currently **not used**.

The runner is configured for the `raaphhh/dotfiles` repository and handles dotfile deployment workflows.

## Troubleshooting

### Runner Not Appearing in GitHub

Check container logs:
```bash
docker-compose logs github-actions-runner
```

Common issues:
- Invalid GitHub token (regenerate token)
- Repository name mismatch
- Network connectivity issues

### Runner Offline

```bash
# Restart runner
docker-compose restart github-actions-runner

# Or redeploy
docker-compose down
docker-compose up -d
```

### Workflow Failures

Check workflow logs in GitHub Actions UI and runner container logs:
```bash
docker-compose logs -f github-actions-runner
```

### Token Expiration

GitHub tokens can expire. If the runner stops working:
1. Generate a new token
2. Update `.env` file
3. Restart runner: `docker-compose restart`

## Migration to Organization Runner

To convert from repository-level to organization-level:

1. **Create GitHub Organization** (free)
2. **Update `.env`**:
   ```bash
   GITHUB_OWNER=<org-name>
   # Remove or comment out GITHUB_REPOSITORY
   ```
3. **Redeploy**:
   ```bash
   docker-compose down
   docker-compose up -d
   ```
4. **Verify** runner appears at:
   `https://github.com/organizations/<org-name>/settings/actions/runners`

## Related Services

- **Docker Socket Proxy**: [../docker-socket-proxy/](../docker-socket-proxy/)
- **Cronicle**: Can trigger GitHub Actions workflows via API

## Resources

- [GitHub Actions Self-Hosted Runners](https://docs.github.com/en/actions/hosting-your-own-runners)
- [Runner Labels](https://docs.github.com/en/actions/hosting-your-own-runners/using-labels-with-self-hosted-runners)
- [Organization Runners](https://docs.github.com/en/actions/hosting-your-own-runners/adding-self-hosted-runners#adding-a-self-hosted-runner-to-an-organization)
