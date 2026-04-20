# Pocket ID Integration Blueprint

This guide is a reusable blueprint for adding authentication to a new service.

It covers two patterns:
- Pattern A: service behind Traefik + TinyAuth (forward-auth gate)
- Pattern B: service uses native OIDC directly with Pocket ID

## Quick Decision Tree

Use TinyAuth when:
- The service has no OIDC support
- You want simple access gating in front of the app
- You accept that app-level login may still exist (double login)

Use native OIDC when:
- The service supports OpenID Connect well
- You want true in-app SSO identity
- You want to avoid TinyAuth-only sessions for that app

## Shared Prerequisites

Before integrating any new service:
- Ensure your Pocket ID issuer URL and TinyAuth URL are reachable
- Ensure local DNS or your reverse proxy resolves service domains to the correct ingress endpoint
- Ensure Traefik has a router for the service domain
- Ensure Pocket ID user groups exist for access control (example: `admins`)
- Keep all secrets in `.env` (never hardcode in compose files)

Recommended naming:
- App URL: `https://<service>.example.com`
- Pocket ID client name: `<service>-oidc` (for native OIDC)
- TinyAuth app key: `<service>`

---

## Pattern A - Traefik + TinyAuth

Use this when the app does not support OIDC.

### 1) Register app policy in TinyAuth

In `services/infrastructure/tinyauth/docker-compose.yml`, add labels on `tinyauth`:

```yaml
- "tinyauth.apps.<service>.config.domain=<service>.example.com"
- "tinyauth.apps.<service>.oauth.groups=<pocketid_group>"
```

Then wire variables in `services/infrastructure/tinyauth/.env.example` and `.env`.

Example variables:

```env
SERVICE_HOST=<service>.example.com
SERVICE_OAUTH_GROUPS=admins
```

### 2) Add forward-auth middleware to Traefik route

In Traefik dynamic config (`dynamic.yml`), the router for the app should include:

```yaml
middlewares:
  - allow-admin-apps
  - tinyauth
```

And middleware definition:

```yaml
tinyauth:
  forwardAuth:
    address: "http://tinyauth:3000/api/auth/traefik"
    trustForwardHeader: true
```

### 3) Keep or remove app-local auth

- Default: keep app-local auth enabled (more secure, double login)
- Optional: disable app-local auth for single login UX
  - Only do this if direct app access is blocked except via Traefik

### 4) Verify

- Unauthenticated request to app should redirect to TinyAuth login
- After Pocket ID login, request should return to app URL
- TinyAuth should enforce group access

Useful checks:

```bash
curl -k -i -H "Accept: text/html" https://<service>.example.com/
curl -k -i https://auth.example.com/login
```

Expected first response: `307` redirect to your TinyAuth login flow.

---

## Pattern B - Native OIDC (no TinyAuth in front)

Use this when the app supports OIDC directly.

### 1) Create OIDC client in Pocket ID

In Pocket ID admin:
- Create client for `<service>`
- Set redirect/callback URI exactly as required by the app
- Assign allowed user groups (for example `admins`)
- Note client ID and client secret

### 2) Configure app OIDC settings

In service `.env.example` add placeholders, for example:

```env
SSO_ENABLED=false
SSO_CLIENT_ID=your_client_id
SSO_CLIENT_SECRET=your_client_secret
SSO_AUTHORITY=https://id.example.com
```

In service `.env` set real values and enable SSO.

### 3) Ensure app runtime config is not overriding env

Some apps persist config in their own data file/DB (for example `config.json`) and can override env values.

If behavior does not match env:
- Check app admin UI settings
- Check runtime config file under appdata
- Restart container after updating settings

### 4) Verify

- Open app login page and choose SSO/OIDC option
- Confirm redirect to Pocket ID authorize endpoint
- Confirm callback returns to app and creates session

Useful checks:

```bash
curl -k -I https://id.example.com/.well-known/openid-configuration
```

Expected: `200`.

---

## Common Pitfalls

- DNS split-brain: client resolves the wrong ingress IP or bypasses your intended proxy path
- Wrong callback URL in Pocket ID client (must be exact)
- Group mismatch (`admins` in TinyAuth but user not in that Pocket ID group)
- Non-HTML clients hitting forward-auth path get `401` instead of redirect (normal)
- App-level auth still enabled when expecting single-login UX
- Service-specific runtime config overriding `.env`

## Standard Validation Checklist

- [ ] `nslookup <service>.example.com` returns the expected ingress IP on client
- [ ] `https://id.example.com` opens from same client
- [ ] `https://auth.example.com/login` opens from same client
- [ ] Pocket ID user is in required group
- [ ] Traefik route and middleware chain are correct
- [ ] Login flow returns to expected service URL

## Change Checklist (for this repo)

When integrating a new service:
- Update service `docker-compose.yml`
- Update service `.env.example` with placeholders
- Update service `.env` with real values (local only, gitignored)
- Update Traefik dynamic config when needed
- Update TinyAuth labels/env when using Pattern A
- Restart only affected stacks and test end-to-end

## Copy/Paste Templates

Use these as starting blocks when integrating a new service.

### Template A - TinyAuth protected service

1) Add to `services/infrastructure/tinyauth/.env.example`:

```env
MYSERVICE_HOST=mysvc.example.com
MYSERVICE_OAUTH_GROUPS=admins
```

2) Add to `services/infrastructure/tinyauth/.env` with your real domain:

```env
MYSERVICE_HOST=mysvc.example.com
MYSERVICE_OAUTH_GROUPS=admins
```

3) Add labels to `tinyauth` in `services/infrastructure/tinyauth/docker-compose.yml`:

```yaml
- "tinyauth.apps.myservice.config.domain=${MYSERVICE_HOST}"
- "tinyauth.apps.myservice.oauth.groups=${MYSERVICE_OAUTH_GROUPS}"
```

4) Add router/service to Traefik dynamic config:

```yaml
http:
  routers:
    myservice:
      rule: "Host(`mysvc.example.com`)"
      entryPoints:
        - websecure
      middlewares:
        - allow-admin-apps
        - tinyauth
      service: myservice-service
      tls:
        certResolver: cloudflare

  services:
    myservice-service:
      loadBalancer:
        passHostHeader: true
        servers:
          - url: "http://myservice:8080"
```

5) Restart relevant stacks:

```bash
docker compose -f services/infrastructure/tinyauth/docker-compose.yml up -d
docker compose -f services/infrastructure/traefik/docker-compose.yml up -d
```

### Template B - Native OIDC service

1) Create Pocket ID client:
- Name: `myservice-oidc`
- Redirect URI: app specific callback URL
- Allowed groups: usually `admins`

2) Add placeholders to service `.env.example`:

```env
OIDC_ENABLED=OIDC_ENABLED
OIDC_CLIENT_ID=your_client_id
OIDC_CLIENT_SECRET=your_client_secret
OIDC_ISSUER=https://id.example.com
```

3) Add real values to service `.env`:

```env
OIDC_ENABLED=true
OIDC_CLIENT_ID=your_client_id
OIDC_CLIENT_SECRET=your_client_secret
OIDC_ISSUER=https://id.example.com
```

4) Restart service and test SSO login path.

### Smoke test snippet (both patterns)

```bash
nslookup mysvc.example.com
curl -k -I https://id.example.com/.well-known/openid-configuration
curl -k -i -H "Accept: text/html" https://mysvc.example.com/
```
