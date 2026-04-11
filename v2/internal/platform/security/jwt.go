package security

import (
	"context"
	"crypto/subtle"
	"errors"
	"fmt"
	"strconv"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"wezu/v2/internal/config"
	"wezu/v2/internal/shared/types"
)

type TokenPair struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	ExpiresInSec int64  `json:"expires_in_sec"`
}

type Claims struct {
	UserID    int64    `json:"uid"`
	RoleID    int64    `json:"rid"`
	Superuser bool     `json:"su"`
	Perms     []string `json:"perms,omitempty"`
	TokenUse  string   `json:"use"`
	jwt.RegisteredClaims
}

type JWTManager struct {
	cfg   config.Config
	redis *redis.Client
}

func NewJWTManager(cfg config.Config, redisClient *redis.Client) *JWTManager {
	return &JWTManager{cfg: cfg, redis: redisClient}
}

func (m *JWTManager) Issue(principal types.Principal) (TokenPair, error) {
	now := time.Now().UTC()
	accessExp := now.Add(m.cfg.AccessTokenTTL)
	refreshExp := now.Add(m.cfg.RefreshTokenTTL)

	perms := make([]string, 0, len(principal.Permissions))
	for p := range principal.Permissions {
		perms = append(perms, p)
	}

	accessClaims := Claims{
		UserID:    principal.UserID,
		RoleID:    principal.RoleID,
		Superuser: principal.Superuser,
		Perms:     perms,
		TokenUse:  "access",
		RegisteredClaims: jwt.RegisteredClaims{
			Issuer:    m.cfg.JWTIssuer,
			Audience:  jwt.ClaimStrings{m.cfg.JWTAudience},
			IssuedAt:  jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(accessExp),
			ID:        uuid.NewString(),
			Subject:   strconv.FormatInt(principal.UserID, 10),
		},
	}

	refreshClaims := Claims{
		UserID:    principal.UserID,
		RoleID:    principal.RoleID,
		Superuser: principal.Superuser,
		TokenUse:  "refresh",
		RegisteredClaims: jwt.RegisteredClaims{
			Issuer:    m.cfg.JWTIssuer,
			Audience:  jwt.ClaimStrings{m.cfg.JWTAudience},
			IssuedAt:  jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(refreshExp),
			ID:        uuid.NewString(),
			Subject:   strconv.FormatInt(principal.UserID, 10),
		},
	}

	accessToken, err := jwt.NewWithClaims(jwt.SigningMethodHS256, accessClaims).SignedString([]byte(m.cfg.JWTAccessSecret))
	if err != nil {
		return TokenPair{}, fmt.Errorf("sign access token: %w", err)
	}
	refreshToken, err := jwt.NewWithClaims(jwt.SigningMethodHS256, refreshClaims).SignedString([]byte(m.cfg.JWTRefreshSecret))
	if err != nil {
		return TokenPair{}, fmt.Errorf("sign refresh token: %w", err)
	}

	return TokenPair{AccessToken: accessToken, RefreshToken: refreshToken, ExpiresInSec: int64(m.cfg.AccessTokenTTL.Seconds())}, nil
}

func (m *JWTManager) ParseAccess(token string) (Claims, error) {
	return m.parse(token, []byte(m.cfg.JWTAccessSecret), "access")
}

func (m *JWTManager) ParseRefresh(token string) (Claims, error) {
	return m.parse(token, []byte(m.cfg.JWTRefreshSecret), "refresh")
}

func (m *JWTManager) parse(token string, secret []byte, expectedUse string) (Claims, error) {
	parsed, err := jwt.ParseWithClaims(token, &Claims{}, func(t *jwt.Token) (any, error) {
		if t.Method.Alg() != jwt.SigningMethodHS256.Alg() {
			return nil, fmt.Errorf("unexpected signing method: %s", t.Method.Alg())
		}
		return secret, nil
	}, jwt.WithIssuer(m.cfg.JWTIssuer), jwt.WithAudience(m.cfg.JWTAudience), jwt.WithValidMethods([]string{jwt.SigningMethodHS256.Alg()}))
	if err != nil {
		return Claims{}, fmt.Errorf("parse token: %w", err)
	}
	claims, ok := parsed.Claims.(*Claims)
	if !ok || !parsed.Valid {
		return Claims{}, errors.New("invalid claims")
	}
	if subtle.ConstantTimeCompare([]byte(claims.TokenUse), []byte(expectedUse)) != 1 {
		return Claims{}, errors.New("invalid token type")
	}
	return *claims, nil
}

func (m *JWTManager) Revoke(ctx context.Context, jti string, exp time.Time) error {
	if m.redis == nil || jti == "" {
		return nil
	}
	ttl := time.Until(exp)
	if ttl <= 0 {
		ttl = time.Minute
	}
	return m.redis.Set(ctx, "session:revoked:"+jti, "1", ttl).Err()
}

func (m *JWTManager) IsRevoked(ctx context.Context, jti string) (bool, error) {
	if m.redis == nil || jti == "" {
		return false, nil
	}
	count, err := m.redis.Exists(ctx, "session:revoked:"+jti).Result()
	if err != nil {
		return false, err
	}
	return count > 0, nil
}
