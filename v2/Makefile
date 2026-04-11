APP_NAME=wezu-api-v2

.PHONY: run test fmt vet tidy perf

run:
	go run ./cmd/api

test:
	go test ./...

fmt:
	gofmt -w ./cmd ./internal

vet:
	go vet ./...

tidy:
	go mod tidy

perf:
	k6 run perf/k6/smoke.js
