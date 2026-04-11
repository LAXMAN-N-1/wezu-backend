package middleware

import (
	"net/http"
	"strings"

	"wezu/v2/internal/platform/security"
	"wezu/v2/internal/shared/envelope"
)

func RequireAuth(jwtManager *security.JWTManager) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			authHeader := r.Header.Get("Authorization")
			if authHeader == "" {
				envelope.Fail(w, http.StatusUnauthorized, BuildMeta(r.Context()), "unauthorized", "missing authorization header")
				return
			}
			parts := strings.SplitN(authHeader, " ", 2)
			if len(parts) != 2 || !strings.EqualFold(parts[0], "Bearer") {
				envelope.Fail(w, http.StatusUnauthorized, BuildMeta(r.Context()), "unauthorized", "invalid authorization header")
				return
			}

			claims, err := jwtManager.ParseAccess(parts[1])
			if err != nil {
				envelope.Fail(w, http.StatusUnauthorized, BuildMeta(r.Context()), "unauthorized", "invalid access token")
				return
			}
			revoked, err := jwtManager.IsRevoked(r.Context(), claims.ID)
			if err != nil {
				envelope.Fail(w, http.StatusUnauthorized, BuildMeta(r.Context()), "unauthorized", "session validation failed")
				return
			}
			if revoked {
				envelope.Fail(w, http.StatusUnauthorized, BuildMeta(r.Context()), "unauthorized", "session revoked")
				return
			}

			r = r.WithContext(SetClaims(r.Context(), claims))
			next.ServeHTTP(w, r)
		})
	}
}
