package cache

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

type entry struct {
	Payload []byte    `json:"payload"`
	FreshTo time.Time `json:"fresh_to"`
	StaleTo time.Time `json:"stale_to"`
}

type call struct {
	wg  sync.WaitGroup
	val []byte
	err error
}

type SWRCache struct {
	client *redis.Client
	mu     sync.Mutex
	calls  map[string]*call
}

func NewSWR(client *redis.Client) *SWRCache {
	return &SWRCache{client: client, calls: map[string]*call{}}
}

func (c *SWRCache) GetOrCompute(
	ctx context.Context,
	key string,
	ttl time.Duration,
	stale time.Duration,
	compute func(context.Context) ([]byte, error),
) (payload []byte, cached bool, staleServed bool, err error) {
	now := time.Now().UTC()

	cachedPayload, loadErr := c.client.Get(ctx, key).Bytes()
	if loadErr == nil {
		var e entry
		if err := json.Unmarshal(cachedPayload, &e); err == nil {
			switch {
			case now.Before(e.FreshTo):
				return e.Payload, true, false, nil
			case now.Before(e.StaleTo):
				go c.refresh(context.Background(), key, ttl, stale, compute)
				return e.Payload, true, true, nil
			}
		}
	} else if !errors.Is(loadErr, redis.Nil) {
		return nil, false, false, fmt.Errorf("redis get: %w", loadErr)
	}

	data, err := c.doSingleFlight(ctx, key, compute)
	if err != nil {
		return nil, false, false, err
	}

	if err := c.set(ctx, key, data, ttl, stale); err != nil {
		return nil, false, false, err
	}
	return data, false, false, nil
}

func (c *SWRCache) Invalidate(ctx context.Context, keys ...string) error {
	if len(keys) == 0 {
		return nil
	}
	return c.client.Del(ctx, keys...).Err()
}

func (c *SWRCache) refresh(
	ctx context.Context,
	key string,
	ttl time.Duration,
	stale time.Duration,
	compute func(context.Context) ([]byte, error),
) {
	data, err := c.doSingleFlight(ctx, key, compute)
	if err != nil {
		return
	}
	_ = c.set(ctx, key, data, ttl, stale)
}

func (c *SWRCache) doSingleFlight(ctx context.Context, key string, compute func(context.Context) ([]byte, error)) ([]byte, error) {
	c.mu.Lock()
	if existing, ok := c.calls[key]; ok {
		c.mu.Unlock()
		existing.wg.Wait()
		return existing.val, existing.err
	}
	current := &call{}
	current.wg.Add(1)
	c.calls[key] = current
	c.mu.Unlock()

	current.val, current.err = compute(ctx)
	current.wg.Done()

	c.mu.Lock()
	delete(c.calls, key)
	c.mu.Unlock()
	return current.val, current.err
}

func (c *SWRCache) set(ctx context.Context, key string, payload []byte, ttl, stale time.Duration) error {
	e := entry{
		Payload: payload,
		FreshTo: time.Now().UTC().Add(ttl),
		StaleTo: time.Now().UTC().Add(stale),
	}
	b, err := json.Marshal(e)
	if err != nil {
		return fmt.Errorf("marshal cache entry: %w", err)
	}
	exp := stale
	if exp <= 0 {
		exp = ttl
	}
	if exp <= 0 {
		exp = 30 * time.Second
	}
	if err := c.client.Set(ctx, key, b, exp).Err(); err != nil {
		return fmt.Errorf("redis set: %w", err)
	}
	return nil
}
