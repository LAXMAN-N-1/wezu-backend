# WEZU v2 Rewrite Runbook

## Objective
Deploy the Go-based `v2` backend with a big-bang cutover while meeting:
- `P95 < 100ms`
- `P99 < 250ms`
- core API error rate `<0.5%`

## Pre-Cutover Checklist
1. Apply v2 index/read-model SQL scripts from `v2/sql/schema`.
2. Validate API smoke tests and load tests from `v2/perf/k6/smoke.js`.
3. Validate auth token issuance and revocation behavior.
4. Confirm metrics and tracing dashboards are receiving data.
5. Confirm rollback image for Python backend is pinned and ready.

## Cutover Steps
1. Scale up `wezu-backend-v2` to target capacity.
2. Warm cache via synthetic requests for high-traffic endpoints.
3. Switch ingress route to `v2` service.
4. Monitor latency/error SLOs for 30 minutes.
5. Freeze schema changes during stabilization window.

## Rollback Criteria
- P95 > 150ms for 5+ minutes.
- Error rate > 1% sustained for 3+ minutes.
- Authentication failures > 2x baseline.

## Rollback Steps
1. Switch ingress back to stable Python backend service.
2. Pause v2 deployment and collect logs/traces.
3. Invalidate v2 cache keys and disable refresh workers.
4. Open incident report with failed endpoints and query traces.
