package pagination

import (
	"testing"
	"time"
)

func TestCursorRoundTrip(t *testing.T) {
	in := Cursor{CreatedAt: time.Now().UTC().Truncate(time.Second), ID: 42}
	enc, err := Encode(in)
	if err != nil {
		t.Fatalf("encode: %v", err)
	}
	out, err := Decode(enc)
	if err != nil {
		t.Fatalf("decode: %v", err)
	}
	if out.ID != in.ID || !out.CreatedAt.Equal(in.CreatedAt) {
		t.Fatalf("unexpected decode result: %+v", out)
	}
}

func TestParseLimit(t *testing.T) {
	if got := ParseLimit("", 50, 200); got != 50 {
		t.Fatalf("expected default, got %d", got)
	}
	if got := ParseLimit("500", 50, 200); got != 200 {
		t.Fatalf("expected capped max, got %d", got)
	}
}
