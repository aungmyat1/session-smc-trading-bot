# Unified Dashboard Deployment Guide

## Purpose

Deploy the unified SVOS and trading dashboard behind Nginx and oauth2-proxy while keeping Flask private, preserving `DEMO_ONLY=true`, and leaving `LIVE_TRADING=false` unless an external human authorization process changes it.

## Files

- Frontend source: `New Dashborad/Two system on one Dashboard`
- Built assets: `New Dashborad/dist`
- Flask app: `dashboard/app.py`
- Example Nginx config: `deploy/dashboard/nginx.new-dashboard.conf.example`
- Example oauth2-proxy config: `deploy/dashboard/oauth2-proxy.cfg.example`
- Example environment file: `deploy/dashboard/dashboard.env.example`
- Example systemd units:
  - `deploy/dashboard/dashboard.service.example`
  - `deploy/dashboard/oauth2-proxy.service.example`

## Secrets and identity

- Set `DASHBOARD_PROXY_SECRET` in the dashboard environment file and inject the same value from Nginx with the trusted proxy header.
- Configure oauth2-proxy with the OIDC issuer, client ID, client secret, cookie secret, and redirect URL for the private dashboard hostname.
- In Nginx, strip any incoming `Authorization`, `X-SVOS-Actor`, `X-SVOS-Role`, and proxy identity headers before adding trusted values.
- Map only explicitly allowed users or groups to one of:
  - `research_operator`
  - `incident_operator`
  - `risk_operator`
  - `admin`

## Build and release

1. Install frontend dependencies in `New Dashborad/Two system on one Dashboard`.
2. Build the frontend with `npm run build`.
3. Preserve the current `New Dashborad/dist` as a rollback artifact before replacing it.
4. Verify the Flask virtual environment and dependencies are present.
5. Copy `deploy/dashboard/dashboard.env.example` to a private `dashboard.env` file and fill in deployment values.
6. Install the systemd service files and reload systemd.
7. Install the Nginx and oauth2-proxy configs, then restart those services.
8. Restart only the dashboard-facing services:
   - `dashboard.service`
   - `oauth2-proxy.service`
   - `nginx`

## Health checks

- Confirm the private Flask process responds:
  - `curl http://127.0.0.1:8080/api/session/me`
- Confirm authenticated browser traffic reaches the SPA:
  - `https://<dashboard-host>/new-dashboard/`
- Confirm session identity resolves through oauth2-proxy and Nginx header mapping.
- Confirm a read-only view loads even when live broker data is unavailable.
- Confirm a permitted operator can execute one non-destructive workflow, such as report generation.
- Confirm the dashboard still reports `LIVE_TRADING=false` and `DEMO_ONLY=true` unless the environment was independently changed.

## Rollback

1. Restore the previous `New Dashborad/dist` artifact.
2. Restart `dashboard.service`.
3. Re-check `/new-dashboard/` and `/api/session/me`.
4. If the issue is auth-related, restore the prior Nginx and oauth2-proxy configs and restart those services.

## Notes

- The dashboard does not create any path to enable live trading.
- The production activation control records staged-disabled runtime state only.
- If broker connectivity is degraded, the UI intentionally keeps the last good snapshot and disables mutations after the stale timeout.
