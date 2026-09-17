# СХЕМА Business Platform

Commercial Intelligence & Execution OS.

## v1.4

The repository starts from a modular-monolith foundation:

- domain rules are isolated from infrastructure and adapters;
- PostgreSQL is the transactional authority;
- critical command paths are policy-gated and idempotent;
- evidence and audit are first-class concerns;
- external systems integrate through adapters;
- MAX is a communication adapter, never a domain dependency.

### Development

Open the repository in GitHub Codespaces. The dev container installs the project and development test dependencies.

Run:

```bash
pytest
```

Architecture baseline: `ARCHITECTURE.md`.

Database foundation migration: `db/migrations/0001_foundation.sql`.
