package cache

import (
	"context"
	"sync/atomic"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
)

func TestSWRGetOrComputeSingleFlight(t *testing.T) {
	mini, err := miniredis.Run()
	if err != nil {
		t.Fatalf("start miniredis: %v", err)
	}
	defer mini.Close()

	client := redis.NewClient(&redis.Options{Addr: mini.Addr()})
	cache := NewSWR(client)

	var calls int32
	compute := func(context.Context) ([]byte, error) {
		atomic.AddInt32(&calls, 1)
		time.Sleep(20 * time.Millisecond)
		return []byte(`{"ok":true}`), nil
	}

	ctx := context.Background()
	results := make(chan error, 8)
	for i := 0; i < 8; i++ {
		go func() {
			_, _, _, err := cache.GetOrCompute(ctx, "k", 50*time.Millisecond, 200*time.Millisecond, compute)
			results <- err
		}()
	}
	for i := 0; i < 8; i++ {
		if err := <-results; err != nil {
			t.Fatalf("get or compute: %v", err)
		}
	}
	if got := atomic.LoadInt32(&calls); got != 1 {
		t.Fatalf("expected single compute call, got %d", got)
	}
}
