# New Dashboard

This package is the React/Vite frontend for the project dashboard migration.

It is intentionally **frontend-only**:

- the authoritative backend remains the Flask dashboard in `dashboard/app.py`
- project data comes from `/api/new-dashboard/*` and existing `/api/platform/*`
- the old Express sandbox and Gemini flows are not part of the baseline runtime

## Development

Prerequisites:

- Node.js 20+
- the Flask dashboard backend running locally, typically on `http://127.0.0.1:8080`

Commands:

```bash
npm install
npm run dev
```

Optional backend override:

```bash
VITE_BACKEND_URL=http://127.0.0.1:8080 npm run dev
```

## Build

```bash
npm run build
```

The build output is written to `New Dashborad/dist/` and can be served by the
existing Flask dashboard at `/new-dashboard/`.
