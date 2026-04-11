package pagination

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"strconv"
	"time"
)

type Cursor struct {
	CreatedAt time.Time `json:"created_at"`
	ID        int64     `json:"id"`
}

func Encode(c Cursor) (string, error) {
	b, err := json.Marshal(c)
	if err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(b), nil
}

func Decode(raw string) (Cursor, error) {
	b, err := base64.RawURLEncoding.DecodeString(raw)
	if err != nil {
		return Cursor{}, fmt.Errorf("decode cursor: %w", err)
	}
	var c Cursor
	if err := json.Unmarshal(b, &c); err != nil {
		return Cursor{}, fmt.Errorf("unmarshal cursor: %w", err)
	}
	if c.ID <= 0 {
		return Cursor{}, fmt.Errorf("invalid cursor id")
	}
	if c.CreatedAt.IsZero() {
		return Cursor{}, fmt.Errorf("invalid cursor time")
	}
	return c, nil
}

func ParseLimit(raw string, def, max int) int {
	if raw == "" {
		return def
	}
	n, err := strconv.Atoi(raw)
	if err != nil || n <= 0 {
		return def
	}
	if n > max {
		return max
	}
	return n
}
