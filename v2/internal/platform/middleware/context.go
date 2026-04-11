package middleware

import (
	"context"
	"time"

	"wezu/v2/internal/platform/security"
	"wezu/v2/internal/shared/envelope"
	"wezu/v2/internal/shared/types"
)

type key string

const (
	traceIDKey   key = "trace_id"
	startedAtKey key = "started_at"
	claimsKey    key = "claims"
)

func SetTraceID(ctx context.Context, traceID string) context.Context {
	return context.WithValue(ctx, traceIDKey, traceID)
}

func GetTraceID(ctx context.Context) string {
	v, ok := ctx.Value(traceIDKey).(string)
	if !ok {
		return ""
	}
	return v
}

func SetStartedAt(ctx context.Context, startedAt time.Time) context.Context {
	return context.WithValue(ctx, startedAtKey, startedAt)
}

func GetStartedAt(ctx context.Context) time.Time {
	v, ok := ctx.Value(startedAtKey).(time.Time)
	if !ok {
		return time.Now().UTC()
	}
	return v
}

func SetClaims(ctx context.Context, claims security.Claims) context.Context {
	return context.WithValue(ctx, claimsKey, claims)
}

func GetClaims(ctx context.Context) (security.Claims, bool) {
	claims, ok := ctx.Value(claimsKey).(security.Claims)
	return claims, ok
}

func PrincipalFromClaims(claims security.Claims) types.Principal {
	permissions := make(map[string]struct{}, len(claims.Perms))
	for _, p := range claims.Perms {
		permissions[p] = struct{}{}
	}
	return types.Principal{
		UserID:      claims.UserID,
		RoleID:      claims.RoleID,
		Permissions: permissions,
		Superuser:   claims.Superuser,
	}
}

func BuildMeta(ctx context.Context) envelope.Meta {
	return envelope.Meta{
		TraceID:   GetTraceID(ctx),
		LatencyMS: time.Since(GetStartedAt(ctx)).Milliseconds(),
	}
}
