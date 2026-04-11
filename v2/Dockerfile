# syntax=docker/dockerfile:1.7

FROM golang:1.23-alpine AS builder
WORKDIR /src

RUN apk add --no-cache git ca-certificates

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /out/wezu-api-v2 ./cmd/api

FROM gcr.io/distroless/static-debian12
WORKDIR /app
COPY --from=builder /out/wezu-api-v2 /app/wezu-api-v2

EXPOSE 8081
ENTRYPOINT ["/app/wezu-api-v2"]
