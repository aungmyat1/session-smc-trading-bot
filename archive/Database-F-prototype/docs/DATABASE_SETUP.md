# Database Setup Guide

## Quick Start (Local)

```bash
docker compose up -d
```

Adminer UI: http://localhost:8080

## Environment Variables

```bash
export POSTGRES_PASSWORD=your_secure_password
export DATABASE_URL=postgresql://trading_user:password@localhost:5432/trading_research
```

## Initialize Schema

Schema is automatically applied via `scripts/init.sql` when the container starts.