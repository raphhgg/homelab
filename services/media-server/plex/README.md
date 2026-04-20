# Plex Remote Access via Pangolin + Pocket ID

This setup exposes Plex externally through Pangolin, with Pocket ID as the login provider.

Everything below is a reusable pattern, not a drop-in config. Replace domains, internal upstream addresses, and access policies to match your own environment.

## Architecture

- Identity: Pocket ID (`https://id.ext.raphh.me`)
- Access gateway: Pangolin resource (`https://plex.ext.raphh.me`)
- Media permissions: Plex users/library sharing
- Internal upstream: Plex origin such as `http://plex-host-or-container:32400`

Request flow:

1. User opens `https://plex.ext.raphh.me`
2. Pangolin checks access policy for the resource
3. User authenticates with Pocket ID
4. Pangolin forwards traffic to your Plex origin (`http://plex-host-or-container:32400`)
5. Plex applies its own account/library permissions

## Plex Remote Access Setting

Because Pangolin is the external entry point, Plex direct remote access/port-forwarding is not required.

Recommended Plex settings:

- Keep router port forwarding for Plex disabled
- Keep UPnP/NAT-PMP automatic mapping disabled on router/Plex
- In Plex network settings, set `Custom server access URLs` to:

```
https://plex.ext.raphh.me
```

Plex auth should remain enabled.

## Permission Layers

Use each system for a specific responsibility:

- Pocket ID: user identity (who the user is)
- Pangolin: network/resource access (who can reach `plex.ext.raphh.me`)
- Plex: media permissions (what they can watch/manage)

## User Onboarding Checklist

1. Create user in Pocket ID
   - Ensure user can log in to `https://id.ext.raphh.me`
   - Ensure user has at least one working passkey

2. Grant Pangolin access
   - Confirm user exists in Pangolin (auto-provision or manual)
   - Assign a role/user policy that allows `plex.ext.raphh.me`

3. Grant Plex library access
   - Invite user in Plex
   - Assign allowed libraries/restrictions

4. Validate end-to-end
   - Open `https://plex.ext.raphh.me` from external network
   - Confirm flow: Pocket ID login -> Plex loads -> playback works

## User Offboarding Checklist

1. Remove access in Pangolin for immediate edge block
2. Remove Plex library access/invite
3. Disable or remove Pocket ID user if needed

## Notes

- `id.ext.raphh.me` should not be protected by Pangolin auth (avoid auth recursion)
- Keep one internal Pangolin owner account as break-glass admin access
