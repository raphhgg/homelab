# Pocket ID Integration Blueprint

This guide is a reusable blueprint for adding authentication to a new service in this homelab.

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
- Ensure `https://id.raphh.me` and `https://auth.raphh.me` are reachable
- Ensure DNS rewrites resolve `*.raphh.me` to Traefik (`10.10.2.201`) on LAN
- Ensure Traefik has a router for the service domain
- Ensure Pocket ID user groups exist for access control (example: `admins`)
- Keep all secrets in `.env` (never hardcode in compose files)

Recommended naming:
- App URL: `https://<service>.raphh.me`
- Pocket ID client name: `<service>-oidc` (for native OIDC)
- TinyAuth app key: `<service>`

---

## Pattern A - Traefik + TinyAuth

Use this when the app does not support OIDC.

### 1) Register app policy in TinyAuth

In `services/infrastructure/tinyauth/docker-compose.yml`, add labels on `tinyauth`:

```yaml
- "tinyauth.apps.<service>.config.domain=<service>.raphh.me"
- "tinyauth.apps.<service>.oauth.groups=<pocketid_group>"
```

Then wire variables in `services/infrastructure/tinyauth/.env.example` and `.env`.

Example variables:

```env
SERVICE_HOST=<service>.raphh.me
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
curl -k -i -H "Accept: text/html" https://<service>.raphh.me/
curl -k -i https://auth.raphh.me/login
```

Expected first response: `307` redirect to `auth.raphh.me/login?...`

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
SSO_AUTHORITY=https://id.raphh.me
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
curl -k -I https://id.raphh.me/.well-known/openid-configuration
```

Expected: `200`.

---

## Common Pitfalls

- DNS split-brain: client resolves public Cloudflare IP instead of local Traefik IP
- Wrong callback URL in Pocket ID client (must be exact)
- Group mismatch (`admins` in TinyAuth but user not in that Pocket ID group)
- Non-HTML clients hitting forward-auth path get `401` instead of redirect (normal)
- App-level auth still enabled when expecting single-login UX
- Service-specific runtime config overriding `.env`

## Standard Validation Checklist

- [ ] `nslookup <service>.raphh.me` returns `10.10.2.201` on client
- [ ] `https://id.raphh.me` opens from same client
- [ ] `https://auth.raphh.me/login` opens from same client
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
MYSERVICE_HOST=mysvc.your_domain
MYSERVICE_OAUTH_GROUPS=admins
```

2) Add to `services/infrastructure/tinyauth/.env`:

```env
MYSERVICE_HOST=mysvc.raphh.me
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
      rule: "Host(`mysvc.raphh.me`)"
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
          - url: "http://10.10.2.123:8080"
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
OIDC_ISSUER=https://id.your_domain
```

3) Add real values to service `.env`:

```env
OIDC_ENABLED=true
OIDC_CLIENT_ID=real_client_id
OIDC_CLIENT_SECRET=real_client_secret
OIDC_ISSUER=https://id.raphh.me
```

4) Restart service and test SSO login path.

### Smoke test snippet (both patterns)

```bash
nslookup mysvc.raphh.me
curl -k -I https://id.raphh.me/.well-known/openid-configuration
curl -k -i -H "Accept: text/html" https://mysvc.raphh.me/
```
