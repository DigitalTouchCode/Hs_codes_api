# Changelog

All notable changes to this project will be documented in this file.

## [v1.0] - 2026-06-03

### Added
- HS code fuzzy search via PostgreSQL trigram similarity (`GET /api/v1/hs-codes/?q=`)
- Weighted scoring — description ranked 2× higher than HS code
- Configurable similarity threshold via `HS_CODE_SEARCH_THRESHOLD` env variable
- CSV bulk upload with duplicate detection and blank row skipping
- Health check endpoint (`GET /api/v1/health/`)
- Role-based permission class (`IsAdminOrStaff`) for internal endpoints
- Multi-stage Dockerfile with non-root user
- Docker Compose setup with PostgreSQL 16 and healthcheck
- CI workflow — 40 tests against a live PostgreSQL service container
- CD workflow — auto-deploys to VPS on CI success via SSH
- Black code formatting enforced via pre-commit hook
- Loguru structured logging on all views
- Throttling — 100 req/min (anon), 1000 req/min (authenticated) in production

