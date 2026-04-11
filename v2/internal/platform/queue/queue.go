package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
)

type TaskStatus string

const (
	TaskQueued    TaskStatus = "queued"
	TaskRunning   TaskStatus = "running"
	TaskCompleted TaskStatus = "completed"
	TaskFailed    TaskStatus = "failed"
)

type Task struct {
	ID        string          `json:"id"`
	Type      string          `json:"type"`
	Payload   json.RawMessage `json:"payload"`
	CreatedAt time.Time       `json:"created_at"`
}

type Status struct {
	State      TaskStatus `json:"state"`
	Error      string     `json:"error,omitempty"`
	FinishedAt time.Time  `json:"finished_at,omitempty"`
}

type Handler func(context.Context, Task) error

type Queue struct {
	ch       chan Task
	handlers map[string]Handler
	status   sync.Map
}

func New(buffer int) *Queue {
	if buffer <= 0 {
		buffer = 512
	}
	return &Queue{
		ch:       make(chan Task, buffer),
		handlers: map[string]Handler{},
	}
}

func (q *Queue) Register(taskType string, h Handler) {
	q.handlers[taskType] = h
}

func (q *Queue) Enqueue(taskType string, payload any) (string, error) {
	h, ok := q.handlers[taskType]
	if !ok || h == nil {
		return "", fmt.Errorf("no handler registered for task type %s", taskType)
	}
	b, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("marshal task payload: %w", err)
	}
	t := Task{ID: uuid.NewString(), Type: taskType, Payload: b, CreatedAt: time.Now().UTC()}
	q.status.Store(t.ID, Status{State: TaskQueued})
	q.ch <- t
	return t.ID, nil
}

func (q *Queue) Start(ctx context.Context, workers int) {
	if workers <= 0 {
		workers = 2
	}
	for i := 0; i < workers; i++ {
		go q.worker(ctx)
	}
}

func (q *Queue) worker(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case task := <-q.ch:
			h := q.handlers[task.Type]
			q.status.Store(task.ID, Status{State: TaskRunning})
			err := h(ctx, task)
			if err != nil {
				q.status.Store(task.ID, Status{State: TaskFailed, Error: err.Error(), FinishedAt: time.Now().UTC()})
				continue
			}
			q.status.Store(task.ID, Status{State: TaskCompleted, FinishedAt: time.Now().UTC()})
		}
	}
}

func (q *Queue) Status(taskID string) (Status, bool) {
	v, ok := q.status.Load(taskID)
	if !ok {
		return Status{}, false
	}
	s, ok := v.(Status)
	return s, ok
}
