package events

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/redis/go-redis/v9"
)

type InvalidationEvent struct {
	Keys []string `json:"keys"`
}

type Invalidator struct {
	redis   *redis.Client
	channel string
}

func NewInvalidator(client *redis.Client, channel string) *Invalidator {
	if channel == "" {
		channel = "cache:invalidate"
	}
	return &Invalidator{redis: client, channel: channel}
}

func (i *Invalidator) Publish(ctx context.Context, keys ...string) error {
	if i.redis == nil || len(keys) == 0 {
		return nil
	}
	b, err := json.Marshal(InvalidationEvent{Keys: keys})
	if err != nil {
		return fmt.Errorf("marshal invalidation event: %w", err)
	}
	return i.redis.Publish(ctx, i.channel, b).Err()
}

func (i *Invalidator) Subscribe(ctx context.Context, consume func([]string) error) error {
	if i.redis == nil {
		return nil
	}
	sub := i.redis.Subscribe(ctx, i.channel)
	defer sub.Close()
	ch := sub.Channel()
	for {
		select {
		case <-ctx.Done():
			return nil
		case msg := <-ch:
			if msg == nil {
				continue
			}
			var ev InvalidationEvent
			if err := json.Unmarshal([]byte(msg.Payload), &ev); err != nil {
				continue
			}
			if err := consume(ev.Keys); err != nil {
				return err
			}
		}
	}
}
