package auth

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/jackc/pgx/v5"
	"wezu/v2/internal/platform/middleware"
	"wezu/v2/internal/platform/security"
	"wezu/v2/internal/shared/container"
	"wezu/v2/internal/shared/envelope"
	"wezu/v2/internal/shared/types"
)

type Repository struct {
	deps container.Dependencies
}

type Service struct {
	repo Repository
	jwt  *security.JWTManager
}

type Handler struct {
	svc Service
}

type userRecord struct {
	ID             int64
	Email          sql.NullString
	Phone          sql.NullString
	FullName       sql.NullString
	HashedPassword sql.NullString
	RoleID         sql.NullInt64
	IsSuperuser    bool
	Status         string
}

type loginRequest struct {
	Identifier string `json:"identifier"`
	Password   string `json:"password"`
}

type refreshRequest struct {
	RefreshToken string `json:"refresh_token"`
}

type logoutRequest struct {
	AccessToken string `json:"access_token"`
}

type loginResponse struct {
	UserID    int64              `json:"user_id"`
	FullName  string             `json:"full_name"`
	RoleID    int64              `json:"role_id"`
	Superuser bool               `json:"superuser"`
	TokenPair security.TokenPair `json:"tokens"`
}

func NewHandler(deps container.Dependencies) Handler {
	repo := Repository{deps: deps}
	return Handler{svc: Service{repo: repo, jwt: deps.JWT}}
}

func RegisterRoutes(r chi.Router, deps container.Dependencies) {
	h := NewHandler(deps)
	r.Route("/auth", func(ar chi.Router) {
		ar.Post("/login", h.login)
		ar.Post("/refresh", h.refresh)
		ar.With(middleware.RequireAuth(deps.JWT)).Post("/logout", h.logout)
	})
}

func (h Handler) login(w http.ResponseWriter, r *http.Request) {
	var req loginRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		envelope.Fail(w, http.StatusBadRequest, middleware.BuildMeta(r.Context()), "bad_request", "invalid json")
		return
	}
	res, err := h.svc.Login(r.Context(), req)
	if err != nil {
		status := http.StatusUnauthorized
		code := "unauthorized"
		if errors.Is(err, errBadRequest) {
			status = http.StatusBadRequest
			code = "bad_request"
		}
		envelope.Fail(w, status, middleware.BuildMeta(r.Context()), code, err.Error())
		return
	}
	envelope.OK(w, middleware.BuildMeta(r.Context()), res)
}

func (h Handler) refresh(w http.ResponseWriter, r *http.Request) {
	var req refreshRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		envelope.Fail(w, http.StatusBadRequest, middleware.BuildMeta(r.Context()), "bad_request", "invalid json")
		return
	}
	pair, err := h.svc.Refresh(r.Context(), req.RefreshToken)
	if err != nil {
		envelope.Fail(w, http.StatusUnauthorized, middleware.BuildMeta(r.Context()), "unauthorized", err.Error())
		return
	}
	envelope.OK(w, middleware.BuildMeta(r.Context()), map[string]any{"tokens": pair})
}

func (h Handler) logout(w http.ResponseWriter, r *http.Request) {
	claims, ok := middleware.GetClaims(r.Context())
	if !ok {
		envelope.Fail(w, http.StatusUnauthorized, middleware.BuildMeta(r.Context()), "unauthorized", "missing claims")
		return
	}
	if err := h.svc.Logout(r.Context(), claims.ID, claims.ExpiresAt.Time); err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "logout_failed", "failed to revoke session")
		return
	}
	envelope.OK(w, middleware.BuildMeta(r.Context()), map[string]any{"message": "logged out"})
}

var errBadRequest = errors.New("bad request")

func (s Service) Login(ctx context.Context, req loginRequest) (loginResponse, error) {
	identifier := strings.TrimSpace(req.Identifier)
	if identifier == "" || req.Password == "" {
		return loginResponse{}, fmt.Errorf("%w: identifier and password are required", errBadRequest)
	}

	u, perms, err := s.repo.FindUserForAuth(ctx, identifier)
	if err != nil {
		return loginResponse{}, err
	}
	if !security.VerifyPassword(u.HashedPassword.String, req.Password) {
		return loginResponse{}, errors.New("invalid credentials")
	}
	if strings.EqualFold(u.Status, "suspended") || strings.EqualFold(u.Status, "deleted") {
		return loginResponse{}, errors.New("account not active")
	}

	principal := types.Principal{
		UserID:      u.ID,
		RoleID:      u.RoleID.Int64,
		Permissions: perms,
		Superuser:   u.IsSuperuser,
	}
	pair, err := s.jwt.Issue(principal)
	if err != nil {
		return loginResponse{}, fmt.Errorf("issue token: %w", err)
	}

	return loginResponse{
		UserID:    u.ID,
		FullName:  u.FullName.String,
		RoleID:    u.RoleID.Int64,
		Superuser: u.IsSuperuser,
		TokenPair: pair,
	}, nil
}

func (s Service) Refresh(ctx context.Context, refreshToken string) (security.TokenPair, error) {
	claims, err := s.jwt.ParseRefresh(strings.TrimSpace(refreshToken))
	if err != nil {
		return security.TokenPair{}, errors.New("invalid refresh token")
	}
	revoked, err := s.jwt.IsRevoked(ctx, claims.ID)
	if err != nil {
		return security.TokenPair{}, errors.New("refresh validation failed")
	}
	if revoked {
		return security.TokenPair{}, errors.New("refresh token revoked")
	}

	perms, err := s.repo.GetPermissionsByRole(ctx, claims.RoleID)
	if err != nil {
		return security.TokenPair{}, err
	}
	principal := types.Principal{UserID: claims.UserID, RoleID: claims.RoleID, Superuser: claims.Superuser, Permissions: perms}
	pair, err := s.jwt.Issue(principal)
	if err != nil {
		return security.TokenPair{}, err
	}
	_ = s.jwt.Revoke(ctx, claims.ID, claims.ExpiresAt.Time)
	return pair, nil
}

func (s Service) Logout(ctx context.Context, tokenID string, exp time.Time) error {
	return s.jwt.Revoke(ctx, tokenID, exp)
}

func (r Repository) FindUserForAuth(ctx context.Context, identifier string) (userRecord, map[string]struct{}, error) {
	const q = `
SELECT id, email, phone_number, full_name, hashed_password, role_id, is_superuser, status
FROM users
WHERE is_deleted = false AND (email = $1 OR phone_number = $1)
LIMIT 1`
	var u userRecord
	err := r.deps.DB.QueryRow(ctx, q, identifier).Scan(&u.ID, &u.Email, &u.Phone, &u.FullName, &u.HashedPassword, &u.RoleID, &u.IsSuperuser, &u.Status)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return userRecord{}, nil, errors.New("invalid credentials")
		}
		return userRecord{}, nil, fmt.Errorf("query user: %w", err)
	}
	perms, err := r.GetPermissionsByRole(ctx, u.RoleID.Int64)
	if err != nil {
		return userRecord{}, nil, err
	}
	return u, perms, nil
}

func (r Repository) GetPermissionsByRole(ctx context.Context, roleID int64) (map[string]struct{}, error) {
	if roleID == 0 {
		return map[string]struct{}{}, nil
	}
	const q = `
SELECT p.slug
FROM permissions p
JOIN role_permissions rp ON rp.permission_id = p.id
WHERE rp.role_id = $1`
	rows, err := r.deps.DB.Query(ctx, q, roleID)
	if err != nil {
		return nil, fmt.Errorf("query permissions: %w", err)
	}
	defer rows.Close()
	perms := map[string]struct{}{}
	for rows.Next() {
		var slug string
		if err := rows.Scan(&slug); err != nil {
			return nil, fmt.Errorf("scan permission: %w", err)
		}
		perms[slug] = struct{}{}
	}
	if rows.Err() != nil {
		return nil, rows.Err()
	}
	return perms, nil
}
