# ADR-001: SQLite Over PostgreSQL

**Status**: Accepted
**Date**: 2026-03-03
**Decision Makers**: Architecture Team

## Context

The Embedinator needs a relational database for metadata storage: collections, documents, ingestion jobs, parent chunks, query traces, settings, and provider configuration. The system is designed as a self-hosted single-user application.

Two candidates were evaluated:
- **PostgreSQL**: Full-featured RDBMS, industry standard for production web applications
- **SQLite**: Embedded single-file database, zero-config

## Decision

Use **SQLite with WAL (Write-Ahead Logging) journal mode** as the sole relational database.

## Rationale

1. **Zero-config deployment**: SQLite requires no daemon, no credentials file, no init script, and no port management. PostgreSQL requires all of these.
2. **WAL mode concurrency**: Allows unlimited concurrent readers with a single serialized writer — appropriate for a system where reads (queries, document listing) far outnumber writes (ingestion, settings updates).
3. **Single-file simplicity**: Backup is `cp embedinator.db backup.db`. Portability is copying one file. Reset is deleting one file.
4. **No additional Docker service**: Adding PostgreSQL would mean a 5th container with volume management, health checks, and migration tooling.
5. **Sufficient write throughput**: Ingestion happens sequentially per job; queries are read-only. SQLite's write serialization is not a limiting factor.

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| PostgreSQL | Requires separate service, credentials management, migration tooling — complexity with no benefit at single-user scale |
| DuckDB | Optimized for analytics, not OLTP; less ecosystem maturity for async Python |
| JSON files | No indexing, no foreign keys, no atomic writes, no concurrent access |

## Consequences

### Positive
- Single `docker compose up` starts everything — no database initialization step
- Backup and restore are trivial file operations
- No connection pooling complexity
- In-memory SQLite (`:memory:`) enables fast unit tests

### Negative
- Write throughput bounded by disk I/O on WAL file (acceptable for this workload)
- No built-in replication or horizontal scaling (not needed for single-user)
- If the project ever needs multi-user/multi-tenant, migration to PostgreSQL would be required

### Risks
- Concurrent ingestion jobs could contend on writer lock — mitigated by serializing ingestion jobs in the pipeline
