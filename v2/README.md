# WEZU API v2 (Go Rewrite)

High-performance modular monolith targeting sub-100ms P95 latency with PostgreSQL + Redis + read models.

## Scope Implemented
- API gateway style entry with centralized middleware.
- Domain modules: `auth`, `users`, `stations`, `swaps`, `inventory`, `tickets`, `analytics`, `admin`.
- `pgx` query layer with explicit projections and keyset pagination.
- Redis SWR cache + single-flight dedupe.
- Background queue for async completion/refresh jobs.
- Event-driven cache invalidation.
- Metrics + tracing bootstrap.
- k6 performance gate script with `P95 < 100ms`, `P99 < 250ms` thresholds.

## Run Locally
```bash
cd v2
cp .env.example .env
export $(grep -v '^#' .env | xargs)
make tidy
make run
```

Server starts on `:8081` by default.

## Tests
```bash
cd v2
make test
```

## Load Test
```bash
cd v2
BASE_URL=http://127.0.0.1:8081 ACCESS_TOKEN=<token> make perf
```

## SQL Tooling
- `sqlc` configuration is available in `sqlc.yaml`.
- SQL definitions and index/read-model scripts live under `sql/`.

To generate typed query code:
```bash
cd v2
sqlc generate
```

## Notes
- Current local toolchain is Go 1.23; module uses `go 1.23` for compatibility.
- Production target can be raised to Go 1.24 once your build agents are upgraded.
