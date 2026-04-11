# API Performance Optimization — Agent Guidelines

> **Scope**: These guidelines are for use by an AI coding agent operating on a backend that already meets industry-standard response times. The goal is to push beyond baseline — identifying micro-optimizations, architectural improvements, and intelligent patterns that yield measurable gains without introducing regressions.

---

## 0. Agent Operating Rules

Before making any change, the agent **must**:

1. **Profile first, optimize second.** Never assume where the bottleneck is. Use actual measurements.
2. **One change at a time.** Isolate changes so their impact can be confirmed or rolled back cleanly.
3. **Do no harm.** If an optimization introduces complexity that risks correctness, flag it and ask before proceeding.
4. **Document every change** inline and in the changelog section at the end of this file.
5. **Validate before and after** using the benchmarking commands listed in Section 8.

---

## 1. Triage Protocol — Where to Look First

When tasked with "reduce response time", the agent must follow this triage order. Do not skip steps.

```
1. Identify the slowest endpoints       → Section 2
2. Audit database query patterns        → Section 3
3. Inspect caching layers               → Section 4
4. Review async / concurrency model     → Section 5
5. Check serialization / payload size   → Section 6
6. Examine network and connection pools → Section 7
```

Use structured logging or APM traces (e.g. OpenTelemetry, Datadog, CloudWatch) to produce a **ranked list of endpoints by P95 latency** before touching any code.

---

## 2. Endpoint-Level Analysis

### 2.1 Time-to-First-Byte (TTFB) Breakdown

For each slow endpoint, decompose latency into buckets:

| Bucket | What to measure |
|---|---|
| **Auth / middleware** | JWT decode, permission checks, rate limiting |
| **I/O wait** | DB queries, external API calls, file reads |
| **Compute** | Business logic, transformations, sorting |
| **Serialization** | ORM → dict → JSON |
| **Network** | Response size, TCP overhead |

### 2.2 Hot Path Rules

- Every hot-path endpoint (high traffic or SLA-critical) should complete **core logic in under 20ms** of CPU time.
- If a route does more than one "class" of work (e.g. read + compute + write + notify), consider splitting concerns.

### 2.3 Background Offload Pattern

If a request triggers work that doesn't need to finish before the response:

```python
# ❌ Blocking — makes caller wait for the notification
def create_order(data):
    order = db.create(data)
    send_confirmation_email(order)   # blocks here
    return order

# ✅ Non-blocking — push to task queue, respond immediately
def create_order(data):
    order = db.create(data)
    task_queue.enqueue(send_confirmation_email, order.id)
    return order
```

**Recommended queues**: Celery + Redis, ARQ, BullMQ (Node), or cloud-native (SQS, Cloud Tasks).

---

## 3. Database Optimization

Database I/O is the most common bottleneck in already-fast backends. Apply these checks in order.

### 3.1 Query Audit Checklist

For every DB call in a slow endpoint, verify:

- [ ] Is there a **covering index** for this query's WHERE + ORDER BY columns?
- [ ] Is the query fetching **only the columns it uses** (no `SELECT *`)?
- [ ] Are there **N+1 query patterns**? (Loop that fires per row)
- [ ] Is `EXPLAIN ANALYZE` showing sequential scans on large tables?
- [ ] Are there missing **foreign key indexes**?

### 3.2 Fixing N+1 Queries

```python
# ❌ N+1 — fires one query per order
orders = db.query(Order).all()
for order in orders:
    print(order.user.name)   # separate query each time

# ✅ Eager load with JOIN
orders = db.query(Order).options(joinedload(Order.user)).all()
```

### 3.3 Indexing Strategy

```sql
-- Composite index for common filter + sort patterns
CREATE INDEX idx_orders_user_created
ON orders (user_id, created_at DESC)
WHERE status != 'deleted';   -- partial index reduces index size

-- Index for full-text search instead of ILIKE
CREATE INDEX idx_products_name_fts
ON products USING gin(to_tsvector('english', name));
```

### 3.4 Read Replicas

For read-heavy endpoints, route queries to a **read replica**:

```python
# FastAPI / SQLAlchemy example
def get_db_read():
    yield SessionLocal(bind=read_replica_engine)

@router.get("/products")
def list_products(db=Depends(get_db_read)):   # read replica
    ...
```

### 3.5 Batch Operations

```python
# ❌ One insert per iteration
for item in items:
    db.add(Item(**item))
    db.commit()

# ✅ Bulk insert in one round-trip
db.bulk_insert_mappings(Item, items)
db.commit()
```

### 3.6 Query Result Limits

Always paginate or cap unbounded queries:

```python
# Cursor-based pagination — more efficient than OFFSET for large datasets
def get_orders(cursor: str | None, limit: int = 50):
    query = db.query(Order).order_by(Order.id)
    if cursor:
        query = query.filter(Order.id > decode_cursor(cursor))
    return query.limit(limit).all()
```

---

## 4. Caching Strategy

### 4.1 Cache Decision Tree

```
Is the data user-specific?
├── No  → Shared cache (Redis, Memcached) with appropriate TTL
└── Yes → Per-user cache key OR skip caching

Does the data change frequently?
├── No  → Long TTL (minutes to hours)
└── Yes → Short TTL + cache invalidation on write

Is recomputing it expensive?
├── Yes → Cache aggressively
└── No  → Cache only if traffic is very high
```

### 4.2 Response-Level Caching

```python
# FastAPI + Redis example — cache entire response
@router.get("/catalog")
@cache(expire=300)   # 5 minutes
async def get_catalog():
    return db.query(Product).all()
```

### 4.3 Fragment / Computed-Value Caching

Cache expensive sub-computations, not just full responses:

```python
async def get_user_stats(user_id: str):
    cache_key = f"user_stats:{user_id}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    stats = compute_stats(user_id)   # expensive
    await redis.setex(cache_key, 120, json.dumps(stats))
    return stats
```

### 4.4 Cache Invalidation Rules

- **Write-through**: Update cache on every write. Keeps cache consistent but adds write latency.
- **Cache-aside (lazy)**: Populate on first miss. Simplest; acceptable for non-critical freshness.
- **Event-driven invalidation**: Publish a `cache.invalidate` event on data change, consumed by cache layer.

Never cache:
- Auth tokens or permission-sensitive data without scoping the key to the user.
- Data that must be real-time (inventory counts during checkout, live prices).

---

## 5. Async and Concurrency

### 5.1 Async I/O — Do Not Block the Event Loop

In async frameworks (FastAPI, Express, Go), blocking the event loop stalls all concurrent requests.

```python
# ❌ Synchronous DB driver in async route — blocks event loop
@router.get("/data")
async def get_data():
    return db.query(Thing).all()   # sync driver blocks!

# ✅ Use async driver (asyncpg, databases, Tortoise ORM)
@router.get("/data")
async def get_data():
    return await db.fetch_all(query)
```

### 5.2 Parallel Fan-Out

When a route needs data from multiple independent sources, fetch them in parallel:

```python
# ❌ Sequential — total time = A + B + C
user    = await get_user(user_id)
orders  = await get_orders(user_id)
balance = await get_balance(user_id)

# ✅ Parallel — total time = max(A, B, C)
user, orders, balance = await asyncio.gather(
    get_user(user_id),
    get_orders(user_id),
    get_balance(user_id),
)
```

### 5.3 Connection Pool Sizing

Too few connections = queuing. Too many = DB resource exhaustion.

```python
# Recommended starting formula:
# pool_size = (num_cpu_cores * 2) + effective_spindle_count

engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_pre_ping=True,   # validates connections before use
)
```

---

## 6. Serialization and Payload Optimization

### 6.1 Reduce Payload Size

Large payloads increase time on the wire and serialization cost.

- Use **field selection / sparse fieldsets**: Let callers request only fields they need.
- **Paginate** all list endpoints — never return unbounded arrays.
- Use **Pydantic `response_model`** to exclude unneeded fields at the schema level, not in code.

```python
class OrderSummary(BaseModel):   # lightweight schema for list endpoints
    id: str
    status: str
    total: float

class OrderDetail(OrderSummary):   # full schema for single-item endpoints
    items: list[OrderItem]
    shipping_address: Address
    ...
```

### 6.2 Faster Serialization

```python
# orjson is 3-10x faster than stdlib json for large payloads
import orjson
from fastapi.responses import ORJSONResponse

@router.get("/large-dataset", response_class=ORJSONResponse)
async def large_dataset():
    return data
```

### 6.3 HTTP Compression

Enable gzip/brotli for responses over ~1KB:

```python
# FastAPI
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

---

## 7. Network and Infrastructure

### 7.1 HTTP Keep-Alive and Connection Reuse

Ensure all outbound HTTP clients (to external APIs, microservices) reuse connections:

```python
# ❌ New connection per request
async def call_external():
    async with httpx.AsyncClient() as client:   # opens + closes each time
        return await client.get(URL)

# ✅ Shared client with connection pooling
_client = httpx.AsyncClient(limits=httpx.Limits(max_connections=50))

async def call_external():
    return await _client.get(URL)
```

### 7.2 DNS Caching

For services making many outbound calls, enable DNS caching to avoid repeated lookups:

```python
# Use aiodns with a TTL-respecting cache, or configure at the OS level
# In Kubernetes: configure ndots and search domains in pod spec to reduce lookup chains
```

### 7.3 CDN and Edge Caching

For endpoints serving static or semi-static content:

- Set `Cache-Control: public, max-age=N, stale-while-revalidate=M` headers.
- Route cacheable traffic through CDN (CloudFront, Fastly, Cloudflare).
- Use **stale-while-revalidate** to serve cached data instantly while refreshing in background.

### 7.4 Response Streaming

For large data transfers, stream the response instead of buffering the entire payload:

```python
from fastapi.responses import StreamingResponse

@router.get("/export")
async def export_data():
    async def generate():
        async for row in db.stream(query):
            yield orjson.dumps(row) + b"\n"
    return StreamingResponse(generate(), media_type="application/x-ndjson")
```

---

## 8. Benchmarking and Validation Commands

The agent must run before/after benchmarks for every optimization. Use these commands:

```bash
# HTTP load test — measure P50/P95/P99 latency and throughput
wrk -t4 -c100 -d30s --latency https://api.example.com/endpoint

# Alternative with detailed percentiles
hey -n 10000 -c 100 https://api.example.com/endpoint

# Database slow query log (PostgreSQL)
# Set in postgres.conf or per-session:
SET log_min_duration_statement = 100;   # log queries > 100ms

# Explain a query
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT ...;

# Python profiling (cProfile or py-spy for production-safe profiling)
py-spy record -o profile.svg --pid <PID>

# FastAPI route timing middleware (add temporarily during investigation)
import time
@app.middleware("http")
async def add_timing(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Response-Time"] = f"{(time.perf_counter()-start)*1000:.2f}ms"
    return response
```

---

## 9. Anti-Patterns — What NOT to Do

The agent must avoid these common but counterproductive "optimizations":

| Anti-Pattern | Why It's Wrong | Better Alternative |
|---|---|---|
| Caching everything aggressively | Stale data causes correctness bugs | Cache only safe, bounded data with TTLs |
| Increasing pool size indefinitely | DB CPU/memory exhaustion | Tune based on DB server capacity |
| Removing all logging on hot paths | Loses observability when issues arise | Use sampling or async log sinks |
| Premature denormalization | Schema complexity, write anomalies | Add indexes first; denormalize only if proven necessary |
| Over-parallelizing everything | Deadlocks, connection starvation | Fan-out only truly independent calls |
| Skipping validation for speed | Security and data integrity risks | Use lazy/async validation where possible |
| Micro-optimizing cold paths | Wastes time, no user impact | Focus on P95 hot paths only |

---

## 10. Performance Budget — Targets by Endpoint Category

Use these as acceptance criteria after any optimization work:

| Endpoint Type | P50 Target | P95 Target | Notes |
|---|---|---|---|
| Simple read (cached) | < 10ms | < 30ms | Cache hit path |
| Simple read (DB) | < 30ms | < 80ms | Single indexed query |
| Authenticated read | < 40ms | < 100ms | Includes JWT + permission check |
| List / paginated | < 50ms | < 120ms | With cursor pagination |
| Write (create/update) | < 60ms | < 150ms | Sync commit, async side-effects |
| Aggregation / report | < 100ms | < 300ms | Pre-computed or materialized view |
| External API fan-out | < 150ms | < 400ms | Parallel calls, circuit breaker |

If current baselines already meet these targets, aim for **20–30% improvement** over existing P95.

---

## 11. Changelog

> The agent must append an entry here for every optimization applied.

```
DATE        | ENDPOINT / COMPONENT       | CHANGE MADE                          | BEFORE (P95) | AFTER (P95)
------------|----------------------------|--------------------------------------|--------------|-------------
YYYY-MM-DD  | GET /example               | Added Redis cache, TTL=120s          | 210ms        | 18ms
2026-04-08  | GLOBAL                     | Injected X-Response-Time Profiling   | -            | -
2026-04-08  | POST /admin/batteries/bulk | Rewrote N+1 loop to Batch UPDATE     | ~1s (100+)   | Expected <50ms
2026-04-08  | GET /admin/stations        | Fixed COUNT() doubling sub-query join| >250ms       | Expected <80ms
2026-04-08  | GLOBAL LISTINGS            | Implemented pg_trgm GIN Indexes      | >500ms       | Expected <50ms
2026-04-09  | LISTINGS /admin/users      | Built `fields=` query Sparse slicing | >80ms        | Expected <10ms
2026-04-09  | LISTINGS /admin/stations   | Built `fields=` query Sparse slicing | >80ms        | Expected <10ms
2026-04-09  | POST /admin/batteries/bulk | BackgroundTasks Audit offload        | ~300ms       | Expected <20ms
2026-04-09  | DASHBOARDS * /stats        | SWR Caching Middleware               | >800ms Miss  | 0ms wait on TTFB
2026-04-09  | LISTINGS * /admin/         | Replaced default backend JSON with ORJSONResponse | >80ms serialize| Expected <10ms
2026-04-09  | LISTINGS * /admin/         | Added Base total-count TTFB cached short-circuits | >150ms scan    | 0ms TTFB
2026-04-09  | LISTINGS /admin/users      | Wrapped RBAC DB mapping iteration into cached_call| ~25ms          | 0ms TTFB
2026-04-09  | SCHEMA   Admin DB          | B-Tree Indexing applied to 8 filtering columns    | >120ms SeqScan | Expected <5ms
2026-04-09  | LISTINGS * /admin/         | Migrated Offset pagination to Keyset Cursors      | >800ms offset  | O(1) <2ms Time
2026-04-09  | CORE API Pipeline          | Bridged Admin Endpoints to asyncpg / AsyncSession | ~500 Thread Cap| >10,000 req/s
```

---

## 12. Escalation Criteria

The agent must **stop and ask for human review** when:

- A proposed change alters database schema (index additions are safe; column changes are not).
- A change affects authentication, authorization, or security middleware.
- Estimated improvement is < 5ms but introduces significant complexity.
- The slowness root cause appears to be in infrastructure (VPS resource limits, network topology) rather than application code.
- Any change would require a deployment window or service restart in production.

---

*Guidelines version: 1.0 — optimized for AI agent consumption. Update Section 11 after each run.*
