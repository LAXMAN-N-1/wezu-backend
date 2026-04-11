package middleware

import (
	"net/http"

	"wezu/v2/internal/shared/envelope"
)

func RequirePermission(permission string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			claims, ok := GetClaims(r.Context())
			if !ok {
				envelope.Fail(w, http.StatusUnauthorized, BuildMeta(r.Context()), "unauthorized", "missing authentication context")
				return
			}
			principal := PrincipalFromClaims(claims)
			if !principal.HasPermission(permission) {
				envelope.Fail(w, http.StatusForbidden, BuildMeta(r.Context()), "forbidden", "insufficient permissions")
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}
